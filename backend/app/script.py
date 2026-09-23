"""灵声 VoiceForge - 剧本模式解析

把「角色：台词」形式的文本解析为带角色的台词行列表，
支持两种输入形态：
  1. 角色行：  `角色名：台词内容`（或使用英文冒号 `角色名: 台词`）
  2. 无前缀行：归为「旁白」（旁白统一使用默认叙述音色）

示例：
    旁白：夜已经深了，她独自站在窗前。
    林小雨：我真的不想再等了。
    陈默：那你想怎么办？
"""
from __future__ import annotations

import re

ROLE_LINE = re.compile(r"^([^\s：:]{1,16})[：:]\s*(.+)$")


def parse_script(text: str) -> list[dict]:
    """返回 [{role, text}] 列表，保持原始行顺序。"""
    lines: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = ROLE_LINE.match(line)
        if m and len(m.group(1)) < 10 and m.group(2).strip():
            lines.append({"role": m.group(1).strip(), "text": m.group(2).strip()})
        else:
            lines.append({"role": "旁白", "text": line})
    return lines


def is_script(text: str) -> bool:
    """判断文本是否为剧本格式：至少出现 2 个不同的非旁白角色行。

    FIX-024：原先只要 1 个角色行就判定为剧本，导致含中文冒号的普通文本
    （如「日期：2024」）被误判。要求 >=2 个不同角色才认定为剧本。
    """
    try:
        roles = {ln["role"] for ln in parse_script(text) if ln["role"] != "旁白"}
    except Exception:
        return False
    return len(roles) >= 2


def auto_role_voices(roles: list[str], narration_voice: str,
                     pick_voices: list[str]) -> dict[str, str]:
    """自动为角色分配音色：旁白用默认叙述音色，其余角色轮换不同的中文音色。

    pick_voices 来自音色列表（zh-CN 优先，男女交替），保证角色间音色明显不同。
    用户显式指定的 role_map 优先（由调用方合并）。
    """
    assigned: dict[str, str] = {}
    pool = [v for v in pick_voices if v != narration_voice]
    if not pool:
        pool = pick_voices or [narration_voice]
    idx = 0
    for role in roles:
        if role == "旁白":
            assigned[role] = narration_voice
        else:
            assigned[role] = pool[idx % len(pool)]
            idx += 1
    return assigned
