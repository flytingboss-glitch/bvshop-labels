"""手機 / 電腦都能用的網頁介面（Flask）。

python -m studio.server  ->  http://<你的電腦IP>:7860
手機在同一個 Wi-Fi 打開這個網址就能用；出門在外用 Tailscale 或 Cloudflare Tunnel 連回家。
"""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

from . import config
from .pipeline import make_video

app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
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


def _run(job_id: str, params: dict) -> None:
    def progress(msg: str, pct: int) -> None:
        with LOCK:
            JOBS[job_id].update(status="running", message=msg, percent=pct)

    try:
        result = make_video(params["topic"], scene_count=params["scenes"], style=params["style"],
                            voice=params["voice"], image_backend=params["images"],
                            offline=params["offline"], progress=progress)
        with LOCK:
            JOBS[job_id].update(status="done", percent=100, message="完成",
                                video_url=f"/output/{Path(result['video']).name}",
                                caption_url=f"/output/{Path(result['caption_file']).name}",
                                title=result["title"], hashtags=result["hashtags"],
                                duration=result["duration"], script_source=result["script_source"])
    except Exception as e:  # noqa: BLE001
        with LOCK:
            JOBS[job_id].update(status="error", message=f"失敗：{e}")


@app.get("/")
def index():
    return render_template("index.html", voices=VOICES, backends=IMAGE_BACKENDS,
                           default_backend=config.IMAGE_BACKEND, llm=f"{config.LLM_MODEL} @ {config.LLM_BASE_URL}")


@app.post("/api/jobs")
def create_job():
    data = request.get_json(silent=True) or request.form
    topic = (data.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "請輸入主題"}), 400
    params = {
        "topic": topic,
        "scenes": max(3, min(int(data.get("scenes") or 5), 12)),
        "style": (data.get("style") or "").strip(),
        "voice": data.get("voice") or None,
        "images": data.get("images") or None,
        "offline": str(data.get("offline", "")).lower() in ("1", "true", "on", "yes"),
    }
    job_id = uuid.uuid4().hex[:10]
    with LOCK:
        JOBS[job_id] = {"id": job_id, "status": "queued", "percent": 0, "message": "排隊中", "topic": topic}
    threading.Thread(target=_run, args=(job_id, params), daemon=True).start()
    return jsonify({"id": job_id})


@app.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    with LOCK:
        job = JOBS.get(job_id)
    return (jsonify(job), 200) if job else (jsonify({"error": "not found"}), 404)


@app.get("/api/jobs")
def list_jobs():
    with LOCK:
        return jsonify(sorted(JOBS.values(), key=lambda j: j["id"]))


@app.get("/output/<path:name>")
def output(name: str):
    return send_from_directory(config.OUTPUT_DIR, name)


def main() -> None:
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "7860")), threaded=True)


if __name__ == "__main__":
    main()
