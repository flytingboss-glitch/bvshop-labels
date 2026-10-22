"""② 聲音克隆配音：CosyVoice FastAPI（零樣本，5~10 秒你的錄音即可）。失敗時退回 edge-tts 台灣腔。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import requests

from . import config, tts


def _pcm_to_wav(pcm: bytes, out: Path, sr: int) -> Path:
    subprocess.run([config.FFMPEG, "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", "pipe:0",
                    "-c:a", "pcm_s16le", str(out)], input=pcm, check=True)
    return out


def _prep_reference(ref: Path, out: Path) -> Path:
    """參考音檔：單聲道 16k、去頭尾靜音、最多 15 秒（CosyVoice 建議 3~15 秒乾淨人聲）。"""
    subprocess.run([config.FFMPEG, "-y", "-loglevel", "error", "-i", str(ref), "-vn", "-ac", "1", "-ar", "16000",
                    "-af", "silenceremove=start_periods=1:start_threshold=-40dB:stop_periods=1:stop_threshold=-40dB",
                    "-t", "15", "-c:a", "pcm_s16le", str(out)], check=True)
    return out


def clone_tts(text: str, ref_audio: Path, out_wav: Path, ref_text: str = "", work: Path | None = None) -> Path:
    """用 ref_audio 的聲音唸 text。ref_text = 參考音檔裡講的內容（有給用 zero_shot 更像；沒給用 cross_lingual）。"""
    work = work or out_wav.parent
    ref16 = _prep_reference(ref_audio, work / "ref_16k.wav")
    base = config.COSYVOICE_URL.rstrip("/")
    with open(ref16, "rb") as f:
        files = {"prompt_wav": ("ref.wav", f, "audio/wav")}
        if ref_text.strip():
            r = requests.post(f"{base}/inference_zero_shot", data={"tts_text": text, "prompt_text": ref_text.strip()},
                              files=files, timeout=config.SERVICE_TIMEOUT, stream=True)
        else:
            r = requests.post(f"{base}/inference_cross_lingual", data={"tts_text": text}, files=files,
                              timeout=config.SERVICE_TIMEOUT, stream=True)
        r.raise_for_status()
        pcm = b"".join(r.iter_content(1 << 16))
    if len(pcm) < 1000:
        raise RuntimeError("CosyVoice 回傳空音訊")
    return _pcm_to_wav(pcm, out_wav, config.COSYVOICE_SAMPLE_RATE)


def speak(text: str, out_wav: Path, ref_audio: Path | None = None, ref_text: str = "", work: Path | None = None) -> tuple[Path, str]:
    """統一入口：有參考音檔就克隆，否則 / 失敗時用 edge-tts。回傳 (wav, 使用的後端)。"""
    if ref_audio and Path(ref_audio).exists():
        try:
            return clone_tts(text, Path(ref_audio), out_wav, ref_text, work), "cosyvoice"
        except Exception as e:  # noqa: BLE001
            print(f"[voice] CosyVoice 失敗（{e}），改用 edge-tts")
    mp3 = out_wav.with_suffix(".mp3")
    tts.synthesize(text, mp3)
    subprocess.run([config.FFMPEG, "-y", "-loglevel", "error", "-i", str(mp3), "-ac", "1", "-ar", "24000",
                    "-c:a", "pcm_s16le", str(out_wav)], check=True)
    return out_wav, "edge-tts"
