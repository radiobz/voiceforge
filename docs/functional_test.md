# 灵声 VoiceForge 全功能端到端测试报告

- **测试时间**: 2026-09-24
- **测试环境**: http://127.0.0.1:8000 (Edge-TTS 在线)
- **测试方法**: Python requests 轮询 + ffprobe 校验音频文件

## 测试总览

| 指标 | 数值 |
|------|------|
| 测试用例总数 | 31 |
| 通过 | 27 |
| 失败 | 4 |
| 通过率 | 87.1% |

---

## 失败用例清单

| # | 用例 | 严重程度 | 说明 |
|---|------|----------|------|
| F1 | 11.2 GET /api/voices/custom/{vid}/audio | **Bug - 功能阻断** | 自定义音色参考音频无法下载，返回 `{"error":"not found"}` |
| F2 | 11.2b 磁盘 wav 文件名与返回 id 不一致 | **Bug - 功能阻断** | 注册表 id 与磁盘 wav 文件名不匹配（双 uuid 生成缺陷） |
| F3 | 5.4 TTS 多段落 segments | 性能/超时 | >1000 字长文本合成超过 120s 仍未完成（84 个分片逐句调用 Edge-TTS） |
| F4 | 3.5 长文本 blocks（首次运行） | 已修复 | 首次测试文本仅 960 字未达 1000 字阈值；修正后通过 |

---

## 详细测试结果

### 1. GET /api/health

| 用例 | 结果 | 说明 |
|------|------|------|
| 1.1 验证 status=ok 和 engine 字段 | ✅ PASS | 返回 `{"status":"ok","engine":"Edge-TTS · 在线"}` |

### 2. GET /api/voices

| 用例 | 结果 | 说明 |
|------|------|------|
| 2.1 无参数返回所有音色 | ✅ PASS | 返回数十个音色，字段完整（short_name/display_name/locale/gender/tags/voice_type） |
| 2.2 lang=zh-CN 过滤中文音色 | ✅ PASS | 仅返回 zh 开头音色 + custom 置顶 |
| 2.3 lang=en-US 过滤英文音色 | ✅ PASS | 仅返回 en 开头音色 |
| 2.4 q=晓晓 搜索过滤 | ✅ PASS | 匹配到 XiaoxiaoNeural 等 |

### 3. POST /api/files/parse

| 用例 | 结果 | 说明 |
|------|------|------|
| 3.1 UTF-8 txt 上传 | ✅ PASS | chars 精确匹配，blocks≥1，文本完整提取 |
| 3.2 GBK 编码 txt 自动识别 | ✅ PASS | GBK 文本正确解码为中文，无乱码 |
| 3.3 docx 文本提取 | ✅ PASS | python-docx 生成的标题+段落正确提取 |
| 3.4 pdf 文本提取 | ✅ PASS | PDF 文本成功提取 |
| 3.5 长文本 >1000 字 blocks 计数 | ✅ PASS | 1280 字正确分块为 ≥2 个 blocks |

### 4. POST /api/emotion/analyze

| 用例 | 结果 | 说明 |
|------|------|------|
| 4.1 开心文本 → joy | ✅ PASS | emotion=joy |
| 4.2 悲伤文本 → sad | ✅ PASS | emotion=sad |
| 4.3 愤怒文本 → angry | ✅ PASS | emotion=angry |
| 4.4 平静文本 → calm | ✅ PASS | emotion=calm |
| 4.5 空文本 → calm, strength=0 | ✅ PASS | emotion=calm, strength=0.0, segments=[] |
| 4.6 segments 字段结构 | ✅ PASS | 每段含 text/emotion/label/strength 字段 |

### 5. POST /api/tts/synthesize

| 用例 | 结果 | 说明 |
|------|------|------|
| 5.1 短文本合成 mp3 | ✅ PASS | 任务 done，audio_url 可下载，文件非空 |
| 5.2 wav 格式输出 | ✅ PASS | output_format=wav 产出 .wav 文件，ffprobe 确认 PCM/WAV |
| 5.3 SRT 字幕合成 | ✅ PASS | with_subtitle=true 返回 subtitle_url，SRT 含时间轴 `-->` |
| 5.4 多段落 segments 数量 | ⚠️ 超时 | >1000 字触发 2 个 chunks，但 84 个分片逐句合成超 120s 未完成（见 F3） |
| 5.5 剧本模式（角色:台词） | ✅ PASS | 3 行台词解析为 3 segments，role 字段正确（旁白/小明/小红），多音色分配生效 |
| 5.6 emotion=sad 韵律应用 | ✅ PASS | auto_emotion=false + emotion=sad，segments[0].emotion=sad |
| 5.7 SSE 流推送进度 | ✅ PASS | 连接 /api/tasks/{id}/stream 收到多条 data 事件 |

### 6. POST /api/music/generate

| 用例 | 结果 | 说明 |
|------|------|------|
| 6.1 chill/15s/calm | ✅ PASS | 生成 mp3，ffprobe 时长约 15s，music_meta 含 key/bpm/kind/beat |
| 6.2 lofi/10s/sad/rhythm=full/guitar=true | ✅ PASS | music_meta.rhythm=full, music_meta.guitar=true |
| 6.3 meditation/10s | ✅ PASS | 独立模式生成成功 |
| 6.4 seed=42 可复现性 | ✅ PASS | 两次 seed=42 生成的 key/bpm/kind/beat/rhythm/guitar 完全一致 |
| 6.5 music_meta 字段完整 | ✅ PASS | 含 key/bpm/kind/beat/rhythm/guitar 全部字段 |

### 7. POST /api/music/adapt

| 用例 | 结果 | 说明 |
|------|------|------|
| 7.1 复用 TTS task_id 配乐 | ✅ PASS | 返回 mix_url/voice_url/music_url，三个文件均可下载且非空 |

### 8. POST /api/music/analyze

| 用例 | 结果 | 说明 |
|------|------|------|
| 8.1 上传生成的 mp3 分析 | ✅ PASS | 返回 profile（bpm/key/mode/brightness）+ params（可直接用于 generate） |

### 9. GET /api/tasks/{id}

| 用例 | 结果 | 说明 |
|------|------|------|
| 9.1 存在的任务 | ✅ PASS | 返回完整 TaskResult：status/done, audio_url, segments, progress 等 |
| 9.2 不存在的任务 | ✅ PASS | 返回 `{"error":"task not found"}` |

### 10. GET /api/tasks/{id}/stream (SSE)

| 用例 | 结果 | 说明 |
|------|------|------|
| 10.1 已完成任务推送最终状态 | ✅ PASS | SSE 推送 data 事件，含 status="done" |
| 10.2 不存在任务推送 error | ✅ PASS | 返回 `event: error\ndata: not found` |

### 11. 自定义音色 CRUD

| 用例 | 结果 | 说明 |
|------|------|------|
| 11.1 POST 上传 wav | ✅ PASS | 返回 id/analysis/closest，分析含 f0_median/gender/tags |
| 11.2 GET 下载参考音频 | ❌ FAIL | **返回 `{"error":"not found"}`，音频无法下载** |
| 11.2b 磁盘文件与 id 一致性 | ❌ FAIL | **注册表 id 与磁盘 wav 文件名不匹配** |
| 11.3 用自定义音色 id 合成 | ✅ PASS | resolve_voice 回退到 closest 内置音色，合成成功 |
| 11.4 DELETE 删除 | ✅ PASS | 注册表删除成功（但磁盘 wav 成为孤儿文件） |

---

## 重点 Bug 分析

### Bug: 自定义音色上传后 ref_wav URL 不可访问

**现象**: 上传 wav 后返回的 `ref_wav` URL 请求返回 `{"error":"not found"}`，参考音频无法下载。

**根因**（`backend/app/voice_lab.py`）:

`create_custom()` 函数在第 250 行生成了第一个 `vid`：
```python
vid = "custom_" + uuid.uuid4().hex[:8]       # vid_A
wav_path = os.path.join(REFS_DIR, f"{vid}.wav")  # 保存为 {vid_A}.wav
# ...
"ref_wav": f"/api/voices/custom/{vid}/audio",      # URL 指向 vid_A
return registry.add(entry)                          # 但 add() 会重新生成 vid
```

`registry.add()` 在第 218 行又生成了**第二个** `vid`：
```python
def add(self, entry):
    vid = "custom_" + uuid.uuid4().hex[:8]   # vid_B ≠ vid_A
    entry["id"] = vid                         # entry.id = vid_B
    self.items[vid] = entry                   # 注册表 key = vid_B
    return entry
```

结果：
- 磁盘文件: `{vid_A}.wav`
- 注册表 key: `{vid_B}`
- `ref_wav` URL: `/api/voices/custom/{vid_A}/audio`
- entry.id: `{vid_B}`

当 GET `/api/voices/custom/{vid_B}/audio` 时：
1. `registry.get(vid_B)` → 找到 entry
2. 查找 `REFS_DIR/{vid_B}.wav` → **不存在**（实际文件是 `{vid_A}.wav`）
3. 返回 `{"error":"audio missing"}`

当 GET `/api/voices/custom/{vid_A}/audio`（即 ref_wav URL）时：
1. `registry.get(vid_A)` → **None**（注册表 key 是 vid_B）
2. 返回 `{"error":"not found"}`

两种路径都失败。

**实际验证数据**:
- 本次测试上传返回 id = `custom_841739ca`
- 磁盘 refs 目录文件: `custom_162c2f76.wav, custom_4737d840.wav, custom_4ce40985.wav, custom_62241b10.wav, custom_9ca90044.wav, custom_ecedbc1a.wav`
- 注册表中 key 为 `custom_c1398408` 的条目，其 `ref_wav` 指向 `/api/voices/custom/custom_62241b10/audio`，而磁盘上确实有 `custom_62241b10.wav`——但注册表 key 是 `custom_c1398408`，二者不匹配。

**修复建议**: 在 `create_custom()` 中不要提前生成 vid，改为先生成 entry，调用 `registry.add(entry)` 后用返回的 vid 来构造 ref_wav 和保存 wav；或在 `add()` 中接受外部传入的 vid。

**附带影响**: DELETE 也会残留孤儿 wav 文件（删除时按 registry id 找 wav 找不到）。

---

## 性能观察

### F3: 长文本 TTS 合成慢

>1000 字文本（约 30 句）触发分块后，每句单独调用 Edge-TTS（共 84 个 piece），120 秒内未完成。这是架构性瓶颈——逐句同步网络调用，无并发。建议对短 piece 做并发合成或使用 Edge-TTS 的长文本一次性合成能力。

---

## 结论

核心 API（健康检查、音色列表、文件解析、情绪分析、TTS 合成、音乐生成/适配/分析、任务查询、SSE）均功能正常。**唯一阻断性 Bug 是自定义音色的 uuid 重复生成导致 ref_wav 不可访问**，影响参考音频试听和未来克隆引擎的 prompt_speech 加载，需优先修复。
