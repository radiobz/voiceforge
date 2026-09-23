"""灵声 VoiceForge - FastAPI 主程序"""
from __future__ import annotations

import asyncio
import os
import re

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import engines, tasks, voice_lab
from .config import BASE_DIR, OUTPUT_DIR
from .parsers import parse_file
from .schemas import (EmotionRequest, EmotionResponse, EmotionSegment,
                      FileParseResponse, MusicAdaptRequest, MusicGenerateRequest,
                      SynthesizeRequest, VoiceInfo)

MAX_UPLOAD = 100 * 1024 * 1024  # 100MB
# FIX-005：vid 白名单，防止 DELETE 路径遍历
_VID_RE = re.compile(r"^custom_[0-9a-f]{8}$")

app = FastAPI(title="灵声 VoiceForge", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# FIX-004：ValueError 统一转 400，避免 FastAPI 默认返回 500
@app.exception_handler(ValueError)
async def value_error_handler(request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# FIX-008：保存后台任务句柄，避免被 GC 回收导致任务静默取消
_background_tasks: set = set()


def _run_bg(coro):
    t = asyncio.create_task(coro)
    _background_tasks.add(t)
    t.add_done_callback(_background_tasks.discard)
    return t

# 输出文件静态访问
os.makedirs(OUTPUT_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")


@app.get("/api/health")
async def health():
    return {"status": "ok", "engine": engines.ENGINE_LABEL}


@app.get("/api/voices")
async def voices(lang: str | None = None, q: str | None = None):
    base = await engines.list_voices(lang=lang, keyword=q)
    # 自定义音色置顶
    customs = []
    for e in voice_lab.registry.all():
        customs.append(VoiceInfo(
            short_name=e["id"], display_name="自定义 · " + e["display_name"],
            locale="custom", gender=e["analysis"].get("gender", "未知"),
            tags=e["analysis"].get("tags", []),
            voice_type="custom", ref_wav=e.get("ref_wav", ""),
            analysis=e.get("analysis", {}),
            closest=[c for c in e.get("closest", [])]))
    if lang and lang != "custom" and lang.lower() != "zh-cn":
        customs = []
    if q:
        kw = q.lower()
        customs = [c for c in customs
                   if kw in c.display_name.lower() or kw in "".join(c.tags).lower()]
    return customs + base


@app.post("/api/voices/custom")
async def upload_custom_voice(file: UploadFile = File(...), name: str = Form("")):
    # FIX-006：read 前预检大小（file.size 可能为 None，chunked 传输时 read 后仍由 create_custom 二次校验）
    if file.size and file.size > voice_lab.MAX_UPLOAD:
        raise HTTPException(
            status_code=400,
            detail=f"文件超过 {voice_lab.MAX_UPLOAD // 1024 // 1024}MB 上限")
    data = await file.read()
    all_voices = await engines.list_voices()
    # FIX-004：删除无意义的 except ValueError 包裹，ValueError 由全局处理器转 400
    entry = voice_lab.create_custom(file.filename or "voice.mp3", data,
                                    name=name, voices=all_voices)
    return entry


@app.get("/api/voices/custom/{vid}/audio")
async def custom_voice_audio(vid: str):
    import os as _os
    entry = voice_lab.registry.get(vid)
    if not entry:
        # FIX-007：不存在返回 404
        raise HTTPException(status_code=404, detail="not found")
    wav = _os.path.join(voice_lab.REFS_DIR, f"{vid}.wav")
    if not _os.path.exists(wav):
        raise HTTPException(status_code=404, detail="audio missing")
    return FileResponse(wav, media_type="audio/wav")


@app.delete("/api/voices/custom/{vid}")
async def delete_custom_voice(vid: str):
    # FIX-005：vid 白名单校验，防止路径遍历
    if not _VID_RE.match(vid):
        raise HTTPException(status_code=400, detail="invalid vid")
    ok = voice_lab.registry.remove(vid)
    if not ok:
        # registry 未命中则不删文件
        return {"deleted": False}
    import os as _os
    wav = _os.path.realpath(_os.path.join(voice_lab.REFS_DIR, f"{vid}.wav"))
    refs_root = _os.path.realpath(voice_lab.REFS_DIR)
    # 二次校验：wav 必须位于 REFS_DIR 内
    if (wav == refs_root or wav.startswith(refs_root + _os.sep)) and _os.path.exists(wav):
        _os.remove(wav)
    return {"deleted": True}


@app.post("/api/files/parse")
async def parse_file_api(file: UploadFile = File(...)):
    # FIX-006：read 前预检大小
    if file.size and file.size > MAX_UPLOAD:
        raise HTTPException(status_code=400,
                            detail=f"文件超过 {MAX_UPLOAD // 1024 // 1024}MB 上限")
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=400,
                            detail=f"文件超过 {MAX_UPLOAD // 1024 // 1024}MB 上限")
    text = parse_file(file.filename or "input.txt", data)
    from .chunker import chunk_text
    blocks = len(chunk_text(text))
    return FileParseResponse(filename=file.filename or "", text=text,
                             chars=len(text), blocks=blocks)


@app.post("/api/emotion/analyze")
async def emotion_analyze(body: EmotionRequest):
    # FIX-009：使用 Pydantic 模型 EmotionRequest 替代裸 dict
    from .chunker import chunk_text
    from .emotion import analyze, analyze_segments
    text = (body.text or "").strip()
    if not text:
        return EmotionResponse(emotion="calm", label="平静", strength=0.0, segments=[])
    emo, st = analyze(text)
    from .config import EMOTION_LABELS
    segs = analyze_segments(chunk_text(text))
    return EmotionResponse(
        emotion=emo, label=EMOTION_LABELS.get(emo, emo), strength=st,
        segments=[EmotionSegment(**s) for s in segs])


@app.post("/api/tts/synthesize")
async def synthesize(req: SynthesizeRequest):
    tr = tasks.create_task(req)
    # FIX-008：保存任务句柄
    _run_bg(tasks.run_task(tr.task_id, req))
    return {"task_id": tr.task_id}


@app.post("/api/music/generate")
async def music_generate(req: MusicGenerateRequest):
    """独立生成氛围音乐（chill/冥想/氛围），随机种子，最长 40 分钟。"""
    tr = tasks.create_task(req)
    _run_bg(tasks.run_music_generate(tr.task_id, req))
    return {"task_id": tr.task_id}


@app.post("/api/music/adapt")
async def music_adapt(req: MusicAdaptRequest):
    """自适应配乐：语音（复用任务或现合成）+ 情绪/时长匹配音乐 + 混音。"""
    tr = tasks.create_task(req)
    _run_bg(tasks.run_music_adapt(tr.task_id, req))
    return {"task_id": tr.task_id}


@app.post("/api/music/analyze")
async def music_analyze(file: UploadFile = File(...)):
    """分析音频/视频的音乐风格特征（BPM/调式/亮度/节奏/黑胶感），
    返回 profile + 可直接用于 /api/music/generate 的生成参数。"""
    from . import audio_profile
    import tempfile as _tmp
    # FIX-006：read 前预检大小
    if file.size and file.size > MAX_UPLOAD:
        raise HTTPException(status_code=400,
                            detail=f"文件超过 {MAX_UPLOAD // 1024 // 1024}MB 上限")
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=400,
                            detail=f"文件超过 {MAX_UPLOAD // 1024 // 1024}MB 上限")
    fd, tmp = _tmp.mkstemp(suffix=".media")
    import os as _os
    _os.close(fd)
    with open(tmp, "wb") as fh:
        fh.write(data)
    try:
        prof = audio_profile.extract(tmp)
    finally:
        if _os.path.exists(tmp):
            _os.remove(tmp)
    params = audio_profile.to_params(prof)
    return {"profile": prof, "params": params}


@app.get("/api/tasks/{task_id}")
async def task_status(task_id: str):
    tr = tasks.get_task(task_id)
    if not tr:
        # FIX-007：不存在返回 404
        raise HTTPException(status_code=404, detail="task not found")
    return tr


@app.get("/api/tasks/{task_id}/stream")
async def task_stream(task_id: str):
    """SSE 进度推送"""
    async def gen():
        tr = tasks.get_task(task_id)
        if not tr:
            yield "event: error\ndata: not found\n\n"
            return
        while tr.status in ("queued", "running"):
            yield f"data: {tr.model_dump_json()}\n\n"
            await asyncio.sleep(0.8)
        yield f"data: {tr.model_dump_json()}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# 前端静态资源（构建产物存在时挂载）
_frontend_dist = os.path.join(BASE_DIR, "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
