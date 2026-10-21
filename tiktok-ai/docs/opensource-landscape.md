# 全球開源「短影音智能體」調查（2026‑10）

抖音上那些「智能剪片 / 智能生成劇本 / 無限生圖」的智能體，骨子裡幾乎都是下面這些開源專案包一層殼再賣。
以下資料來自各專案 GitHub 首頁（星數為 2026‑10‑21 查詢當下），台灣可直接使用的程度以 ✅ / ⚠️ 標示。

## A. 「一句話成片」：主題 → 劇本 → 配音 → 素材 → 字幕 → 直式影片

| 專案 | ★ | 授權 | 特色 | 台灣可用 | 備註 |
|---|---|---|---|---|---|
| [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | 133k | MIT | 最紅。WebUI + REST API + CLI + Docker。LLM 支援 OpenAI / Claude / Gemini / DeepSeek / Qwen / Ollama；TTS 有 Edge‑TTS（免費）、Azure、ElevenLabs、Kokoro、Chatterbox；素材 Pexels / Pixabay / 本機 / AI 生影片 | ✅ | 最低 4 核 4GB RAM 免 GPU。沒有登入機制，不要直接開到公網 |
| [Pixelle‑Video](https://github.com/AIDC-AI/Pixelle-Video) | 29k | Apache‑2.0 | 阿里國際開源。每句旁白生一張圖（預設 Flux），接 **本機 ComfyUI** 就是「無限生圖」；Edge‑TTS / Index‑TTS 聲音克隆；HTML 模板直/橫/方 | ✅ | 最接近抖音那種「智能體」。全免費組合 = Ollama + 本機 ComfyUI（要 GPU） |
| [NarratoAI](https://github.com/linyqh/NarratoAI) | 11.5k | MIT | 影視解說 / 二創：丟一部片，AI 看懂內容寫解說、自動剪輯、配音、字幕。v0.8.6（2026‑07） | ⚠️ | TTS 偏中國服務（豆包、騰訊），要改 Edge‑TTS 台灣腔。作者警告有人改名在抖音/B站販售 |
| [ShortGPT](https://github.com/RayVentura/ShortGPT) | 8.1k | MIT | 最早的框架之一，Gradio 介面 | ⚠️ | 依賴 OpenAI + ElevenLabs，README 自稱 Experimental，更新慢 |
| [short‑video‑factory](https://github.com/YILS-LIN/short-video-factory) | — | — | 桌面程式（非工程師友善），產品行銷片批量生成 | ✅ | |
| [YumCut](https://github.com/IgorShadurin/app.yumcut.com) / [ai‑shorts‑generator](https://github.com/AbdullahNaveed/ai-shorts-generator) | 小 | MIT | 英文圈的輕量版本，Next.js / Python | ✅ | 拿來讀 code 學流程很適合 |

## B. 「長片切短片」：Podcast / 直播 / 課程 → 爆點 9:16 短片 + 字幕 + 發文文案

| 專案 | ★ | 授權 | 特色 | 台灣可用 | 備註 |
|---|---|---|---|---|---|
| [AutoClip](https://github.com/zhouxiaoka/autoclip) | 9.6k | MIT | 一個連結一鍵出片：切片、字幕、封面、**標題/描述/hashtag 文案**、發布包 ZIP。macOS / Windows 桌面版，Linux 用 Docker。LLM 可接 Ollama | ✅ | 適配抖音、小紅書、TikTok、Reels、Shorts |
| [OpenShorts](https://github.com/mutonby/openshorts) | 6.9k | MIT（cloud/ 目錄另有商業授權） | Opus Clip 替代品：faster‑whisper + Gemini/本機 LLM 找爆點、MediaPipe 人臉追蹤、鉤子字卡、MCP / REST / n8n | ✅ | CPU 8 分鐘片要 5‑8 分鐘；RTX 4060 約 1 分鐘 |
| [HotClip](https://github.com/xixihhhh/hotclip) | 353 | AGPL‑3.0 | 免安裝桌面版（Win / Apple Silicon），本機 SenseVoice / Paraformer 轉寫，Ollama 可全離線，有 Claude Code Agent Skill | ✅ | AGPL：改了拿去賣要開源 |
| [artbyjazi/autoclip](https://github.com/artbyjazi/autoclip) | — | MIT | 全離線（Whisper + Ollama），講者追蹤 | ✅ | |

## C. 「無限生圖 / 生影片」底層

| 專案 | 說明 | 台灣可用 |
|---|---|---|
| [ComfyUI](https://github.com/comfyanonymous/ComfyUI)（GPL‑3.0，115k★） | 本機跑 SDXL / Flux / Z‑Image / Qwen‑Image，**真正無限量、零費用**，但要 NVIDIA 8GB+ VRAM（Flux 建議 12‑24GB） | ✅ |
| Wan 2.x / HunyuanVideo 1.5 / FramePack | 開源文生影片、圖生影片，消費級顯卡可跑但很慢 | ✅ |
| [Pollinations](https://github.com/pollinations/pollinations)（MIT） | 免費雲端生圖 API，2026 年改版後多半要註冊金鑰，有速率限制，**不是無限** | ⚠️ |
| Pexels / Pixabay | 免費圖庫 / 影片庫，免費 API key，MoneyPrinterTurbo 的素材來源 | ✅ |

## D. 配音 / 字幕 / 發布

| 專案 | 說明 | 台灣可用 |
|---|---|---|
| [edge‑tts](https://github.com/rany2/edge-tts) | 微軟 Edge 線上語音，免費免金鑰。台灣腔：`zh-TW-HsiaoChenNeural`（女）、`zh-TW-HsiaoYuNeural`（女）、`zh-TW-YunJheNeural`（男） | ✅ 台灣直連沒問題（中國那邊才會被擋） |
| Kokoro / Index‑TTS / Chatterbox / Fish Audio | 本機 TTS，可聲音克隆 | ✅ |
| faster‑whisper / whisper.cpp / SenseVoice | 本機語音轉字幕 | ✅ |
| [social‑auto‑upload](https://github.com/dreammis/social-auto-upload) / [Postiz](https://github.com/gitroomhq/postiz-app) | 一鍵發 TikTok / 抖音 / IG / YouTube；Postiz 是完整開源社群排程平台 | ✅ |
| [awesome‑ai‑media‑cn](https://github.com/JuneYaooo/awesome-ai-media-cn) | 150+ 專案的中文總表，每週更新，想找更多從這裡 | — |

## 關於「無限量」「無限生圖」的實話

1. **本機跑才是無限**。Ollama（劇本）+ ComfyUI（圖）+ Edge‑TTS（配音）+ FFmpeg（合成）全在自己電腦上，不計次、不收費。代價是要一張 NVIDIA 顯卡（RTX 3060 12GB 二手約 NT$6‑8k 就能跑 SDXL；Flux 建議 4070 Ti Super 16GB 以上）。
2. **雲端「免費無限」都有條件**：Gemini 免費層有每日額度、Pollinations 有速率限制、Pexels 每小時 200 次。抖音那些智能體敢說無限，是因為它們用的是中國便宜的雲端模型 + 自己吸收成本，或根本就是上述開源專案改皮。
3. **沒顯卡的折衷**：劇本用 Gemini 免費層或 Groq 免費層、圖用 Pexels 圖庫、配音用 Edge‑TTS，整套仍是 NT$0，只是圖不是 AI 畫的。

## 合規提醒（TikTok）

TikTok 規定「真實感的 AI 生成影像 / 聲音」要開啟 **AI‑generated content 標籤**，台灣帳號一樣適用；用圖庫素材則不用。拿別人的長片切片（NarratoAI、AutoClip 類）要注意著作權與平台「搬運」判定。
