@echo off
chcp 65001 >nul
title tiktok-ai 一鍵安裝
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo 需要系統管理員權限，請在跳出的視窗按「是」...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
cd /d "%~dp0"
if not exist "%~dp0install.ps1" (
  echo 正在下載安裝腳本...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -UseBasicParsing -Uri https://raw.githubusercontent.com/flytingboss-glitch/bvshop-labels/claude/tiktok-ai-video-editing-uqcqwh/tiktok-ai/install.ps1 -OutFile \"%~dp0install.ps1\""
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
