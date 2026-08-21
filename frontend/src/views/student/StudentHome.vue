<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getDashboard, getTodaySchedule, getWeekSchedule } from '@/api/user'

const router = useRouter()
const data = ref({ user: {}, classes: [], today_tasks: {},
  total_answered: 0, correct_count: 0, accuracy: 0, subject_count: 0,
  total_percent: 0, weekly_seconds: 0 })
const todaySchedule = ref([])
const weekSchedule = ref([])
const loading = ref(true)
const view = ref('today') // 'today' | 'week'

const weekNames = ['周一', '周二', '周三', '周四', '周五']
const weekdayNow = new Date().getDay() === 0 ? 7 : new Date().getDay() // isoweekday（周一=1 ... 周日=7）

// 科目配色：与管理员端课表完全一致
const subjectColors = {
  '语文': '#e6a23c', '数学': '#409eff', '英语': '#67c23a', '物理': '#909399',
  '化学': '#fa541c', '生物': '#67c23a', '政治': '#f56c6c', '地理': '#36cfc9',
  '历史': '#722ed1', '体育': '#fa8c16', '音乐': '#eb2f96', '美术': '#13c2c2', '劳动': '#8c8c8c'
}
function subjectColor(s) { return subjectColors[s] || '#8B5CF6' }

// 学习数据（附加在左侧个人信息卡底部，仿个人信息卡风格）
const statRows = computed(() => [
  { title: '累计答题', value: data.value.total_answered || 0, suffix: '题', icon: 'EditPen', bg: 'bg-icon-info' },
  { title: '答对题数', value: data.value.correct_count || 0, suffix: '题', icon: 'SuccessFilled', bg: 'bg-icon-success' },
  { title: '正确率', value: ((data.value.accuracy || 0) * 100).toFixed(1), suffix: '%', icon: 'TrendCharts', bg: 'bg-icon-orange2' },
  { title: '涉及知识点', value: data.value.subject_count || 0, suffix: '个', icon: 'Collection', bg: 'bg-icon-purple' }
])

// 顶部功能入口（顶替原先一行四个统计卡的位置）
const quickTop = [
  { path: '/student/chat', title: '智能问答', icon: 'ChatDotRound', bg: 'bg-icon-purple' },
  { path: '/student/analysis', title: '学情分析', icon: 'DataAnalysis', bg: 'bg-icon-info' }
]

function go(q) {
  router.push(q.path)
}

// 本周课表：weekday → { period: course }，及最大节次
const weekMap = computed(() => {
  const m = {}
  for (const row of weekSchedule.value) {
    if (!m[row.weekday]) m[row.weekday] = {}
    m[row.weekday][row.period] = row
  }
  return m
})
const maxPeriod = computed(() => {
  let max = 0
  for (const row of weekSchedule.value) max = Math.max(max, row.period || 0)
  return Math.max(8, max)
})
const periodList = computed(() => {
  const arr = []
  for (let p = 1; p <= maxPeriod.value; p++) arr.push(p)
  return arr
})

const progressTip = computed(() => {
  const p = data.value.total_percent || 0
  if (p >= 100) return '已全部完成，真棒！'
  if (p > 0) return `完成 ${p}%，继续加油`
  return '暂无练习记录，去智能问答开始答题吧'
})

function fmtSeconds(s) {
  if (!s) return '0 分钟'
  const m = Math.round(s / 60)
  if (m < 60) return `${m} 分钟`
  return `${Math.floor(m / 60)} 小时 ${m % 60} 分钟`
}

onMounted(async () => {
  try {
    const [d, td, wk] = await Promise.all([getDashboard(), getTodaySchedule(), getWeekSchedule()])
    data.value = d
    todaySchedule.value = [...(td || [])].sort((a, b) => a.period - b.period)
    weekSchedule.value = wk || []
  } catch (e) {
    ElMessage.error('看板数据加载失败：' + (e.message || '未知错误'))
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-loading="loading">
    <el-row :gutter="16">
      <!-- 左：个人信息 + 学习进度 + 学习数据（单一面板） -->
      <el-col :xs="24" :sm="24" :md="8" :lg="7" class="row-stack">
        <div class="page-card profile-panel">
          <!-- 个人信息：头像左；姓名、学号、班级右对齐缩进 -->
          <div class="pp-head">
            <el-avatar :size="60" :src="data.user?.avatar || undefined" class="pp-avatar">
              {{ (data.user?.full_name || data.user?.username || 'U').slice(0, 1) }}
            </el-avatar>
            <div class="pp-id">
              <div class="pp-name">
                {{ data.user?.full_name || data.user?.username }}
                <el-tag size="small" effect="plain" type="warning" style="margin-left:6px">学生</el-tag>
              </div>
            </div>
          </div>
          <div class="pp-infor">
            <div class="pp-id-line">学号：{{ data.user?.student_no || '-' }}</div>
            <div class="pp-id-line">班级：{{ data.classes?.map((c) => c.class_name).join('、') || '未分班' }}</div>
          </div>
          <el-button plain size="small" class="pp-edit" @click="router.push('/student/profile')">
            <el-icon style="margin-right:4px"><Edit /></el-icon>编辑资料
          </el-button>

          <div class="pp-divider"></div>

          <!-- 学习进度概览 -->
          <div class="pp-section">
            <h3 class="card-title" style="margin:0 0 10px">学习进度概览</h3>
            <div class="progress-head">
              <span class="gray">总体完成度</span>
              <b class="progress-num">{{ data.total_percent || 0 }}%</b>
            </div>
            <el-progress :percentage="data.total_percent || 0" :stroke-width="8" :show-text="false" />
            <div class="progress-tip">{{ progressTip }}</div>
            <div class="pp-dashed"></div>
            <div class="progress-item">
              <span class="progress-label"><span class="stat-icon-sm bg-icon-warning"><el-icon><Odometer /></el-icon></span>本周学习时长</span>
              <b>{{ fmtSeconds(data.weekly_seconds) }}</b>
            </div>
            <div class="progress-item">
              <span class="progress-label"><span class="stat-icon-sm bg-icon-info"><el-icon><Clock /></el-icon></span>待完成练习</span>
              <b>{{ data.today_tasks?.pending_exercises || 0 }}</b>
            </div>
            <div class="progress-item">
              <span class="progress-label"><span class="stat-icon-sm bg-icon-danger"><el-icon><Warning /></el-icon></span>待复习错题</span>
              <b>{{ data.today_tasks?.wrong_review || 0 }}</b>
            </div>
          </div>

          <div class="pp-divider"></div>

          <!-- 学习数据（统计项，仿个人信息卡风格） -->
          <div class="pp-section">
            <h3 class="card-title" style="margin:0 0 4px">学习数据</h3>
            <div v-for="s in statRows" :key="s.title" class="info-item">
              <span class="info-icon" :class="s.bg"><el-icon><component :is="s.icon" /></el-icon></span>
              <div class="info-text">
                <span>{{ s.title }}</span>
                <b>{{ s.value }}<small class="stat-suffix">{{ s.suffix }}</small></b>
              </div>
            </div>
          </div>
        </div>
      </el-col>

      <!-- 右：功能入口 → 课程安排 -->
      <el-col :xs="24" :sm="24" :md="16" :lg="17" class="row-stack">
        <!-- 1. 功能入口（智能问答 / 学情分析，顶替原统计卡位置） -->
        <div class="func-row func-row-2">
          <div v-for="(q, i) in quickTop" :key="i" class="func-card" @click="go(q)">
            <span class="stat-icon-mc" :class="q.bg"><el-icon :size="24"><component :is="q.icon" /></el-icon></span>
            <div class="func-body">
              <div class="func-title">{{ q.title }}</div>
            </div>
            <el-icon class="func-arrow"><ArrowRight /></el-icon>
          </div>
        </div>

        <!-- 2. 课程安排：今日列表 / 本周网格表格 -->
        <div class="page-card">
          <div class="sched-head">
            <h3 class="card-title" style="margin:0">课程安排</h3>
            <el-radio-group v-model="view" size="small">
              <el-radio-button value="today">今日</el-radio-button>
              <el-radio-button value="week">本周</el-radio-button>
            </el-radio-group>
          </div>

          <template v-if="view === 'today'">
            <el-empty v-if="!todaySchedule.length" description="今天暂无课程，好好休息" :image-size="70" />
            <div v-else class="schedule-list">
              <div v-for="(row, i) in todaySchedule" :key="i" class="schedule-item st-item">
                <span class="period-badge" :style="{ background: subjectColor(row.subject) }">{{ row.period }}</span>
                <div class="sch-main">
                  <div class="sch-subject">{{ row.subject }}</div>
                  <div class="sch-sub">{{ row.teacher_name || '待定' }}</div>
                </div>
              </div>
            </div>
          </template>

          <template v-else>
            <el-empty v-if="!weekSchedule.length" description="本周暂无课程安排" :image-size="70" />
            <div v-else class="week-table">
              <div class="wt-head wt-corner">节次</div>
              <div v-for="(w, i) in weekNames" :key="w" class="wt-head" :class="{ 'is-today': (i + 1) === weekdayNow }">{{ w }}</div>

              <template v-for="p in periodList" :key="p">
                <div class="wt-period">{{ p }}</div>
                <div v-for="(w, i) in weekNames" :key="w" class="wt-cell" :class="{ 'is-today': (i + 1) === weekdayNow }">
                  <el-tooltip
                    v-if="weekMap[i + 1] && weekMap[i + 1][p]"
                    :content="weekMap[i + 1][p].teacher_name || '待定'"
                    placement="top"
                    effect="dark"
                  >
                    <span class="wt-subject" :style="{ background: subjectColor(weekMap[i + 1][p].subject) }">
                      {{ weekMap[i + 1][p].subject }}
                    </span>
                  </el-tooltip>
                </div>
              </template>
            </div>
          </template>
        </div>
      </el-col>
    </el-row>
  </div>
</template>
