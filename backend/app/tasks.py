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
import random as _random
import time
import uuid

from . import audio
from . import engines
from . import script as script_mod
from . import voice_lab
from .chunker import chunk_text
from .config import EMOTION_LABELS, EMOTION_PROSODY, OUTPUT_DIR
from .emotion import analyze, analyze_segments
from .schemas import SegmentResult, SynthesizeRequest, TaskResult

_tasks: dict[str, TaskResult] = {}
_locks: dict[str, asyncio.Lock] = {}
# FIX-010：记录任务创建时间，用于 TTL 清理，防止 _tasks/_locks 无限增长
_task_created: dict[str, float] = {}
_TASK_TTL = 3600.0  # 1 小时


def _lock(task_id: str) -> asyncio.Lock:
    if task_id not in _locks:
        _locks[task_id] = asyncio.Lock()
    return _locks[task_id]


def _evict_old_tasks() -> None:
    """清理 done/failed 且超过 TTL 的任务；不动 running/queued。"""
    now = time.time()
    stale = [tid for tid, tr in _tasks.items()
             if tr.status in ("done", "failed")
             and now - _task_created.get(tid, now) > _TASK_TTL]
    for tid in stale:
        _tasks.pop(tid, None)
        _locks.pop(tid, None)
        _task_created.pop(tid, None)


def get_task(task_id: str) -> TaskResult | None:
    _evict_old_tasks()
    return _tasks.get(task_id)


def create_task(req) -> TaskResult:
    task_id = uuid.uuid4().hex[:12]
    tr = TaskResult(task_id=task_id, status="queued", message="任务已创建")
    _tasks[task_id] = tr
    _task_created[task_id] = time.time()
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
                       emotion: str | None, strength: float,
                       task_dir: str, tag: str) -> str:
    """合成单个文本片 -> 修剪前导静音 -> 返回修剪后的 mp3 路径。

    voice 可能是自定义音色 id（custom_xxx），此处解析为最接近的内置音色；
    emotion/strength 供指令式引擎（CosyVoice2/GLM-TTS/豆包）使用，
    韵律型引擎（Edge）忽略它们、直接用 rate/pitch/volume。
    """
    eff_voice = voice_lab.resolve_voice(voice)
    raw = os.path.join(task_dir, f"{tag}_raw.mp3")
    await engines.synthesize(text, raw, eff_voice, rate=rate, pitch=pitch,
                             volume=volume, emotion=emotion, strength=strength)
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
                                   meta["emotion"], meta["strength"],
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
                               emo, st, task_dir, f"line_{i:04d}")
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
            # FIX-011：拼接使用 silence_ms=0，字幕时间轴不再加 0.3s 块间间隙
            audio.make_srt([s.dict() for s in tr.segments], srt_path, gap=0.0)
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


# ---------------------------------------------------------------- 灵声配乐

def _agg_mood(tr: TaskResult) -> str:
    """取语音各段占比最高的情绪作为配乐基调。"""
    counts: dict[str, int] = {}
    for s in tr.segments:
        counts[s.emotion] = counts.get(s.emotion, 0) + 1
    if not counts:
        return "calm"
    return max(counts, key=counts.get)


def _seg_times(tr: TaskResult) -> list[tuple[float, float]]:
    """由分段时长推各段时间区间（拼接零静音，累计起点）。"""
    times = []
    cursor = 0.0
    for s in tr.segments:
        times.append((cursor, cursor + s.duration))
        cursor += s.duration
    return times


def _voice_file(task_id: str) -> str:
    """定位已合成语音任务的主音频文件（merged.mp3 或最终命名）。"""
    d = os.path.join(OUTPUT_DIR, task_id)
    for name in ("merged.mp3", f"voiceforge_{task_id}.mp3", f"voiceforge_{task_id}.wav"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return ""


async def run_music_generate(task_id: str, req) -> None:
    """独立音乐生成：随机 / 指定风格情绪时长种子。"""
    from . import musicgen
    tr = _tasks[task_id]
    async with _lock(task_id):
        tr.status = "running"
        try:
            seconds = max(10.0, min(musicgen.MAX_SECONDS, float(req.duration)))
            mood = req.mood or _random.choice(musicgen.DEFAULT_MOOD_POOL)
            seed = req.seed if req.seed is not None else _random.randrange(1, 1_000_000)
            tr.progress = 15
            tr.message = f"谱曲中 · {req.mode} · {mood} · seed {seed}"
            task_dir = os.path.join(OUTPUT_DIR, tr.task_id)
            os.makedirs(task_dir, exist_ok=True)
            final_name = f"voiceforge_{tr.task_id}.mp3"
            final_path = os.path.join(task_dir, final_name)
            meta = musicgen.generate(req.mode, mood, seconds, seed, final_path,
                                     profile=getattr(req, "profile", None),
                                     rhythm=getattr(req, "rhythm", None),
                                     guitar=getattr(req, "guitar", None))
            tr.progress = 96
            tr.message = "编码 MP3"
            tr.audio_url = f"/outputs/{tr.task_id}/{final_name}"
            tr.music_meta = {**meta, "label": _MUSIC_MOOD_LABEL.get(mood, mood)}
            tr.duration = seconds
            tr.progress = 100
            tr.status = "done"
            tr.message = (f"音乐生成完成 · {seconds:.0f}s · {meta['key']}调 · "
                          f"{meta['bpm']}BPM · {_MUSIC_MOOD_LABEL.get(mood, mood)} · seed {seed}")
        except Exception as e:
            tr.status = "failed"
            tr.message = f"音乐生成失败：{e}"


_MUSIC_MOOD_LABEL = {
    "joy": "开心·明亮", "sad": "悲伤·舒缓", "calm": "平静·空灵",
    "angry": "张力·小调", "fear": "暗色·缥缈", "surprised": "惊喜·灵动",
}


async def run_music_adapt(task_id: str, req) -> None:
    """自适应配乐：语音 + 情绪/时长匹配音乐 + 音量平衡混音。

    输入二选一：复用已有 TTS 任务（task_id）或直接给文本（先合成语音）。
    """
    from . import musicgen
    tr = _tasks[task_id]
    async with _lock(task_id):
        tr.status = "running"
        internal_voice_task: str | None = None
        try:
            voice_task = req.task_id or ""
            voice_tr = None
            if req.task_id:
                voice_tr = _tasks.get(req.task_id)
            if voice_tr is None and (req.text or "").strip():
                # 先合成语音（复用现有 TTS 流水线）
                stt = SynthesizeRequest(
                    text=req.text, voice=req.voice, emotion=req.emotion,
                    emotion_strength=req.emotion_strength,
                    auto_emotion=req.auto_emotion, rate=req.rate,
                    pitch=req.pitch, volume=req.volume,
                    script_mode=req.script_mode, role_map=req.role_map,
                    with_subtitle=req.with_subtitle)
                voice_task = uuid.uuid4().hex[:12]
                internal_voice_task = voice_task
                _tasks[voice_task] = TaskResult(task_id=voice_task, status="queued",
                                                message="语音合成中")
                _task_created[voice_task] = time.time()
                await run_task(voice_task, stt)
                voice_tr = _tasks.get(voice_task)
            if voice_tr is None or voice_tr.status != "done":
                raise ValueError("未找到可配乐的语音（task_id 无效且未提供文本）")
            voice_path = _voice_file(voice_task)
            if not voice_path:
                raise ValueError("语音音频文件缺失")
            # 配乐基调：文本情绪自适应 or 手动指定
            mood = req.mood or _agg_mood(voice_tr)
            seconds = voice_tr.duration + 2.0
            seed = _random.randrange(1, 1_000_000)
            tr.progress = 8
            tr.message = f"语音就绪 · {voice_tr.duration:.1f}s · 配乐基调 {_MUSIC_MOOD_LABEL.get(mood, mood)}"
            task_dir = os.path.join(OUTPUT_DIR, tr.task_id)
            os.makedirs(task_dir, exist_ok=True)
            music_path = os.path.join(task_dir, f"voiceforge_{tr.task_id}_music.mp3")
            meta = musicgen.generate(req.mode, mood, seconds, seed, music_path)
            tr.progress = 60
            tr.message = "混音中（说话段自动压低音乐）"
            mix_path = os.path.join(task_dir, f"voiceforge_{tr.task_id}_mix.mp3")
            music_trim = os.path.join(task_dir, f"voiceforge_{tr.task_id}_music_trim.wav")
            mix_wav = os.path.join(task_dir, f"voiceforge_{tr.task_id}_mix.wav")
            dur = musicgen.mix_with_voice(
                voice_path, music_path, _seg_times(voice_tr),
                balance=req.balance, out_mix=mix_wav, out_music=music_trim)
            musicgen.to_mp3(mix_wav, mix_path)
            music_trim_mp3 = os.path.join(task_dir, f"voiceforge_{tr.task_id}_music.mp3")
            musicgen.to_mp3(music_trim, music_trim_mp3)
            # FIX-013：中间 wav 文件在转 mp3 成功后删除
            for _w in (mix_wav, music_trim):
                if os.path.exists(_w):
                    try:
                        os.remove(_w)
                    except OSError:
                        pass
            # 交付文件：语音（复制主文件）、配乐、混音
            voice_dst = os.path.join(task_dir, f"voiceforge_{tr.task_id}_voice.mp3")
            musicgen.to_mp3(voice_path, voice_dst)
            tr.audio_url = f"/outputs/{tr.task_id}/voiceforge_{tr.task_id}_mix.mp3"
            tr.voice_url = f"/outputs/{tr.task_id}/voiceforge_{tr.task_id}_voice.mp3"
            tr.music_url = f"/outputs/{tr.task_id}/voiceforge_{tr.task_id}_music.mp3"
            tr.mix_url = tr.audio_url
            tr.subtitle_url = voice_tr.subtitle_url
            for s in voice_tr.segments:
                tr.segments.append(s)
            tr.music_meta = {**meta, "label": _MUSIC_MOOD_LABEL.get(mood, mood),
                             "balance": req.balance}
            tr.duration = dur
            tr.progress = 100
            tr.status = "done"
            tr.message = (f"配乐完成 · 语音 {voice_tr.duration:.1f}s + 音乐 · "
                          f"{meta['key']}调 {meta['bpm']}BPM · 平衡={req.balance}")
        except Exception as e:
            tr.status = "failed"
            tr.message = f"配乐失败：{e}"
        finally:
            # FIX-012：清理 run_music_adapt 内部创建的 voice_task，避免残留
            if internal_voice_task:
                _tasks.pop(internal_voice_task, None)
                _locks.pop(internal_voice_task, None)
                _task_created.pop(internal_voice_task, None)
