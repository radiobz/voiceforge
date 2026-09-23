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


def split_for_tts(text: str, max_chars: int = 1100) -> list[str]:
    """把文本切成 edge-tts 单次合成的安全长度（保证 < 4096 字节）。

    edge-tts 库内部按 4096 字节硬切分文本（中文无空格时会落在任意字符后），
    且每个 SSML 切片开头都带约 150~190ms 前导静音——两者叠加会在句中产生
    可闻的"断音/机器感"。这里先按句子切分，超长句再在标点处二次切分，
    确保每片都小于 4096 字节（1100 汉字 ≈ 3300 字节），由上层逐片合成并
    修剪前导静音后拼接。
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
