<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { getMe } from '@/api/auth'
import { getClassInfo, updateMe, uploadAvatar } from '@/api/user'

const router = useRouter()
const userStore = useUserStore()
const classes = ref([])
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
  const payload = {
    username: form.username || undefined,
    full_name: form.full_name || undefined,
    email: form.email || undefined
  }
  if (form.password) {
    if (form.password.length < 6) { ElMessage.warning('密码至少 6 位'); return }
    payload.password = form.password
  }
  await updateMe(payload)
  ElMessage.success('保存成功')
  form.password = ''
  await load()
}

async function logout() {
  await ElMessageBox.confirm('确定退出登录吗？', '提示', { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' })
  userStore.logout()
  router.push('/login')
}

onMounted(load)
</script>

<template>
  <el-row :gutter="16">
    <!-- 左侧：个人信息编辑卡 -->
    <el-col :xs="24" :sm="24" :md="8" class="row-stack">
      <div class="page-card">
        <h3 class="card-title">个人信息</h3>

        <!-- 头像区域 -->
        <div class="profile-avatar-section">
          <el-upload :show-file-list="false" :http-request="customAvatar" accept="image/*">
            <el-avatar :size="72" :src="userStore.user?.avatar || undefined" class="profile-avatar">
              {{ (userStore.user?.full_name || userStore.user?.username || 'U').slice(0, 1) }}
            </el-avatar>
          </el-upload>
          <div class="profile-name-row">
            <div class="profile-name">{{ userStore.user?.full_name || userStore.user?.username }}</div>
            <el-tag size="small" effect="plain" type="warning" style="margin-left:6px">学生</el-tag>
          </div>
          <div class="profile-id-row">
            <span class="profile-tag">学号 {{ userStore.user?.student_no || '-' }}</span>
            <span class="profile-tag">{{ userStore.user?.grade || '年级' }}</span>
          </div>
          <div class="profile-avatar-hint">点击头像上传更换</div>
        </div>

        <div class="pp-divider"></div>

        <el-form ref="formRef" :model="form" label-position="top" class="sp-form">
          <el-form-item label="用户名">
            <el-input v-model="form.username" clearable placeholder="输入用户名" />
          </el-form-item>
          <el-form-item label="姓名">
            <el-input v-model="form.full_name" clearable placeholder="输入真实姓名" />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="form.email" placeholder="选填，用于找回密码" clearable />
          </el-form-item>
          <el-form-item label="新密码">
            <el-input v-model="form.password" type="password" show-password placeholder="至少 6 位，留空则不修改" />
          </el-form-item>
          <el-form-item class="sp-form-actions">
            <el-button type="primary" @click="save">
              <el-icon style="margin-right:4px"><Check /></el-icon>保存修改
            </el-button>
            <el-button type="danger" plain @click="logout">
              <el-icon style="margin-right:4px"><SwitchButton /></el-icon>退出登录
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-col>

    <!-- 右侧：班级与安全 -->
    <el-col :xs="24" :sm="24" :md="16" class="row-stack">
      <!-- 班级信息 -->
      <div class="page-card">
        <div class="sp-card-header">
          <h3 class="card-title" style="margin:0">我的班级与任课教师</h3>
          <el-tag type="info" effect="plain" size="small">共 {{ classes.length }} 个班级</el-tag>
        </div>

        <div v-if="classes.length" class="class-list">
          <div v-for="(c, i) in classes" :key="i" class="class-item">
            <div class="class-item-left">
              <span class="info-icon-sm bg-icon-info" style="width:48px; height:48px; border-radius:12px; flex-shrink:0">
                <el-icon :size="48"><School /></el-icon>
              </span>
              <div class="class-item-info">
                <div class="class-item-name">{{ c.class_name }}</div>
                <div class="class-item-meta">{{ c.grade || '-' }}</div>
              </div>
            </div>
            <div class="class-item-right">
              <div class="class-item-teacher-row">
                <span class="class-item-label">任课教师</span>
                <span class="class-item-value">{{ c.teacher_name || '-' }}</span>
                <el-tag v-if="c.teacher_title" size="small" type="warning" effect="light" style="margin-left:6px">{{ c.teacher_title }}</el-tag>
              </div>
              <div class="class-item-dept">
                <span class="class-item-label">教研组</span>
                <span class="class-item-value">{{ c.teacher_department || '-' }}</span>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无班级信息" :image-size="80" />
      </div>

      <!-- 账号安全 -->
      <div class="page-card" style="margin-top: 16px">
        <h3 class="card-title">账号与安全</h3>
        <div class="sp-security-box">
          <span class="sp-security-icon">
            <el-icon :size="22"><Lock /></el-icon>
          </span>
          <div class="sp-security-body">
            <div class="sp-security-title">定期修改密码，保障账号安全</div>
            <div class="sp-security-desc">建议使用字母 + 数字 + 特殊符号组合的强密码，不要在多个平台共用同一密码。如忘记密码，请联系任课教师或学校管理员重置。</div>
          </div>
        </div>
      </div>
    </el-col>
  </el-row>
</template>

<style scoped>
/* ====== 头像区域 ====== */
.profile-avatar-section {
  text-align: center;
  padding: 18px 14px 6px;
}
.profile-avatar {
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(139, 92, 246, 0.18);
  transition: box-shadow 0.2s;
}
.profile-avatar:hover { box-shadow: 0 6px 20px rgba(139, 92, 246, 0.3); }
.profile-name-row {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 12px;
}
.profile-name {
  font-size: 18px;
  font-weight: 700;
  color: #1A1A1A;
}
.profile-id-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 6px;
}
.profile-tag {
  display: inline-block;
  padding: 2px 10px;
  font-size: 12px;
  color: #606266;
  background: #F5F7FA;
  border-radius: 6px;
  border: 1px solid #EBEEF3;
}
.profile-avatar-hint {
  color: #C7C7D1;
  font-size: 12px;
  margin-top: 8px;
}

/* ====== 分割线 ====== */
.pp-divider {
  height: 1px;
  background: #F0F2F5;
  margin: 8px 0;
}

/* ====== 表单 ====== */
.sp-form :deep(.el-form-item) {
  margin-bottom: 14px;
}
.sp-form :deep(.el-form-item__label) {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  padding-bottom: 4px;
}
.sp-form :deep(.el-input__wrapper) {
  border-radius: 10px;
}
.sp-form-actions {
  margin-top: 8px;
}
.sp-form-actions :deep(.el-form-item__content) {
  gap: 10px;
}
.sp-form-actions .el-button {
  border-radius: 10px;
  height: 38px;
}

/* ====== 班级列表 ====== */
.sp-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.class-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.class-item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: #FAFBFC;
  border: 1px solid #F0F2F5;
  border-radius: 12px;
  transition: border-color 0.15s, background 0.15s;
}
.class-item:hover {
  border-color: #DDD6FE;
  background: #F8F7FF;
}
.class-item-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.class-item-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.class-item-name {
  font-weight: 600;
  color: #1A1A1A;
  font-size: 14px;
}
.class-item-meta {
  color: #909399;
  font-size: 12px;
}
.class-item-right {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.class-item-teacher-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.class-item-dept {
  display: flex;
  align-items: center;
  gap: 6px;
}
.class-item-label {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}
.class-item-value {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

/* ====== 安全提示 ====== */
.sp-security-box {
  display: flex;
  gap: 14px;
  padding: 16px 18px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.06), rgba(47, 111, 237, 0.06));
  border: 1px solid #E9E4FE;
  border-radius: 12px;
}
.sp-security-icon {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #F3EDFB;
  color: #722ED1;
  border-radius: 12px;
}
.sp-security-body {
  flex: 1;
  line-height: 1.8;
}
.sp-security-title {
  font-weight: 600;
  color: #1A1A1A;
  font-size: 14px;
  margin-bottom: 2px;
}
.sp-security-desc {
  color: #909399;
  font-size: 13px;
}

/* ====== 响应式 ====== */
@media (max-width: 767px) {
  .class-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  .class-item-right {
    width: 100%;
    padding-left: 60px;
  }
  .sp-security-box {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
