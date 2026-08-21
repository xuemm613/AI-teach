/**
 * 答题判题纯函数（无副作用，便于单元测试）。
 *
 * - 多选：统一把 checkbox 数组（如 ['B','A','A']）归一化排序拼接（"AAB"），
 *   与标准答案（如 "AAB"/"A,B,A"）做归一化后比较；
 * - 单选/判断/填空：归一化字符串后比较。
 */

/** 归一化：去空白/去常见标点/转小写 */
export function normAnswer(s) {
  return (s == null ? '' : String(s))
    .trim()
    .toLowerCase()
    .replace(/[\s，。、,.;；:：'"“”]/g, '')
}

/** 多选：数组 → 排序拼接字符串；其余类型保证字符串 */
export function normalizePracticeAnswer(type, value) {
  if (Array.isArray(value)) {
    // 单选误传多值场景也做排序拼接，兜底不崩溃
    return [...value].filter(Boolean).sort().join('')
  }
  if (type === 'multiple') {
    return (value || '').replace(/[，,]/g, '')
  }
  return value || ''
}

/** 判题核心：返回该作答是否与标准答案一致 */
export function isAnswerCorrect(type, userAnswer, answer) {
  const ua = normAnswer(normalizePracticeAnswer(type, userAnswer))
  const ans = normAnswer(answer)
  if (!ua) return false
  if (type === 'judge') {
    const judgeMap = { 对: 'a', 正确: 'a', true: 'a', 错: 'b', 错误: 'b', false: 'b' }
    const u = judgeMap[ua] || ua
    const a = judgeMap[ans] || ans
    return !!u && u === a
  }
  if (type === 'multiple') {
    return [...ua].sort().join('') === [...ans].sort().join('')
  }
  // single / fill / qa
  return ua === ans
}

/** 题型中文标签 */
export const TYPE_LABELS = {
  single: '单选题',
  multiple: '多选题',
  judge: '判断题',
  fill: '填空题',
  qa: '问答题',
}

const TYPE_ALIAS = {
  single: 'single', 单选题: 'single', 单选: 'single', choice: 'single', choices: 'single',
  select: 'single', selected: 'single',
  multiple: 'multiple', 多选题: 'multiple', 多选: 'multiple', multi: 'multiple',
  multiplechoice: 'multiple', multiple_choice: 'multiple',
  judge: 'judge', 判断题: 'judge', 判断: 'judge', true_false: 'judge', 对的错: 'judge',
  fill: 'fill', 填空题: 'fill', 填空: 'fill', blank: 'fill', fillblank: 'fill', 空: 'fill',
  qa: 'qa', 问答题: 'qa', 问答: 'qa', shortanswer: 'qa', short_answer: 'qa', text: 'qa',
}

/** 题型归一化：把中文/英文等异构 type 归一到标准 key */
export function typeKey(type) {
  return TYPE_ALIAS[String(type || '').trim().toLowerCase()] || 'qa'
}

/** 展示用题型标签 */
export function typeLabel(type, hasOptions) {
  const k = typeKey(type)
  // 有选项却识别为问答型 → 按单选题展示
  const key = k === 'qa' && hasOptions ? 'single' : k
  return TYPE_LABELS[key] || '题目'
}