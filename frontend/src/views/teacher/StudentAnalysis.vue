<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { getStudentProfile } from '@/api/user'

const route = useRoute()
const profile = ref(null)
const loading = ref(true)
let radar = null
let trend = null

function render() {
  // 数据不足或容器未就绪时跳过，避免图表初始化报错导致整页空白
  try {
    const mastery = profile.value?.knowledge_mastery || []
    const activity = profile.value?.activity_30d || []
    if (mastery.length && document.getElementById('masteryChart')) {
      radar = echarts.init(document.getElementById('masteryChart'))
      radar.setOption({
        title: { text: '各知识点掌握度' },
        tooltip: {},
        radar: { indicator: mastery.map((m) => ({ name: m.knowledge_point, max: 100 })) },
        series: [{ type: 'radar', data: [{ value: mastery.map((m) => m.mastery), name: '掌握度' }] }]
      })
    }
    if (activity.length && document.getElementById('trendChart')) {
      trend = echarts.init(document.getElementById('trendChart'))
      trend.setOption({
        title: { text: '最近30天学习活跃度' },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: activity.map((d) => d.date) },
        yAxis: { type: 'value' },
        series: [{ type: 'line', smooth: true, areaStyle: {}, data: activity.map((d) => d.count) }]
      })
    }
  } catch (e) {
    console.error('学情图表渲染失败：', e)
  }
}
function resize() { radar?.resize(); trend?.resize() }

async function load() {
  loading.value = true
  try {
    profile.value = await getStudentProfile(route.params.id)
    // 等 DOM 渲染出图表容器后再初始化，否则右侧图表无法显示
    await nextTick()
    render()
  } finally { loading.value = false }
}

onMounted(load)
onBeforeUnmount(() => { window.removeEventListener('resize', resize); radar?.dispose(); trend?.dispose() })
</script>

<template>
  <div v-loading="loading">
    <template v-if="profile">
      <el-row :gutter="16">
        <el-col :span="8">
          <div class="page-card">
            <h3 style="margin-bottom: 14px">学生基础信息</h3>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="姓名">{{ profile.student.full_name }}</el-descriptions-item>
              <el-descriptions-item label="学号">{{ profile.student.student_no || '-' }}</el-descriptions-item>
              <el-descriptions-item label="年级">{{ profile.student.grade || '-' }}</el-descriptions-item>
              <el-descriptions-item label="班级">{{ profile.classes.map((c) => c.class_name).join('、') || '-' }}</el-descriptions-item>
              <el-descriptions-item label="30天答题">{{ profile.total_answered_30d }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </el-col>
        <el-col :span="16">
          <div class="page-card">
            <el-empty v-if="!(profile.knowledge_mastery || []).length" description="暂无知识点掌握数据" :image-size="60" />
            <div v-else id="masteryChart" style="height: 320px"></div>
          </div>
          <div class="page-card" style="margin-top: 16px">
            <el-empty v-if="!(profile.activity_30d || []).length" description="暂无学习活跃数据" :image-size="60" />
            <div v-else id="trendChart" style="height: 280px"></div>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="16" style="margin-top: 16px">
        <el-col :span="12">
          <div class="page-card">
            <h3 style="margin-bottom: 12px">错题历史（{{ profile.wrong_history.length }}）</h3>
            <div v-for="w in profile.wrong_history" :key="w.id" class="wrong-item">
              <div class="w-title">{{ w.exercise.content }}</div>
              <div class="w-meta">正确答案：{{ w.exercise.answer }}　错因：{{ w.reason || '未分析' }}</div>
            </div>
            <el-empty v-if="!profile.wrong_history.length" description="暂无错题" :image-size="60" />
          </div>
        </el-col>
        <el-col :span="12">
          <div class="page-card">
            <h3 style="margin-bottom: 12px">学习行为记录（最近 30 条）</h3>
            <div v-for="(b, i) in profile.behavior_records" :key="i" class="wrong-item">
              <div class="w-title">
                {{ b.content }}
                <el-tag size="small" :type="b.is_correct ? 'success' : 'danger'">{{ b.is_correct ? '答对' : '答错' }}</el-tag>
              </div>
              <div class="w-meta">{{ new Date(b.time).toLocaleString() }}</div>
            </div>
            <el-empty v-if="!profile.behavior_records.length" description="暂无行为记录" :image-size="60" />
          </div>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<style scoped>
.wrong-item { padding: 8px 0; border-bottom: 1px solid #f5efe6; }
.w-title { font-size: 14px; }
.w-meta { color: #909399; font-size: 12px; margin-top: 2px; }
</style>
