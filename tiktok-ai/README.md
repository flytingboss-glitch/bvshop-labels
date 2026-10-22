# 🎬 tiktok‑ai：台灣可用的 TikTok 短影音智能體

三個分頁、三件事，手機與電腦瀏覽器都能用，全部元件開源、可完全本機執行、不計次：

| 分頁 | 做什麼 |
|---|---|
| **① 連結 → 文案** | 貼抖音 / TikTok / YouTube 分享連結 → 下載 → faster‑whisper 逐字稿 → LLM 改寫成**合規、台灣用語、指定秒數**的新劇本（附合規修改說明） |
| **② 文案 → 影片** | 主題或 ① 的劇本 → 配音（台灣腔，或**你的聲音**）→ 圖片（可本機無限生圖）→ 動態字幕 → 1080×1920 直式影片 |
| **③ 我的影片 + 我的聲音** | 上傳沒講話的影片 + 5~15 秒錄音 → CosyVoice 克隆你的聲音唸文案 → MuseTalk 對嘴 → 字幕 → 成片 |

長度可選 **15 / 30 / 60 / 90 秒**（LLM 依秒數控制字數，約每秒 4 字），輸出 1080p；要 4K 改 `.env` 的 `VIDEO_W/VIDEO_H` 即可。

抖音上那些「智能剪片 / 智能劇本 / 無限生圖」的智能體，底層幾乎都是開源專案；
完整調查（19 個專案、星數、授權、台灣可用性）見 **[docs/opensource-landscape.md](docs/opensource-landscape.md)**。

## 架構：三件事，三個開源專案

| 需求 | 用什麼 | 本專案的位置 |
|---|---|---|
| ① 文案 / 劇本 → 成片 | **本專案 `studio/`**（自己寫的、最輕量、台灣化）或 MoneyPrinterTurbo（133k★，功能最全） | `docker compose up -d` |
| ② 長片 → 爆點短片 + 字幕 + 發文文案 | **AutoClip**（9.6k★，MIT） | `--profile extra` |
| ③ 無限生圖 | **ComfyUI**（本機 SDXL / Flux / Z‑Image） | `--profile gpu` |
| 劇本 LLM | **Ollama**（本機免費）或 Gemini / OpenAI 任何相容 API | compose 內建 |
| 台灣腔配音 | **edge‑tts**（免費免金鑰：曉臻 / 曉雨 / 雲哲） | 內建 |

```
手機 / 電腦瀏覽器 ──► studio (Flask, :7860) ──► Ollama (:11434) 劇本
                                          ├──► edge-tts            配音 + 時間軸
                                          ├──► ComfyUI (:8188) / Pexels / Pollinations  圖片
                                          └──► FFmpeg              Ken Burns + ASS 字幕 + 合成
```

> **最快的方法（Windows）**：下載 [`安裝.bat`](安裝.bat) 放到桌面，按兩下，跳出的視窗按「是」。它會自動裝 Docker、下載專案、啟動、下載模型、開防火牆、開瀏覽器；中途要求重新開機時重開後再按一次即可。
>
> **想了解每一步？** 看 **[docs/安裝教學-Windows.md](docs/安裝教學-Windows.md)**：Docker 安裝、顯卡設定、手機連線、抖音 cookie、每個分頁怎麼按，含常見問題表。

## 你的機器：RTX 4050 Laptop 6GB 的建議設定

6GB 顯存可以做完 ①②③，但要挑小模型，而且**生圖與對嘴不要同時跑**：

| 元件 | 建議 | 原因 |
|---|---|---|
| 劇本 LLM | Ollama `gemma3:4b`（或 `qwen2.5:7b` 會部分落到 CPU，慢但可用） | 7B Q4 約 4.7GB，和其他服務搶顯存 |
| 聲音克隆 | `CosyVoice2-0.5B`（.env 預設） | 0.5B 模型，約 2‑3GB |
| 對嘴 | **MuseTalk 1.5 + fp16**（compose 已設） | 官方實測 4GB 顯卡可跑；LatentSync 需 8GB 以上，跑不動 |
| 生圖 | ComfyUI + **Z‑Image Turbo GGUF Q3/Q4** 或 SDXL 768px | Flux 要 12GB 以上 |
| 逐字稿 | faster‑whisper `small`（CPU 也行） | |
| 筆電注意 | 插電、效能模式；8 秒對嘴影片約 3‑5 分鐘 | 筆電 4050 功耗受限 |

啟動順序建議：平常只開 `docker compose up -d`（① + ②，Ollama 吃 GPU）；要做 ③ 時 `docker compose --profile voice up -d`，做完 `docker compose stop cosyvoice musetalk` 把顯存還回來。

## 5 分鐘上手（電腦不用顯卡也能跑 ①②）

```bash
cd tiktok-ai
cp .env.example .env               # 預設：Ollama 劇本 + Edge-TTS 台灣腔 + 純色卡片圖
docker compose up -d --build
docker exec ollama ollama pull gemma3:4b      # 第一次：下載劇本模型（約 3GB）
```
打開 `http://localhost:7860`，輸入主題、按「開始生成」，1‑3 分鐘後可直接在網頁預覽、下載 mp4，旁邊有標題與 hashtag 文案。

**手機使用**：同一個 Wi‑Fi 打開 `http://<電腦IP>:7860`。出門在外想用，裝 [Tailscale](https://tailscale.com)（免費）在手機和電腦上，網址改成 Tailscale IP 即可；不要直接把 7860 開到公網（沒有登入機制）。

### ① 抖音連結需要 cookie
`douyin-api`（Evil0ctal/Douyin_TikTok_Download_API v4）解析抖音前要填一次你的抖音網頁 cookie：
用瀏覽器登入 douyin.com → F12 → Network 任一請求複製 `Cookie` → 貼到 `douyin-config/config.yaml` 的 `cookie:` 欄 → `docker compose restart douyin-api`。
TikTok / YouTube 連結不需要，會自動走 yt‑dlp 備援。

### ③ 聲音克隆 + 對嘴
```bash
docker compose --profile voice up -d --build     # 首次 build 會下載 CosyVoice（~2GB）與 MuseTalk（~4GB）權重，需要一點時間
```
- 錄音：安靜環境、只有你的聲音、5~15 秒、講一段自然的話；在網頁上傳後填「錄音裡說的內容」會更像。
- 影片：正面、臉占畫面 1/3 以上、光線均勻、25fps 最好；MuseTalk 只改嘴型，頭部大動作仍會跟原片。
- 沒開 GPU 服務時，③ 會退回「只換音軌 + 字幕」，流程不中斷。
- 合規：克隆聲音與 AI 對嘴的影片，TikTok 要求開啟「AI 生成內容」標籤，且只能用你自己的聲音與臉。

### 不用 Docker（純 Python）

```bash
pip install -r studio/requirements.txt          # 另需 ffmpeg 與中文字型（Noto Sans CJK TC / 文泉驛）
python -m studio.server                         # 網頁版
python -m studio.cli "台北三家必吃早餐" --seconds 30    # 命令列版；--voice-sample me.wav 用你的聲音
python -m studio.cli "測試" --offline --images placeholder   # 不連任何雲端，驗證環境
```

## 圖片來源怎麼選（.env 的 `IMAGE_BACKEND`）

| 值 | 費用 | 需要 | 說明 |
|---|---|---|---|
| `comfyui` | 0、**無限** | NVIDIA 8GB+ VRAM | `docker compose --profile gpu up -d`，把 `sd_xl_base_1.0.safetensors`（或 Z‑Image / Flux）放進 `comfyui/ComfyUI/models/checkpoints/`，工作流範本在 `studio/workflows/sdxl_text2img.json`，可換成你自己從 ComfyUI 匯出的 API 格式 JSON |
| `pexels` | 0 | 免費 API key（[pexels.com/api](https://www.pexels.com/api/)） | 真實照片，沒顯卡的最佳選擇 |
| `pollinations` | 0 | 可能需註冊金鑰 | 雲端 AI 生圖，有速率限制 |
| `placeholder` | 0 | 無 | 漸層卡片 + 關鍵字，用來測流程 |

## 劇本 LLM 怎麼選（.env 的 `LLM_*`）

- **本機免費**：`LLM_BASE_URL=http://ollama:11434/v1`、`LLM_MODEL=qwen2.5:7b`（繁中最順）。
- **雲端免費層**：Gemini `https://generativelanguage.googleapis.com/v1beta/openai/` + `gemini-2.5-flash`；Groq 也可。
- 任何 OpenAI 相容端點都能用，提示詞已要求「台灣用語、口語、第一句鉤子、最後 CTA」。
- LLM 連不到時會自動退回模板劇本，流程不會中斷（網頁上會標示「模板」）。

## 進階：功能更全的開源專案（同一個 compose）

```bash
docker compose --profile extra up -d
```
- **MoneyPrinterTurbo** `http://localhost:8501`：Pexels 影片素材混剪、多種字幕樣式、批量生成、REST API。
- **AutoClip** `http://localhost:3000`：丟長片（或 YouTube 連結），自動切 10 支短片、字幕、封面、發文文案。

兩者都讀同一份 `.env`（Pexels key、LLM 設定），想深入可直接看它們的 README。

## 產出

- `output/<時間>-<id>.mp4`：1080×1920 / 30fps / H.264 + AAC，已燒字幕，可直接上 TikTok。
- `output/<時間>-<id>.txt`：標題 + hashtag，貼到 TikTok 文案欄。
- `work/<id>/subtitles.srt`：字幕檔，想在 CapCut（剪映國際版）再加特效可匯入。
- `work/<id>/script.json`：AI 劇本（可改完重跑）。

## 服務一覽（docker compose）

| 服務 | 埠 | profile | 用途 |
|---|---|---|---|
| studio | 7860 | 預設 | 本專案網頁 / API |
| ollama | 11434 | 預設 | 劇本 LLM |
| douyin-api | 8081 | 預設 | ① 連結解析 |
| comfyui | 8188 | gpu | 本機生圖 |
| cosyvoice | 50000 | voice | ② ③ 聲音克隆 |
| musetalk | 8600 | voice | ③ 對嘴（`services/musetalk-api/`，本專案包的 HTTP 殼） |
| moneyprinterturbo / autoclip | 8501 / 3000 | extra | 進階工具 |

## 已知限制 / 下一步

- 開發用的 sandbox 無法連外也沒有 GPU：FFmpeg 合成、ASS 字幕、三個分頁的 API、備援路徑（模板劇本、無聲音軌、只換音軌）全部實測通過；edge‑tts、CosyVoice、MuseTalk、Douyin API 的實際串接是依各專案的介面文件寫的，第一次在你電腦上跑若有錯誤訊息，貼給我即可調整。
- `services/musetalk-api` 的 Docker 映像是本專案自行包裝，MuseTalk 的 mmpose 相依在不同 CUDA 版本上偶爾要手動調整。
- 之後可加：Whisper 逐字卡拉 OK 字幕、Pexels **影片**素材（目前是照片 + Ken Burns）、Postiz 自動排程發 TikTok、多帳號矩陣。
