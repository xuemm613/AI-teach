<script setup>
import { computed } from 'vue'

const props = defineProps({
  content: { type: String, default: '' }
})

function escapeHtml(s) {
  return (s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function inline(s) {
  return s
    .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
}

function renderMarkdown(text) {
  const lines = (text || '').split('\n')
  const out = []
  let inCode = false
  let list = null

  const closeList = () => {
    if (list) {
      out.push(`</${list}>`)
      list = null
    }
  }

  let i = 0
  while (i < lines.length) {
    const raw = lines[i]
    const trimmed = escapeHtml(raw).trim()

    if (/^```/.test(trimmed)) {
      closeList()
      if (inCode) {
        out.push('</pre>')
        inCode = false
      } else {
        out.push('<pre>')
        inCode = true
      }
      i++
      continue
    }
    if (inCode) {
      out.push(escapeHtml(raw))
      i++
      continue
    }
    // 表格：连续以 | 开头的行渲染为 HTML 表格，避免表格错位
    if (/^\s*\|/.test(raw)) {
      closeList()
      const tableRows = []
      while (i < lines.length && /^\s*\|/.test(lines[i])) {
        tableRows.push(lines[i])
        i++
      }
      const rows = tableRows.map((row) =>
        row.split('|').slice(1, -1).map((c) => inline(escapeHtml(c).trim()))
      )
      // 过滤分隔行（如 |---|---|）
      const body = rows.filter((r, idx) => !(idx === 1 && r.every((c) => /^:?-{2,}:?$/.test(c))))
      let html = '<table><thead><tr>'
      ;(body[0] || []).forEach((c) => { html += `<th>${c}</th>` })
      html += '</tr></thead><tbody>'
      for (const row of body.slice(1)) {
        html += '<tr>'
        row.forEach((c) => { html += `<td>${c}</td>` })
        html += '</tr>'
      }
      html += '</tbody></table>'
      out.push(html)
      continue
    }
    if (!trimmed) {
      closeList()
      i++
      continue
    }
    const h3 = trimmed.match(/^###\s+(.*)$/)
    const h2 = trimmed.match(/^##\s+(.*)$/)
    const h1 = trimmed.match(/^#\s+(.*)$/)
    if (h1 || h2 || h3) {
      closeList()
      const tag = h1 ? 'h1' : h2 ? 'h2' : 'h3'
      out.push(`<${tag}>${inline((h1 || h2 || h3)[1])}</${tag}>`)
      i++
      continue
    }
    const li = trimmed.match(/^[-*]\s+(.*)$/) || trimmed.match(/^\d+\.\s+(.*)$/)
    if (li) {
      if (list !== 'ul') {
        closeList()
        out.push('<ul>')
        list = 'ul'
      }
      out.push(`<li>${inline(li[1])}</li>`)
      i++
      continue
    }
    closeList()
    out.push(`<p>${inline(trimmed)}</p>`)
    i++
  }
  if (inCode) out.push('</pre>')
  closeList()
  return out.join('\n')
}

const html = computed(() => renderMarkdown(props.content))
</script>

<template>
  <div class="markdown-body" v-html="html"></div>
</template>
