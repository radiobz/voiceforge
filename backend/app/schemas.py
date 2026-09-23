"""灵声 VoiceForge - Pydantic 数据模型"""
from typing import List, Optional
from pydantic import BaseModel, Field


class VoiceInfo(BaseModel):
    short_name: str
    display_name: str
    locale: str
    gender: str
    styles: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    voice_type: str = "edge"           # edge / custom
    ref_wav: str = ""                  # 自定义音色参考音频（用于试听/克隆）
    analysis: dict = Field(default_factory=dict)
    closest: List[dict] = Field(default_factory=list)


class FileParseResponse(BaseModel):
    filename: str
    text: str
    chars: int
    blocks: int


class EmotionSegment(BaseModel):
    text: str
    emotion: str
    label: str
    strength: float


class EmotionResponse(BaseModel):
    emotion: str
    label: str
    strength: float
    segments: List[EmotionSegment] = Field(default_factory=list)


class SynthesizeRequest(BaseModel):
    text: str
    voice: str = "zh-CN-XiaoxiaoNeural"
    emotion: Optional[str] = None          # 手动指定: joy/sad/angry/calm/surprised/fear
    emotion_strength: float = 0.6          # 0.1-1.5
    auto_emotion: bool = True              # 自动识别
    rate: float = 1.0                      # 语速 0.5-2.0
    pitch: float = 0.0                     # 音调 -50 ~ +50
    volume: float = 1.0                    # 音量 0.0-2.0
    output_format: str = "mp3"             # mp3 / wav
    with_subtitle: bool = False            # 是否生成 SRT 字幕
    script_mode: Optional[bool] = None     # 剧本模式（角色:台词）；None=自动检测
    role_map: Optional[dict] = None        # 角色->音色映射（缺省角色自动分配）


class MusicGenerateRequest(BaseModel):
    mode: str = "chill"                    # chill / meditation / ambient / lofi
    duration: int = 120                    # 秒，10~2400（40 分钟）
    mood: Optional[str] = None             # joy/sad/calm/angry/fear/surprised；None=随机
    seed: Optional[int] = None             # None=随机种子
    profile: Optional[dict] = None         # 风格分析覆盖（audio_profile.to_params 输出）


class MusicAdaptRequest(BaseModel):
    task_id: str = ""                      # 复用已合成的语音任务（优先）
    text: str = ""                         # 或提供文本：将先按 TTS 参数合成语音
    voice: str = "zh-CN-XiaoxiaoNeural"
    emotion: Optional[str] = None
    emotion_strength: float = 0.6
    auto_emotion: bool = True
    rate: float = 1.0
    pitch: float = 0.0
    volume: float = 1.0
    script_mode: Optional[bool] = None
    role_map: Optional[dict] = None
    mode: str = "chill"                    # 配乐风格
    mood: Optional[str] = None             # None=根据文本情绪自适应
    balance: str = "auto"                  # loud/auto/low：音乐音量平衡
    with_subtitle: bool = False


class SegmentResult(BaseModel):
    index: int
    text: str
    emotion: str
    label: str
    strength: float
    duration: float = 0.0
    role: str = ""                         # 剧本模式下的角色名（普通模式为空）
    voice: str = ""                        # 该段实际使用的音色
    audio: str = ""


class TaskResult(BaseModel):
    task_id: str
    status: str                            # queued/running/done/failed
    progress: float = 0.0                  # 0-100
    message: str = ""
    segments: List[SegmentResult] = Field(default_factory=list)
    audio_url: str = ""
    subtitle_url: str = ""
    music_url: str = ""                    # 配乐任务：纯音乐
    mix_url: str = ""                      # 配乐任务：混合成品
    voice_url: str = ""                    # 配乐任务：纯语音
    music_meta: dict = Field(default_factory=dict)   # 音乐元信息
    chars: int = 0
    duration: float = 0.0
