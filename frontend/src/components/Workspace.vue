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
        <span class="mode-switch">
          <button class="mode-btn" :class="{on: mode==='plain'}" @click="mode='plain'">朗读模式</button>
          <button class="mode-btn" :class="{on: mode==='script'}" @click="mode='script'">剧本模式</button>
        </span>
        <span class="tag gray" style="margin-left:auto">自动检测编码</span>
      </div>
      <div class="tarea-wrap">
        <textarea v-model="text" placeholder="在这里输入文字，或点击右上角「导入文件」上传 txt / Word / PDF 文档……" :disabled="busy"></textarea>
      </div>
      <div class="tcard-foot">
        <span>字数 <b>{{ text.length.toLocaleString() }}</b></span>
        <span v-if="mode==='plain'">约 <b>{{ Math.max(1, Math.round(text.length / 4.2 / 60 * 10) / 10) }}</b> 分钟</span>
        <span v-else class="tag teal">剧本 · {{ scriptRoles.length }} 个角色</span>
        <span v-if="mode==='plain' && text.length > 1000" class="tag amber" style="margin-left:auto">自动分块 · {{ blockCount }} 块</span>
        <span v-else-if="mode==='plain'" class="tag teal" style="margin-left:auto">单块合成</span>
      </div>
      <p v-if="mode==='script'" class="script-hint">
        每行按 <b>角色名：台词</b> 书写；未标注的行自动归为「旁白」。示例：<code>林小雨：我真的不想再等了！</code>
      </p>
    </div>

    <div v-if="mode==='script' && scriptRoles.length" class="card rolecard">
      <div class="head">
        <span class="ic amber"><svg viewBox="0 0 24 24" fill="none"><circle cx="9" cy="8" r="3.2" stroke="currentColor" stroke-width="1.7"/><path d="M3.5 19c.6-3 2.8-4.5 5.5-4.5s4.9 1.5 5.5 4.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/><circle cx="17" cy="9" r="2.6" stroke="currentColor" stroke-width="1.7"/><path d="M15.5 14.6c2.2.3 3.9 1.5 4.5 3.9" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg></span>
        <span class="t">角色音色分配</span>
        <span class="tag gray" style="margin-left:auto">留空 = 自动分配</span>
      </div>
      <div class="roles">
        <div v-for="r in scriptRoles" :key="r" class="role-row">
          <span class="rname">{{ r }}</span>
          <select :value="roleSel[r] || ''" @change="roleSel[r] = $event.target.value">
            <option value="">自动分配</option>
            <option v-for="v in zhVoices" :key="v.short_name" :value="v.short_name">{{ v.display_name }}</option>
          </select>
        </div>
      </div>
    </div>

    <div class="two-col">
      <VoicePanel :voices="voices" :loading="voicesLoading" :voice="voice" @select="voice = $event" @toast="emit('toast', $event)" @custom-uploaded="onCustomUploaded" />
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

    <MusicPanel :task="task" @toast="emit('toast', $event)" />

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
import MusicPanel from './MusicPanel.vue'

const emit = defineEmits(['toast', 'save-history'])

const text = ref('')
const voices = ref([])
const zhVoices = ref([])
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
const mode = ref('plain')
const roleSel = ref({})

const blockCount = computed(() => Math.ceil(text.value.length / 1000))
const emotionLabel = computed(() => {
  if (emotion.value === 'auto') return '自动识别'
  const e = EMOTIONS.find(x => x.key === emotion.value)
  return e ? e.label : '平静'
})

const scriptRoles = computed(() => {
  const roles = new Set()
  for (const line of text.value.split('\n')) {
    const m = line.match(/^([^\s：:]{1,16})[：:]\s*(.+)$/)
    if (m && m[1].length < 10 && m[2].trim()) roles.add(m[1].trim())
  }
  roles.delete('旁白')
  return [...roles]
})

onMounted(async () => {
  try {
    const all = await api.voices('zh-CN')
    voices.value = all
    zhVoices.value = all
    if (all.length) voice.value = all[0].short_name
  } catch (e) {
    emit('toast', '音色列表加载失败：' + e.message)
  }
  voicesLoading.value = false
})

// 手动指定情绪时关闭自动
watch(emotion, v => { if (v !== 'auto') autoEmotion.value = false })

// 文本含剧本格式时自动切换到剧本模式
watch(text, () => {
  if (text.value && scriptRoles.value.length && mode.value === 'plain') mode.value = 'script'
})

function clearText() { text.value = ''; task.value = null }
function onImported(t) { text.value = t; emit('toast', `已导入文本 · ${t.length.toLocaleString()} 字`) }

function onCustomUploaded(entry) {
  const vo = {
    short_name: entry.id,
    display_name: '自定义 · ' + entry.display_name,
    locale: 'custom',
    gender: entry.analysis?.gender || '未知',
    tags: entry.analysis?.tags || [],
    voice_type: 'custom',
    ref_wav: entry.ref_wav || '',
    analysis: entry.analysis || {},
    closest: entry.closest || []
  }
  voices.value = [vo, ...voices.value.filter(v => v.short_name !== entry.id)]
}

async function synthesize() {
  busy.value = true
  task.value = null
  try {
    const roleMap = {}
    for (const [r, v] of Object.entries(roleSel.value)) {
      if (v) roleMap[r] = v
    }
    const payload = {
      text: text.value,
      voice: voice.value,
      script_mode: mode.value === 'script',
      role_map: Object.keys(roleMap).length ? roleMap : undefined,
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
.mode-switch { display: inline-flex; border: 1px solid var(--line-strong); border-radius: 999px; padding: 2px; }
.mode-btn { border: 0; background: transparent; border-radius: 999px; padding: 4px 13px; font-size: 12px; color: var(--ink-soft); font-weight: 600; transition: all .15s; }
.mode-btn.on { background: var(--accent); color: #fff; }
.script-hint { font-size: 11.5px; color: var(--ink-faint); padding: 0 16px 11px; line-height: 1.6; }
.script-hint b { color: var(--ink-soft); }
.script-hint code { font-family: var(--mono); font-size: 11px; background: var(--paper); border: 1px solid var(--line); border-radius: 5px; padding: 1px 6px; color: var(--teal); }
.rolecard .head { display: flex; align-items: center; gap: 10px; padding: 12px 16px; border-bottom: 1px solid var(--line); }
.rolecard .head .ic { width: 26px; height: 26px; border-radius: 8px; display: grid; place-items: center; flex: none; }
.rolecard .head .ic svg { width: 14px; height: 14px; }
.rolecard .head .ic.amber { background: var(--amber-soft); color: var(--amber); }
.rolecard .head .t { font-size: 13.5px; font-weight: 700; }
.roles { padding: 12px 16px; display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 9px; }
.role-row { display: flex; align-items: center; gap: 10px; }
.rname { font-size: 12.5px; font-weight: 700; min-width: 70px; }
.role-row select { flex: 1; border: 1px solid var(--line-strong); border-radius: 9px; background: var(--card); padding: 7px 10px; font-size: 12.5px; color: var(--ink); outline: none; }
@media (max-width: 640px) { .mode-btn { padding: 4px 10px; font-size: 11.5px; } }
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
