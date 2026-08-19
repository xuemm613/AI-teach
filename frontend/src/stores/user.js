import { defineStore } from 'pinia'

import { getMe, login as apiLogin, refreshToken as apiRefresh, register as apiRegister } from '@/api/auth'

export const useUserStore = defineStore('user', {
  state: () => ({
    accessToken: localStorage.getItem('access_token') || '',
    refreshToken: localStorage.getItem('refresh_token') || '',
    user: JSON.parse(localStorage.getItem('user_info') || 'null')
  }),
  getters: {
    isLoggedIn: (s) => !!s.accessToken,
    role: (s) => s.user?.role || ''
  },
  actions: {
    setTokens(access, refresh) {
      this.accessToken = access
      this.refreshToken = refresh
      localStorage.setItem('access_token', access)
      localStorage.setItem('refresh_token', refresh)
    },
    async login(payload) {
      const data = await apiLogin(payload)
      this.setTokens(data.access_token, data.refresh_token)
      this.user = data.user
      localStorage.setItem('user_info', JSON.stringify(data.user))
      return data
    },
    async register(payload) {
      const data = await apiRegister(payload)
      this.setTokens(data.access_token, data.refresh_token)
      this.user = data.user
      localStorage.setItem('user_info', JSON.stringify(data.user))
      return data
    },
    async fetchMe() {
      const data = await getMe()
      this.user = data
      localStorage.setItem('user_info', JSON.stringify(data))
      return data
    },
    async refresh() {
      const data = await apiRefresh(this.refreshToken)
      this.setTokens(data.access_token, data.refresh_token)
      this.user = data.user
      localStorage.setItem('user_info', JSON.stringify(data.user))
    },
    logout() {
      this.accessToken = ''
      this.refreshToken = ''
      this.user = null
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user_info')
    }
  }
})