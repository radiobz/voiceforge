"""灵声 VoiceForge - 新引擎模板（复制本文件为 engines/<name>.py 后实现）

接入步骤：
  1. 复制本文件为 engines/cosyvoice.py / glmtts.py / volcengine.py ...
  2. 实现 synthesize()（必需）与 list_voices()（可选，默认返回空）
  3. 设置环境变量 VFORGE_ENGINE=<name> 启用
  4. 无需改动 tasks.py / 前端 / API

实现参考（按引擎类型选择）：
  - 本地 GPU 引擎（CosyVoice2 / GLM-TTS 开源版）：加载模型权重，参考音频
    由 voice 参数携带的 custom_xxx id 关联（见 voice_lab.resolve_voice）。
  - 托管 API（智谱 GLM-TTS / 火山豆包声音复刻）：用参考音频调 clone 接口
    拿克隆音色，再合成；密钥放环境变量，勿入库。
"""
from __future__ import annotations

from typing import Optional

# 引擎显示名（出现在 /api/health 与界面）
ENGINE_LABEL = "示例引擎"

# 情绪 -> 自然语言指令（供指令式引擎使用；韵律型引擎可忽略）
EMOTION_INSTRUCTIONS = {
    "joy": "用开心愉快的语气说",
    "sad": "用低沉悲伤的语气说",
    "angry": "用愤怒激动的语气说",
    "calm": "用平静舒缓的语气说",
    "surprised": "用惊讶的语气说",
    "fear": "用紧张害怕的语气说",
}


async def list_voices(lang: str | None = None,
                      keyword: str | None = None) -> list[dict]:
    """返回本引擎可用音色。格式与 /api/voices 契约一致。"""
    return []


async def synthesize(text: str, out_path: str, voice: str,
                     rate: float = 1.0, pitch: float = 0.0,
                     volume: float = 1.0,
                     emotion: Optional[str] = None,
                     strength: float = 0.0) -> None:
    """合成单个文本段到 out_path（mp3 或 wav）。

    voice 说明：
      - 内置音色：Edge short_name
      - 自定义音色：custom_xxx。克隆类引擎可经 voice_lab.registry.get(id)
        取得 entry["ref_wav"] 对应的参考音频（backend/data/refs/<id>.wav），
        作为零样本克隆的 prompt_speech。
    情绪：将 emotion 映射为指令（EMOTION_INSTRUCTIONS）或韵律参数。

    例（本地模型加载示意，勿直接使用）：
        import torch
        model = load_model()                      # 启动时加载一次
        ref_wav = resolve_reference_audio(voice)  # 参考音频路径
        instruct = EMOTION_INSTRUCTIONS.get(emotion, "用自然的语气说")
        audio = model.inference_zero_shot(text, ref_wav, instruct=instruct)
        save_wav(audio, out_path)
    """
    raise NotImplementedError("请在复制后的引擎文件中实现 synthesize")
