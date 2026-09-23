"""灵声 VoiceForge - FastAPI 主程序"""
from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import engines, tasks, voice_lab
from .config import BASE_DIR, OUTPUT_DIR
from .parsers import parse_file
from .schemas import (EmotionResponse, EmotionSegment, FileParseResponse,
                      MusicAdaptRequest, MusicGenerateRequest,
                      SynthesizeRequest, VoiceInfo)

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
    data = await file.read()
    all_voices = await engines.list_voices()
    try:
        entry = voice_lab.create_custom(file.filename or "voice.mp3", data,
                                        name=name, voices=all_voices)
    except ValueError as e:
        raise ValueError(str(e)) from e
    return entry


@app.get("/api/voices/custom/{vid}/audio")
async def custom_voice_audio(vid: str):
    import os as _os
    entry = voice_lab.registry.get(vid)
    if not entry:
        return {"error": "not found"}
    wav = _os.path.join(voice_lab.REFS_DIR, f"{vid}.wav")
    if not _os.path.exists(wav):
        return {"error": "audio missing"}
    return FileResponse(wav, media_type="audio/wav")


@app.delete("/api/voices/custom/{vid}")
async def delete_custom_voice(vid: str):
    ok = voice_lab.registry.remove(vid)
    import os as _os
    wav = _os.path.join(voice_lab.REFS_DIR, f"{vid}.wav")
    if _os.path.exists(wav):
        _os.remove(wav)
    return {"deleted": ok}


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


@app.post("/api/music/generate")
async def music_generate(req: MusicGenerateRequest):
    """独立生成氛围音乐（chill/冥想/氛围），随机种子，最长 40 分钟。"""
    tr = tasks.create_task(req)
    asyncio.get_running_loop().create_task(tasks.run_music_generate(tr.task_id, req))
    return {"task_id": tr.task_id}


@app.post("/api/music/adapt")
async def music_adapt(req: MusicAdaptRequest):
    """自适应配乐：语音（复用任务或现合成）+ 情绪/时长匹配音乐 + 混音。"""
    tr = tasks.create_task(req)
    asyncio.get_running_loop().create_task(tasks.run_music_adapt(tr.task_id, req))
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
