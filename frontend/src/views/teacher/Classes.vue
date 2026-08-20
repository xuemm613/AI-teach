<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getMyClasses } from '@/api/user'

const router = useRouter()
const classes = ref([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try { classes.value = await getMyClasses() } finally { loading.value = false }
})
</script>

<template>
  <div class="page-card" v-loading="loading">
    <h3 style="margin-bottom: 16px">我所带的班级（{{ classes.length }}）</h3>
    <el-row :gutter="16">
      <el-col v-for="c in classes" :key="c.id" :span="8" style="margin-bottom: 16px">
        <el-card shadow="hover" class="class-card" @click="router.push(`/teacher/classes/${c.id}`)">
          <div class="c-name">{{ c.name }}</div>
          <div class="c-meta">编号：{{ c.class_no || '-' }} · {{ c.grade || '-' }}</div>
          <el-tag type="primary">{{ c.student_count }} 名学生</el-tag>
          <div class="c-link">进入班级详情 →</div>
        </el-card>
      </el-col>
    </el-row>
    <el-empty v-if="!classes.length" description="暂无班级，请联系管理员分配" />
  </div>
</template>

<style scoped>
.class-card { cursor: pointer; }
.c-name { font-size: 17px; font-weight: 700; margin-bottom: 6px; }
.c-meta { color: #909399; font-size: 13px; margin-bottom: 10px; }
.c-link { margin-top: 12px; color: #2F6FED; font-size: 13px; }
</style>