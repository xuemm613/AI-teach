<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getDashboard, getTodaySchedule } from '@/api/user'

const router = useRouter()
const data = ref({ user: {}, classes: [], total_percent: 0, weekly_seconds: 0 })
const schedule = ref([])
const loading = ref(true)

function fmtSeconds(s) {
  if (!s) return '0 分钟'
  const m = Math.round(s / 60)
  if (m < 60) return `${m} 分钟`
  return `${Math.floor(m / 60)} 小时 ${m % 60} 分钟`
}

onMounted(async () => {
  try {
    const [d, sc] = await Promise.all([getDashboard(), getTodaySchedule()])
    data.value = d
    schedule.value = sc || []
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
      <el-col :span="8">
        <div class="page-card profile-card">
          <el-avatar :size="72" :src="data.user?.avatar || undefined">{{ (data.user?.full_name || data.user?.username || 'U').slice(0, 1) }}</el-avatar>
          <div class="name">{{ data.user?.full_name || data.user?.username }}</div>
          <div class="meta">
            <div>年级：{{ data.user?.grade || '-' }}　　学号：{{ data.user?.student_no || '-' }}</div>
            <div>班级：{{ data.classes?.map((c) => c.class_name).join('、') || '未分班' }}</div>
          </div>
          <el-button type="primary" size="small" plain style="margin-top: 10px" @click="router.push('/student/profile')">编辑资料</el-button>
        </div>
        <div class="page-card" style="margin-top: 16px">
          <h4 style="margin-bottom: 10px">学习进度概览</h4>
          <div class="task-row"><span>总体完成度</span><b>{{ data.total_percent || 0 }}%</b></div>
          <div class="task-row"><span>本周学习时长</span><b>{{ fmtSeconds(data.weekly_seconds) }}</b></div>
        </div>
      </el-col>

      <el-col :span="16">
        <div class="page-card">
          <h3 style="margin-bottom: 12px">今日课程安排</h3>
          <el-empty v-if="!schedule.length" description="今天暂无课程" :image-size="70" />
          <el-table v-else :data="schedule" stripe class="schedule-table">
            <el-table-column label="节次" width="110">
              <template #default="{ row }">第 {{ row.period }} 节</template>
            </el-table-column>
            <el-table-column prop="subject" label="科目" width="170" />
            <el-table-column prop="class_name" label="班级" width="220" />
            <el-table-column prop="teacher_name" label="任课老师" min-width="160" />
          </el-table>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.profile-card { text-align: center; }
.name { font-size: 18px; font-weight: 700; margin: 10px 0 4px; }
.meta { color: #909399; font-size: 13px; line-height: 1.9; }
.task-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; color: #303133; }
.schedule-table .el-table__cell { padding: 10px 0; }
.schedule-table .cell { padding: 0 16px; }
</style>
