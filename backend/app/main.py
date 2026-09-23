"""灵声 VoiceForge - FastAPI 主程序"""
from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import engines, tasks
from .config import BASE_DIR, OUTPUT_DIR
from .parsers import parse_file
from .schemas import (EmotionResponse, EmotionSegment, FileParseResponse,
                      SynthesizeRequest)

MAX_UPLOAD = 100 * 1024 * 1024  # 100MB

app = FastAPI(title="灵声 VoiceForge", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# 输出文件静态访问
os.makedirs(OUTPUT_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")


@app.get("/api/health")
async def health():
    return {"status": "ok", "engine": engines.ENGINE_LABEL}


@app.get("/api/voices")
async def voices(lang: str | None = None, q: str | None = None):
    return await engines.list_voices(lang=lang, keyword=q)


@app.post("/api/files/parse")
async def parse_file_api(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise ValueError("文件超过 100MB 上限")
    text = parse_file(file.filename or "input.txt", data)
    from .chunker import chunk_text
    blocks = len(chunk_text(text))
    return FileParseResponse(filename=file.filename or "", text=text,
                             chars=len(text), blocks=blocks)


@app.post("/api/emotion/analyze")
async def emotion_analyze(body: dict):
    from .chunker import chunk_text
    from .emotion import analyze, analyze_segments
    text = (body.get("text") or "").strip()
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
    asyncio.get_running_loop().create_task(tasks.run_task(tr.task_id, req))
    return {"task_id": tr.task_id}


@app.get("/api/tasks/{task_id}")
async def task_status(task_id: str):
    tr = tasks.get_task(task_id)
    if not tr:
        return {"error": "task not found"}
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
