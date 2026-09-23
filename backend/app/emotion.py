"""灵声 VoiceForge - 轻量情绪识别（词典 + 规则）

输出 6 类情绪（joy/sad/angry/calm/surprised/fear）及强度 0~1。
完全离线、零外部依赖；后续可平滑替换为 LLM 分析。
"""
from __future__ import annotations

import re

from .config import EMOTION_LABELS

# 情绪词典：词 -> 权重
_LEXICON: dict[str, dict[str, float]] = {
    "joy": {
        "开心": 1.0, "高兴": 1.0, "快乐": 1.0, "喜悦": 1.0, "欢喜": 0.9, "愉快": 0.9,
        "笑容": 0.8, "微笑": 0.7, "笑": 0.5, "哈哈": 0.8, "哈哈哈": 1.0, "嘿嘿": 0.7,
        "幸福": 0.9, "幸运": 0.8, "惊喜万分": 1.0, "兴奋": 0.9, "欢呼": 1.0, "庆祝": 0.9,
        "美好": 0.6, "美妙": 0.8, "棒": 0.7, "太好了": 1.0, "好开心": 1.0, "喜欢": 0.5,
        "爱": 0.4, "期待": 0.5, "希望": 0.4, "恭喜": 1.0, "生日快乐": 1.0, "新年快乐": 1.0,
    },
    "sad": {
        "悲伤": 1.0, "难过": 1.0, "伤心": 1.0, "痛苦": 1.0, "心痛": 1.0, "心碎": 1.2,
        "哭泣": 1.0, "哭": 0.8, "眼泪": 0.9, "泪": 0.7, "哭泣声": 1.0,
        "惆怅": 0.9, "忧郁": 0.9, "郁闷": 0.8, "沮丧": 0.9, "失落": 0.9, "失望": 0.8,
        "孤独": 0.9, "寂寞": 0.9, "孤单": 0.8, "思念": 0.8, "怀念": 0.7, "回忆": 0.4,
        "离别": 0.9, "告别": 0.8, "离开": 0.4, "失去": 0.9, "失去你": 1.0, "永别": 1.2,
        "遗憾": 0.9, "后悔": 0.8, "愧疚": 0.8, "抱歉": 0.5, "对不起": 0.6, "痛苦不堪": 1.2,
        "唉": 0.6, "呜": 0.8, "呜呜": 1.0, "想哭": 1.0, "心如刀绞": 1.3, "肝肠寸断": 1.3,
        "绝望": 1.2, "无助": 0.9, "委屈": 0.9, "伤": 0.4,
    },
    "angry": {
        "愤怒": 1.0, "生气": 1.0, "恼火": 1.0, "气愤": 1.0, "震怒": 1.2, "暴怒": 1.2,
        "怒火": 1.1, "火冒三丈": 1.3, "气死": 1.2, "气炸": 1.2, "可恶": 1.0,
        "混蛋": 1.1, "岂有此理": 1.1, "过分": 0.8, "太过分": 1.0, "无法容忍": 1.1,
        "忍无可忍": 1.2, "滚": 0.9, "闭嘴": 1.0, "闭嘴吧": 1.1, "恨": 0.9, "憎恨": 1.0,
        "讨厌": 0.8, "烦": 0.6, "烦躁": 0.8, "心烦": 0.7, "抓狂": 1.0, "愤怒至极": 1.3,
        "吵": 0.5, "吵死": 1.0, "投诉": 0.7, "抗议": 0.8, "不公": 0.8, "不公平": 0.9,
        "卑鄙": 1.1, "无耻": 1.1, "骗子": 0.9,
    },
    "surprised": {
        "惊喜": 1.0, "惊讶": 1.0, "震惊": 1.1, "惊呆": 1.1, "目瞪口呆": 1.1,
        "居然": 0.8, "竟然": 0.8, "没想到": 0.9, "万万没想到": 1.1, "意外": 0.7,
        "天哪": 0.9, "天啊": 0.9, "哇": 0.8, "哇塞": 1.0, "我的天": 1.0, "不会吧": 1.0,
        "真的假的": 1.1, "太意外": 1.0, "难以置信": 1.1, "不可思议": 1.0,
        "奇迹": 0.9, "大吃一惊": 1.2, "突然": 0.4, "爆炸性": 0.8, "重磅": 0.8,
    },
    "fear": {
        "害怕": 1.0, "恐惧": 1.1, "恐惧不安": 1.2, "惊恐": 1.2, "惊吓": 1.0,
        "吓人": 1.0, "吓死": 1.2, "可怕": 1.0, "恐怖": 1.0, "毛骨悚然": 1.3,
        "胆战心惊": 1.2, "心慌": 0.9, "不安": 0.8, "焦虑": 0.8, "紧张": 0.7,
        "担心": 0.7, "担忧": 0.8, "忧心忡忡": 1.0, "提心吊胆": 1.1, "不寒而栗": 1.2,
        "危险": 0.8, "威胁": 0.8, "出事": 0.8, "救命": 1.1, "救命啊": 1.2, "不要": 0.3,
        "别过来": 1.1, "魔鬼": 1.0, "鬼": 0.8, "死亡": 0.7, "死了": 0.7, "血": 0.5,
    },
}

_NEGATION = ("不", "没", "别", "莫", "无", "未", "不要", "没有", "不是", "绝不", "毫无")
_BOOST = re.compile(r"[！!]{1,}")
_QUESTION = re.compile(r"[？?]{1,}")

# 否定词直接推动悲伤/愤怒倾向的短语
_SAD_NEG = ("不开心", "不高兴", "不快乐", "不幸福", "难过", "失落")
_ANGER_NEG = ("不公", "不公平", "不平")


def _score_text(text: str) -> dict[str, float]:
    scores = {k: 0.0 for k in _LEXICON}
    for emo, words in _LEXICON.items():
        for word, w in words.items():
            idx = 0
            while True:
                i = text.find(word, idx)
                if i < 0:
                    break
                # 否定检测：词前 2 字符内有否定词，降低该词情绪权重
                neg = any(text[max(0, i - 2):i].endswith(n) for n in _NEGATION)
                scores[emo] += w * (0.25 if neg else 1.0)
                idx = i + len(word)
    # 标点增强
    if _BOOST.search(text):
        scores["surprised"] += 0.3
        scores["angry"] += 0.15
    if _QUESTION.search(text) and len(text) < 40:
        scores["surprised"] += 0.2
    return scores


def analyze(text: str) -> tuple[str, float]:
    """返回 (emotion_key, strength 0~1)。文本过短或无明显情绪时归为 calm。"""
    text = text.strip()
    if not text:
        return "calm", 0.0
    scores = _score_text(text)
    # 特殊否定短语覆盖
    for p in _SAD_NEG:
        if p in text:
            scores["sad"] += 1.0
    for p in _ANGER_NEG:
        if p in text:
            scores["angry"] += 1.0

    best = max(scores, key=lambda k: scores[k])
    best_score = scores[best]
    total = sum(scores.values())
    # 无任何命中 → 平静
    if total < 0.5:
        return "calm", 0.0
    # 强度 = 该情绪占比（0~1），叠加原始分值
    ratio = best_score / total if total > 0 else 0
    strength = min(1.0, round(0.35 + ratio * 0.65, 2))
    if best == "calm":
        strength = 0.0
    return best, strength


def analyze_segments(chunks: list[str]) -> list[dict]:
    """对每个分块分析，返回 [{text, emotion, label, strength}]"""
    out = []
    for ch in chunks:
        emo, st = analyze(ch)
        out.append({"text": ch, "emotion": emo, "label": EMOTION_LABELS.get(emo, emo), "strength": st})
    return out
