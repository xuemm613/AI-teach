<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { SUBJECTS } from '@/constants'

const router = useRouter()
const store = useUserStore()

const mode = ref('login')
const loading = ref(false)
const formRef = ref()

const gradeOptions = ['七年级', '八年级', '九年级']

const form = reactive({
  username: '',
  password: '',
  role: 'student',
  full_name: '',
  email: '',
  grade: '',
  subject: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, min: 6, message: '请输入至少 6 位密码', trigger: 'blur' }],
  full_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }]
}

async function submit() {
  await formRef.value.validate()
  loading.value = true
  try {
    if (mode.value === 'login') {
      await store.login({ username: form.username, password: form.password })
      ElMessage.success('登录成功')
      router.push('/')   // 由路由守卫跳转到对应角色首页（管理员→数据看板）
    } else {
      await store.register({ ...form })
      ElMessage.success('注册成功')
      router.push('/')
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <svg class="logo-icon" viewBox="0 0 24 24" width="44" height="44" aria-hidden="true">
          <path fill="#8B5CF6" d="M5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82zM12 3L1 9l11 6 9-4.91V17h2V9L12 3z"/>
        </svg>
        <h1>AI 教育智能体</h1>
      </div>

      <el-tabs v-model="mode" stretch>
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large" @keyup.enter="submit">
        <el-form-item label="工号/学号" prop="username">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>

        <template v-if="mode === 'register'">
          <el-form-item label="身份">
            <el-radio-group v-model="form.role">
              <el-radio-button value="student">学生</el-radio-button>
              <el-radio-button value="teacher">教师</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="姓名" prop="full_name">
            <el-input v-model="form.full_name" />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="form.email" />
          </el-form-item>
          <el-form-item v-if="form.role === 'student'" label="年级">
            <el-select v-model="form.grade" style="width: 100%">
              <el-option v-for="g in gradeOptions" :key="g" :label="g" :value="g" />
            </el-select>
          </el-form-item>
          <el-form-item v-else label="学科">
            <el-select v-model="form.subject" style="width: 100%">
              <el-option v-for="s in SUBJECTS" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
        </template>

        <el-button type="primary" style="width: 100%" :loading="loading" @click="submit">
          {{ mode === 'login' ? '登 录' : '注 册' }}
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #F3F4F6;
}
.login-card {
  width: 420px;
  background: #fff;
  border-radius: 12px;
  padding: 32px 36px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
  border: 1px solid #D0D5DD;
}
.brand {
  text-align: center;
  margin-bottom: 18px;
}
.brand .logo-icon {
  margin-bottom: 6px;
}
.brand h1 {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 1px;
  line-height: 1.5;
  color: #303133;
}
</style>
