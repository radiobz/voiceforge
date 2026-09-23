# 灵声 VoiceForge 后端静态代码审查报告

**审查范围**：`backend/app/` 下全部 16 个 Python 文件（约 2200 行）+ 前端 `api.js`
**审查日期**：2026-09-24
**审查方法**：逐文件通读 + 跨文件数据流追踪
**问题总数**：34（CRITICAL 5 / HIGH 7 / MEDIUM 12 / LOW 10）

---

## 问题汇总表

| ID | 级别 | 文件 | 简述 |
|---|---|---|---|
| BUG-001 | CRITICAL | voice_lab.py:250,218 | vid 生成两次，wav 文件名与 registry id 不一致 |
| BUG-002 | CRITICAL | main.py:84-91 | DELETE /api/voices/custom/{vid} 路径遍历任意文件删除 |
| BUG-003 | CRITICAL | tasks.py:26-27 | _tasks / _locks 字典无限增长，内存泄漏 |
| BUG-004 | CRITICAL | musicgen.py:531-533 | 中间 WAV 文件从不删除，单任务最多泄漏 ~423MB 磁盘 |
| BUG-005 | CRITICAL | main.py:68,98,152 | ValueError 未转 HTTPException，业务校验失败返回 500 |
| BUG-006 | HIGH | engines/__init__.py:62 | list_voices 永远调用 edge，忽略 VFORGE_ENGINE 切换 |
| BUG-007 | HIGH | musicgen.py:625 | mix_with_voice 的"纯音乐"输出仍带 ducking 压音包络 |
| BUG-008 | HIGH | main.py:175-189 + api.js:68 | SSE 完成后浏览器 EventSource 自动重连导致死循环 |
| BUG-009 | HIGH | main.py:124,132,140 | 后台任务在客户端断连后继续运行，无取消机制 |
| BUG-010 | HIGH | schemas.py 全文 | Pydantic 模型缺少 range / enum / 长度校验 |
| BUG-011 | HIGH | main.py:62,96,150 | file.read() 全量读入内存，无流式大小预检 |
| BUG-012 | HIGH | audio.py:103 vs tasks.py:107 | SRT 字幕假设块间 0.3s 静音，实际拼接为 0 静音，字幕漂移 |
| BUG-013 | MEDIUM | engines/__init__.py:39 | ENGINE_LABEL 硬编码为 Edge，切换引擎后 health 显示错误 |
| BUG-014 | MEDIUM | parsers/__init__.py:44 | 仅靠扩展名判断文件类型，无 magic bytes 嗅探 |
| BUG-015 | MEDIUM | 全局 subprocess.run | ffmpeg 失败时 stderr 被 capture_output 吞掉，错误信息不透传 |
| BUG-016 | MEDIUM | voice_lab.py:208 | registry json.load(open(...)) 文件句柄未关闭 |
| BUG-017 | MEDIUM | main.py:23-26 | CORS allow_origins=["*"] 全开放 |
| BUG-018 | MEDIUM | main.py:33-35 | /api/health 泄露引擎标签，信息泄露 |
| BUG-019 | MEDIUM | main.py:77,80,171 | 资源不存在时返回 200 + error body，前端无法识别失败 |
| BUG-020 | MEDIUM | audio.py:18 | 静音缓存文件写在源码目录旁，只读文件系统部署会崩溃 |
| BUG-021 | MEDIUM | edge.py:99-100 | edge_tts 网络请求无超时，断网时任务永久挂起 |
| BUG-022 | MEDIUM | main.py:124 等 | create_task(fire-and-forget) 未保存句柄，异常无人回收 |
| BUG-023 | MEDIUM | voice_lab.py:84-88 | _decode() 未检查 returncode，ffmpeg 失败静默返回空数组 |
| BUG-024 | MEDIUM | musicgen.py:486-516 | render_wav 全量 numpy 数组驻留内存，40 分钟曲目峰值内存高 |
| BUG-025 | LOW | main.py:107 | /api/emotion/analyze 接收裸 dict 而非 Pydantic 模型 |
| BUG-026 | LOW | tasks.py:320-324 | music_adapt 内部创建的 voice_task 残留在 _tasks 中不清理 |
| BUG-027 | LOW | main.py:63 | 上传自定义音色前同步调用 list_voices() 触发网络请求 |
| BUG-028 | LOW | script.py:35-41 | is_script() 对含中文冒号的普通文本误判为剧本 |
| BUG-029 | LOW | api.js:68-72 | EventSource 无 onerror 处理，断网后无提示 |
| BUG-030 | LOW | emotion.py:111-112 | best=="calm" 分支为死代码（scores 无 calm 键） |
| BUG-031 | LOW | main.py:30 | /outputs 静态目录公开可访问，无鉴权 |
| BUG-032 | LOW | audio.py:73-82 | duration_ms 静默返回 0，ffprobe 失败导致 SRT/混音时间错位 |
| BUG-033 | LOW | musicgen.py:225-238 | 鼓组事件用独立 random.Random(seed+beat_i) 而非共享 rng，行为不一致 |
| BUG-034 | LOW | voice_lab.py:246-247 | MAX_UPLOAD 校验在 read() 之后，无法阻止超大上传耗尽内存 |

---

## CRITICAL 级别问题

### BUG-001：自定义音色 vid 生成两次，wav 文件与 registry id 不一致

**文件**：`voice_lab.py` 第 250 行 + 第 218 行
**严重级别**：CRITICAL

**问题描述**：
`create_custom()` 在第 250 行生成第一个 `vid1`，并用它命名 wav 文件（第 251 行 `f"{vid}.wav"`），同时把 `ref_wav` 字段设为 `/api/voices/custom/{vid1}/audio`。但随后第 265 行调用 `registry.add(entry)`，而 `CustomVoiceRegistry.add()` 在第 218 行**又生成了一个全新的 `vid2`**，并覆盖 `entry["id"]` 和 `entry["short_name"]`。

结果：
- 磁盘上的 wav 文件：`data/refs/<vid1>.wav`
- registry 中的 id/short_name：`<vid2>`
- entry 中的 ref_wav URL：指向 `<vid1>`（已失效）

**触发条件**：每次创建自定义音色。

**影响范围**：
1. **试听/预览音色**：前端用 ref_wav URL 请求 `/api/voices/custom/<vid1>/audio`，`registry.get(vid1)` 返回 None（registry 存的是 vid2），接口返回 `{"error": "not found"}` —— 自定义音色试听完全不可用。
2. **删除音色**：`DELETE /api/voices/custom/<vid2>` 成功从 registry 删除，但代码拼接 `REFS_DIR/<vid2>.wav` 去删文件——磁盘上实际是 `<vid1>.wav`，删除失败，wav 文件永久残留磁盘。
3. **TTS 合成**：前端用 short_name=vid2 发请求，`resolve_voice(vid2)` 能在 registry 找到条目，合成功能正常——所以这个 bug 隐蔽，试听坏了但合成"看起来正常"。

**修复建议**：
在 `create_custom()` 中生成一次 vid，传给 `registry.add()` 复用，而不是让 add 重新生成：

```python
# voice_lab.py create_custom() 改为：
vid = "custom_" + uuid.uuid4().hex[:8]
wav_path = os.path.join(REFS_DIR, f"{vid}.wav")
duration = extract_audio(data, filename, wav_path)
...
entry = {
    "id": vid,
    "short_name": vid,
    "source": filename,
    ...
}
return registry.add(entry)  # add() 不再生成新 vid

# CustomVoiceRegistry.add() 改为：
def add(self, entry: dict) -> dict:
    vid = entry.get("id") or ("custom_" + uuid.uuid4().hex[:8])
    entry["id"] = vid
    entry["short_name"] = vid
    entry["created_at"] = time.time()
    self.items[vid] = entry
    self._save()
    return entry
```

---

### BUG-002：DELETE /api/voices/custom/{vid} 路径遍历导致任意文件删除

**文件**：`main.py` 第 84-91 行
**严重级别**：CRITICAL

**问题描述**：
```python
@app.delete("/api/voices/custom/{vid}")
async def delete_custom_voice(vid: str):
    ok = voice_lab.registry.remove(vid)
    import os as _os
    wav = _os.path.join(voice_lab.REFS_DIR, f"{vid}.wav")
    if _os.path.exists(wav):
        _os.remove(wav)
    return {"deleted": ok}
```

关键缺陷：即使 `registry.remove(vid)` 返回 `False`（vid 不在 registry 中），代码**仍然继续执行文件删除**。攻击者传入含 `../` 的 vid 即可穿越目录：

```
DELETE /api/voices/custom/..%2F..%2F..%2Ftmp%2Fevil
```
→ `os.path.join(REFS_DIR, "../../tmp/evil.wav")` → 删除 `/tmp/evil.wav`
→ 同理可删除系统中任意 `.wav` 文件（如其他用户上传的音频、Python 包内资源等）。

**触发条件**：任何能访问该 API 的客户端发送构造过的 vid。

**修复建议**：
1. registry.remove 返回 False 时直接返回，不执行文件删除；
2. 对 vid 做白名单校验（只允许 `custom_[0-9a-f]{8}`）；
3. 用 `os.path.realpath` 校验最终路径必须在 REFS_DIR 内。

```python
import re
_VID_RE = re.compile(r"^custom_[0-9a-f]{8}$")

@app.delete("/api/voices/custom/{vid}")
async def delete_custom_voice(vid: str):
    if not _VID_RE.match(vid):
        return {"deleted": False, "error": "invalid vid"}
    ok = voice_lab.registry.remove(vid)
    if not ok:
        return {"deleted": False}
    wav = os.path.join(voice_lab.REFS_DIR, f"{vid}.wav")
    if os.path.exists(wav):
        os.remove(wav)
    return {"deleted": True}
```

---

### BUG-003：_tasks / _locks 字典无限增长（内存泄漏）

**文件**：`tasks.py` 第 26-27 行
**严重级别**：CRITICAL

**问题描述**：
```python
_tasks: dict[str, TaskResult] = {}
_locks: dict[str, asyncio.Lock] = {}
```

每个 TTS / 音乐生成 / 配乐请求都通过 `create_task()` 往 `_tasks` 插入一条 TaskResult（含 segments 列表、audio_url 等），但**代码中没有任何地方删除条目**。长期运行的服务会：
- 每个合成任务累积一个 TaskResult 对象（含 N 个 SegmentResult）
- `_locks` 同样无限增长，每个 Lock 对象约几百字节
- 内存随请求数线性增长，最终 OOM

**触发条件**：服务长期运行 + 持续接收合成请求。

**修复建议**：
1. 增加任务 TTL 清理机制：在 `get_task()` 或后台定时任务中，清理超过 1 小时的 done/failed 任务；
2. 同时清理对应的输出目录（可选）和 _locks 条目；
3. 示例：

```python
_TASK_TTL = 3600  # 1 小时

def _evict_old_tasks():
    now = time.time()
    stale = [tid for tid, tr in _tasks.items()
             if tr.status in ("done", "failed") and now - getattr(tr, "_created_at", now) > _TASK_TTL]
    for tid in stale:
        _tasks.pop(tid, None)
        _locks.pop(tid, None)
```

在 `create_task` 中记录 `_created_at`，在 `get_task` 或 SSE 循环中周期性调用 `_evict_old_tasks()`。

---

### BUG-004：音乐生成中间 WAV 文件从不删除（磁盘泄漏）

**文件**：`musicgen.py` 第 531-533 行；`tasks.py` 第 343-344 行
**严重级别**：CRITICAL

**问题描述**：
`musicgen.generate()` 流程：
```python
wav = out_mp3.rsplit(".", 1)[0] + ".wav"   # 中间 WAV
render_wav(plan, wav)                       # 写出完整 WAV
to_mp3(wav, out_mp3)                        # 转 MP3
# wav 文件从未 os.remove！
```

一段 40 分钟（2400s）的立体声 16-bit 44.1kHz WAV 文件大小约：
`2400 * 44100 * 2ch * 2bytes ≈ 423 MB`

在 `run_music_adapt` 中更严重：同时产生 `voiceforge_<id>_music.wav`、`voiceforge_<id>_mix.wav` 两个大 WAV，加上 `music_trim.wav`，每个 adapt 任务可能泄漏近 1GB 临时文件。

**触发条件**：每次音乐生成或配乐任务。

**修复建议**：在 `generate()` 和 `mix_with_voice()` 的 `to_mp3()` 成功后删除中间 WAV：

```python
def generate(...):
    plan = generate_plan(...)
    wav = out_mp3.rsplit(".", 1)[0] + ".wav"
    try:
        render_wav(plan, wav)
        to_mp3(wav, out_mp3)
    finally:
        if os.path.exists(wav):
            os.remove(wav)
    ...
```

同样在 `tasks.py` 的 `run_music_adapt` 中，`music_trim.wav` 和 `mix_wav` 在 `to_mp3` 后应删除。

---

### BUG-005：ValueError 未转 HTTPException，业务校验失败返回 500

**文件**：`main.py` 第 68、98、152 行；`voice_lab.py` 多处
**严重级别**：CRITICAL

**问题描述**：
FastAPI 默认不把 `ValueError` 映射为 400。代码中大量地方直接 `raise ValueError("...")`：
- `main.py:68`：`raise ValueError(str(e)) from e`（自定义音色校验失败）
- `main.py:98`：`raise ValueError("文件超过 100MB 上限")`
- `main.py:152`：`raise ValueError("文件超过 100MB 上限")`
- `voice_lab.py:247,249,255`：各类校验失败

这些都会被 FastAPI 捕获为未处理异常，返回 **500 Internal Server Error**，而不是语义正确的 **400 Bad Request**。前端 `api.js` 的 `j()` 函数会把 500 当作普通错误抛出，但状态码不对，且错误响应体不是 `{"detail": "..."}` 格式。

更荒谬的是 `main.py:67-68`：
```python
except ValueError as e:
    raise ValueError(str(e)) from e
```
这只是原样重新抛出，毫无作用。

**修复建议**：
1. 统一引入 `from fastapi import HTTPException`，把所有业务校验失败改为 `raise HTTPException(status_code=400, detail="...")`；
2. 或在 FastAPI 应用层注册一个全局异常处理器，把 ValueError 转为 400：

```python
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(ValueError)
async def value_error_handler(request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})
```

---

## HIGH 级别问题

### BUG-006：engines.list_voices() 永远调用 edge，忽略 VFORGE_ENGINE

**文件**：`engines/__init__.py` 第 61-69 行
**严重级别**：HIGH

**问题描述**：
```python
async def list_voices(lang=None, keyword=None):
    voices = await edge.list_voices()   # ← 硬编码 edge
    ...
```

即使环境变量 `VFORGE_ENGINE=cosyvoice` 或 `glmtts`，`list_voices()` 仍然返回 Edge-TTS 的音色列表，而不是当前引擎的音色。这意味着：
- 切换到 CosyVoice2 后，前端音色选择器展示的还是 Edge 音色；
- `voice_lab.match_edge_voices()` 用的也是 Edge 音色池，匹配结果对 CosyVoice 无意义；
- `tasks._run_script()` 中角色音色自动分配从 `zh_pool` 取的也是 Edge 音色。

对比 `synthesize()` 函数（第 78 行）正确使用了 `_engine_module()` 分发，但 `list_voices()` 没有。

**修复建议**：
```python
async def list_voices(lang=None, keyword=None):
    mod = _engine_module()
    if hasattr(mod, "list_voices"):
        voices = await mod.list_voices(lang=lang, keyword=keyword)
    else:
        voices = await edge.list_voices()
    # 再做 lang/keyword 过滤...
```

---

### BUG-007：mix_with_voice 的"纯音乐"输出仍带 ducking 压音包络

**文件**：`musicgen.py` 第 616、625 行
**严重级别**：HIGH

**问题描述**：
用户明确要求检查此问题。追踪数据流：

```python
# 第 616 行：music_bus 已经乘了 ducking 包络 * gap
music_bus = music * (env[:, None] * bcfg["gap"])

# 语音段内：env = level = duck/gap → music_bus = music * duck
# 语音段外：env = 1.0           → music_bus = music * gap

# 第 625 行：除以 gap 后写入"纯音乐"
write_audio(music_bus * (1.0 / max(bcfg["gap"], 1e-9)), out_music)
```

除以 gap 后：
- 语音段内：`music * duck / gap = music * (duck/gap)` = **仍然被压低到 duck/gap 比例**（如 auto 档 0.34/0.48 ≈ 0.71，即音量压到 71%）
- 语音段外：`music * gap / gap = music`（恢复正常）

注释写的是"纯配乐（未压）"，但实际输出的音乐文件在人声说话段仍然是被压低的。这不是"纯音乐"，而是"带侧链压缩效果的音乐"。用户拿到 `music_url` 期望得到完整响度的配乐母带，实际得到的是被人声节奏牵着走的闪避版本。

**修复建议**：
`out_music` 应该写未经过 ducking 包络的原始音乐（仅裁剪到人声时长 + 尾部淡出）：

```python
# 替换第 625 行：
pure_music = music[:keep].copy()
if keep > fade:
    pure_music[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None]
write_audio(pure_music, out_music)
```

---

### BUG-008：SSE 完成后浏览器 EventSource 自动重连导致死循环

**文件**：`main.py` 第 175-189 行 + `api.js` 第 68-72 行
**严重级别**：HIGH

**问题描述**：
SSE 生成器在任务结束（status=done/failed）后，yield 最后一条数据然后函数返回，`StreamingResponse` 关闭连接。但浏览器的 `EventSource` 标准行为是：**连接断开后自动重连**（默认 3 秒后）。

重连后，`gen()` 再次被调用，此时 `tr.status` 已经是 done/failed，while 循环不进入，直接 yield 一次最终状态然后返回——服务器又关闭连接——浏览器又重连……形成**无限重连循环**，每 3 秒一次请求，直到页面关闭。

前端 `api.js` 的 `taskStream` 没有在收到 done/failed 后调用 `es.close()`：

```javascript
taskStream(id, onData) {
    const es = new EventSource(`${BASE}/api/tasks/${id}/stream`)
    es.onmessage = e => onData(JSON.parse(e.data))
    return es   // 调用方需自己 close，但 onData 里没有 close 逻辑
}
```

**修复建议**（二选一）：
1. **前端修复**：在 `onData` 回调中判断 status，done/failed 时关闭：
```javascript
taskStream(id, onData) {
    const es = new EventSource(`${BASE}/api/tasks/${id}/stream`)
    es.onmessage = e => {
        const data = JSON.parse(e.data)
        onData(data)
        if (data.status === 'done' || data.status === 'failed') {
            es.close()
        }
    }
    return es
}
```
2. **后端修复**：任务结束后发送一个自定义事件名 `event: end` 并关闭，浏览器收到非 `message` 事件不会自动重连（实际上 SSE 规范中连接关闭仍会重连，所以前端 close 是必须的）。

---

### BUG-009：后台任务在客户端断连后继续运行，无取消机制

**文件**：`main.py` 第 124、132、140 行
**严重级别**：HIGH

**问题描述**：
```python
@app.post("/api/tts/synthesize")
async def synthesize(req: SynthesizeRequest):
    tr = tasks.create_task(req)
    asyncio.get_running_loop().create_task(tasks.run_task(tr.task_id, req))
    return {"task_id": tr.task_id}
```

任务通过 `create_task()` 丢到后台后，HTTP 响应立即返回。如果用户随后关闭浏览器/刷新页面，或者任务查询接口不再被调用，后台协程**继续完整执行**——包括所有 ffmpeg 子进程、Edge-TTS 网络请求、numpy 渲染。没有任何机制检测客户端是否还关心这个任务。

对于音乐生成（最长 40 分钟渲染 + MP3 编码），用户放弃页面后服务器仍在消耗 CPU 和内存渲染完整曲目。

**修复建议**：
1. 在任务对象上记录最后活跃时间，配合 BUG-003 的 TTL 清理；
2. SSE 生成器中检测 `await request.is_disconnected()`，断连时设置取消标志；
3. 长期方案：引入任务队列（如 ARQ/Celery），支持取消和 worker 级资源回收。

---

### BUG-010：Pydantic 模型缺少参数范围/枚举校验

**文件**：`schemas.py` 全文
**严重级别**：HIGH

**问题描述**：
所有数值参数都没有 `Field(ge=, le=)` 约束，枚举参数没有 `Literal` 约束：

| 字段 | 注释声称范围 | 实际校验 |
|---|---|---|
| `rate` | 0.5-2.0 | 无 |
| `pitch` | -50~+50 | 无 |
| `volume` | 0.0-2.0 | 无 |
| `emotion_strength` | 0.1-1.5 | 无 |
| `duration` | 10-2400 | 无（仅在 tasks 层 clamp） |
| `emotion` | 6 种枚举 | 无（任意字符串都接受） |
| `mode` | chill/meditation/ambient/lofi | 无 |
| `mood` | 6 种情绪 | 无 |
| `balance` | loud/auto/low | 无 |
| `output_format` | mp3/wav | 无 |
| `text` | 无长度上限 | 无（可传 10MB 文本） |

虽然 `tasks._prosody()` 对 rate/pitch/volume 做了 clamp，但这是事后补救。恶意/误操作请求（如 `rate=999`、`duration=-1`、`emotion="hacker"`）会直接穿透到下游，产生难以调试的错误。

**修复建议**：使用 Pydantic v2 的 `Field` 和 `Literal`：

```python
from pydantic import BaseModel, Field
from typing import Literal

class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000)
    voice: str = "zh-CN-XiaoxiaoNeural"
    emotion: Literal["joy","sad","angry","calm","surprised","fear",None] = None
    emotion_strength: float = Field(0.6, ge=0.0, le=1.5)
    rate: float = Field(1.0, ge=0.5, le=2.0)
    pitch: float = Field(0.0, ge=-50.0, le=50.0)
    volume: float = Field(1.0, ge=0.0, le=2.0)
    output_format: Literal["mp3", "wav"] = "mp3"
    ...

class MusicGenerateRequest(BaseModel):
    mode: Literal["chill","meditation","ambient","lofi"] = "chill"
    duration: int = Field(120, ge=10, le=2400)
    mood: Literal["joy","sad","calm","angry","fear","surprised",None] = None
    balance: Literal["loud","auto","low"] = "auto"
```

---

### BUG-011：文件上传全量读入内存，无流式大小预检

**文件**：`main.py` 第 62、96、150 行
**严重级别**：HIGH

**问题描述**：
```python
async def upload_custom_voice(file: UploadFile = File(...)):
    data = await file.read()   # ← 整个文件读入内存
```

三个上传接口（自定义音色、文件解析、音乐分析）都用 `await file.read()` 一次性读全量。虽然后续代码检查了 `len(data) > MAX_UPLOAD`，但**此时内存已经吃掉了文件大小**。一个恶意客户端上传 500MB 文件，在服务端检查到超限之前，500MB 内存已经被占用。并发 10 个这样的请求直接 OOM。

**修复建议**：
1. 先读 `file.size`（Starlette UploadFile 提供）做预检；
2. 或分块读取，超过上限立即中止：

```python
async def upload_custom_voice(file: UploadFile = File(...)):
    if file.size and file.size > voice_lab.MAX_UPLOAD:
        raise HTTPException(400, detail="文件超过 200MB 上限")
    data = await file.read()
    ...
```

---

### BUG-012：SRT 字幕时间轴与实际音频不匹配（块间静音假设错误）

**文件**：`audio.py` 第 103 行 vs `tasks.py` 第 107、118 行
**严重级别**：HIGH

**问题描述**：
`audio.make_srt()` 第 103 行：
```python
cursor += dur + 0.3  # 块间加 0.3s 空隙对齐拼接静音
```

但 `tasks.py` 中实际拼接时传的是 `silence_ms=0`：
```python
audio.concat_mp3(piece_paths, seg_path, silence_ms=0)   # 第 107 行
audio.concat_mp3(seg_files, merged_mp3, silence_ms=0)   # 第 118 行
```

实际音频中块与块之间**没有任何静音间隙**，但 SRT 字幕假设每块之间有 0.3s 间隙。这意味着：
- 10 段后，字幕已经比音频提前了 3 秒；
- 100 段后漂移 30 秒；
- 用户看到字幕"已经说到第三段了"，音频还在第二段末尾。

**修复建议**：
拼接时如果 `silence_ms=0`，SRT 也不应加间隙。把 `make_srt` 的 gap 改为可参数化，并与 concat 参数对齐：

```python
def make_srt(segments, out_path, gap: float = 0.0):
    ...
    cursor += dur + gap
```

调用方传入与 `concat_mp3` 相同的 `silence_ms/1000`。

---

## MEDIUM 级别问题

### BUG-013：ENGINE_LABEL 硬编码为 Edge

**文件**：`engines/__init__.py` 第 39 行
**问题**：`ENGINE_LABEL = "Edge-TTS · 在线"` 是模块加载时的硬编码常量。虽然 `_LABELS` 字典有其他引擎的标签，但 `health()` 接口返回的 `engines.ENGINE_LABEL` 永远是 Edge。切换到 CosyVoice2 后，`/api/health` 仍然显示 "Edge-TTS · 在线"。
**修复**：在 `_engine_module()` 加载后更新 ENGINE_LABEL，或在 health() 中动态取 `_LABELS.get(ENGINE, ENGINE)`。

---

### BUG-014：文件解析仅靠扩展名判断类型

**文件**：`parsers/__init__.py` 第 43-49 行
**问题**：
```python
def parse_file(filename: str, data: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "docx": return parse_docx(data)
    if ext == "pdf": return parse_pdf(data)
    return parse_text(data)
```
用户把一个 PDF 文件改名为 `.txt`，会走 `parse_text()`，尝试用 UTF-8/GBK 解码二进制 PDF，输出一堆乱码。反之把 docx 改名为 `.pdf`，`PdfReader` 会抛异常导致 500。没有 magic bytes（文件头）嗅探。
**修复**：根据文件头魔数（`PK\x03\x04` = docx/zip，`%PDF` = pdf）做二次判断，扩展名仅作兜底。

---

### BUG-015：ffmpeg 失败时 stderr 被吞掉

**文件**：`audio.py`、`musicgen.py`、`voice_lab.py`、`audio_profile.py` 中所有 `subprocess.run(..., check=True, capture_output=True)`
**问题**：`check=True` 在非零退出码时抛 `CalledProcessError`，但 `str(e)` 只包含命令和 returncode，**不包含 stderr**。capture_output 把 stderr 捕获到了 `e.stderr`，但上层 `tasks.py` 的异常处理是 `f"合成失败：{e}"`，用户看到的是 `Command '...' returned non-zero exit status 1`，完全不知道是 ffmpeg 参数错误还是输入文件损坏。
**修复**：封装一个统一的 `_run_ffmpeg()` 函数，在 CalledProcessError 中解码 stderr 并抛出带详细信息的 RuntimeError：

```python
def _run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "ignore")[-500:]
        raise RuntimeError(f"命令失败: {' '.join(cmd[:3])}... | {err}")
```

---

### BUG-016：registry 文件句柄未关闭

**文件**：`voice_lab.py` 第 208 行
**问题**：`self.items = json.load(open(path, encoding="utf-8"))` —— `open()` 返回的文件对象没有显式关闭，依赖 CPython 垃圾回收。在长期运行进程中可能导致文件句柄泄漏。
**修复**：`with open(path, encoding="utf-8") as f: self.items = json.load(f)`。

---

### BUG-017：CORS 全开放

**文件**：`main.py` 第 23-26 行
**问题**：`allow_origins=["*"]` 配合 `allow_methods=["*"]`、`allow_headers=["*"]`。虽然没有 allow_credentials，但任何网站都能调用此 API。如果未来加上认证 cookie，会变成 CSRF 风险。
**修复**：生产环境应配置具体域名白名单，开发环境才用 `*`。

---

### BUG-018：/api/health 泄露引擎信息

**文件**：`main.py` 第 33-35 行
**问题**：返回 `{"status": "ok", "engine": "Edge-TTS · 在线"}`。虽然不严重，但暴露后端技术栈有助于攻击者定向搜索 Edge-TTS 相关漏洞。
**修复**：health 端点只返回 `{"status": "ok"}`，引擎信息放到需鉴权的 `/api/admin/info`。

---

### BUG-019：资源不存在时返回 200 + error body

**文件**：`main.py` 第 77、80、171 行
**问题**：
```python
if not entry:
    return {"error": "not found"}   # HTTP 200！
```
前端 `api.js` 的 `j()` 函数判断 `if (!r.ok)` 才抛错。HTTP 200 不会抛错，前端拿到 `{"error": "..."}` 但没有抛异常，调用方误以为成功。任务查询、音色试听都是这个模式。
**修复**：改为 `raise HTTPException(status_code=404, detail="not found")`。

---

### BUG-020：静音缓存文件写在源码目录旁

**文件**：`audio.py` 第 18 行
**问题**：`.silence_%dms.mp3` 写在 `os.path.dirname(__file__)` 即源码目录。如果应用部署在只读文件系统（如 Docker 镜像只读层、PyPI 安装），`ffmpeg` 无法写入，`concat_mp3` 第一次调用就崩溃。
**修复**：改用 `tempfile.gettempdir()` 或 `OUTPUT_DIR` 下的缓存目录。

---

### BUG-021：edge_tts 网络请求无超时

**文件**：`edge.py` 第 99-100 行
**问题**：`await com.save(out_path)` 没有超时参数。如果 Edge-TTS 端点网络抖动或挂起，这个协程会永久等待，占用任务槽和 asyncio 资源。
**修复**：用 `asyncio.wait_for(com.save(out_path), timeout=60)` 包裹，超时后抛异常。

---

### BUG-022：fire-and-forget 任务句柄未保存

**文件**：`main.py` 第 124、132、140 行
**问题**：`asyncio.get_running_loop().create_task(tasks.run_task(...))` 返回的 Task 对象没有被保存到任何集合中。Python 文档明确指出：只被事件循环弱引用的 Task 可能被 GC 回收。更实际的问题是：如果 `run_task` 在 `try/except` 之外抛异常（如 `_tasks[task_id]` KeyError），异常变成 "Task exception was never retrieved" 警告，任务静默死亡，状态永远停留在 queued。
**修复**：维护一个全局 `_background_tasks: set`，添加 done_callback 自动移除：
```python
_bg = set()
t = asyncio.create_task(coro)
_bg.add(t)
t.add_done_callback(_bg.discard)
```

---

### BUG-023：voice_lab._decode 未检查 ffmpeg 返回码

**文件**：`voice_lab.py` 第 84-88 行
**问题**：
```python
raw = subprocess.run([...], capture_output=True).stdout
return np.frombuffer(raw, dtype=np.float32)
```
没有 `check=True`。如果 ffmpeg 失败（如 wav 文件损坏），stdout 为空，`np.frombuffer` 返回空数组。后续 `_f0_series([])` 返回空列表，`f0_median=0`，性别被判为"未知"——用户上传一个损坏文件却得到一个"分析成功"的空壳自定义音色。
**修复**：检查 `r.returncode`，非零则抛异常。

---

### BUG-024：render_wav 峰值内存高

**文件**：`musicgen.py` 第 486-516 行
**问题**：虽然分块渲染（每块 60s），但每个 `_render_block` 返回的 numpy 数组约 `60 * 44100 * 2ch * 4bytes ≈ 21MB`，加上 n2 尾部 2 秒额外分配，单块峰值约 28MB。这在可接受范围，但 `_lowpass_fft` 对 n2 长度做 FFT（62s * 44100 ≈ 2.7M 点），临时数组再增 ~22MB。整体单块峰值 ~50MB，40 分钟曲目分 40 块逐块释放，不会累积。可接受但应注意。
**修复建议**：低优先级，若内存紧张可把 CHUNK 从 60 降到 30。

---

## LOW 级别问题

### BUG-025：/api/emotion/analyze 接收裸 dict

**文件**：`main.py` 第 107 行
**问题**：`async def emotion_analyze(body: dict)` 直接接收裸 dict，没有 Pydantic 校验。如果 body 不是 JSON 或没有 text 字段，行为靠 `body.get("text") or ""` 兜底。应定义 `EmotionRequest` 模型。

### BUG-026：music_adapt 内部 voice_task 残留

**文件**：`tasks.py` 第 320-324 行
**问题**：当 adapt 接口需要先合成语音时，创建了一个内部 task 加入 `_tasks` 字典，但这个 task 对用户不可见也不会被清理（配合 BUG-003 的内存泄漏）。

### BUG-027：上传自定义音色前同步网络调用

**文件**：`main.py` 第 63 行
**问题**：`all_voices = await engines.list_voices()` 在上传时被调用，虽然有缓存但首次请求会阻塞上传流程数秒。

### BUG-028：is_script 误判

**文件**：`script.py` 第 35-41 行
**问题**：任何包含中文冒号 `：` 的普通文本（如"日期：2024-01-01"）都会被 `is_script()` 判定为剧本模式。建议要求至少出现 2 个不同角色行才判定为剧本。

### BUG-029：EventSource 无 onerror

**文件**：`api.js` 第 68-72 行
**问题**：没有 `es.onerror` 处理。网络断开时浏览器自动重连但用户无感知，也不会在重试 N 次后放弃。

### BUG-030：emotion.py 死代码

**文件**：`emotion.py` 第 111-112 行
**问题**：`if best == "calm": strength = 0.0` 永远不会执行，因为 `scores` 字典的键来自 `_LEXICON`（不含 calm），`max()` 只可能返回 joy/sad/angry/surprised/fear 之一。

### BUG-031：/outputs 静态目录公开

**文件**：`main.py` 第 30 行
**问题**：`/outputs` 目录无鉴权，任何知道 task_id 的人都能下载合成产物。task_id 是 12 位 hex（48 bit），不算弱，但在多用户场景下应加签名 URL 或鉴权。

### BUG-032：duration_ms 静默返回 0

**文件**：`audio.py` 第 81-82 行
**问题**：ffprobe 失败时返回 0.0，导致 SRT 字幕时长为 0、混音时间轴错位，但任务仍然标记为"成功"。应至少记录警告日志。

### BUG-033：鼓组 RNG 使用独立 Random 实例

**文件**：`musicgen.py` 第 225-238 行
**问题**：鼓组事件用 `random.Random(seed + beat_i)` 而不是共享的 `plan["rng"]`。这意味着修改琶音/弹拨的随机性不会影响鼓组，鼓组的随机性也不跟随 plan 的 rng 状态。虽然确定性可复现，但语义上不一致，后续调参时容易困惑。

### BUG-034：MAX_UPLOAD 校验在 read() 之后

**文件**：`voice_lab.py` 第 246-247 行
**问题**：`create_custom()` 检查 `len(data) > MAX_UPLOAD`，但 `data` 已经在 `main.py:62` 被 `await file.read()` 完整读入内存。这个校验是事后的，无法防止内存耗尽。配合 BUG-011 修复。

---

## 跨文件数据流关键发现

### 1. voice_lab.create_custom 的 vid 不一致链（BUG-001 详解）

```
create_custom():
  vid1 = uuid() → wav 存为 refs/<vid1>.wav
  entry["ref_wav"] = "/api/voices/custom/<vid1>/audio"
  registry.add(entry):
    vid2 = uuid()          ← 新 id
    entry["id"] = vid2
    entry["short_name"] = vid2
    self.items[vid2] = entry

后果：
  GET  /api/voices/custom/<vid1>/audio → registry.get(vid1)=None → 404 试听失败
  DEL  /api/voices/custom/<vid2>       → registry 删成功，删 refs/<vid2>.wav → 文件不存在 → 残留 refs/<vid1>.wav
  TTS  用 short_name=<vid2>             → resolve_voice(vid2) 找到 closest → 正常
```

### 2. mix_with_voice 纯音乐压音链（BUG-007 详解）

```python
env = ones(keep)
for (s,e) in seg_times:
    env[i0:i1] = duck/gap        # 语音段压低

music_bus = music * (env * gap)
# 语音段: music * duck
# 段外:   music * gap

write_audio(music_bus / gap, out_music)
# 语音段: music * duck/gap = music * (duck/gap)  ← 仍被压！
# 段外:   music
```

### 3. 任务字典生命周期（BUG-003 详解）

```
create_task()     → _tasks[tid] = TaskResult()
run_task()        → 修改 tr.status / tr.segments
SSE 循环          → 读取 tr.model_dump_json()
（之后）           → 无人调用 _tasks.pop(tid)，永不释放
```

### 4. ValueError 流转链（BUG-005 详解）

```
main.py route handler
  → voice_lab.create_custom() raises ValueError
  → main.py:67 except ValueError: raise ValueError(str(e))
  → FastAPI 未注册 ValueError handler
  → 默认 ServerErrorMiddleware → 500 Internal Server Error
  → 前端 api.js: r.ok=false, msg="Internal Server Error"
```

---

## 修复优先级建议

**第一阶段（安全 + 数据正确性，本周）**：
- BUG-001（vid 不一致）
- BUG-002（路径遍历删除）
- BUG-005（ValueError→400）
- BUG-010（Pydantic 校验）
- BUG-011（上传内存）

**第二阶段（资源泄漏 + 稳定性）**：
- BUG-003（任务字典 TTL）
- BUG-004（WAV 临时文件清理）
- BUG-008（SSE 重连）
- BUG-009（任务取消）
- BUG-021（edge-tts 超时）

**第三阶段（功能正确性）**：
- BUG-006（list_voices 引擎分发）
- BUG-007（纯音乐压音）
- BUG-012（SRT 时间轴）

**第四阶段（加固）**：
- 其余 MEDIUM / LOW 项
