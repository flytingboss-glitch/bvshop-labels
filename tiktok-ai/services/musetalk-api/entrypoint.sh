#!/bin/sh
# 第一次啟動下載 MuseTalk 權重到 /app/MuseTalk/models（掛 volume，下次不用再下載）
set -e
cd /app/MuseTalk
M=models
need() { [ ! -s "$1" ]; }
mkdir -p $M/musetalk $M/musetalkV15 $M/syncnet $M/dwpose $M/face-parse-bisent $M/sd-vae $M/whisper
HF="huggingface-cli download --local-dir"
export HF_ENDPOINT="${HF_ENDPOINT:-https://huggingface.co}"

if need $M/musetalkV15/unet.pth; then
  echo "[musetalk] 下載模型權重（約 4GB，只有第一次）…"
  $HF $M TMElyralab/MuseTalk musetalk/musetalk.json musetalk/pytorch_model.bin musetalkV15/musetalk.json musetalkV15/unet.pth
fi
need $M/sd-vae/diffusion_pytorch_model.bin && $HF $M/sd-vae stabilityai/sd-vae-ft-mse config.json diffusion_pytorch_model.bin
need $M/whisper/pytorch_model.bin && $HF $M/whisper openai/whisper-tiny config.json pytorch_model.bin preprocessor_config.json
need $M/dwpose/dw-ll_ucoco_384.pth && $HF $M/dwpose yzd-v/DWPose dw-ll_ucoco_384.pth
need $M/syncnet/latentsync_syncnet.pt && $HF $M/syncnet ByteDance/LatentSync latentsync_syncnet.pt
if need $M/face-parse-bisent/79999_iter.pth; then
  gdown --id 154JgKpzCPW82qINcVieuPH3fZ2e0P812 -O $M/face-parse-bisent/79999_iter.pth \
    || echo "[musetalk] ! 79999_iter.pth 從 Google Drive 下載失敗，請手動下載放到 musetalk-models/face-parse-bisent/"
fi
need $M/face-parse-bisent/resnet18-5c106cde.pth && curl -L https://download.pytorch.org/models/resnet18-5c106cde.pth -o $M/face-parse-bisent/resnet18-5c106cde.pth
echo "[musetalk] 權重就緒，啟動 API :8600"
exec uvicorn api:app --app-dir /app --host 0.0.0.0 --port 8600
