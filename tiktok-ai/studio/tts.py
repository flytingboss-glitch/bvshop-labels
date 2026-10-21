"""步驟 2：旁白配音。預設 edge-tts（免費、免金鑰、有台灣腔），失敗時退回無聲音軌。"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from . import config


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def _estimate_seconds(text: str) -> float:
    # 中文口語約每秒 4~4.5 字
    return max(1.5, len(text) / 4.2 + 0.4)


def _silent(text: str, out: Path) -> float:
    secs = _estimate_seconds(text)
    subprocess.run(
        [config.FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", f"{secs:.2f}", "-c:a", "libmp3lame", "-q:a", "4", str(out)],
        check=True,
    )
    return secs


async def _edge(text: str, out: Path, voice: str, rate: str) -> None:
    import edge_tts  # 延遲載入，沒安裝時其他後端仍可用

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(out))


def synthesize(text: str, out: Path, voice: str | None = None) -> float:
    """把 text 轉成 out（mp3），回傳秒數。"""
    out.parent.mkdir(parents=True, exist_ok=True)
    voice = voice or config.TTS_VOICE
    if config.TTS_BACKEND == "edge":
        try:
            asyncio.run(_edge(text, out, voice, config.TTS_RATE))
            if out.exists() and out.stat().st_size > 0:
                return _probe_duration(out)
            raise RuntimeError("edge-tts 輸出為空")
        except Exception as e:  # noqa: BLE001
            print(f"[tts] edge-tts 失敗（{e}），改用無聲音軌")
    return _silent(text, out)
