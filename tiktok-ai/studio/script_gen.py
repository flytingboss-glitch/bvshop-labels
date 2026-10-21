"""步驟 1：主題 -> 短影片劇本（JSON）。

走任何 OpenAI 相容 API（Ollama / Gemini / OpenAI / Groq ...）。
連不到 LLM 時自動退回「模板劇本」，整條管線仍可跑完，方便測試。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict

import requests

from . import config

SYSTEM_PROMPT = """你是一位專門做 TikTok / Reels / Shorts 的台灣短影音編劇。
請用台灣人習慣的繁體中文口語（不要用中國大陸用語），寫一支直式短影片的劇本。
規則：
1. 第一句必須是 3 秒內抓住注意力的「鉤子」。
2. 每個場景一句旁白，10~28 個字，口語、有節奏。
3. 每個場景附一段英文 image_prompt（給文生圖模型用，描述畫面、光線、風格，不要有文字或 logo）。
4. 最後一個場景是行動呼籲（CTA）。
5. 只輸出 JSON，不要加任何說明或 markdown。格式：
{"title": "...", "hashtags": ["#..."], "scenes": [{"narration": "...", "image_prompt": "...", "keyword": "..."}]}
"""


@dataclass
class Scene:
    narration: str
    image_prompt: str = ""
    keyword: str = ""


@dataclass
class Script:
    title: str
    scenes: list[Scene]
    hashtags: list[str] = field(default_factory=list)
    source: str = "llm"

    def to_dict(self) -> dict:
        return asdict(self)


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("LLM 回覆裡找不到 JSON")
    return json.loads(text[start:end + 1])


def _call_llm(topic: str, scene_count: int, style: str) -> Script:
    user = (
        f"主題：{topic}\n場景數：{scene_count}\n風格：{style or '輕鬆、資訊型'}\n"
        f"目標長度：約 {scene_count * 5} 秒。"
    )
    url = config.LLM_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {config.LLM_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": config.LLM_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        "temperature": 0.8,
    }
    r = requests.post(url, headers=headers, json=body, timeout=config.LLM_TIMEOUT)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    data = _extract_json(content)
    scenes = [
        Scene(
            narration=str(s.get("narration", "")).strip(),
            image_prompt=str(s.get("image_prompt", "")).strip(),
            keyword=str(s.get("keyword", "")).strip(),
        )
        for s in data.get("scenes", [])
        if str(s.get("narration", "")).strip()
    ]
    if not scenes:
        raise ValueError("LLM 沒有產生任何場景")
    return Script(
        title=str(data.get("title", topic)).strip() or topic,
        scenes=scenes,
        hashtags=[str(h) for h in data.get("hashtags", [])][:8],
        source="llm",
    )


def template_script(topic: str, scene_count: int = 5) -> Script:
    """離線 / LLM 掛掉時的保底劇本，確保流程能走完。"""
    base = [
        Scene(f"你知道嗎？關於{topic}，大部分人都搞錯了這一點。", f"{topic}, dramatic close-up, cinematic lighting, vertical", topic),
        Scene(f"先說結論：{topic}真正的關鍵只有一個。", f"{topic}, minimal flat lay, soft studio light", "關鍵"),
        Scene(f"第一，搞懂{topic}的基本原理，比任何技巧都重要。", f"{topic}, detailed illustration, warm tones", "原理"),
        Scene(f"第二，每天花五分鐘練習，三十天後你會很有感。", f"person practicing {topic}, morning light, lifestyle photo", "練習"),
        Scene(f"第三，把成果記錄下來，才知道自己進步了多少。", f"notebook and phone tracking progress, top view", "記錄"),
        Scene("覺得有用的話，追蹤我，下一支告訴你更多。", "smartphone with social media app, neon glow, vertical", "追蹤"),
    ]
    if scene_count < len(base):
        picked = base[: scene_count - 1] + [base[-1]]
    else:
        picked = base
    return Script(title=f"{topic}｜三個重點一次看懂", scenes=picked, hashtags=[f"#{topic}", "#短影音", "#台灣"], source="template")


def generate_script(topic: str, scene_count: int = 5, style: str = "", offline: bool = False) -> Script:
    if offline:
        return template_script(topic, scene_count)
    try:
        return _call_llm(topic, scene_count, style)
    except Exception as e:  # noqa: BLE001
        print(f"[script] LLM 失敗（{e}），改用模板劇本")
        return template_script(topic, scene_count)
