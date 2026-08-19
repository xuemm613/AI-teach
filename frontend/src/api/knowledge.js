import request from './request'

export const uploadFile = (formData) =>
  request.post('/knowledge/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data)
export const listFiles = (params) => request.get('/knowledge/files', { params }).then((r) => r.data)
export const getKnowledgeStats = () => request.get('/knowledge/stats').then((r) => r.data)
export const deleteFile = (id) => request.delete(`/knowledge/files/${id}`).then((r) => r.data)
export const getFileContent = (id) => request.get(`/knowledge/files/${id}/content`).then((r) => r.data)
export const searchKnowledge = (data) => request.post('/knowledge/search', data).then((r) => r.data)
export const askKnowledge = (data) => request.post('/knowledge/ask', data).then((r) => r.data)