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
      <!-- 自定义音色上传 -->
      <div class="custom-zone">
        <div class="cz-head">
          <span class="cz-t">自定义音色</span>
          <button class="btn sm" @click="fileInput.click()" :disabled="uploading">
            <svg viewBox="0 0 24 24" fill="none"><path d="M12 16V4m0 0L7 9m5-5 5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
            {{ uploading ? '分析中…' : '导入音视频' }}
          </button>
          <input ref="fileInput" type="file" accept="audio/*,video/*" style="display:none" @change="onPick" />
        </div>
        <p class="cz-note">
          上传语音或视频片段，自动提取人声并分析音色标签；Edge 引擎以「近似音色」参与合成，
          参考片段会持久保存，接入 CosyVoice2 后可零样本克隆。
        </p>
        <!-- 分析结果卡片 -->
        <div v-if="lastCustom" class="cz-result">
          <div class="cz-info">
            <span class="cz-name">{{ lastCustom.display_name }}</span>
            <span class="tags">
              <span v-for="t in (lastCustom.analysis?.tags || [])" :key="t" class="tag teal">{{ t }}</span>
            </span>
            <span class="cz-meta">
              {{ lastCustom.analysis?.gender || '' }}
              {{ lastCustom.analysis?.f0_median ? '· 基频 ' + lastCustom.analysis.f0_median + ' Hz' : '' }}
              {{ lastCustom.analysis?.duration ? '· ' + lastCustom.analysis.duration + 's' : '' }}
            </span>
            <span v-if="lastCustom.closest?.length" class="cz-match">
              近似音色：<b>{{ lastCustom.closest[0].short_name }}</b>（{{ lastCustom.closest[0].gender === 'Female' ? '女声' : '男声' }}）
            </span>
          </div>
          <div class="cz-acts">
            <button class="btn sm" @click="preview(lastCustom.id)">
              <svg viewBox="0 0 24 24" fill="none"><path d="M8 5v14l11-7L8 5Z" fill="currentColor"/></svg>
              试听
            </button>
            <button class="btn primary sm" @click="$emit('select', lastCustom.id)">设为音色</button>
          </div>
        </div>
        <!-- 已有自定义音色 -->
        <div v-if="customVoices.length" class="custom-list">
          <div v-for="v in customVoices" :key="v.short_name" class="custom-item" :class="{sel: v.short_name===voice}" @click="$emit('select', v.short_name)">
            <span class="c-ava">{{ initial(v.display_name) }}</span>
            <span class="c-info">
              <span class="c-nm">{{ v.display_name }}</span>
              <span class="c-tags">{{ (v.tags || []).join(' · ') || '自定义音色' }}</span>
            </span>
            <button class="play-mini" @click.stop="preview(v.short_name)">
              <svg viewBox="0 0 24 24" fill="none"><path d="M8 5v14l11-7L8 5Z" fill="currentColor"/></svg>
            </button>
          </div>
        </div>
        <audio v-if="previewing" :src="previewSrc" autoplay style="display:none" @ended="previewing=''" />
      </div>

      <div class="vsearch">
        <svg viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="1.7"/><path d="m20 20-4-4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>
        <input v-model="q" placeholder="搜索音色或语言…" />
      </div>
      <div class="vgrid">
        <button v-for="v in filtered" :key="v.short_name" class="vitem" :class="{sel: v.short_name===voice}" @click="$emit('select', v.short_name)">
          <span class="ava" :style="avaStyle(v)">{{ shortName(v) }}</span>
          <span class="info">
            <span class="nm">{{ v.display_name }}</span>
            <span class="meta">{{ v.locale }} · {{ v.gender === 'Female' ? '女声' : v.gender === 'Male' ? '男声' : v.gender }}{{ v.tags.length ? ' · ' + v.tags.slice(0,2).join(' ') : '' }}</span>
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
import { api } from '../api'

const props = defineProps({ voices: Array, loading: Boolean, voice: String })
const emit = defineEmits(['select', 'toast', 'custom-uploaded'])
const q = ref('')
const fileInput = ref(null)
const uploading = ref(false)
const lastCustom = ref(null)
const previewing = ref('')
const previewSrc = ref('')

const customVoices = computed(() => props.voices.filter(v => v.voice_type === 'custom'))
const filtered = computed(() => {
  if (!q.value) return props.voices.slice(0, 14)
  const kw = q.value.toLowerCase()
  return props.voices.filter(v =>
    v.short_name.toLowerCase().includes(kw) ||
    v.display_name.toLowerCase().includes(kw) ||
    v.locale.toLowerCase().includes(kw)
  ).slice(0, 24)
})

async function onPick(e) {
  const f = e.target.files[0]
  if (!f) return
  uploading.value = true
  try {
    const entry = await api.uploadCustomVoice(f)
    lastCustom.value = entry
    emit('custom-uploaded', entry)
    emit('toast', `已分析音色：${entry.display_name}`)
  } catch (err) {
    emit('toast', '导入失败：' + err.message)
  }
  uploading.value = false
  e.target.value = ''
}

function preview(id) {
  const v = customVoices.value.find(x => x.short_name === id) || lastCustom.value
  if (!v?.ref_wav) return
  if (previewing.value === id) { previewing.value = ''; return }
  previewing.value = id
  previewSrc.value = v.ref_wav
}

function initial(name) {
  const m = String(name || '').replace(/^自定义\s*[·:]?\s*/, '')
  return m ? m[0] : '自'
}
function shortName(v) {
  if (v.voice_type === 'custom') return initial(v.display_name)
  const m = v.short_name.match(/^[a-z]{2}-[A-Z]{2}-([A-Za-z]+)/)
  return m ? m[1].slice(0, 2) : v.short_name.slice(0, 2)
}
function avaStyle(v) {
  const colors = ['#E2572E', '#0E7C7B', '#7A5FA8', '#C8861E', '#3E7CB1', '#B0578D']
  let h = 0
  for (const c of v.short_name) h = (h * 31 + c.charCodeAt(0)) % 997
  return { background: v.voice_type === 'custom' ? '#1D1B16' : colors[h % colors.length] }
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
.custom-zone { border: 1px dashed var(--line-strong); border-radius: 11px; padding: 11px 12px; margin-bottom: 12px; background: #FBFAF5; }
.cz-head { display: flex; align-items: center; gap: 10px; }
.cz-t { font-size: 12.5px; font-weight: 700; color: var(--ink-soft); }
.cz-head .btn { margin-left: auto; }
.cz-note { font-size: 10.5px; color: var(--ink-faint); line-height: 1.6; margin-top: 7px; }
.cz-result { margin-top: 10px; background: var(--card); border: 1px solid var(--line); border-radius: 9px; padding: 10px 12px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.cz-info { flex: 1; min-width: 200px; }
.cz-name { font-size: 12.5px; font-weight: 700; margin-right: 8px; }
.tags { display: inline-flex; gap: 5px; }
.tags .tag { font-size: 9.5px; padding: 1px 7px; }
.cz-meta { display: block; font-size: 10.5px; color: var(--ink-faint); margin-top: 3px; }
.cz-match { display: block; font-size: 10.5px; color: var(--teal); margin-top: 2px; }
.cz-match b { font-family: var(--mono); }
.cz-acts { display: flex; gap: 7px; }
.custom-list { margin-top: 9px; display: grid; gap: 6px; }
.custom-item { display: flex; align-items: center; gap: 9px; border: 1px solid var(--line); border-radius: 9px; padding: 8px 10px; cursor: pointer; transition: all .15s; }
.custom-item:hover { border-color: var(--line-strong); }
.custom-item.sel { border-color: var(--accent); background: var(--accent-soft); }
.c-ava { width: 26px; height: 26px; border-radius: 50%; background: var(--ink); color: #fff; display: grid; place-items: center; font-size: 11px; font-weight: 700; flex: none; }
.c-info { flex: 1; min-width: 0; }
.c-nm { display: block; font-size: 12px; font-weight: 700; line-height: 1.3; }
.c-tags { display: block; font-size: 10px; color: var(--ink-faint); margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.play-mini { width: 24px; height: 24px; border-radius: 50%; border: 1px solid var(--line-strong); background: var(--card); display: grid; place-items: center; color: var(--ink); flex: none; }
.play-mini svg { width: 10px; height: 10px; }
.vsearch { display: flex; align-items: center; gap: 8px; border: 1px solid var(--line); border-radius: 10px; background: var(--card); padding: 8px 12px; margin-bottom: 12px; }
.vsearch svg { width: 14px; height: 14px; color: var(--ink-faint); flex: none; }
.vsearch input { border: 0; outline: 0; background: transparent; font-size: 13px; width: 100%; color: var(--ink); }
.vgrid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.vitem { display: flex; align-items: center; gap: 10px; border: 1px solid var(--line); border-radius: 11px; padding: 10px; background: var(--card); text-align: left; transition: all .15s; }
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
