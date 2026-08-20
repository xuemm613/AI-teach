<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { getStudentProfile } from '@/api/user'

const route = useRoute()
const router = useRouter()
const profile = ref(null)
const loading = ref(true)
const wrongDialog = ref(false)
const behaviorDialog = ref(false)
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
        series: [{
          type: 'radar',
          data: [{
            value: mastery.map((m) => m.mastery),
            name: '掌握度',
            areaStyle: { color: 'rgba(139, 92, 246, 0.25)' },
            lineStyle: { color: '#8B5CF6' },
            itemStyle: { color: '#8B5CF6' }
          }]
        }]
      })
    }
    if (activity.length && document.getElementById('trendChart')) {
      trend = echarts.init(document.getElementById('trendChart'))
      trend.setOption({
        title: { text: '最近30天学习活跃度' },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: activity.map((d) => d.date) },
        yAxis: { type: 'value' },
        series: [{
          type: 'line', smooth: true,
          color: '#F97316',
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(249, 115, 22, 0.4)' }, { offset: 1, color: 'rgba(255, 255, 255, 0)' }]) },
          data: activity.map((d) => d.count)
        }]
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
      <div style="margin-bottom: 12px">
        <el-button @click="router.back()">← 返回班级</el-button>
      </div>
      <el-row :gutter="16">
        <el-col :span="10">
          <div class="page-card info-card">
            <h3 style="margin-bottom: 14px">学生基础信息</h3>
            <div class="info-list">
              <div class="info-item">
                <div class="info-icon" style="background:#E9ECF2;color:#2F6FED"><el-icon><User /></el-icon></div>
                <div class="info-text"><span>姓名</span><b>{{ profile.student.full_name }}</b></div>
              </div>
              <div class="info-item">
                <div class="info-icon" style="background:#F3EDFB;color:#722ED1"><el-icon><Postcard /></el-icon></div>
                <div class="info-text"><span>学号</span><b>{{ profile.student.student_no || '-' }}</b></div>
              </div>
              <div class="info-item">
                <div class="info-icon" style="background:#ECF8F1;color:#43B97F"><el-icon><Reading /></el-icon></div>
                <div class="info-text"><span>年级</span><b>{{ profile.student.grade || '-' }}</b></div>
              </div>
              <div class="info-item">
                <div class="info-icon" style="background:#FDF6EC;color:#E6A23C"><el-icon><School /></el-icon></div>
                <div class="info-text"><span>班级</span><b>{{ profile.classes.map((c) => c.class_name).join('、') || '-' }}</b></div>
              </div>
              <div class="info-item">
                <div class="info-icon" style="background:#FDECEC;color:#F56C6C"><el-icon><DataAnalysis /></el-icon></div>
                <div class="info-text"><span>30天答题</span><b>{{ profile.total_answered_30d }}</b></div>
              </div>
            </div>
          </div>
          <div class="info-modules">
            <div class="info-module" @click="wrongDialog = true">
              <el-icon :size="24" color="#F56C6C"><WarningFilled /></el-icon>
              <span>错题历史</span>
            </div>
            <div class="info-module" @click="behaviorDialog = true">
              <el-icon :size="24" color="#8B5CF6"><Histogram /></el-icon>
              <span>学习行为记录</span>
            </div>
          </div>
        </el-col>
        <el-col :span="14">
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

      <el-dialog v-model="wrongDialog" title="错题历史" width="640px">
        <div v-for="w in profile.wrong_history" :key="w.id" class="wrong-item">
          <div class="w-title">{{ w.exercise.content }}</div>
          <div class="w-meta">正确答案：{{ w.exercise.answer }}</div>
        </div>
        <el-empty v-if="!profile.wrong_history.length" description="暂无错题" :image-size="60" />
        <template #footer><el-button @click="wrongDialog = false">关闭</el-button></template>
      </el-dialog>

      <el-dialog v-model="behaviorDialog" title="学习行为记录" width="640px">
        <div v-for="(b, i) in profile.behavior_records" :key="i" class="wrong-item">
          <div class="w-title">
            {{ b.content }}
            <el-tag size="small" :type="b.is_correct ? 'success' : 'danger'">{{ b.is_correct ? '答对' : '答错' }}</el-tag>
          </div>
          <div class="w-meta">{{ new Date(b.time).toLocaleString() }}</div>
        </div>
        <el-empty v-if="!profile.behavior_records.length" description="暂无行为记录" :image-size="60" />
        <template #footer><el-button @click="behaviorDialog = false">关闭</el-button></template>
      </el-dialog>
    </template>
  </div>
</template>

<style scoped>
.info-list { display: flex; flex-direction: column; }
.info-item { display: flex; align-items: center; gap: 14px; padding: 14px 0; border-bottom: 1px solid #F0F2F5; }
.info-item:last-child { border-bottom: none; }
.info-icon { width: 42px; height: 42px; border-radius: 12px; font-size: 21px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.info-text { display: flex; flex-direction: column; gap: 3px; }
.info-text span { font-size: 13px; color: #909399; }
.info-text b { font-size: 16px; color: #303133; font-weight: 600; }
.info-modules { display: flex; gap: 12px; margin-top: 16px; }
.info-module { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; padding: 16px 8px; border: 1px solid #D0D5DD; border-radius: 8px; cursor: pointer; transition: all .2s; background: #fff; }
.info-module:hover { border-color: #C4B5FD; box-shadow: 0 2px 8px rgba(139, 92, 246, 0.12); }
.info-module span { font-weight: 600; font-size: 14px; color: #303133; }
.wrong-item { padding: 8px 0; border-bottom: 1px solid #DEE3EA; }
.w-title { font-size: 14px; }
.w-meta { color: #909399; font-size: 12px; margin-top: 2px; }
</style>
