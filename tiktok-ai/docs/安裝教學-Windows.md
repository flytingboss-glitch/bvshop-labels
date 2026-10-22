# 安裝教學（Windows 筆電 + RTX 4050 6GB，零基礎版）

整個過程大約 40 分鐘，其中 30 分鐘是在等下載。只要會複製貼上就能完成。

> **懶人路線**：不想一步步做，就只做這件事：到 GitHub 專案頁 `tiktok-ai/安裝.bat` → 右上角「Download raw file」圖示 → 存到桌面 → 按兩下 → 視窗按「是」。
> 它會自動完成第 1 到第 4 步（含裝 Docker、下載專案、啟動、下載模型、防火牆）。中途要求重新開機時，重開後再按兩下一次就會續跑。
> 之後需要的第 5 步（抖音 cookie）與第 6 步（聲音 + 對嘴）仍照下面做。

---

## 第 0 步：確認電腦條件

- Windows 10 21H2 以上或 Windows 11（按 `Win + R` 輸入 `winver` 可看版本）
- 硬碟空間至少 **40 GB**（模型檔很大）
- NVIDIA 顯示卡驅動更新到最新：打開 **NVIDIA App**（或 GeForce Experience）→ 驅動程式 → 更新
- 筆電**插電**，電源模式調「最佳效能」

---

## 第 1 步：安裝 Docker Desktop（一次性，約 10 分鐘）

Docker 是「把一整套軟體打包好，一鍵開關」的工具，之後所有東西都靠它跑。

1. 到 <https://www.docker.com/products/docker-desktop/> 下載 **Docker Desktop for Windows**，安裝，一路「下一步」。
2. 安裝時勾選 **Use WSL 2 instead of Hyper-V**（預設就是勾的）。
3. 重新開機。
4. 打開 Docker Desktop，看到左下角綠色 **Engine running** 就成功。第一次打開會要你登入，可以按 Skip 跳過。
5. 讓 Docker 看得到顯示卡：打開「開始」→ 輸入 `PowerShell` → 右鍵「以系統管理員身分執行」，貼上：
   ```powershell
   wsl --update
   wsl --install -d Ubuntu
   ```
   跑完後重新開機一次。
6. 驗證顯卡：在 PowerShell 貼上
   ```powershell
   docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
   ```
   看到一張表，裡面有 **NVIDIA GeForce RTX 4050 Laptop GPU** 就成功。看不到的話，先確認 NVIDIA 驅動是最新的，再重做第 5 步。

---

## 第 2 步：下載這個專案（2 分鐘）

1. 到 <https://github.com/flytingboss-glitch/bvshop-labels> → 上方分支下拉選 `claude/tiktok-ai-video-editing-uqcqwh` → 綠色 **Code** 按鈕 → **Download ZIP**。
2. 解壓縮到你想放的地方，例如 `D:\tiktok-ai`。裡面要看到 `tiktok-ai` 資料夾。
3. 進到 `D:\tiktok-ai\tiktok-ai` 這一層（裡面有 `docker-compose.yml`）。
4. 把 `.env.example` 複製一份，改名成 `.env`（檔名前面有一個點）。
   > 看不到副檔名？檔案總管 → 檢視 → 勾「副檔名」。

---

## 第 3 步：第一次啟動（約 15 分鐘，都在等下載）

1. 在 `D:\tiktok-ai\tiktok-ai` 資料夾的空白處 **Shift + 右鍵 → 在這裡開啟 PowerShell 視窗**（或在路徑列輸入 `powershell` 按 Enter）。
2. 貼上並按 Enter：
   ```powershell
   docker compose up -d --build
   ```
   第一次會跑很久（下載基底映像、安裝套件），看到一排 `Started` 或 `Running` 就完成。
3. 下載劇本模型（約 3 GB）：
   ```powershell
   docker exec ollama ollama pull gemma3:4b
   ```
4. 打開瀏覽器輸入 <http://localhost:7860>，看到「🎬 短影音智能體」就成功了。

以後要開：打開 Docker Desktop → 左側 Containers → `tiktok-ai` 旁邊按 ▶。要關：按 ■。不需要再打指令。

---

## 第 4 步：手機也要能用（3 分鐘）

**同一個 Wi‑Fi**：
1. 電腦 PowerShell 輸入 `ipconfig`，找「無線區域網路介面卡 Wi‑Fi」底下的 **IPv4 位址**，例如 `192.168.1.23`。
2. 手機瀏覽器打開 `http://192.168.1.23:7860`。
3. 如果打不開，Windows 防火牆擋了：PowerShell（系統管理員）貼上
   ```powershell
   New-NetFirewallRule -DisplayName "tiktok-ai" -Direction Inbound -LocalPort 7860 -Protocol TCP -Action Allow
   ```

**出門在外也要用**：電腦和手機都裝 [Tailscale](https://tailscale.com/download)（免費），同一個帳號登入，手機改用 Tailscale 顯示的電腦 IP（100.x.x.x）加 `:7860`。不要把 7860 直接開到公網，這個頁面沒有密碼。

---

## 第 5 步：讓「① 貼抖音連結」能用（一次性）

抖音要有 cookie 才給影片（不一定要登入，但登入最穩）：

1. 電腦瀏覽器打開 <https://www.douyin.com>（建議登入）。
2. 按 `F12` → 上方 **Network（網路）** → 重新整理頁面 → 點清單裡任一個 `douyin.com` 的請求 → 右側 **Headers** 往下找 **Cookie:** → 右鍵 **Copy value**。
3. 回到 `http://localhost:7860` 的 ① 分頁，展開「⚙️ 抖音 Cookie」，貼上 → 儲存。看到「✔ 已設定」即可。

Cookie 幾週會過期，再出現「需要 cookie」時重貼一次。TikTok、YouTube 連結不用這步。

---

## 第 6 步：讓「③ 我的聲音 + 對嘴」能用（一次性，約 20 分鐘下載）

```powershell
docker compose --profile voice up -d --build
```
會下載 CosyVoice（約 2 GB）與 MuseTalk（約 4 GB）權重。完成後 Docker Desktop 會多出 `cosyvoice` 和 `musetalk` 兩個容器。

6 GB 顯卡的使用習慣：**要做 ③ 的時候才開這兩個**，做完在 Docker Desktop 把它們按 ■ 停掉，顯存才夠給 Ollama 和生圖。

---

## 第 7 步：（選配）本機無限生圖

```powershell
docker compose --profile gpu up -d
```
然後把模型檔放到 `D:\tiktok-ai\tiktok-ai\comfyui\ComfyUI\models\checkpoints\`。6 GB 顯卡建議：
- **Z‑Image Turbo GGUF Q4**（約 4 GB，品質好、速度快）或
- **SDXL** `sd_xl_base_1.0.safetensors`（6.9 GB，解析度要降到 768）

再把 `.env` 的 `IMAGE_BACKEND=comfyui`，`docker compose restart studio`。
沒顯存壓力又想要真實照片：改用 `IMAGE_BACKEND=pexels`，到 <https://www.pexels.com/api/> 免費申請 key 填進 `PEXELS_API_KEY`。

---

## 網頁怎麼操作（每天用的部分）

### ① 連結 → 文案
1. 手機抖音 / TikTok 按「分享」→「複製連結」，整段貼進第一格。
2. 選 15 / 30 / 60 / 90 秒。
3. 按「抓文案並改寫」，等 1~3 分鐘。
4. 畫面會顯示：原文案、逐字稿、**新劇本**（已改成台灣用語、去掉違規字，並列出改了哪些）。
5. 按「帶到 ②」做圖文影片，或「帶到 ③」用你的聲音講。

### ② 文案 → 影片
1. 輸入主題（或已經從 ① 帶過來的劇本）。
2. 選秒數、配音（台灣腔三選一）、圖片來源。
3. 想用自己的聲音：上傳 5~15 秒錄音，填一下錄音裡說了什麼。
4. 按「開始生成」，1~3 分鐘後直接預覽、下載 mp4；下方有標題和 hashtag，貼到 TikTok 文案欄。

### ③ 我的影片 + 我的聲音
1. 上傳你沒講話的影片（正面、臉清楚、光線均勻）。
2. 貼上要講的文案（可從 ① 帶過來）。
3. 上傳你的錄音（安靜環境、只有你的聲音、5~15 秒）。
4. 勾「MuseTalk 對嘴」→ 按「生成我的影片」。30 秒影片約 3~8 分鐘。
5. 發 TikTok 時記得開「AI 生成內容」標籤。

---

## 常見問題

| 狀況 | 怎麼辦 |
|---|---|
| 網頁顯示「劇本來源：模板」 | Ollama 還沒載完模型，或 `.env` 的 `LLM_MODEL` 打錯。PowerShell 跑 `docker exec ollama ollama list` 看有沒有 `gemma3:4b` |
| ① 顯示「抓不到影片」或「Fresh cookies are needed」 | 抖音 cookie 沒設或過期，重做第 5 步（在網頁 ① 分頁貼）；TikTok 連結請確認是公開影片 |
| ③ 顯示「對嘴：未對嘴」 | `musetalk` 容器沒開或跑失敗。Docker Desktop 點 `musetalk` 看 Logs，把紅字貼給我 |
| 配音是無聲 | edge‑tts 連不上微軟（防火牆或公司網路）。換個網路再試 |
| 顯示 CUDA out of memory | 顯存不夠：停掉 `comfyui` 或 `musetalk` 其中一個，或把 Ollama 換成 `gemma3:1b` |
| `ports are not available … forbidden by its access permissions` | Windows 把那個埠保留走了。重新按兩下「安裝.bat」會自動改用別的埠；手動的話在 `.env` 把 `STUDIO_PORT=7860` 改成 `17860`，再 `docker compose up -d` |
| 想全部重來 | PowerShell：`docker compose down` 再 `docker compose up -d` |

遇到任何錯誤，把紅字訊息整段貼給我就好。
