import { createRouter, createWebHistory } from "vue-router"

const routes = [
  { path: "/login", component: () => import("@/views/LoginView.vue") },
  { path: "/allocation", component: () => import("@/views/AllocationView.vue") },
  { path: "/approval", component: () => import("@/views/ApprovalView.vue") },
  { path: "/execute", component: () => import("@/views/ExecuteView.vue") },
  { path: "/", redirect: "/login" },
]

const router = createRouter({ history: createWebHistory("/admin/"), routes })

router.beforeEach((to) => {
  const token = localStorage.getItem("access")
  if (!token && to.path !== "/login") return "/login"
  return true
})

export default router
