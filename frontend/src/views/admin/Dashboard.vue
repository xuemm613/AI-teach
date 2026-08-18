<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { getDashboardStats } from '@/api/admin'

const stats = ref({})
let pieChart = null, lineChart = null, activeChart = null

function render() {
  pieChart = echarts.init(document.getElementById('roleChart'))
  lineChart = echarts.init(document.getElementById('dailyChart'))
  activeChart = echarts.init(document.getElementById('activeChart'))

  pieChart.setOption({
    title: { text: '用户角色分布' },
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{ type: 'pie', radius: ['40%', '68%'], data: [
      { name: '管理员', value: stats.value.admin_count || 0 },
      { name: '教师', value: stats.value.teacher_count || 0 },
      { name: '学生', value: stats.value.student_count || 0 }
    ] }]
  })
  lineChart.setOption({
    title: { text: '每日答题量（近30天）' },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: (stats.value.daily_answers || []).map((d) => d.date) },
    yAxis: { type: 'value' },
    series: [{ type: 'line', smooth: true, areaStyle: {}, data: (stats.value.daily_answers || []).map((d) => d.count) }]
  })
  activeChart.setOption({
    title: { text: '近7天活跃用户数' },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: (stats.value.daily_active_users || []).map((d) => d.date) },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', barWidth: '40%', data: (stats.value.daily_active_users || []).map((d) => d.count) }]
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
      <el-col :span="4"><div class="stat-card" style="background: linear-gradient(135deg,#a67b5b,#2f6fd0)"><span>用户总数</span><span class="num">{{ stats.user_count || 0 }}</span></div></el-col>
      <el-col :span="4"><div class="stat-card" style="background: linear-gradient(135deg,#c4a484,#a67b5b)"><span>累计答题</span><span class="num">{{ stats.record_count || 0 }}</span></div></el-col>
      <el-col :span="4"><div class="stat-card" style="background: linear-gradient(135deg,#8a6247,#6e4f38)"><span>总体正确率</span><span class="num">{{ ((stats.accuracy || 0) * 100).toFixed(1) }}%</span></div></el-col>
      <el-col :span="4"><div class="stat-card" style="background: linear-gradient(135deg,#b08968,#8a6247)"><span>教案数</span><span class="num">{{ stats.lesson_plan_count || 0 }}</span></div></el-col>
      <el-col :span="4"><div class="stat-card" style="background: linear-gradient(135deg,#b08968,#8a6247)"><span>今日活跃</span><span class="num">{{ stats.active_users_today || 0 }}</span></div></el-col>
      <el-col :span="4"><div class="stat-card" style="background: linear-gradient(135deg,#a67b5b,#7e5a3f)"><span>知识库文档</span><span class="num">{{ stats.knowledge_file_count || 0 }}</span></div></el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="8"><div class="page-card"><div id="roleChart" style="height: 320px"></div></div></el-col>
      <el-col :span="16"><div class="page-card"><div id="dailyChart" style="height: 320px"></div></div></el-col>
    </el-row>
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="24"><div class="page-card"><div id="activeChart" style="height: 320px"></div></div></el-col>
    </el-row>
  </div>
</template>