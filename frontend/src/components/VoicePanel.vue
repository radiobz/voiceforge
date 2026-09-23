<template>
  <div class="card vcard">
    <div class="head">
      <span class="ic teal">
        <svg viewBox="0 0 24 24" fill="none"><path d="M9 18V6l10-2v12" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/><circle cx="6.5" cy="18" r="2.5" stroke="currentColor" stroke-width="1.7"/><circle cx="16.5" cy="16" r="2.5" stroke="currentColor" stroke-width="1.7"/></svg>
      </span>
      <span class="t">选择音色</span>
      <span class="tag gray" style="margin-left:auto">{{ voices.length }} 个音色</span>
    </div>
    <div class="body">
      <div class="vsearch">
        <svg viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="1.7"/><path d="m20 20-4-4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>
        <input v-model="q" placeholder="搜索音色或语言…" />
      </div>
      <div class="vgrid">
        <button v-for="v in filtered" :key="v.short_name" class="vitem" :class="{sel: v.short_name===voice}" @click="$emit('select', v.short_name)">
          <span class="ava" :style="avaStyle(v)">{{ shortName(v) }}</span>
          <span class="info">
            <span class="nm">{{ v.display_name }}</span>
            <span class="meta">{{ v.locale }} · {{ v.gender === 'Female' ? '女声' : '男声' }}{{ v.tags.length ? ' · ' + v.tags.slice(0,2).join(' ') : '' }}</span>
          </span>
          <span class="play"><svg viewBox="0 0 24 24" fill="none"><path d="M8 5v14l11-7L8 5Z" fill="currentColor"/></svg></span>
        </button>
        <div v-if="!filtered.length" class="empty">没有匹配的音色</div>
      </div>
      <div class="vfoot"><span>共 {{ voices.length }} 个 · 免费在线</span></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({ voices: Array, loading: Boolean, voice: String })
defineEmits(['select', 'toast'])
const q = ref('')

const filtered = computed(() => {
  if (!q.value) return props.voices.slice(0, 12)
  const kw = q.value.toLowerCase()
  return props.voices.filter(v =>
    v.short_name.toLowerCase().includes(kw) ||
    v.display_name.toLowerCase().includes(kw) ||
    v.locale.toLowerCase().includes(kw)
  ).slice(0, 24)
})

function shortName(v) {
  const m = v.short_name.match(/^[a-z]{2}-[A-Z]{2}-([A-Za-z]+)/)
  return m ? m[1].slice(0, 2) : v.short_name.slice(0, 2)
}
function avaStyle(v) {
  const colors = ['#E2572E', '#0E7C7B', '#7A5FA8', '#C8861E', '#3E7CB1', '#B0578D']
  let h = 0
  for (const c of v.short_name) h = (h * 31 + c.charCodeAt(0)) % 997
  return { background: colors[h % colors.length] }
}
</script>

<style scoped>
.vcard { overflow: hidden; }
.head { display: flex; align-items: center; gap: 10px; padding: 13px 16px; border-bottom: 1px solid var(--line); }
.head .ic { width: 28px; height: 28px; border-radius: 8px; display: grid; place-items: center; flex: none; }
.head .ic svg { width: 15px; height: 15px; }
.head .ic.teal { background: var(--teal-soft); color: var(--teal); }
.head .t { font-size: 14px; font-weight: 700; }
.body { padding: 13px 16px 15px; }
.vsearch { display: flex; align-items: center; gap: 8px; border: 1px solid var(--line); border-radius: 10px; background: var(--card); padding: 8px 12px; margin-bottom: 12px; }
.vsearch svg { width: 14px; height: 14px; color: var(--ink-faint); flex: none; }
.vsearch input { border: 0; outline: 0; background: transparent; font-size: 13px; width: 100%; color: var(--ink); }
.vgrid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.vitem {
  display: flex; align-items: center; gap: 10px; border: 1px solid var(--line);
  border-radius: 11px; padding: 10px; background: var(--card); text-align: left;
  transition: all .15s;
}
.vitem:hover { border-color: var(--line-strong); }
.vitem.sel { border-color: var(--accent); background: var(--accent-soft); box-shadow: 0 0 0 1px var(--accent); }
.ava { width: 34px; height: 34px; border-radius: 50%; flex: none; display: grid; place-items: center; font-size: 11px; font-weight: 700; color: #fff; }
.info { min-width: 0; }
.nm { display: block; font-size: 12.5px; font-weight: 700; line-height: 1.3; }
.meta { display: block; font-size: 10px; color: var(--ink-faint); margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.play { margin-left: auto; width: 24px; height: 24px; border-radius: 50%; border: 1px solid var(--line-strong); display: grid; place-items: center; color: var(--ink); flex: none; background: var(--card); }
.play svg { width: 10px; height: 10px; }
.vfoot { display: flex; justify-content: space-between; margin-top: 11px; font-size: 11px; color: var(--ink-faint); }
.empty { grid-column: 1 / -1; text-align: center; color: var(--ink-faint); font-size: 12.5px; padding: 18px 0; }
</style>
