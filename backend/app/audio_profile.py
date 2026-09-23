"""灵声 VoiceForge - 音乐风格分析（v0.6）

对音频/视频提取风格特征：BPM、调式（key/mode）、亮度、频谱斜率、能量、
鼓组强度与节奏网格、黑胶/噪点密度、噪声平坦度等；并映射为生成参数
（供 musicgen 的 profile 覆盖使用）。
纯 numpy + ffmpeg，完全离线。
"""
from __future__ import annotations

import os
import subprocess
import tempfile

import numpy as np

SR = 44100
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Schmuckler 调性分布模板
_KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def load_audio(path: str, max_sec: float = 120.0) -> np.ndarray:
    """解码任意音频/视频为单声道 float32（[-1,1]，截取前 max_sec 秒）。"""
    fd, tmp = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", path,
             "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", tmp],
            check=True, capture_output=True)
        import wave
        with wave.open(tmp, "rb") as wf:
            n = wf.getnframes()
            data = np.frombuffer(wf.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
        return data[:int(max_sec * SR)]
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _stft(x: np.ndarray, n_fft: int = 2048, hop: int = 512) -> np.ndarray:
    frames = 1 + (len(x) - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(frames)[:, None]
    win = np.hanning(n_fft)
    return np.fft.rfft(x[idx] * win, axis=1)


def detect_bpm(x: np.ndarray) -> tuple[float, float]:
    """频谱通量自相关 -> BPM。返回 (bpm, 置信度 0~1)。"""
    n_fft, hop = 1024, 256
    if len(x) < n_fft * 2:
        return 0.0, 0.0
    S = np.abs(_stft(x, n_fft, hop))
    flux = np.diff(np.mean(S, axis=1), axis=0)
    flux = np.clip(flux, 0, None)
    flux -= np.mean(flux)
    flux /= (np.std(flux) + 1e-9)
    ac = np.correlate(flux, flux, "full")[len(flux) - 1:]
    ac[:2] = 0
    min_lag = int(60 / 200 * SR / hop)     # 200 BPM 上限
    max_lag = int(60 / 50 * SR / hop)      # 50 BPM 下限
    seg = ac[min_lag:max_lag]
    if seg.size < 2 or np.max(seg) <= 0:
        return 0.0, 0.0
    lag = min_lag + int(np.argmax(seg))
    bpm = 60.0 / (lag * hop / SR)
    # 倍速修正：落在 50~110 区间（lofi 常见）
    while bpm < 55:
        bpm *= 2
    while bpm > 115:
        bpm /= 2
    conf = float(np.clip(np.max(seg) / (np.mean(seg) + 1e-9) / 8, 0, 1))
    return round(bpm, 1), conf


def detect_key(x: np.ndarray) -> tuple[str, str, float]:
    """色度向量与调性模板相关 -> (key, major/minor, 置信度)。"""
    if len(x) < 4096:
        return "C", "major", 0.0
    S = np.mean(np.abs(_stft(x)) ** 2, axis=0)
    freqs = np.fft.rfftfreq(2048, 1 / SR)
    chroma = np.zeros(12)
    for i in range(12):
        f0 = 55.0 * 2 ** (i / 12)
        mask = (freqs >= f0 * 0.85) & (freqs < f0 * 1.7 * 8)   # 含泛音（至 8 倍频）
        # 只取属于该音阶级的频率（f0 * 2^k）
        k_mask = np.zeros_like(freqs, dtype=bool)
        for k in range(1, 9):
            lo, hi = f0 * 2 ** k * 0.97, f0 * 2 ** k * 1.03
            k_mask |= (freqs >= lo) & (freqs < hi)
        chroma[i] = np.sum(S[k_mask])
    if np.max(chroma) <= 0:
        return "C", "major", 0.0
    chroma = chroma / (np.linalg.norm(chroma) + 1e-9)
    best_key, best_mode, best_s = 0, "major", -1.0
    for shift in range(12):
        c = np.roll(chroma, shift)
        s_maj = float(np.dot(c, _KS_MAJOR / np.linalg.norm(_KS_MAJOR)))
        s_min = float(np.dot(c, _KS_MINOR / np.linalg.norm(_KS_MINOR)))
        if s_maj > best_s:
            best_s, best_key, best_mode = s_maj, shift, "major"
        if s_min > best_s:
            best_s, best_key, best_mode = s_min, shift, "minor"
    return NOTE_NAMES[best_key], best_mode, float(np.clip(best_s * 6, 0, 1))


def _frame_rms(x: np.ndarray, hop: int = 512) -> np.ndarray:
    n = (len(x) - hop) // hop
    return np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)


def detect_beat(x: np.ndarray, bpm: float) -> dict:
    """低频脉冲检测：是否 4/4 稳态节拍 + 每小节 kick 密度。"""
    if bpm <= 0 or len(x) < SR * 2:
        return dict(beat=False, kick_density=0.0, grid_conf=0.0)
    low = np.convolve(x, np.ones(80) / 80, "same")          # ~550Hz 低通
    rms = _frame_rms(np.abs(low))
    thr = np.mean(rms) + 1.5 * np.std(rms)
    onsets = np.where(rms > thr)[0]
    if len(onsets) < 4:
        return dict(beat=False, kick_density=0.0, grid_conf=0.0)
    beat = 60.0 / bpm
    beat_frames = beat / (512 / SR)
    # 把 onset 对齐到最近节拍网格，统计命中率
    hits = np.zeros(int(len(rms) / max(1, beat_frames)) + 1, dtype=int)
    for o in onsets:
        bi = int(round(o / beat_frames))
        if 0 <= bi < len(hits):
            hits[bi] += 1
    active = np.mean(hits > 0)
    conf = float(np.clip(active * 2 - 0.4, 0, 1))
    kicks_per_beat = len(onsets) / max(1.0, len(rms) / beat_frames)
    kick_den = float(np.clip(kicks_per_beat / 2.0, 0, 1))
    return dict(beat=conf > 0.35, kick_density=round(kick_den, 2), grid_conf=round(conf, 2))


def detect_texture(x: np.ndarray) -> dict:
    """亮度（频谱质心）、频谱斜率、平坦度、高频噪点密度（黑胶感）。"""
    S = np.abs(_stft(x)) ** 2
    S = np.mean(S, axis=0) + 1e-12
    freqs = np.fft.rfftfreq(2048, 1 / SR)
    centroid = float(np.sum(freqs * S) / np.sum(S))
    logf = np.log(freqs[1:] + 1e-9)
    logS = np.log(S[1:] + 1e-12)
    slope = float(np.polyfit(logf, logS, 1)[0])
    flat = float(np.exp(np.mean(np.log(S))) / np.mean(S))
    # 6k~16k 冲激密度（黑胶爆点/铙钹质感）
    idx = (freqs >= 6000) & (freqs < 16000)
    if np.sum(idx) > 0:
        hi = S[idx] / (np.mean(S[idx]) + 1e-9)
        crackle = float(np.mean(hi > 6))
    else:
        crackle = 0.0
    return dict(brightness=round(centroid / 1000, 1), spectral_slope=round(slope, 3),
                flatness=round(flat, 4), crackle_density=round(crackle, 4))


def detect_energy(x: np.ndarray) -> dict:
    rms = _frame_rms(x)
    if len(rms) < 2:
        return dict(rms=0.0, dynamics=0.0, active_ratio=0.0)
    gate = np.mean(rms) + 0.5 * np.std(rms)
    return dict(rms=round(float(np.mean(rms)), 4),
                dynamics=round(float(np.std(rms) / (np.mean(rms) + 1e-9)), 2),
                active_ratio=round(float(np.mean(rms > gate)), 2))


def extract(path: str, max_sec: float = 120.0) -> dict:
    x = load_audio(path, max_sec)
    if len(x) < SR:
        return dict(duration=round(len(x) / SR, 2), error="音频过短")
    bpm, bpm_conf = detect_bpm(x)
    key, mode, key_conf = detect_key(x)
    beat = detect_beat(x, bpm)
    tex = detect_texture(x)
    eng = detect_energy(x)
    # 短片段下自相关置信度偏弱，节拍网格命中可补强 BPM 置信度
    bpm_conf = max(bpm_conf, beat.get("grid_conf", 0) * 0.6)
    return dict(duration=round(len(x) / SR, 2),
                bpm=bpm, bpm_confidence=round(bpm_conf, 2),
                key=key, mode=mode, key_confidence=round(key_conf, 2),
                **beat, **tex, **eng)


def to_params(profile: dict) -> dict:
    """风格特征 -> 生成参数覆盖（musicgen profile）。"""
    note_idx = NOTE_NAMES.index(profile.get("key", "C"))
    tonic = 60 + note_idx - (9 if profile.get("mode") == "minor" else 0)   # C3 基准
    p = dict(tonic=tonic, scale=profile.get("mode", "major"))
    if profile.get("bpm", 0) > 0:
        p["bpm"] = profile["bpm"]
    beat = profile.get("beat", False)
    p["beat"] = beat
    p["beat_density"] = profile.get("kick_density", 0.5) if beat else 0.0
    p["vinyl"] = min(1.0, profile.get("crackle_density", 0.0) * 6)
    b = profile.get("brightness", 3.0)
    p["brightness"] = float(np.clip(b / 4.0, 0.3, 1.2))
    eng = profile.get("rms", 0.05)
    p["energy"] = float(np.clip(eng / 0.08, 0.4, 1.4))
    p["confidence"] = round(
        (profile.get("bpm_confidence", 0) + profile.get("key_confidence", 0)) / 2, 2)
    return p
