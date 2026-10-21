"""步驟 3：每個場景一張直式圖片。

後端：
- comfyui      本機 ComfyUI（SDXL / Flux / Z-Image 等），無限量、不花錢，需要 GPU
- pexels       免費圖庫（需免費 API key，台灣可申請）
- pollinations 免費雲端生圖（有速率限制，近期可能需要金鑰）
- placeholder  純本機漸層卡片（永遠可用，拿來測流程）
"""
from __future__ import annotations

import json
import random
import time
import urllib.parse
import uuid
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from . import config

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "C:/Windows/Fonts/msjh.ttc",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _fit_portrait(src: Path, dst: Path) -> None:
    w, h = config.VIDEO_W, config.VIDEO_H
    im = Image.open(src).convert("RGB")
    scale = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    left, top = (im.width - w) // 2, (im.height - h) // 2
    im.crop((left, top, left + w, top + h)).save(dst, quality=92)


# ---------- placeholder ----------
def placeholder(keyword: str, index: int, dst: Path) -> Path:
    w, h = config.VIDEO_W, config.VIDEO_H
    palettes = [((25, 36, 99), (233, 64, 87)), ((16, 94, 84), (248, 196, 113)),
                ((60, 20, 90), (255, 140, 66)), ((10, 60, 110), (120, 220, 200))]
    c1, c2 = palettes[index % len(palettes)]
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        t = y / h
        col = tuple(round(c1[i] * (1 - t) + c2[i] * t) for i in range(3))
        for x in range(w):
            px[x, y] = col
    d = ImageDraw.Draw(im)
    f = _font(140)
    text = keyword[:6] or str(index + 1)
    bbox = d.textbbox((0, 0), text, font=f)
    d.text(((w - bbox[2]) / 2, (h - bbox[3]) / 2 - 80), text, font=f, fill=(255, 255, 255))
    im.save(dst, quality=92)
    return dst


# ---------- pexels ----------
def pexels(query: str, dst: Path) -> Path:
    if not config.PEXELS_API_KEY:
        raise RuntimeError("沒有 PEXELS_API_KEY")
    r = requests.get(
        "https://api.pexels.com/v1/search",
        params={"query": query, "orientation": "portrait", "per_page": 10, "locale": "zh-TW"},
        headers={"Authorization": config.PEXELS_API_KEY}, timeout=30,
    )
    r.raise_for_status()
    photos = r.json().get("photos", [])
    if not photos:
        raise RuntimeError(f"Pexels 找不到：{query}")
    url = random.choice(photos)["src"]["large2x"]
    raw = dst.with_suffix(".raw.jpg")
    raw.write_bytes(requests.get(url, timeout=60).content)
    _fit_portrait(raw, dst)
    raw.unlink(missing_ok=True)
    return dst


# ---------- pollinations ----------
def pollinations(prompt: str, dst: Path) -> Path:
    url = config.POLLINATIONS_URL + urllib.parse.quote(prompt)
    r = requests.get(url, params={"width": config.VIDEO_W, "height": config.VIDEO_H,
                                  "nologo": "true", "seed": random.randint(1, 10**6)}, timeout=120)
    r.raise_for_status()
    raw = dst.with_suffix(".raw.jpg")
    raw.write_bytes(r.content)
    _fit_portrait(raw, dst)
    raw.unlink(missing_ok=True)
    return dst


# ---------- comfyui ----------
def comfyui(prompt: str, dst: Path) -> Path:
    """用 ComfyUI 的 /prompt API 跑一個 text2img 工作流。
    工作流檔案是「API 格式」JSON，裡面可放 {{PROMPT}} {{NEGATIVE}} {{SEED}} {{WIDTH}} {{HEIGHT}} {{CHECKPOINT}} 佔位字。
    """
    tpl = Path(config.COMFYUI_WORKFLOW).read_text(encoding="utf-8")
    filled = (tpl.replace("{{PROMPT}}", json.dumps(prompt, ensure_ascii=False)[1:-1])
                 .replace("{{NEGATIVE}}", "text, watermark, logo, lowres, blurry, deformed")
                 .replace("{{SEED}}", str(random.randint(1, 2**31)))
                 .replace("{{WIDTH}}", str(config.VIDEO_W if config.VIDEO_W <= 1024 else 832))
                 .replace("{{HEIGHT}}", str(config.VIDEO_H if config.VIDEO_H <= 1024 else 1216))
                 .replace("{{CHECKPOINT}}", config.COMFYUI_CHECKPOINT))
    workflow = json.loads(filled)
    client_id = uuid.uuid4().hex
    base = config.COMFYUI_URL.rstrip("/")
    r = requests.post(f"{base}/prompt", json={"prompt": workflow, "client_id": client_id}, timeout=30)
    r.raise_for_status()
    pid = r.json()["prompt_id"]
    deadline = time.time() + config.COMFYUI_TIMEOUT
    while time.time() < deadline:
        h = requests.get(f"{base}/history/{pid}", timeout=30).json()
        if pid in h:
            outputs = h[pid].get("outputs", {})
            for node in outputs.values():
                for img in node.get("images", []):
                    q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img.get("subfolder", ""),
                                                "type": img.get("type", "output")})
                    data = requests.get(f"{base}/view?{q}", timeout=60).content
                    raw = dst.with_suffix(".raw.png")
                    raw.write_bytes(data)
                    _fit_portrait(raw, dst)
                    raw.unlink(missing_ok=True)
                    return dst
            raise RuntimeError("ComfyUI 完成但沒有輸出圖片")
        time.sleep(2)
    raise TimeoutError("ComfyUI 生圖逾時")


def make_image(prompt: str, keyword: str, index: int, dst: Path, backend: str | None = None) -> Path:
    backend = backend or config.IMAGE_BACKEND
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        if backend == "comfyui":
            return comfyui(prompt, dst)
        if backend == "pexels":
            return pexels(keyword or prompt, dst)
        if backend == "pollinations":
            return pollinations(prompt, dst)
    except Exception as e:  # noqa: BLE001
        print(f"[image] {backend} 失敗（{e}），改用 placeholder")
    return placeholder(keyword, index, dst)
