<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { getDashboardStats } from '@/api/admin'

const stats = ref({})
let pieChart = null, lineChart = null, activeChart = null

function fmtDate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

// 取最近 7 天数据，没有数据的日期补 0（保证 7 个日期都显示）
function last7(items) {
  const map = {}
  ;(items || []).forEach((it) => { map[it.date] = it.count })
  const days = []
  const today = new Date()
  for (let i = 6; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(today.getDate() - i)
    const key = fmtDate(d)
    days.push({ date: key, label: key.slice(5), count: map[key] || 0 })
  }
  return days
}

function render() {
  pieChart = echarts.init(document.getElementById('roleChart'))
  lineChart = echarts.init(document.getElementById('dailyChart'))
  activeChart = echarts.init(document.getElementById('activeChart'))

  pieChart.setOption({
    title: { text: '用户角色分布', left: 20 },
    tooltip: { trigger: 'item' },
    legend: { orient: 'vertical', right: '6%', top: 'middle', itemGap: 28 },
    series: [{ type: 'pie', radius: ['45%', '65%'], center: ['42%', '54%'], color: ['#8B5CF6', '#67C23A', '#F97316'], data: [
      { name: '管理员', value: stats.value.admin_count || 0 },
      { name: '教师', value: stats.value.teacher_count || 0 },
      { name: '学生', value: stats.value.student_count || 0 }
    ] }]
  })

  const answers7 = last7(stats.value.daily_answers)
  lineChart.setOption({
    title: { text: '每日答题量（近7天）' },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: answers7.map((d) => d.label) },
    yAxis: { type: 'value' },
    series: [{ type: 'line', smooth: true, color: '#F97316', areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(249, 115, 22, 0.4)' }, { offset: 1, color: 'rgba(255, 255, 255, 0)' }]) }, data: answers7.map((d) => d.count) }]
  })

  const active7 = last7(stats.value.daily_active_users)
  activeChart.setOption({
    title: { text: '近7天活跃用户数' },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: active7.map((d) => d.label) },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', barWidth: '12%', itemStyle: { borderRadius: [8, 8, 0, 0], color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#8B5CF6' }, { offset: 1, color: '#C4B5FD' }]) }, data: active7.map((d) => d.count) }]
  })
}
function resize() { pieChart?.resize(); lineChart?.resize(); activeChart?.resize() }

onMounted(async () => {
  stats.value = await getDashboardStats()
  render()
  window.addEventListener('resize', resize)
})
onBeforeUnmount(() => { window.removeEventListener('resize', resize); pieChart?.dispose(); lineChart?.dispose(); activeChart?.dispose() })
</script>

<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="12">
        <el-row :gutter="16">
          <el-col :span="8"><div class="stat-card" style="background:#FFFFFF;color:#303133"><div class="stat-icon" style="background:#E9ECF2;color:#2F6FED"><el-icon :size="24"><User /></el-icon></div><div class="stat-info"><span>用户总数</span><span class="num">{{ stats.user_count || 0 }}</span></div></div></el-col>
          <el-col :span="8"><div class="stat-card" style="background:#FFFFFF;color:#303133"><div class="stat-icon" style="background:#ECF8F1;color:#43B97F"><el-icon :size="24"><ChatDotRound /></el-icon></div><div class="stat-info"><span>累计答题</span><span class="num">{{ stats.record_count || 0 }}</span></div></div></el-col>
          <el-col :span="8"><div class="stat-card" style="background:#FFFFFF;color:#303133"><div class="stat-icon" style="background:#FDF6EC;color:#E6A23C"><el-icon :size="24"><DataAnalysis /></el-icon></div><div class="stat-info"><span>总体正确率</span><span class="num">{{ ((stats.accuracy || 0) * 100).toFixed(1) }}%</span></div></div></el-col>
          <el-col :span="8" style="margin-top: 16px"><div class="stat-card" style="background:#FFFFFF;color:#303133"><div class="stat-icon" style="background:#FDECEC;color:#F56C6C"><el-icon :size="24"><Document /></el-icon></div><div class="stat-info"><span>教案数</span><span class="num">{{ stats.lesson_plan_count || 0 }}</span></div></div></el-col>
          <el-col :span="8" style="margin-top: 16px"><div class="stat-card" style="background:#FFFFFF;color:#303133"><div class="stat-icon" style="background:#FEF0E6;color:#FA8C16"><el-icon :size="24"><Odometer /></el-icon></div><div class="stat-info"><span>今日活跃</span><span class="num">{{ stats.active_users_today || 0 }}</span></div></div></el-col>
          <el-col :span="8" style="margin-top: 16px"><div class="stat-card" style="background:#FFFFFF;color:#303133"><div class="stat-icon" style="background:#F3EDFB;color:#722ED1"><el-icon :size="24"><FolderOpened /></el-icon></div><div class="stat-info"><span>知识库文档</span><span class="num">{{ stats.knowledge_file_count || 0 }}</span></div></div></el-col>
        </el-row>
      </el-col>
      <el-col :span="12" style="display:flex"><div class="page-card" style="flex:1;display:flex;flex-direction:column"><div id="roleChart" style="flex:1;min-height:220px"></div></div></el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="12"><div class="page-card"><div id="dailyChart" style="height: 320px"></div></div></el-col>
      <el-col :span="12"><div class="page-card"><div id="activeChart" style="height: 320px"></div></div></el-col>
    </el-row>
  </div>
</template>

<style scoped>
.stat-card { flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 16px; min-height: 168px; }
.stat-icon { width: 40px; height: 40px; border-radius: 10px; background: #E9ECF2; color: #2F6FED; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.stat-info { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 2px; min-width: 0; }
.stat-info span:first-child { font-size: 16px; }
.stat-info .num { font-size: 30px; }
</style>