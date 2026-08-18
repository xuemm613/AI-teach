<script setup>
import { onMounted, reactive, ref } from 'vue'
import { listLoginLogs } from '@/api/admin'

const logs = ref([])
const logTotal = ref(0)
const logQuery = reactive({ page: 1, size: 30 })
const logLoading = ref(false)

async function loadLogs() {
  logLoading.value = true
  try {
    const data = await listLoginLogs(logQuery)
    logs.value = data.items
    logTotal.value = data.total
  } finally { logLoading.value = false }
}

function fmtTime(t) {
  if (!t) return '-'
  const d = new Date(t)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

onMounted(loadLogs)
</script>

<template>
  <div class="page-card">
    <h3 style="margin-bottom: 12px">系统登录记录</h3>
    <el-table :data="logs" v-loading="logLoading" stripe>
      <el-table-column label="时间" width="180">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="登录用户（工号/学号 + 姓名）" min-width="240">
        <template #default="{ row }">{{ row.detail || row.username || '-' }}</template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!logs.length && !logLoading" description="暂无登录记录" :image-size="60" />
    <el-pagination style="margin-top:16px; justify-content:flex-end" layout="total, prev, pager, next" :total="logTotal" :page-size="logQuery.size" v-model:current-page="logQuery.page" @current-change="loadLogs" />
  </div>
</template>
