import axios from 'axios'
import { ElMessage } from 'element-plus'

import router from '@/router'
import { useUserStore } from '@/stores/user'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 180000
})

request.interceptors.request.use((config) => {
  const store = useUserStore()
  if (store.accessToken) {
    config.headers.Authorization = `Bearer ${store.accessToken}`
  }
  return config
})

let refreshing = null

request.interceptors.response.use(
  (response) => {
    const body = response.data
    if (body && typeof body.code !== 'undefined' && body.code !== 0) {
      ElMessage.error(body.message || '请求失败')
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    return body
  },
  async (error) => {
    const { response, config } = error
    const store = useUserStore()
    if (response && response.status === 401 && !config._retry && store.refreshToken) {
      config._retry = true
      try {
        if (!refreshing) {
          refreshing = store.refresh()
        }
        await refreshing
        refreshing = null
        config.headers.Authorization = `Bearer ${store.accessToken}`
        return request(config)
      } catch (e) {
        refreshing = null
        store.logout()
        router.push('/login')
      }
    }
    const msg = response?.data?.message || error.message || '网络错误'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default request