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
      plan.value = task.output || {}
      planDate.value = task.created_at || ''
      ElMessage.success('个性化方案已生成')
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
  exercise: { label: '做了题', color: '#a67b5b' },
  question: { label: '问了问题', color: '#8a6247' },
  collect: { label: '收藏错题', color: '#a67b5b' }
}

onMounted(() => {
  loadStats().catch((e) => console.warn('学习统计加载失败', e))
  loadLatestPlan()
  window.addEventListener('resize', resize)
})
onBeforeUnmount(() => { window.removeEventListener('resize', resize); radar?.dispose(); activity?.dispose() })
</script>

<template>
  <div>
    <div class="page-card plan-card">
      <div style="display:flex; justify-content:space-between; align-items:center">
        <div>
          <h3>个性化学习辅导（AI Agent）</h3>
        </div>
        <el-button type="primary" size="large" :loading="generating" @click="genPlan">生成我的辅导方案</el-button>
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
            <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#a67b5b,#7e5a3f)"><span>累计答题</span><span class="num">{{ stats.total_answered || 0 }}</span></div></el-col>
            <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#c4a484,#a67b5b)"><span>答对题数</span><span class="num">{{ stats.correct_count || 0 }}</span></div></el-col>
            <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#8a6247,#6e4f38)"><span>正确率</span><span class="num">{{ ((stats.accuracy || 0) * 100).toFixed(1) }}%</span></div></el-col>
            <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#b08968,#8a6247)"><span>涉及知识点</span><span class="num">{{ (stats.knowledge_mastery || []).length }}</span></div></el-col>
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
            <el-table-column label="正确答案" width="140"><template #default="{ row }">{{ row.exercise.answer }}</template></el-table-column>
            <el-table-column label="加入时间" width="170"><template #default="{ row }">{{ fmtTime(row.created_at) }}</template></el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }"><el-button type="danger" link @click="removeWrong(row.id)">已掌握/删除</el-button></template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!wrongItems.length" description="暂无错题，继续保持！" />
        </el-tab-pane>

        <el-tab-pane label="学习记录" name="records">
          <div style="display:flex; gap:10px; margin-bottom: 12px">
            <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" @change="loadTimeline" />
          </div>
          <el-timeline style="padding-left: 6px">
            <el-timeline-item v-for="(item, i) in timeline" :key="i" :timestamp="fmtTime(item.time)" :color="typeMeta[item.type]?.color" placement="top">
              <div>
                <el-tag size="small" style="border:none; background:#f4ebdd; color:#a67b5b">{{ typeMeta[item.type]?.label }}</el-tag>
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
.plan-progress { color: #a67b5b; font-size: 14px; padding: 20px 0; text-align: center; }
.plan-date { color: #909399; font-size: 13px; margin-bottom: 12px; }
.gray { color: #909399; font-size: 13px; }
.plan-section { margin-bottom: 14px; }
.plan-section h4 { margin-bottom: 6px; color: #7e5a3f; }
.plan-section ul { padding-left: 22px; }
.plan-section li { margin: 3px 0; }
</style>