# MuseTalk 1.5 + HTTP API
# 版本完全照官方 README：Python 3.10、torch 2.0.1、mmcv 2.0.1、mmdet 3.1.0、mmpose 1.1.0。
# 基底用 devel（含 nvcc）：mim 找得到 mmcv 預編譯檔就直接用，找不到也能自己編譯（官方 MuseTalk 映像同樣做法）。
# 之前失敗的原因：torch 版本太新（2.4）與 mmcv 2.0.1 不相容、且 runtime 映像沒有編譯器。
# 模型權重（約 4GB）在第一次啟動時下載到 volume，build 不會因為下載失敗而中斷。
FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-devel

ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1 \
    TORCH_CUDA_ARCH_LIST="8.6;8.9" MMCV_WITH_OPS=1 MAX_JOBS=4
RUN apt-get update && apt-get install -y --no-install-recommends git ffmpeg libgl1 libglib2.0-0 gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone --depth 1 https://github.com/TMElyralab/MuseTalk.git
WORKDIR /app/MuseTalk

# 1) MuseTalk 本體相依（官方 requirements.txt）
RUN pip install -r requirements.txt

# 2) OpenMMLab（官方指定版本）。mmpose 用 --no-deps 避開 chumpy（新版 pip 裝不起來，推論用不到）
RUN pip install -U openmim \
 && mim install mmengine \
 && mim install "mmcv==2.0.1" \
 && mim install "mmdet==3.1.0" \
 && pip install --no-deps mmpose==1.1.0 \
 && pip install json_tricks munkres xtcocotools "scipy<1.12" matplotlib

# 3) API 與下載工具
RUN pip install fastapi==0.110.0 "uvicorn[standard]==0.29.0" python-multipart pyyaml "huggingface_hub[cli]==0.30.2" gdown

COPY api.py /app/api.py
COPY entrypoint.sh /app/entrypoint.sh
ENV MUSETALK_DIR=/app/MuseTalk
EXPOSE 8600
CMD ["sh", "/app/entrypoint.sh"]
