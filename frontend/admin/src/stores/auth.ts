import { defineStore } from "pinia"
import api from "@/api/client"

export const useAuth = defineStore("auth", {
  state: () => ({
    user: null as any,
    needsMfa: false,
  }),
  actions: {
    async login(email: string, password: string) {
      const r = await api.post("/auth/login/", { email, password })
      localStorage.setItem("access", r.data.access)
      localStorage.setItem("refresh", r.data.refresh)
      this.user = r.data.user
      this.needsMfa = !!r.data.mfa_required
    },
    async verifyMfa(code: string) {
      await api.post("/auth/mfa/verify/", { code })
      this.needsMfa = false
    },
    logout() {
      localStorage.removeItem("access")
      localStorage.removeItem("refresh")
      this.user = null
      this.needsMfa = false
    },
  },
})
