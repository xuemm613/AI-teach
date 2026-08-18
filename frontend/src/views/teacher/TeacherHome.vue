<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getTeacherDashboard } from '@/api/user'

const router = useRouter()
const data = ref({ user: {}, today_schedule: [] })
const loading = ref(true)

const quickLinks = [
  { path: '/teacher/lesson', title: '智能备课', desc: 'AI 一键生成完整教案', icon: 'Document', color: '#a67b5b' },
  { path: '/teacher/knowledge', title: '知识点检索/知识库', desc: '上传教材讲义，RAG 入库', icon: 'FolderOpened', color: '#67c23a' },
  { path: '/teacher/classes', title: '查看班级学情', desc: '班级概览与学生画像', icon: 'School', color: '#e6a23c' }
]

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
          <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#a67b5b,#2f6fd0)"><span>所带班级</span><span class="num">{{ data.class_count || 0 }}</span></div></el-col>
          <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#c4a484,#a67b5b)"><span>学生总数</span><span class="num">{{ data.student_count || 0 }}</span></div></el-col>
          <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#8a6247,#6e4f38)"><span>班级平均正确率</span><span class="num">{{ ((data.accuracy || 0) * 100).toFixed(1) }}%</span></div></el-col>
          <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#b08968,#8a6247)"><span>累计答题</span><span class="num">{{ data.total_answered || 0 }}</span></div></el-col>
        </el-row>
        <el-row :gutter="16" style="margin-top: 16px">
          <el-col v-for="q in quickLinks" :key="q.path" :span="8">
            <div class="quick" @click="router.push(q.path)">
              <el-icon :size="30" :color="q.color"><component :is="q.icon" /></el-icon>
              <div class="q-title">{{ q.title }}</div>
              <div class="q-desc">{{ q.desc }}</div>
            </div>
          </el-col>
        </el-row>
      </el-col>
    </el-row>

    <div class="page-card" style="margin-top: 16px">
      <h3 style="margin-bottom: 12px">今日安排</h3>
      <el-empty v-if="!data.today_schedule?.length" description="今天暂无课程安排" :image-size="70" />
      <el-table v-else :data="data.today_schedule" stripe>
        <el-table-column label="节次" width="100">
          <template #default="{ row }">第 {{ row.period }} 节</template>
        </el-table-column>
        <el-table-column prop="class_name" label="班级" min-width="200" />
        <el-table-column prop="subject" label="科目" width="140" />
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.profile-card { text-align: center; }
.name { font-size: 18px; font-weight: 700; margin: 10px 0 4px; }
.meta { color: #909399; font-size: 13px; line-height: 1.9; }
.quick { text-align: center; padding: 16px 8px; border: 1px solid #e8dfce; border-radius: 8px; cursor: pointer; transition: all .2s; background: #fff; }
.quick:hover { border-color: #a67b5b; box-shadow: 0 2px 8px rgba(64,158,255,.2); }
.q-title { font-weight: 600; margin-top: 8px; }
.q-desc { font-size: 12px; color: #909399; margin-top: 4px; }
.gray { color: #909399; font-size: 13px; }
</style>
