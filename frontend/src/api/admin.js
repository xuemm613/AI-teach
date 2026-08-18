import request from './request'

export const getDashboardStats = () => request.get('/admin/dashboard/stats').then((r) => r.data)

export const listClasses = (params) => request.get('/admin/classes', { params }).then((r) => r.data)
export const createClass = (data) => request.post('/admin/classes', data).then((r) => r.data)
export const updateClass = (id, data) => request.put(`/admin/classes/${id}`, data).then((r) => r.data)
export const deleteClass = (id) => request.delete(`/admin/classes/${id}`).then((r) => r.data)
export const classStudents = (id) => request.get(`/admin/classes/${id}/students`).then((r) => r.data)
export const addClassStudents = (id, studentIds) => request.post(`/admin/classes/${id}/students`, studentIds).then((r) => r.data)
export const removeClassStudent = (id, sid) => request.delete(`/admin/classes/${id}/students/${sid}`).then((r) => r.data)
export const transferStudent = (id, data) => request.post(`/admin/students/${id}/transfer`, data).then((r) => r.data)
export const getTimetableOverview = () => request.get('/admin/timetable/overview').then((r) => r.data)

export const listCourses = (params) => request.get('/admin/courses', { params }).then((r) => r.data)
export const createCourse = (data) => request.post('/admin/courses', data).then((r) => r.data)
export const updateCourse = (id, data) => request.put(`/admin/courses/${id}`, data).then((r) => r.data)
export const deleteCourse = (id) => request.delete(`/admin/courses/${id}`).then((r) => r.data)

export const listExercises = (params) => request.get('/admin/exercises', { params }).then((r) => r.data)
export const createExercise = (data) => request.post('/admin/exercises', data).then((r) => r.data)
export const updateExercise = (id, data) => request.put(`/admin/exercises/${id}`, data).then((r) => r.data)
export const deleteExercise = (id) => request.delete(`/admin/exercises/${id}`).then((r) => r.data)
export const listTeachers = () => request.get('/admin/teachers').then((r) => r.data)
export const listStudents = () => request.get('/admin/students').then((r) => r.data)

export const listLoginLogs = (params) => request.get('/admin/login-logs', { params }).then((r) => r.data)