# 引擎扩展指南（预留适配接口）

VoiceForge 的 TTS 引擎是可插拔的：`backend/app/engines/` 定义了统一接口，
切换引擎**只需要改一个环境变量，无需改动 tasks / 前端 / API**。

## 接口契约（engines/__init__.py）

任何新引擎实现两个函数即可接入：

```python
async def list_voices(lang=None, keyword=None) -> list[dict]
async def synthesize(text, out_path, voice, rate=1.0, pitch=0.0,
                     volume=1.0, emotion=None, strength=0.0) -> None
```

| 参数 | 含义 | 谁用 |
| --- | --- | --- |
| `voice` | 内置音色 short_name 或自定义音色 id（`custom_xxx`） | 全部 |
| `rate/pitch/volume` | 韵律参数 | Edge（韵律型） |
| `emotion` | 情绪标签 joy/sad/angry/calm/surprised/fear | 指令型引擎（CosyVoice2 instruct / GLM-TTS / 豆包） |
| `strength` | 情绪强度 0~1 | 同上 |

指令型引擎把 `emotion` 映射为自然语言指令（如 "用低沉悲伤的语气说"），
韵律型引擎（Edge）忽略 `emotion`、直接用 rate/pitch/volume。

## 启用方式

```bash
# 环境变量切换（默认 edge）
VFORGE_ENGINE=cosyvoice     # 本地 GPU：CosyVoice2
VFORGE_ENGINE=glmtts        # 本地 GPU 或智谱 API
VFORGE_ENGINE=volcengine    # 火山豆包语音 API（声音复刻）
```

未选择的新引擎**不会被加载**（懒加载），所以放一个未实现的引擎文件不影响现有功能。

## 新增引擎步骤

1. 复制 `backend/app/engines/template_engine.py` → `backend/app/engines/<name>.py`
2. 实现 `synthesize()`（必需）与 `list_voices()`（可选）
3. 设 `VFORGE_ENGINE=<name>` 重启后端
4. 回归：普通模式 / 剧本模式 / 字幕 / 下载链路不变

## 与现有功能如何衔接

### 自定义音色（已就绪的克隆素材）
用户在界面导入的参考音频已持久保存在 `backend/data/refs/<id>.wav`，
克隆类引擎在 `synthesize()` 中通过 `voice_lab.registry.get(voice)` 取到
`ref_wav` → 本地文件路径，直接作为零样本克隆的 `prompt_speech`。
界面"自定义音色"功能无需任何改动即可成为克隆入口。

### 剧本模式（角色 → 克隆音色）
剧本模式已把每个角色映射到一个 voice 并逐句传入 `emotion`：
- 角色 = 参考音频（用户为每个角色录 3~10 秒）
- 情绪 = 指令（`EMOTION_INSTRUCTIONS` 模板已给出）
接入克隆引擎后，剧本模式即升级为"每个角色真实声音 + 情绪演绎"的完整有声剧。

## 候选引擎清单（选型参考）

| 引擎 | 部署 | 克隆 | 成本 | 备注 |
| --- | --- | --- | --- | --- |
| **CosyVoice2**（阿里开源） | 本地 GPU ≥8G | 零样本 3~10s | 0 元授权 | Apache 2.0，中文最强，指令情绪 |
| **GLM-TTS**（智谱开源） | 本地 GPU 4~6G 或智谱 API | 3 秒克隆 | API 约 2 元/万字符（限时） | 情绪"表演"级 + 自定义发音 |
| **豆包声音复刻**（火山 API） | 无需 GPU | 秒级复刻 | 免费 5000 字 + 10 音色，之后约 2.8 元/万字符 | 豆包对话听感，多角色演绎 |
| **GPT-SoVITS** | 本地 GPU ≥8G | 少样本 | 0 元授权 | MIT，还原度高 |
| Edge-TTS（现状） | 无 GPU | 无克隆（近似匹配） | 0 元 | 朗读级 |

> 说明：开源模型"免费"但需要 GPU 机器；托管 API 免硬件但按量计费。
> 本仓库默认 Edge-TTS 不依赖 GPU；克隆引擎按需启用，互不影响。
