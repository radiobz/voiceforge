# 灵声 VoiceForge

文字转语音（TTS）网页应用：输入或导入文本（txt / Word / PDF），自由选择音色与情绪，一键生成自然流畅的语音文件（MP3 / WAV），并自动附带 SRT 字幕。长文本自动分块合成，不限长度。

Text-to-Speech web app: type or import text (txt / Word / PDF), pick a voice and emotion, generate natural speech (MP3 / WAV) with optional SRT subtitles. Long text is automatically chunked — no length limit.

## 功能特性 / Features

- **多种输入方式**：手工输入、导入 `.txt` / `.docx` / `.pdf`（自动识别编码）
- **322 个在线音色**：中英日韩等多语言，支持搜索筛选
- **情绪化语音**：内置轻量情绪分类（开心 / 悲伤 / 愤怒 / 平静 / 惊喜 / 恐惧），通过语速 / 音调 / 音量韵律映射自然表达
- **不限长文本**：自动分块（每块 1000 字）+ 块间重叠 + 静音拼接，逐段独立识别情绪
- **输出**：MP3 / WAV 语音文件 + 逐段 SRT 字幕 + 浏览器内播放与下载
- **历史记录**：最近 50 条合成记录保存在本地浏览器，可回听与重新下载

## 技术栈 / Tech Stack

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3 + Vite（零 UI 框架，自绘设计系统） |
| 后端 | FastAPI + Edge-TTS（微软神经语音，免费在线） |
| 音频处理 | FFmpeg（分块拼接、WAV 转码） |
| 文档解析 | python-docx（Word）、pypdf（PDF）、charset-normalizer（编码识别） |

## 快速开始 / Quick Start

### 本地运行 / Run locally

要求：Python 3.10+、Node 18+、FFmpeg（可选，用于分块拼接与 WAV 输出）。

```bash
# 1. 后端
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2. 前端（开发模式）
cd frontend
npm install
npm run dev   # http://localhost:5173 （自动代理 /api 到 8000）

# 3. 前端（生产构建，由后端直接托管）
npm run build
# 后端将自动挂载 frontend/dist，直接访问 http://localhost:8000
```

### Docker / Docker Compose

```bash
docker compose up --build
# 访问 http://localhost:8000
```

## 项目结构 / Structure

```
voiceforge/
├── backend/            # FastAPI 后端
│   ├── app/
│   │   ├── main.py     # 路由入口（API + 前端静态托管）
│   │   ├── config.py   # 配置与情绪韵律映射
│   │   ├── chunker.py  # 长文本分块
│   │   ├── emotion.py  # 轻量情绪分类器
│   │   ├── audio.py    # FFmpeg 拼接 / 转码
│   │   ├── tasks.py    # 合成任务编排（队列+进度+SSE）
│   │   ├── parsers/    # txt / docx / pdf 解析
│   │   └── engines/    # 语音引擎适配层（Edge-TTS，预留本地模型入口）
│   └── requirements.txt
├── frontend/           # Vue 3 + Vite 前端
│   └── src/            # 组件：工作台 / 音色 / 情绪 / 输出 / 导入 / 历史 / 设置
└── outputs/            # 合成产物（按 task_id 分目录）
```

## API 一览 / API Overview

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| GET | `/api/voices?lang=&q=` | 音色列表（322 个，支持筛选） |
| POST | `/api/files/parse` | 解析 txt / docx / pdf |
| POST | `/api/emotion/analyze` | 文本情绪分析 |
| POST | `/api/tts/synthesize` | 创建合成任务，返回 `task_id` |
| GET | `/api/tasks/{id}` | 查询任务状态 / 结果 |
| GET | `/api/tasks/{id}/stream` | SSE 进度推送 |

## 关于语音自然度 / About voice naturalness

本项目基于微软 Edge-TTS 神经语音，免费、无需密钥、离线不可用，听感为**自然真人朗读 / 播报级**——朗读连贯、无机械断句。它**不**等同于豆包 / ChatGPT 那种端到端语音大模型的对话拟真度（那种需要专有大模型）。项目在 `backend/app/engines/` 设计了引擎适配层，后续可无缝接入本地开源大模型（如 CosyVoice / ChatTTS 等）升级自然度与情绪表现力。

## 许可证 / License

[MIT](LICENSE)
