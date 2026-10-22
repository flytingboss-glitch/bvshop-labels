"""② 我的無聲影片 + 我的聲音 + 文案 → 用我的聲音講話、嘴型對上的影片。

流程：文案 → 克隆配音（CosyVoice）→ 對嘴（MuseTalk API）→ 字幕 → 1080x1920 輸出。
MuseTalk 不在（沒 GPU）時退回「只換音軌」：影片仍會配上你的聲音與字幕，只是嘴型不會動。
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import requests

from . import config, render, sources, voice


def _fit_video(src: Path, dst: Path, seconds: float) -> Path:
    """裁成 9:16、1080x1920、25fps（MuseTalk 以 25fps 訓練），長度補到 seconds（短就正反循環、長就裁掉）。"""
    w, h = config.VIDEO_W, config.VIDEO_H
    dur = sources.probe_duration(src)
    base_vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=25,format=yuv420p"
    if dur >= seconds:
        cmd = [config.FFMPEG, "-y", "-loglevel", "error", "-i", str(src), "-t", f"{seconds:.3f}", "-an",
               "-vf", base_vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(dst)]
    else:
        # 來回播放（正放+倒放）避免跳接，直到夠長
        loops = int(seconds // max(dur, 0.5)) + 1
        cmd = [config.FFMPEG, "-y", "-loglevel", "error", "-i", str(src), "-an",
               "-filter_complex", f"[0:v]{base_vf},split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0,loop=loop={loops}:size=32767:start=0,trim=duration={seconds:.3f},setpts=PTS-STARTPTS[v]",
               "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(dst)]
    subprocess.run(cmd, check=True)
    return dst


def _lipsync(video: Path, audio: Path, out: Path) -> Path:
    base = config.MUSETALK_URL.rstrip("/")
    with open(video, "rb") as v, open(audio, "rb") as a:
        r = requests.post(f"{base}/lipsync", files={"video": ("in.mp4", v, "video/mp4"), "audio": ("in.wav", a, "audio/wav")},
                          timeout=config.SERVICE_TIMEOUT, stream=True)
    r.raise_for_status()
    with open(out, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            f.write(chunk)
    if out.stat().st_size < 10_000:
        raise RuntimeError("MuseTalk 回傳空影片")
    return out


def _script_to_scenes(text: str, total: float) -> list[dict]:
    """整段文案依句子字數比例切時間軸，給字幕用。"""
    parts = [p.strip() for p in re.split(r"(?<=[。！？!?\n])", text) if p.strip()]
    chars = sum(len(p) for p in parts) or 1
    t, scenes = 0.0, []
    for p in parts:
        d = total * len(p) / chars
        scenes.append({"narration": p, "start": t, "duration": d})
        t += d
    return scenes


def dub_video(video_in: Path, script_text: str, ref_audio: Path | None, *, ref_text: str = "",
              lipsync: bool = True, job_id: str, progress=None, bgm: str | None = None) -> dict:
    report = progress or (lambda m, p: print(f"[{p:3d}%] {m}"))
    work = config.WORK_DIR / job_id
    work.mkdir(parents=True, exist_ok=True)
    script_text = script_text.strip()
    if not script_text:
        raise ValueError("文案是空的")

    report("克隆配音", 10)
    wav, voice_backend = voice.speak(script_text, work / "voice.wav", ref_audio, ref_text, work)
    total = sources.probe_duration(wav) + 0.4

    report("整理影片（9:16、25fps、對齊長度）", 30)
    fitted = _fit_video(video_in, work / "fitted.mp4", total)

    synced, lipsync_backend = None, "none"
    if lipsync:
        report("MuseTalk 對嘴中（6GB 顯卡約 1 分鐘影片 / 5 分鐘）", 45)
        try:
            synced = _lipsync(fitted, wav, work / "synced.mp4")
            lipsync_backend = "musetalk"
        except Exception as e:  # noqa: BLE001
            print(f"[dub] 對嘴失敗（{e}），改為只換音軌")
    if synced is None:
        synced = fitted

    report("字幕與合成", 80)
    scenes = _script_to_scenes(script_text, total)
    ass = render.write_ass(scenes, work / "subtitles.ass")
    render.write_srt(scenes, work / "subtitles.srt")
    out = config.OUTPUT_DIR / f"{job_id}.mp4"
    render.mux(synced, wav, ass, out, bgm=bgm or config.BGM_PATH or None)
    (config.OUTPUT_DIR / f"{job_id}.txt").write_text(script_text, encoding="utf-8")
    report("完成", 100)
    return {"job_id": job_id, "video": str(out), "duration": round(total, 1), "voice_backend": voice_backend,
            "lipsync_backend": lipsync_backend, "caption_file": str(config.OUTPUT_DIR / f"{job_id}.txt")}
