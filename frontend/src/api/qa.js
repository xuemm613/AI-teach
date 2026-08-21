import request from './request'

export const ask = (data) => request.post('/qa/ask', data).then((r) => r.data)

// 流式问答：通过 fetch 读取 SSE，逐字回调
export async function askStream({ question, session_id, subject, chapter, history, onToken, onDone, context_from, stage_name, stage_content, weak_points }) {
  const res = await fetch('/api/v1/qa/ask-stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`
    },
    body: JSON.stringify({ question, session_id, subject, chapter, history, context_from, stage_name, stage_content, weak_points })
  })
  if (!res.ok || !res.body) throw new Error('请求失败')
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let full = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop()
    for (const part of parts) {
      for (const line of part.split('\n')) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6).trim()
        if (!data || data === '[DONE]') continue
        try {
          const obj = JSON.parse(data)
          if (obj.token) { full += obj.token; onToken && onToken(full) }
          if (obj.done) { onDone && onDone(obj.session_id) }
        } catch (e) { /* 忽略无法解析的分片 */ }
      }
    }
  }
  return full
}
export const collect = (data) => request.post('/qa/collect', data).then((r) => r.data)
export const listSessions = () => request.get('/qa/sessions').then((r) => r.data)
export const sessionMessages = (id) => request.get(`/qa/sessions/${id}`).then((r) => r.data)
export const deleteSession = (id) => request.delete(`/qa/sessions/${id}`).then((r) => r.data)