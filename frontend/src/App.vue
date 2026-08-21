<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// 移动端抽屉侧栏控制
const asideOpen = ref(false)
function toggleAside() { asideOpen.value = !asideOpen.value }
function closeAside()  { asideOpen.value = false }
// 路由变化时自动关闭移动端侧栏
import { watch } from 'vue'
watch(() => route.fullPath, () => { if (window.innerWidth < 768) asideOpen.value = false })

// ESC 关闭抽屉
function onEsc(e) { if (e.key === 'Escape') asideOpen.value = false }
onMounted(async () => {
  window.addEventListener('keydown', onEsc)
  if (userStore.isLoggedIn) {
    try { await userStore.fetchMe() } catch (e) { /* 忽略，保持本地缓存 */ }
  }
})
onBeforeUnmount(() => { window.removeEventListener('keydown', onEsc) })

const roleTextMap = { admin: '管理员', teacher: '教师', student: '学生' }
const roleTagTypeMap = { admin: 'danger', teacher: 'warning', student: 'success' }
const roleText = computed(() => roleTextMap[userStore.role] || userStore.role)
const roleTagType = computed(() => roleTagTypeMap[userStore.role] || 'info')

const menuMap = {
  student: [
    { path: '/student',          title: '学习看板',  icon: 'HomeFilled' },
    { path: '/student/chat',     title: '智能问答',  icon: 'ChatDotRound' },
    { path: '/student/analysis', title: '学情分析',  icon: 'DataAnalysis' },
    { path: '/student/profile',  title: '个人中心',  icon: 'User' }
  ],
  teacher: [
    { path: '/teacher',          title: '教师首页',  icon: 'HomeFilled' },
    { path: '/teacher/lesson',   title: '智能备课',  icon: 'Document' },
    { path: '/teacher/knowledge',title: '知识库管理',icon: 'FolderOpened' },
    { path: '/teacher/classes',  title: '班级管理',  icon: 'School' },
    { path: '/teacher/profile',  title: '个人中心',  icon: 'User' }
  ],
  admin: [
    { path: '/admin/dashboard',  title: '数据看板',  icon: 'PieChart' },
    { path: '/admin/users',      title: '用户管理',  icon: 'User' },
    { path: '/admin/classes',    title: '班级管理',  icon: 'School' },
    { path: '/admin/courses',    title: '课表管理',  icon: 'Calendar' },
    { path: '/admin/exercises',  title: '题库管理',  icon: 'EditPen' },
    { path: '/admin/system',     title: '系统设置/日志', icon: 'Setting' }
  ]
}

const isPublic = computed(() => route.meta.public === true)
const menus = computed(() => menuMap[userStore.role] || [])

const activeMenu = computed(() => {
  if (route.path.startsWith('/teacher/classes/') || route.path.startsWith('/teacher/students/')) return '/teacher/classes'
  return route.path
})

async function onCommand(command) {
  if (command === 'logout') {
    await ElMessageBox.confirm('确定退出登录吗？', '提示', { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' })
    userStore.logout()
    router.push('/login')
  }
}
</script>

<template>
  <router-view v-if="isPublic" />

  <el-container v-else class="layout">
    <!-- 移动端遮罩 -->
    <div v-if="asideOpen" class="mobile-mask" @click="closeAside"></div>

    <el-aside width="220px" class="aside" :class="{ open: asideOpen }">
      <div class="logo">
        <svg class="logo-icon" viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
          <path fill="#8B5CF6" d="M5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82zM12 3L1 9l11 6 9-4.91V17h2V9L12 3z"/>
        </svg>
        <span>AI 教育智能体</span>
      </div>
      <el-menu :default-active="activeMenu" router background-color="transparent" text-color="#303133" active-text-color="#7C3AED" :collapse="false">
        <el-menu-item v-for="item in menus" :key="item.path" :index="item.path">
          <el-icon :size="18"><component :is="item.icon" /></el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div style="display:flex; align-items:center">
          <!-- 移动端汉堡按钮 -->
          <button type="button" class="mobile-menu-btn" aria-label="切换菜单" @click="toggleAside">
            <el-icon :size="18"><Menu /></el-icon>
          </button>
          <span class="title">{{ route.meta.title || '' }}</span>
        </div>
        <el-dropdown @command="onCommand" trigger="click">
          <span class="user" tabindex="0">
            <el-avatar :size="32" :src="userStore.user?.avatar || undefined" style="flex-shrink:0">
              {{ (userStore.user?.full_name || userStore.user?.username || 'U').slice(0, 1) }}
            </el-avatar>
            <span class="user-name">{{ userStore.user?.full_name || userStore.user?.username }}</span>
            <el-tag size="small" :type="roleTagType" effect="plain" class="role-tag">{{ roleText }}</el-tag>
            <el-icon :size="14" style="color:#909399; margin-left:2px"><CaretBottom /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>
                <div style="line-height:1.5">
                  <div style="font-weight:600">{{ userStore.user?.full_name || userStore.user?.username }}</div>
                  <div style="font-size:12px;color:#909399">{{ userStore.user?.email || '-' }}</div>
                </div>
              </el-dropdown-item>
              <el-dropdown-item divided command="logout">
                <el-icon style="margin-right:6px;color:#F56C6C"><SwitchButton /></el-icon>
                <span style="color:#F56C6C">退出登录</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
/* 用户下拉区 hover 与视觉优化 */
.header .user {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  outline: none;
  padding: 4px 8px 4px 4px;
  border-radius: 999px;
  border: 1px solid transparent;
  transition: background-color .2s, border-color .2s;
}
.header .user:hover {
  background-color: #F5F3FF;
  border-color: #E9E4FE;
}
.user-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.role-tag {
  border-radius: 999px;
  padding: 0 8px;
  font-weight: 500;
}
/* 移动端遮罩 */
.mobile-mask {
  position: fixed;
  inset: 0;
  background: rgba(17, 24, 39, 0.35);
  z-index: 999;
  backdrop-filter: blur(1px);
  animation: fadeIn .2s ease;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
</style>
