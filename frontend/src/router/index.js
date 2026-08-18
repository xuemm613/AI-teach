import { createRouter, createWebHistory } from 'vue-router'

import { useUserStore } from '@/stores/user'

const routes = [
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue'), meta: { public: true, title: '登录' } },
  // 学生端
  { path: '/student', component: () => import('@/views/student/StudentHome.vue'), meta: { role: 'student', title: '学习看板' } },
  { path: '/student/chat', component: () => import('@/views/student/ChatQA.vue'), meta: { role: 'student', title: '智能问答' } },
  { path: '/student/analysis', component: () => import('@/views/student/LearningProfile.vue'), meta: { role: 'student', title: '学情分析' } },
  { path: '/student/profile', component: () => import('@/views/student/StudentProfile.vue'), meta: { role: 'student', title: '个人中心' } },
  // 教师端
  { path: '/teacher', component: () => import('@/views/teacher/TeacherHome.vue'), meta: { role: 'teacher', title: '教师首页' } },
  { path: '/teacher/lesson', component: () => import('@/views/teacher/LessonPlan.vue'), meta: { role: 'teacher', title: '智能备课' } },
  { path: '/teacher/knowledge', component: () => import('@/views/teacher/Knowledge.vue'), meta: { role: 'teacher', title: '知识库管理' } },
  { path: '/teacher/classes', component: () => import('@/views/teacher/Classes.vue'), meta: { role: 'teacher', title: '班级管理' } },
  { path: '/teacher/classes/:id', component: () => import('@/views/teacher/ClassDetail.vue'), meta: { role: 'teacher', title: '班级详情' } },
  { path: '/teacher/students/:id', component: () => import('@/views/teacher/StudentAnalysis.vue'), meta: { role: 'teacher', title: '学生学情分析' } },
  { path: '/teacher/profile', component: () => import('@/views/teacher/TeacherProfile.vue'), meta: { role: 'teacher', title: '个人中心' } },
  // 管理后台
  { path: '/admin/dashboard', component: () => import('@/views/admin/Dashboard.vue'), meta: { role: 'admin', title: '数据看板' } },
  { path: '/admin/users', component: () => import('@/views/admin/UserManage.vue'), meta: { role: 'admin', title: '用户管理' } },
  { path: '/admin/classes', component: () => import('@/views/admin/AdminClasses.vue'), meta: { role: 'admin', title: '班级管理' } },
  { path: '/admin/courses', component: () => import('@/views/admin/CourseManage.vue'), meta: { role: 'admin', title: '课表管理' } },
  { path: '/admin/exercises', component: () => import('@/views/admin/ExerciseManage.vue'), meta: { role: 'admin', title: '题库管理' } },
  { path: '/admin/system', component: () => import('@/views/admin/SystemManage.vue'), meta: { role: 'admin', title: '系统设置/日志' } }
]

const router = createRouter({ history: createWebHistory(), routes })
const roleHome = { admin: '/admin/dashboard', teacher: '/teacher', student: '/student' }

router.beforeEach((to) => {
  const store = useUserStore()
  if (to.meta.public) return true
  if (!store.isLoggedIn) return '/login'
  if (to.path === '/') return roleHome[store.role] || '/login'
  if (to.meta.role && to.meta.role !== store.role) return roleHome[store.role] || '/login'
  return true
})

export default router