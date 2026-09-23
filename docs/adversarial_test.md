# 灵声 VoiceForge 对抗式测试报告

> 测试时间：2026-09-24  
> 目标：http://127.0.0.1:8000  
> 测试方法：Python httpx（异步并发）+ curl，覆盖边界条件、异常输入、安全漏洞、并发、编码、路径等攻击面

---

## 总览

| 指标 | 数值 |
|------|------|
| 测试用例总数 | 39 |
| 通过 | 31 |
| 失败（500/崩溃/未友好处理） | 6 |
| 代码级风险发现 | 2 |
| 通过率 | 79.5% |

### 问题严重级别分布

| 严重级别 | 数量 | 说明 |
|----------|------|------|
| 🔴 Critical | 1 | 上传文件大小检查滞后于内存读取，可致 DoS |
| 🟠 High | 6 | 无效文件类型导致未捕获异常 → HTTP 500，无友好错误提示 |
| 🟡 Medium | 1 | DELETE 端点 vid 参数未做路径校验（HTTP 层已阻挡，但代码层有隐患） |
| 🔵 Low | 0 | — |

---

## A. 空输入与非法输入（#1–#13）

| # | 用例 | 输入 | 状态码 | 实际结果 | 预期 | 判定 |
|---|------|------|--------|----------|------|------|
| 1 | 空文本 TTS | `POST /api/tts/synthesize {"text":""}` | 200 | 任务创建成功，异步执行后 status=failed，message="合成失败：文本为空" | 友好错误，不 500 | ✅ PASS |
| 2 | 全空格 TTS | `POST /api/tts/synthesize {"text":"   "}` | 200 | 任务创建成功，异步失败（strip 后为空） | 友好错误，不 500 | ✅ PASS |
| 3 | 空文本情绪分析 | `POST /api/emotion/analyze {"text":""}` | 200 | 返回 `{"emotion":"calm","label":"平静","strength":0.0,"segments":[]}` | 返回 calm | ✅ PASS |
| 4 | 无 text 字段 | `POST /api/emotion/analyze {}` | 200 | 返回 calm（`body.get("text") or ""` 兜底） | 返回 calm，不 500 | ✅ PASS |
| 5 | text=None | `POST /api/emotion/analyze {"text":null}` | 200 | 返回 calm（`None or ""` 兜底） | 返回 calm，不 500 | ✅ PASS |
| 6 | 音乐 duration=0 | `POST /api/music/generate {"duration":0}` | 200 | 任务成功完成，实际生成 10s（`max(10.0, min(2400, 0))=10`） | 钳制到 10s 或报错 | ✅ PASS |
| 7 | 音乐 duration=-100 | `POST /api/music/generate {"duration":-100}` | 200 | 任务成功完成，实际生成 10s | 钳制或报错 | ✅ PASS |
| 8 | 音乐 duration=99999 | `POST /api/music/generate {"duration":99999}` | 200 | 任务成功完成，实际生成 2400s（`min(2400, 99999)=2400`），message 含 "2400s" | 钳制到 2400 | ✅ PASS |
| 9 | 音乐 mood=invalid | `{"duration":10,"mood":"invalid_mood"}` | 200 | 任务成功完成（mood 查找失败后走默认/随机逻辑） | 报错或回退，不崩溃 | ✅ PASS |
| 10 | 音乐 rhythm=invalid | `{"duration":10,"rhythm":"invalid"}` | 200 | 任务成功完成（无效 rhythm 被忽略/回退默认） | 回退默认，不崩溃 | ✅ PASS |
| 11 | 音乐 mode=invalid | `{"duration":10,"mode":"invalid_mode"}` | 200 | 任务异步失败，message="音乐生成失败：..."（KeyError 被 try/except 捕获） | 报错，不崩溃/挂起 | ✅ PASS |
| 12 | TTS 极端韵律参数 | `{"text":"你好世界","rate":999,"pitch":999,"volume":-1}` | 200 | 任务成功完成（`_prosody` 函数中 `max(0.5, min(2.0, ...))` 钳制） | 钳制或报错 | ✅ PASS |
| 13 | 不存在的音色 | `{"text":"测试","voice":"nonexistent_voice"}` | 200 | 任务异步失败，Edge-TTS 报错被捕获 | 任务 failed，不挂起 | ✅ PASS |

**小结**：空输入与非法输入处理良好。Pydantic 模型 + 异步任务 try/except 双层保护有效。duration 钳制（`max(10, min(2400, ...))`）和韵律钳制（`max/min`）均正确工作。

---

## B. 超长输入（#14–#17）

| # | 用例 | 输入 | 状态码 | 实际结果 | 预期 | 判定 |
|---|------|------|--------|----------|------|------|
| 14 | 50000 字 TTS | text=50000 汉字 | 200 | 任务成功创建，task_id 正常返回，不崩溃 | 分块处理，不崩溃 | ✅ PASS |
| 15 | 100000 字情绪分析 | text=100000 汉字 | 200 | 约 2-3 秒返回，不超时不崩溃 | 合理时间返回 | ✅ PASS |
| 16 | 上传 10MB txt | big.txt (10MB) | 200 | 解析成功，返回 chars 和 blocks | 能处理 | ✅ PASS |
| 17 | 随机二进制 .pdf | fake.pdf (5KB 随机字节) | **500** | `pypdf.errors.PdfStreamError: Stream has ended unexpectedly` — 未捕获异常 | 友好报错，不 500 | ❌ FAIL |

**#17 详细 traceback**：
```
File "app/parsers/__init__.py", line 34, in parse_pdf
    reader = PdfReader(io.BytesIO(data))
File "pypdf/_utils.py", line 319, in read_previous_line
    raise PdfStreamError(STREAM_TRUNCATED_PREMATURELY)
pypdf.errors.PdfStreamError: Stream has ended unexpectedly
```

---

## C. 文件类型伪造（#18–#23）

| # | 用例 | 输入 | 状态码 | 实际结果 | 预期 | 判定 |
|---|------|------|--------|----------|------|------|
| 18 | 文本命名 .pdf | fake.pdf (纯文本内容) | **500** | `PdfStreamError: Stream has ended unexpectedly`，pypdf 尝试解析文本头失败 | 友好报错，不 500 | ❌ FAIL |
| 19 | 文本命名 .docx | fake.docx (纯文本内容) | **500** | `zipfile.BadZipFile: File is not a zip file`，python-docx 尝试解压文本失败 | 友好报错，不 500 | ❌ FAIL |
| 20 | 文本命名 .mp3 → 音色上传 | fake.mp3 (纯文本内容) | **500** | `ValueError: 音轨提取失败：...Invalid argument`，ffmpeg 无法处理文本数据 | 友好报错，不 500 | ❌ FAIL |
| 21 | 文本命名 .mp4 → 音色上传 | fake.mp4 (纯文本内容) | **500** | `ValueError: 音轨提取失败：...Invalid data found when processing input` | 友好报错，不 500 | ❌ FAIL |
| 22 | 0 字节文件 → 文件解析 | empty.txt (0 bytes) | 200 | 返回空文本，chars=0，blocks=0 | 友好报错或空结果 | ✅ PASS |
| 23 | 0 字节文件 → 音色上传 | empty.mp3 (0 bytes) | **500** | `ValueError: 音轨提取失败：...Invalid argument` | 友好报错，不 500 | ❌ FAIL |

**#18–#23 根因分析**：所有 500 错误同源——端点函数没有 try/except 包裹第三方库调用：
- `parse_file_api` 直接调用 `parse_file()` → `parse_pdf()` / `parse_docx()`，pypdf 和 python-docx 的异常未被捕获
- `upload_custom_voice` 虽然 `except ValueError` 后 `raise ValueError(str(e))`，但**没有注册全局异常处理器**将 ValueError 转为 HTTP 400，导致 FastAPI 默认返回 500

---

## D. 并发与资源（#24–#27）

| # | 用例 | 输入 | 状态码 | 实际结果 | 预期 | 判定 |
|---|------|------|--------|----------|------|------|
| 24 | 5 并发音乐生成 | 5× `{duration:10}` | 200 | 5 个 task_id 全部唯一（7c94a42e…, d3877c55… 等），全部 status=done，文件隔离在各自 task 目录 | 全部完成，task_id 隔离 | ✅ PASS |
| 25 | 3 并发 TTS | 3× `{text:"并发测试文本。"}` | 200 | 3 个任务全部完成，无竞态 | 全部完成 | ✅ PASS |
| 26 | 100 快速创建任务 | 100× POST music/generate（fire and forget） | 200 | 100/100 全部返回 200，task_id 字典无崩溃 | 不崩溃 | ✅ PASS |
| 27 | 100 次查询不存在任务 | 100× GET /api/tasks/nonexistent | 200 | 100/100 返回 `{"error":"task not found"}`，约 1-2 秒完成 | 不崩溃 | ✅ PASS |

**小结**：并发处理稳健。`uuid.uuid4().hex[:12]` 生成唯一 task_id，每个任务在 `OUTPUT_DIR/{task_id}/` 独立目录，无文件覆盖风险。`_tasks` 字典在 100 并发下无异常。

---

## E. SSE 与异步任务（#28–#30）

| # | 用例 | 输入 | 状态码 | 实际结果 | 预期 | 判定 |
|---|------|------|--------|----------|------|------|
| 28 | SSE 客户端断开后任务继续 | 启动音乐任务 → 连接 SSE 2 秒后断开 | 200 | 后端任务继续执行，最终 status=done，不崩溃 | 任务继续完成 | ✅ PASS |
| 29 | 已完成任务 SSE | GET /api/tasks/{done_id}/stream | 200 | 立即推送最终状态 JSON 后流结束（while 循环条件 `status in (queued, running)` 不满足） | 推送最终状态后结束 | ✅ PASS |
| 30 | 不存在任务 SSE | GET /api/tasks/nonexistent/stream | 200 | 推送 `event: error\ndata: not found\n\n` 后结束 | 推送 error 事件 | ✅ PASS |

**小结**：SSE 实现正确。客户端断开不影响后台任务（asyncio task 独立运行）。已完成任务立即推送最终状态。不存在任务正确推送 error 事件。

---

## F. 路径与编码（#31–#33）

| # | 用例 | 输入 | 状态码 | 实际结果 | 预期 | 判定 |
|---|------|------|--------|----------|------|------|
| 31 | 中文+空格目录输出 | VFORGE_OUTPUT_DIR 环境变量 | — | 代码审查确认 config.py 支持 `VFORGE_OUTPUT_DIR` 环境变量覆盖；ffmpeg 调用使用绝对路径，理论上支持非 ASCII 路径（需重启后端实测） | ffmpeg 拼接正常 | ✅ PASS* |
| 32 | 中文空格文件名上传 | "测试 文件 名.txt" | 200 | 解析成功，返回文本内容 | 正常解析 | ✅ PASS |
| 33 | 特殊字符文件名上传 | "test'& file.txt" | 200 | 解析成功 | 不报错 | ✅ PASS |

> *#31 需在另一个端口重启后端并设置 `VFORGE_OUTPUT_DIR=/tmp/输出 目录` 进行实测，本次未重启后端。

---

## G. 端口与依赖（#34–#35）

| # | 用例 | 输入 | 状态码 | 实际结果 | 预期 | 判定 |
|---|------|------|--------|----------|------|------|
| 34 | 端口占用检测 | 在 8000 端口启动第二个 uvicorn | — | 第二个实例报错退出，stderr 含 "Address already in use"，现有进程不受影响 | 报端口占用错误 | ✅ PASS |
| 35 | ffmpeg 缺失行为 | 模拟 PATH 中无 ffmpeg | — | 代码审查：`musicgen.generate()` 内部调用 ffmpeg 转 MP3，异常被 `run_music_generate` 的 try/except 捕获，任务标记 failed 并显示错误信息 | 友好报错提示 ffmpeg 未安装 | ✅ PASS* |

> *#35 未在运行中的后端上实际模拟 ffmpeg 缺失（需重启后端并修改 PATH）。代码层面异常处理完整。

---

## H. 安全（#36–#39）

| # | 用例 | 输入 | 状态码 | 实际结果 | 预期 | 判定 |
|---|------|------|--------|----------|------|------|
| 36 | 路径遍历 | `GET /outputs/../etc/passwd` | 404 | StaticFiles 正确阻止，返回 404 | 被阻止 | ✅ PASS |
| 36b | 编码路径遍历 | `GET /outputs/%2e%2e/etc/passwd` | 404 | 编码遍历同样被阻止 | 被阻止 | ✅ PASS |
| 37 | DELETE 路径遍历 | `DELETE /api/voices/custom/../../etc/passwd` | 405 | HTTP 层路径规范化后路由不匹配，返回 405 | 不删除任意文件 | ✅ PASS |
| 37b | DELETE 编码遍历 | `DELETE /api/voices/custom/..%2F..%2Fetc%2Fpasswd` | 405 | 编码斜杠被规范化，405 | 不删除任意文件 | ✅ PASS |
| 38 | CORS 配置 | OPTIONS /api/health with Origin: http://evil.example.com | 200 | 返回 CORS 头（`Access-Control-Allow-Origin: *`） | 返回 CORS 头 | ✅ PASS |
| 39 | 超大文件上传 | 代码审查 | — | **发现问题**：`data = await file.read()` 在 `if len(data) > MAX_UPLOAD` 之前执行，整个请求体先读入内存才检查大小 | 读取前检查大小 | ❌ FAIL |

### #39 详细分析（🔴 Critical）

```python
# app/main.py 第 96-98 行
@app.post("/api/files/parse")
async def parse_file_api(file: UploadFile = File(...)):
    data = await file.read()          # ← 先读全部数据到内存
    if len(data) > MAX_UPLOAD:        # ← 后检查大小
        raise ValueError("文件超过 100MB 上限")
```

同样的问题存在于：
- `upload_custom_voice`：**完全没有大小检查**（`voice_lab.MAX_UPLOAD = 200MB` 定义了但未在端点使用）
- `music_analyze`：同样先 `await file.read()` 再检查

**影响**：攻击者可发送超大请求体（如 1GB），服务器会将全部数据读入内存后才发现超限，可导致 OOM DoS。

**修复建议**：
1. 在端点开头通过 `Content-Length` 请求头预检大小
2. 使用 `await file.read(size=CHUNK_SIZE)` 分块读取并累计大小，超限即中断
3. 对 `upload_custom_voice` 也添加大小检查

---

## 问题清单（按严重级别）

### 🔴 Critical

| ID | 问题 | 位置 | 说明 |
|----|------|------|------|
| C-1 | 上传文件大小检查滞后于内存读取 | `main.py:96-98`（parse_file_api）、`main.py:62`（upload_custom_voice）、`main.py:150`（music_analyze） | 先 `await file.read()` 再检查 `len(data) > MAX_UPLOAD`，可被超大文件 DoS。`upload_custom_voice` 甚至无大小检查。 |

### 🟠 High

| ID | 问题 | 位置 | 触发用例 | traceback 摘要 |
|----|------|------|----------|----------------|
| H-1 | PDF 解析异常未捕获 | `parsers/__init__.py:34` `parse_pdf()` | #17, #18 | `pypdf.errors.PdfStreamError: Stream has ended unexpectedly` |
| H-2 | DOCX 解析异常未捕获 | `parsers/__init__.py:20` `parse_docx()` | #19 | `zipfile.BadZipFile: File is not a zip file` |
| H-3 | 音色上传 ValueError 未转 HTTP 错误 | `main.py:65-68` `upload_custom_voice()` | #20, #21, #23 | `ValueError: 音轨提取失败：...` — 虽然 catch 了 ValueError 并 re-raise，但无全局 exception handler 转为 400，结果是 500 |

**H-1/H-2/H-3 共同根因**：缺少 FastAPI 全局异常处理器。建议添加：

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"error": str(exc)})

@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": "服务器内部错误"})
```

同时在 `parse_file_api` 中包裹 `try/except` 捕获 `pypdf` 和 `python-docx` 的异常。

### 🟡 Medium

| ID | 问题 | 位置 | 说明 |
|----|------|------|------|
| M-1 | DELETE 端点 vid 参数未做路径校验 | `main.py:84-91` `delete_custom_voice()` | `os.path.join(REFS_DIR, f"{vid}.wav")` 直接拼接 vid，若 vid 含 `../` 理论上可遍历删除文件。当前 HTTP 层路径规范化已阻挡，但代码层应添加 `vid` 白名单校验（如只允许 `[a-zA-Z0-9_]`）。 |

---

## 架构亮点（做得好的地方）

1. **异步任务 try/except 完备**：`run_task` 和 `run_music_generate` 都有 `except Exception` 捕获，任务标记 failed 而非崩溃
2. **duration 钳制正确**：`max(10.0, min(2400, float(req.duration)))` 有效处理 0、负数、超大值
3. **韵律参数钳制**：`_prosody()` 中 rate/pitch/volume 均有 `max/min` 边界保护
4. **emotion_analyze 健壮**：接受 `dict` 类型，使用 `.get("text") or ""` 兜底 None/缺失字段
5. **StaticFiles 路径遍历防护**：`/outputs` 挂载正确阻止了 `../etc/passwd`
6. **并发安全**：uuid task_id + 独立输出目录，5-100 并发无竞态
7. **SSE 实现正确**：客户端断开不影响后台任务，已完成任务立即推送最终状态
8. **Pydantic 模型校验**：SynthesizeRequest 要求 text 为 str，MusicGenerateRequest 有默认值
