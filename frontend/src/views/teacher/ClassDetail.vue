<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'
import { getClassDetail, removeClassStudent } from '@/api/user'

const route = useRoute()
const router = useRouter()
const detail = ref(null)
const loading = ref(true)

async function load() {
  loading.value = true
  try { detail.value = await getClassDetail(route.params.id) } finally { loading.value = false }
}

async function removeStudent(sid) {
  await ElMessageBox.confirm('确定将该学生移出班级吗？', '提示', { type: 'warning' })
  await removeClassStudent(route.params.id, sid)
  ElMessage.success('已移出班级')
  await load()
}

async function exportReport() {
  const blob = await request.get(`/users/me/classes/${route.params.id}/report/export`, { responseType: 'blob' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${detail.value.name}_学习报告.docx`
  a.click()
  window.URL.revokeObjectURL(url)
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <template v-if="detail">
      <div class="page-card">
        <div style="display:flex; justify-content:space-between; align-items:center">
          <div>
            <h3>{{ detail.name }}</h3>
            <span class="gray">编号：{{ detail.class_no || '-' }} · {{ detail.grade || '-' }} · 班主任：{{ detail.teacher_name || '-' }}</span>
          </div>
          <div>
            <el-button type="primary" plain @click="router.push('/teacher/classes')">返回列表</el-button>
            <el-button type="success" @click="exportReport">生成班级学习报告（Word）</el-button>
          </div>
        </div>
        <el-row :gutter="16" style="margin-top: 16px">
          <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#a67b5b,#2f6fd0)"><span>学生人数</span><span class="num">{{ detail.student_count }}</span></div></el-col>
          <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#c4a484,#a67b5b)"><span>累计答题</span><span class="num">{{ detail.total_answered }}</span></div></el-col>
          <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#8a6247,#6e4f38)"><span>平均正确率</span><span class="num">{{ (detail.accuracy * 100).toFixed(1) }}%</span></div></el-col>
          <el-col :span="6"><div class="stat-card" style="background: linear-gradient(135deg,#b08968,#8a6247)"><span>薄弱知识点</span><span class="num" style="font-size:20px">{{ detail.weak_top?.length || 0 }} 个</span></div></el-col>
        </el-row>
      </div>

      <div class="page-card" style="margin-top: 16px">
        <h3 style="margin-bottom: 12px">薄弱知识点 TOP5</h3>
        <el-tag v-for="w in detail.weak_top" :key="w.knowledge_point" type="danger" size="large" style="margin:4px">{{ w.knowledge_point }}（{{ w.count }}次）</el-tag>
        <span v-if="!detail.weak_top?.length" class="gray">暂无数据</span>
      </div>

      <div class="page-card" style="margin-top: 16px">
        <h3 style="margin-bottom: 12px">班级学生列表</h3>
        <el-table :data="detail.students" stripe>
          <el-table-column prop="full_name" label="姓名" width="130" />
          <el-table-column prop="student_no" label="学号" width="130" />
          <el-table-column prop="answered" label="答题数" width="90" />
          <el-table-column label="正确率" width="160">
            <template #default="{ row }"><el-progress :percentage="Number((row.accuracy * 100).toFixed(1))" :stroke-width="12" /></template>
          </el-table-column>
          <el-table-column label="最近学习状态" min-width="170">
            <template #default="{ row }">
              <span v-if="row.last_active">{{ new Date(row.last_active).toLocaleString() }}</span>
              <span v-else class="gray">暂无记录</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button type="primary" link @click="router.push(`/teacher/students/${row.student_id}`)">学情分析</el-button>
              <el-button type="danger" link @click="removeStudent(row.student_id)">移出班级</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.gray { color: #909399; font-size: 13px; }
</style>