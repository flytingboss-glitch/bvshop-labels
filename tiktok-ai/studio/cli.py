"""命令列：python -m studio.cli "主題" [--scenes 5] [--offline] [--images comfyui|pexels|pollinations|placeholder]"""
import argparse
import json

from .pipeline import make_video


def main() -> None:
    p = argparse.ArgumentParser(description="一句話生成 TikTok 直式短影片")
    p.add_argument("topic", help="影片主題，例如：台北三家必吃早餐")
    p.add_argument("--scenes", type=int, default=5)
    p.add_argument("--seconds", type=int, default=None, help="目標長度 15 / 30 / 60 / 90（給了就不看 --scenes）")
    p.add_argument("--voice-sample", default=None, help="你的 5~15 秒錄音，用你的聲音講（需 CosyVoice 服務）")
    p.add_argument("--style", default="")
    p.add_argument("--voice", default=None, help="edge-tts 聲音，預設 zh-TW-HsiaoChenNeural")
    p.add_argument("--images", default=None, help="comfyui | pexels | pollinations | placeholder")
    p.add_argument("--bgm", default=None, help="背景音樂 mp3 路徑")
    p.add_argument("--offline", action="store_true", help="不呼叫 LLM，用模板劇本")
    a = p.parse_args()
    result = make_video(a.topic, scene_count=a.scenes, style=a.style, voice=a.voice,
                        image_backend=a.images, offline=a.offline, bgm=a.bgm, target_seconds=a.seconds,
                        ref_audio=a.voice_sample)
    print(json.dumps({k: v for k, v in result.items() if k != "scenes"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
