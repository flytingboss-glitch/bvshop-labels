"""① 貼抖音 / TikTok / YouTube 連結 → 下載影片 → 逐字稿 + 原文案。

抓取順序：
1. Douyin_TikTok_Download_API（抖音、TikTok、快手、B 站；compose 內建）
2. yt-dlp（TikTok、YouTube、IG 等備援；抖音近年 yt-dlp 不穩）
逐字稿用 faster-whisper（本機，CPU 也能跑 small 模型）。
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import requests

from . import config

URL_RE = re.compile(r"https?://[^\s一-鿿\"'<>]+")


@dataclass
class SourceVideo:
    url: str
    path: Path
    desc: str = ""
    author: str = ""
    transcript: str = ""
    segments: list[dict] = field(default_factory=list)   # [{start, end, text}]
    duration: float = 0.0
    fetched_by: str = ""


def extract_url(text: str) -> str:
    """抖音分享文字長這樣：『7.12 复制打开抖音，看看… https://v.douyin.com/xxxx/ …』，只要網址。"""
    m = URL_RE.search(text.strip())
    if not m:
        raise ValueError("找不到網址，請貼含 http 的分享連結")
    return m.group(0).rstrip("/。，,)")


def _walk(obj, want: tuple[str, ...]):
    """在任意巢狀 JSON 裡找第一個符合 key 的字串值（API 回傳格式版本差異大，用這招最耐用）。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in want and isinstance(v, str) and v.strip():
                return v
        for v in obj.values():
            r = _walk(v, want)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _walk(v, want)
            if r:
                return r
    return None


def _find_play_url(data) -> str | None:
    # 常見：data.video.play_addr.url_list[0] / data.video.playAddr / data.video.play_addr_h264.url_list
    for key in ("play_addr_h264", "play_addr", "playAddr", "play_url", "bit_rate"):
        node = _walk_node(data, key)
        if isinstance(node, dict):
            lst = node.get("url_list") or node.get("urlList")
            if isinstance(lst, list) and lst:
                return lst[-1] if isinstance(lst[-1], str) else None
        if isinstance(node, str) and node.startswith("http"):
            return node
        if isinstance(node, list) and node and isinstance(node[0], dict):
            inner = node[0].get("play_addr", {})
            lst = inner.get("url_list") if isinstance(inner, dict) else None
            if lst:
                return lst[-1]
    return _walk(data, ("nwm_video_url", "nwm_video_url_HQ", "video_url", "download_addr"))


def _walk_node(obj, key: str):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _walk_node(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _walk_node(v, key)
            if r is not None:
                return r
    return None


def _download(url: str, dst: Path, headers: dict | None = None) -> Path:
    h = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
         "Referer": "https://www.douyin.com/"}
    h.update(headers or {})
    with requests.get(url, headers=h, stream=True, timeout=120, allow_redirects=True) as r:
        r.raise_for_status()
        with open(dst, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    if dst.stat().st_size < 10_000:
        raise RuntimeError("下載到的檔案太小，可能被平台擋了")
    return dst


def fetch_via_douyin_api(url: str, dst: Path) -> SourceVideo:
    api = config.DOUYIN_API_URL.rstrip("/") + "/api/hybrid/video_data"
    r = requests.get(api, params={"url": url, "minimal": "false"}, timeout=60)
    r.raise_for_status()
    data = r.json()
    if data.get("code") not in (None, 200, 0):
        raise RuntimeError(f"Douyin API 回應 {data.get('code')}：{data.get('message') or data.get('msg')}")
    payload = data.get("data", data)
    play = _find_play_url(payload)
    if not play:
        raise RuntimeError("API 回傳裡找不到影片網址（可能需要更新 cookie）")
    _download(play, dst)
    return SourceVideo(url=url, path=dst,
                       desc=_walk(payload, ("desc", "title", "caption")) or "",
                       author=_walk(payload, ("nickname", "author_name", "uniqueId")) or "",
                       fetched_by="douyin_api")


def fetch_via_ytdlp(url: str, dst: Path) -> SourceVideo:
    import yt_dlp  # 延遲載入

    opts = {"outtmpl": str(dst.with_suffix("")) + ".%(ext)s", "format": "bv*[height<=1080]+ba/b[height<=1080]/b",
            "merge_output_format": "mp4", "quiet": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    got = next(dst.parent.glob(dst.stem + ".*"))
    if got != dst:
        got.rename(dst)
    return SourceVideo(url=url, path=dst, desc=(info.get("description") or info.get("title") or ""),
                       author=info.get("uploader") or "", fetched_by="yt-dlp")


def fetch_video(share_text: str, work: Path) -> SourceVideo:
    url = extract_url(share_text)
    work.mkdir(parents=True, exist_ok=True)
    dst = work / "source.mp4"
    errors = []
    for fn in (fetch_via_douyin_api, fetch_via_ytdlp):
        try:
            sv = fn(url, dst)
            sv.duration = probe_duration(dst)
            return sv
        except Exception as e:  # noqa: BLE001
            errors.append(f"{fn.__name__}: {e}")
    raise RuntimeError("抓不到影片。" + " | ".join(errors))


def probe_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out or 0)


def extract_audio(video: Path, wav: Path, sr: int = 16000) -> Path:
    subprocess.run([config.FFMPEG, "-y", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sr),
                    "-c:a", "pcm_s16le", str(wav)], check=True)
    return wav


def transcribe(audio: Path, language: str = "zh") -> tuple[str, list[dict]]:
    """faster-whisper 逐字稿；回傳 (全文, 段落)。沒裝 faster-whisper 時回空字串，流程不中斷。"""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("[sources] 未安裝 faster-whisper，略過逐字稿")
        return "", []
    device = config.WHISPER_DEVICE
    compute = "float16" if device == "cuda" else "int8"
    if device == "auto":
        try:
            import ctranslate2
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:  # noqa: BLE001
            device = "cpu"
        compute = "float16" if device == "cuda" else "int8"
    model = WhisperModel(config.WHISPER_MODEL, device=device, compute_type=compute)
    segs, _ = model.transcribe(str(audio), language=language, vad_filter=True, initial_prompt="繁體中文，台灣用語。")
    segments = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs]
    text = "".join(s["text"] for s in segments)
    try:  # 簡轉繁（whisper 常吐簡體）
        from opencc import OpenCC
        text = OpenCC("s2twp").convert(text)
    except Exception:  # noqa: BLE001
        pass
    return text, segments


def fetch_and_transcribe(share_text: str, work: Path) -> SourceVideo:
    sv = fetch_video(share_text, work)
    wav = extract_audio(sv.path, work / "source_16k.wav")
    sv.transcript, sv.segments = transcribe(wav)
    return sv
