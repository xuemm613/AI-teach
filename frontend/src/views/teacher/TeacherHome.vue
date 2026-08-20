<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getTeacherDashboard } from '@/api/user'

const router = useRouter()
const data = ref({ user: {}, today_schedule: [] })
const loading = ref(true)

const quickLinks = [
  { path: '/teacher/lesson', title: '智能备课', icon: 'Document', color: '#8B5CF6' },
  { path: '/teacher/knowledge', title: '知识点检索/知识库', icon: 'FolderOpened', color: '#43B97F' },
  { path: '/teacher/classes', title: '查看班级学情', icon: 'School', color: '#E6A23C' }
]

const classColors = ['#8B5CF6', '#F97316', '#43B97F', '#2F6FED', '#E6A23C']
function classColor(id) { return classColors[id % classColors.length] }
const sortedSchedule = computed(() => [...(data.value.today_schedule || [])].sort((a, b) => a.period - b.period))

onMounted(async () => {
  try {
    data.value = await getTeacherDashboard()
  } finally { loading.value = false }
})
</script>

<template>
  <div v-loading="loading">
    <el-row :gutter="16">
      <el-col :span="7">
        <div class="page-card profile-card">
          <el-avatar :size="72" :src="data.user?.avatar || undefined">{{ (data.user?.full_name || data.user?.username || 'U').slice(0, 1) }}</el-avatar>
          <div class="name">{{ data.user?.full_name || data.user?.username }}</div>
          <div class="meta">
            <div>职称：{{ data.user?.title || '-' }}　教研组：{{ data.user?.department || '-' }}</div>
            <div>工号：{{ data.user?.employee_no || '-' }}</div>
          </div>
          <el-button size="small" plain style="margin-top:10px" @click="router.push('/teacher/profile')">编辑资料</el-button>
        </div>
      </el-col>
      <el-col :span="17">
        <el-row :gutter="16">
          <el-col :span="6"><div class="stat-card" style="background:#FFFFFF;color:#303133"><div class="stat-icon" style="background:#E9ECF2;color:#2F6FED"><el-icon :size="24"><School /></el-icon></div><div class="stat-info"><span>所带班级</span><span class="num">{{ data.class_count || 0 }}</span></div></div></el-col>
          <el-col :span="6"><div class="stat-card" style="background:#FFFFFF;color:#303133"><div class="stat-icon" style="background:#ECF8F1;color:#43B97F"><el-icon :size="24"><UserFilled /></el-icon></div><div class="stat-info"><span>学生总数</span><span class="num">{{ data.student_count || 0 }}</span></div></div></el-col>
          <el-col :span="6"><div class="stat-card" style="background:#FFFFFF;color:#303133"><div class="stat-icon" style="background:#FDF6EC;color:#E6A23C"><el-icon :size="24"><DataAnalysis /></el-icon></div><div class="stat-info"><span>班级平均正确率</span><span class="num">{{ ((data.accuracy || 0) * 100).toFixed(1) }}%</span></div></div></el-col>
          <el-col :span="6"><div class="stat-card" style="background:#FFFFFF;color:#303133"><div class="stat-icon" style="background:#FDECEC;color:#F56C6C"><el-icon :size="24"><Document /></el-icon></div><div class="stat-info"><span>累计答题</span><span class="num">{{ data.total_answered || 0 }}</span></div></div></el-col>
        </el-row>
        <el-row :gutter="16" style="margin-top: 16px">
          <el-col v-for="q in quickLinks" :key="q.path" :span="8">
            <div class="quick" @click="router.push(q.path)">
              <el-icon :size="30" :color="q.color"><component :is="q.icon" /></el-icon>
              <div class="q-title">{{ q.title }}</div>
            </div>
          </el-col>
        </el-row>
      </el-col>
    </el-row>

    <div class="page-card" style="margin-top: 16px">
      <h3 style="margin-bottom: 12px">今日安排</h3>
      <el-empty v-if="!data.today_schedule?.length" description="今天暂无课程安排" :image-size="70" />
      <div v-else class="schedule-list">
        <div v-for="(row, i) in sortedSchedule" :key="i" class="schedule-item">
          <span class="period-badge">{{ row.period }}</span>
          <span class="schedule-subject">{{ row.subject }}</span>
          <span class="schedule-period">第 {{ row.period }} 节</span>
          <el-tag :color="classColor(row.class_id)" effect="dark" style="color:#fff;border:none;margin-left:auto">{{ row.class_name }}</el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stat-card { flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 16px; min-height: 168px; }
.stat-icon { width: 40px; height: 40px; border-radius: 10px; background: #E9ECF2; color: #2F6FED; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.stat-info { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 2px; min-width: 0; }
.stat-info span:first-child { font-size: 16px; }
.stat-info .num { font-size: 30px; }
.profile-card { text-align: center; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.name { font-size: 18px; font-weight: 700; margin: 10px 0 4px; }
.meta { color: #909399; font-size: 13px; line-height: 1.9; }
.quick { text-align: center; padding: 20px 8px; min-height: 100px; display: flex; flex-direction: column; align-items: center; justify-content: center; border: 1px solid #D0D5DD; border-radius: 8px; cursor: pointer; transition: all .2s; background: #fff; }
.quick:hover { border-color: #9AA4B2; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.q-title { font-weight: 600; margin-top: 8px; }
.gray { color: #909399; font-size: 13px; }
.schedule-list { display: flex; flex-direction: column; gap: 12px; }
.schedule-item { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border: 1px solid #F0F2F5; border-radius: 10px; background: #FAFBFC; }
.period-badge { width: 34px; height: 34px; border-radius: 50%; background: linear-gradient(135deg, #8B5CF6, #6D28D9); color: #fff; font-weight: 700; font-size: 15px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.schedule-subject { font-weight: 600; color: #303133; font-size: 15px; }
.schedule-period { color: #909399; font-size: 13px; }
</style>
