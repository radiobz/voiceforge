"""灵声 VoiceForge - 自定义音色（语音风格参考）

导入音频/视频片段 -> 提取音轨 -> 分析音色特征 -> 注册为可选项。
Edge-TTS 不支持真克隆，因此提供「近似音色匹配」：按性别 + 基频距离
推荐最接近的内置音色用于合成；参考音频被持久保存，供将来接入
CosyVoice2 等零样本克隆引擎时直接作为 prompt_speech 使用。
"""
from __future__ import annotations

import json
import os
import subprocess
import uuid

import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
REFS_DIR = os.path.join(DATA_DIR, "refs")
REGISTRY_PATH = os.path.join(DATA_DIR, "custom_voices.json")
os.makedirs(REFS_DIR, exist_ok=True)

MAX_UPLOAD = 200 * 1024 * 1024      # 200MB
ANALYZE_MAX_SEC = 300.0             # 只分析前 5 分钟
MIN_DURATION = 2.0                  # 至少 2 秒才有分析意义

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv", ".m4v"}

# 中文音色的基准基频（近似值，用于匹配打分）
ZH_BASELINE_F0 = {
    "zh-CN-XiaoxiaoNeural": 205, "zh-CN-XiaoyiNeural": 210,
    "zh-CN-YunxiNeural": 145, "zh-CN-YunyangNeural": 150,
    "zh-CN-YunjianNeural": 135, "zh-CN-YunxiaNeural": 165,
    "zh-CN-liaoning-XiaobeiNeural": 200, "zh-CN-shaanxi-XiaoniNeural": 215,
    "zh-CN-XiaomoNeural": 200, "zh-CN-XiaohanNeural": 215,
    "zh-CN-XiaomengNeural": 230, "zh-CN-XiaochenNeural": 190,
    "zh-CN-XiaoruiNeural": 220, "zh-CN-XiaoshuangNeural": 260,
    "zh-CN-XiaoxuanNeural": 215, "zh-CN-XiaoyouNeural": 240,
    "zh-CN-XiaozhenNeural": 225, "zh-CN-YunfengNeural": 160,
    "zh-CN-YunhaoNeural": 155, "zh-CN-YunjieNeural": 150,
    "zh-CN-YunyeNeural": 165, "zh-CN-YunzeNeural": 140,
}


def _is_video(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in VIDEO_EXTS


def _is_supported(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in (AUDIO_EXTS | VIDEO_EXTS)


def extract_audio(data: bytes, filename: str, out_wav: str) -> float:
    """提取音轨为 16k 单声道 wav；返回时长（秒）。"""
    ext = os.path.splitext(filename)[1].lower() or ".mp3"
    tmp = os.path.join(REFS_DIR, f".tmp_{uuid.uuid4().hex}{ext}")
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", tmp, "-vn", "-ac", "1", "-ar", "16000",
             "-t", str(ANALYZE_MAX_SEC), out_wav],
            capture_output=True)
        if r.returncode != 0 or not os.path.exists(out_wav) or os.path.getsize(out_wav) < 2048:
            err = (r.stderr or b"").decode("utf-8", "ignore")[-300:]
            if "does not contain any stream" in err or "no audio" in err.lower():
                raise ValueError("文件中没有可用的音频轨道")
            raise ValueError(f"音轨提取失败：{err.splitlines()[-1] if err else 'unknown'}")
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", out_wav],
            capture_output=True)
        try:
            return float(json.loads(probe.stdout).get("format", {}).get("duration", 0))
        except Exception:
            return 0.0
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _decode(wav_path: str) -> np.ndarray:
    r = subprocess.run(
        ["ffmpeg", "-v", "quiet", "-i", wav_path, "-f", "f32le",
         "-ac", "1", "-ar", "16000", "-"],
        capture_output=True)
    if r.returncode != 0:
        err = (r.stderr or b"").decode("utf-8", "ignore")[-300:]
        raise ValueError(f"音频解码失败：{err.splitlines()[-1] if err else 'unknown'}")
    return np.frombuffer(r.stdout, dtype=np.float32)


def _f0_series(x: np.ndarray, sr: int = 16000,
               win: int = 400, hop: int = 160) -> list[float]:
    """自相关法基频估计（60~400Hz），仅保留浊音帧。"""
    f0s: list[float] = []
    n = len(x)
    lo, hi = sr // 400, sr // 60
    for start in range(0, n - win, hop):
        frame = x[start:start + win]
        if float(np.sqrt((frame ** 2).mean())) < 0.02:
            continue
        f = frame - frame.mean()
        ac = np.correlate(f, f, mode="full")[win - 1: win + win // 2]
        if ac[0] <= 0:
            continue
        ac = ac / ac[0]
        seg = ac[lo:hi + 1]
        if len(seg) < 2 or float(seg.max()) < 0.25:
            continue
        peak = int(np.argmax(seg)) + lo
        f0 = sr / peak
        if 60 <= f0 <= 400:
            f0s.append(f0)
    return f0s


def _speech_ratio(x: np.ndarray, win: int = 160) -> float:
    n = len(x) // win
    if n == 0:
        return 0.0
    rms = np.sqrt((x[:n * win].reshape(n, win) ** 2).mean(axis=1))
    return float((rms > 0.02).mean())


def _syllable_rate(x: np.ndarray, speech_ratio: float, duration: float) -> float:
    """粗略音节速率（能量包络起振数 / 有声时长）。仅用于快/中/慢标签。"""
    if duration <= 0:
        return 0.0
    win = 160
    n = len(x) // win
    if n == 0:
        return 0.0
    rms = np.sqrt((x[:n * win].reshape(n, win) ** 2).mean(axis=1))
    voiced = rms > 0.03
    onsets = int(((voiced[1:] & ~voiced[:-1])).sum())
    speech_dur = max(0.1, speech_ratio * duration)
    return onsets / speech_dur


def analyze_voice(wav_path: str) -> dict:
    """分析音色特征：基频/性别/语速/标签。"""
    x = _decode(wav_path)
    duration = float(len(x)) / 16000.0
    f0s = _f0_series(x)
    f0_median = float(np.median(f0s)) if len(f0s) > 5 else 0.0
    f0_lo = float(np.percentile(f0s, 15)) if f0s else 0.0
    f0_hi = float(np.percentile(f0s, 85)) if f0s else 0.0
    sr = _speech_ratio(x)
    syll = _syllable_rate(x, sr, duration)

    if f0_median <= 0:
        gender, pitch_tag = "未知", "未检出"
    elif f0_median < 165:
        gender = "男声"
        pitch_tag = "低沉" if f0_median < 120 else ("沉稳" if f0_median < 150 else "清朗")
    elif f0_median > 175:
        gender = "女声"
        pitch_tag = "温柔" if f0_median < 195 else ("清亮" if f0_median < 225 else "甜美高亮")
    else:
        gender = "中性"
        pitch_tag = "低沉" if f0_median < 170 else "清亮"

    rate_tag = "舒缓" if syll < 3 else ("适中" if syll <= 4.5 else "明快")
    tags = [t for t in (gender, pitch_tag, rate_tag) if t and t != "未知"]
    return {
        "duration": round(duration, 1),
        "f0_median": round(f0_median, 1) if f0_median else None,
        "f0_range": [round(f0_lo, 1), round(f0_hi, 1)] if f0s else [],
        "gender": gender, "pitch_tag": pitch_tag, "rate_tag": rate_tag,
        "speech_ratio": round(sr, 2), "syllable_rate": round(syll, 2),
        "tags": tags,
    }


def _gender_of_voice(short_name: str) -> str:
    base = ZH_BASELINE_F0.get(short_name)
    if base is None:
        return ""
    return "男声" if base < 165 else ("女声" if base > 175 else "中性")


def match_edge_voices(features: dict, voices: list[dict], top: int = 3) -> list[dict]:
    """按性别（硬条件）+ 基频距离（半音）推荐最接近的内置中文音色。"""
    f0 = features.get("f0_median") or 0
    gender = features.get("gender", "未知")
    scored = []
    for v in voices:
        if not v["locale"].startswith("zh") or "Multilingual" in v["short_name"]:
            continue
        base = ZH_BASELINE_F0.get(v["short_name"])
        if base is None:
            continue
        if gender in ("男声", "女声") and _gender_of_voice(v["short_name"]) != gender:
            continue
        dist = abs(np.log2(f0 / base)) * 12 if f0 > 0 else 6.0
        scored.append({**v, "match_distance": round(dist, 1)})
    scored.sort(key=lambda s: s["match_distance"])
    return scored[:top]


# ---------- 注册表（持久化） ----------

class CustomVoiceRegistry:
    def __init__(self, path: str = REGISTRY_PATH):
        self.path = path
        self.items: dict[str, dict] = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.items = json.load(f)
            except Exception:
                self.items = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.items, fh, ensure_ascii=False, indent=2)

    def add(self, entry: dict) -> dict:
        # FIX-001：若 entry 已带 id（create_custom 预填）则复用，保证 wav 文件名与 registry id 一致
        vid = entry.get("id") or ("custom_" + uuid.uuid4().hex[:8])
        entry["id"] = vid
        entry["short_name"] = vid
        entry["created_at"] = __import__("time").time()
        self.items[vid] = entry
        self._save()
        return entry

    def get(self, vid: str) -> dict | None:
        return self.items.get(vid)

    def all(self) -> list[dict]:
        return sorted(self.items.values(), key=lambda e: e["created_at"], reverse=True)

    def remove(self, vid: str) -> bool:
        entry = self.items.pop(vid, None)
        if not entry:
            return False
        self._save()
        return True


registry = CustomVoiceRegistry()


def create_custom(filename: str, data: bytes, name: str = "",
                  voices: list[dict] | None = None) -> dict:
    """创建自定义音色：提取 -> 分析 -> 匹配 -> 注册。"""
    if len(data) > MAX_UPLOAD:
        raise ValueError("文件超过 200MB 上限")
    if not _is_supported(filename):
        raise ValueError("仅支持音频（mp3/wav/m4a/aac/ogg/flac）或视频（mp4/mov/mkv/avi/webm）")
    vid = "custom_" + uuid.uuid4().hex[:8]
    wav_path = os.path.join(REFS_DIR, f"{vid}.wav")
    duration = extract_audio(data, filename, wav_path)
    if duration < MIN_DURATION:
        os.remove(wav_path)
        raise ValueError(f"语音片段太短（{duration:.1f}s），至少需要 {MIN_DURATION:.0f} 秒")
    features = analyze_voice(wav_path)
    closest = match_edge_voices(features, voices or []) if voices else []
    entry = {
        "id": vid,
        "short_name": vid,
        "source": filename,
        "display_name": name.strip() or os.path.splitext(os.path.basename(filename))[0],
        "ref_wav": f"/api/voices/custom/{vid}/audio",
        "analysis": features,
        "closest": closest,
    }
    return registry.add(entry)


def resolve_voice(voice_id: str) -> str:
    """自定义音色 id -> 最接近的内置音色 short_name；普通音色原样返回。"""
    if not voice_id or not voice_id.startswith("custom_"):
        return voice_id
    entry = registry.get(voice_id)
    if not entry:
        return voice_id
    closest = entry.get("closest") or []
    return closest[0]["short_name"] if closest else "zh-CN-XiaoxiaoNeural"
