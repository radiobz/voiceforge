"""灵声 VoiceForge - 后端配置"""
import os

# 基础路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.environ.get("VFORGE_OUTPUT_DIR", os.path.join(BASE_DIR, "..", "outputs"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 长文本分块
MAX_CHUNK_CHARS = int(os.environ.get("VFORGE_MAX_CHUNK", "1000"))   # 单块最大字符
OVERLAP_SENTENCES = 0                                               # 块间重叠句子数（0 = 不重复合成，避免同一句被读两遍）
JOIN_SILENCE_MS = int(os.environ.get("VFORGE_JOIN_SILENCE", "0"))   # 块间额外静音（0 = 沿用模型自身的句末自然停顿）

# Edge-TTS
EDGE_VOICE = os.environ.get("VFORGE_EDGE_VOICE", "zh-CN-XiaoxiaoNeural")
EDGE_RATE = os.environ.get("VFORGE_EDGE_RATE", "+0%")
EDGE_VOLUME = os.environ.get("VFORGE_EDGE_VOLUME", "+0%")

# 情绪 -> 韵律参数增量（rate 倍数、pitch Hz、volume 倍数）
# 免费 Edge 端点不支持 express-as 风格（实测），采用原生韵律参数映射。
# 增量刻意取「温和」值：过大的语速/音调提升会让轻声字（如「的」）被压缩成
# 顿挫的机器感，温和的韵律更接近自然朗读。强度加权 w = 0.5 + strength。
EMOTION_PROSODY = {
    "joy":       {"rate": 0.05, "pitch": 4.0,  "volume": 0.05},
    "sad":       {"rate": -0.06, "pitch": -4.0, "volume": -0.03},
    "angry":     {"rate": 0.05, "pitch": 3.0,  "volume": 0.10},
    "calm":      {"rate": 0.0,  "pitch": 0.0,  "volume": 0.0},
    "surprised": {"rate": 0.06, "pitch": 5.0,  "volume": 0.05},
    "fear":      {"rate": -0.05, "pitch": -3.0, "volume": -0.05},
}
EMOTION_LABELS = {
    "joy": "开心", "sad": "悲伤", "angry": "愤怒",
    "calm": "平静", "surprised": "惊喜", "fear": "恐惧",
}
