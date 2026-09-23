<template>
  <div class="mwrap">

    <!-- ============ 独立音乐生成 ============ -->
    <div class="card mcard">
      <div class="head">
        <span class="ic accent">
          <svg viewBox="0 0 24 24" fill="none"><path d="M9 18V6l10-2v12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="7" cy="18" r="2.2" stroke="currentColor" stroke-width="1.8"/><circle cx="17" cy="16" r="2.2" stroke="currentColor" stroke-width="1.8"/></svg>
        </span>
        <span class="t">独立音乐生成</span>
        <span class="tag gray" style="margin-left:auto">算法生成 · 每次随机</span>
      </div>
      <div class="body">
        <div class="ctl-row">
          <div class="ctl">
            <label>风格</label>
            <div class="chips-row">
              <button v-for="m in MODES" :key="m.key" class="chip" :class="{on: genMode===m.key}"
                      @click="genMode = m.key">{{ m.label }}</button>
            </div>
          </div>
          <div class="ctl grow">
            <label>时长 · <b>{{ genMin }} 分钟</b></label>
            <input type="range" min="1" max="40" step="1" v-model.number="genMin">
            <div class="rng-scale"><span>1</span><span>10</span><span>20</span><span>40</span></div>
          </div>
          <div class="ctl">
            <label>情绪基调</label>
            <select v-model="genMood">
              <option value="">随机</option>
              <option v-for="e in MOOD_OPTS" :key="e.key" :value="e.key">{{ e.label }}</option>
            </select>
          </div>
          <div class="ctl">
            <label>节奏密度</label>
            <select v-model="genRhythm">
              <option value="">自动</option>
              <option v-for="r in RHYTHM_OPTS" :key="r.key" :value="r.key">{{ r.label }}</option>
            </select>
          </div>
          <div class="ctl">
            <label>乐器</label>
            <div class="chips-row">
              <button class="chip" :class="{on: genGuitar}" @click="genGuitar = !genGuitar">吉他</button>
            </div>
          </div>
        </div>
        <div class="btn-row">
          <button class="btn primary" :disabled="genBusy" @click="generateMusic">
            <svg v-if="!genBusy" viewBox="0 0 24 24" fill="none"><path d="M8 5v14l11-7L8 5Z" fill="currentColor"/></svg>
            <svg v-else class="spin" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="2" stroke-dasharray="30 20" stroke-linecap="round"/></svg>
            {{ genBusy ? '生成中…' : '生成音乐' }}
          </button>
          <button v-if="genTask" class="btn" :disabled="genBusy" @click="rollAgain">换一首</button>
          <span class="tip">最长 40 分钟 · 生成通常需十几秒到一分钟</span>
        </div>

        <!-- 参考风格分析：上传音频/视频 -> 分析 -> 按此风格生成 -->
        <div class="ctl-row ana-row">
          <label class="ana-label">参考风格</label>
          <label class="file-btn btn">
            <svg viewBox="0 0 24 24" fill="none"><path d="M12 16V4m0 0 5 5m-5-5-5 5M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
            上传音/视频分析风格
            <input type="file" accept="audio/*,video/*" hidden @change="analyzeRef" :disabled="anaBusy">
          </label>
          <span v-if="anaBusy" class="tip">分析中…</span>
          <span v-else-if="anaInfo" class="tip mono">{{ anaInfo }}</span>
        </div>

        <div v-if="genBusy" class="progress-bar"><i :style="{width: genTask ? genTask.progress + '%' : '8%'}"></i></div>

        <div v-if="genTask && genTask.status === 'failed'" class="err">{{ genTask.message }}</div>

        <div v-if="genTask && genTask.status === 'done'" class="result">
          <div class="meta">
            <span class="chip on">{{ genTask.music_meta.label }}</span>
            <span v-if="genTask.music_meta.from_profile" class="chip accent">参考风格</span>
            <span class="chip">{{ genTask.music_meta.key }}调</span>
            <span class="chip">{{ genTask.music_meta.bpm }} BPM</span>
            <span v-if="genTask.music_meta.rhythm !== 'none'" class="chip">{{ ({none:'无节奏',light:'轻鼓点',standard:'标准',full:'饱满'})[genTask.music_meta.rhythm] }}</span>
            <span v-if="genTask.music_meta.guitar" class="chip">吉他</span>
            <span class="chip">{{ genTask.music_meta.kind }}</span>
            <span class="chip mono">seed {{ genTask.music_meta.seed }}</span>
          </div>
          <div class="player">
            <audio controls :src="genTask.audio_url"></audio>
            <a class="btn primary sm" :href="genTask.audio_url" download>
              <svg viewBox="0 0 24 24" fill="none"><path d="M12 3v12m0 0 5-5m-5 5-5-5M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
              下载 MP3
            </a>
          </div>
          <p class="done-msg">{{ genTask.message }}</p>
        </div>
      </div>
    </div>

    <!-- ============ 自适应配乐 ============ -->
    <div class="card mcard">
      <div class="head">
        <span class="ic teal">
          <svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.8"/><path d="M12 7v5l3.5 2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
        </span>
        <span class="t">自适应配乐</span>
        <span class="tag teal" style="margin-left:auto">情绪 + 时长自动匹配</span>
      </div>
      <div class="body">
        <p v-if="!task || task.status !== 'done'" class="hint">
          先在上方完成一次语音合成，再为这段语音生成匹配的背景音乐（情绪决定调式、时长决定长短、说话段自动压低音乐）。
        </p>

        <template v-if="task && task.status === 'done'">
          <div class="ctl-row">
            <div class="ctl">
              <label>配乐风格</label>
              <select v-model="adMode">
                <option v-for="m in MODES" :key="m.key" :value="m.key">{{ m.label }}</option>
              </select>
            </div>
            <div class="ctl">
              <label>情绪基调</label>
              <select v-model="adMood">
                <option value="">按文本情绪自适应</option>
                <option v-for="e in MOOD_OPTS" :key="e.key" :value="e.key">{{ e.label }}</option>
              </select>
            </div>
            <div class="ctl">
              <label>音乐音量</label>
              <select v-model="adBalance">
                <option value="loud">更明显</option>
                <option value="auto">自动平衡</option>
                <option value="low">压低（人声为主）</option>
              </select>
            </div>
          </div>
          <div class="btn-row">
            <button class="btn primary" :disabled="adBusy" @click="adaptMusic">
              <svg v-if="!adBusy" viewBox="0 0 24 24" fill="none"><path d="M8 5v14l11-7L8 5Z" fill="currentColor"/></svg>
              <svg v-else class="spin" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="2" stroke-dasharray="30 20" stroke-linecap="round"/></svg>
              {{ adBusy ? '配乐中…' : '为当前语音生成配乐' }}
            </button>
            <span class="tip">基于语音 · {{ fmtDur(task.duration) }} · {{ task.segments.length }} 段</span>
          </div>

          <div v-if="adBusy" class="progress-bar"><i :style="{width: (adTask ? adTask.progress : 5) + '%'}"></i></div>

          <div v-if="adTask && adTask.status === 'failed'" class="err">{{ adTask.message }}</div>

          <div v-if="adTask && adTask.status === 'done'" class="result">
            <div class="meta">
              <span class="chip on">{{ adTask.music_meta.label }}</span>
              <span class="chip">{{ adTask.music_meta.key }}调</span>
              <span class="chip">{{ adTask.music_meta.bpm }} BPM</span>
              <span class="chip">平衡 · {{ balanceLabel(adTask.music_meta.balance) }}</span>
            </div>
            <div class="tracks">
              <div class="track">
                <span class="tname">混音成品</span>
                <audio controls :src="adTask.audio_url"></audio>
                <a class="btn sm" :href="adTask.audio_url" download>下载</a>
              </div>
              <div class="track">
                <span class="tname">纯语音</span>
                <audio controls :src="adTask.voice_url"></audio>
                <a class="btn sm" :href="adTask.voice_url" download>下载</a>
              </div>
              <div class="track">
                <span class="tname">纯音乐</span>
                <audio controls :src="adTask.music_url"></audio>
                <a class="btn sm" :href="adTask.music_url" download>下载</a>
              </div>
            </div>
            <div class="dl-more">
              <a v-if="adTask.subtitle_url" class="btn sm" :href="adTask.subtitle_url" download>SRT 字幕</a>
              <span class="done-msg">{{ adTask.message }}</span>
            </div>
          </div>
        </template>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../api'

const props = defineProps({ task: Object })
const emit = defineEmits(['toast'])

const MODES = [
  { key: 'chill', label: 'Chill' },
  { key: 'lofi', label: 'Lofi · 黑胶' },
  { key: 'meditation', label: '冥想静想' },
  { key: 'ambient', label: '轻氛围' }
]
const MOOD_OPTS = [
  { key: 'joy', label: '开心·明亮' },
  { key: 'calm', label: '平静·空灵' },
  { key: 'sad', label: '悲伤·舒缓' },
  { key: 'angry', label: '张力·小调' },
  { key: 'fear', label: '暗色·缥缈' },
  { key: 'surprised', label: '惊喜·灵动' }
]
const RHYTHM_OPTS = [
  { key: 'none', label: '无节奏' },
  { key: 'light', label: '轻鼓点' },
  { key: 'standard', label: '标准' },
  { key: 'full', label: '饱满' }
]

const genMode = ref('chill')
const genMin = ref(3)
const genMood = ref('')
const genRhythm = ref('')
const genGuitar = ref(true)
const genBusy = ref(false)
const genTask = ref(null)
const anaBusy = ref(false)
const anaInfo = ref('')
const anaProfile = ref(null)

async function analyzeRef(ev) {
  const file = ev.target.files && ev.target.files[0]
  if (!file) return
  anaBusy.value = true
  anaInfo.value = ''
  anaProfile.value = null
  try {
    const r = await api.musicAnalyze(file)
    anaProfile.value = r.params
    anaInfo.value = `BPM ${r.profile.bpm} · ${r.profile.key}${r.profile.mode === 'minor' ? 'm' : ''}调 · ${r.profile.beat ? '有律动' : '无节拍'} · 亮度 ${r.profile.brightness}k`
    genMode.value = 'lofi'
    emit('toast', '已按参考风格定向，可直接生成')
  } catch (e) {
    emit('toast', '分析失败：' + e.message)
  } finally {
    anaBusy.value = false
  }
}

const adMode = ref('chill')
const adMood = ref('')
const adBalance = ref('auto')
const adBusy = ref(false)
const adTask = ref(null)

function poll(taskId, onData) {
  const es = api.taskStream(taskId, data => {
    onData(data)
    if (data.status === 'done' || data.status === 'failed') {
      es.close()
      genBusy.value = false
      adBusy.value = false
      if (data.status === 'done') emit('toast', '完成')
    }
  })
}

async function generateMusic() {
  genBusy.value = true
  genTask.value = null
  try {
    const { task_id } = await api.musicGenerate({
      mode: genMode.value,
      duration: genMin.value * 60,
      mood: genMood.value || null,
      rhythm: genRhythm.value || null,
      guitar: genGuitar.value,
      profile: anaProfile.value || null
    })
    poll(task_id, d => { genTask.value = d })
  } catch (e) {
    genBusy.value = false
    emit('toast', '生成失败：' + e.message)
  }
}

function rollAgain() { generateMusic() }

async function adaptMusic() {
  adBusy.value = true
  adTask.value = null
  try {
    const { task_id } = await api.musicAdapt({
      task_id: props.task.task_id,
      mode: adMode.value,
      mood: adMood.value || null,
      balance: adBalance.value
    })
    const es = api.taskStream(task_id, d => {
      adTask.value = d
      if (d.status === 'done' || d.status === 'failed') {
        es.close()
        adBusy.value = false
        if (d.status === 'done') emit('toast', '配乐完成')
      }
    })
  } catch (e) {
    adBusy.value = false
    emit('toast', '配乐失败：' + e.message)
  }
}

function fmtDur(sec) {
  if (!sec || sec <= 0) return '0:00'
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
function balanceLabel(b) {
  return ({ loud: '更明显', auto: '自动', low: '压低' })[b] || b
}
</script>

<style scoped>
.mwrap { display: flex; flex-direction: column; gap: 14px; }
.mcard { overflow: hidden; }
.head { display: flex; align-items: center; gap: 10px; padding: 13px 16px; border-bottom: 1px solid var(--line); }
.head .ic { width: 28px; height: 28px; border-radius: 8px; display: grid; place-items: center; flex: none; }
.head .ic svg { width: 15px; height: 15px; }
.head .ic.accent { background: var(--accent-soft); color: var(--accent); }
.head .ic.teal { background: var(--teal-soft); color: var(--teal); }
.head .t { font-size: 14px; font-weight: 700; }
.body { padding: 15px 16px 17px; display: flex; flex-direction: column; gap: 12px; }
.hint { font-size: 12.5px; color: var(--ink-faint); line-height: 1.7; border: 1.5px dashed var(--line-strong); border-radius: 11px; padding: 12px 14px; }
.ctl-row { display: flex; gap: 16px; flex-wrap: wrap; }
.ctl { display: flex; flex-direction: column; gap: 7px; }
.ctl.grow { flex: 1; min-width: 170px; }
.ctl label { font-size: 11.5px; color: var(--ink-faint); font-weight: 600; }
.ctl label b { color: var(--ink); font-family: var(--mono); }
.ctl select {
  border: 1px solid var(--line-strong); border-radius: 9px; background: var(--card);
  padding: 7px 10px; font-size: 12.5px; color: var(--ink); outline: none;
}
.chips-row { display: flex; gap: 7px; }
.chip {
  border: 1px solid var(--line-strong); background: var(--card); border-radius: 999px;
  padding: 6px 13px; font-size: 12px; color: var(--ink-soft); font-weight: 600; transition: all .15s;
}
.chip.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.chip.mono { font-family: var(--mono); font-size: 11px; }
input[type="range"] { width: 100%; accent-color: var(--accent); }
.rng-scale { display: flex; justify-content: space-between; font-size: 10px; color: var(--ink-faint); font-family: var(--mono); }
.btn-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.ana-row { align-items: center; gap: 10px; margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--line); }
.ana-label { font-size: 12px; color: var(--ink-faint); }
.file-btn { cursor: pointer; margin: 0; }
.tip { font-size: 11.5px; color: var(--ink-faint); }
.progress-bar { height: 7px; border-radius: 999px; background: var(--line); overflow: hidden; }
.progress-bar i { display: block; height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--teal), #4FB6B4); transition: width .4s; }
.err { font-size: 12.5px; color: #A33A2E; background: #F3E3E3; border-radius: 9px; padding: 9px 12px; }
.result { border-top: 1px solid var(--line); padding-top: 13px; display: flex; flex-direction: column; gap: 11px; }
.meta { display: flex; gap: 7px; flex-wrap: wrap; }
.player { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.player audio { flex: 1; min-width: 220px; }
.tracks { display: flex; flex-direction: column; gap: 8px; }
.track { display: flex; align-items: center; gap: 10px; }
.tname { font-size: 12.5px; font-weight: 700; width: 66px; flex: none; }
.track audio { flex: 1; min-width: 160px; }
.dl-more { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.done-msg { font-size: 11.5px; color: var(--ink-faint); }
.spin { animation: rot 1s linear infinite; }
@keyframes rot { to { transform: rotate(360deg); } }
@media (max-width: 640px) {
  .track { flex-wrap: wrap; }
  .track audio { min-width: 100%; }
  .tname { width: auto; }
}
</style>
