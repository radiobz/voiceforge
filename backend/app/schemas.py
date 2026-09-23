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


class SegmentResult(BaseModel):
    index: int
    text: str
    emotion: str
    label: str
    strength: float
    duration: float = 0.0
    audio: str = ""


class TaskResult(BaseModel):
    task_id: str
    status: str                            # queued/running/done/failed
    progress: float = 0.0                  # 0-100
    message: str = ""
    segments: List[SegmentResult] = Field(default_factory=list)
    audio_url: str = ""
    subtitle_url: str = ""
    chars: int = 0
    duration: float = 0.0
