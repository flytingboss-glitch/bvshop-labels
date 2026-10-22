"""手機 / 電腦都能用的網頁介面（Flask）。

python -m studio.server  ->  http://<你的電腦IP>:7860
手機在同一個 Wi-Fi 打開這個網址就能用；出門在外用 Tailscale 或 Cloudflare Tunnel 連回家。

分頁：
  ① 連結 → 文案      貼抖音 / TikTok 連結，抓逐字稿，改寫成合規、台灣化、指定秒數的劇本
  ② 文案 → 影片      主題或 ① 的劇本 → 配音（可用你的聲音）→ 圖 → 字幕 → 直式影片
  ③ 我的影片 + 我的聲音  上傳沒講話的影片 + 10 秒錄音 → 克隆配音 + 對嘴
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

from . import config, script_gen, sources
from .dub import dub_video
from .pipeline import make_video

app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 ** 3
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()

VOICES = [
    ("zh-TW-HsiaoChenNeural", "曉臻（女・台灣）"),
    ("zh-TW-HsiaoYuNeural", "曉雨（女・台灣）"),
    ("zh-TW-YunJheNeural", "雲哲（男・台灣）"),
]
IMAGE_BACKENDS = [
    ("placeholder", "純色卡片（測試用，永遠可用）"),
    ("comfyui", "ComfyUI 本機生圖（無限量，需 GPU）"),
    ("pexels", "Pexels 免費圖庫（需免費 API key）"),
    ("pollinations", "Pollinations 雲端生圖"),
]
ALLOWED_AUDIO = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".webm", ".mp4"}
ALLOWED_VIDEO = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def _new_job(kind: str, **extra) -> str:
    job_id = uuid.uuid4().hex[:10]
    with LOCK:
        JOBS[job_id] = {"id": job_id, "kind": kind, "status": "queued", "percent": 0, "message": "排隊中",
                        "created": time.time(), **extra}
    return job_id


def _set(job_id: str, **kw) -> None:
    with LOCK:
        JOBS[job_id].update(**kw)


def _progress(job_id: str):
    return lambda msg, pct: _set(job_id, status="running", message=msg, percent=pct)


def _run(job_id: str, fn, *args, **kwargs) -> None:
    try:
        result = fn(*args, **kwargs)
        _set(job_id, status="done", percent=100, message="完成", **result)
    except Exception as e:  # noqa: BLE001
        _set(job_id, status="error", message=f"失敗：{e}")


def _spawn(job_id: str, fn, *args, **kwargs) -> None:
    threading.Thread(target=_run, args=(job_id, fn, *args), kwargs=kwargs, daemon=True).start()


def _bool(v) -> bool:
    return str(v or "").lower() in ("1", "true", "on", "yes")


def _voice_path(voice_id: str | None) -> Path | None:
    if not voice_id:
        return None
    for p in config.UPLOAD_DIR.glob(f"voice_{voice_id}.*"):
        return p
    return None


# ---------------- pages ----------------
@app.get("/")
def index():
    return render_template("index.html", voices=VOICES, backends=IMAGE_BACKENDS, durations=config.DURATION_PRESETS,
                           default_backend=config.IMAGE_BACKEND, llm=f"{config.LLM_MODEL} @ {config.LLM_BASE_URL}")


# ---------------- ① 連結 → 文案 ----------------
def _extract_job(job_id: str, share_text: str, target_seconds: int, style: str, offline: bool,
                 upload: Path | None = None, desc: str = "") -> dict:
    report = _progress(job_id)
    work = config.WORK_DIR / f"src-{job_id}"
    work.mkdir(parents=True, exist_ok=True)
    if upload is not None:
        report("讀取上傳的影片", 10)
        dst = work / "source.mp4"
        upload.replace(dst)
        sv = sources.from_upload(dst, desc)
    else:
        report("下載影片", 10)
        sv = sources.fetch_video(share_text, work)
    report("逐字稿（faster-whisper）", 40)
    try:
        wav = sources.extract_audio(sv.path, work / "source_16k.wav")
        sv.transcript, sv.segments = sources.transcribe(wav)
    except Exception as e:  # noqa: BLE001  影片沒有音軌（純音樂 / 無聲）時，改用原文案改寫
        print(f"[extract] 無法取音訊：{e}")
    report("改寫成合規劇本", 75)
    script = script_gen.rewrite_from_transcript(sv.transcript, sv.desc, target_seconds, style, offline=offline)
    (work / "script.json").write_text(json.dumps(script.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"source_url": sv.url, "fetched_by": sv.fetched_by, "author": sv.author, "desc": sv.desc,
            "source_duration": sv.duration, "transcript": sv.transcript, "script": script.to_dict(),
            "source_video": f"/work/src-{job_id}/source.mp4"}


@app.post("/api/extract")
def api_extract():
    data = request.get_json(silent=True) or request.form
    share = (data.get("url") or "").strip()
    f = request.files.get("video")
    has_file = bool(f and f.filename)
    if has_file and Path(f.filename).suffix.lower() not in ALLOWED_VIDEO:
        return jsonify({"error": "請上傳 mp4 / mov 影片"}), 400
    if not share and not has_file:
        return jsonify({"error": "請貼上分享連結，或上傳影片"}), 400
    job_id = _new_job("extract", url=share or (f.filename if has_file else ""))
    upload = None
    if has_file:
        upload = config.UPLOAD_DIR / f"src_{job_id}{Path(f.filename).suffix.lower()}"
        f.save(upload)
    # 分享文字裡 # 之前的部分就是原文案，上傳時拿來當 desc
    desc = re.sub(r"https?://\S+.*$", "", share).strip() if share else ""
    _spawn(job_id, _extract_job, job_id, share, int(data.get("target_seconds") or 30),
           (data.get("style") or "").strip(), _bool(data.get("offline")), upload, desc)
    return jsonify({"id": job_id})


@app.get("/api/settings/douyin_cookie")
def get_cookie():
    return jsonify(sources.cookie_status())


@app.post("/api/settings/douyin_cookie")
def set_cookie():
    data = request.get_json(silent=True) or request.form
    try:
        sources.save_cookie(data.get("cookie") or "")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(sources.cookie_status())


# ---------------- 聲音樣本 ----------------
@app.post("/api/voices")
def api_voices():
    f = request.files.get("audio")
    if not f or Path(f.filename).suffix.lower() not in ALLOWED_AUDIO:
        return jsonify({"error": "請上傳 wav / mp3 / m4a 錄音（5~15 秒，安靜環境、只有你的聲音）"}), 400
    vid = uuid.uuid4().hex[:8]
    dst = config.UPLOAD_DIR / f"voice_{vid}{Path(f.filename).suffix.lower()}"
    f.save(dst)
    return jsonify({"voice_id": vid, "name": f.filename})


# ---------------- ② 文案 → 影片 ----------------
@app.post("/api/jobs")
def create_job():
    data = request.get_json(silent=True) or request.form
    topic = (data.get("topic") or "").strip()
    script_json = data.get("script")
    script = None
    if script_json:
        try:
            d = json.loads(script_json) if isinstance(script_json, str) else script_json
            script = script_gen.Script(title=d.get("title") or topic or "影片",
                                       scenes=[script_gen.Scene(**{k: s.get(k, "") for k in ("narration", "image_prompt", "keyword")})
                                               for s in d.get("scenes", []) if s.get("narration")],
                                       hashtags=d.get("hashtags", []), source=d.get("source", "edited"))
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": f"劇本 JSON 格式錯誤：{e}"}), 400
        if not script.scenes:
            return jsonify({"error": "劇本沒有任何場景"}), 400
    if not topic and script is None:
        return jsonify({"error": "請輸入主題或提供劇本"}), 400
    target = int(data.get("target_seconds") or 0) or None
    job_id = _new_job("video", topic=topic or (script.title if script else ""))
    _spawn(job_id, lambda: _video_job(job_id, topic, script, target, data))
    return jsonify({"id": job_id})


def _video_job(job_id: str, topic: str, script, target, data) -> dict:
    r = make_video(topic or (script.title if script else "影片"), target_seconds=target,
                   scene_count=max(3, min(int(data.get("scenes") or 5), 18)), style=(data.get("style") or "").strip(),
                   voice=data.get("voice") or None, image_backend=data.get("images") or None,
                   offline=_bool(data.get("offline")), script=script,
                   ref_audio=_voice_path(data.get("voice_id")), ref_text=(data.get("ref_text") or "").strip(),
                   progress=_progress(job_id))
    return {"video_url": f"/output/{Path(r['video']).name}", "caption_url": f"/output/{Path(r['caption_file']).name}",
            "title": r["title"], "hashtags": r["hashtags"], "duration": r["duration"], "script_source": r["script_source"]}


# ---------------- ③ 我的影片 + 我的聲音 ----------------
@app.post("/api/dub")
def api_dub():
    f = request.files.get("video")
    if not f or Path(f.filename).suffix.lower() not in ALLOWED_VIDEO:
        return jsonify({"error": "請上傳 mp4 / mov 影片"}), 400
    text = (request.form.get("script") or "").strip()
    if not text:
        return jsonify({"error": "請貼上要講的文案"}), 400
    job_id = _new_job("dub", topic=text[:30])
    vpath = config.UPLOAD_DIR / f"video_{job_id}{Path(f.filename).suffix.lower()}"
    f.save(vpath)
    ref = _voice_path(request.form.get("voice_id"))
    ref_text = (request.form.get("ref_text") or "").strip()
    lipsync = _bool(request.form.get("lipsync", "1"))

    def job():
        r = dub_video(vpath, text, ref, ref_text=ref_text, lipsync=lipsync, job_id=f"dub-{job_id}",
                      progress=_progress(job_id))
        return {"video_url": f"/output/{Path(r['video']).name}", "duration": r["duration"],
                "voice_backend": r["voice_backend"], "lipsync_backend": r["lipsync_backend"]}
    _spawn(job_id, job)
    return jsonify({"id": job_id})


# ---------------- 共用 ----------------
@app.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    with LOCK:
        job = JOBS.get(job_id)
    return (jsonify(job), 200) if job else (jsonify({"error": "not found"}), 404)


@app.get("/api/jobs")
def list_jobs():
    with LOCK:
        return jsonify(sorted(JOBS.values(), key=lambda j: j["created"]))


@app.get("/output/<path:name>")
def output(name: str):
    return send_from_directory(config.OUTPUT_DIR, name)


@app.get("/work/<path:name>")
def work_file(name: str):
    return send_from_directory(config.WORK_DIR, name)


def main() -> None:
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "7860")), threaded=True)


if __name__ == "__main__":
    main()
