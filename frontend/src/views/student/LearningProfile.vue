<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { addWrongBook, batchDeleteWrongBook, deleteWrongBook, getExercises, getMyActivity, getMyStats, getSimilarExercises, getTimeline, getWrongBook, submitRecord } from '@/api/user'
import { myAnalysis, myAnalysisLatest } from '@/api/tutor'
import { selectWeakValues } from '@/utils/weakHighlight'
import { isAnswerCorrect, normalizePracticeAnswer, typeKey, typeLabel } from '@/utils/answer'
import { SUBJECTS } from '@/constants'

const route = useRoute()
const router = useRouter()
const tab = ref('stats')
const stats = ref({})
const wrongItems = ref([])
const timeline = ref([])
const range = ref([])

// 错题本筛选与批量操作
const wrongLoading = ref(false)
const wrongSearch = ref('')
const wrongSubject = ref('')
const wrongKnowledgePoint = ref('')
const wrongSelection = ref([])

// 学习记录筛选：快捷选项 + 自定义范围
const timelineLoading = ref(false)
const timelineQuickFilter = ref('')
const timelineLegend = ref(true)

// 科目筛选：生成方案 + 学习统计（雷达图按科目查看）
const planSubject = ref('')      // '' = 全部科目
const statsSubject = ref('')     // '' = 全部科目
const subjectOptions = computed(() => ['', ...SUBJECTS].map((s) => ({ label: s || '全部科目', value: s })))

// 支持 hash 定位：/student/analysis#wrong 直接跳转到错题本
watch(() => route.hash, (h) => {
  if (h === '#wrong') tab.value = 'wrong'
  if (h === '#records') tab.value = 'records'
}, { immediate: true })

// Agent 个性化方案（生成过一次后一直展示，直到再次点击生成）
const plan = ref(null)
const planDate = ref('')
const planLoading = ref(false)
const generating = ref(false)
const progressText = ref('')
let progressTimer = null
const progressHints = ['正在拉取最近学习记录...', '正在分析学习情况...', '正在诊断薄弱知识点...', '正在生成个性化辅导方案...']

async function genPlan() {
  generating.value = true
  planLoading.value = true
  plan.value = null
  let idx = 0
  progressText.value = progressHints[0]
  progressTimer = setInterval(() => {
    idx = (idx + 1) % progressHints.length
    progressText.value = progressHints[idx]
  }, 2500)
  try {
    const task = await myAnalysis(planSubject.value)
    if (task.status === 'completed') {
      const output = task.output || {}
      if (output.message) {
        plan.value = null
        planDate.value = ''
        ElMessage.warning(output.message)
      } else {
        plan.value = output
        planDate.value = task.created_at || ''
        // 用同一科目数据生成方案时，也同步一次统计展示
        if (planSubject.value === statsSubject.value) loadStats(statsSubject.value)
        ElMessage.success('个性化方案已生成')
      }
    } else {
      ElMessage.warning('方案生成未完成：' + (task.error || '未知原因'))
    }
  } catch (e) {
    ElMessage.error('生成失败，请确认大模型配置')
  } finally {
    clearInterval(progressTimer)
    progressTimer = null
    planLoading.value = false
    generating.value = false
  }
}

// 进入页面直接展示最近一次已生成的方案，不自动重新生成
async function loadLatestPlan() {
  try {
    const task = await myAnalysisLatest()
    if (task && task.status === 'completed' && task.output) {
      if (task.output.message) return
      plan.value = task.output
      planDate.value = task.created_at || ''
    }
  } catch (e) { /* 忽略 */ }
}

// 跳转到智能问答：把目标（阶段目标/推荐练习/薄弱点）一并交给 AI 追问
// 增强：传递结构化上下文参数，使 LLM 能基于完整学情信息生成精准回答
function toChat(q, extraContext = {}) {
  const txt = (q || '').trim()
  if (!txt) return
  const query = { subject: planSubject.value || undefined, q: txt }
  // 携带结构化上下文参数
  if (extraContext.stage) query.stage_name = extraContext.stage
  if (extraContext.stageContent) query.stage_content = extraContext.stageContent
  if (extraContext.weakPoints) query.weak_points = extraContext.weakPoints
  query.context_from = 'analysis'
  router.push({ path: '/student/chat', query })
}

// 导出学情报告（Markdown，带时间戳），学生/家长可保存
function exportPlan() {
  if (!plan.value) { ElMessage.warning('请先生成辅导方案'); return }
  if (plan.value.message) { ElMessage.warning(plan.value.message); return }
  const lines = []
  lines.push('# 学情分析报告')
  lines.push('生成时间：' + (planDate.value ? fmtTime(planDate.value) : '-'))
  lines.push('')
  lines.push('## 薄弱点诊断')
  lines.push(plan.value.weakness_diagnosis || '（无）')
  lines.push('')
  const path = plan.value.learning_path || []
  if (path.length) {
    lines.push('## 定制学习路径')
    path.forEach((st, i) => {
      lines.push(`${i + 1}. ${st.stage || ''}：${st.content || ''}`)
      if (st.exercises && st.exercises.length) lines.push('   建议练习：' + st.exercises.join('、'))
    })
    lines.push('')
  }
  const recs = plan.value.recommended_exercises || []
  if (recs.length) lines.push('## 推荐练习\n' + recs.map((r) => '- ' + r).join('\n') + '\n')
  const sugs = plan.value.suggestions || []
  if (sugs.length) lines.push('## 学习建议\n' + sugs.map((s) => '- ' + s).join('\n') + '\n')
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `学情分析报告_${new Date().toISOString().slice(0, 10)}.md`
  a.click()
  URL.revokeObjectURL(a.href)
}

// 阶段任务状态：未开始 / 进行中 / 已完成（本地交互，点击循环切换）
const stageStatus = reactive({})
const STAGE_STATUS = [
  { key: 'todo', label: '未开始', type: 'info' },
  { key: 'doing', label: '进行中', type: 'warning' },
  { key: 'done', label: '已完成', type: 'success' },
]
function stageStatusInfo(i) {
  const s = stageStatus[i] || 'todo'
  return STAGE_STATUS.find((x) => x.key === s) || STAGE_STATUS[0]
}
function cycleStageStatus(i) {
  const cur = stageStatus[i] || 'todo'
  const idx = STAGE_STATUS.findIndex((x) => x.key === cur)
  stageStatus[i] = STAGE_STATUS[(idx + 1) % STAGE_STATUS.length].key
}

let radar = null
let activity = null

async function loadStats(subject = statsSubject.value) {
  statsSubject.value = subject
  stats.value = await getMyStats(subject)
  renderCharts()
  loadActivity()
}

function renderCharts() {
  if (radar) radar.dispose()
  const radarEl = document.getElementById('radarChart')
  if (!radarEl) return
  radar = echarts.init(radarEl)
  // 知识点情况（mastery 已按掌握度升序），只展示薄弱优先的若干项，避免标签重叠
  const mastery = (stats.value.knowledge_mastery || [])
  const shown = mastery.slice(0, 8)
  const names = shown.map((m) => m.knowledge_point)
  if (!names.length) {
    radar.setOption({
      title: { text: '知识点掌握度', left: 8, textStyle: { fontSize: 15, fontWeight: 600, color: '#1A1A1A' } },
      tooltip: { trigger: 'item' },
      series: [],
      graphic: [{
        type: 'text', z: 100, left: 'center', top: 'middle',
        style: { text: '暂无知识点统计', fill: '#909399', fontSize: 14 }
      }]
    })
    return
  }
  const fullVals = shown.map((m) => m.mastery)
  const weakVals = selectWeakValues(fullVals)
  const latest = fullVals[0] !== undefined ? `最薄弱：${names[0]}（${fullVals[0]}%）` : ''
  radar.setOption({
    title: { text: '知识点掌握度', left: 8, textStyle: { fontSize: 15, fontWeight: 600, color: '#1A1A1A' } },
    tooltip: { trigger: 'item' },
    legend: {
      bottom: 0,
      data: [{ name: '整体掌握度', icon: 'roundRect' }, { name: '薄弱点高亮', icon: 'circle' }],
      selected: { '整体掌握度': true, '薄弱点高亮': false },
      textStyle: { fontSize: 12, color: '#606266' },
      left: 'center'
    },
    radar: {
      indicator: names.map((n) => ({ name: n, max: 100 })),
      radius: '58%',
      center: ['50%', '45%'],
      axisName: { color: '#4B5563', fontSize: 11 }
    },
    series: [
      {
        type: 'radar',
        name: '整体掌握度',
        symbolSize: 4,
        data: [{ value: fullVals, name: '整体掌握度' }],
        areaStyle: { color: 'rgba(139, 92, 246, 0.20)' },
        lineStyle: { color: '#8B5CF6', width: 2 },
        itemStyle: { color: '#8B5CF6' }
      },
      {
        type: 'radar',
        name: '薄弱点高亮',
        symbolSize: 8,
        symbol: 'circle',
        data: [{ value: weakVals, name: '薄弱点高亮', lineStyle: {} }],
        areaStyle: { color: 'rgba(239, 68, 68, 0.30)' },
        lineStyle: { color: '#EF4444', width: 2.5 },
        itemStyle: { color: '#EF4444', borderColor: '#fff', borderWidth: 2 }
      }
    ],
    graphic: latest
      ? [{ type: 'text', z: 100, left: 8, top: 40, style: { text: latest, fill: '#EF4444', fontSize: 12, fontWeight: 600 } }]
      : []
  })
}

// 活跃度趋势：日 / 周 / 月 切换
const actPeriod = ref('day')
const actItems = ref([])
async function loadActivity() {
  try {
    const res = await getMyActivity(actPeriod.value, statsSubject.value)
    actItems.value = (res && res.items) || []
  } catch (e) {
    actItems.value = []
  }
  renderActivity()
}
function renderActivity() {
  if (activity) activity.dispose()
  const activityEl = document.getElementById('activityChart')
  if (!activityEl) return
  activity = echarts.init(activityEl)
  const items = actItems.value
  const labels = items.map((i) => i.label)
  const values = items.map((i) => i.count)
  activity.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 20, top: 30, bottom: 40 },
    xAxis: {
      type: 'category',
      data: labels,
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#D0D5DD' } },
      axisLabel: { color: '#909399', fontSize: 11, rotate: labels.length > 10 ? 30 : 0 }
    },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#E9ECF2' } }, axisLabel: { color: '#909399' } },
    series: [{
      type: 'line', smooth: true,
      color: '#F97316',
      symbol: 'circle', symbolSize: 6,
      lineStyle: { width: 2.5 },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(249, 115, 22, 0.42)' }, { offset: 1, color: 'rgba(255, 255, 255, 0)' }]) },
      itemStyle: { color: '#F97316', borderColor: '#fff', borderWidth: 2 },
      data: values
    }]
  })
}
function resize() { radar?.resize(); activity?.resize() }

// 活跃度文字解读：比较最近两个时间片
const activityInsight = computed(() => {
  const items = actItems.value
  if (items.length < 2) return items.length ? '已开始记录学习活跃度，继续保持！' : '暂无活跃度数据'
  const last = items[items.length - 1].count
  const prev = items[items.length - 2].count
  const label = items[items.length - 1].label
  if (last > prev) return `周期「${label}」学习活跃度上升，继续保持！`
  if (last < prev) return `周期「${label}」活跃度略有回落，抽空多练几道题哦～`
  return '近段时间学习节奏稳定，坚持就是胜利！'
})

async function loadWrong() {
  wrongLoading.value = true
  try {
    const params = {}
    if (wrongSearch.value) params.knowledge_point = wrongSearch.value
    if (wrongSubject.value) params.subject = wrongSubject.value
    wrongItems.value = await getWrongBook(params)
  } catch (e) {
    wrongItems.value = []
  } finally {
    wrongLoading.value = false
  }
  wrongSelection.value = []
}

async function loadTimeline() {
  timelineLoading.value = true
  try {
    const params = {}
    if (timelineQuickFilter.value === '7d') {
      const d = new Date(); d.setDate(d.getDate() - 7)
      params.start = d.toISOString().slice(0, 10)
    } else if (timelineQuickFilter.value === '30d') {
      const d = new Date(); d.setDate(d.getDate() - 30)
      params.start = d.toISOString().slice(0, 10)
    }
    if (range.value && range.value.length === 2) { params.start = range.value[0]; params.end = range.value[1] }
    timeline.value = await getTimeline(params)
  } catch (e) {
    timeline.value = []
  } finally {
    timelineLoading.value = false
  }
}

async function removeWrong(id) {
  await deleteWrongBook(id)
  ElMessage.success('已删除')
  await loadWrong()
}

async function batchDeleteWrong() {
  if (!wrongSelection.value.length) { ElMessage.warning('请勾选要删除的错题'); return }
  await batchDeleteWrongBook(wrongSelection.value)
  ElMessage.success('批量删除成功')
  await loadWrong()
}

function exportWrong() {
  if (!wrongItems.value.length) { ElMessage.warning('暂无错题可导出'); return }
  const lines = ['科目,题目,答案,知识点,加入时间']
  wrongItems.value.forEach((w) => {
    const ex = w.exercise || {}
    const kps = (ex.knowledge_points || []).join(';')
    const content = (ex.content || '').replace(/,/g, '，')
    const answer = (ex.answer || '').replace(/,/g, '，')
    lines.push([w.subject || '', content, answer, kps, (w.created_at || '').slice(0, 10)].join(','))
  })
  const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `错题本_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}

function exportTimeline() {
  if (!timeline.value.length) { ElMessage.warning('暂无记录可导出'); return }
  const lines = ['时间,类型,标题,详情']
  timeline.value.forEach((t) => {
    const typeLabel = { exercise: '做题', question: '提问', collect: '收藏' }[t.type] || t.type
    lines.push([(t.time || '').slice(0, 16), typeLabel, (t.title || '').replace(/,/g, '，'), (t.detail || '').replace(/,/g, '，')].join(','))
  })
  const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `学习记录_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}

// 同类练：弹窗内逐题练习相似题
const similarPracticeDialog = ref(false)
const similarPracticeLoading = ref(false)
const similarPracticeItems = ref([])
const similarPracticeIndex = ref(0)
const similarPracticeAnswer = ref('')
const similarPracticeResult = ref(null)
const similarPracticeSubmitting = ref(false)
const similarPracticeResults = ref([])
const similarPracticeDone = ref(false)
const similarPracticeSource = ref(null)

const similarPracticeCurrent = computed(() => {
  const items = similarPracticeItems.value
  const idx = similarPracticeIndex.value
  return items.length ? items[idx] : null
})
const similarPracticeType = computed(() => {
  const ex = similarPracticeCurrent.value
  if (!ex) return 'qa'
  const k = typeKey(ex.type || '')
  if (k === 'qa' && (ex.options || []).length) return 'single'
  return k
})
const similarPracticeProgress = computed(() => {
  const total = similarPracticeItems.value.length
  const idx = similarPracticeIndex.value + 1
  return { idx, total, pct: total > 0 ? Math.round(idx / total * 100) : 0 }
})

async function openSimilarPractice(item) {
  similarPracticeSource.value = item
  similarPracticeItems.value = []
  similarPracticeIndex.value = 0
  similarPracticeAnswer.value = ''
  similarPracticeResult.value = null
  similarPracticeSubmitting.value = false
  similarPracticeResults.value = []
  similarPracticeDone.value = false
  similarPracticeLoading.value = true
  similarPracticeDialog.value = true

  const ex = item.exercise || {}
  try {
    const res = await getSimilarExercises(ex.id, 3)
    const items = (res && res.items) || []
    if (!items.length) {
      ElMessage.warning('暂无同类题，请稍后再试')
      similarPracticeDialog.value = false
      return
    }
    similarPracticeItems.value = items
    const genCount = res?.generated_count || 0
    if (items.length < 3 && genCount > 0) {
      ElMessage.info('同类题数量有限，已为你生成补充题目')
    }
  } catch (e) {
    ElMessage.error('获取同类题失败，请检查网络')
    similarPracticeDialog.value = false
  } finally {
    similarPracticeLoading.value = false
  }
}

function similarPracticePick(kind, key) {
  if (kind === 'single') { similarPracticeAnswer.value = key; return }
  if (kind === 'multiple') {
    const arr = Array.isArray(similarPracticeAnswer.value) ? [...similarPracticeAnswer.value] : []
    const i = arr.indexOf(key)
    if (i >= 0) arr.splice(i, 1); else arr.push(key)
    similarPracticeAnswer.value = arr
  }
}
function similarPracticeIsActive(kind, key) {
  if (kind === 'single') return similarPracticeAnswer.value === key
  if (kind === 'multiple') return Array.isArray(similarPracticeAnswer.value) && similarPracticeAnswer.value.includes(key)
  return false
}

async function similarPracticeSubmit() {
  if (similarPracticeSubmitting.value || similarPracticeResult.value !== null) return
  const ex = similarPracticeCurrent.value
  if (!ex) return
  similarPracticeSubmitting.value = true
  const ua = normalizePracticeAnswer(ex.type, similarPracticeAnswer.value)
  const isCorrect = isAnswerCorrect(ex.type, ua, ex.answer)
  similarPracticeResult.value = isCorrect
  try {
    await submitRecord({ exercise_id: ex.id, user_answer: ua, is_correct: isCorrect, duration_seconds: 30 })
    similarPracticeResults.value.push({ exercise_id: ex.id, is_correct: isCorrect, content: ex.content })
    if (!isCorrect && similarPracticeSource.value) {
      try {
        await addWrongBook({ exercise_id: ex.id, reason: '同类练习答错' })
      } catch (e) { /* 静默 */ }
    }
  } catch (e) {
    ElMessage.error('提交失败，请重试')
  } finally {
    similarPracticeSubmitting.value = false
  }
}

function similarPracticeNext() {
  const nextIdx = similarPracticeIndex.value + 1
  if (nextIdx >= similarPracticeItems.value.length) {
    similarPracticeDone.value = true
    return
  }
  similarPracticeIndex.value = nextIdx
  similarPracticeAnswer.value = ''
  similarPracticeResult.value = null
  similarPracticeSubmitting.value = false
}

function similarPracticeClose() {
  similarPracticeDialog.value = false
  if (similarPracticeSource.value) loadWrong()
}

// 点击学习记录跳转
function viewTimelineExercise(item) {
  // 从 timeline 中找到对应的 wrong item 或直接打开查看原题弹窗
  // 如果 timeline 的 type 是 exercise，用 exercise_id 打开
  if (item.type === 'exercise') {
    const wrong = wrongItems.value.find((w) => w.exercise_id === item.exercise_id)
    if (wrong) { viewWrong(wrong); return }
    // 不在错题本中时，用 exercise 数据构造一个只读对象
    currentWrong.value = {
      exercise: { content: item.title, options: [], answer: '', analysis: '', knowledge_points: [] },
      subject: item.subject || '',
    }
    wrongDialog.value = true
  } else if (item.type === 'question') {
    // AI 会话记录跳转
    router.push({ path: '/student/chat', query: { q: item.title } })
  }
}

function switchTab(t) {
  tab.value = t
  if (t === 'stats') nextTick(() => { renderCharts(); renderActivity() })
  if (t === 'wrong') { wrongSelection.value = []; loadWrong() }
  if (t === 'records') loadTimeline()
}

function fmtTime(t) {
  if (!t) return ''
  const d = new Date(t)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

const typeMeta = {
  exercise: { label: '做了题', color: '#6B8AFF', bg: '#EEF1FF' },
  question: { label: '问了问题', color: '#E8A838', bg: '#FFF8E7' },
  collect:  { label: '收藏错题', color: '#52B77D', bg: '#E8F7EF' }
}

// 科目颜色映射（用于错题本科目标签）
const SUBJECT_COLORS = {
  '语文': '#8B5CF6', '数学': '#2F6FED', '英语': '#D97706',
  '物理': '#059669', '化学': '#DC2626', '生物': '#16A34A',
  '政治': '#E11D48', '地理': '#0891B2', '历史': '#7C3AED',
  '体育': '#EA580C', '音乐': '#C026D3', '美术': '#DB2777', '劳动': '#65A30D'
}
function subjectColor(s) { return SUBJECT_COLORS[s] || '#8B5CF6' }

// 错题本查看原题与正确答案
const wrongDialog = ref(false)
const currentWrong = ref(null)
// 错题本答题交互状态
const wrongAnswer = ref('')
const wrongResult = ref(null)       // null: 未作答, true: 正确, false: 错误
const wrongSubmitting = ref(false)
const wrongSimilarList = ref([])    // 答错后展示相似题

// 错题本当前题型的归一化类型
const recalcWrongType = computed(() => {
  if (!currentWrong.value) return 'qa'
  const ex = currentWrong.value.exercise || {}
  const k = typeKey(ex.type || '')
  if (k === 'qa' && (ex.options || []).length) return 'single'
  return k
})

function viewWrong(row) {
  currentWrong.value = row
  wrongAnswer.value = ''
  wrongResult.value = null
  wrongSubmitting.value = false
  wrongSimilarList.value = []
  wrongDialog.value = true
}

// 提交错题本中的答案
async function submitWrongAnswer() {
  if (wrongSubmitting.value || wrongResult.value !== null || !currentWrong.value) return
  wrongSubmitting.value = true
  const ex = currentWrong.value.exercise || {}
  const ua = normalizePracticeAnswer(ex.type, wrongAnswer.value)
  const isCorrect = isAnswerCorrect(ex.type, ua, ex.answer)
  wrongResult.value = isCorrect
  try {
    await submitRecord({ exercise_id: ex.id, user_answer: ua, is_correct: isCorrect, duration_seconds: 30 })
    if (isCorrect) {
      // 答对：自动移出错题本
      await deleteWrongBook(currentWrong.value.id)
      ElMessage.success('回答正确，已自动移出错题本！')
      await loadWrong()
    } else {
      // 答错：加载相似题推荐
      await loadWrongSimilar()
    }
  } catch (e) {
    ElMessage.error('提交失败，请重试')
  } finally {
    wrongSubmitting.value = false
  }
}

// 加载错题相似题
async function loadWrongSimilar() {
  wrongSimilarList.value = []
  const ex = (currentWrong.value && currentWrong.value.exercise) || {}
  if (!ex.id) return
  try {
    const res = await getSimilarExercises(ex.id, 3)
    wrongSimilarList.value = (res && res.items) || []
  } catch (e) {
    wrongSimilarList.value = []
  }
}

// 点击错题本相似题，跳转至智能问答练习
function openWrongSimilar(ex) {
  if (!ex) return
  const kp = (ex.knowledge_points || []).join('、') || '巩固练习'
  router.push({
    path: '/student/chat',
    query: {
      q: `请出一道关于「${kp}」的题目，难度和题型与上次类似，让我巩固练习`,
      subject: currentWrong.value?.subject || undefined
    }
  })
}

function pickWrongOption(kind, key) {
  if (kind === 'single') { wrongAnswer.value = key; return }
  if (kind === 'multiple') {
    const arr = Array.isArray(wrongAnswer.value) ? [...wrongAnswer.value] : []
    const i = arr.indexOf(key)
    if (i >= 0) arr.splice(i, 1); else arr.push(key)
    wrongAnswer.value = arr
  }
}
function isWrongOptActive(kind, key) {
  if (kind === 'single') return wrongAnswer.value === key
  if (kind === 'multiple') return Array.isArray(wrongAnswer.value) && wrongAnswer.value.includes(key)
  return false
}

// 语音朗读生成的辅导方案
const speaking = ref(false)
function planToText() {
  if (!plan.value) return ''
  if (plan.value.message) return plan.value.message
  const parts = []
  if (plan.value.weakness_diagnosis) parts.push('薄弱点诊断：' + plan.value.weakness_diagnosis)
  const path = plan.value.learning_path || []
  if (path.length) {
    parts.push('学习路径：')
    path.forEach((st, i) => {
      let item = (i + 1) + '、' + (st.stage || '') + '：' + (st.content || '')
      if (st.exercises && st.exercises.length) item += '，建议练习：' + st.exercises.join('、')
      parts.push(item)
    })
  }
  const recs = plan.value.recommended_exercises || []
  if (recs.length) parts.push('推荐练习：' + recs.join('、'))
  const sugs = plan.value.suggestions || []
  if (sugs.length) parts.push('学习建议：' + sugs.join('、'))
  return parts.join('。')
}
function speakPlan() {
  if (!plan.value) { ElMessage.warning('请先生成辅导方案'); return }
  if (!('speechSynthesis' in window)) { ElMessage.warning('当前浏览器不支持语音朗读'); return }
  if (speaking.value) {
    window.speechSynthesis.cancel()
    speaking.value = false
    return
  }
  const text = planToText()
  if (!text) { ElMessage.warning('暂无可以朗读的内容'); return }
  const utter = new SpeechSynthesisUtterance(text)
  utter.lang = 'zh-CN'
  utter.rate = 1
  utter.onend = () => { speaking.value = false }
  utter.onerror = () => { speaking.value = false }
  window.speechSynthesis.speak(utter)
  speaking.value = true
}

// 回到顶部
const showTop = ref(false)
function onScroll() { showTop.value = window.scrollY > 480 }
function backTop() { window.scrollTo({ top: 0, behavior: 'smooth' }) }

// 学习统计四张卡片：统一白色卡片 + 马卡龙图标
const statCards = computed(() => [
  { label: '累计答题', value: String(stats.value.total_answered || 0), icon: 'Document', tone: 'violet' },
  { label: '答对题数', value: String(stats.value.correct_count || 0), icon: 'CircleCheck', tone: 'blue' },
  { label: '正确率', value: ((stats.value.accuracy || 0) * 100).toFixed(1) + '%', icon: 'TrendCharts', tone: 'amber' },
  { label: '涉及知识点', value: String((stats.value.knowledge_mastery || []).length), icon: 'Collection', tone: 'green' }
])

onMounted(() => {
  loadStats().catch((e) => console.warn('学习统计加载失败', e))
  loadLatestPlan()
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('resize', resize)
})
onBeforeUnmount(() => {
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
  window.removeEventListener('scroll', onScroll)
  window.removeEventListener('resize', resize)
  radar?.dispose(); activity?.dispose()
})
</script>

<template>
  <div>
    <!-- ================= AI 个性化学习辅导主卡 ================= -->
    <div class="page-card plan-card">
      <div class="plan-head">
        <div class="plan-head-left">
          <span class="info-icon-sm bg-icon-purple" style="width:44px; height:44px; font-size:22px; border-radius:12px">
            <el-icon><MagicStick /></el-icon>
          </span>
          <div>
            <h3 style="margin:0; font-size:18px; font-weight:700; color:#1A1A1A">个性化学习辅导（AI Agent）</h3>
            <div class="gray" style="margin-top:2px">基于你的学习记录，自动生成专属薄弱点诊断 + 定制学习路径</div>
          </div>
        </div>
        <div class="plan-head-actions">
          <el-select v-model="planSubject" placeholder="按科目" clearable size="default" style="width:130px" class="plan-subject">
            <el-option v-for="s in SUBJECTS" :key="s" :label="s" :value="s" />
          </el-select>
          <el-button size="default" :type="plan ? 'primary' : 'primary'" :class="plan ? 'btn-regenerate' : ''" :loading="generating" @click="genPlan">
            <el-icon style="margin-right:4px"><Promotion /></el-icon>
            {{ plan ? '重新生成方案' : '生成我的辅导方案' }}
          </el-button>
          <el-button v-if="plan && !plan.message" size="default" plain @click="exportPlan">
            <el-icon style="margin-right:4px"><Download /></el-icon>导出报告
          </el-button>
          <el-button size="default" :type="speaking ? 'warning' : 'default'" :disabled="!plan" @click="speakPlan">
            <el-icon style="margin-right:4px"><Microphone /></el-icon>
            {{ speaking ? '停止朗读' : '语音朗读' }}
          </el-button>
        </div>
      </div>

      <div v-loading="planLoading" style="margin-top: 18px">
        <div v-if="planLoading" class="plan-progress">
          <el-icon style="margin-right:6px; vertical-align:-2px"><Loading /></el-icon>
          {{ progressText }}
        </div>
        <template v-if="plan && !planLoading">
          <div class="plan-banner">
            <el-icon size="20"><CircleCheck /></el-icon>
            <div>
              <div class="plan-banner-title">方案已生成，请按阶段执行</div>
              <div v-if="planDate" class="plan-banner-sub">生成时间：{{ fmtTime(planDate) }} · 完成后可再次点击「重新生成方案」更新诊断</div>
            </div>
          </div>

          <div class="plan-section">
            <h4>📌 弱点诊断</h4>
            <p style="color:#303133; line-height:1.9">{{ plan.weakness_diagnosis }}</p>
          </div>

          <div class="plan-section">
            <h4>🗺 定制学习路径</h4>
            <el-timeline style="padding-left:4px">
              <el-timeline-item
                v-for="(st, i) in plan.learning_path || []"
                :key="i"
                placement="top"
                :color="['#8B5CF6','#2F6FED','#43B97F','#F97316','#722ED1'][i % 5]"
                :hollow="false"
              >
                <div class="stage-head">
                  <span class="stage-badge">{{ i + 1 }}</span>
                  <span class="stage-title">{{ st.stage }}</span>
                  <el-tag
                    size="small"
                    :type="stageStatusInfo(i).type"
                    effect="light"
                    class="stage-status"
                    style="cursor:pointer"
                    @click="cycleStageStatus(i)"
                  >{{ stageStatusInfo(i).label }}</el-tag>
                </div>
                <div class="stage-goal"><b>学习目标：</b>{{ st.content }}</div>
                <div v-if="st.exercises && st.exercises.length" class="stage-exercises">
                  <span class="stage-ex-label">建议练习：</span>
                  <el-button
                    v-for="ex in st.exercises"
                    :key="ex"
                    size="small"
                    class="ex-go-btn"
                    @click="toChat('请给我讲清楚「' + st.stage + '」' + (st.content || '') + '知识点，并结合建议练习「' + ex + '」出题巩固', { stage: st.stage, stageContent: st.content, weakPoints: plan?.weakness_diagnosis || '' })"
                  >{{ ex }}</el-button>
                </div>
              </el-timeline-item>
            </el-timeline>
          </div>

          <div class="plan-section">
            <h4>✏️ 推荐练习</h4>
            <div class="rec-box">
              <button
                v-for="(r, i) in plan.recommended_exercises || []"
                :key="i"
                class="rec-chip"
                @click="toChat('请为我搜集《' + r + '》的相关习题，以便我巩固掌握', { weakPoints: plan?.weakness_diagnosis || '' })"
              >{{ r }}<el-icon style="margin-left:4px"><Right /></el-icon></button>
              <span v-if="!plan.recommended_exercises?.length" class="gray">暂无推荐练习</span>
            </div>
          </div>

          <div class="plan-section">
            <h4>💡 学习建议（按优先级）</h4>
            <ul class="sug-list">
              <li v-for="(s, i) in plan.suggestions || []" :key="i" :class="{ first: i === 0 }">
                <span class="sug-dot" :style="{ background: i === 0 ? '#8B5CF6' : '#C7C7D1' }"></span>
                {{ s }}
              </li>
            </ul>
            <span v-if="!plan.suggestions?.length" class="gray">暂无学习建议</span>
          </div>
        </template>
        <el-empty v-else-if="!planLoading" description="点击上方按钮，生成你的专属个性化辅导方案" :image-size="80" />
      </div>
    </div>

    <!-- ================= Tabs：学习统计 / 错题本 / 学习记录 ================= -->
    <div class="page-card" style="margin-top: 16px">
      <el-tabs v-model="tab" @tab-change="switchTab" class="lp-tabs">
        <!-- -------- Tab 1: 学习统计 -------- -->
        <el-tab-pane label="学习统计" name="stats">
          <div class="stats-toolbar">
            <span class="sub-title" style="margin:0">按科目查看：</span>
            <el-select v-model="statsSubject" clearable placeholder="全部科目" size="default" style="width:130px" @change="loadStats($event || '')">
              <el-option v-for="s in SUBJECTS" :key="s" :label="s" :value="s" />
            </el-select>
          </div>
          <el-row :gutter="16">
            <el-col v-for="c in statCards" :key="c.label" :xs="12" :sm="12" :md="6">
              <div class="sc-card">
                <div class="sc-icon" :class="'sc-' + c.tone"><el-icon :size="18"><component :is="c.icon" /></el-icon></div>
                <div class="sc-body">
                  <span class="sc-num">{{ c.value }}</span>
                  <span class="sc-label">{{ c.label }}</span>
                </div>
              </div>
            </el-col>
          </el-row>
          <el-row :gutter="16" style="margin-top: 16px">
            <el-col :xs="24" :sm="24" :md="12"><div class="chart-box" id="radarChart" style="height: 340px"></div></el-col>
            <el-col :xs="24" :sm="24" :md="12">
              <div class="chart-toolbar">
                <span class="chart-title">学习活跃度趋势</span>
                <el-radio-group v-model="actPeriod" size="small" @change="loadActivity">
                  <el-radio-button value="day">日</el-radio-button>
                  <el-radio-button value="week">周</el-radio-button>
                  <el-radio-button value="month">月</el-radio-button>
                </el-radio-group>
              </div>
              <div class="chart-box" id="activityChart" style="height: 316px"></div>
              <div class="chart-insight"><el-icon style="margin-right:4px; color:#8B5CF6"><DataAnalysis /></el-icon>{{ activityInsight }}</div>
            </el-col>
          </el-row>
        </el-tab-pane>

        <!-- -------- Tab 2: 错题本（支持 hash #wrong） -------- -->
        <el-tab-pane label="错题本" name="wrong" id="wrong">
          <!-- 顶部工具栏 -->
          <div class="wrong-toolbar">
            <div class="wrong-toolbar-left">
              <span class="sub-title" style="margin:0">共 {{ wrongItems.length }} 道错题</span>
              <el-input v-model="wrongSearch" clearable placeholder="搜索知识点…" size="small" style="width:160px" @keyup.enter="loadWrong" @clear="loadWrong">
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
              <el-select v-model="wrongSubject" clearable placeholder="科目筛选" size="small" style="width:120px" @change="loadWrong">
                <el-option v-for="s in SUBJECTS" :key="s" :label="s" :value="s" />
              </el-select>
            </div>
            <div class="wrong-toolbar-right">
              <el-button size="small" plain :disabled="!wrongSelection.length" @click="batchDeleteWrong">
                <el-icon style="margin-right:4px"><Delete /></el-icon>批量删除 ({{ wrongSelection.length }})
              </el-button>
              <el-button v-if="wrongItems.length" size="small" plain @click="exportWrong">
                <el-icon style="margin-right:4px"><Download /></el-icon>导出 CSV
              </el-button>
            </div>
          </div>
          <!-- 错题表格 -->
          <el-table
            v-loading="wrongLoading"
            :data="wrongItems"
            stripe
            style="width: 100%"
            class="lp-table wrong-table"
            @selection-change="wrongSelection = $event.map((r) => r.id)"
          >
            <el-table-column type="selection" width="40" />
            <el-table-column label="科目" width="90">
              <template #default="{ row }">
                <span class="subject-tag" :style="{ background: subjectColor(row.subject) + '18', color: subjectColor(row.subject) }">{{ row.subject || '通用' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="题目" min-width="240">
              <template #default="{ row }">
                <div class="wrong-q-text">{{ row.exercise.content }}</div>
              </template>
            </el-table-column>
            <el-table-column label="难度" width="80" align="center">
              <template #default="{ row }">
                <span class="diff-tag" :class="'diff-' + (row.exercise.difficulty || 'medium')">{{ { easy: '基础', medium: '提高', hard: '拔高' }[row.exercise.difficulty] || '提高' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="知识点" min-width="120">
              <template #default="{ row }">
                <span class="kp-block">{{ (row.exercise.knowledge_points || []).slice(0, 2).join('、') || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="加入时间" width="160">
              <template #default="{ row }"><span class="gray">{{ fmtTime(row.created_at) }}</span></template>
            </el-table-column>
            <el-table-column label="操作" width="240" fixed="right">
              <template #default="{ row }">
                <div class="wrong-actions">
                  <el-button size="small" plain @click="viewWrong(row)"><el-icon style="margin-right:3px"><View /></el-icon>查看原题</el-button>
                  <el-button size="small" type="primary" plain @click="openSimilarPractice(row)"><el-icon style="margin-right:3px"><Refresh /></el-icon>刷同类</el-button>
                  <el-button size="small" text type="danger" @click="removeWrong(row.id)"><el-icon><Delete /></el-icon></el-button>
                </div>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无错题，多多练习，错题将会收集在这里" :image-size="70" />
            </template>
          </el-table>

          <!-- 查看原题弹窗 -->
          <el-dialog v-model="wrongDialog" title="原题重做" width="640px" class="wrong-detail-dialog" :close-on-click-modal="true" @keydown.esc="wrongDialog = false">
            <template v-if="currentWrong">
              <div class="wd-content">
                <div class="wd-meta-row" v-if="currentWrong.subject || (currentWrong.exercise.knowledge_points || []).length">
                  <span class="subject-tag" v-if="currentWrong.subject" :style="{ background: subjectColor(currentWrong.subject) + '18', color: subjectColor(currentWrong.subject) }">{{ currentWrong.subject }}</span>
                  <el-tag v-for="kp in currentWrong.exercise.knowledge_points" :key="kp" size="small" class="kp-tag">{{ kp }}</el-tag>
                </div>
                <div class="wd-section"><div class="wd-label">题目</div><div class="wd-text">{{ currentWrong.exercise.content }}</div></div>
                <div v-if="(currentWrong.exercise.options || []).length" class="wd-section">
                  <div class="wd-label">选项</div>
                  <div class="wd-options">
                    <div v-for="o in currentWrong.exercise.options" :key="o.key || o.text" class="wd-opt-item">
                      <span class="wd-opt-key">{{ o.key || '?' }}</span>
                      <span class="wd-opt-text">{{ o.text || o }}</span>
                    </div>
                  </div>
                </div>

                <!-- 答题交互区域 -->
                <div class="wd-section" v-if="wrongResult === null">
                  <div class="wd-label">你的答案</div>
                  <template v-if="recalcWrongType === 'single' || recalcWrongType === 'multiple'">
                    <div class="wrong-opt-grid">
                      <button
                        v-for="(o, i) in (currentWrong.exercise.options || [])"
                        :key="o.key || i"
                        type="button"
                        class="wrong-opt-btn"
                        :class="{ active: isWrongOptActive(recalcWrongType, o.key || 'ABCD'[i]) }"
                        @click="pickWrongOption(recalcWrongType, o.key || 'ABCD'[i])"
                      >{{ o.key || 'ABCD'[i] }}</button>
                    </div>
                  </template>
                  <template v-else-if="recalcWrongType === 'judge'">
                    <div class="wrong-opt-grid" style="grid-template-columns: repeat(2, 1fr)">
                      <button type="button" class="wrong-opt-btn" :class="{ active: wrongAnswer === '对' }" @click="wrongAnswer = '对'">✓ 对</button>
                      <button type="button" class="wrong-opt-btn" :class="{ active: wrongAnswer === '错' }" @click="wrongAnswer = '错'">✗ 错</button>
                    </div>
                  </template>
                  <template v-else-if="recalcWrongType === 'fill'">
                    <el-input v-model="wrongAnswer" placeholder="请输入答案文本" class="ex-input" @keyup.enter.prevent="submitWrongAnswer" />
                  </template>
                  <template v-else>
                    <el-input v-model="wrongAnswer" type="textarea" :rows="3" placeholder="请输入你的答案" />
                  </template>
                </div>

                <!-- 答题结果 -->
                <div v-if="wrongResult !== null" class="wrong-result" :class="wrongResult ? 'ok' : 'no'">
                  <el-icon :size="18" v-if="wrongResult"><CircleCheck /></el-icon>
                  <el-icon :size="18" v-else><CircleClose /></el-icon>
                  <span>{{ wrongResult ? '回答正确，已自动移出错题本！' : '回答错误，查看下方解析理解错因' }}</span>
                </div>
                <div v-if="wrongResult !== null" class="wd-section">
                  <div class="wd-label">正确答案</div>
                  <div style="text-align:left; width:100%">
                    <el-tag size="small" type="success" effect="light" style="font-weight:600">{{ currentWrong.exercise.answer }}</el-tag>
                  </div>
                </div>
                <div v-if="wrongResult !== null && currentWrong.exercise.analysis" class="wd-section">
                  <div class="wd-label">解析</div>
                  <div class="wd-analysis">{{ currentWrong.exercise.analysis }}</div>
                </div>
                <div v-if="currentWrong.reason" class="wd-section">
                  <div class="wd-label">错因</div>
                  <el-tag size="small" type="danger" effect="light">{{ currentWrong.reason }}</el-tag>
                </div>

                <!-- 答错后推荐相似题 -->
                <div v-if="wrongResult === false && wrongSimilarList.length" class="similar-box">
                  <div class="similar-title"><el-icon style="margin-right:4px; color:#8B5CF6"><Lightning /></el-icon>举一反三：推荐相似题</div>
                  <div class="similar-items">
                    <div
                      v-for="(s, i) in wrongSimilarList"
                      :key="i"
                      class="similar-item clickable"
                      @click="openWrongSimilar(s)"
                    >
                      <span class="similar-num">{{ i + 1 }}</span>
                      <span class="similar-text">{{ s.content?.slice(0, 60) }}{{ (s.content || '').length > 60 ? '…' : '' }}</span>
                      <el-icon class="similar-arrow"><Right /></el-icon>
                    </div>
                  </div>
                  <div class="similar-tip">点击相似题可跳转至智能问答练习，也可前往「AI 出题练习」做更多巩固</div>
                </div>
                <div v-if="wrongResult === false && !wrongSimilarList.length" class="similar-box">
                  <div class="similar-tip"><el-icon style="margin-right:4px; color:#8B5CF6"><InfoFilled /></el-icon>暂无相似例题，建议先巩固本章知识点，或前往智能问答「AI 出题练习」多练变式题</div>
                </div>
              </div>
            </template>
            <template #footer>
              <div class="wd-footer">
                <el-button size="default" @click="wrongDialog = false">关闭</el-button>
                <el-button
                  v-if="wrongResult === null"
                  size="default"
                  type="primary"
                  :disabled="!wrongAnswer || (Array.isArray(wrongAnswer) && !wrongAnswer.length) || wrongSubmitting"
                  :loading="wrongSubmitting"
                  @click="submitWrongAnswer"
                >提交答案</el-button>
                <el-button v-if="wrongResult !== null" size="default" type="primary" @click="wrongDialog = false">完成</el-button>
              </div>
            </template>
          </el-dialog>

          <!-- 同类练弹窗 -->
          <el-dialog v-model="similarPracticeDialog" :title="similarPracticeDone ? '同类练习总结' : '同类练习'" width="640px" class="sp-dialog" :close-on-click-modal="false" :before-close="similarPracticeClose">
            <!-- 加载骨架屏 -->
            <div v-if="similarPracticeLoading" class="sp-loading">
              <el-icon class="sp-loading-icon" :size="36"><Loading /></el-icon>
              <div class="sp-loading-text">正在为你匹配同类题目...</div>
            </div>

            <!-- 完成总结 -->
            <div v-else-if="similarPracticeDone" class="sp-summary">
              <div class="sp-summary-icon">
                <el-icon :size="48" style="color:#8B5CF6"><CircleCheckFilled /></el-icon>
              </div>
              <div class="sp-summary-title">同类练习完成！</div>
              <div class="sp-summary-stats">
                <div class="sp-stat-item">
                  <span class="sp-stat-num correct">{{ similarPracticeResults.filter(r => r.is_correct).length }}</span>
                  <span class="sp-stat-label">答对</span>
                </div>
                <div class="sp-stat-divider"></div>
                <div class="sp-stat-item">
                  <span class="sp-stat-num wrong">{{ similarPracticeResults.filter(r => !r.is_correct).length }}</span>
                  <span class="sp-stat-label">答错</span>
                </div>
                <div class="sp-stat-divider"></div>
                <div class="sp-stat-item">
                  <span class="sp-stat-num total">{{ similarPracticeResults.length }}</span>
                  <span class="sp-stat-label">总题数</span>
                </div>
              </div>
              <div class="sp-summary-bar-wrap">
                <div class="sp-summary-bar">
                  <div class="sp-summary-bar-fill" :style="{ width: (similarPracticeResults.filter(r => r.is_correct).length / Math.max(similarPracticeResults.length, 1) * 100) + '%' }"></div>
                </div>
                <span class="sp-summary-pct">{{ (similarPracticeResults.filter(r => r.is_correct).length / Math.max(similarPracticeResults.length, 1) * 100).toFixed(0) }}%</span>
              </div>
              <div class="sp-summary-actions">
                <el-button type="primary" @click="openSimilarPractice(similarPracticeSource)"><el-icon style="margin-right:4px"><Refresh /></el-icon>再来一组</el-button>
                <el-button plain @click="similarPracticeDialog = false">关闭</el-button>
              </div>
            </div>

            <!-- 逐题答题区域 -->
            <div v-else-if="similarPracticeCurrent" class="sp-practice-body">
              <div class="sp-header">
                <div class="sp-progress-bar">
                  <div class="sp-progress-fill" :style="{ width: similarPracticeProgress.pct + '%' }"></div>
                </div>
                <span class="sp-progress-text">{{ similarPracticeProgress.idx }} / {{ similarPracticeProgress.total }}</span>
              </div>
              <div class="sp-content">
                <div class="sp-meta">
                  <el-tag v-for="kp in (similarPracticeCurrent.knowledge_points || []).slice(0, 2)" :key="kp" size="small" class="kp-tag">{{ kp }}</el-tag>
                  <el-tag v-if="similarPracticeCurrent.generated" size="small" type="warning" effect="light">AI 生成</el-tag>
                </div>
                <div class="sp-question">{{ similarPracticeCurrent.content }}</div>
                <div v-if="(similarPracticeCurrent.options || []).length" class="sp-options">
                  <div v-for="o in similarPracticeCurrent.options" :key="o.key || o.text" class="sp-opt-item">
                    <span class="sp-opt-key">{{ o.key || '?' }}</span>
                    <span class="sp-opt-text">{{ o.text || o }}</span>
                  </div>
                </div>
                <div class="sp-answer-section" v-if="similarPracticeResult === null">
                  <div class="sp-answer-label">请作答</div>
                  <template v-if="similarPracticeType === 'single' || similarPracticeType === 'multiple'">
                    <div class="sp-opt-grid">
                      <button v-for="(o, i) in (similarPracticeCurrent.options || [])" :key="o.key || i" type="button" class="sp-opt-btn" :class="{ active: similarPracticeIsActive(similarPracticeType, o.key || 'ABCD'[i]) }" @click="similarPracticePick(similarPracticeType, o.key || 'ABCD'[i])">{{ o.key || 'ABCD'[i] }}</button>
                    </div>
                  </template>
                  <template v-else-if="similarPracticeType === 'judge'">
                    <div class="sp-opt-grid" style="grid-template-columns: repeat(2, 1fr)">
                      <button type="button" class="sp-opt-btn" :class="{ active: similarPracticeAnswer === '对' }" @click="similarPracticeAnswer = '对'">✓ 对</button>
                      <button type="button" class="sp-opt-btn" :class="{ active: similarPracticeAnswer === '错' }" @click="similarPracticeAnswer = '错'">✗ 错</button>
                    </div>
                  </template>
                  <template v-else-if="similarPracticeType === 'fill'">
                    <el-input v-model="similarPracticeAnswer" placeholder="请输入答案" class="sp-input" @keyup.enter.prevent="similarPracticeSubmit" />
                  </template>
                  <template v-else>
                    <el-input v-model="similarPracticeAnswer" type="textarea" :rows="3" placeholder="请输入你的答案" />
                  </template>
                </div>
                <div v-if="similarPracticeResult === true" class="sp-result ok">
                  <el-icon :size="18"><CircleCheck /></el-icon><span>✔ 回答正确！</span>
                </div>
                <div v-else-if="similarPracticeResult === false" class="sp-result no">
                  <el-icon :size="18"><CircleClose /></el-icon><span>✘ 回答错误</span>
                </div>
                <div v-if="similarPracticeResult === false && similarPracticeCurrent.analysis" class="sp-analysis">
                  <div class="sp-analysis-label">解析</div>
                  <div class="sp-analysis-text">{{ similarPracticeCurrent.analysis }}</div>
                </div>
              </div>
            </div>
            <el-empty v-else description="暂无同类题" :image-size="70" />

            <template #footer>
              <div class="sp-footer" v-if="similarPracticeCurrent && !similarPracticeDone">
                <el-button plain @click="similarPracticeClose">退出练习</el-button>
                <el-button v-if="similarPracticeResult === null" type="primary" :disabled="!similarPracticeAnswer || (Array.isArray(similarPracticeAnswer) && !similarPracticeAnswer.length)" :loading="similarPracticeSubmitting" @click="similarPracticeSubmit">提交答案</el-button>
                <el-button v-else type="primary" @click="similarPracticeNext">{{ similarPracticeProgress.idx >= similarPracticeProgress.total ? '查看总结' : '下一题' }}<el-icon style="margin-left:4px"><Right /></el-icon></el-button>
              </div>
            </template>
          </el-dialog>
        </el-tab-pane>

        <!-- -------- Tab 3: 学习记录 -------- -->
        <el-tab-pane label="学习记录" name="records" id="records">
          <!-- 图例说明 -->
          <div class="tl-legend" v-if="timelineLegend">
            <span class="tl-legend-title">类型图例：</span>
            <span v-for="(m, key) in typeMeta" :key="key" class="tl-legend-dot">
              <span class="tl-dot" :style="{ background: m.color }"></span>{{ m.label }}
            </span>
          </div>
          <!-- 筛选栏 -->
          <div class="tl-filter">
            <span class="sub-title" style="margin:0">时间范围：</span>
            <el-radio-group v-model="timelineQuickFilter" size="small" @change="range = []; loadTimeline()">
              <el-radio-button value="">全部</el-radio-button>
              <el-radio-button value="7d">近 7 天</el-radio-button>
              <el-radio-button value="30d">近 30 天</el-radio-button>
            </el-radio-group>
            <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" range-separator="至"
              start-placeholder="开始日期" end-placeholder="结束日期" size="small" style="width:240px"
              @change="timelineQuickFilter = ''; loadTimeline()" />
            <el-button v-if="timeline.length" size="small" plain @click="exportTimeline">
              <el-icon style="margin-right:4px"><Download /></el-icon>导出
            </el-button>
          </div>
          <!-- 时间线 -->
          <div v-loading="timelineLoading" class="tl-wrap">
            <el-timeline style="padding-left: 6px">
              <el-timeline-item
                v-for="(item, i) in timeline" :key="i"
                :timestamp="fmtTime(item.time)" :color="typeMeta[item.type]?.color || '#8B5CF6'" placement="top"
              >
                <div class="tl-item">
                  <div class="tl-head">
                    <span class="tl-type-tag" :style="{ background: (typeMeta[item.type]?.bg || '#F0F2F5'), color: (typeMeta[item.type]?.color || '#606266') }">
                      {{ typeMeta[item.type]?.label }}
                    </span>
                    <span class="tl-title" :class="{ clickable: item.type === 'exercise' || item.type === 'question' }" @click="viewTimelineExercise(item)">{{ item.title }}</span>
                    <span v-if="item.type === 'exercise'" class="tl-result" :class="item.is_correct ? 'result-right' : 'result-wrong'">
                      {{ item.is_correct ? '✓ 正确' : '✗ 错误' }}
                    </span>
                  </div>
                  <div class="gray" style="margin-top:3px; font-size:13px">{{ item.detail }}</div>
                </div>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-if="!timeline.length && !timelineLoading" description="暂无学习记录，快去答题吧" :image-size="70" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 回到顶部 -->
    <transition name="fade">
      <el-button v-show="showTop" class="back-top" circle @click="backTop">
        <el-icon><Top /></el-icon>
      </el-button>
    </transition>
  </div>
</template>

<style scoped>
/* 小图标容器装饰 */
.info-icon-sm { display: inline-flex; align-items: center; justify-content: center; }

/* 顶部卡片头 */
.plan-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.plan-head-left { display: flex; align-items: center; gap: 12px; }
.plan-head-actions { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.plan-subject :deep(.el-select__wrapper) { border-radius: 10px; }
.plan-head-actions .el-button { border-radius: 10px; height: 36px; }
.plan-head-actions .btn-regenerate { background: #F5F3FF; border-color: #DDD6FE; color: #7C3AED; }
.plan-head-actions .btn-regenerate:hover { background: #EDE9FE; border-color: #C4B5FD; color: #6D28D9; }
.plan-head-actions .is-weak { opacity: .62; }

/* 顶部状态横幅（提高视觉权重） */
.plan-banner {
  display: flex; align-items: center; gap: 12px;
  background: linear-gradient(90deg, #F0FDF4, #ECFDF5);
  border: 1px solid #C6F6D5;
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 16px;
  color: #15803D;
}
.plan-banner-title { font-size: 15px; font-weight: 700; }
.plan-banner-sub { font-size: 12px; color: #4B7E5F; margin-top: 2px; }

.plan-section h4 { margin: 18px 0 10px; font-size: 15px; font-weight: 700; color: #1A1A1A; }

/* 阶段路径：标题/学习目标/建议练习 三层级 */
.stage-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.stage-badge {
  width: 22px; height: 22px; border-radius: 50%;
  background: #8B5CF6; color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; flex-shrink: 0;
}
.stage-title { font-size: 15px; font-weight: 700; color: #1A1A1A; }
.stage-status { margin-left: auto; }
.stage-goal { color: #4b5563; line-height: 1.75; margin-bottom: 8px; }
.stage-exercises { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.stage-ex-label { font-size: 13px; color: #909399; flex-shrink: 0; }
.ex-go-btn {
  border-radius: 8px; height: 26px; padding: 0 12px;
  color: #7C3AED; border-color: #DDD6FE; background: #F5F3FF;
}
.ex-go-btn:hover, .ex-go-btn:focus { background: #EDE9FE; border-color: #8B5CF6; color: #6D28D9; }

/* 推荐练习：流式可点击标签 */
.rec-box { display: flex; flex-wrap: wrap; gap: 10px; }
.rec-chip {
  display: inline-flex; align-items: center;
  border: 1px solid #FCE7BF; background: #FFF7E6;
  border-radius: 999px; padding: 6px 14px;
  font-size: 13px; color: #9A6B00; cursor: pointer;
  transition: all .15s;
}
.rec-chip:hover { background: #FDE9BF; border-color: #F6C563; transform: translateY(-1px); }

/* 学习建议（优先级） */
.sug-list { list-style: none; padding: 0; margin: 0; }
.sug-list li { display: flex; gap: 8px; align-items: flex-start; line-height: 1.8; color: #303133; }
.sug-list li.first { font-weight: 600; color: #1A1A1A; }
.sug-dot { width: 8px; height: 8px; margin-top: 10px; border-radius: 50%; flex-shrink: 0; }

/* 学习统计工具栏 */
.stats-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }

/* 统计数据卡片：清新简约风格 */
.sc-card {
  display: flex; align-items: center; gap: 12px;
  background: #fff; border-radius: 14px;
  box-shadow: 0 4px 14px rgba(0,0,0,0.04);
  border: 1px solid #F0F2F5;
  padding: 16px 14px; margin-bottom: 8px;
}
.sc-icon {
  width: 42px; height: 42px; border-radius: 10px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
}
.sc-violet { background: #F5F0FF; color: #8B5CF6; }
.sc-blue { background: #EFF4FF; color: #3B82F6; }
.sc-amber { background: #FFFAEB; color: #F59E0B; }
.sc-green { background: #ECFDF5; color: #10B981; }
.sc-body { display: flex; flex-direction: column; gap: 0; }
.sc-num { font-size: 22px; font-weight: 700; color: #1A1A1A; line-height: 1.2; }
.sc-label { font-size: 13px; color: #909399; line-height: 1.4; }

/* 图表卡片 */
.chart-box {
  background: #FAFBFC; border: 1px solid #F0F2F5; border-radius: 12px; padding: 6px;
}
.chart-toolbar {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  margin-bottom: 8px; padding: 0 2px; flex-wrap: wrap;
}
.chart-title {
  font-size: 14px; font-weight: 600; color: #1A1A1A;
}
.chart-toolbar :deep(.el-radio-button__inner) {
  border-radius: 8px;
}
.chart-toolbar :deep(.el-radio-button:first-child) .el-radio-button__inner { border-radius: 8px 0 0 8px; }
.chart-toolbar :deep(.el-radio-button:last-child) .el-radio-button__inner { border-radius: 0 8px 8px 0; }
.chart-insight {
  display: flex; align-items: center; gap: 4px;
  margin-top: 10px; padding: 10px 14px;
  background: #F6F5FF; color: #5B557A;
  border-radius: 10px; font-size: 13px;
}

/* Tabs 视觉微调 */
.lp-tabs :deep(.el-tabs__item) { font-size: 15px; font-weight: 500; height: 44px; line-height: 44px; }
.lp-tabs :deep(.el-tabs__active-bar) { background-color: #8B5CF6; height: 2px; }
.lp-tabs :deep(.el-tabs__item.is-active) { color: #7C3AED; font-weight: 600; }
.lp-tabs :deep(.el-tabs__nav-wrap::after) { background-color: #D0D5DD; height: 1px; }
.lp-table :deep(.el-table__header th) { font-weight: 600; }

/* 回到顶部 */
.back-top { position: fixed; right: 28px; bottom: 40px; z-index: 50; }
.fade-enter-active, .fade-leave-active { transition: opacity .25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* ==================== 错题本 ==================== */
.wrong-toolbar {
  display: flex; justify-content: space-between; align-items: center; gap: 10px;
  margin-bottom: 12px; flex-wrap: wrap;
}
.wrong-toolbar-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.wrong-toolbar-right { display: flex; align-items: center; gap: 8px; }
.wrong-table :deep(.el-table__header th) { font-weight: 600; color: #1A1A1A; }
.wrong-table :deep(.el-table__row) { transition: background .12s; }
.wrong-table :deep(.el-table__row:hover) { background: #F9F7FF !important; }
.wrong-table :deep(.el-table__body tr.el-table__row--striped:hover) { background: #F9F7FF !important; }
/* 题目文本 */
.wrong-q-text {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  line-height: 1.6; color: #303133; font-size: 13px;
}
.wrong-kp-row { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.kp-tag {
  background: #F3E8FF !important; color: #7C3AED !important;
  border: none !important; border-radius: 6px; padding: 0 8px; line-height: 22px; font-size: 11px;
}
.kp-more { font-size: 11px; color: #909399; line-height: 22px; }
/* 科目标签 */
.subject-tag {
  display: inline-block; padding: 0 10px; line-height: 24px;
  border-radius: 8px; font-size: 12px; font-weight: 500;
}
/* 难度标签 */
.diff-tag {
  display: inline-block; padding: 0 10px; line-height: 24px;
  border-radius: 8px; font-size: 12px; font-weight: 500; text-align: center;
}
.diff-easy { background: #ECFDF5; color: #059669; }
.diff-medium { background: #FEF3C7; color: #D97706; }
.diff-hard { background: #FEE2E2; color: #DC2626; }
/* 知识点块 */
.kp-block { background: #F3E8FF; color: #7C3AED; padding: 0 10px; line-height: 24px; border-radius: 8px; font-size: 12px; display: inline-block; }
/* 错题操作栏 */
.wrong-actions { display: flex; align-items: center; gap: 4px; }
.wrong-actions .el-button { border-radius: 8px; height: 28px; padding: 0 8px; font-size: 12px; }
/* 空状态 */
.wrong-table :deep(.el-empty) { padding: 32px 0; }

/* 查看原题弹窗 */
.wrong-detail-dialog :deep(.el-dialog__body) { padding: 16px 24px; }
.wd-content { display: flex; flex-direction: column; gap: 14px; }
.wd-meta-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }
.wd-section { display: flex; flex-direction: column; gap: 6px; padding: 8px 0; border-bottom: 1px dashed #EEF1F4; }
.wd-section:last-child { border-bottom: none; }
.wd-label { font-weight: 600; color: #1A1A1A; font-size: 13px; }
.wd-text { color: #303133; line-height: 1.8; font-size: 14px; }
.wd-options { display: flex; flex-direction: column; gap: 6px; }
.wd-opt-item { display: flex; align-items: baseline; gap: 8px; padding: 4px 8px; background: #F8F9FB; border-radius: 8px; }
.wd-opt-key { font-weight: 700; color: #8B5CF6; width: 22px; font-size: 14px; text-align: center; }
.wd-opt-text { color: #303133; line-height: 1.6; }
.wd-analysis { color: #606266; line-height: 1.9; font-size: 13px; white-space: pre-wrap; }
.wd-footer { display: flex; justify-content: flex-end; gap: 10px; }
.wd-footer .el-button { border-radius: 10px; height: 36px; }

/* 错题本答题交互 */
.wrong-opt-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-top: 4px;
}
.wrong-opt-btn {
  height: 40px;
  border: 1px solid #E3E6EB;
  border-radius: 10px;
  background: #F8F9FB;
  color: #4b5563;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s;
  outline: none;
}
.wrong-opt-btn:hover { border-color: #8B5CF6; color: #8B5CF6; }
.wrong-opt-btn.active {
  background: #8B5CF6;
  border-color: #8B5CF6;
  color: #fff;
}
.wrong-result {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  border-radius: 10px;
  font-weight: 600;
  margin: 4px 0;
}
.wrong-result.ok { background: #ECF8F1; color: #2E9E6B; border: 1px solid #B7E4C7; }
.wrong-result.no { background: #FDECEC; color: #E04A4A; border: 1px solid #F5B7B7; }
.similar-box {
  margin-top: 8px;
  padding: 12px 14px;
  background: #F8F9FB;
  border-radius: 10px;
  border: 1px solid #EEF1F5;
}
.similar-title {
  font-weight: 600;
  font-size: 14px;
  color: #1A1A1A;
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}
.similar-items { display: flex; flex-direction: column; gap: 8px; }
.similar-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 8px;
  background: #fff;
  border-radius: 8px;
}
.similar-num {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #8B5CF6;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}
.similar-text { color: #303133; font-size: 13px; line-height: 1.6; }
.similar-item.clickable { cursor: pointer; transition: background .15s, border-color .15s; border: 1px solid transparent; }
.similar-item.clickable:hover { background: #F5F3FF; border-color: #DDD6FE; }
.similar-item.clickable:hover .similar-text { color: #6D28D9; }
.similar-arrow { color: #C7C7D1; font-size: 14px; flex-shrink: 0; margin-left: auto; transition: color .15s; }
.similar-item.clickable:hover .similar-arrow { color: #8B5CF6; }
.similar-tip { color: #909399; font-size: 12px; margin-top: 8px; line-height: 1.5; display: flex; align-items: center; gap: 4px; }

/* ==================== 学习记录 ==================== */
.tl-legend { display: flex; align-items: center; gap: 14px; margin-bottom: 12px; flex-wrap: wrap; font-size: 13px; }
.tl-legend-title { color: #909399; font-size: 12px; }
.tl-legend-dot { display: inline-flex; align-items: center; gap: 4px; color: #606266; }
.tl-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.tl-filter { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.tl-filter .el-radio-button__inner { border-radius: 8px; }
.tl-filter .el-radio-button:first-child .el-radio-button__inner { border-radius: 8px 0 0 8px; }
.tl-filter .el-radio-button:last-child .el-radio-button__inner { border-radius: 0 8px 8px 0; }
.tl-wrap { min-height: 100px; }
/* 时间线 item */
.tl-item { line-height: 1.65; }
.tl-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tl-type-tag {
  display: inline-block; padding: 0 10px; line-height: 24px;
  border-radius: 8px; font-size: 12px; font-weight: 500; border: none; flex-shrink: 0;
}
.tl-title { color: #303133; font-weight: 500; font-size: 14px; max-width: 420px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tl-title.clickable { cursor: pointer; transition: color .15s; }
.tl-title.clickable:hover { color: #8B5CF6; text-decoration: underline; }
.tl-result { display: inline-block; padding: 0 8px; line-height: 22px; border-radius: 6px; font-size: 11px; font-weight: 600; flex-shrink: 0; }
.result-right { background: #ECFDF5; color: #059669; }
.result-wrong { background: #FEF2F2; color: #DC2626; }

/* ==================== 同类练弹窗 ==================== */
.sp-dialog :deep(.el-dialog__body) { padding: 16px 24px 0; }
.sp-dialog :deep(.el-dialog__footer) { padding: 12px 24px 16px; }
.sp-loading { display: flex; flex-direction: column; align-items: center; padding: 60px 0; gap: 14px; }
.sp-loading-icon { animation: spin 1s linear infinite; color: #8B5CF6; }
@keyframes spin { 100% { transform: rotate(360deg); } }
.sp-loading-text { color: #606266; font-size: 14px; }
.sp-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.sp-progress-bar { flex: 1; height: 6px; background: #F0F2F5; border-radius: 3px; overflow: hidden; }
.sp-progress-fill { height: 100%; background: linear-gradient(90deg, #8B5CF6, #A78BFA); border-radius: 3px; transition: width .3s; }
.sp-progress-text { color: #909399; font-size: 13px; font-weight: 600; white-space: nowrap; }
.sp-content { display: flex; flex-direction: column; gap: 14px; }
.sp-meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.sp-question { color: #1A1A1A; font-size: 15px; line-height: 1.9; font-weight: 500; }
.sp-options { display: flex; flex-direction: column; gap: 6px; }
.sp-opt-item { display: flex; align-items: baseline; gap: 8px; padding: 4px 8px; background: #F8F9FB; border-radius: 8px; }
.sp-opt-key { font-weight: 700; color: #8B5CF6; width: 22px; font-size: 14px; text-align: center; }
.sp-opt-text { color: #303133; line-height: 1.6; }
.sp-answer-section { padding: 10px 0; border-top: 1px dashed #EEF1F4; }
.sp-answer-label { font-weight: 600; color: #1A1A1A; font-size: 13px; margin-bottom: 8px; }
.sp-opt-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.sp-opt-btn { height: 40px; border: 1px solid #E3E6EB; border-radius: 10px; background: #F8F9FB; color: #4b5563; font-size: 15px; font-weight: 600; cursor: pointer; transition: all .15s; outline: none; }
.sp-opt-btn:hover { border-color: #8B5CF6; color: #8B5CF6; }
.sp-opt-btn.active { background: #8B5CF6; border-color: #8B5CF6; color: #fff; }
.sp-input { margin-top: 4px; }
.sp-input :deep(.el-input__wrapper) { border-radius: 10px; }
.sp-result { display: flex; align-items: center; gap: 6px; padding: 10px 14px; border-radius: 10px; font-weight: 600; font-size: 14px; }
.sp-result.ok { background: #ECF8F1; color: #2E9E6B; border: 1px solid #B7E4C7; }
.sp-result.no { background: #FDECEC; color: #E04A4A; border: 1px solid #F5B7B7; }
.sp-analysis { padding: 10px 14px; background: #F8F9FB; border-radius: 10px; border: 1px solid #EEF1F5; }
.sp-analysis-label { font-weight: 600; color: #1A1A1A; font-size: 13px; margin-bottom: 4px; }
.sp-analysis-text { color: #606266; line-height: 1.8; font-size: 13px; white-space: pre-wrap; }
.sp-footer { display: flex; justify-content: flex-end; gap: 10px; }
.sp-footer .el-button { border-radius: 10px; height: 36px; }
.sp-summary { display: flex; flex-direction: column; align-items: center; padding: 30px 20px 10px; gap: 18px; }
.sp-summary-icon { margin-bottom: 4px; }
.sp-summary-title { font-size: 20px; font-weight: 700; color: #1A1A1A; }
.sp-summary-stats { display: flex; align-items: center; gap: 24px; }
.sp-stat-item { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.sp-stat-num { font-size: 28px; font-weight: 800; }
.sp-stat-num.correct { color: #2E9E6B; }
.sp-stat-num.wrong { color: #E04A4A; }
.sp-stat-num.total { color: #8B5CF6; }
.sp-stat-label { font-size: 13px; color: #909399; }
.sp-stat-divider { width: 1px; height: 36px; background: #E8E8EE; }
.sp-summary-bar-wrap { display: flex; align-items: center; gap: 10px; width: 80%; }
.sp-summary-bar { flex: 1; height: 8px; background: #F0F2F5; border-radius: 4px; overflow: hidden; }
.sp-summary-bar-fill { height: 100%; background: linear-gradient(90deg, #2E9E6B, #52C41A); border-radius: 4px; transition: width .5s; }
.sp-summary-pct { font-size: 16px; font-weight: 700; color: #2E9E6B; }
.sp-summary-actions { display: flex; gap: 10px; margin-top: 4px; }
.sp-summary-actions .el-button { border-radius: 10px; height: 38px; }

@media (max-width: 480px) { .plan-head-actions { width: 100%; } .plan-subject { flex: 1; } .sp-opt-grid { grid-template-columns: repeat(2, 1fr); } .sp-summary-stats { gap: 16px; } .sp-summary-bar-wrap { width: 100%; } }
</style>