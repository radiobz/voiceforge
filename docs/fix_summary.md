# 灵声 VoiceForge 后端 Bug 修复摘要

修复日期：2026-09-24
后端运行：`http://127.0.0.1:8000`（已重启，health 返回 ok）
原则：不引入新依赖、不改 API 契约、保持向后兼容。

## 修复状态总览

| FIX | 严重度 | 文件 | 状态 |
|-----|--------|------|------|
| FIX-001 | CRITICAL | voice_lab.py | ✅ 已修复 |
| FIX-002 | MEDIUM | voice_lab.py | ✅ 已修复 |
| FIX-003 | MEDIUM | voice_lab.py | ✅ 已修复 |
| FIX-004 | CRITICAL | main.py | ✅ 已修复 |
| FIX-005 | CRITICAL | main.py | ✅ 已修复 |
| FIX-006 | HIGH | main.py | ✅ 已修复 |
| FIX-007 | MEDIUM | main.py | ✅ 已修复 |
| FIX-008 | MEDIUM | main.py | ✅ 已修复 |
| FIX-009 | LOW | main.py / schemas.py | ✅ 已修复 |
| FIX-010 | CRITICAL | tasks.py | ✅ 已修复 |
| FIX-011 | HIGH | audio.py / tasks.py | ✅ 已修复 |
| FIX-012 | LOW | tasks.py | ✅ 已修复 |
| FIX-013 | CRITICAL | musicgen.py / tasks.py | ✅ 已修复 |
| FIX-014 | HIGH | musicgen.py | ✅ 已修复 |
| FIX-015 | HIGH | schemas.py | ✅ 已修复 |
| FIX-016 | HIGH | engines/__init__.py | ✅ 已修复 |
| FIX-017 | MEDIUM | engines/__init__.py | ✅ 已修复 |
| FIX-018 | MEDIUM | audio.py | ✅ 已修复 |
| FIX-019 | MEDIUM | audio.py | ✅ 已修复 |
| FIX-020 | LOW | audio.py | ✅ 已修复 |
| FIX-021 | MEDIUM | parsers/__init__.py | ✅ 已修复 |
| FIX-022 | MEDIUM | engines/edge.py | ✅ 已修复 |
| FIX-023 | LOW | emotion.py | ✅ 已修复 |
| FIX-024 | LOW | script.py | ✅ 已修复 |
| FIX-025 | HIGH | frontend/src/api.js | ✅ 已修复 |

## 各 FIX 说明

### voice_lab.py
- **FIX-001**：`CustomVoiceRegistry.add()` 改为复用 `entry.get("id")`；`create_custom()` 在 entry 中预填 `id/short_name=vid`，`wav_path` 与 `entry["id"]` 使用同一 vid，彻底消除「wav 文件名 vs registry id 不一致」。
- **FIX-002**：registry 加载改为 `with open(...) as f: json.load(f)`，关闭文件句柄。
- **FIX-003**：`_decode()` 检查 ffmpeg 返回码，失败时抛 `ValueError("音频解码失败：...")` 并附带 stderr 末尾信息，不再静默返回空数组。

### main.py
- **FIX-004**：新增 `@app.exception_handler(ValueError)` 全局处理器，统一返回 HTTP 400 + `{"detail": ...}`；删除 `upload_custom_voice` 中无意义的 `except ValueError: raise ValueError` 包裹。
- **FIX-005**：DELETE 增加 vid 白名单正则 `^custom_[0-9a-f]{8}$`，不匹配返回 400；`registry.remove()` 返回 False 时直接 `{"deleted": False}` 不删文件；删文件前用 `os.path.realpath` 校验路径位于 `REFS_DIR` 内。
- **FIX-006**：三处上传端点（custom 200MB / parse 100MB / music analyze 100MB）在 `await file.read()` 前预检 `file.size`；`file.size` 为 None（chunked）时 read 后再校验，超限返回 400。
- **FIX-007**：`custom_voice_audio()`（entry 不存在 / wav 不存在）与 `task_status()`（task 不存在）由 `return {"error":...}` 改为 `raise HTTPException(404)`。
- **FIX-008**：新增 `_background_tasks` 集合与 `_run_bg(coro)` 辅助函数（add_done_callback 自动 discard），三处 fire-and-forget 改为 `_run_bg(...)`，避免任务句柄被 GC 回收而静默取消。
- **FIX-009**：新增 `EmotionRequest` Pydantic 模型，`/api/emotion/analyze` 由 `body: dict` 改为 `body: EmotionRequest`；空 text 仍返回 calm 兜底。

### tasks.py
- **FIX-010**：新增 `_task_created` 时间字典与 `_TASK_TTL=3600`；`_evict_old_tasks()` 清理 done/failed 且超过 TTL 的任务及其 `_locks` 条目，`running/queued` 不受影响；`get_task()` 每次调用触发清理。
- **FIX-011**：`audio.make_srt` 新增 `gap` 参数（默认 0.0）；`_finalize()` 调用时传 `gap=0.0`，字幕时间轴与零静音拼接对齐，消除 0.3s 漂移。
- **FIX-012**：`run_music_adapt` 内部创建的 voice_task 用 `internal_voice_task` 标记，在 `finally` 中从 `_tasks/_locks/_task_created` 移除。

### musicgen.py
- **FIX-013**：`generate()` 用 try/finally 包裹 render_wav + to_mp3，成功后删除中间 wav；`run_music_adapt` 中 `mix_wav`、`music_trim.wav` 在 to_mp3 成功后删除。
- **FIX-014**：`mix_with_voice` 的 `out_music` 改为写「原始音乐（裁剪 + 尾部淡出）」`pure_music`，不再写被 ducking 包络压过的 `music_bus/gap`，纯音乐交付件不再带 ducking。

### schemas.py
- **FIX-015**：为 `SynthesizeRequest/MusicGenerateRequest/MusicAdaptRequest` 的数值参数加 `Field(ge=, le=)`（emotion_strength 0~1.5、rate 0.5~2、pitch ±50、volume 0~2、duration 10~2400），枚举参数加 `Literal`（emotion、mode、rhythm、balance、output_format）；`text` 仅设 `min_length=1`，不设 max 以支持长文本；新增 `EmotionRequest`。

### engines/__init__.py
- **FIX-016**：`list_voices()` 改为通过 `_engine_module()` 分发，模块实现了 `list_voices` 就用它，否则回退 edge；lang/keyword 过滤逻辑保留。
- **FIX-017**：`ENGINE_LABEL` 改为 `_LABELS.get(ENGINE, ENGINE)`，按 `VFORGE_ENGINE` 动态取值。

### audio.py
- **FIX-018**：新增 `_run_ffmpeg(cmd)` 辅助，`CalledProcessError` 时解码 stderr 末尾 500 字符并抛 `RuntimeError`；`_silence_file/concat_mp3/trim_leading_silence_mp3/to_wav` 统一改用它。
- **FIX-019**：静音缓存目录由源码目录 `os.path.dirname(__file__)` 改为 `tempfile.gettempdir()/voiceforge_silence`，避免只读源码目录写失败。
- **FIX-020**：`duration_ms()` 异常仍返回 0.0（不破坏调用方），但增加 `logger.warning` 记录。

### parsers/__init__.py
- **FIX-021**：`parse_file()` 优先 magic bytes 嗅探（`%PDF` → pdf；`PK` → 尝试 docx），再走扩展名兜底；`parse_pdf/parse_docx` 包 try/except，解析失败抛 `ValueError("文件格式无效或已损坏...")`（经全局处理器转 400）。

### engines/edge.py
- **FIX-022**：`com.save(out_path)` 用 `asyncio.wait_for(..., timeout=120)` 包裹，网络挂起不再永久卡死任务；新增 `import asyncio`。

### emotion.py
- **FIX-023**：删除死代码 `if best == "calm": strength = 0.0`（scores 无 calm 键，calm 已在上方提前返回）。

### script.py
- **FIX-024**：`is_script()` 判定阈值由「≥1 个非旁白角色」改为「≥2 个不同的非旁白角色」，避免「日期：2024」这类含中文冒号的普通文本被误判为剧本。

### frontend/src/api.js
- **FIX-025**：`taskStream()` 在 `onmessage` 中判断 `data.status` 为 `done/failed` 时调用 `es.close()`，杜绝浏览器自动重连造成的死循环；`onerror` 静默。（未改动 `frontend/dist/` 编译产物。）

## 冒烟测试结果（重启后实测）

| 用例 | 期望 | 实际 |
|------|------|------|
| POST /api/emotion/analyze `{"text":"你好"}` | 200 | ✅ 200，返回 calm |
| POST /api/music/generate `{"mode":"chill","duration":10,"mood":"calm"}` | 任务完成 | ✅ done 100%，仅落盘 mp3（中间 wav 已删，FIX-013 验证） |
| POST /api/tts/synthesize `{"text":"测试一下"}` | 任务完成 | ✅ done 100%（edge-tts 联网合成成功） |
| DELETE /api/voices/custom/invalid_vid | 400 | ✅ 400 `{"detail":"invalid vid"}`，未删任何文件 |
| POST /api/files/parse 上传 fake.pdf（实为文本） | 400 友好错误 | ✅ 400 `{"detail":"文件格式无效或已损坏（pdf 解析失败）"}` |
| GET /api/tasks/nonexistent（回归） | 404 | ✅ 404 |

uvicorn 日志 `/tmp/vforge.log` 无 traceback / error。
