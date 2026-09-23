"""灵声 VoiceForge - TTS 引擎适配层（统一接口 + 可插拔）

【引擎接口契约】任何新引擎只需实现本模块中的同名函数即可接入：

    async def list_voices(lang=None, keyword=None) -> list[dict]
    async def synthesize(text, out_path, voice, rate=1.0, pitch=0.0,
                         volume=1.0, emotion=None, strength=0.0) -> None

参数说明：
  text    待合成文本（已按句切分，单段 ≤ 1100 字）
  voice   音色标识：
          - 内置音色：Edge short_name（如 zh-CN-XiaoxiaoNeural）
          - 自定义音色：custom_xxx（tasks 层已通过 voice_lab.resolve_voice
            解析为最接近的内置音色；克隆类引擎可直接改用参考音频）
  rate / pitch / volume  韵律参数（0.5~2.0 / ±50Hz / 0~2），Edge 使用
  emotion  情绪标签（joy/sad/angry/calm/surprised/fear，可为 None）
  strength 情绪强度 0~1
           - 韵律型引擎（Edge）：忽略 emotion，用 rate/pitch/volume 表达
           - 指令型引擎（CosyVoice2 instruct / GLM-TTS / 豆包 API）：
            可将 emotion 映射为自然语言指令，如 "用低沉悲伤的语气说"

【引擎选择】通过环境变量 VFORGE_ENGINE 切换（默认 edge）：
    VFORGE_ENGINE=edge         Edge-TTS（免费在线，无需密钥）
    VFORGE_ENGINE=cosyvoice    CosyVoice2（本地 GPU，零样本克隆）
    VFORGE_ENGINE=glmtts       GLM-TTS（本地 GPU 或智谱 API）
    VFORGE_ENGINE=volcengine   火山豆包语音 API（声音复刻）

新增引擎：复制 engines/template_engine.py 为 engines/<name>.py，
实现上述两个函数即可，无需改动 tasks/ 与前端。
"""
from __future__ import annotations

import importlib
import os
from typing import Optional

from . import edge

ENGINE = os.environ.get("VFORGE_ENGINE", "edge").lower()

_LABELS = {
    "edge": "Edge-TTS · 在线",
    "cosyvoice": "CosyVoice2 · 本地",
    "glmtts": "GLM-TTS · 本地/API",
    "volcengine": "豆包语音 · API",
}

# FIX-017：ENGINE_LABEL 按当前引擎动态取值，而非硬编码
ENGINE_LABEL = _LABELS.get(ENGINE, ENGINE)


def _engine_module():
    """按需加载当前引擎模块（未选择时不加载，避免启动依赖 GPU 包）。"""
    if ENGINE == "edge":
        return edge
    try:
        return importlib.import_module(f".{ENGINE}", package=__name__)
    except ImportError as e:
        raise RuntimeError(
            f"引擎 {ENGINE} 未安装或未实现（可参考 template_engine.py）：{e}") from e


async def list_voices(lang: str | None = None, keyword: str | None = None) -> list[dict]:
    # FIX-016：通过 _engine_module() 分发，未实现 list_voices 的引擎回退到 edge
    mod = _engine_module()
    if hasattr(mod, "list_voices"):
        voices = await mod.list_voices()
    else:
        voices = await edge.list_voices()
    if lang:
        voices = [v for v in voices if v["locale"].startswith(lang)]
    if keyword:
        kw = keyword.lower()
        voices = [v for v in voices if kw in v["short_name"].lower()
                  or kw in v["display_name"].lower() or kw in v["locale"].lower()]
    return voices


async def synthesize(text: str, out_path: str, voice: str,
                     rate: float = 1.0, pitch: float = 0.0,
                     volume: float = 1.0,
                     emotion: Optional[str] = None,
                     strength: float = 0.0) -> None:
    """统一合成入口：按 VFORGE_ENGINE 分发到具体引擎。"""
    mod = _engine_module()
    if hasattr(mod, "synthesize_to_file") and ENGINE == "edge":
        await edge.synthesize_to_file(text, out_path, voice, rate, pitch, volume)
        return
    await mod.synthesize(text, out_path, voice, rate=rate, pitch=pitch,
                         volume=volume, emotion=emotion, strength=strength)


def split_for_tts(text: str, max_chars: int = 1100) -> list[str]:
    """把文本切成单次合成的安全长度（Edge 需 < 4096 字节；通用句级切分）。

    edge-tts 库内部按 4096 字节硬切分文本（中文无空格时会落在任意字符后），
    且每个 SSML 切片开头都带约 150~190ms 前导静音——两者叠加会在句中产生
    可闻的"断音/机器感"。这里先按句子切分，超长句再在标点处二次切分，
    确保每片都小于 4096 字节（1100 汉字 ≈ 3300 字节），由上层逐片合成并
    修剪前导静音后拼接。其他引擎同样受益于句级切分。
    """
    from ..chunker import split_sentences
    sents = split_sentences(text)
    if not sents:
        sents = [text]
    pieces: list[str] = []
    for s in sents:
        if len(s) <= max_chars:
            pieces.append(s)
            continue
        seg = s
        while len(seg) > max_chars:
            cut = seg.rfind("，", 0, max_chars)
            if cut < max_chars // 3:
                cut = seg.rfind("、", 0, max_chars)
            if cut < max_chars // 3:
                cut = seg.rfind("；", 0, max_chars)
            if cut < max_chars // 3:
                cut = max_chars
            if cut == max_chars:
                pieces.append(seg[:max_chars])
                seg = seg[max_chars:]
            else:
                pieces.append(seg[:cut + 1])
                seg = seg[cut + 1:]
        if seg:
            pieces.append(seg)
    return pieces
