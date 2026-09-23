"""灵声 VoiceForge - 音频后处理（ffmpeg：拼接 / 转格式 / 字幕）"""
from __future__ import annotations

import json
import os
import subprocess
import uuid

from .config import JOIN_SILENCE_MS

SILENCE_CACHE: dict[int, str] = {}


def _silence_file(ms: int) -> str:
    """生成指定毫秒的静音 mp3（缓存复用）。"""
    if ms in SILENCE_CACHE and os.path.exists(SILENCE_CACHE[ms]):
        return SILENCE_CACHE[ms]
    path = os.path.join(os.path.dirname(__file__), ".silence_%dms.mp3" % ms)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono",
         "-t", f"{ms / 1000:.3f}", "-q:a", "9", path],
        check=True, capture_output=True)
    SILENCE_CACHE[ms] = path
    return path


def concat_mp3(seg_files: list[str], out_path: str, silence_ms: int = JOIN_SILENCE_MS) -> None:
    """把多个 mp3 用自然停顿拼接为单个 mp3。silence_ms<=0 时不插入额外静音。"""
    if not seg_files:
        raise ValueError("empty segments")
    if len(seg_files) == 1:
        subprocess.run(["ffmpeg", "-y", "-i", seg_files[0], "-codec", "copy", out_path],
                       check=True, capture_output=True)
        return
    silence = _silence_file(silence_ms) if silence_ms > 0 else None
    list_path = os.path.join(os.path.dirname(out_path), f".concat_{uuid.uuid4().hex}.txt")
    lines = []
    for i, f in enumerate(seg_files):
        if i > 0 and silence:
            lines.append(f"file '{silence.replace(chr(39), chr(39)*2)}'")
        lines.append(f"file '{f.replace(chr(39), chr(39)*2)}'")
    with open(list_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
             "-c:a", "libmp3lame", "-q:a", "2", out_path],
            check=True, capture_output=True)
    finally:
        if os.path.exists(list_path):
            os.remove(list_path)


def trim_leading_silence_mp3(src: str, dst: str, threshold_db: float = -48.0) -> None:
    """修剪开头近静音。

    edge-tts 每个合成片段（SSML 单元）开头都会带约 150~190ms 的前导静音，
    多片段拼接时会在句中形成可闻的"断音"。本函数只移除真正低于阈值的静音，
    不影响语音起始辅音。
    """
    subprocess.run(
        ["ffmpeg", "-y", "-i", src,
         "-af", f"silenceremove=start_periods=1:start_threshold={threshold_db}dB:start_silence=0.04",
         "-c:a", "libmp3lame", "-q:a", "2", dst],
        check=True, capture_output=True)


def to_wav(src_mp3: str, out_wav: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-i", src_mp3, "-ar", "44100", "-ac", "2", out_wav],
                   check=True, capture_output=True)


def duration_ms(path: str) -> float:
    """返回音频时长（秒）。"""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", path], capture_output=True, check=True)
        info = json.loads(r.stdout)
        return float(info.get("format", {}).get("duration", 0))
    except Exception:
        return 0.0


def make_srt(segments: list[dict], out_path: str) -> None:
    """按分块时长生成 SRT 字幕（各块内按句号二次均分时间）。"""
    entries = []
    cursor = 0.0
    for seg in segments:
        dur = seg.get("duration", 0.0)
        text = seg.get("text", "")
        # 块内按句子拆分（最多 6 段），时间均分
        import re
        parts = re.split(r"(?<=[。！？；!?;])", text)
        parts = [p for p in parts if p.strip()]
        if not parts:
            parts = [text]
        per = dur / len(parts)
        for i, p in enumerate(parts):
            start = cursor + i * per
            end = start + per
            entries.append((start, end, p.strip()))
        cursor += dur + 0.3  # 块间加 0.3s 空隙对齐拼接静音

    _write_srt(entries, out_path)


def make_srt_units(units: list[dict], out_path: str, gap: float = 0.2) -> None:
    """按实际台词行时长生成 SRT（剧本模式，逐行精确计时）。"""
    entries = []
    cursor = 0.0
    for u in units:
        dur = u.get("duration", 0.0)
        text = u.get("text", "").strip()
        role = u.get("role", "")
        if not text:
            continue
        label = f"[{role}] {text}" if role else text
        entries.append((cursor, cursor + dur, label))
        cursor += dur + gap
    _write_srt(entries, out_path)


def _write_srt(entries: list[tuple], out_path: str) -> None:
    def _fmt(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int((sec - int(sec)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for i, (s, e, t) in enumerate(entries, 1):
        lines.append(str(i))
        lines.append(f"{_fmt(s)} --> {_fmt(e)}")
        lines.append(t)
        lines.append("")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
