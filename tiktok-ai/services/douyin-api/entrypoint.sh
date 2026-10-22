#!/bin/sh
# 包在 Douyin_TikTok_Download_API v4 外面的啟動器：
# 1. 從 /shared/douyin_cookie_header.txt（studio 網頁「⚙️ 抖音 Cookie」存的）把 cookie 寫進 config.yaml
# 2. 啟動服務；cookie 檔變動就自動重啟（它只在啟動時讀 config）
CFG=/app/crawlers/douyin/web/config.yaml
COOKIE=/shared/douyin_cookie_header.txt
[ -f "$CFG.orig" ] || cp "$CFG" "$CFG.orig"

apply_cookie() {
  python3 - "$CFG" "$COOKIE" <<'PY'
import sys, yaml
cfg, ck = sys.argv[1], sys.argv[2]
try:
    cookie = open(ck, encoding="utf-8").read().strip()
except FileNotFoundError:
    cookie = ""
data = yaml.safe_load(open(cfg + ".orig", encoding="utf-8"))
if cookie:
    data["TokenManager"]["douyin"]["headers"]["Cookie"] = cookie
    print(f"[douyin-api] 已套用 cookie（{len(cookie)} 字元）")
else:
    print("[douyin-api] 尚未設定 cookie，使用預設值（抖音多半會失敗）")
yaml.safe_dump(data, open(cfg, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
PY
}

sig() { md5sum "$COOKIE" 2>/dev/null | cut -d' ' -f1; }

while true; do
  apply_cookie
  CUR=$(sig)
  setsid sh ./start.sh &
  PID=$!
  while [ "$(sig)" = "$CUR" ] && kill -0 "$PID" 2>/dev/null; do sleep 5; done
  echo "[douyin-api] cookie 變更或服務退出，重新啟動…"
  kill -TERM -- -"$PID" 2>/dev/null || kill -TERM "$PID" 2>/dev/null
  wait "$PID" 2>/dev/null
  sleep 1
done
