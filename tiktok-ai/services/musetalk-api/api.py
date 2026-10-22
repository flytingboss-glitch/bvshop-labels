"""把 MuseTalk 1.5 的命令列包成 HTTP：POST /lipsync (video, audio) -> mp4。
給 studio/dub.py 呼叫。單工（一次一支），6GB 顯卡請用 --use_float16。
"""
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

MUSETALK_DIR = Path(os.environ.get("MUSETALK_DIR", "/app/MuseTalk"))
VERSION = os.environ.get("MUSETALK_VERSION", "v15")
EXTRA = os.environ.get("MUSETALK_EXTRA_ARGS", "--use_float16 --batch_size 4")
app = FastAPI(title="MuseTalk API")
LOCK = threading.Lock()


@app.get("/health")
def health():
    return {"ok": True, "version": VERSION}


@app.post("/lipsync")
def lipsync(video: UploadFile = File(...), audio: UploadFile = File(...)):
    job = uuid.uuid4().hex[:8]
    tmp = Path(tempfile.mkdtemp(prefix=f"mt_{job}_"))
    vpath, apath = tmp / "input.mp4", tmp / "speech.wav"
    with open(vpath, "wb") as f:
        shutil.copyfileobj(video.file, f)
    with open(apath, "wb") as f:
        shutil.copyfileobj(audio.file, f)
    cfg = tmp / "task.yaml"
    cfg.write_text(yaml.safe_dump({"task_0": {"video_path": str(vpath), "audio_path": str(apath), "result_name": "out.mp4"}}))
    result_dir = tmp / "results"
    unet = "models/musetalkV15/unet.pth" if VERSION == "v15" else "models/musetalk/pytorch_model.bin"
    unet_cfg = "models/musetalkV15/musetalk.json" if VERSION == "v15" else "models/musetalk/config.json"
    cmd = ["python", "-m", "scripts.inference", "--inference_config", str(cfg), "--result_dir", str(result_dir),
           "--unet_model_path", unet, "--unet_config", unet_cfg, "--version", VERSION, *EXTRA.split()]
    with LOCK:
        proc = subprocess.run(cmd, cwd=MUSETALK_DIR, capture_output=True, text=True)
    out = result_dir / VERSION / "out.mp4"
    if proc.returncode != 0 or not out.exists():
        shutil.rmtree(tmp, ignore_errors=True)
        raise HTTPException(500, f"MuseTalk 失敗：{proc.stderr[-2000:]}")
    return FileResponse(str(out), media_type="video/mp4", filename="lipsync.mp4",
                        background=None)
