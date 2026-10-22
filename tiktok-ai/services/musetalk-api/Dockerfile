# MuseTalk 1.5 + HTTP API。首次 build 會下載約 4GB 權重。
FROM pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime
RUN apt-get update && apt-get install -y --no-install-recommends git ffmpeg libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN git clone --depth 1 https://github.com/TMElyralab/MuseTalk.git
WORKDIR /app/MuseTalk
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-deps "git+https://github.com/open-mmlab/mmpose.git@main" || true \
    && pip install --no-cache-dir openmim && mim install "mmengine" "mmcv>=2.0.1" "mmdet>=3.1.0" "mmpose>=1.1.0" \
    && pip install --no-cache-dir fastapi uvicorn python-multipart pyyaml huggingface_hub
# 權重：官方腳本（需要網路，約 4GB）。若失敗，請依 README 手動放到 models/ 後 rebuild。
RUN sh ./download_weights.sh || echo "download_weights.sh 失敗，請手動放模型"
COPY api.py /app/api.py
ENV MUSETALK_DIR=/app/MuseTalk
EXPOSE 8600
CMD ["uvicorn", "api:app", "--app-dir", "/app", "--host", "0.0.0.0", "--port", "8600"]
