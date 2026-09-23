<template>
  <div class="card ocard">
    <div class="head">
      <span class="ic accent">
        <svg viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" stroke-width="1.8"/><path d="M9 9l6 6m0-6-6 6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
      </span>
      <span class="t">合成输出</span>
      <span v-if="task && task.status==='done'" class="tag teal" style="margin-left:auto">已完成 · {{ fmtDur(task.duration) }}</span>
      <span v-else-if="task && task.status==='failed'" class="tag" style="margin-left:auto;background:#F3E3E3;color:#A33A2E">失败</span>
      <span v-else-if="task && task.status==='running'" class="tag amber" style="margin-left:auto">{{ Math.round(task.progress) }}%</span>
      <span v-else class="tag gray" style="margin-left:auto">等待合成</span>
    </div>

    <!-- 空态 -->
    <div v-if="!task || task.status==='failed'" class="body empty-state">
      <template v-if="task && task.status==='failed'">{{ task.message }}</template>
      <template v-else>输入文本并点击「开始合成」，音频将在这里出现。</template>
    </div>

    <!-- 进度态 -->
    <div v-else-if="task.status==='running' || task.status==='queued'" class="body">
      <div class="progress-bar"><i :style="{width: task.progress + '%'}"></i></div>
      <p class="msg">{{ task.message }} · {{ Math.round(task.progress) }}%</p>
      <div class="segs">
        <div v-for="s in task.segments" :key="s.index" class="seg">
          <span class="idx">#{{ String(s.index).padStart(2,'0') }}</span>
          <span v-if="s.role" class="role">{{ s.role }}</span>
          <span class="em">{{ s.label }}</span>
          <span class="bar"><i style="width:60%"></i></span>
          <span class="st">合成中…</span>
        </div>
      </div>
    </div>

    <!-- 完成态 -->
    <div v-else-if="task.status==='done'" class="body">
      <div class="player">
        <button class="play-btn" @click="togglePlay">
          <svg v-if="!playing" viewBox="0 0 24 24"><path d="M8 5v14l11-7L8 5Z"/></svg>
          <svg v-else viewBox="0 0 24 24"><path d="M7 5h4v14H7zM13 5h4v14h-4z"/></svg>
        </button>
        <div class="wave" @click="seekFromWave">
          <i v-for="(w,i) in waves" :key="i" :class="{played: i <= waveIndex}"></i>
        </div>
        <span class="time">{{ fmtDur(cur) }} / {{ fmtDur(task.duration) }}</span>
        <div class="dl">
          <a class="btn primary sm" :href="task.audio_url" download>
            <svg viewBox="0 0 24 24" fill="none"><path d="M12 3v12m0 0 5-5m-5 5-5-5M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
            下载 MP3
          </a>
          <a v-if="task.subtitle_url" class="btn sm" :href="task.subtitle_url" download>
            <svg viewBox="0 0 24 24" fill="none"><rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.7"/><path d="M7 11h6M7 14h4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>
            SRT 字幕
          </a>
        </div>
      </div>
      <audio ref="audioEl" :src="task.audio_url" @timeupdate="onTime" @ended="playing=false" style="display:none"></audio>
      <div class="segs">
        <div v-for="s in task.segments" :key="s.index" class="seg">
          <span class="idx">#{{ String(s.index).padStart(2,'0') }}</span>
          <span v-if="s.role" class="role">{{ s.role }}</span>
          <span class="em" :class="'e-'+s.emotion">{{ s.label }}</span>
          <span class="bar"><i :style="{width: Math.min(100, s.duration / Math.max(1, task.duration) * 100) + '%'}"></i></span>
          <span class="st">{{ fmtDur(s.duration) }}</span>
        </div>
      </div>
      <p class="done-msg">{{ task.message }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({ task: Object, busy: Boolean, voice: String, emotionLabel: String })
const emit = defineEmits(['toast', 'done'])

const audioEl = ref(null)
const playing = ref(false)
const cur = ref(0)
const waveIndex = ref(0)
const waves = Array.from({ length: 36 }, () => 10 + Math.round(Math.random() * 26))

watch(() => props.task?.status, (s) => {
  if (s === 'done' && props.task) {
    emit('done', {
      id: props.task.task_id,
      text: props.task.segments.map(x => x.text).join('').slice(0, 60),
      voice: props.voice,
      emotion: props.emotionLabel,
      duration: props.task.duration,
      audioUrl: props.task.audio_url,
      at: Date.now()
    })
  }
})

function fmtDur(sec) {
  if (!sec || sec <= 0) return '0:00'
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
function togglePlay() {
  const a = audioEl.value
  if (!a) return
  if (a.paused) { a.play(); playing.value = true } else { a.pause(); playing.value = false }
}
function onTime() {
  const a = audioEl.value
  cur.value = a.currentTime
  waveIndex.value = Math.round(a.currentTime / Math.max(0.1, props.task.duration) * (waves.length - 1))
}
function seekFromWave(e) {
  const a = audioEl.value
  if (!a) return
  const rect = e.currentTarget.getBoundingClientRect()
  const ratio = (e.clientX - rect.left) / rect.width
  a.currentTime = ratio * a.duration
}
</script>

<style scoped>
.ocard { overflow: hidden; }
.head { display: flex; align-items: center; gap: 10px; padding: 13px 16px; border-bottom: 1px solid var(--line); }
.head .ic { width: 28px; height: 28px; border-radius: 8px; display: grid; place-items: center; flex: none; }
.head .ic svg { width: 15px; height: 15px; }
.head .ic.accent { background: var(--accent-soft); color: var(--accent); }
.head .t { font-size: 14px; font-weight: 700; }
.body { padding: 15px 16px 17px; }
.empty-state { color: var(--ink-faint); font-size: 13px; text-align: center; padding: 26px 10px; border: 1.5px dashed var(--line-strong); border-radius: 12px; }
.progress-bar { height: 7px; border-radius: 999px; background: var(--line); overflow: hidden; }
.progress-bar i { display: block; height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--teal), #4FB6B4); transition: width .4s; }
.msg { font-size: 12.5px; color: var(--ink-soft); margin-top: 9px; }
.player { display: flex; align-items: center; gap: 13px; }
.play-btn {
  width: 45px; height: 45px; border-radius: 50%; background: var(--accent); border: 0;
  display: grid; place-items: center; cursor: pointer; flex: none; box-shadow: 0 4px 14px rgba(226,87,46,.35);
}
.play-btn svg { width: 17px; height: 17px; fill: #fff; }
.wave { flex: 1; display: flex; align-items: center; gap: 3px; height: 44px; cursor: pointer; }
.wave i { flex: 1; background: var(--accent); opacity: .35; border-radius: 2px; min-width: 2px; }
.wave i:nth-child(3n) { background: var(--teal); }
.wave i:nth-child(5n) { background: #C9C2B2; }
.wave i.played { opacity: 1; }
.time { font-family: var(--mono); font-size: 11.5px; color: var(--ink-faint); flex: none; }
.dl { display: flex; gap: 7px; flex: none; }
.segs { margin-top: 13px; border-top: 1px solid var(--line); padding-top: 11px; display: grid; gap: 7px; }
.seg { display: flex; align-items: center; gap: 9px; font-size: 12px; color: var(--ink-soft); }
.idx { font-family: var(--mono); color: var(--ink-faint); width: 40px; flex: none; font-size: 11px; }
.role { flex: none; font-size: 11px; font-weight: 700; color: var(--teal); background: var(--teal-soft); border-radius: 6px; padding: 1px 8px; }
.em { flex: none; min-width: 34px; font-weight: 600; font-size: 11px; }
.e-joy { color: #B0578D; } .e-sad { color: #3E5C9B; } .e-angry { color: #C0392B; }
.e-calm { color: var(--ink-faint); } .e-surprised { color: #C8861E; } .e-fear { color: #5A4A8F; }
.bar { flex: 1; height: 5px; border-radius: 999px; background: var(--line); position: relative; overflow: hidden; }
.bar i { position: absolute; left: 0; top: 0; bottom: 0; background: var(--teal); border-radius: 999px; }
.st { font-size: 11px; color: var(--ink-faint); flex: none; font-family: var(--mono); }
.done-msg { font-size: 11.5px; color: var(--ink-faint); margin-top: 10px; }
@media (max-width: 700px) {
  .player { flex-wrap: wrap; }
  .dl { width: 100%; }
  .dl .btn { flex: 1; justify-content: center; }
}
</style>
