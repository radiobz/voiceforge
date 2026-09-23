"""灵声 VoiceForge - 合成任务管理（队列 + 进度 + 分段结果）

两条合成流水线：
  - 普通模式：长文本按句切分 -> 逐句情绪 + 韵律参数 -> 逐句合成并修剪前导静音
    -> 零静音拼接（沿用模型自身句末停顿）。消除 edge-tts 4096 字节随机切块
    与前导静音造成的"断音"。
  - 剧本模式：`角色：台词` 解析 -> 角色自动分配音色 -> 逐句情绪 -> 逐句合成
    -> 修剪 -> 拼接。实现"多人有声剧"听感（多音色 + 情绪随台词变化）。
"""
from __future__ import annotations

import asyncio
import os
import uuid

from . import audio
from . import engines
from . import script as script_mod
from .chunker import chunk_text
from .config import EMOTION_LABELS, EMOTION_PROSODY, OUTPUT_DIR
from .emotion import analyze, analyze_segments
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


def _prosody(req, emotion_key: str, strength: float) -> tuple[float, float, float]:
    """情绪 -> 韵律参数（率/调/量），强度加权 w = 0.5 + strength。"""
    base = EMOTION_PROSODY.get(emotion_key, EMOTION_PROSODY["calm"])
    w = 0.5 + strength if emotion_key != "calm" else 0.0
    rate = max(0.5, min(2.0, req.rate + base["rate"] * w))
    pitch = max(-50.0, min(50.0, req.pitch + base["pitch"] * w))
    volume = max(0.0, min(2.0, req.volume + base["volume"] * w))
    return rate, pitch, volume


async def _synth_piece(tr: TaskResult, text: str, voice: str,
                       rate: float, pitch: float, volume: float,
                       task_dir: str, tag: str) -> str:
    """合成单个文本片 -> 修剪前导静音 -> 返回修剪后的 mp3 路径。"""
    raw = os.path.join(task_dir, f"{tag}_raw.mp3")
    await engines.synthesize(text, raw, voice, rate=rate, pitch=pitch, volume=volume)
    trimmed = os.path.join(task_dir, f"{tag}.mp3")
    audio.trim_leading_silence_mp3(raw, trimmed)
    return trimmed


async def _run_plain(tr: TaskResult, req, text: str) -> None:
    """普通模式：分块 -> 分句 -> 逐句情绪合成。"""
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("文本无法分块")
    tr.progress = 5
    tr.message = f"已分为 {len(chunks)} 个分块"

    seg_meta = analyze_segments(chunks)
    if not req.auto_emotion and req.emotion:
        for m in seg_meta:
            m["emotion"] = req.emotion
            m["label"] = EMOTION_LABELS.get(req.emotion, req.emotion)
            m["strength"] = req.emotion_strength
    tr.progress = 12
    tr.message = "情绪识别完成"

    task_dir = os.path.join(OUTPUT_DIR, tr.task_id)
    os.makedirs(task_dir, exist_ok=True)
    total = len(chunks)
    seg_files: list[str] = []
    for i, (chunk, meta) in enumerate(zip(chunks, seg_meta)):
        rate, pitch, volume = _prosody(req, meta["emotion"], meta["strength"])
        pieces = engines.split_for_tts(chunk)
        piece_paths = []
        for j, piece in enumerate(pieces):
            p = await _synth_piece(tr, piece, req.voice, rate, pitch, volume,
                                   task_dir, f"seg_{i:03d}_p{j:02d}")
            piece_paths.append(p)
        seg_path = os.path.join(task_dir, f"seg_{i:03d}.mp3")
        audio.concat_mp3(piece_paths, seg_path, silence_ms=0)
        seg_files.append(seg_path)
        dur = audio.duration_ms(seg_path)
        tr.segments.append(SegmentResult(
            index=i + 1, text=chunk, emotion=meta["emotion"],
            label=meta["label"], strength=meta["strength"], duration=dur,
            voice=req.voice))
        tr.progress = 12 + round(78 * (i + 1) / total, 1)
        tr.message = f"正在合成 {i + 1}/{total}：{meta['label']}"
    tr.message = "音频拼接中"
    merged_mp3 = os.path.join(task_dir, "merged.mp3")
    audio.concat_mp3(seg_files, merged_mp3, silence_ms=0)
    _finalize(tr, req, task_dir, merged_mp3)


async def _run_script(tr: TaskResult, req, text: str) -> None:
    """剧本模式：角色行解析 -> 角色音色分配 -> 逐句情绪 -> 逐句合成。"""
    lines = script_mod.parse_script(text)
    if not lines:
        raise ValueError("剧本解析为空")
    tr.progress = 5
    tr.message = f"解析到 {len(lines)} 个台词行"

    roles: list[str] = []
    for ln in lines:
        if ln["role"] not in roles:
            roles.append(ln["role"])
    voices = await engines.list_voices()
    zh_pool = [v["short_name"] for v in voices
               if v["locale"].startswith("zh") and "Multilingual" not in v["short_name"]]
    if not zh_pool:
        zh_pool = [v["short_name"] for v in voices]
    role_voices = script_mod.auto_role_voices(roles, req.voice, zh_pool)
    if req.role_map:
        for r, v in req.role_map.items():
            if v:
                role_voices[r] = v
    tr.message = f"角色音色分配完成 · {len(roles)} 个角色"

    task_dir = os.path.join(OUTPUT_DIR, tr.task_id)
    os.makedirs(task_dir, exist_ok=True)
    total = len(lines)
    piece_paths: list[str] = []
    units: list[dict] = []
    for i, ln in enumerate(lines):
        emo, st = analyze(ln["text"])
        if not req.auto_emotion and req.emotion:
            emo = req.emotion
            st = req.emotion_strength
        label = EMOTION_LABELS.get(emo, emo)
        rate, pitch, volume = _prosody(req, emo, st)
        voice = role_voices.get(ln["role"], req.voice)
        p = await _synth_piece(tr, ln["text"], voice, rate, pitch, volume,
                               task_dir, f"line_{i:04d}")
        piece_paths.append(p)
        dur = audio.duration_ms(p)
        units.append({"role": ln["role"], "text": ln["text"], "emotion": emo,
                      "label": label, "strength": st, "duration": dur, "voice": voice})
        tr.segments.append(SegmentResult(
            index=i + 1, text=ln["text"], emotion=emo, label=label,
            strength=st, duration=dur, role=ln["role"], voice=voice))
        tr.progress = 12 + round(78 * (i + 1) / total, 1)
        tr.message = f"正在合成 {i + 1}/{total}：{ln['role']} · {label}"
    tr.message = "音频拼接中"
    merged_mp3 = os.path.join(task_dir, "merged.mp3")
    audio.concat_mp3(piece_paths, merged_mp3, silence_ms=0)
    _finalize(tr, req, task_dir, merged_mp3, units=units)


def _finalize(tr: TaskResult, req, task_dir: str, merged_mp3: str,
              units: list[dict] | None = None) -> None:
    """输出格式转换 + 字幕 + 收尾字段。"""
    tr.progress = 94
    fmt = req.output_format or "mp3"
    final_name = f"voiceforge_{tr.task_id}.{fmt}"
    final_path = os.path.join(task_dir, final_name)
    if fmt == "wav":
        audio.to_wav(merged_mp3, final_path)
    else:
        if os.path.exists(merged_mp3) and os.path.abspath(final_path) != os.path.abspath(merged_mp3):
            os.replace(merged_mp3, final_path)
    tr.progress = 97
    if req.with_subtitle:
        srt_path = os.path.join(task_dir, f"voiceforge_{tr.task_id}.srt")
        if units:
            audio.make_srt_units(units, srt_path)
        else:
            audio.make_srt([s.dict() for s in tr.segments], srt_path)
        tr.subtitle_url = f"/outputs/{tr.task_id}/voiceforge_{tr.task_id}.srt"
    tr.audio_url = f"/outputs/{tr.task_id}/{final_name}"
    tr.duration = sum(s.duration for s in tr.segments)
    tr.status = "done"
    tr.progress = 100
    tr.message = f"合成完成 · 共 {len(tr.segments)} 段 · {tr.duration:.1f}s"


async def run_task(task_id: str, req) -> None:
    tr = _tasks[task_id]
    async with _lock(task_id):
        tr.status = "running"
        try:
            text = (req.text or "").strip()
            if not text:
                raise ValueError("文本为空")
            tr.chars = len(text)
            script_mode = req.script_mode
            if script_mode is None:
                script_mode = script_mod.is_script(text)
            tr.message = "剧本模式" if script_mode else "普通模式"
            if script_mode:
                await _run_script(tr, req, text)
            else:
                await _run_plain(tr, req, text)
        except Exception as e:
            tr.status = "failed"
            tr.message = f"合成失败：{e}"
