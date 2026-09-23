"""灵声 VoiceForge - TTS 引擎适配层入口

统一引擎接口，当前实现 Edge-TTS；未来可扩展 GPT-SoVITS / CosyVoice / ChatTTS。
"""
from . import edge

ENGINE_LABEL = "Edge-TTS · 在线"


async def list_voices(lang: str | None = None, keyword: str | None = None) -> list[dict]:
    voices = await edge.list_voices()
    if lang:
        voices = [v for v in voices if v["locale"].startswith(lang)]
    if keyword:
        kw = keyword.lower()
        voices = [v for v in voices if kw in v["short_name"].lower()
                  or kw in v["display_name"].lower() or kw in v["locale"].lower()]
    return voices


async def synthesize(text: str, out_path: str, voice: str,
                     rate: float = 1.0, pitch: float = 0.0, volume: float = 1.0) -> None:
    await edge.synthesize_to_file(text, out_path, voice, rate, pitch, volume)
