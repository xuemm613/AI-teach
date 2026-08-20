<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const roleTextMap = { admin: '管理员', teacher: '教师', student: '学生' }
const roleText = computed(() => roleTextMap[userStore.role] || userStore.role)

const menuMap = {
  student: [
    { path: '/student', title: '学习看板', icon: 'HomeFilled' },
    { path: '/student/chat', title: '智能问答', icon: 'ChatDotRound' },
    { path: '/student/analysis', title: '学情分析', icon: 'DataAnalysis' },
    { path: '/student/profile', title: '个人中心', icon: 'User' }
  ],
  teacher: [
    { path: '/teacher', title: '教师首页', icon: 'HomeFilled' },
    { path: '/teacher/lesson', title: '智能备课', icon: 'Document' },
    { path: '/teacher/knowledge', title: '知识库管理', icon: 'FolderOpened' },
    { path: '/teacher/classes', title: '班级管理', icon: 'School' },
    { path: '/teacher/profile', title: '个人中心', icon: 'User' }
  ],
  admin: [
    { path: '/admin/dashboard', title: '数据看板', icon: 'PieChart' },
    { path: '/admin/users', title: '用户管理', icon: 'User' },
    { path: '/admin/classes', title: '班级管理', icon: 'School' },
    { path: '/admin/courses', title: '课表管理', icon: 'Calendar' },
    { path: '/admin/exercises', title: '题库管理', icon: 'EditPen' },
    { path: '/admin/system', title: '系统设置/日志', icon: 'Setting' }
  ]
}

const isPublic = computed(() => route.meta.public === true)
const menus = computed(() => menuMap[userStore.role] || [])

// 每次进入系统都从服务端拉取最新用户信息，保证修改后（如管理员改名）全局同步
onMounted(async () => {
  if (userStore.isLoggedIn) {
    try { await userStore.fetchMe() } catch (e) { /* 忽略，保持本地缓存 */ }
  }
})
const activeMenu = computed(() => {
  if (route.path.startsWith('/teacher/classes/') || route.path.startsWith('/teacher/students/')) return '/teacher/classes'
  return route.path
})

async function onCommand(command) {
  if (command === 'logout') {
    await ElMessageBox.confirm('确定退出登录吗？', '提示', { type: 'warning' })
    userStore.logout()
    router.push('/login')
  }
}
</script>

<template>
  <router-view v-if="isPublic" />

  <el-container v-else class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">
        <svg class="logo-icon" viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
          <path fill="#8B5CF6" d="M5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82zM12 3L1 9l11 6 9-4.91V17h2V9L12 3z"/>
        </svg>
        <span>AI 教育智能体</span>
      </div>
      <el-menu :default-active="activeMenu" router background-color="transparent" text-color="#303133" active-text-color="#7C3AED">
        <el-menu-item v-for="item in menus" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <span class="title">{{ route.meta.title || '' }}</span>
        <el-dropdown @command="onCommand">
          <span class="user">
            <el-avatar :size="30" :src="userStore.user?.avatar || undefined">{{ (userStore.user?.full_name || userStore.user?.username || 'U').slice(0, 1) }}</el-avatar>
            <span>{{ userStore.user?.full_name || userStore.user?.username }}</span>
            <el-tag size="small" type="info" effect="plain">{{ roleText }}</el-tag>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
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