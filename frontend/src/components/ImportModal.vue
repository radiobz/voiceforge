<template>
  <div class="mask" @click.self="$emit('close')">
    <div class="modal card">
      <div class="m-head">
        <h4>导入文本文件</h4>
        <button class="x" @click="$emit('close')">✕</button>
      </div>
      <div class="m-body">
        <div class="drop" @dragover.prevent @drop.prevent="onDrop" @click="pick">
          <svg viewBox="0 0 24 24" fill="none"><path d="M12 16V4m0 0L7 9m5-5 5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
          <div class="dt">拖拽文件到此处，或点击选择</div>
          <div class="ds">支持 .txt / .docx / .pdf · 单个文件 ≤ 100MB · 自动识别编码</div>
          <div class="files"><em>.txt</em><em>.docx</em><em>.pdf</em></div>
          <input ref="fileInput" type="file" accept=".txt,.docx,.pdf,text/plain,application/pdf" style="display:none" @change="onPick" />
        </div>
        <div v-if="state==='parsing'" class="progress">
          <div class="p-row">
            <span class="fname">{{ fileName }}</span>
            <span class="pct">解析中…</span>
          </div>
          <div class="p-bar"><i></i></div>
          <div class="p-note">正在提取文本并统计字数…</div>
        </div>
        <div v-if="state==='done'" class="progress ok">
          <div class="p-row">
            <span class="fname">{{ fileName }}</span>
            <span class="pct ok">{{ chars.toLocaleString() }} 字</span>
          </div>
          <div class="p-note">解析完成，将填入文本框（预计 {{ blocks }} 个分块）</div>
        </div>
        <div v-if="state==='error'" class="progress err">
          <div class="p-note">{{ error }}</div>
        </div>
      </div>
      <div class="m-foot">
        <button class="btn" @click="$emit('close')">取消</button>
        <button class="btn primary" :disabled="state!=='done'" @click="confirm">确认导入</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../api'

const emit = defineEmits(['close', 'imported', 'toast'])
const fileInput = ref(null)
const state = ref('idle')
const fileName = ref('')
const chars = ref(0)
const blocks = ref(0)
const error = ref('')
let parsedText = ''

function pick() { fileInput.value.click() }
function onPick(e) { const f = e.target.files[0]; if (f) handle(f) }
function onDrop(e) { const f = e.dataTransfer.files[0]; if (f) handle(f) }

async function handle(file) {
  const ext = file.name.split('.').pop().toLowerCase()
  if (!['txt', 'docx', 'pdf'].includes(ext)) {
    emit('toast', '仅支持 txt / docx / pdf 文件')
    return
  }
  if (file.size > 100 * 1024 * 1024) {
    emit('toast', '文件超过 100MB 上限')
    return
  }
  fileName.value = file.name
  state.value = 'parsing'
  try {
    const r = await api.parse(file)
    parsedText = r.text
    chars.value = r.chars
    blocks.value = r.blocks
    state.value = 'done'
  } catch (e) {
    state.value = 'error'
    error.value = '解析失败：' + e.message
  }
}

function confirm() {
  emit('imported', parsedText)
  emit('close')
}
</script>

<style scoped>
.mask {
  position: fixed; inset: 0; background: rgba(29,27,22,.45); z-index: 100;
  display: grid; place-items: center; padding: 20px;
}
.modal { width: 100%; max-width: 520px; }
.m-head { display: flex; align-items: center; justify-content: space-between; padding: 15px 18px; border-bottom: 1px solid var(--line); }
.m-head h4 { font-size: 15px; font-weight: 700; }
.x { width: 26px; height: 26px; border-radius: 50%; border: 1px solid var(--line); background: var(--card); color: var(--ink-faint); font-size: 12px; }
.m-body { padding: 18px; }
.drop {
  border: 2px dashed var(--line-strong); border-radius: 13px; padding: 28px 20px;
  text-align: center; background: #FBFAF5; cursor: pointer; transition: all .15s;
}
.drop:hover { border-color: var(--accent); background: var(--accent-soft); }
.drop svg { width: 30px; height: 30px; color: var(--accent); }
.dt { font-size: 14px; font-weight: 700; margin-top: 9px; }
.ds { font-size: 12px; color: var(--ink-faint); margin-top: 4px; }
.files { margin-top: 10px; display: flex; justify-content: center; gap: 6px; }
.files em { font-style: normal; font-size: 11px; font-family: var(--mono); border: 1px solid var(--line-strong); border-radius: 6px; padding: 3px 10px; color: var(--ink-soft); background: var(--card); }
.progress { margin-top: 15px; background: var(--paper); border: 1px solid var(--line); border-radius: 11px; padding: 13px 15px; }
.p-row { display: flex; align-items: center; gap: 10px; font-size: 12.5px; }
.fname { font-family: var(--mono); font-size: 12px; }
.pct { margin-left: auto; font-family: var(--mono); font-weight: 600; color: var(--teal); }
.pct.ok { color: var(--teal); }
.p-bar { height: 6px; border-radius: 999px; background: var(--line); margin-top: 10px; overflow: hidden; }
.p-bar i { display: block; height: 100%; width: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--teal), #4FB6B4); animation: slide 1.2s ease-in-out infinite; }
@keyframes slide { 0% { width: 20%; } 100% { width: 100%; } }
.p-note { font-size: 11px; color: var(--ink-faint); margin-top: 9px; }
.err .p-note { color: #A33A2E; }
.m-foot { display: flex; gap: 10px; padding: 14px 18px; border-top: 1px solid var(--line); justify-content: flex-end; }
</style>
