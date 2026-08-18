import request from './request'

export const register = (data) => request.post('/auth/register', data).then((r) => r.data)
export const login = (data) => request.post('/auth/login', data).then((r) => r.data)
export const refreshToken = (refresh_token) => request.post('/auth/refresh', { refresh_token }).then((r) => r.data)
export const getMe = () => request.get('/auth/me').then((r) => r.data)