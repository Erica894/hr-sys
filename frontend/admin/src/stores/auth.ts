import { defineStore } from "pinia"
import api from "@/api/client"

function loadRoles(): string[] {
  try {
    const raw = localStorage.getItem("roles")
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

export const useAuth = defineStore("auth", {
  state: () => ({
    user: { email: localStorage.getItem("email") || "" } as { email: string },
    needsMfa: false,
    roles: loadRoles() as string[],
  }),
  getters: {
    isAuthenticated: () => !!localStorage.getItem("access"),
  },
  actions: {
    async login(email: string, password: string) {
      const r = await api.post("/auth/login/", { email, password })
      localStorage.setItem("access", r.data.access)
      localStorage.setItem("refresh", r.data.refresh)
      localStorage.setItem("email", email)
      this.user = { email }
      this.roles = Array.isArray(r.data.roles) ? r.data.roles : []
      localStorage.setItem("roles", JSON.stringify(this.roles))
      this.needsMfa = !!r.data.mfa_required
    },
    async verifyMfa(code: string) {
      await api.post("/auth/mfa/verify/", { code })
      this.needsMfa = false
    },
    hasRole(code: string): boolean {
      return this.roles.includes(code)
    },
    logout() {
      localStorage.removeItem("access")
      localStorage.removeItem("refresh")
      localStorage.removeItem("roles")
      localStorage.removeItem("email")
      this.user = { email: "" }
      this.needsMfa = false
      this.roles = []
    },
  },
})
