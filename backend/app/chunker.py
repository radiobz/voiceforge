"""灵声 VoiceForge - 长文本智能分块

按句子边界切分，每块不超过 MAX_CHUNK_CHARS；
块间保留 OVERLAP_SENTENCES 个句子作为上下文重叠，保证句读连贯、语气自然。
"""
from __future__ import annotations

import re

from .config import MAX_CHUNK_CHARS, OVERLAP_SENTENCES

# 句子切分：句号/问号/感叹号/分号 + 换行
_SENT_SPLIT = re.compile(r"(?<=[。！？；\n!?;])")
# 段落分隔
_PARA_SPLIT = re.compile(r"\n\s*\n")


def split_sentences(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    sents: list[str] = []
    for para in _PARA_SPLIT.split(text):
        para = para.strip()
        if not para:
            continue
        parts = _SENT_SPLIT.split(para)
        buf = ""
        for p in parts:
            p = p.strip()
            if not p:
                continue
            buf += p
            if buf.endswith(("。", "！", "？", "；", "!", "?", ";")):
                sents.append(buf)
                buf = ""
        if buf:
            sents.append(buf)
    return sents


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS,
               overlap: int = OVERLAP_SENTENCES) -> list[str]:
    """返回分块列表，每块为自然连贯的文本。"""
    sents = split_sentences(text)
    if not sents:
        return []
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for s in sents:
        # 单句超长（无标点长段），按硬字符切
        if len(s) > max_chars and not cur:
            for i in range(0, len(s), max_chars):
                chunks.append(s[i:i + max_chars])
            continue
        if cur_len + len(s) > max_chars and cur:
            chunks.append("".join(cur))
            # 重叠：保留末尾 N 句
            keep = cur[-overlap:] if overlap > 0 else []
            cur = keep
            cur_len = sum(len(x) for x in keep)
        cur.append(s)
        cur_len += len(s)
    if cur:
        chunks.append("".join(cur))
    return chunks
