<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { askStream, deleteSession, listSessions, sessionMessages } from '@/api/qa'
import { generateExercise } from '@/api/tutor'
import { addWrongBook, getMyCourses, submitRecord } from '@/api/user'
import { SUBJECTS } from '@/constants'
import CitationList from '@/components/CitationList.vue'
import MarkdownView from '@/components/MarkdownView.vue'

const sessions = ref([])
const currentSessionId = ref(null)
const messages = ref([])
const input = ref('')
const sending = ref(false)
const listRef = ref()

// 科目 / 章节选择
const subjects = ref([])
const courses = ref([])
const subject = ref('')
const chapter = ref('')

// 练习（agent 出题 / 相似例题）
const practiceDialog = ref(false)
const practiceItem = ref(null)
const practiceAnswer = ref('')
const practiceResult = ref(null)
const practiceLoading = ref(false)
const practiceSource = ref('') // generated / similar
const similarList = ref([])

// 语音
const voiceSupported = ref(typeof window !== 'undefined' && !!(window.SpeechRecognition || window.webkitSpeechRecognition))
const listening = ref(false)
let recognition = null

function initRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SR) return
  recognition = new SR()
  recognition.lang = 'zh-CN'
  recognition.interimResults = false
  recognition.onresult = (e) => { input.value = e.results[0][0].transcript; listening.value = false; send() }
  recognition.onerror = () => { listening.value = false; ElMessage.warning('语音识别失败，请检查麦克风权限') }
  recognition.onend = () => { listening.value = false }
}
function toggleVoice() {
  if (!voiceSupported.value) { ElMessage.warning('请使用 Chrome/Edge 浏览器并允许麦克风权限'); return }
  if (listening.value) { recognition.stop(); listening.value = false; return }
  try { recognition.start(); listening.value = true } catch (e) { listening.value = false }
}

async function loadSessions() { sessions.value = await listSessions() }
async function openSession(id) { currentSessionId.value = id; messages.value = await sessionMessages(id); scrollToBottom() }
function newSession() { currentSessionId.value = null; messages.value = [] }
function scrollToBottom() { nextTick(() => { if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight }) }

async function send() {
  const question = input.value.trim()
  if (!question || sending.value) return
  sending.value = true
  const history = messages.value.map((m) => ({ role: m.role, content: m.content })).slice(-6)
  messages.value.push({ role: 'user', content: question })
  const msgIndex = messages.value.push({ role: 'assistant', content: '', sources: [] }) - 1
  input.value = ''
  scrollToBottom()
  try {
    await askStream({
      question,
      session_id: currentSessionId.value,
      subject: subject.value || null,
      chapter: chapter.value || null,
      history,
      onToken: (full) => { messages.value[msgIndex].content = full; scrollToBottom() },
      onDone: (sid) => { currentSessionId.value = sid }
    })
    if (!messages.value[msgIndex].content) messages.value[msgIndex].content = '（未获取到回答，请重试）'
    await loadSessions()
  } catch (e) {
    messages.value[msgIndex].content = `（请求失败：${e.message || '未知错误'}）`
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

async function removeSession(id) {
  await deleteSession(id)
  await loadSessions()
  if (currentSessionId.value === id) newSession()
}

// agent 出题：按科目/章节生成一道题
async function genExercise() {
  const knowledgePoint = chapter.value || subject.value || '通用知识点'
  practiceLoading.value = true
  practiceSource.value = 'generated'
  practiceItem.value = null
  practiceResult.value = null
  practiceAnswer.value = ''
  practiceDialog.value = true
  try {
    // 关联该科目的课程；若无该科目课程则由后端按科目自动创建，保证题库科目正确
    const course = courses.value.find((c) => c.subject === subject.value)
    const data = await generateExercise({ knowledge_point: knowledgePoint, difficulty: 'medium', course_id: course ? course.id : null, subject: subject.value || null })
    if (!data.exercise_id && !data.id) {
      ElMessage.warning('题目生成后未能入库，无法记录答题与收藏，请稍后再试')
      practiceDialog.value = false
      return
    }
    practiceItem.value = { ...data, id: data.exercise_id || data.id }
  } catch (e) {
    // 禁答等失败提示已由请求拦截器统一弹出，这里只关闭弹窗
    practiceDialog.value = false
  } finally { practiceLoading.value = false }
}

// 打开相似例题
function openSimilar(ex) {
  practiceSource.value = 'similar'
  practiceItem.value = ex
  practiceResult.value = null
  practiceAnswer.value = ''
  practiceDialog.value = true
}

function cleanAnswer(s) { return (s || '').trim().toLowerCase().replace(/[\s，。、,.;；:：'"“”]/g, '') }
function firstKey(s) { const m = cleanAnswer(s).match(/^([a-d])/); return m ? m[1] : '' }

async function submitPractice() {
  const ex = practiceItem.value
  let isCorrect = false
  const ua = practiceAnswer.value
  if (ex.type === 'single') {
    // 选择题：比较所选选项键，或比较整段文本
    isCorrect = (firstKey(ua) === firstKey(ex.answer)) || (cleanAnswer(ua) === cleanAnswer(ex.answer))
  } else if (ex.type === 'judge') {
    const judgeMap = { 对: 'a', 正确: 'a', true: 'a', 错: 'b', 错误: 'b', false: 'b' }
    const u = judgeMap[cleanAnswer(ua)] || firstKey(ua)
    const a = judgeMap[cleanAnswer(ex.answer)] || firstKey(ex.answer)
    isCorrect = !!u && u === a
  } else if (ex.type === 'multiple') {
    const sort = (s) => (s || '').split('').sort().join('')
    isCorrect = sort(ua) === sort(ex.answer)
  } else {
    // 填空/问答：文本比对
    isCorrect = cleanAnswer(ua) === cleanAnswer(ex.answer) && cleanAnswer(ua) !== ''
  }
  practiceResult.value = isCorrect
  // 答错后自动在下方推荐相似例题；答对则清空
  if (isCorrect) { similarList.value = [] } else { await loadSimilar() }
  // 仅记录答题；错题本由学生手动点击“加入错题本”收藏
  await submitRecord({ exercise_id: ex.id, user_answer: ua, is_correct: isCorrect, duration_seconds: 30 })
}

// 加载相似例题（同知识点/同科目，排除当前题）
async function loadSimilar() {
  similarList.value = []
  if (!practiceItem.value) return
  const kp = (practiceItem.value.knowledge_points || [])[0]
  const params = kp ? { knowledge_point: kp, limit: 5 } : { course_id: practiceItem.value.course_id, limit: 5 }
  try {
    const exs = await getExercises(params)
    similarList.value = (exs || []).filter((e) => e.id !== practiceItem.value.id).slice(0, 3)
  } catch (e) { similarList.value = [] }
}

async function collectPractice() {
  await addWrongBook({ exercise_id: practiceItem.value.id, reason: practiceSource.value === 'generated' ? 'AI 出题收藏' : '相似例题收藏' })
  ElMessage.success('已加入错题本')
}

function optionText(options) { return (options || []).map((o) => `${o.key}. ${o.text}`).join('　') }

onMounted(async () => {
  initRecognition()
  subjects.value = SUBJECTS
  subject.value = subjects.value[0]
  try {
    courses.value = await getMyCourses()
  } catch (e) {
    console.warn('课程加载失败', e)
  }
  try {
    await loadSessions()
  } catch (e) {
    console.warn('会话加载失败', e)
  }
  newSession()
})
onBeforeUnmount(() => { if (recognition) { try { recognition.stop() } catch (e) { /* noop */ } } })
</script>

<template>
  <div class="chat-page">
    <div class="session-panel page-card">
      <el-button type="primary" style="width: 100%; margin-bottom: 12px" @click="newSession">＋ 新对话</el-button>
      <div v-for="s in sessions" :key="s.id" class="session-item" :class="{ active: s.id === currentSessionId }" @click="openSession(s.id)">
        <span class="session-title">{{ s.title }}</span>
        <el-icon class="del" @click.stop="removeSession(s.id)"><Delete /></el-icon>
      </div>
      <el-empty v-if="!sessions.length" description="暂无会话" :image-size="60" />
    </div>

    <div class="chat-panel page-card">
      <div class="subject-bar">
        <span class="label">科目：</span>
        <el-select v-model="subject" placeholder="选择科目" style="width: 140px">
          <el-option v-for="s in subjects" :key="s" :label="s" :value="s" />
        </el-select>
        <span class="label" style="margin-left: 12px">章节：</span>
        <el-input v-model="chapter" clearable style="width: 180px" />
        <el-button type="primary" plain style="margin-left: 12px" @click="genExercise">🎯 AI 出题练习</el-button>
      </div>

      <div ref="listRef" class="msg-list">
        <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
          <div class="bubble">
            <MarkdownView :content="m.content" />
            <CitationList v-if="m.role === 'assistant'" :sources="m.sources || []" />

          </div>
        </div>
        <div v-if="!messages.length" class="empty-tip">
          <p>选择科目/章节，输入问题开始问答，或点击「AI 出题练习」生成题目</p>
          <p class="small">支持多轮追问、语音输入，答案附带引用来源</p>
        </div>
      </div>

      <div class="input-area">
        <el-input v-model="input" type="textarea" :rows="2" resize="none" placeholder="请输入问题" @keydown.enter.exact.prevent="send" />
        <div class="actions">
          <el-button :type="listening ? 'danger' : 'default'" :disabled="!voiceSupported" @click="toggleVoice">
            <el-icon style="margin-right:4px"><Microphone /></el-icon>{{ listening ? '停止录音' : '语音输入' }}
          </el-button>
          <el-button type="primary" :loading="sending" @click="send">发送</el-button>
        </div>
      </div>
    </div>

    <el-dialog v-model="practiceDialog" :title="practiceSource === 'generated' ? 'AI 出题练习' : '相似例题练习'" width="560px">
      <div v-loading="practiceLoading">
        <template v-if="practiceItem">
          <p style="line-height:1.7"><b>题目：</b>{{ practiceItem.content }}</p>
          <p v-if="practiceItem.options && practiceItem.options.length" style="margin-top:6px"><b>选项：</b>{{ optionText(practiceItem.options) }}</p>

          <template v-if="practiceItem.type === 'single'">
            <el-radio-group v-model="practiceAnswer">
              <el-radio v-for="o in practiceItem.options || []" :key="o.key" :value="o.key">{{ o.key }}. {{ o.text }}</el-radio>
            </el-radio-group>
          </template>
          <template v-else-if="practiceItem.type === 'multiple'">
            <el-checkbox-group v-model="practiceAnswer">
              <el-checkbox v-for="o in practiceItem.options || []" :key="o.key" :value="o.key">{{ o.key }}. {{ o.text }}</el-checkbox>
            </el-checkbox-group>
          </template>
          <template v-else-if="practiceItem.type === 'judge'">
            <el-radio-group v-model="practiceAnswer"><el-radio value="对">对</el-radio><el-radio value="错">错</el-radio></el-radio-group>
          </template>
          <template v-else>
            <el-input v-model="practiceAnswer" type="textarea" :rows="2" placeholder="请输入你的答案" />
          </template>

          <div v-if="practiceResult !== null" class="result" :class="practiceResult ? 'ok' : 'no'">
            {{ practiceResult ? '✓ 回答正确' : '✗ 回答错误' }}
          </div>
          <div v-if="practiceResult !== null" class="analysis">答案：{{ practiceItem.answer }}　解析：{{ practiceItem.analysis }}</div>
          <div v-if="similarList.length" class="similar-box">
            <div class="similar-title">答错了，点击练习相似例题：</div>
            <div v-for="(s, j) in similarList" :key="j" class="similar-item" @click="openSimilar(s)">
              <span>{{ s.content.slice(0, 40) }}</span><el-icon style="margin-left:4px"><Right /></el-icon>
            </div>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="practiceDialog = false">关闭</el-button>
        <el-button type="primary" :disabled="!practiceItem" @click="submitPractice">提交答案</el-button>
        <el-button v-if="practiceItem && practiceResult !== null" type="warning" plain @click="collectPractice">加入错题本</el-button>
        <el-button v-if="practiceSource === 'generated'" type="primary" plain @click="genExercise">再出一题</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.chat-page { display: flex; gap: 16px; height: calc(100vh - 160px); }
.session-panel { width: 240px; overflow-y: auto; flex-shrink: 0; }
.session-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border-radius: 6px; cursor: pointer; margin-bottom: 6px; color: #303133; }
.session-item:hover { background: #fbf6ed; }
.session-item.active { background: #f4ebdd; color: #a67b5b; }
.session-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.del { visibility: hidden; }
.session-item:hover .del { visibility: visible; }
.chat-panel { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.subject-bar { display: flex; align-items: center; padding-bottom: 12px; border-bottom: 1px solid #efe5d3; margin-bottom: 8px; }
.subject-bar .label { font-size: 13px; color: #7e5a3f; }
.msg-list { flex: 1; overflow-y: auto; padding: 8px 4px; }
.msg { display: flex; margin-bottom: 14px; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }
.bubble { max-width: 80%; padding: 12px 14px; border-radius: 10px; line-height: 1.7; }
.msg.user .bubble { background: #a67b5b; color: #fff; }
.msg.assistant .bubble { background: #faf5ec; color: #303133; }
.empty-tip { text-align: center; color: #909399; margin-top: 60px; }
.empty-tip .small { font-size: 12px; margin-top: 6px; }
.input-area { border-top: 1px solid #efe5d3; padding-top: 12px; }
.actions { display: flex; justify-content: flex-end; margin-top: 8px; gap: 8px; }
.result { margin-top: 8px; font-weight: 700; }
.result.ok { color: #67c23a; }
.result.no { color: #f56c6c; }
.analysis { color: #606266; font-size: 13px; margin: 6px 0; }
.similar-box { margin-top: 10px; border-top: 1px dashed #e2d5be; padding-top: 8px; }
.similar-title { font-size: 13px; color: #909399; margin-bottom: 4px; }
.similar-item { cursor: pointer; color: #a67b5b; font-size: 13px; padding: 3px 0; display: flex; align-items: center; }
.similar-item:hover { text-decoration: underline; }
</style>