<template>
  <div class="shell">
    <aside class="side">
      <div class="logo">
        <span class="lg">
          <svg viewBox="0 0 32 32" fill="none"><path d="M6 20c1-6 3-8 4-8s3 2 4 8c1 6 3 8 4 8s3-2 4-8" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/></svg>
        </span>
        <div>灵声<small>VOICEFORGE</small></div>
      </div>
      <nav>
        <button class="nav-item" :class="{on: view==='work'}" @click="view='work'">
          <svg viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="7" height="9" rx="1.5" stroke="currentColor" stroke-width="1.7"/><rect x="14" y="3" width="7" height="5" rx="1.5" stroke="currentColor" stroke-width="1.7"/><rect x="14" y="12" width="7" height="9" rx="1.5" stroke="currentColor" stroke-width="1.7"/><rect x="3" y="16" width="7" height="5" rx="1.5" stroke="currentColor" stroke-width="1.7"/></svg>
          工作台
        </button>
        <button class="nav-item" :class="{on: view==='history'}" @click="view='history'">
          <svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="1.7"/><path d="M12 7v5l3 2" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>
          历史记录
        </button>
        <button class="nav-item" :class="{on: view==='settings'}" @click="view='settings'">
          <svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.7"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3.9a7 7 0 0 0-2-1.2L14.2 3h-4l-.4 2.6a7 7 0 0 0-2 1.2l-2.3-.9-2 3.4 2 1.5a7 7 0 0 0 0 2.4l-2 1.5 2 3.4 2.3-.9a7 7 0 0 0 2 1.2l.4 2.6h4l.4-2.6a7 7 0 0 0 2-1.2l2.3.9 2-3.4-2-1.5c.06-.4.1-.8.1-1.2Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>
          设置
        </button>
      </nav>
      <div class="engine-box">
        <span class="dot"></span>
        <div>
          <div class="e-name">Edge-TTS</div>
          <div class="e-sub">在线 · 免费</div>
        </div>
      </div>
    </aside>

    <main class="main">
      <Workspace v-if="view==='work'"
        @toast="toast" @save-history="saveHistory" />
      <HistoryView v-else-if="view==='history'"
        :items="history" @toast="toast" @clear="clearHistory" />
      <SettingsView v-else
        @toast="toast" />
    </main>

    <div class="toast" :class="{show: toastMsg}">{{ toastMsg }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import Workspace from './components/Workspace.vue'
import HistoryView from './components/HistoryView.vue'
import SettingsView from './components/SettingsView.vue'

const view = ref('work')
const toastMsg = ref('')
let toastTimer = null
function toast(msg) {
  toastMsg.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toastMsg.value = ''), 2200)
}

const HISTORY_KEY = 'voiceforge_history'
const history = ref([])
function loadHistory() {
  try { history.value = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') } catch (e) { history.value = [] }
}
function saveHistory(item) {
  history.value.unshift(item)
  if (history.value.length > 50) history.value = history.value.slice(0, 50)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value))
}
function clearHistory() {
  history.value = []
  localStorage.removeItem(HISTORY_KEY)
}
onMounted(loadHistory)
</script>

<style scoped>
.shell { display: flex; min-height: 100vh; }
.side {
  width: 188px; flex: none; background: var(--ink); color: var(--paper);
  padding: 20px 14px; display: flex; flex-direction: column; gap: 4px;
}
.logo { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 16px; padding: 4px 8px 22px; }
.logo .lg { width: 30px; height: 30px; border-radius: 9px; background: var(--accent); display: grid; place-items: center; flex: none; }
.logo .lg svg { width: 17px; height: 17px; }
.logo small { display: block; font-size: 9px; font-weight: 400; letter-spacing: 2px; color: rgba(246,243,236,.55); }
.nav-item {
  display: flex; align-items: center; gap: 10px; width: 100%;
  font-size: 13.5px; color: rgba(246,243,236,.62); background: transparent;
  border: 0; border-radius: 9px; padding: 10px 12px; text-align: left; transition: all .15s;
}
.nav-item svg { width: 16px; height: 16px; flex: none; }
.nav-item:hover { color: var(--paper); background: rgba(246,243,236,.07); }
.nav-item.on { background: rgba(246,243,236,.12); color: var(--paper); font-weight: 600; }
.engine-box { margin-top: auto; border-top: 1px solid rgba(246,243,236,.12); padding-top: 14px; display: flex; gap: 9px; align-items: center; font-size: 12px; }
.engine-box .dot { width: 8px; height: 8px; border-radius: 50%; background: #5ED0CD; box-shadow: 0 0 0 3px rgba(94,208,205,.2); flex: none; }
.e-name { font-weight: 600; color: rgba(246,243,236,.85); }
.e-sub { font-size: 10.5px; color: rgba(246,243,236,.5); }
.main { flex: 1; min-width: 0; padding: 22px 26px; }

@media (max-width: 720px) {
  .shell { flex-direction: column; }
  .side { width: 100%; flex-direction: row; align-items: center; padding: 10px 14px; gap: 8px; }
  .logo { padding: 0 10px 0 0; }
  .logo .lg { width: 26px; height: 26px; border-radius: 7px; }
  .logo small { display: none; }
  .nav-item { padding: 8px 10px; font-size: 12.5px; }
  .engine-box { margin-top: 0; margin-left: auto; border-top: 0; padding-top: 0; }
  .main { padding: 14px 14px 80px; }
}
</style>
