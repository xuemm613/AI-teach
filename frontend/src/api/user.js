import request from './request'

export const updateMe = (data) => request.put('/users/me', data).then((r) => r.data)
export const uploadAvatar = (formData) =>
  request.post('/users/me/avatar', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data)
export const getMyCourses = () => request.get('/users/me/courses').then((r) => r.data)
export const getMyRecords = (params) => request.get('/users/me/records', { params }).then((r) => r.data)
export const submitRecord = (data) => request.post('/users/me/records', data).then((r) => r.data)
export const getMyStats = () => request.get('/users/me/stats').then((r) => r.data)
export const getWrongBook = (params) => request.get('/users/me/wrong-book', { params }).then((r) => r.data)
export const addWrongBook = (data) => request.post('/users/me/wrong-book', data).then((r) => r.data)
export const deleteWrongBook = (id) => request.delete(`/users/me/wrong-book/${id}`).then((r) => r.data)
export const getExercises = (params) => request.get('/users/me/exercises', { params }).then((r) => r.data)

// ---- 学生端 ----
export const getDashboard = () => request.get('/users/me/dashboard').then((r) => r.data)
export const getTodaySchedule = () => request.get('/users/me/today-schedule').then((r) => r.data)
export const getTimeline = (params) => request.get('/users/me/timeline', { params }).then((r) => r.data)
export const getClassInfo = () => request.get('/users/me/class-info').then((r) => r.data)

// ---- 教师端 ----
export const getTeacherDashboard = () => request.get('/users/me/teacher-dashboard').then((r) => r.data)
export const getMyClasses = () => request.get('/users/me/classes').then((r) => r.data)
export const getClassDetail = (id) => request.get(`/users/me/classes/${id}`).then((r) => r.data)
export const removeClassStudent = (cid, sid) => request.delete(`/users/me/classes/${cid}/students/${sid}`).then((r) => r.data)
export const getStudentProfile = (id) => request.get(`/users/me/students/${id}/profile`).then((r) => r.data)
export const sendMessage = (id, data) => request.post(`/users/me/students/${id}/message`, data).then((r) => r.data)

// ---- 用户管理（管理员） ----
export const listUsers = (params) => request.get('/users', { params }).then((r) => r.data)
export const createUser = (data) => request.post('/users', data).then((r) => r.data)
export const updateUser = (id, data) => request.put(`/users/${id}`, data).then((r) => r.data)
export const deleteUser = (id) => request.delete(`/users/${id}`).then((r) => r.data)
