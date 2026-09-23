<template>
  <div class="ws">
    <div class="ws-top">
      <div>
        <h1>新建合成任务</h1>
        <p class="sub">文本 · 音色 · 情绪 · 参数，一次配齐</p>
      </div>
      <div class="acts">
        <button class="btn" @click="showImport = true">
          <svg viewBox="0 0 24 24" fill="none"><path d="M12 16V4m0 0L7 9m5-5 5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
          导入文件
        </button>
        <button class="btn" @click="clearText">
          <svg viewBox="0 0 24 24" fill="none"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m3 0-1 13a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L6 7" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>
          清空
        </button>
      </div>
    </div>

    <!-- 文本输入 -->
    <div class="card tcard">
      <div class="tcard-head">
        <span class="ic accent">
          <svg viewBox="0 0 24 24" fill="none"><path d="M4 6h16M4 12h10M4 18h7" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>
        </span>
        <span class="t">待合成文本</span>
        <span class="chips"><em>.txt</em><em>.docx</em><em>.pdf</em></span>
        <span class="tag gray" style="margin-left:auto">自动检测编码</span>
      </div>
      <div class="tarea-wrap">
        <textarea v-model="text" placeholder="在这里输入文字，或点击右上角「导入文件」上传 txt / Word / PDF 文档……" :disabled="busy"></textarea>
      </div>
      <div class="tcard-foot">
        <span>字数 <b>{{ text.length.toLocaleString() }}</b></span>
        <span>约 <b>{{ Math.max(1, Math.round(text.length / 4.2 / 60 * 10) / 10) }}</b> 分钟</span>
        <span v-if="text.length > 1000" class="tag amber" style="margin-left:auto">自动分块 · {{ blockCount }} 块</span>
        <span v-else class="tag teal" style="margin-left:auto">单块合成</span>
      </div>
    </div>

    <div class="two-col">
      <VoicePanel :voices="voices" :loading="voicesLoading" :voice="voice" @select="voice = $event" @toast="emit('toast', $event)" />
      <EmotionPanel :text="text" :auto-emotion="autoEmotion" :emotion="emotion" :strength="strength"
        :rate="rate" :pitch="pitch" :volume="volume"
        @toggle-auto="autoEmotion = !autoEmotion"
        @emotion="emotion = $event"
        @strength="strength = $event"
        @rate="rate = $event" @pitch="pitch = $event" @volume="volume = $event" />
    </div>

    <div class="gen-row">
      <button class="btn primary big" :disabled="!text.trim() || busy" @click="synthesize">
        <svg v-if="!busy" viewBox="0 0 24 24" fill="none"><path d="M8 5v14l11-7L8 5Z" fill="currentColor"/></svg>
        <svg v-else class="spin" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="2" stroke-dasharray="30 20" stroke-linecap="round"/></svg>
        {{ busy ? '合成中…' : '开始合成' }}
      </button>
    </div>

    <OutputCard :task="task" :busy="busy" :voice="voice" :emotion-label="emotionLabel"
      @toast="emit('toast', $event)" @done="onDone" />

    <ImportModal v-if="showImport" @close="showImport = false" @imported="onImported" @toast="emit('toast', $event)" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { api, EMOTIONS } from '../api'
import VoicePanel from './VoicePanel.vue'
import EmotionPanel from './EmotionPanel.vue'
import OutputCard from './OutputCard.vue'
import ImportModal from './ImportModal.vue'

const emit = defineEmits(['toast', 'save-history'])

const text = ref('')
const voices = ref([])
const voicesLoading = ref(true)
const voice = ref('zh-CN-XiaoxiaoNeural')
const autoEmotion = ref(true)
const emotion = ref('auto')
const strength = ref(0.6)
const rate = ref(1.0)
const pitch = ref(0)
const volume = ref(1.0)
const busy = ref(false)
const task = ref(null)
const showImport = ref(false)

const blockCount = computed(() => Math.ceil(text.value.length / 1000))
const emotionLabel = computed(() => {
  if (emotion.value === 'auto') return '自动识别'
  const e = EMOTIONS.find(x => x.key === emotion.value)
  return e ? e.label : '平静'
})

onMounted(async () => {
  try {
    const all = await api.voices('zh-CN')
    voices.value = all
    if (all.length) voice.value = all[0].short_name
  } catch (e) {
    emit('toast', '音色列表加载失败：' + e.message)
  }
  voicesLoading.value = false
})

// 手动指定情绪时关闭自动
watch(emotion, v => { if (v !== 'auto') autoEmotion.value = false })

function clearText() { text.value = ''; task.value = null }
function onImported(t) { text.value = t; emit('toast', `已导入文本 · ${t.length.toLocaleString()} 字`) }

async function synthesize() {
  busy.value = true
  task.value = null
  try {
    const payload = {
      text: text.value,
      voice: voice.value,
      auto_emotion: autoEmotion.value,
      emotion: emotion.value === 'auto' ? null : emotion.value,
      emotion_strength: strength.value,
      rate: rate.value, pitch: pitch.value, volume: volume.value,
      output_format: 'mp3',
      with_subtitle: true
    }
    const { task_id } = await api.synthesize(payload)
    const es = api.taskStream(task_id, data => {
      task.value = data
      if (data.status === 'done') {
        es.close()
        busy.value = false
        emit('toast', '合成完成')
      } else if (data.status === 'failed') {
        es.close()
        busy.value = false
        emit('toast', data.message)
      }
    })
  } catch (e) {
    busy.value = false
    emit('toast', '合成失败：' + e.message)
  }
}

function onDone(item) {
  emit('save-history', item)
}
</script>

<style scoped>
.ws { display: flex; flex-direction: column; gap: 14px; max-width: 1060px; margin: 0 auto; }
.ws-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.ws-top h1 { font-size: 21px; font-weight: 800; letter-spacing: -.3px; }
.ws-top .sub { font-size: 12px; color: var(--ink-faint); margin-top: 2px; }
.acts { display: flex; gap: 8px; }
.tcard-head { display: flex; align-items: center; gap: 10px; padding: 13px 16px; border-bottom: 1px solid var(--line); }
.tcard-head .ic { width: 28px; height: 28px; border-radius: 8px; display: grid; place-items: center; flex: none; }
.tcard-head .ic svg { width: 15px; height: 15px; }
.tcard-head .ic.accent { background: var(--accent-soft); color: var(--accent); }
.tcard-head .t { font-size: 14px; font-weight: 700; }
.chips { display: flex; gap: 6px; }
.chips em { font-style: normal; font-size: 10.5px; font-family: var(--mono); border: 1px solid var(--line); border-radius: 6px; padding: 2px 8px; color: var(--ink-faint); }
.tarea-wrap { padding: 14px 16px 8px; }
.tarea-wrap textarea {
  width: 100%; min-height: 130px; border: 1px dashed var(--line-strong); border-radius: 11px;
  background: #FBFAF5; padding: 13px 15px; font-size: 14px; line-height: 1.8; color: var(--ink);
  resize: vertical; outline: none; transition: all .15s;
}
.tarea-wrap textarea:focus { border-color: var(--teal); background: #fff; }
.tarea-wrap textarea:disabled { opacity: .7; }
.tcard-foot { display: flex; align-items: center; gap: 16px; padding: 0 16px 13px; font-size: 12px; color: var(--ink-faint); flex-wrap: wrap; }
.tcard-foot b { font-family: var(--mono); color: var(--ink); font-weight: 600; }
.two-col { display: grid; grid-template-columns: 1.2fr 1fr; gap: 14px; }
.gen-row .btn.big { width: 100%; justify-content: center; padding: 13px; font-size: 14.5px; }
.spin { animation: rot 1s linear infinite; }
@keyframes rot { to { transform: rotate(360deg); } }
@media (max-width: 900px) { .two-col { grid-template-columns: 1fr; } }
</style>
