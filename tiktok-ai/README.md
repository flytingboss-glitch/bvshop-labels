# 🎬 tiktok‑ai：台灣可用的 TikTok 短影音智能體

一句話 → AI 劇本 → 台灣腔配音 → 圖片（可本機無限生圖）→ 動態字幕 → 1080×1920 直式影片。
手機、電腦都能用（瀏覽器開網頁），全部元件開源、可完全本機執行、不計次。

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

## 5 分鐘上手（電腦不用顯卡也能跑）

```bash
cd tiktok-ai
cp .env.example .env               # 預設：Ollama 劇本 + Edge-TTS 台灣腔 + 純色卡片圖
docker compose up -d --build
docker exec ollama ollama pull qwen2.5:7b     # 第一次：下載劇本模型（約 4.7GB；記憶體不夠改 gemma3:4b）
```
打開 `http://localhost:7860`，輸入主題、按「開始生成」，1‑3 分鐘後可直接在網頁預覽、下載 mp4，旁邊有標題與 hashtag 文案。

**手機使用**：同一個 Wi‑Fi 打開 `http://<電腦IP>:7860`。出門在外想用，裝 [Tailscale](https://tailscale.com)（免費）在手機和電腦上，網址改成 Tailscale IP 即可；不要直接把 7860 開到公網（沒有登入機制）。

### 不用 Docker（純 Python）

```bash
pip install -r studio/requirements.txt          # 另需 ffmpeg 與中文字型（Noto Sans CJK TC / 文泉驛）
python -m studio.server                         # 網頁版
python -m studio.cli "台北三家必吃早餐" --scenes 5     # 命令列版
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

## 已知限制 / 下一步

- 這個 sandbox 無法連外，所以 edge‑tts 與 LLM 在本機端到端只以「無聲 + 模板劇本」驗證過；FFmpeg 合成、ASS 字幕、網頁 API 全部實測通過。
- 之後可加：BGM 自動選曲、Whisper 逐字卡拉 OK 字幕、Pexels **影片**素材（目前是照片 + Ken Burns）、Postiz 自動排程發 TikTok。
