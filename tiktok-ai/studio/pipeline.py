"""把四個步驟串起來：主題 -> 劇本 -> 配音 -> 圖片 -> 影片。"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Callable

from . import config, images, render, script_gen, tts

Progress = Callable[[str, int], None]


def _job_id() -> str:
    """純 ASCII 檔名，手機瀏覽器 / Windows / 雲端硬碟都不會出問題；標題另存在 .txt。"""
    import uuid
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


def make_video(topic: str, *, scene_count: int = 5, style: str = "", voice: str | None = None,
               image_backend: str | None = None, offline: bool = False, bgm: str | None = None,
               target_seconds: int | None = None, script: script_gen.Script | None = None,
               ref_audio: Path | None = None, ref_text: str = "",
               progress: Progress | None = None) -> dict:
    """topic → 影片。也可直接給 script（例如 ① 從連結改寫出來的劇本）或 ref_audio（用你的聲音講）。"""
    report = progress or (lambda msg, pct: print(f"[{pct:3d}%] {msg}"))
    job_id = _job_id()
    work = config.WORK_DIR / job_id
    work.mkdir(parents=True, exist_ok=True)

    report("生成劇本", 5)
    if script is None:
        script = script_gen.generate_script(topic, scene_count=scene_count, style=style, offline=offline,
                                            target_seconds=target_seconds)
    (work / "script.json").write_text(json.dumps(script.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    scenes, clips, tracks, t = [], [], [], 0.0
    n = len(script.scenes)
    for i, sc in enumerate(script.scenes):
        report(f"場景 {i + 1}/{n}：配音", 10 + int(60 * i / n))
        if ref_audio:
            from . import voice as voice_mod
            voice_mod.speak(sc.narration, work / f"voice_{i:02d}.wav", Path(ref_audio), ref_text, work)
            subprocess.run([config.FFMPEG, "-y", "-loglevel", "error", "-i", str(work / f"voice_{i:02d}.wav"),
                            "-c:a", "libmp3lame", "-q:a", "3", str(work / f"voice_{i:02d}.mp3")], check=True)
        else:
            tts.synthesize(sc.narration, work / f"voice_{i:02d}.mp3", voice=voice)
        dur = tts._probe_duration(work / f"voice_{i:02d}.mp3")
        dur = max(dur, 1.5) + 0.35  # 每句留一點呼吸

        report(f"場景 {i + 1}/{n}：生圖", 12 + int(60 * i / n))
        img = images.make_image(sc.image_prompt or sc.narration, sc.keyword, i, work / f"img_{i:02d}.jpg",
                                backend=image_backend)

        report(f"場景 {i + 1}/{n}：動態化", 15 + int(60 * i / n))
        # 配音補齊到場景長度，讓影像與聲音同長
        padded = work / f"voice_{i:02d}_pad.mp3"
        subprocess.run([config.FFMPEG, "-y", "-loglevel", "error", "-i", str(work / f"voice_{i:02d}.mp3"),
                        "-af", f"apad=whole_dur={dur:.3f}", "-t", f"{dur:.3f}", "-c:a", "libmp3lame", "-q:a", "3",
                        str(padded)], check=True)
        clip = render.image_to_clip(img, dur, work / f"clip_{i:02d}.mp4", i)
        clips.append(clip)
        tracks.append(padded)
        scenes.append({"narration": sc.narration, "start": t, "duration": dur, "image": str(img)})
        t += dur

    report("合成字幕與影片", 80)
    srt = render.write_srt(scenes, work / "subtitles.srt")      # 給剪映 / CapCut 再編輯用
    ass = render.write_ass(scenes, work / "subtitles.ass")      # 燒錄用
    video = render.concat_clips(clips, work / "video_noaudio.mp4")
    voice_all = render.concat_audio(tracks, work / "voice_all.mp3")
    out = config.OUTPUT_DIR / f"{job_id}.mp4"
    render.mux(video, voice_all, ass, out, bgm=bgm or config.BGM_PATH or None)

    caption = f"{script.title}\n\n" + " ".join(script.hashtags)
    (config.OUTPUT_DIR / f"{job_id}.txt").write_text(caption, encoding="utf-8")
    report("完成", 100)
    return {
        "job_id": job_id,
        "title": script.title,
        "hashtags": script.hashtags,
        "script_source": script.source,
        "duration": round(t, 1),
        "video": str(out),
        "caption_file": str(config.OUTPUT_DIR / f"{job_id}.txt"),
        "srt": str(srt),
        "scenes": scenes,
    }
