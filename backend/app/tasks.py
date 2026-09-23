"""灵声 VoiceForge - 合成任务管理（队列 + 进度 + 分段结果）"""
from __future__ import annotations

import asyncio
import os
import uuid

from . import audio
from . import engines
from .chunker import chunk_text
from .config import EMOTION_LABELS, EMOTION_PROSODY, OUTPUT_DIR
from .emotion import analyze_segments
from .schemas import SegmentResult, TaskResult

_tasks: dict[str, TaskResult] = {}
_locks: dict[str, asyncio.Lock] = {}


def _lock(task_id: str) -> asyncio.Lock:
    if task_id not in _locks:
        _locks[task_id] = asyncio.Lock()
    return _locks[task_id]


def get_task(task_id: str) -> TaskResult | None:
    return _tasks.get(task_id)


def create_task(req) -> TaskResult:
    task_id = uuid.uuid4().hex[:12]
    tr = TaskResult(task_id=task_id, status="queued", message="任务已创建")
    _tasks[task_id] = tr
    return tr


async def run_task(task_id: str, req) -> None:
    tr = _tasks[task_id]
    async with _lock(task_id):
        tr.status = "running"
        try:
            text = (req.text or "").strip()
            if not text:
                raise ValueError("文本为空")
            tr.chars = len(text)

            # 1. 分块
            chunks = chunk_text(text)
            if not chunks:
                raise ValueError("文本无法分块")
            tr.progress = 5
            tr.message = f"已分为 {len(chunks)} 个分块"

            # 2. 情绪
            seg_meta = analyze_segments(chunks)
            if not req.auto_emotion and req.emotion:
                for m in seg_meta:
                    m["emotion"] = req.emotion
                    m["label"] = EMOTION_LABELS.get(req.emotion, req.emotion)
                    m["strength"] = req.emotion_strength
            tr.progress = 12
            tr.message = "情绪识别完成"

            # 3. 逐块合成（情绪 -> 韵律参数：率/调/量增量，强度加权）
            seg_files: list[str] = []
            task_dir = os.path.join(OUTPUT_DIR, task_id)
            os.makedirs(task_dir, exist_ok=True)
            total = len(chunks)
            for i, (chunk, meta) in enumerate(zip(chunks, seg_meta)):
                emo = meta["emotion"]
                strength = meta["strength"]
                base = EMOTION_PROSODY.get(emo, EMOTION_PROSODY["calm"])
                # 情绪强度加权：增量 * (0.5 + 强度)，强度 0 时保持用户参数
                w = 0.5 + strength if emo != "calm" else 0.0
                rate = max(0.5, min(2.0, req.rate + base["rate"] * w))
                pitch = max(-50.0, min(50.0, req.pitch + base["pitch"] * w))
                volume = max(0.0, min(2.0, req.volume + base["volume"] * w))
                seg_path = os.path.join(task_dir, f"seg_{i:03d}.mp3")
                await engines.synthesize(chunk, seg_path, req.voice,
                                         rate=rate, pitch=pitch, volume=volume)
                seg_files.append(seg_path)
                dur = audio.duration_ms(seg_path)
                tr.segments.append(SegmentResult(
                    index=i + 1, text=chunk, emotion=emo,
                    label=meta["label"], strength=meta["strength"], duration=dur))
                tr.progress = 12 + round(78 * (i + 1) / total, 1)
                tr.message = f"正在合成 {i + 1}/{total}：{meta['label']}"
            # 进度回调接口（供 SSE 轮询使用）
            tr.message = "音频拼接中"

            # 4. 拼接 + 转换
            merged_mp3 = os.path.join(task_dir, "merged.mp3")
            audio.concat_mp3(seg_files, merged_mp3)
            tr.progress = 94

            fmt = req.output_format or "mp3"
            final_name = f"voiceforge_{task_id}.{fmt}"
            final_path = os.path.join(task_dir, final_name)
            if fmt == "wav":
                audio.to_wav(merged_mp3, final_path)
            else:
                final_path = merged_mp3
                final_name = f"voiceforge_{task_id}.mp3"
                final_path = os.path.join(task_dir, final_name)
                if os.path.exists(merged_mp3) and os.path.abspath(final_path) != os.path.abspath(merged_mp3):
                    os.replace(merged_mp3, final_path)
            tr.progress = 97

            # 5. 字幕
            if req.with_subtitle:
                srt_path = os.path.join(task_dir, f"voiceforge_{task_id}.srt")
                audio.make_srt([s.dict() for s in tr.segments], srt_path)
                tr.subtitle_url = f"/outputs/{task_id}/voiceforge_{task_id}.srt"

            tr.audio_url = f"/outputs/{task_id}/{final_name}"
            tr.duration = sum(s.duration for s in tr.segments)
            tr.status = "done"
            tr.progress = 100
            tr.message = f"合成完成 · 共 {len(chunks)} 段 · {tr.duration:.1f}s"
        except Exception as e:
            tr.status = "failed"
            tr.message = f"合成失败：{e}"
