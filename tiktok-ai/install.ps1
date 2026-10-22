# ============================================================
#  tiktok-ai 一鍵安裝（Windows）
#  用法：在「安裝.bat」上按兩下（會自動要求系統管理員權限）
#  會做：裝 Docker Desktop → 啟用 WSL2 → 下載專案 → 建 .env → 啟動容器 → 下載 LLM → 開防火牆 → 開瀏覽器
#  需要你親手做的只有：Docker 安裝完的「重新開機」，重開後再按一次「安裝.bat」即可續跑
# ============================================================
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Repo      = "flytingboss-glitch/bvshop-labels"
$Branch    = "claude/tiktok-ai-video-editing-uqcqwh"
$Install   = if ($env:TIKTOK_AI_DIR) { $env:TIKTOK_AI_DIR } else { "$env:USERPROFILE\tiktok-ai" }
$Model     = "gemma3:4b"
$Port      = 7860

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    ✔ $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    ! $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host "`n✘ $msg" -ForegroundColor Red; Read-Host "按 Enter 結束"; exit 1 }

# Windows（Hyper-V / WSL）會隨機保留一些埠，被保留的埠 Docker 開不起來（"forbidden by its access permissions"）
function Get-ExcludedRanges {
    $r = @()
    try {
        netsh interface ipv4 show excludedportrange protocol=tcp 2>$null | ForEach-Object {
            if ($_ -match '^\s*(\d+)\s+(\d+)') { $r += ,@([int]$matches[1], [int]$matches[2]) }
        }
    } catch {}
    return $r
}
function Test-PortFree($port, $ranges) {
    foreach ($x in $ranges) { if ($port -ge $x[0] -and $port -le $x[1]) { return $false } }
    try { if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { return $false } } catch {}
    return $true
}
function Get-FreePort($preferred, $ranges) {
    foreach ($p in @($preferred, ($preferred + 10000), ($preferred + 20000)) + (20000..20100)) {
        if ($p -lt 65535 -and (Test-PortFree $p $ranges)) { return $p }
    }
    return $preferred
}
function Set-EnvValue($file, $key, $value) {
    $lines = Get-Content $file -Encoding UTF8
    if ($lines -match "^$key=") { $lines = $lines -replace "^$key=.*$", "$key=$value" } else { $lines += "$key=$value" }
    Set-Content $file $lines -Encoding UTF8
}

# ---------- 0. 權限與環境 ----------
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Fail "請用「安裝.bat」啟動（需要系統管理員權限）" }
if ($PSVersionTable.PSVersion.Major -lt 5) { Fail "PowerShell 版本太舊，請更新 Windows" }
Step "檢查顯示卡"
try { $gpu = (nvidia-smi --query-gpu=name,memory.total --format=csv,noheader) 2>$null; Ok "NVIDIA：$gpu" }
catch { Warn "找不到 nvidia-smi，請先更新 NVIDIA 驅動（NVIDIA App → 驅動程式）。沒有 GPU 也能做 ①②，只是沒有生圖與對嘴。" }

# ---------- 1. WSL2 ----------
Step "啟用 WSL2（Docker 需要）"
$wslOk = $false
try { wsl --status *> $null; $wslOk = ($LASTEXITCODE -eq 0) } catch {}
if (-not $wslOk) {
    dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart | Out-Null
    dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart | Out-Null
    try { wsl --install --no-distribution } catch {}
    Warn "WSL 剛啟用，需要重新開機。重開機後請再按一次「安裝.bat」續跑。"
    $r = Read-Host "現在重新開機？(y/n)"
    if ($r -eq "y") { Restart-Computer -Force }
    exit 0
}
try { wsl --update *> $null } catch {}
Ok "WSL2 就緒"

# ---------- 2. Docker Desktop ----------
Step "檢查 Docker Desktop"
$dockerExe = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
if (-not (Get-Command docker -ErrorAction SilentlyContinue) -and -not (Test-Path $dockerExe)) {
    Ok "下載並安裝 Docker Desktop（約 600MB，幾分鐘）"
    $dl = "$env:TEMP\DockerDesktopInstaller.exe"
    Invoke-WebRequest -Uri "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe" -OutFile $dl -UseBasicParsing
    Start-Process -FilePath $dl -ArgumentList "install","--quiet","--accept-license","--backend=wsl-2" -Wait
    Warn "Docker 安裝完成，需要重新開機（或登出再登入）。重開機後請再按一次「安裝.bat」續跑。"
    $r = Read-Host "現在重新開機？(y/n)"
    if ($r -eq "y") { Restart-Computer -Force }
    exit 0
}
if (-not (Get-Process "Docker Desktop" -ErrorAction SilentlyContinue)) {
    Ok "啟動 Docker Desktop…"
    Start-Process $dockerExe
}
$env:Path += ";$env:ProgramFiles\Docker\Docker\resources\bin"
$tries = 0
while ($true) {
    try { docker info *> $null; if ($LASTEXITCODE -eq 0) { break } } catch {}
    $tries++
    if ($tries -gt 60) { Fail "Docker 一直沒起來。請手動打開 Docker Desktop，看到左下角綠色 Engine running 後再按一次「安裝.bat」。" }
    Write-Host "    等待 Docker 啟動…($tries)" ; Start-Sleep 5
}
Ok "Docker 可用"

# ---------- 3. 下載專案 ----------
Step "下載專案到 $Install"
New-Item -ItemType Directory -Force -Path $Install | Out-Null
$zip = "$env:TEMP\tiktok-ai.zip"
Invoke-WebRequest -Uri "https://github.com/$Repo/archive/refs/heads/$Branch.zip" -OutFile $zip -UseBasicParsing
$tmpx = "$env:TEMP\tiktok-ai-extract"
if (Test-Path $tmpx) { Remove-Item $tmpx -Recurse -Force }
Expand-Archive -Path $zip -DestinationPath $tmpx -Force
$src = Get-ChildItem $tmpx -Directory | Select-Object -First 1
Copy-Item "$($src.FullName)\tiktok-ai\*" $Install -Recurse -Force
Ok "專案已就位"

# ---------- 4. .env ----------
Set-Location $Install
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Ok "已建立 .env（預設：gemma3:4b、Edge-TTS 台灣腔、純色卡片圖）" } else { Ok ".env 已存在，保留你的設定" }

Step "挑選沒被 Windows 保留的埠"
$ranges = Get-ExcludedRanges
$Port = Get-FreePort 7860 $ranges
$OllamaPort = Get-FreePort 11434 $ranges
Set-EnvValue ".env" "STUDIO_PORT" $Port
Set-EnvValue ".env" "OLLAMA_PORT" $OllamaPort
Set-EnvValue ".env" "COMFYUI_PORT" (Get-FreePort 8188 $ranges)
Ok "網頁埠 $Port、Ollama 埠 $OllamaPort"

# ---------- 5. 啟動 ----------
Step "啟動容器（第一次要下載映像與套件，約 5~15 分鐘）"
docker compose down 2>$null | Out-Null
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { Fail "docker compose 失敗，請把上面的紅字貼給 Claude" }
Ok "studio / ollama / douyin-api 已啟動"

Step "下載劇本模型 $Model（約 3GB）"
docker exec ollama ollama pull $Model
if ($LASTEXITCODE -ne 0) { Warn "模型下載失敗，稍後可手動執行：docker exec ollama ollama pull $Model" } else { Ok "模型就緒" }

# ---------- 6. 防火牆（手機連線用）----------
Step "開放手機連線（同一個 Wi-Fi）"
if (-not (Get-NetFirewallRule -DisplayName "tiktok-ai" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "tiktok-ai" -Direction Inbound -LocalPort $Port -Protocol TCP -Action Allow | Out-Null
}
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.*" -and $_.InterfaceAlias -notlike "*vEthernet*" -and $_.InterfaceAlias -notlike "*Docker*" } | Select-Object -First 1).IPAddress
Ok "手機瀏覽器打開：http://${ip}:$Port"

# ---------- 7. 完成 ----------
Step "完成！"
Write-Host @"

    電腦：http://localhost:$Port
    手機：http://${ip}:$Port   （同一個 Wi-Fi）

    之後開關：打開 Docker Desktop → Containers → tiktok-ai 旁的 ▶ / ■
    要貼抖音連結：先登入 douyin.com 複製 cookie 到 $Install\douyin-config\config.yaml（見 docs\安裝教學-Windows.md 第 5 步）
    要用自己的聲音+對嘴：在 $Install 開 PowerShell 執行 docker compose --profile voice up -d --build

"@
Start-Process "http://localhost:$Port"
Read-Host "按 Enter 關閉"
