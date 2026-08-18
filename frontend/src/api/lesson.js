import request from './request'

export const generateLesson = (data) => request.post('/lesson/generate', data).then((r) => r.data)
export const listPlans = (params) => request.get('/lesson/plans', { params }).then((r) => r.data)
export const updatePlan = (id, data) => request.put(`/lesson/plans/${id}`, data).then((r) => r.data)
export const deletePlan = (id) => request.delete(`/lesson/plans/${id}`).then((r) => r.data)
export const exportPlan = async (id, filename) => {
  const blob = await request.get(`/lesson/plans/${id}/export`, { responseType: 'blob' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || 'lesson_plan.docx'
  a.click()
  window.URL.revokeObjectURL(url)
}