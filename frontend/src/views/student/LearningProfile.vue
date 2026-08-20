<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { deleteWrongBook, getMyStats, getTimeline, getWrongBook } from '@/api/user'
import { myAnalysis, myAnalysisLatest } from '@/api/tutor'

const tab = ref('stats')
const stats = ref({})
const wrongItems = ref([])
const timeline = ref([])
const range = ref([])

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
    const task = await myAnalysis()
    if (task.status === 'completed') {
      const output = task.output || {}
      if (output.message) {
        // 无学习记录：仅弹出提示，页面保持空状态
        plan.value = null
        planDate.value = ''
        ElMessage.warning(output.message)
      } else {
        plan.value = output
        planDate.value = task.created_at || ''
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
      // 无学习记录的提示不作为方案展示，页面保持空状态
      if (task.output.message) return
      plan.value = task.output
      planDate.value = task.created_at || ''
    }
  } catch (e) { /* 忽略 */ }
}

let radar = null
let activity = null

async function loadStats() {
  stats.value = await getMyStats()
  renderCharts()
}

function renderCharts() {
  if (radar) radar.dispose()
  if (activity) activity.dispose()
  radar = echarts.init(document.getElementById('radarChart'))
  activity = echarts.init(document.getElementById('activityChart'))
  const mastery = stats.value.knowledge_mastery || []
  radar.setOption({
    title: { text: '各知识点掌握度' },
    tooltip: {},
    radar: { indicator: mastery.map((m) => ({ name: m.knowledge_point, max: 100 })) },
    series: [{ type: 'radar', data: [{ value: mastery.map((m) => m.mastery), name: '掌握度' }] }]
  })
  const last7 = (stats.value.daily || []).slice(-7)
  activity.setOption({
    title: { text: '近7天学习活跃度' },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: last7.map((d) => d.date) },
    yAxis: { type: 'value' },
    series: [{ type: 'line', smooth: true, areaStyle: {}, data: last7.map((d) => d.count) }]
  })
}

function resize() { radar?.resize(); activity?.resize() }

async function loadWrong() {
  wrongItems.value = await getWrongBook()
}

async function loadTimeline() {
  const params = {}
  if (range.value && range.value.length === 2) { params.start = range.value[0]; params.end = range.value[1] }
  timeline.value = await getTimeline(params)
}

async function removeWrong(id) {
  await deleteWrongBook(id)
  ElMessage.success('已删除')
  await loadWrong()
}

function switchTab(t) {
  tab.value = t
  if (t === 'stats') loadStats()
  if (t === 'wrong') loadWrong()
  if (t === 'records') loadTimeline()
}

function fmtTime(t) {
  if (!t) return ''
  const d = new Date(t)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

const typeMeta = {
  exercise: { label: '做了题', color: '#2F6FED' },
  question: { label: '问了问题', color: '#F2A93B' },
  collect: { label: '收藏错题', color: '#43B97F' }
}

// 错题本查看原题与正确答案
const wrongDialog = ref(false)
const currentWrong = ref(null)
function viewWrong(row) {
  currentWrong.value = row
  wrongDialog.value = true
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

onMounted(() => {
  loadStats().catch((e) => console.warn('学习统计加载失败', e))
  loadLatestPlan()
  window.addEventListener('resize', resize)
})
onBeforeUnmount(() => { if ('speechSynthesis' in window) window.speechSynthesis.cancel(); window.removeEventListener('resize', resize); radar?.dispose(); activity?.dispose() })
</script>

<template>
  <div>
    <div class="page-card plan-card">
      <div style="display:flex; justify-content:space-between; align-items:center">
        <div>
          <h3>个性化学习辅导（AI Agent）</h3>
        </div>
        <div style="display:flex; gap:10px">
          <el-button size="large" :type="speaking ? 'warning' : 'default'" :disabled="!plan" @click="speakPlan">
            {{ speaking ? '停止朗读' : '🔊 语音朗读' }}
          </el-button>
          <el-button type="primary" size="large" :loading="generating" @click="genPlan">生成我的辅导方案</el-button>
        </div>
      </div>

      <div v-loading="planLoading" style="margin-top: 16px">
        <div v-if="planLoading" class="plan-progress">{{ progressText }}</div>
        <template v-if="plan && !planLoading">
          <el-alert type="success" :closable="false" style="margin-bottom: 12px">🎯 方案已生成，请按阶段执行</el-alert>
          <div v-if="planDate" class="plan-date">方案生成时间：{{ fmtTime(planDate) }}（如需更新请再次点击“生成我的辅导方案”）</div>
          <div class="plan-section">
            <h4>📌 弱点诊断</h4>
            <p>{{ plan.weakness_diagnosis }}</p>
          </div>
          <div class="plan-section">
            <h4>🗺 定制学习路径</h4>
            <el-timeline>
              <el-timeline-item v-for="(st, i) in plan.learning_path || []" :key="i" :timestamp="st.stage" placement="top">
                <div>{{ st.content }}</div>
                <div v-if="st.exercises && st.exercises.length" class="gray">练习：{{ st.exercises.join('、') }}</div>
              </el-timeline-item>
            </el-timeline>
          </div>
          <div class="plan-section">
            <h4>✏️ 推荐练习</h4>
            <el-tag v-for="(r, i) in plan.recommended_exercises || []" :key="i" style="margin:4px">{{ r }}</el-tag>
          </div>
          <div class="plan-section">
            <h4>💡 学习建议</h4>
            <ul><li v-for="(s, i) in plan.suggestions || []" :key="i">{{ s }}</li></ul>
          </div>
        </template>
        <el-empty v-else-if="!planLoading" description="点击上方按钮，生成个性化辅导方案" :image-size="80" />
      </div>
    </div>

    <div class="page-card" style="margin-top: 16px">
      <el-tabs v-model="tab" @tab-change="switchTab">
        <el-tab-pane label="学习统计" name="stats">
          <el-row :gutter="16">
            <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#2F6FED,#1D4ED8)"><span>累计答题</span><span class="num">{{ stats.total_answered || 0 }}</span></div></el-col>
            <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#7FB0F5,#2F6FED)"><span>答对题数</span><span class="num">{{ stats.correct_count || 0 }}</span></div></el-col>
            <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#3E76E8,#1E3A8A)"><span>正确率</span><span class="num">{{ ((stats.accuracy || 0) * 100).toFixed(1) }}%</span></div></el-col>
            <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#43B97F,#2E9E6B)"><span>涉及知识点</span><span class="num">{{ (stats.knowledge_mastery || []).length }}</span></div></el-col>
          </el-row>
          <el-row :gutter="16" style="margin-top: 16px">
            <el-col :span="12"><div id="radarChart" style="height: 320px"></div></el-col>
            <el-col :span="12"><div id="activityChart" style="height: 320px"></div></el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane label="错题本" name="wrong">
          <el-table :data="wrongItems" stripe>
            <el-table-column label="题目" min-width="260">
              <template #default="{ row }">
                <div>{{ row.exercise.content }}</div>
                <el-tag v-for="kp in row.exercise.knowledge_points || []" :key="kp" size="small" type="info" style="margin-right:4px">{{ kp }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="加入时间" width="170"><template #default="{ row }">{{ fmtTime(row.created_at) }}</template></el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button type="primary" link @click="viewWrong(row)">查看原题</el-button>
                <el-button type="danger" link @click="removeWrong(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!wrongItems.length" description="暂无错题，继续保持！" />

          <el-dialog v-model="wrongDialog" title="原题与正确答案" width="640px">
            <template v-if="currentWrong">
              <div class="wrong-detail">
                <p><b>题目：</b>{{ currentWrong.exercise.content }}</p>
                <p v-if="(currentWrong.exercise.options || []).length"><b>选项：</b>{{ currentWrong.exercise.options.map((o) => o.key + '. ' + o.text).join('　') }}</p>
                <p><b>正确答案：</b>{{ currentWrong.exercise.answer }}</p>
                <p v-if="currentWrong.exercise.analysis"><b>解析：</b>{{ currentWrong.exercise.analysis }}</p>
                <p v-if="currentWrong.reason"><b>错因：</b>{{ currentWrong.reason }}</p>
                <div style="margin-top: 10px">
                  <el-tag v-for="kp in currentWrong.exercise.knowledge_points || []" :key="kp" size="small" type="info" style="margin-right:4px">{{ kp }}</el-tag>
                </div>
              </div>
            </template>
            <template #footer><el-button @click="wrongDialog = false">关闭</el-button></template>
          </el-dialog>
        </el-tab-pane>

        <el-tab-pane label="学习记录" name="records">
          <div style="display:flex; gap:10px; margin-bottom: 12px">
            <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" @change="loadTimeline" />
          </div>
          <el-timeline style="padding-left: 6px">
            <el-timeline-item v-for="(item, i) in timeline" :key="i" :timestamp="fmtTime(item.time)" :color="typeMeta[item.type]?.color" placement="top">
              <div>
                <el-tag size="small" style="border:none; background:#E9ECF2; color:#2F6FED">{{ typeMeta[item.type]?.label }}</el-tag>
                <span style="margin-left:6px">{{ item.title }}</span>
                <el-tag v-if="item.type === 'exercise'" size="small" :type="item.is_correct ? 'success' : 'danger'" style="margin-left:6px">{{ item.is_correct ? '正确' : '错误' }}</el-tag>
              </div>
              <div class="gray">{{ item.detail }}</div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-if="!timeline.length" description="暂无记录" />
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<style scoped>
.plan-card h3 { margin-bottom: 4px; }
.plan-progress { color: #2F6FED; font-size: 14px; padding: 20px 0; text-align: center; }
.plan-date { color: #909399; font-size: 13px; margin-bottom: 12px; }
.gray { color: #909399; font-size: 13px; }
.plan-section { margin-bottom: 14px; }
.plan-section h4 { margin-bottom: 6px; color: #1D4ED8; }
.plan-section ul { padding-left: 22px; }
.plan-section li { margin: 3px 0; }
.wrong-detail p { line-height: 1.7; margin: 6px 0; }
</style>