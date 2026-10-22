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


COMPLIANCE_RULES = """平台合規（TikTok / 抖音 / Reels 通用）：
- 不用絕對化用語：最、第一、唯一、100%、保證、永久、根治、治癒。
- 不做醫療、減肥、投資報酬的效果承諾；不提價格「最低」。
- 不出現他人品牌名、聯絡方式、導流字眼（加我、私訊、連結在…）；CTA 只能是追蹤、留言、收藏、分享。
- 不照抄原文，要用自己的話重寫，結構與例子都要換。
- 台灣用語：影片不說視頻、品質不說質量、軟體不說軟件、網路不說網絡、數位不說數字化。
"""


def plan_duration(target_seconds: int | None, scene_count: int | None = None) -> tuple[int, int]:
    """目標秒數 → (場景數, 總字數上限)。沒給秒數就用場景數反推。"""
    if target_seconds:
        target_seconds = max(10, min(int(target_seconds), 180))
        scenes = max(3, min(round(target_seconds / config.SECONDS_PER_SCENE), 18))
    else:
        scenes = scene_count or 5
        target_seconds = int(scenes * config.SECONDS_PER_SCENE)
    chars = int(target_seconds * config.CHARS_PER_SECOND)
    return scenes, chars


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


def _chat(system: str, user: str, temperature: float = 0.8) -> str:
    url = config.LLM_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {config.LLM_API_KEY}", "Content-Type": "application/json"}
    body = {"model": config.LLM_MODEL, "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    r = requests.post(url, headers=headers, json=body, timeout=config.LLM_TIMEOUT)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _parse_script(content: str, fallback_title: str) -> Script:
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
        title=str(data.get("title", fallback_title)).strip() or fallback_title,
        scenes=scenes,
        hashtags=[str(h) for h in data.get("hashtags", [])][:8],
        source="llm",
    )


def _call_llm(topic: str, scene_count: int, style: str, target_seconds: int | None = None) -> Script:
    scenes, chars = plan_duration(target_seconds, scene_count)
    user = (f"主題：{topic}\n場景數：{scenes}\n風格：{style or '輕鬆、資訊型'}\n"
            f"目標長度：約 {int(scenes * config.SECONDS_PER_SCENE)} 秒，全部旁白加起來不超過 {chars} 個字。\n{COMPLIANCE_RULES}")
    return _parse_script(_chat(SYSTEM_PROMPT, user), topic)


REWRITE_PROMPT = """你是一位台灣短影音編劇兼平台審核員。使用者會給你一支抖音 / TikTok 影片的「原始逐字稿」與「原文案」。
請你：
1. 先用一句話抓出這支影片的核心賣點與結構（鉤子 → 內容 → CTA）。
2. 用自己的話、台灣人的口語重寫成一支新的直式短影片劇本，不可照抄原句，例子與順序要換。
3. 嚴格遵守平台合規規則。
4. 只輸出 JSON，不要加任何說明或 markdown。格式：
{"title": "...", "hashtags": ["#..."], "selling_point": "...", "compliance_notes": ["原文有『保證瘦』已改為…"],
 "scenes": [{"narration": "...", "image_prompt": "英文畫面描述", "keyword": "..."}]}
"""


def rewrite_from_transcript(transcript: str, desc: str = "", target_seconds: int = 30, style: str = "",
                            offline: bool = False) -> Script:
    """① 逐字稿 + 原文案 → 合規、台灣化、指定秒數的新劇本。"""
    scenes, chars = plan_duration(target_seconds)
    src = (transcript or "").strip() or (desc or "").strip()
    if not src:
        raise ValueError("沒有逐字稿也沒有文案，無法改寫")
    if not offline:
        user = (f"原文案：{desc or '（無）'}\n原始逐字稿：\n{src[:4000]}\n\n"
                f"場景數：{scenes}；全部旁白不超過 {chars} 字；風格：{style or '保留原片節奏'}。\n{COMPLIANCE_RULES}")
        try:
            sc = _parse_script(_chat(REWRITE_PROMPT, user, temperature=0.7), desc[:30] or "改寫影片")
            sc.source = "llm-rewrite"
            return sc
        except Exception as e:  # noqa: BLE001
            print(f"[script] LLM 改寫失敗（{e}），改用規則式重排")
    return _rule_rewrite(src, desc, scenes, chars)


_BANNED = {"保證": "有機會", "最好": "很不錯", "第一": "前段班", "唯一": "少見", "100%": "幾乎", "根治": "改善",
           "治癒": "緩解", "永久": "長期", "視頻": "影片", "質量": "品質", "軟件": "軟體", "網絡": "網路",
           "數字化": "數位化", "加我": "追蹤我", "私信": "留言", "私訊我": "留言", "鏈接": "連結"}


def _rule_rewrite(src: str, desc: str, scenes: int, chars: int) -> Script:
    """LLM 不在時的保底：簡轉繁、去違規字、截到字數。不是改寫，只是合規清洗。"""
    try:
        from opencc import OpenCC
        src, desc = OpenCC("s2twp").convert(src), OpenCC("s2twp").convert(desc)
    except Exception:  # noqa: BLE001
        pass
    src = re.sub(r"\s*#\S+", "", src).strip()   # hashtag 不唸進旁白
    for bad, good in _BANNED.items():
        src = src.replace(bad, good)
    parts = [p.strip() for p in re.split(r"(?<=[。！？!?])", src) if p.strip()]
    out, used = [], 0
    for p in parts:
        if used + len(p) > chars:
            break
        out.append(p)
        used += len(p)
    if not out:
        out = [src[:chars]]
    # 平均分配到場景
    per = max(1, round(len(out) / scenes))
    grouped = ["".join(out[i:i + per]) for i in range(0, len(out), per)][:scenes]
    grouped.append("覺得實用的話，收藏起來、追蹤我看更多。")
    sc = [Scene(narration=g, image_prompt=f"{g[:20]}, vertical, cinematic", keyword=g[:4]) for g in grouped]
    return Script(title=(desc or grouped[0])[:30], scenes=sc, hashtags=["#短影音", "#台灣"], source="rule-rewrite")


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


def generate_script(topic: str, scene_count: int = 5, style: str = "", offline: bool = False,
                    target_seconds: int | None = None) -> Script:
    scene_count, _ = plan_duration(target_seconds, scene_count)
    if offline:
        return template_script(topic, scene_count)
    try:
        return _call_llm(topic, scene_count, style, target_seconds)
    except Exception as e:  # noqa: BLE001
        print(f"[script] LLM 失敗（{e}），改用模板劇本")
        return template_script(topic, scene_count)
