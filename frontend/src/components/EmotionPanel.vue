<template>
  <div class="card ecard">
    <div class="head">
      <span class="ic amber">
        <svg viewBox="0 0 24 24" fill="none"><path d="M12 3c2.5 3 4.5 5.2 4.5 8a4.5 4.5 0 1 1-9 0c0-2.8 2-5 4.5-8Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>
      </span>
      <span class="t">情绪与参数</span>
      <label class="switch" :class="{off: !autoEmotion}">
        <input type="checkbox" :checked="autoEmotion" @change="$emit('toggle-auto')" />
        <span class="track"></span>自动识别
      </label>
    </div>
    <div class="body">
      <div v-if="analyzing" class="detect"><span class="spin"></span>正在分析文本情绪…</div>
      <div v-else-if="autoEmotion && detected && detected.emotion !== 'calm'" class="detect">
        <svg viewBox="0 0 24 24" fill="none"><path d="M12 2v4m0 12v4M2 12h4m12 0h4M5 5l2.5 2.5M16.5 16.5 19 19M19 5l-2.5 2.5M7.5 16.5 5 19" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/><circle cx="12" cy="12" r="3.5" stroke="currentColor" stroke-width="1.7"/></svg>
        已识别：<b>{{ detected.label }}</b> · 强度 {{ detected.strength.toFixed(2) }}
      </div>
      <div v-else-if="autoEmotion" class="detect quiet">
        <svg viewBox="0 0 24 24" fill="none"><path d="M12 2v4m0 12v4M2 12h4m12 0h4M5 5l2.5 2.5M16.5 16.5 19 19M19 5l-2.5 2.5M7.5 16.5 5 19" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/><circle cx="12" cy="12" r="3.5" stroke="currentColor" stroke-width="1.7"/></svg>
        已识别：平静（无明显情绪）
      </div>

      <div class="echips">
        <button class="echip" :class="{sel: emotion==='auto'}" @click="$emit('emotion','auto')">自动<span class="em">auto</span></button>
        <button v-for="e in EMOTIONS" :key="e.key" class="echip" :class="{sel: emotion===e.key}" @click="$emit('emotion', e.key)">
          {{ e.label }}<span class="em">{{ e.key }}</span>
        </button>
      </div>

      <div class="params">
        <div class="param">
          <div class="p-head"><span>情绪强度</span><span class="val">{{ strength.toFixed(1) }}</span></div>
          <input type="range" min="0.1" max="1.5" step="0.1" :value="strength" @input="$emit('strength', +$event.target.value)" />
        </div>
        <div class="param">
          <div class="p-head"><span>语速</span><span class="val">{{ rate.toFixed(2) }}×</span></div>
          <input type="range" min="0.5" max="2" step="0.05" :value="rate" @input="$emit('rate', +$event.target.value)" />
        </div>
        <div class="param">
          <div class="p-head"><span>音调</span><span class="val">{{ pitch > 0 ? '+' : '' }}{{ pitch }}Hz</span></div>
          <input type="range" min="-50" max="50" step="1" :value="pitch" @input="$emit('pitch', +$event.target.value)" />
        </div>
        <div class="param">
          <div class="p-head"><span>音量</span><span class="val">{{ Math.round(volume * 100) }}%</span></div>
          <input type="range" min="0" max="2" step="0.05" :value="volume" @input="$emit('volume', +$event.target.value)" />
        </div>
      </div>
      <p class="hint">情绪通过语音韵律（语速/音调/音量）自然表达；免费 Edge 端点不支持更高级的说话风格，若追求更强的情绪表现可后续接入本地模型引擎。</p>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { api, EMOTIONS } from '../api'

const props = defineProps({
  text: String, autoEmotion: Boolean, emotion: String, strength: Number,
  rate: Number, pitch: Number, volume: Number
})
defineEmits(['toggle-auto', 'emotion', 'strength', 'rate', 'pitch', 'volume'])
const detected = ref(null)
const analyzing = ref(false)

let timer = null
watch(() => props.text, () => {
  clearTimeout(timer)
  timer = setTimeout(analyze, 600)
}, { immediate: true })

async function analyze() {
  if (!props.text.trim()) { detected.value = null; return }
  analyzing.value = true
  try {
    const r = await api.analyze(props.text)
    detected.value = r
  } catch (e) { /* 静默 */ }
  analyzing.value = false
}
</script>

<style scoped>
.ecard { overflow: hidden; }
.head { display: flex; align-items: center; gap: 10px; padding: 13px 16px; border-bottom: 1px solid var(--line); }
.head .ic { width: 28px; height: 28px; border-radius: 8px; display: grid; place-items: center; flex: none; }
.head .ic svg { width: 15px; height: 15px; }
.head .ic.amber { background: var(--amber-soft); color: var(--amber); }
.head .t { font-size: 14px; font-weight: 700; }
.body { padding: 13px 16px 15px; }
.switch { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; color: var(--ink-soft); cursor: pointer; margin-left: auto; user-select: none; }
.switch input { display: none; }
.switch .track { width: 32px; height: 18px; border-radius: 999px; background: var(--teal); position: relative; transition: background .2s; }
.switch .track::after { content: ""; position: absolute; top: 2px; right: 2px; width: 14px; height: 14px; border-radius: 50%; background: #fff; transition: right .2s; }
.switch.off .track { background: #CFC8B8; }
.switch.off .track::after { right: 16px; }
.detect {
  display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--teal);
  background: var(--teal-soft); border-radius: 9px; padding: 8px 11px; margin-bottom: 11px; font-weight: 600;
}
.detect svg { width: 14px; height: 14px; flex: none; }
.detect.quiet { color: var(--ink-soft); font-weight: 400; }
.spin { width: 13px; height: 13px; border: 2px solid var(--teal); border-top-color: transparent; border-radius: 50%; animation: rot 0.8s linear infinite; flex: none; }
@keyframes rot { to { transform: rotate(360deg); } }
.echips { display: grid; grid-template-columns: repeat(4, 1fr); gap: 7px; }
.echip {
  border: 1px solid var(--line); border-radius: 9px; padding: 7px 2px; text-align: center;
  font-size: 12px; background: var(--card); transition: all .15s;
}
.echip .em { display: block; font-size: 9.5px; color: var(--ink-faint); margin-top: 1px; font-family: var(--mono); }
.echip:hover { border-color: var(--line-strong); }
.echip.sel { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); font-weight: 700; }
.echip.sel .em { color: var(--accent); }
.params { margin-top: 13px; display: grid; grid-template-columns: 1fr 1fr; gap: 13px 15px; }
.param { font-size: 11.5px; color: var(--ink-soft); }
.param .p-head { display: flex; justify-content: space-between; margin-bottom: 6px; }
.param .val { font-family: var(--mono); color: var(--ink); font-weight: 600; }
.hint { margin-top: 13px; font-size: 11px; color: var(--ink-faint); line-height: 1.6; }
</style>
