<template>
  <div class="page">
    <div class="ph">
      <h1>历史记录</h1>
      <p class="sub">本地保存最近 50 条合成记录 · 刷新后仍可回听与下载</p>
      <button v-if="items.length" class="btn sm" @click="$emit('clear')">
        <svg viewBox="0 0 24 24" fill="none"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m3 0-1 13a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L6 7" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>
        清空
      </button>
    </div>
    <div v-if="!items.length" class="card empty">
      暂无记录。完成一次合成后，记录会自动保存在这里。
    </div>
    <div v-else class="list">
      <div v-for="it in items" :key="it.id + it.at" class="card row">
        <button class="play-btn" @click="play(it)">
          <svg v-if="!playingId || playingId !== it.id" viewBox="0 0 24 24"><path d="M8 5v14l11-7L8 5Z"/></svg>
          <svg v-else viewBox="0 0 24 24"><path d="M7 5h4v14H7zM13 5h4v14h-4z"/></svg>
        </button>
        <div class="info">
          <div class="txt">{{ it.text }}…</div>
          <div class="meta">
            <span class="tag teal">{{ it.emotion }}</span>
            <span>{{ it.voice }}</span>
            <span>{{ fmtTime(it.at) }}</span>
            <span>{{ fmtDur(it.duration) }}</span>
          </div>
        </div>
        <div class="dl">
          <a class="btn sm" :href="it.audioUrl" download>
            <svg viewBox="0 0 24 24" fill="none"><path d="M12 3v12m0 0 5-5m-5 5-5-5M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
            下载
          </a>
        </div>
        <audio v-if="playingId === it.id" ref="audios" :src="it.audioUrl" style="display:none" @ended="playingId=null" autoplay></audio>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'

const props = defineProps({ items: Array })
defineEmits(['toast', 'clear'])
const playingId = ref(null)
const audios = ref([])

function play(it) {
  if (playingId.value === it.id) { playingId.value = null; return }
  playingId.value = it.id
  nextTick(() => {
    const a = audios.value[0]
    if (a) a.play().catch(() => {})
  })
}
function fmtTime(ts) {
  const d = new Date(ts)
  return `${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
function fmtDur(sec) {
  if (!sec) return '—'
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
</script>

<style scoped>
.page { max-width: 860px; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; }
.ph { display: flex; align-items: flex-end; gap: 14px; flex-wrap: wrap; }
.ph h1 { font-size: 21px; font-weight: 800; }
.ph .sub { font-size: 12px; color: var(--ink-faint); margin-bottom: 2px; }
.ph .btn { margin-left: auto; }
.empty { text-align: center; color: var(--ink-faint); font-size: 13px; padding: 44px 20px; border-style: dashed; }
.list { display: flex; flex-direction: column; gap: 10px; }
.row { display: flex; align-items: center; gap: 14px; padding: 13px 16px; }
.play-btn { width: 40px; height: 40px; border-radius: 50%; background: var(--accent); border: 0; display: grid; place-items: center; cursor: pointer; flex: none; }
.play-btn svg { width: 15px; height: 15px; fill: #fff; }
.info { flex: 1; min-width: 0; }
.txt { font-size: 13.5px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.meta { display: flex; align-items: center; gap: 10px; margin-top: 5px; font-size: 11px; color: var(--ink-faint); flex-wrap: wrap; }
.dl .btn { flex: none; }
@media (max-width: 640px) { .dl .btn { padding: 6px 9px; } }
</style>
