"""灵声 VoiceForge - 算法生成音乐引擎（v0.5 灵声配乐）

基于 numpy 的程序化氛围音乐合成器（Brian Eno 式生成音乐思路），
完全离线、免费、每次随机：
  - 分层：暖垫和弦(pad) + 低音(drone/bass) + 稀疏琶音/弹拨(arp/pluck)
          + 滤波噪声氛围(texture) + 单点回声(doubling) + 立体声展宽(haas)
  - 参数：风格 x 情绪(调式/速度) x 时长(最长 40 分钟) x 随机种子
  - 渲染：分块渲染流式写 WAV（内存恒定），再经 ffmpeg 转 MP3

情绪 -> 调式映射：
  joy 大调明亮 / sad 小调舒缓 / calm 五声音阶空灵 / angry 小调张力
  fear 暗色 drone / surprised 大调灵动
"""
from __future__ import annotations

import os
import random
import struct
import subprocess
import wave

import numpy as np

SR = 44100
MAX_SECONDS = 2400          # 40 分钟上限
CHUNK = 60                  # 每块渲染 60s，流式写盘
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# 和声模式（相对根音的半音）
CHORD_PATTERNS = {
    "maj7": [0, 4, 7, 11],
    "min7": [0, 3, 7, 10],
    "dom7": [0, 4, 7, 10],
    "m6":   [0, 3, 7, 9],
    "M6":   [0, 4, 7, 9],
    "sus2": [0, 2, 7],
    "add9": [0, 4, 7, 14],
    "drone": [0, 7],
}
PENTA = [0, 2, 4, 7, 9]     # 大调五声（琶音/弹拨用）

# 情绪 -> 进行 + 速度 + 亮度
MOODS = {
    "joy":       dict(prog=[("maj7", 0), ("min7", -3), ("maj7", -4), ("M6", -2)],
                      bpm=(70, 80), bright=0.72, kind="major"),
    "calm":      dict(prog=[("sus2", 0), ("add9", -4), ("sus2", 2), ("add9", -2)],
                      bpm=(56, 66), bright=0.48, kind="pentatonic"),
    "sad":       dict(prog=[("min7", 0), ("maj7", -4), ("min7", 5), ("maj7", 7)],
                      bpm=(50, 58), bright=0.34, kind="minor"),
    "angry":     dict(prog=[("min7", 0), ("maj7", -4), ("min7", 5), ("dom7", 7)],
                      bpm=(64, 74), bright=0.42, kind="minor"),
    "fear":      dict(prog=[("min7", 0), ("add9", -4), ("min7", 0), ("maj7", -4)],
                      bpm=(44, 52), bright=0.28, kind="dark"),
    "surprised": dict(prog=[("maj7", 0), ("maj7", 2), ("min7", -1), ("maj7", 7)],
                      bpm=(76, 86), bright=0.8, kind="major"),
}

# 未指定情绪时的默认基调池（偏暗暖，避免明亮大调刺耳）
DEFAULT_MOOD_POOL = ["calm", "calm", "sad", "fear"]

# 风格 -> 分层参数
#   rhythm_def: 默认节奏密度 none/light/standard/full；swing: 八分音符摆动
#   guitar: 是否启用吉他（Karplus-Strong 拨弦）层
MODES = {
    "chill":      dict(chord_len=(7, 9), arp_step=(0.28, 0.4), arp_prob=0.45,
                       pluck=True, pad_gain=0.16, bass_gain=0.13, arp_gain=0.075,
                       pluck_gain=0.06, noise_gain=0.030, noise_cut=420, lfo=(0.06, 0.1),
                       rhythm_def="light", swing=0.08, guitar=True, guitar_gain=0.065,
                       vinyl=False, wobble=False),
    "meditation": dict(chord_len=(12, 18), arp_step=(1.2, 2.0), arp_prob=0.35,
                       pluck=False, pad_gain=0.20, bass_gain=0.17, arp_gain=0.05,
                       pluck_gain=0.0, noise_gain=0.045, noise_cut=300, lfo=(0.03, 0.06),
                       rhythm_def="none", swing=0.0, guitar=False, guitar_gain=0.0,
                       vinyl=False, wobble=False),
    "ambient":    dict(chord_len=(9, 12), arp_step=(0.7, 1.1), arp_prob=0.4,
                       pluck=True, pad_gain=0.18, bass_gain=0.14, arp_gain=0.06,
                       pluck_gain=0.05, noise_gain=0.035, noise_cut=360, lfo=(0.05, 0.08),
                       rhythm_def="light", swing=0.06, guitar=True, guitar_gain=0.05,
                       vinyl=False, wobble=False),
    "lofi":       dict(chord_len=(9, 13), arp_step=(0.42, 0.6), arp_prob=0.42,
                       pluck=True, pad_gain=0.17, bass_gain=0.15, arp_gain=0.07,
                       pluck_gain=0.055, noise_gain=0.030, noise_cut=300, lfo=(0.05, 0.08),
                       rhythm_def="standard", swing=0.12, guitar=True, guitar_gain=0.055,
                       vinyl=True, wobble=True),
}

RHYTHM_DENSITY = {"none": 0.0, "light": 0.35, "standard": 0.6, "full": 0.9}

# lofi 的柔和进行（7/9 和弦为主，chill-hop 风格；避免明亮大调 maj7 刺耳）
LOFI_PROGS = {
    "major": [("add9", 0), ("min7", -3), ("add9", -4), ("sus2", -2)],
    "minor": [("min7", 0), ("add9", -4), ("min7", 5), ("add9", 7)],
    "pentatonic": [("sus2", 0), ("add9", -4), ("sus2", 2), ("add9", -2)],
}

GAIN_SAFE = 0.90           # 输出峰值安全系数


def _note_name(midi: int) -> str:
    return f"{NOTE_NAMES[(midi % 12 + 12) % 12]}{midi // 12 - 1}"


def _midi_to_freq(m: int) -> float:
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def _lowpass_fft(x: np.ndarray, cutoff: float) -> np.ndarray:
    """一阶低通（FFT 频域滤波，矢量快速）。"""
    n = len(x)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    filt = 1.0 / (1.0 + (freqs / cutoff) ** 2)
    return np.fft.irfft(np.fft.rfft(x) * filt, n=n).astype(np.float32)


# ---------------------------------------------------------------- 事件生成

def _plan(seed: int, mode: str, mood: str, seconds: float,
          profile: dict | None = None, rhythm: str | None = None,
          guitar: bool | None = None) -> dict:
    """由种子生成整首音乐的结构计划（和声/琶音/弹拨/吉他/鼓组/黑胶）。

    profile: audio_profile.to_params() 的风格覆盖（tonic/scale/bpm/beat/vinyl/...）。
    rhythm: 节奏密度 none/light/standard/full，None=按风格默认（参考风格有律动时取 standard）。
    guitar: 吉他层开关，None=按风格默认。
    """
    rng = random.Random(seed)
    mconf = MOODS[mood]
    st = MODES[mode]
    if guitar is not None:
        st = dict(st)
        st["guitar"] = guitar
    tonic = rng.randint(57, 64)                      # 根音 C3~G3
    bpm = rng.randint(*mconf["bpm"])
    chord_len = rng.uniform(*st["chord_len"])
    n_chords = max(1, int(seconds / chord_len) + 1)
    bright = mconf["bright"]

    # 风格覆盖（分析驱动）
    scale = mconf["kind"]
    if profile:
        if profile.get("tonic"):
            tonic = int(profile["tonic"])
        if profile.get("bpm", 0) > 0:
            bpm = float(profile["bpm"])
        if profile.get("scale"):
            scale = profile["scale"]
        if profile.get("brightness"):
            bright = float(np.clip(profile["brightness"], 0.28, 0.85))
    bright = min(bright, 0.85)                     # 亮度上限：避免刺耳
    if mode == "lofi":
        prog = LOFI_PROGS.get(scale, LOFI_PROGS["major"])
    else:
        prog = mconf["prog"]

    # 和声段
    chords = []
    for i in range(n_chords):
        pat, root_off = prog[i % len(prog)]
        start = i * chord_len
        end = min(start + chord_len, seconds)
        if end - start < 1.0:
            break
        notes = [tonic + root_off + iv for iv in CHORD_PATTERNS[pat]]
        chords.append((start, end, notes, bright))
    # 琶音事件（中低音域五声音阶点缀，整体降八度，避免高频"风铃"感）
    arps = []
    step = rng.uniform(*st["arp_step"])
    t = 0.0
    while t < seconds:
        if rng.random() < st["arp_prob"]:
            deg = rng.choice(PENTA)
            octv = rng.choice([0, 0, 12])
            nn = min(tonic + deg + octv, tonic + 12)
            arps.append((t, rng.uniform(0.5, 0.9), _midi_to_freq(nn),
                         rng.uniform(0.6, 1.0)))
        t += step
    # 弹拨事件（chill/ambient 的"钢琴"点缀，同样收敛在中低音域）
    plucks = []
    if st["pluck"]:
        t = 0.0
        pstep = rng.uniform(1.6, 2.6)
        while t < seconds:
            if rng.random() < 0.35:
                deg = rng.choice(PENTA)
                nn = min(tonic + deg + 12, tonic + 12)
                plucks.append((t, rng.uniform(1.0, 1.6), _midi_to_freq(nn),
                               rng.uniform(0.7, 1.0)))
            t += pstep

    # ---- 吉他（Karplus-Strong 拨弦：和弦扫弦 + 指弹点缀）
    guitar: list[tuple] = []
    if st["guitar"]:
        for (cs, ce, notes, _) in chords:
            strings = [notes[0], notes[1], notes[2]]
            if ce - cs > 2.0 and notes[0] + 12 <= 84:
                strings.append(notes[0] + 12)
            for k, nn in enumerate(strings):
                guitar.append((cs + k * 0.028, _midi_to_freq(nn),
                               rng.uniform(0.6, 0.85)))
            t = cs + 0.5
            while t < ce - 0.4:
                if rng.random() < 0.55:
                    nn = rng.choice(notes)
                    guitar.append((t, _midi_to_freq(nn), rng.uniform(0.35, 0.6)))
                t += rng.uniform(0.3, 0.65)

    # ---- 鼓组（kick / snare / 摆动 hi-hat；节奏密度可调）
    drums: list[tuple] = []
    if rhythm is None:
        rhythm = "standard" if (profile and profile.get("beat")) else st["rhythm_def"]
    if rhythm not in RHYTHM_DENSITY:
        rhythm = st["rhythm_def"]
    density = RHYTHM_DENSITY[rhythm]
    snare_on = rhythm in ("standard", "full")
    if rhythm != "none" and bpm > 0:
        step_b = 60.0 / bpm
        swing = st["swing"] * step_b
        eighth = step_b / 2
        t = 0.0
        beat_i = 0
        while t < seconds:
            bar_pos = beat_i % 4
            if bar_pos in (0, 2) and random.Random(seed + beat_i).random() < density:
                drums.append(("kick", t, random.Random(seed + beat_i * 7).uniform(0.85, 1.0)))
            elif bar_pos == 3 and density > 0.7 and random.Random(seed + beat_i).random() < density * 0.4:
                drums.append(("kick", t + swing, random.Random(seed + beat_i * 7).uniform(0.5, 0.7)))
            if snare_on and bar_pos in (1, 3):
                drums.append(("snare", t, random.Random(seed + beat_i * 13).uniform(0.4, 0.55)))
            for off, swing_on in ((0.0, False), (eighth, True)):
                ht = t + off + (swing if swing_on else 0.0)
                p = 0.75 if rhythm != "full" else 0.9
                if ht < seconds and random.Random(seed + beat_i * 3).random() < p:
                    drums.append(("hat", ht, random.Random(seed + beat_i * 17).uniform(0.35, 0.6)))
            t += step_b
            beat_i += 1

    # ---- 黑胶噪点（lofi：稀疏高频爆点）
    vinyl = float(profile.get("vinyl", 0.0)) if profile else (0.15 if st["vinyl"] else 0.0)
    bursts: list[tuple] = []
    if st["vinyl"] or (profile and vinyl > 0.02):
        rate = 1.5 + 6.0 * min(1.0, vinyl)
        t = 0.0
        while t < seconds:
            if rng.random() < rate / 4.0:
                bursts.append((t, rng.uniform(0.012, 0.03) * (0.4 + vinyl)))
            t += 0.25
    return dict(rng=rng, tonic=tonic, bpm=bpm, mode=mode, mood=mood,
                chords=chords, arps=arps, plucks=plucks, guitar=guitar, drums=drums,
                bursts=bursts, vinyl=vinyl, beat=rhythm != "none", rhythm=rhythm,
                seconds=seconds, bright=bright, st=st,
                np_seed=rng.randrange(0, 2 ** 31))


# ---------------------------------------------------------------- 渲染

def _render_block(plan: dict, b0: float, b1: float) -> np.ndarray:
    """渲染 [b0, b1) 秒的立体声总线（float32, [-1,1]）。"""
    n = int((b1 - b0) * SR)
    n2 = n + int(2.0 * SR)                 # 尾部窗口（容纳衰减尾巴）
    t = np.arange(n2, dtype=np.float32) / SR
    bus = np.zeros(n2, dtype=np.float32)
    rng = plan["rng"]
    st = plan["st"]
    bright = plan["bright"]

    # ---- 和弦垫层
    for (s, e, notes, br) in plan["chords"]:
        if e <= b0 or s >= b1:
            continue
        os_ = max(0, s - b0)
        oe = min(e - b0, b1 - b0)
        k0, k1 = int(os_ * SR), int(oe * SR)
        seg = np.arange(k0, k1, dtype=np.float32) / SR + b0
        env = np.ones(k1 - k0, dtype=np.float32)
        atk = min(int(min(1.6, (e - s) / 2) * SR), len(env))
        rel = min(int(min(2.6, (e - s) / 2) * SR), len(env))
        if atk > 0:
            env[:atk] = np.linspace(0.0, 1.0, atk)
        if rel > 0:
            env[-rel:] *= np.linspace(1.0, 0.0, rel)
        for note in notes[:3]:             # 根音/三音/七音（省第五音）
            f = _midi_to_freq(note)
            g = st["pad_gain"] * (0.9 + 0.3 * br)
            ph = 2 * np.pi * f * seg
            tone = (np.sin(ph) + 0.35 * np.sin(2 * ph)
                    + 0.12 * np.sin(3 * ph)) / 1.47
            bus[k0:k1] += g * tone * env
            bus[k0:k1] += 0.55 * g * np.sin(2 * np.pi * f * 1.0012 * seg) * env

    # ---- 低音（根音 -12/-24，正弦）
    bass_f = _midi_to_freq(plan["tonic"] - 12)
    nch = len(plan["chords"])
    for i, (s, e, notes, _br) in enumerate(plan["chords"]):
        if e <= b0 or s >= b1:
            continue
        os_ = max(0, s - b0)
        oe = min(e - b0, b1 - b0)
        k0, k1 = int(os_ * SR), int(oe * SR)
        seg = np.arange(k0, k1, dtype=np.float32) / SR + b0
        f = bass_f if i % 2 == 0 else bass_f / 2.0
        env = np.ones(k1 - k0, dtype=np.float32)
        atk = int(1.4 * SR); rel = int(2.2 * SR)
        if atk > 0: env[:min(atk, len(env))] = np.linspace(0.0, 1.0, min(atk, len(env)))
        if rel > 0: env[-min(rel, len(env)):] *= np.linspace(1.0, 0.0, min(rel, len(env)))
        bus[k0:k1] += st["bass_gain"] * (np.sin(2 * np.pi * f * seg)
                                         + 0.25 * np.sin(4 * np.pi * f * seg)) * env

    # ---- 琶音/弹拨（指数衰减，按 onset 归属本块渲染；尾部在块边界做平滑）
    spark = np.zeros(n2, dtype=np.float32)
    for ev in plan["arps"] + plan["plucks"]:
        onset, dur, freq, amp = ev
        if onset < b0 or onset > b1 + 2.0 or onset + dur < b0:
            continue
        i0 = int((onset - b0) * SR)
        i1 = min(int((onset - b0 + dur) * SR), n2)
        if i1 <= i0:
            continue
        seg = np.arange(i0, i1, dtype=np.float32) / SR + b0 - onset
        env = np.exp(-seg / (dur * 0.33)) * (1 - np.clip(seg / dur, 0, 1)) ** 2
        g = st["arp_gain"] if ev in plan["arps"] else st["pluck_gain"]
        tone = np.sin(2 * np.pi * freq * seg) + 0.3 * np.sin(4 * np.pi * freq * seg)
        spark[i0:i1] += g * amp * tone * env
    # 块边缘 8ms 平滑：消除分块尾部截断造成的咔哒声
    edge = int(0.008 * SR)
    spark[:edge] *= np.linspace(0.0, 1.0, edge)
    spark[-edge:] *= np.linspace(1.0, 0.0, edge)
    bus[:n] += spark[:n]

    # ---- 吉他（Karplus-Strong 拨弦：块迭代反馈延迟线）
    guitar_bus = np.zeros(n2, dtype=np.float32)
    g_gain = st["guitar_gain"]
    for (t0, freq, vel) in plan["guitar"]:
        if t0 < b0 or t0 > b1 + 0.5:
            continue
        period = max(40, int(SR / freq))
        sustain = 2.2
        n_periods = min(int(sustain * freq), int((b1 + 2.0 - t0) * SR) // period)
        if n_periods <= 0:
            continue
        rng_np = np.random.default_rng(plan["np_seed"] ^ int(t0 * 133357))
        buf = rng_np.normal(0, 1, period).astype(np.float32) * vel
        decay = 10 ** (-2.0 / max(0.1, sustain * freq))
        out = np.empty(n_periods * period, dtype=np.float32)
        for b in range(n_periods):
            seg = buf
            out[b * period:(b + 1) * period] = seg
            buf = (seg + np.roll(seg, -1)) * 0.5 * decay
        i0 = int((t0 - b0) * SR)
        seg_len = min(len(out), n2 - i0)
        if seg_len > 0:
            guitar_bus[i0:i0 + seg_len] += out[:seg_len] * g_gain
    gedge = int(0.003 * SR)
    guitar_bus[:gedge] *= np.linspace(0.0, 1.0, gedge)
    bus[:n] += guitar_bus[:n]

    # ---- 鼓组（kick 正弦音高下滑 / snare 噪声+中频 / hat 短噪声）
    drum_bus = np.zeros(n2, dtype=np.float32)
    for ev in plan["drums"]:
        kind, onset, amp = ev
        if onset < b0 or onset > b1 + 0.5:
            continue
        i0 = int((onset - b0) * SR)
        if kind == "kick":
            ln = int(0.28 * SR)
            seg = np.arange(ln, dtype=np.float32) / SR
            ph = 2 * np.pi * (55.0 * seg + 2.0 * (1.0 - np.exp(-20.0 * seg)))
            tone = np.sin(ph) * np.exp(-6.0 * seg)
            drum_bus[i0:i0 + ln] += 0.22 * amp * tone
        elif kind == "snare":
            ln = int(0.20 * SR)
            rng_np = np.random.default_rng(plan["np_seed"] ^ int(onset * 104729))
            seg = np.arange(ln, dtype=np.float32) / SR
            nse = rng_np.normal(0, 1, ln).astype(np.float32) * np.exp(-seg / 0.05)
            tne = np.sin(2 * np.pi * 185 * seg) * np.exp(-seg / 0.07)
            drum_bus[i0:i0 + ln] += 0.06 * amp * (nse * 0.6 + tne)
        elif kind == "hat":
            ln = int(0.07 * SR)
            rng_np = np.random.default_rng(plan["np_seed"] ^ int(onset * 100003))
            seg = np.arange(ln, dtype=np.float32) / SR
            nse = rng_np.normal(0, 1, ln).astype(np.float32) * np.exp(-seg / 0.02)
            drum_bus[i0:i0 + ln] += 0.03 * amp * nse
    # ---- 黑胶噪点（稀疏短促高频爆点）
    for (t0, amp) in plan["bursts"]:
        if t0 < b0 or t0 > b1:
            continue
        ln = int(0.004 * SR)
        i0 = int((t0 - b0) * SR)
        if i0 + ln <= n2:
            rng_np = np.random.default_rng(plan["np_seed"] ^ int(t0 * 1299709))
            burst = rng_np.normal(0, 1, ln).astype(np.float32) * amp
            drum_bus[i0:i0 + ln] += burst
    edge2 = int(0.004 * SR)
    drum_bus[:edge2] *= np.linspace(0.0, 1.0, edge2)
    drum_bus[-edge2:] *= np.linspace(1.0, 0.0, edge2)
    bus[:n] += drum_bus[:n]

    # ---- 磁带颤音（慢速幅度呼吸，叠加在垫音/低音层上）
    if plan["st"].get("wobble"):
        wob = 1.0 + 0.004 * np.sin(
            2 * np.pi * 0.32 * (np.arange(n, dtype=np.float32) / SR + b0))
        bus[:n] *= wob

    # ---- 噪声氛围（FFT 低通 + 慢速 LFO 呼吸）
    f_lfo = rng.uniform(*st["lfo"])
    rng_np = np.random.default_rng(plan["np_seed"] ^ int(b0 * 7919))
    noise = rng_np.normal(0, 1, n2).astype(np.float32)
    noise = _lowpass_fft(noise, st["noise_cut"])
    noise = noise / (np.max(np.abs(noise)) + 1e-9)
    phase = 2 * np.pi * f_lfo * b0
    lfo = (0.55 + 0.45 * np.sin(phase + 2 * np.pi * f_lfo * t)) ** 1.5
    bus[:n] += st["noise_gain"] * noise[:n] * lfo[:n]

    # ---- 单点回声（doubling，3 抽头矢量实现）
    taps = [0.42, 0.84, 1.68]
    gains = [0.32, 0.18, 0.10]
    wet = np.zeros(n, dtype=np.float32)
    for d, g in zip(taps, gains):
        shift = int(d * SR)
        if shift < n:
            wet[shift:] += g * bus[:n - shift]
    bus = bus[:n] + 0.45 * wet

    # ---- 立体声（haas 5ms 右声道延迟 + 噪声偏置）
    L = bus
    R = np.concatenate([np.zeros(220, dtype=np.float32), bus[:-220]]) if n > 220 else bus
    return np.stack([L, R], axis=1)


def generate_plan(mode: str, mood: str, seconds: float, seed: int,
                  profile: dict | None = None, rhythm: str | None = None,
                  guitar: bool | None = None) -> dict:
    if mode not in MODES:
        raise ValueError(f"未知风格：{mode}（可选 {list(MODES)}）")
    if mood not in MOODS:
        raise ValueError(f"未知情绪：{mood}（可选 {list(MOODS)}）")
    seconds = max(10.0, min(MAX_SECONDS, float(seconds)))
    return _plan(seed, mode, mood, seconds, profile=profile, rhythm=rhythm,
                 guitar=guitar)


def render_wav(plan: dict, out_wav: str) -> None:
    """按计划分块渲染并流式写入 16-bit 立体声 WAV。"""
    seconds = plan["seconds"]
    n_blocks = int(np.ceil(seconds / CHUNK))
    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        peak = 0.0
        for bi in range(n_blocks):
            b0 = bi * CHUNK
            b1 = min(b0 + CHUNK, seconds)
            block = _render_block(plan, b0, b1)
            # 整体淡入 / 淡出
            n = block.shape[0]
            t0 = bi * CHUNK
            if t0 < 3.0:
                k = min(n, int((3.0 - t0) * SR))
                ramp = np.linspace(0.0, 1.0, k)
                block[:k] *= ramp[:, None]
            tail = seconds - t0
            if tail < 5.0 and tail > 0:
                k = min(n, int((5.0 - tail) * SR))
                ramp = np.linspace(0.0, 1.0, k)[::-1]
                block[-k:] *= ramp[:, None]
            peak = max(peak, float(np.max(np.abs(block))))
            block = np.tanh(1.35 * block) / 1.15          # 软限幅
            block *= GAIN_SAFE
            pcm = (block * 32767).astype(np.int16)
            wf.writeframes(pcm.tobytes())
    return peak


def to_mp3(wav_path: str, mp3_path: str, bitrate: str = "192k") -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path, "-b:a", bitrate, mp3_path],
        check=True, capture_output=True)


def generate(mode: str, mood: str, seconds: float, seed: int,
             out_mp3: str, profile: dict | None = None,
             rhythm: str | None = None, guitar: bool | None = None) -> dict:
    """一键生成：plan -> WAV -> MP3，返回元信息（支持风格 profile 覆盖）。"""
    plan = generate_plan(mode, mood, seconds, seed, profile=profile, rhythm=rhythm,
                         guitar=guitar)
    wav = out_mp3.rsplit(".", 1)[0] + ".wav"
    render_wav(plan, wav)
    to_mp3(wav, out_mp3)
    meta = dict(mode=mode, mood=mood, seed=seed, seconds=seconds,
                key=_note_name(plan["tonic"]), bpm=plan["bpm"],
                kind=MOODS[mood]["kind"], beat=plan["beat"],
                rhythm=plan["rhythm"],
                guitar=bool(plan["guitar"]))
    if profile:
        meta["from_profile"] = True
        meta["vinyl"] = round(plan["vinyl"], 3)
    return meta


# ---------------------------------------------------------------- 自适应配乐混音

def load_audio(path: str) -> np.ndarray:
    """解码任意音频为 44.1k 立体声 float32（ffmpeg -> wav -> numpy）。"""
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-ar", str(SR), "-ac", "2",
             "-sample_fmt", "s16", tmp],
            check=True, capture_output=True)
        with wave.open(tmp, "rb") as wf:
            n = wf.getnframes()
            data = np.frombuffer(wf.readframes(n), dtype=np.int16)
        return data.reshape(-1, 2).astype(np.float32) / 32768.0
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def write_audio(audio: np.ndarray, path: str) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
        wf.writeframes(pcm.tobytes())


BALANCE = {
    "loud": dict(gap=0.62, duck=0.46),   # 音乐更明显
    "auto": dict(gap=0.48, duck=0.34),   # 自动平衡
    "low":  dict(gap=0.36, duck=0.22),   # 压低（人声为主）
}


def mix_with_voice(voice_path: str, music_path: str, seg_times: list[tuple[float, float]],
                   out_mix: str, out_music: str,
                   balance: str = "auto") -> float:
    """语音 + 音乐混音：说话段自动压低音乐（带 0.25s 平滑过渡）。

    seg_times: [(start_s, end_s), ...] 语音各段的时间区间。
    out_mix: 混音产物；out_music: 按人声时长裁剪好的纯音乐（配乐交付）。
    返回混音时长（秒）。
    """
    bcfg = BALANCE.get(balance, BALANCE["auto"])
    voice = load_audio(voice_path)
    music = load_audio(music_path)
    if music.shape[0] == 0 or voice.shape[0] == 0:
        raise ValueError("音频解码为空")
    # 音乐按人声时长裁剪（留 2s 收尾），语音补零对齐
    keep = min(music.shape[0], voice.shape[0] + int(2.0 * SR))
    music = music[:keep]
    if voice.shape[0] < keep:
        voice = np.concatenate(
            [voice, np.zeros((keep - voice.shape[0], 2), dtype=np.float32)])
    # 语音段 -> 压低包络（段外 1.0，段内 duck/gap 比例）
    env = np.ones(keep, dtype=np.float32)
    for (s, e) in seg_times:
        i0 = max(0, int((s - 0.08) * SR))
        i1 = min(keep, int((e + 0.20) * SR))
        if i1 <= i0:
            continue
        level = bcfg["duck"] / bcfg["gap"]
        ramp = int(0.25 * SR)
        if i0 > 0:
            env[max(0, i0 - ramp):i0] = np.linspace(1.0, level, min(ramp, i0))
        env[i0:i1] = level
        if i1 < keep:
            env[i1:min(keep, i1 + ramp)] = np.linspace(level, 1.0, min(ramp, keep - i1))
    music_bus = music * (env[:, None] * bcfg["gap"])
    # 淡出混音尾部
    fade = int(1.5 * SR)
    if keep > fade:
        music_bus[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None]
        voice[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None]
    mix = voice + music_bus
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = np.tanh(1.2 * mix / max(peak, 1e-9)) * 0.92 * peak if peak > 1.0 else mix
    write_audio(music_bus * (1.0 / max(bcfg["gap"], 1e-9)), out_music)   # 纯配乐（未压）
    write_audio(mix, out_mix)
    return keep / SR
