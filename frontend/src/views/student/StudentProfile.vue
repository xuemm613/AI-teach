<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { getMe } from '@/api/auth'
import { getClassInfo, updateMe, uploadAvatar } from '@/api/user'

const router = useRouter()
const userStore = useUserStore()
const classes = ref([])
const formRef = ref()
const form = reactive({ full_name: '', email: '', password: '' })
const avatarUploading = ref(false)

async function load() {
  const me = await getMe()
  userStore.user = me
  localStorage.setItem('user_info', JSON.stringify(me))
  form.full_name = me.full_name || ''
  form.email = me.email || ''
  classes.value = await getClassInfo()
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

function logout() {
  userStore.logout()
  router.push('/login')
}

onMounted(load)
</script>

<template>
  <el-row :gutter="16">
    <el-col :span="10">
      <div class="page-card">
        <h3 style="margin-bottom: 16px">个人信息</h3>
        <div style="text-align: center; margin-bottom: 16px">
          <el-upload :show-file-list="false" :http-request="customAvatar" accept="image/*">
            <el-avatar :size="80" :src="userStore.user?.avatar || undefined" style="cursor: pointer">{{ (userStore.user?.full_name || userStore.user?.username || 'U').slice(0, 1) }}</el-avatar>
          </el-upload>
          <div style="color:#909399;font-size:12px;margin-top:6px">点击头像上传</div>
        </div>
        <el-form ref="formRef" :model="form" label-width="80px">
          <el-form-item label="学号"><el-input :model-value="userStore.user?.student_no || '-'" disabled /></el-form-item>
          <el-form-item label="用户名"><el-input :model-value="userStore.user?.username" disabled /></el-form-item>
          <el-form-item label="姓名"><el-input v-model="form.full_name" /></el-form-item>
          <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
          <el-form-item label="新密码"><el-input v-model="form.password" type="password" show-password  /></el-form-item>
          <el-form-item>
            <el-button type="primary" @click="save">保存</el-button>
            <el-button type="danger" plain @click="logout">退出登录</el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-col>
    <el-col :span="14">
      <div class="page-card">
        <h3 style="margin-bottom: 16px">我的班级与任课教师</h3>
        <el-table :data="classes" stripe>
          <el-table-column prop="class_name" label="班级" width="180" />
          <el-table-column prop="grade" label="年级" width="100" />
          <el-table-column label="任课教师" min-width="180">
            <template #default="{ row }">
              {{ row.teacher_name }}
              <el-tag v-if="row.teacher_title" size="small" style="margin-left: 6px">{{ row.teacher_title }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="teacher_department" label="教研组" width="140" />
        </el-table>
        <el-empty v-if="!classes.length" description="暂无班级信息" />
      </div>
    </el-col>
  </el-row>
</template>