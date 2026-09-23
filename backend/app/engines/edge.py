"""灵声 VoiceForge - Edge-TTS 引擎适配层

统一接口：list_voices / synthesize_text

【重要实测结论（2026-09 验证）】
微软免费 Edge 消费端点（speech.platform.bing.com .../readaloud/edge/v1）不支持
SSML 的 mstts:express-as 情绪风格 —— 发送 express-as 会静默返回 0 字节音频。
因此情绪采用端点原生支持的韵律参数（rate / pitch / volume）映射实现，
由调用方（tasks.py）根据情绪标签与强度计算参数增量。该方案自然、稳定、无机械感。

未来若接入 Azure 付费端点或本地引擎（CosyVoice 等），可在此适配层增加
express-as / instruction 支持，接口不变。
"""
from __future__ import annotations

from typing import Optional

import edge_tts

# 常见中文音色的展示名（用于界面）
DISPLAY_NAMES: dict[str, str] = {
    "zh-CN-XiaoxiaoNeural": "晓晓 · 女声", "zh-CN-XiaoyiNeural": "晓伊 · 女声",
    "zh-CN-XiaomoNeural": "晓墨 · 女声", "zh-CN-XiaohanNeural": "晓涵 · 女声",
    "zh-CN-XiaomengNeural": "晓梦 · 女声", "zh-CN-XiaochenNeural": "晓辰 · 男声",
    "zh-CN-XiaoruiNeural": "晓睿 · 女声", "zh-CN-XiaoshuangNeural": "晓双 · 童声",
    "zh-CN-XiaoxuanNeural": "晓萱 · 女声", "zh-CN-XiaoyouNeural": "晓悠 · 女声",
    "zh-CN-XiaozhenNeural": "晓甄 · 女声", "zh-CN-YunxiNeural": "云希 · 男声",
    "zh-CN-YunyangNeural": "云扬 · 男声", "zh-CN-YunjianNeural": "云健 · 男声",
    "zh-CN-YunfengNeural": "云枫 · 男声", "zh-CN-YunhaoNeural": "云皓 · 男声",
    "zh-CN-YunjieNeural": "云杰 · 男声", "zh-CN-YunyeNeural": "云野 · 男声",
    "zh-CN-YunzeNeural": "云泽 · 男声", "zh-CN-YunxiaNeural": "云夏 · 男声",
    "zh-CN-XiaoxiaoMultilingualNeural": "晓晓 · 多语言女声",
    "zh-CN-YunxiMultilingualNeural": "云希 · 多语言男声",
    "zh-CN-XiaoyiMultilingualNeural": "晓伊 · 多语言女声",
}

VOICE_TAGS: dict[str, list[str]] = {
    "zh-CN-XiaoxiaoNeural": ["温暖", "自然"], "zh-CN-YunxiNeural": ["沉稳", "磁性"],
    "zh-CN-YunyangNeural": ["播报", "专业"], "zh-CN-XiaoyiNeural": ["温柔", "知性"],
    "zh-CN-XiaomoNeural": ["情感", "丰富"], "zh-CN-XiaohanNeural": ["温柔", "亲切"],
    "zh-CN-XiaochenNeural": ["活力", "解说"], "zh-CN-YunjianNeural": ["纪录片", "浑厚"],
    "zh-CN-XiaomengNeural": ["梦幻", "甜美"], "zh-CN-XiaoyouNeural": ["故事", "童趣"],
    "zh-CN-XiaoshuangNeural": ["童声", "可爱"], "zh-CN-YunfengNeural": ["自然", "年轻"],
    "zh-CN-YunhaoNeural": ["广告", "活力"], "zh-CN-YunjieNeural": ["阳光", "亲和"],
    "zh-CN-YunyeNeural": ["年轻", "活力"], "zh-CN-YunzeNeural": ["沉稳", "年轻"],
}

_voice_cache: list[dict] | None = None


async def list_voices() -> list[dict]:
    """返回音色列表（含展示名/标签），结果缓存。"""
    global _voice_cache
    if _voice_cache is not None:
        return _voice_cache
    try:
        raw = await edge_tts.list_voices()
    except Exception:
        raw = [{"ShortName": k, "Gender": "Female" if "xiao" in k else "Male",
                "Locale": "zh-CN", "FriendlyName": k} for k in DISPLAY_NAMES]
    voices = []
    for v in raw:
        short = v.get("ShortName", "")
        if not short:
            continue
        voices.append({
            "short_name": short,
            "display_name": DISPLAY_NAMES.get(short) or v.get("FriendlyName", short),
            "locale": v.get("Locale", ""),
            "gender": v.get("Gender", ""),
            "styles": [],  # 免费端点不支持 express-as，见文件头实测说明
            "tags": VOICE_TAGS.get(short, []),
            "voice_type": "edge",
        })
    voices.sort(key=lambda v: (v["locale"].split("-")[0] != "zh", v["short_name"]))
    _voice_cache = voices
    return voices


def _pct(delta: float) -> str:
    """float 增量 -> '+12%' / '-6%' / '+0%'"""
    return f"{'+' if delta >= 0 else ''}{delta * 100:.0f}%"


def _hz(delta: float) -> str:
    return f"{'+' if delta >= 0 else ''}{delta:.0f}Hz"


async def synthesize_to_file(text: str, out_path: str, voice: str,
                             rate: float = 1.0, pitch: float = 0.0,
                             volume: float = 1.0) -> None:
    """合成单段文本到 mp3。rate 0.5~2，pitch -50~50(Hz)，volume 0~2。

    使用 edge-tts 原生参数（率/调/量），不注入 SSML 风格（免费端点不支持）。
    """
    rate_pct = _pct(rate - 1.0)
    pitch_hz = _hz(pitch)
    volume_pct = _pct(volume - 1.0)
    com = edge_tts.Communicate(text, voice, rate=rate_pct, pitch=pitch_hz, volume=volume_pct)
    await com.save(out_path)
