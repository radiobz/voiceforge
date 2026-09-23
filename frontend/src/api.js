const BASE = ''

async function j(url, opts) {
  const r = await fetch(BASE + url, opts)
  if (!r.ok) {
    let msg = r.statusText
    try { msg = (await r.json()).detail || msg } catch (e) { /* ignore */ }
    throw new Error(msg)
  }
  return r.json()
}

export const api = {
  voices(lang, q) {
    const p = new URLSearchParams()
    if (lang) p.set('lang', lang)
    if (q) p.set('q', q)
    const qs = p.toString()
    return j(`/api/voices${qs ? '?' + qs : ''}`)
  },
  parse(file) {
    const fd = new FormData()
    fd.append('file', file)
    return j('/api/files/parse', { method: 'POST', body: fd })
  },
  analyze(text) {
    return j('/api/emotion/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    })
  },
  synthesize(payload) {
    return j('/api/tts/synthesize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
  },
  task(id) {
    return j(`/api/tasks/${id}`)
  },
  taskStream(id, onData) {
    const es = new EventSource(`${BASE}/api/tasks/${id}/stream`)
    es.onmessage = e => onData(JSON.parse(e.data))
    return es
  }
}

export const EMOTIONS = [
  { key: 'joy', label: '开心' },
  { key: 'sad', label: '悲伤' },
  { key: 'angry', label: '愤怒' },
  { key: 'calm', label: '平静' },
  { key: 'surprised', label: '惊喜' },
  { key: 'fear', label: '恐惧' }
]
