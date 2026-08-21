<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import { askStream, deleteSession, listSessions, sessionMessages } from '@/api/qa'
import { generateExercise } from '@/api/tutor'
import { addWrongBook, deleteWrongBook, getMyCourses, getSimilarExercises, getWrongBook, submitRecord } from '@/api/user'
import { SUBJECTS } from '@/constants'
import { isAnswerCorrect, normalizePracticeAnswer, normAnswer, typeKey, typeLabel } from '@/utils/answer'
import CitationList from '@/components/CitationList.vue'
import MarkdownView from '@/components/MarkdownView.vue'

const sessions = ref([])
const currentSessionId = ref(null)
const messages = ref([])
const input = ref('')
const sending = ref(false)
const listRef = ref()

const route = useRoute()

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
// 错题本状态反馈（不修改数据库，复用现有 wrong_book 接口）
const collectMap = ref({})       // exercise_id -> wrong_book id
const isCollected = ref(false)   // 当前题目是否已在错题本
const practiceSubmitting = ref(false) // 提交答案防重复
// 自动发送标记（来自学情分析跳转），用于隐藏用户气泡
const isAutoSend = ref(false)
// 学情分析上下文（来自结构化参数）
const analysisContext = ref('')
// 去除史记录（内容哈希），用于“再出一题/相似题”去重
const generatedHistory = ref([])      // 内容哈希（最多保留最近 12 条）

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
  practiceSubmitting.value = false
  isCollected.value = false
  similarList.value = []           // 新题未作答前不显示相似题
  practiceDialog.value = true
  try {
    const course = courses.value.find((c) => c.subject === subject.value)
    const params = {
      knowledge_point: knowledgePoint,
      difficulty: 'medium',
      course_id: course ? course.id : null,
      subject: subject.value || null,
      exclude_contents: generatedHistory.value.slice(-8), // 去重：提示 LLM 避开已生成题
    }
    const data = await generateExercise(params)
    if (!data.exercise_id && !data.id) {
      ElMessage.warning('题目生成后未能入库，无法记录答题与收藏，请稍后再试')
      practiceDialog.value = false
      return
    }
    // 记录内容哈希，供下一次“再出一题”去重
    generatedHistory.value.push(normAnswer(data.content || ''))
    if (generatedHistory.value.length > 12) generatedHistory.value = generatedHistory.value.slice(-12)
    practiceItem.value = { ...data, id: data.exercise_id || data.id }
    practiceAnswer.value = currentType.value === 'multiple' ? [] : ''
    syncCollectMap()
  } catch (e) {
    // 错误提示由拦截器弹出，仅关闭弹窗
    practiceDialog.value = false
  } finally { practiceLoading.value = false }
}

// 打开相似例题
function openSimilar(ex) {
  practiceSource.value = 'similar'
  practiceItem.value = ex
  practiceResult.value = null
  practiceAnswer.value = currentType.value === 'multiple' ? [] : ''
  practiceSubmitting.value = false
  isCollected.value = false
  similarList.value = []           // 打开相似题练习页，答错后才重新推荐
  practiceDialog.value = true
  syncCollectMap()
}

// 加载错题本收藏映射（exercise_id -> wrong_book id），用于按钮状态回显
async function syncCollectMap() {
  try {
    const items = (await getWrongBook()) || []
    collectMap.value = {}
    items.forEach((it) => { collectMap.value[it.exercise_id] = it.id })
    if (practiceItem.value) isCollected.value = !!collectMap.value[practiceItem.value.id]
  } catch (e) {
    collectMap.value = {}
  }
}

async function submitPractice() {
  if (practiceSubmitting.value || practiceResult.value !== null || !practiceItem.value) return
  practiceSubmitting.value = true
  const ex = practiceItem.value
  const ua = normalizePracticeAnswer(ex.type, practiceAnswer.value) // 多选数组→排序字符串
  const isCorrect = isAnswerCorrect(ex.type, ua, ex.answer)
  practiceResult.value = isCorrect
  if (isCorrect) { similarList.value = [] } else { await loadSimilar() }
  try {
    await submitRecord({ exercise_id: ex.id, user_answer: ua, is_correct: isCorrect, duration_seconds: 30 })
  } finally {
    practiceSubmitting.value = false
  }
}

// 加载相似例题：调用专用相似题接口（P0 门限/硬过滤/回退 + P1 语义匹配 + P2 AI 变式兜底）
async function loadSimilar() {
  similarList.value = []
  if (!practiceItem.value) return
  try {
    const res = await getSimilarExercises(practiceItem.value.id, 3)
    similarList.value = (res && res.items) || []
  } catch (e) { similarList.value = [] }
}

// 归一化的当前题型（识别中文/英文异构 type；有选项却当作问答时按单选处理）
const currentType = computed(() => {
  if (!practiceItem.value) return 'qa'
  const k = typeKey(practiceItem.value.type || '')
  if (k === 'qa' && (practiceItem.value.options || []).length) return 'single'
  return k
})

function pickOption(kind, key) {
  if (kind === 'single') { practiceAnswer.value = key; return }
  if (kind === 'multiple') {
    const arr = Array.isArray(practiceAnswer.value) ? [...practiceAnswer.value] : []
    const i = arr.indexOf(key)
    if (i >= 0) arr.splice(i, 1); else arr.push(key)
    practiceAnswer.value = arr
  }
}
function isOptActive(kind, key) {
  if (kind === 'single') return practiceAnswer.value === key
  if (kind === 'multiple') return Array.isArray(practiceAnswer.value) && practiceAnswer.value.includes(key)
  return false
}

async function collectPractice() {
  const exId = practiceItem.value.id
  try {
    if (isCollected.value) {
      const wid = collectMap.value[exId]
      if (wid) await deleteWrongBook(wid)
      isCollected.value = false
      ElMessage.success('已移出错题本')
    } else {
      await addWrongBook({ exercise_id: exId, reason: '' })
      await syncCollectMap()
      ElMessage.success('已加入错题本')
    }
  } catch (e) {
    /* 错误提示由拦截器弹出 */
  }
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

  // 从学情分析带入推荐练习：自动新建对话并发送预设指令，无需用户手动输入
  // 增强：自动发送不显示用户气泡，直接显示 AI 回答；携带结构化上下文
  const preset = route.query.q
  const contextFrom = route.query.context_from
  if (preset) {
    const presetSubject = route.query.subject
    if (presetSubject && subjects.value.includes(String(presetSubject))) subject.value = String(presetSubject)
    // 拼接学情上下文提示
    let ctx = ''
    const stageName = route.query.stage_name
    const stageContent = route.query.stage_content
    const weakPoints = route.query.weak_points
    if (stageName || stageContent) ctx += `学生当前处于「${stageName || ''}」阶段，目标内容：${stageContent || ''}。`
    if (weakPoints) ctx += `该学生的薄弱点诊断：${weakPoints}。`
    analysisContext.value = ctx
    nextTick(() => {
      autoSend(String(preset))
    })
  }
})

// 自动发送：隐藏用户气泡，直接调用流式接口获取 AI 回答
async function autoSend(question) {
  isAutoSend.value = true
  sending.value = true
  const msgIndex = messages.value.push({ role: 'assistant', content: '', sources: [], isAuto: true }) - 1
  scrollToBottom()
  try {
    await askStream({
      question,
      session_id: currentSessionId.value,
      subject: subject.value || null,
      chapter: chapter.value || null,
      history: [],
      context_from: route.query.context_from || undefined,
      stage_name: route.query.stage_name || undefined,
      stage_content: route.query.stage_content || undefined,
      weak_points: route.query.weak_points || undefined,
      onToken: (full) => {
        messages.value[msgIndex].content = full
        scrollToBottom()
      },
      onDone: (sid) => {
        currentSessionId.value = sid
      }
    })
    if (!messages.value[msgIndex].content) messages.value[msgIndex].content = '（未获取到回答，请重试）'
    await loadSessions()
  } catch (e) {
    messages.value[msgIndex].content = `（请求失败：${e.message || '未知错误'}）`
  } finally {
    sending.value = false
    isAutoSend.value = false
    scrollToBottom()
  }
}
onBeforeUnmount(() => { if (recognition) { try { recognition.stop() } catch (e) { /* noop */ } } })
</script>

<template>
  <div class="chat-page">
    <!-- 左侧：会话列表 -->
    <div class="session-panel page-card">
      <el-button type="primary" style="width: 100%; margin-bottom: 16px" @click="newSession">
        <el-icon style="margin-right:6px"><Plus /></el-icon>新对话
      </el-button>
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px">
        <span class="sub-title" style="margin:0">历史会话</span>
        <el-tag size="small" type="info" effect="plain">{{ sessions.length }}</el-tag>
      </div>
      <div class="session-list-wrap">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === currentSessionId }"
          @click="openSession(s.id)"
        >
          <el-icon style="flex-shrink:0; color:inherit"><ChatLineSquare /></el-icon>
          <span class="session-title">{{ s.title }}</span>
          <el-icon class="del" title="删除会话" @click.stop="removeSession(s.id)"><Delete /></el-icon>
        </div>
        <el-empty v-if="!sessions.length" description="暂无会话，开始你的第一次提问吧" :image-size="60" />
      </div>
    </div>

    <!-- 右侧：对话主区 -->
    <div class="chat-panel page-card">
      <!-- 科目/章节/AI 出题栏 -->
      <div class="subject-bar">
        <div class="field field-subject">
          <span class="label"><el-icon :size="14" style="color:#8B5CF6"><Reading /></el-icon>科目</span>
          <el-select v-model="subject" placeholder="选择科目" size="default">
            <el-option v-for="s in subjects" :key="s" :label="s" :value="s" />
          </el-select>
        </div>
        <div class="field">
          <span class="label"><el-icon :size="14" style="color:#2F6FED"><Collection /></el-icon>章节 / 知识点</span>
          <el-input v-model="chapter" clearable placeholder="可输入章节或知识点" />
        </div>
        <el-button type="primary" plain class="gen-btn" @click="genExercise">
          <el-icon style="margin-right:4px"><Promotion /></el-icon>AI 出题练习
        </el-button>
      </div>

      <!-- 消息列表 -->
      <div ref="listRef" class="msg-list">
        <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
          <!-- 自动发送的消息：不显示用户气泡，只显示 AI 回答上方加提示 -->
          <template v-if="m.isAuto && m.role === 'assistant'">
            <el-avatar :size="34" class="msg-avatar">
              <el-icon :size="18" color="#8B5CF6"><MagicStick /></el-icon>
            </el-avatar>
            <div class="bubble">
              <div class="auto-hint" v-if="analysisContext">
                <el-icon :size="14" color="#8B5CF6"><Reading /></el-icon>
                根据你的学情分析，为你推荐以下内容：
              </div>
              <div class="auto-hint" v-else>
                <el-icon :size="14" color="#8B5CF6"><Lightning /></el-icon>
                为你推荐以下内容：
              </div>
              <MarkdownView :content="m.content" />
              <CitationList v-if="m.sources" :sources="m.sources || []" />
            </div>
          </template>

          <!-- 普通消息 -->
          <template v-else>
            <el-avatar :size="34" class="msg-avatar" v-if="m.role === 'assistant'">
              <el-icon :size="18" color="#8B5CF6"><MagicStick /></el-icon>
            </el-avatar>

            <div class="bubble">
              <MarkdownView :content="m.content" />
              <CitationList v-if="m.role === 'assistant'" :sources="m.sources || []" />
            </div>

            <el-avatar
              :size="34"
              class="msg-avatar"
              v-if="m.role === 'user'"
              :src="$pinia.state.value.user?.user?.avatar || undefined"
            >
              {{ ($pinia.state.value.user?.user?.full_name || $pinia.state.value.user?.user?.username || 'U').slice(0,1) }}
            </el-avatar>
          </template>
        </div>

        <div v-if="!messages.length" class="empty-tip">
          <div class="empty-hero">
            <el-icon :size="44" style="color:#8B5CF6"><ChatDotRound /></el-icon>
          </div>
          <p class="tip-title">开始智能问答，让 AI 为你解答疑惑</p>
          <p class="tip-sub">
            选择科目/章节后，输入问题点击"发送"。也可点击「AI 出题练习」生成专属练习。
          </p>
          <div class="quick-asks">
            <div v-for="(q, i) in ['什么是勾股定理？', '帮我讲一下英语时态', '给我出两道一元二次方程']" :key="i" class="ask-chip" @click="input=q; send()">
              {{ q }}
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <el-input
          v-model="input"
          type="textarea"
          :rows="2"
          resize="none"
          placeholder="请输入你的问题（支持 Enter 发送，Shift+Enter 换行）"
          class="chat-input"
          @keydown.enter.exact.prevent="send"
        />
        <div class="actions">
          <div class="left-actions">
            <el-button :type="listening ? 'danger' : 'default'" :disabled="!voiceSupported" @click="toggleVoice">
              <el-icon style="margin-right:4px"><Microphone /></el-icon>
              {{ listening ? '正在录音…点击停止' : '语音输入' }}
            </el-button>
            <el-tag size="small" type="info" effect="plain" v-if="!voiceSupported" title="请使用 Chrome/Edge 并允许麦克风">
              语音功能受限
            </el-tag>
          </div>
          <div class="right-actions">
            <el-button type="primary" :loading="sending" size="default" @click="send">
              <el-icon style="margin-right:4px"><Promotion /></el-icon>发送
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 练习弹窗 -->
    <el-dialog v-model="practiceDialog" :title="practiceSource === 'generated' ? 'AI 出题练习' : '相似例题练习'" width="560px">
      <div v-loading="practiceLoading">
        <template v-if="practiceItem">
          <div class="ex-header">
            <el-tag size="small" :type="practiceSource === 'generated' ? 'warning' : 'primary'" effect="light" style="margin-right:6px">
              {{ practiceSource === 'generated' ? 'AI 生成' : '相似例题' }}
            </el-tag>
            <el-tag size="small" effect="plain">
              {{ typeLabel(practiceItem.type, (practiceItem.options || []).length > 0) }}
            </el-tag>
          </div>
          <p class="ex-content"><b>题目：</b>{{ practiceItem.content }}</p>
          <p v-if="practiceItem.options && practiceItem.options.length" class="ex-options"><b>选项：</b>{{ optionText(practiceItem.options) }}</p>

          <template v-if="practiceItem.options && practiceItem.options.length && (currentType === 'single' || currentType === 'multiple')">
            <div class="opt-grid">
              <button
                v-for="(o, i) in practiceItem.options"
                :key="o.key || i"
                type="button"
                class="opt-btn"
                :class="{ active: isOptActive(currentType, o.key || 'ABCD'[i]) }"
                @click="pickOption(currentType, o.key || 'ABCD'[i])"
              >{{ o.key || 'ABCD'[i] }}</button>
            </div>
          </template>
          <template v-else-if="currentType === 'judge'">
            <el-radio-group v-model="practiceAnswer" class="ex-radios">
              <el-radio value="对">✓ 对</el-radio>
              <el-radio value="错">✗ 错</el-radio>
            </el-radio-group>
          </template>
          <template v-else-if="currentType === 'fill'">
            <el-input v-model="practiceAnswer" placeholder="请输入答案文本" class="ex-input" @keyup.enter.prevent="submitPractice" />
          </template>
          <template v-else>
            <el-input v-model="practiceAnswer" type="textarea" :rows="3" placeholder="请输入你的答案" />
          </template>

          <transition name="result-pop">
            <div v-if="practiceResult !== null" class="result" :class="practiceResult ? 'ok' : 'no'" role="status">
              <el-icon :size="18" v-if="practiceResult"><CircleCheck /></el-icon>
              <el-icon :size="18" v-else><CircleClose /></el-icon>
              <span>{{ practiceResult ? '回答正确，再接再厉！' : '回答错误，查看下方解析理解错因' }}</span>
            </div>
          </transition>
          <div v-if="practiceResult !== null" class="analysis">
            <div class="an-row"><b>正确答案：</b><el-tag type="success" effect="light" size="small" style="font-weight:600">{{ practiceItem.answer }}</el-tag></div>
            <div v-if="practiceItem.analysis" class="an-row"><b>解析：</b>{{ practiceItem.analysis }}</div>
          </div>

          <div v-if="practiceResult === false && !similarList.length" class="no-similar">
            <el-icon style="margin-right:4px; color:#8B5CF6"><InfoFilled /></el-icon>
            暂无相似例题，建议先巩固本章知识点，或点击「再出一题」多练一道变式。
          </div>
          <div v-if="similarList.length" class="similar-box">
            <div class="similar-title">💡 答错了？试试下面的相似例题：</div>
            <div v-for="(s, j) in similarList" :key="j" class="similar-item" @click="openSimilar(s)">
              <el-icon style="color:#2F6FED; flex-shrink:0"><Promotion /></el-icon>
              <span>{{ s.content.slice(0, 50) }}{{ s.content.length > 50 ? '…' : '' }}</span>
              <el-icon class="arrow"><Right /></el-icon>
            </div>
          </div>
        </template>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button class="df-btn" @click="practiceDialog = false">关闭</el-button>
          <el-button
            type="primary"
            class="df-btn df-primary"
            :disabled="!practiceItem || practiceResult !== null || practiceSubmitting"
            :loading="practiceSubmitting"
            @click="submitPractice"
          >提交答案</el-button>
          <el-button
            v-if="practiceItem && practiceResult !== null"
            class="df-btn"
            :class="{ 'collect-btn-ok': isCollected }"
            @click="collectPractice"
          >
            <el-icon style="margin-right:4px" :class="{ 'is-filled': isCollected }"><Star /></el-icon>
            {{ isCollected ? '已加入错题本' : '加入错题本' }}
          </el-button>
          <el-button v-if="practiceSource === 'generated'" class="df-btn" plain @click="genExercise">
            <el-icon style="margin-right:4px"><RefreshRight /></el-icon>再出一题
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* 整体 chat 布局 */
.chat-page {
  display: flex;
  gap: 16px;
  height: calc(100vh - 160px);
  min-height: 620px;
}
/* --- 左：会话列表 --- */
.session-panel {
  width: 248px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.session-list-wrap {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  padding-right: 2px;
}
.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 6px;
  color: #303133;
  font-size: 14px;
  transition: background-color .15s;
  border: 1px solid transparent;
}
.session-item:hover { background: #F5F3FF; border-color: #E9E4FE; }
.session-item.active {
  background: #F5F3FF;
  color: #7C3AED;
  border-color: #DDD6FE;
  font-weight: 500;
  box-shadow: 0 1px 3px rgba(139,92,246,.08);
}
.session-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.del {
  opacity: 0;
  color: #909399;
  transition: color .15s, opacity .15s;
  padding: 2px;
  border-radius: 4px;
}
.session-item:hover .del { opacity: 1; }
.del:hover { color: #F56C6C !important; background: #FDECEC; }

/* --- 右：对话主区 --- */
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
/* 科目栏 */
.subject-bar {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #EFF1F5;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.subject-bar .field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 160px;
  flex: 1;
}
.subject-bar .field-subject { flex: none; width: 170px; }
.subject-bar .label {
  font-size: 13px;
  color: #303133;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.subject-bar .field-subject .label { color: #722ED1; }
.subject-bar .field:nth-child(2) .label { color: #2F6FED; }
.subject-bar :deep(.el-select__wrapper),
.subject-bar :deep(.el-input__wrapper) { height: 38px; }
.subject-bar :deep(.el-select__wrapper) { min-height: 38px; }
.gen-btn {
  height: 38px;
  align-self: flex-end;
  margin-left: auto;
  border-radius: 10px;
}
.gen-btn:hover { background: #F3EDFB; border-color: #8B5CF6; color: #6D28D9; }

/* 消息列表 */
.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 4px 12px 2px;
  display: flex;
  flex-direction: column;
}
.msg {
  display: flex;
  margin-bottom: 26px;
  gap: 12px;
  align-items: flex-start;
}
.msg.user { flex-direction: row-reverse; }
.msg-avatar {
  flex-shrink: 0;
  background: #F3EDFB;
  box-shadow: 0 2px 6px rgba(139, 92, 246, 0.16);
}
.msg.user .msg-avatar { background: #2F6FED; color: #fff; }

.bubble {
  max-width: 76%;
  padding: 12px 16px;
  border-radius: 14px;
  line-height: 1.75;
  font-size: 14px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
  word-break: break-word;
}
.msg.user .bubble {
  background: linear-gradient(135deg, #F5F3FF, #EDE9FE);
  color: #3B3466;
  border: 1px solid #E6DFFC;
  border-top-right-radius: 4px;
}
.msg.assistant .bubble {
  background: #FFFFFF;
  color: #303133;
  border: 1px solid #F0F2F5;
  border-top-left-radius: 4px;
}
.msg.assistant .bubble :deep(.markdown-body) { color: #303133; }

/* 自动发送提示条 */
.auto-hint {
  font-size: 13px;
  color: #8B5CF6;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  padding: 6px 10px;
  background: #F5F3FF;
  border-radius: 8px;
  font-weight: 500;
}

/* 空状态 */
.empty-tip {
  text-align: center;
  color: #909399;
  margin-top: 10vh;
}
.empty-hero {
  width: 72px; height: 72px;
  margin: 0 auto 0;
  background: linear-gradient(135deg, rgba(139,92,246,.12), rgba(47,111,237,.12));
  border-radius: 20px;
  display: flex; align-items: center; justify-content: center;
}
.tip-title {
  font-size: 16px; font-weight: 600; color: #303133; margin: 16px 0 6px;
}
.tip-sub { font-size: 13px; line-height: 1.7; max-width: 480px; margin: 0 auto 26px; }
.quick-asks {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
  max-width: 680px;
  margin: 0 auto;
}
.ask-chip {
  padding: 9px 18px;
  border-radius: 12px;
  border: 1px solid #DDD6FE;
  background: #FAFAFF;
  color: #6D28D9;
  font-size: 13px;
  cursor: pointer;
  transition: all .18s;
}
.ask-chip:hover {
  background: #F5F3FF;
  border-color: #8B5CF6;
  transform: translateY(-1px);
  color: #5B21B6;
}

/* 输入区 */
.input-area {
  border-top: 1px solid #EFF1F5;
  padding-top: 16px;
}
.chat-input :deep(.el-textarea__inner) {
  border-radius: 12px;
  border-color: #D0D5DD;
  padding: 11px 14px;
  line-height: 1.6;
  transition: border-color .15s, box-shadow .15s;
}
.chat-input :deep(.el-textarea__inner:focus) {
  border-color: #8B5CF6;
  box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.12);
}
.actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  flex-wrap: wrap;
  gap: 8px;
}
.left-actions, .right-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.actions :deep(.el-button) { border-radius: 10px; margin-left: 0; }
.actions :deep(.el-button + .el-button) { margin-left: 10px; }
.actions .left-actions :deep(.el-button) { color: #606266; border-color: #D0D5DD; }
.actions .left-actions :deep(.el-button:hover) { color: #6D28D9; border-color: #8B5CF6; background: #FAF8FF; }

/* 练习弹窗 */
.ex-header { margin-bottom: 10px; display: flex; align-items: center; }
.ex-content {
  line-height: 1.8;
  padding: 12px 14px;
  background: #FAFBFC;
  border-radius: 10px;
  border: 1px solid #EEF1F5;
  color: #303133;
}
.ex-options {
  margin-top: 8px;
  padding: 10px 14px;
  background: #FBFBFF;
  border: 1px solid #F0EDFD;
  border-radius: 10px;
  color: #303133;
  line-height: 1.8;
}
.ex-radios {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}
.ex-radios :deep(.el-radio),
.ex-radios :deep(.el-checkbox) {
  height: auto;
  margin-right: 0;
  padding: 9px 12px;
  border: 1px solid #EEF1F5;
  border-radius: 10px;
  transition: border-color .15s, background-color .15s;
}
.ex-radios :deep(.el-radio:hover),
.ex-radios :deep(.el-checkbox:hover) { border-color: #DDD6FE; background: #FBFAFF; }
.ex-radios :deep(.el-radio.is-checked),
.ex-radios :deep(.el-checkbox.is-checked) { border-color: #8B5CF6; background: #F7F4FF; }
.result {
  margin-top: 14px;
  padding: 10px 14px;
  border-radius: 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}
.result.ok { background: #ECF8F1; color: #2E9E6B; border: 1px solid #B7E4C7; }
.result.no { background: #FDECEC; color: #E04A4A; border: 1px solid #F5B7B7; }
.result-pop-enter-active { transition: all .25s ease; }
.result-pop-enter-from { opacity: 0; transform: translateY(-6px); }
.result-pop-leave-active { transition: all .18s ease; }
.result-pop-leave-to { opacity: 0; transform: translateY(-3px); }
.analysis {
  margin-top: 10px;
  padding: 12px 14px;
  background: #F8F9FB;
  border-radius: 10px;
  color: #303133;
}
.an-row { margin: 4px 0; line-height: 1.75; }
.similar-box {
  margin-top: 14px;
  border-top: 1px dashed #D0D5DD;
  padding-top: 12px;
}
.no-similar {
  margin-top: 14px;
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #909399;
  background: #F8F9FB;
  border: 1px dashed #E3E6EB;
  border-radius: 10px;
}
.ex-input { border-radius: 10px; }
/* 选择题选项按钮：一行四个，仅显示选项字母 */
.opt-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin: 14px 0 4px;
}
.opt-btn {
  height: 44px;
  border: 1px solid #E3E6EB;
  border-radius: 10px;
  background: #F8F9FB;
  color: #4b5563;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s;
}
.opt-btn:hover { border-color: #8B5CF6; color: #8B5CF6; }
.opt-btn.active {
  background: #8B5CF6;
  border-color: #8B5CF6;
  color: #fff;
}
@media (max-width: 480px) { .opt-grid { grid-template-columns: repeat(2, 1fr); } }
.similar-title {
  font-size: 13px;
  font-weight: 500;
  color: #1A1A1A;
  margin-bottom: 8px;
}
.similar-item {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  padding: 8px 12px;
  border-radius: 8px;
  margin-bottom: 6px;
  color: #303133;
  background: #FAFBFC;
  border: 1px solid #F0F2F5;
  transition: all .15s;
}
.similar-item:hover {
  background: #F5F3FF;
  border-color: #DDD6FE;
  color: #5B21B6;
}
.similar-item .arrow {
  margin-left: auto;
  color: #C0C4CC;
  flex-shrink: 0;
  transition: transform .15s, color .15s;
}
.similar-item:hover .arrow { color: #7C3AED; transform: translateX(3px); }

/* 底部按钮组：统一尺寸、主操作权重 */
.dialog-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}
.dialog-footer .df-btn {
  border-radius: 10px;
  height: 36px;
  padding: 0 18px;
}
.dialog-footer .df-primary { min-width: 96px; }
.dialog-footer .is-filled { color: #F6A704; }
/* 已加入错题本：淡黄背景 + 深黄星标 */
.dialog-footer .collect-btn-ok.el-button {
  background: #FEF7D6;
  border-color: #F3E08B;
  color: #8a6d1a;
}
.dialog-footer .collect-btn-ok.el-button:hover,
.dialog-footer .collect-btn-ok.el-button:focus {
  background: #FDF2B8;
  border-color: #EED06E;
  color: #8a6d1a;
}
.dialog-footer .collect-btn-ok .is-filled { color: #E5A400; }
</style>
