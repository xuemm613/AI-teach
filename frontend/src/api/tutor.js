import request from './request'

export const myAnalysis = () => request.post('/tutor/my-analysis').then((r) => r.data)
export const myAnalysisLatest = () => request.get('/tutor/my-analysis/latest').then((r) => r.data)
export const analyzeError = (data) => request.post('/tutor/analyze-error', data).then((r) => r.data)
export const generateExercise = (data) => request.post('/tutor/generate-exercise', data).then((r) => r.data)
