# 灵声 VoiceForge

文字转语音（TTS）网页应用：输入或导入文本（txt / Word / PDF），自由选择音色与情绪，一键生成自然流畅的语音文件（MP3 / WAV），并自动附带 SRT 字幕。长文本自动分块合成，不限长度。

Text-to-Speech web app: type or import text (txt / Word / PDF), pick a voice and emotion, generate natural speech (MP3 / WAV) with optional SRT subtitles. Long text is automatically chunked — no length limit.

## 功能特性 / Features

- **多种输入方式**：手工输入、导入 `.txt` / `.docx` / `.pdf`（自动识别编码）
- **322 个在线音色**：中英日韩等多语言，支持搜索筛选
- **自定义音色（语音风格参考）**：导入音频或视频片段，自动提取人声并分析音色特征（性别 / 基频 / 语速 / 风格标签），推荐最接近的内置音色参与合成；参考片段持久保存，接入 CosyVoice2 后可直接用作零样本克隆素材
- **情绪化语音**：内置轻量情绪分类（开心 / 悲伤 / 愤怒 / 平静 / 惊喜 / 恐惧），通过语速 / 音调 / 音量韵律映射自然表达
- **剧本模式（多人有声剧）**：按 `角色名：台词` 书写即可自动识别角色与旁白，为每个角色分配不同音色（可手动指定），逐句识别情绪，输出多角色演绎的完整音频与带角色前缀的 SRT 字幕
- **不限长文本**：自动分块 + 句级切分，逐句独立识别情绪；消除库级 4096 字节随机切块与前导静音造成的"断音"
- **输出**：MP3 / WAV 语音文件 + 逐段 SRT 字幕 + 浏览器内播放与下载
- **历史记录**：最近 50 条合成记录保存在本地浏览器，可回听与重新下载

### 剧本模式示例 / Script mode example

```
旁白：夜已经深了，江边的风有点凉。
林小雨：我真的不想再等了，每次都这样！
陈默：对不起，是我的错，你想怎么罚我都行。
林小雨：那……你以后还会骗我吗？
陈默：不会了，我保证。
```

未标注的行自动归为「旁白」（使用默认叙述音色）；其余角色自动轮流分配不同的中文音色（男女声交替），也可以在界面中手动指定每个角色的音色。

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

### 部署到 Render（免费公网链接）

仓库根目录已提供 [render.yaml](render.yaml)（Docker 多阶段构建：前端打包 + Python 后端 + ffmpeg）。

1. 登录 [render.com](https://render.com)（可用 GitHub 账号注册，免费）
2. Dashboard → **New → Blueprint** → 选择本仓库 `radiobz/voiceforge`
3. Render 自动读取 render.yaml → 点 **Apply** → 等待首次构建（约 5 分钟）
4. 完成后获得 `https://voiceforge.onrender.com` 公网链接，点开即用

> 免费实例闲置约 15 分钟后休眠，首次访问需等待 30~60 秒冷启动；需要 7×24 常在线可升级付费实例。输出音频与自定义音色数据位于临时磁盘，重新部署会清空（浏览器端历史记录不受影响）。

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
| GET | `/api/voices?lang=&q=` | 音色列表（内置 + 自定义置顶） |
| POST | `/api/voices/custom` | 上传音/视频片段，提取并分析为自定义音色 |
| GET | `/api/voices/custom/{id}/audio` | 自定义音色参考音频（试听） |
| DELETE | `/api/voices/custom/{id}` | 删除自定义音色 |
| POST | `/api/files/parse` | 解析 txt / docx / pdf |
| POST | `/api/emotion/analyze` | 文本情绪分析 |
| POST | `/api/tts/synthesize` | 创建合成任务，返回 `task_id` |
| GET | `/api/tasks/{id}` | 查询任务状态 / 结果 |
| GET | `/api/tasks/{id}/stream` | SSE 进度推送 |

## 关于语音自然度 / About voice naturalness

本项目基于微软 Edge-TTS 神经语音，免费、无需密钥、离线不可用，听感为**自然真人朗读 / 播报级**——朗读连贯、无机械断句。它**不**等同于豆包 / ChatGPT 那种端到端语音大模型的对话拟真度（那种需要专有大模型）。项目在 `backend/app/engines/` 设计了引擎适配层，后续可无缝接入本地开源大模型（如 CosyVoice / ChatTTS 等）升级自然度与情绪表现力。

### 防"断音"处理（v0.2）

实测发现并修复两个造成"机器感/断音"的问题：
1. **库级随机切块**：edge-tts 库内部按 4096 字节硬切分文本（中文无空格时切在任意字符后，高频字如「的」常落在切口），每个切片还带约 150~190ms 前导静音。修复：由应用按句切分 + 修剪前导静音 + 零静音拼接，句间停顿沿用模型自身节奏。
2. **情绪韵律过冲**：语速/音调增量过大时轻声字（的/地/得）被压缩成顿挫感。修复：韵律增量改为温和档（开心 +5% 语速等），更接近自然朗读。

### 多人有声剧的边界（诚实说明）

剧本模式提供"多音色 + 逐句情绪 + 旁白/对白结构"的有声剧听感，但在 Edge-TTS 引擎下：
- 支持：多角色音色分离、情绪随台词逐句变化、自然句读停顿
- 不支持：模型级"吞字/气声/哭腔"等端到端演绎效果（需要语音大模型）
若需达到完整有声剧拟真度，请按 [docs/ENGINE_EXTENSION.md](docs/ENGINE_EXTENSION.md) 接入克隆类引擎（CosyVoice 2 / GLM-TTS / 豆包声音复刻，GPU 机器或 API，零样本音色克隆 + 指令式情绪）——接口已预留，改环境变量即可启用。

## 许可证 / License

[MIT](LICENSE)
