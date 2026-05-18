import axios from "axios"

const api = axios.create({ baseURL: "/api", timeout: 10000 })

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("access")
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  const locale = localStorage.getItem("hr-sys.locale")
  cfg.headers["Accept-Language"] = locale === "en" ? "en" : "zh-hans"
  return cfg
})

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    if (err.response?.status === 401) {
      const refresh = localStorage.getItem("refresh")
      if (refresh) {
        try {
          const r = await axios.post("/api/auth/refresh/", { refresh })
          localStorage.setItem("access", r.data.access)
          err.config.headers.Authorization = `Bearer ${r.data.access}`
          return axios.request(err.config)
        } catch {
          localStorage.removeItem("access")
          localStorage.removeItem("refresh")
          window.location.href = "/login"
        }
      }
    }
    return Promise.reject(err)
  }
)

export default api
