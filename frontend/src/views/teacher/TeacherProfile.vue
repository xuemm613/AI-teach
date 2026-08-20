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
const form = reactive({ username: '', full_name: '', email: '', password: '' })
const avatarUploading = ref(false)

async function load() {
  const me = await getMe()
  userStore.user = me
  localStorage.setItem('user_info', JSON.stringify(me))
  form.username = me.username || ''
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
  const payload = { username: form.username || undefined, full_name: form.full_name || undefined, email: form.email || undefined }
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
  <el-row :gutter="16">
    <el-col :span="10">
      <div class="page-card profile-card">
        <el-upload :show-file-list="false" :http-request="customAvatar" accept="image/*">
          <el-avatar :size="96" :src="userStore.user?.avatar || undefined" style="cursor:pointer">{{ (userStore.user?.full_name || userStore.user?.username || 'U').slice(0, 1) }}</el-avatar>
        </el-upload>
        <div class="avatar-hint">点击头像上传</div>
        <div class="name">{{ userStore.user?.full_name || userStore.user?.username }}</div>
        <el-tag type="primary" effect="plain" style="margin-top: 8px; margin-bottom: 16px">教师</el-tag>
        <div class="info-list">
          <div class="info-item">
            <div class="info-icon" style="background:#E9ECF2;color:#2F6FED"><el-icon><User /></el-icon></div>
            <div class="info-text"><span>工号</span><b>{{ userStore.user?.employee_no || '-' }}</b></div>
          </div>
          <div class="info-item">
            <div class="info-icon" style="background:#F3EDFB;color:#722ED1"><el-icon><Medal /></el-icon></div>
            <div class="info-text"><span>职称</span><b>{{ userStore.user?.title || '-' }}</b></div>
          </div>
          <div class="info-item">
            <div class="info-icon" style="background:#ECF8F1;color:#43B97F"><el-icon><OfficeBuilding /></el-icon></div>
            <div class="info-text"><span>教研组</span><b>{{ userStore.user?.department || '-' }}</b></div>
          </div>
          <div class="info-item">
            <div class="info-icon" style="background:#FDF6EC;color:#E6A23C"><el-icon><Collection /></el-icon></div>
            <div class="info-text"><span>负责科目</span><b>{{ (userStore.user?.subjects || []).join('、') || '-' }}</b></div>
          </div>
        </div>
      </div>
    </el-col>
    <el-col :span="14">
      <div class="page-card">
        <h3 style="margin-bottom: 16px">编辑资料</h3>
        <el-form ref="formRef" :model="form" label-width="90px" size="large">
          <el-form-item label="用户名">
            <el-input v-model="form.username"><template #prefix><el-icon><User /></el-icon></template></el-input>
          </el-form-item>
          <el-form-item label="姓名">
            <el-input v-model="form.full_name"><template #prefix><el-icon><UserFilled /></el-icon></template></el-input>
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="form.email"><template #prefix><el-icon><Message /></el-icon></template></el-input>
          </el-form-item>
          <el-form-item label="新密码">
            <el-input v-model="form.password" type="password" show-password><template #prefix><el-icon><Lock /></el-icon></template></el-input>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="save">保存</el-button>
            <el-button type="danger" plain @click="logout">退出登录</el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-col>
  </el-row>
</template>

<style scoped>
.profile-card { text-align: center; height: 100%; display: flex; flex-direction: column; align-items: center; }
.avatar-hint { color: #909399; font-size: 13px; margin-top: 10px; }
.name { font-size: 22px; font-weight: 700; margin-top: 10px; }
.info-list { width: 100%; text-align: left; margin-top: 14px; }
.info-item { display: flex; align-items: center; gap: 14px; padding: 18px 0; border-bottom: 1px solid #F0F2F5; }
.info-item:last-child { border-bottom: none; }
.info-icon { width: 44px; height: 44px; border-radius: 12px; font-size: 22px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.info-text { display: flex; flex-direction: column; gap: 3px; }
.info-text span { font-size: 13px; color: #909399; }
.info-text b { font-size: 16px; color: #303133; font-weight: 600; }
</style>