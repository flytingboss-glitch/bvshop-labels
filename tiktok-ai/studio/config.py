"""集中設定：全部可用環境變數覆寫，方便 Docker / 本機 / 手機遠端使用。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path(os.environ.get("STUDIO_OUTPUT_DIR", BASE_DIR.parent / "output"))
WORK_DIR = Path(os.environ.get("STUDIO_WORK_DIR", BASE_DIR.parent / "work"))

# ---- LLM（劇本生成）：任何 OpenAI 相容端點都可以 ----
# 本機免費：Ollama  -> http://localhost:11434/v1  model=qwen2.5:7b / gemma3:4b
# 雲端：Gemini      -> https://generativelanguage.googleapis.com/v1beta/openai/  model=gemini-2.5-flash
#       OpenAI/Groq/DeepSeek 等照各家文件填 base_url 即可
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen2.5:7b")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "ollama")
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "180"))

# ---- TTS（配音）：edge-tts 免費、免金鑰，台灣腔三個聲音 ----
TTS_BACKEND = os.environ.get("TTS_BACKEND", "edge")          # edge | silent
TTS_VOICE = os.environ.get("TTS_VOICE", "zh-TW-HsiaoChenNeural")  # zh-TW-HsiaoYuNeural / zh-TW-YunJheNeural(男)
TTS_RATE = os.environ.get("TTS_RATE", "+8%")

# ---- 圖片素材：comfyui（本機無限生成）| pexels（免費圖庫）| pollinations | placeholder ----
IMAGE_BACKEND = os.environ.get("IMAGE_BACKEND", "placeholder")
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://localhost:8188")
COMFYUI_WORKFLOW = os.environ.get("COMFYUI_WORKFLOW", str(BASE_DIR / "workflows" / "sdxl_text2img.json"))
COMFYUI_CHECKPOINT = os.environ.get("COMFYUI_CHECKPOINT", "sd_xl_base_1.0.safetensors")
COMFYUI_TIMEOUT = int(os.environ.get("COMFYUI_TIMEOUT", "600"))
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
POLLINATIONS_URL = os.environ.get("POLLINATIONS_URL", "https://image.pollinations.ai/prompt/")

# ---- 影片輸出 ----
VIDEO_W = int(os.environ.get("VIDEO_W", "1080"))
VIDEO_H = int(os.environ.get("VIDEO_H", "1920"))
VIDEO_FPS = int(os.environ.get("VIDEO_FPS", "30"))
SUBTITLE_FONT = os.environ.get("SUBTITLE_FONT", "WenQuanYi Zen Hei")  # 或 Noto Sans CJK TC
SUBTITLE_FONT_SIZE = int(os.environ.get("SUBTITLE_FONT_SIZE", "64"))
SUBTITLE_MAX_CHARS = int(os.environ.get("SUBTITLE_MAX_CHARS", "14"))
BGM_PATH = os.environ.get("BGM_PATH", "")   # 可選：背景音樂 mp3
BGM_VOLUME = float(os.environ.get("BGM_VOLUME", "0.12"))
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

for d in (OUTPUT_DIR, WORK_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---- ① 貼抖音 / TikTok 連結 → 抓影片與文案 ----
# Douyin_TikTok_Download_API v4（docker compose 內建，port 8081）；TikTok / YouTube 另有 yt-dlp 備援
DOUYIN_API_URL = os.environ.get("DOUYIN_API_URL", "http://localhost:8081")
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")        # tiny/base/small/medium；6GB 顯卡 small 很夠
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "auto")        # auto | cuda | cpu
UPLOAD_DIR = Path(os.environ.get("STUDIO_UPLOAD_DIR", BASE_DIR.parent / "uploads"))
COOKIE_FILE = UPLOAD_DIR / "douyin_cookies.txt"          # Netscape 格式，給 yt-dlp
COOKIE_HEADER_FILE = UPLOAD_DIR / "douyin_cookie_header.txt"  # 一行 header 字串，給 douyin-api 容器（它會自動重啟套用）

# ---- ② 聲音克隆（CosyVoice FastAPI）與對嘴（MuseTalk API）----
COSYVOICE_URL = os.environ.get("COSYVOICE_URL", "http://localhost:50000")
COSYVOICE_SAMPLE_RATE = int(os.environ.get("COSYVOICE_SAMPLE_RATE", "24000"))   # CosyVoice2/3 = 24000，300M = 22050
MUSETALK_URL = os.environ.get("MUSETALK_URL", "http://localhost:8600")
SERVICE_TIMEOUT = int(os.environ.get("SERVICE_TIMEOUT", "1800"))

# ---- ③ 目標秒數 → 字數 ----
CHARS_PER_SECOND = float(os.environ.get("CHARS_PER_SECOND", "4.0"))   # 中文口語約每秒 4 字
SECONDS_PER_SCENE = float(os.environ.get("SECONDS_PER_SCENE", "5.0"))
DURATION_PRESETS = (15, 30, 60, 90)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
