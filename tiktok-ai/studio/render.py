"""步驟 4：字幕 + Ken Burns 推拉 + 合成 1080x1920 直式影片（純 ffmpeg，不用 moviepy）。"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import config


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _split_caption(text: str, max_chars: int) -> list[str]:
    """中文沒有空白可切，先按標點切，再按長度硬切。"""
    import re
    parts = [p for p in re.split(r"(?<=[，。！？、；：,.!?])", text) if p.strip()]
    chunks: list[str] = []
    for p in parts:
        p = p.strip()
        while len(p) > max_chars:
            chunks.append(p[:max_chars])
            p = p[max_chars:]
        if p:
            chunks.append(p)
    return chunks or [text]


def write_srt(scenes: list[dict], path: Path) -> Path:
    """scenes: [{narration, start, duration}] -> 把每句依字數比例切成多段字幕。"""
    lines, idx, t = [], 1, 0.0
    for sc in scenes:
        chunks = _split_caption(sc["narration"], config.SUBTITLE_MAX_CHARS)
        total_chars = sum(len(c) for c in chunks) or 1
        cursor = sc["start"]
        for c in chunks:
            d = sc["duration"] * len(c) / total_chars
            end = cursor + d
            lines.append(f"{idx}\n{_srt_time(cursor)} --> {_srt_time(max(end - 0.05, cursor + 0.2))}\n{c.strip('，。、；：,.')}\n")
            cursor = end
            idx += 1
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _ass_time(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6_000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def write_ass(scenes: list[dict], path: Path) -> Path:
    """ASS 字幕：明確寫 PlayResX/Y，字級與位置才會跟 1080x1920 對齊（SRT+force_style 會以 288 高度縮放）。"""
    w, h = config.VIDEO_W, config.VIDEO_H
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{config.SUBTITLE_FONT},{config.SUBTITLE_FONT_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
        f"-1,0,0,0,100,100,1,0,1,4,2,2,60,60,{int(h * 0.17)},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = []
    for sc in scenes:
        chunks = _split_caption(sc["narration"], config.SUBTITLE_MAX_CHARS)
        total = sum(len(c) for c in chunks) or 1
        cur = sc["start"]
        for c in chunks:
            d = sc["duration"] * len(c) / total
            end = max(cur + d - 0.05, cur + 0.2)
            text = c.strip("，。、；：,.")
            lines.append(f"Dialogue: 0,{_ass_time(cur)},{_ass_time(end)},Default,,0,0,0,,{{\\fad(80,80)}}{text}")
            cur += d
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return path


def image_to_clip(image: Path, duration: float, out: Path, index: int) -> Path:
    w, h, fps = config.VIDEO_W, config.VIDEO_H, config.VIDEO_FPS
    frames = max(int(round(duration * fps)), fps)
    # 偶數場景推近、奇數場景拉遠，畫面才不單調；先放大 2 倍再 zoompan 可減少抖動
    if index % 2 == 0:
        z = "min(zoom+0.0012,1.25)"
    else:
        z = "if(eq(on,1),1.25,max(zoom-0.0012,1.0))"
    vf = (
        f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},"
        f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps},"
        f"format=yuv420p"
    )
    subprocess.run(
        [config.FFMPEG, "-y", "-loglevel", "error", "-i", str(image), "-vf", vf, "-frames:v", str(frames),
         "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)],
        check=True,
    )
    return out


def concat_clips(clips: list[Path], out: Path) -> Path:
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
    subprocess.run([config.FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(out)], check=True)
    return out


def concat_audio(tracks: list[Path], out: Path) -> Path:
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{t.as_posix()}'\n" for t in tracks), encoding="utf-8")
    subprocess.run([config.FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:a", "libmp3lame", "-q:a", "3", str(out)], check=True)
    return out


def mux(video: Path, voice: Path, subs: Path, out: Path, bgm: str | None = None) -> Path:
    sub_path = subs.as_posix().replace(":", r"\:").replace("'", r"\'")
    vf = f"ass='{sub_path}'" if subs.suffix == ".ass" else f"subtitles='{sub_path}'"
    cmd = [config.FFMPEG, "-y", "-loglevel", "error", "-i", str(video), "-i", str(voice)]
    if bgm and Path(bgm).exists():
        cmd += ["-stream_loop", "-1", "-i", bgm,
                "-filter_complex", f"[2:a]volume={config.BGM_VOLUME}[bg];[1:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    return out
