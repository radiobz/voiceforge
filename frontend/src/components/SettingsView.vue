<template>
  <div class="page">
    <div class="ph"><h1>设置</h1><p class="sub">应用级偏好（保存于本地浏览器）</p></div>

    <div class="card sec">
      <div class="s-head"><span class="t">语音引擎</span><span class="tag teal">在线 · 免费</span></div>
      <div class="s-body">
        <div class="kv">
          <span class="k">引擎</span><span class="v">Microsoft Edge-TTS（神经网络语音）</span>
        </div>
        <div class="kv">
          <span class="k">音色数量</span><span class="v">{{ voiceCount }} 个（含多语言）</span>
        </div>
        <div class="kv">
          <span class="k">情绪支持</span><span class="v">内置轻量分类（开心/悲伤/愤怒/平静/惊喜/恐惧）+ 韵律参数映射</span>
        </div>
        <div class="kv">
          <span class="k">自然度说明</span>
          <span class="v">本应用定位「自然真人朗读 / 播报级」。Edge 神经语音朗读自然流畅、无机械断句，但无法达到豆包 / ChatGPT 那种端到端对话大模型的拟真度；项目已预留本地大模型引擎（如 CosyVoice）升级入口。</span>
        </div>
      </div>
    </div>

    <div class="card sec">
      <div class="s-head"><span class="t">合成默认值</span></div>
      <div class="s-body grid">
        <label class="field">
          <span class="k">默认音色</span>
          <select v-model="defVoice">
            <option v-for="v in defVoices" :key="v" :value="v">{{ v }}</option>
          </select>
        </label>
        <label class="field">
          <span class="k">输出格式</span>
          <select v-model="defFormat">
            <option value="mp3">MP3（体积小）</option>
            <option value="wav">WAV（无损）</option>
          </select>
        </label>
        <label class="field">
          <span class="k">长文本分块上限（字/块）</span>
          <select v-model="chunkSize">
            <option :value="500">500</option>
            <option :value="1000">1000（推荐）</option>
            <option :value="1500">1500</option>
            <option :value="2000">2000</option>
          </select>
        </label>
        <label class="field">
          <span class="k">自动附带 SRT 字幕</span>
          <select v-model="subtitle">
            <option :value="true">是</option>
            <option :value="false">否</option>
          </select>
        </label>
      </div>
      <div class="s-foot">
        <button class="btn primary" @click="save">保存设置</button>
        <span class="note">默认值仅影响新任务，不修改历史记录</span>
      </div>
    </div>

    <div class="card sec">
      <div class="s-head"><span class="t">关于灵声 VoiceForge</span></div>
      <div class="s-body">
        <div class="kv"><span class="k">版本</span><span class="v">v0.1.0 · M1 里程碑</span></div>
        <div class="kv"><span class="k">技术栈</span><span class="v">Vue 3 + Vite · FastAPI · Edge-TTS · FFmpeg</span></div>
        <div class="kv"><span class="k">许可证</span><span class="v">MIT</span></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const emit = defineEmits(['toast'])
const KEY = 'voiceforge_settings'
const voiceCount = ref(322)
const defVoice = ref('zh-CN-XiaoxiaoNeural')
const defFormat = ref('mp3')
const chunkSize = ref(1000)
const subtitle = ref(true)
const defVoices = ref(['zh-CN-XiaoxiaoNeural', 'zh-CN-XiaoyiNeural', 'zh-CN-YunxiNeural', 'zh-CN-YunyangNeural', 'en-US-AriaNeural'])

onMounted(async () => {
  try {
    const st = JSON.parse(localStorage.getItem(KEY) || '{}')
    if (st.defVoice) defVoice.value = st.defVoice
    if (st.defFormat) defFormat.value = st.defFormat
    if (st.chunkSize) chunkSize.value = st.chunkSize
    if (typeof st.subtitle === 'boolean') subtitle.value = st.subtitle
    const all = await api.voices('')
    if (all.length) voiceCount.value = all.length
  } catch (e) { /* ignore */ }
})

function save() {
  const st = { defVoice: defVoice.value, defFormat: defFormat.value, chunkSize: +chunkSize.value, subtitle: subtitle.value }
  localStorage.setItem(KEY, JSON.stringify(st))
  emit('toast', '设置已保存')
}
</script>

<style scoped>
.page { max-width: 860px; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; }
.ph h1 { font-size: 21px; font-weight: 800; }
.ph .sub { font-size: 12px; color: var(--ink-faint); margin-top: 2px; }
.sec { padding: 0; }
.s-head { display: flex; align-items: center; gap: 10px; padding: 13px 16px; border-bottom: 1px solid var(--line); }
.s-head .t { font-size: 14px; font-weight: 700; }
.s-body { padding: 15px 16px; display: flex; flex-direction: column; gap: 11px; }
.s-body.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 13px; }
.kv { display: flex; gap: 14px; font-size: 13px; }
.kv .k { color: var(--ink-faint); width: 88px; flex: none; font-size: 12px; padding-top: 1px; }
.kv .v { color: var(--ink-soft); }
.field { display: flex; flex-direction: column; gap: 5px; }
.field .k { font-size: 12px; color: var(--ink-faint); }
.field select { border: 1px solid var(--line-strong); border-radius: 9px; background: var(--card); padding: 9px 11px; font-size: 13px; color: var(--ink); outline: none; }
.s-foot { display: flex; align-items: center; gap: 14px; padding: 0 16px 16px; }
.note { font-size: 11px; color: var(--ink-faint); }
@media (max-width: 640px) { .s-body.grid { grid-template-columns: 1fr; } }
</style>
