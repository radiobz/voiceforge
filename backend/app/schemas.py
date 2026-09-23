"""灵声 VoiceForge - Pydantic 数据模型"""
from typing import List, Literal, Optional
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


class EmotionRequest(BaseModel):
    """FIX-009：/api/emotion/analyze 请求体，替代裸 dict。"""
    text: str = ""


_EMOTION_KEY = Literal["joy", "sad", "angry", "calm", "surprised", "fear"]


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: str = "zh-CN-XiaoxiaoNeural"
    emotion: Optional[_EMOTION_KEY] = None
    emotion_strength: float = Field(0.6, ge=0.0, le=1.5)
    auto_emotion: bool = True
    rate: float = Field(1.0, ge=0.5, le=2.0)
    pitch: float = Field(0.0, ge=-50.0, le=50.0)
    volume: float = Field(1.0, ge=0.0, le=2.0)
    output_format: Literal["mp3", "wav"] = "mp3"
    with_subtitle: bool = False
    script_mode: Optional[bool] = None
    role_map: Optional[dict] = None


class MusicGenerateRequest(BaseModel):
    mode: Literal["chill", "meditation", "ambient", "lofi"] = "chill"
    duration: int = Field(120, ge=10, le=2400)
    mood: Optional[_EMOTION_KEY] = None
    seed: Optional[int] = None
    profile: Optional[dict] = None
    rhythm: Optional[Literal["none", "light", "standard", "full"]] = None
    guitar: Optional[bool] = None


class MusicAdaptRequest(BaseModel):
    task_id: str = ""
    text: str = ""
    voice: str = "zh-CN-XiaoxiaoNeural"
    emotion: Optional[_EMOTION_KEY] = None
    emotion_strength: float = Field(0.6, ge=0.0, le=1.5)
    auto_emotion: bool = True
    rate: float = Field(1.0, ge=0.5, le=2.0)
    pitch: float = Field(0.0, ge=-50.0, le=50.0)
    volume: float = Field(1.0, ge=0.0, le=2.0)
    script_mode: Optional[bool] = None
    role_map: Optional[dict] = None
    mode: Literal["chill", "meditation", "ambient", "lofi"] = "chill"
    mood: Optional[_EMOTION_KEY] = None
    balance: Literal["loud", "auto", "low"] = "auto"
    with_subtitle: bool = False


class SegmentResult(BaseModel):
    index: int
    text: str
    emotion: str
    label: str
    strength: float
    duration: float = 0.0
    role: str = ""
    voice: str = ""
    audio: str = ""


class TaskResult(BaseModel):
    task_id: str
    status: str                            # queued/running/done/failed
    progress: float = 0.0
    message: str = ""
    segments: List[SegmentResult] = Field(default_factory=list)
    audio_url: str = ""
    subtitle_url: str = ""
    music_url: str = ""
    mix_url: str = ""
    voice_url: str = ""
    music_meta: dict = Field(default_factory=dict)
    chars: int = 0
    duration: float = 0.0
