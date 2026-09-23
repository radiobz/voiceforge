# 升级引擎：CosyVoice 2（多人有声剧拟真级）

灵声 VoiceForge 的语音引擎位于 `backend/app/engines/`，接口极简（`synthesize(text, out_path, voice, rate, pitch, volume)`）。
接入 CosyVoice 2 后，可在「剧本模式」中获得**端到端拟真演绎**：指令式情绪（"用低沉悲伤的语气说"）、
零样本音色克隆（3~10 秒参考音频即可得到某个角色的声音）、模型自然产生的吞字 / 气声 / 停顿。

## 硬件要求（重要）

CosyVoice 2 是 LLM + 流式解码架构，**需要 GPU 才能实际使用**：

| 配置 | 可用性 |
| --- | --- |
| NVIDIA GPU ≥ 8GB 显存（如 RTX 3060 及以上） | 推荐，实时性可用 |
| 纯 CPU / 低内存机器 | 不推荐（单句合成耗时数分钟） |
| 云端 GPU（AutoDL / 火山引擎 GPU 实例等） | 适合，按需付费 |

本仓库默认 Edge-TTS 引擎不依赖 GPU；升级 CosyVoice 只影响新增引擎，不影响现有功能。

## 安装（在 GPU 机器上）

```bash
# 1. 安装 CosyVoice 2（官方仓库 FunAudioLLM/CosyVoice）
git clone https://github.com/FunAudioLLM/CosyVoice.git
cd CosyVoice
# 建议使用官方 docker 镜像（已装好依赖与权重下载脚本）
docker build -t cosyvoice2 .   # 或使用预构建镜像

# 2. 下载模型权重（约 2-4GB，需访问 HuggingFace 或使用镜像站）
python3 -m cosyvoice.cli.download --model iic/CosyVoice2-0.5B

# 3. 准备角色参考音频（每个角色 3~10 秒干净人声 wav/mp3）
mkdir -p /data/refs
# 旁白.wav  林小雨.wav  陈默.wav ...
```

## 在本仓库启用

```bash
# 方式 A：直接跑 CosyVoice 服务（推荐，独立进程）
# 见下方 engine 适配层；CosyVoice 侧以 HTTP 服务暴露 /inference_zero_shot

# 方式 B：docker-compose 追加 GPU 服务
docker compose -f docker-compose.gpu.yml up -d
```

### 适配层实现（替换 engines 默认实现）

`backend/app/engines/cosyvoice.py` 示例（接口与 edge.py 一致，调用 CosyVoice 推理服务）：

```python
import requests, json

COSY_SERVICE = "http://127.0.0.1:8001/inference_zero_shot"

async def synthesize(text: str, out_path: str, voice: str,
                     rate: float = 1.0, pitch: float = 0.0, volume: float = 1.0) -> None:
    # voice 此时是角色 ID（如 "林小雨"），对应 refs/林小雨.wav
    resp = requests.post(COSY_SERVICE, json={
        "tts_text": text,
        "prompt_speech_16k": f"/data/refs/{voice}.wav",
        "stream": False,
    }, timeout=600)
    with open(out_path, "wb") as f:
        f.write(resp.content)
```

### 剧本模式的情绪映射

CosyVoice 2 支持指令式情绪（`instruct2`），可在逐句合成时把情绪标签转为自然语言指令，
例如：`joy -> "用开心的语气说"`、`sad -> "用低沉悲伤的语气说"`、`angry -> "用愤怒激动的语气说"`。
在 `tasks.py` 的 `_synth_piece` 中按引擎类型选择传递韵律参数或指令文本即可，无需改动剧本解析与拼接流水线。

## 对接清单（Done Checklist）

- [ ] GPU 机器 + CosyVoice 2 镜像可运行官方 demo
- [ ] 为每个剧本角色录制 / 收集 3~10 秒参考音频
- [ ] 在 engines 下新增 cosyvoice.py 并注册到 `engines/__init__.py`
- [ ] 回归：普通模式与剧本模式的拼接 / 字幕 / 下载链路不变
