<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { getMe } from '@/api/auth'
import { updateMe, uploadAvatar } from '@/api/user'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref()
const form = reactive({ full_name: '', email: '', password: '' })
const avatarUploading = ref(false)

async function load() {
  const me = await getMe()
  userStore.user = me
  localStorage.setItem('user_info', JSON.stringify(me))
  form.full_name = me.full_name || ''
  form.email = me.email || ''
}

async function customAvatar({ file, onSuccess, onError }) {
  avatarUploading.value = true
  const fd = new FormData()
  fd.append('file', file)
  try {
    const data = await uploadAvatar(fd)
    userStore.user.avatar = data.avatar
    localStorage.setItem('user_info', JSON.stringify(userStore.user))
    ElMessage.success('头像已更新')
    onSuccess()
  } catch (e) { onError(e) } finally { avatarUploading.value = false }
}

async function save() {
  const payload = { full_name: form.full_name || undefined, email: form.email || undefined }
  if (form.password) payload.password = form.password
  await updateMe(payload)
  ElMessage.success('保存成功')
  form.password = ''
  await load()
}

function logout() { userStore.logout(); router.push('/login') }

onMounted(load)
</script>

<template>
  <div class="page-card" style="max-width: 560px">
    <h3 style="margin-bottom: 16px">个人信息</h3>
    <div style="text-align: center; margin-bottom: 16px">
      <el-upload :show-file-list="false" :http-request="customAvatar" accept="image/*">
        <el-avatar :size="80" :src="userStore.user?.avatar || undefined" style="cursor:pointer">{{ (userStore.user?.full_name || userStore.user?.username || 'U').slice(0, 1) }}</el-avatar>
      </el-upload>
      <div style="color:#909399;font-size:12px;margin-top:6px">点击头像上传</div>
    </div>
    <el-descriptions :column="2" border style="margin-bottom: 16px">
      <el-descriptions-item label="用户名">{{ userStore.user?.username }}</el-descriptions-item>
      <el-descriptions-item label="工号">{{ userStore.user?.employee_no || '-' }}</el-descriptions-item>
      <el-descriptions-item label="职称">{{ userStore.user?.title || '-' }}</el-descriptions-item>
      <el-descriptions-item label="教研组">{{ userStore.user?.department || '-' }}</el-descriptions-item>
    </el-descriptions>
    <el-form ref="formRef" :model="form" label-width="80px">
      <el-form-item label="姓名"><el-input v-model="form.full_name" /></el-form-item>
      <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
      <el-form-item label="新密码"><el-input v-model="form.password" type="password" show-password  /></el-form-item>
      <el-form-item>
        <el-button type="primary" @click="save">保存</el-button>
        <el-button type="danger" plain @click="logout">退出登录</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>