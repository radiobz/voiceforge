"""灵声 VoiceForge - 后端配置"""
import os

# 基础路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.environ.get("VFORGE_OUTPUT_DIR", os.path.join(BASE_DIR, "..", "outputs"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 长文本分块
MAX_CHUNK_CHARS = int(os.environ.get("VFORGE_MAX_CHUNK", "1000"))   # 单块最大字符
OVERLAP_SENTENCES = 1                                               # 块间重叠句子数（保持语气连贯）
JOIN_SILENCE_MS = int(os.environ.get("VFORGE_JOIN_SILENCE", "350")) # 分块拼接静音时长

# Edge-TTS
EDGE_VOICE = os.environ.get("VFORGE_EDGE_VOICE", "zh-CN-XiaoxiaoNeural")
EDGE_RATE = os.environ.get("VFORGE_EDGE_RATE", "+0%")
EDGE_VOLUME = os.environ.get("VFORGE_EDGE_VOLUME", "+0%")

# 情绪 -> 韵律参数增量（rate 倍数、pitch Hz、volume 倍数）
# 免费 Edge 端点不支持 express-as 风格（实测），采用原生韵律参数映射：
# 开心稍快+音调明亮；悲伤放缓+低沉；愤怒加快+更响；惊喜快+高；恐惧放缓+压低。
EMOTION_PROSODY = {
    "joy":       {"rate": 0.12, "pitch": 8.0,  "volume": 0.10},
    "sad":       {"rate": -0.10, "pitch": -6.0, "volume": -0.05},
    "angry":     {"rate": 0.08, "pitch": 4.0,  "volume": 0.15},
    "calm":      {"rate": 0.0,  "pitch": 0.0,  "volume": 0.0},
    "surprised": {"rate": 0.10, "pitch": 10.0, "volume": 0.08},
    "fear":      {"rate": -0.08, "pitch": -4.0, "volume": -0.08},
}
EMOTION_LABELS = {
    "joy": "开心", "sad": "悲伤", "angry": "愤怒",
    "calm": "平静", "surprised": "惊喜", "fear": "恐惧",
}
