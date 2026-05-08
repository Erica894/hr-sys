import { defineStore } from "pinia"
import api from "@/api/client"

export const useAuth = defineStore("auth", {
  state: () => ({ user: null as any }),
  actions: {
    async login(email: string, password: string) {
      const r = await api.post("/auth/login/", { email, password })
      localStorage.setItem("access", r.data.access)
      localStorage.setItem("refresh", r.data.refresh)
      this.user = r.data.user
    },
    logout() {
      localStorage.removeItem("access")
      localStorage.removeItem("refresh")
      this.user = null
    },
  },
})
