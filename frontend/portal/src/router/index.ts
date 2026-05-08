import { createRouter, createWebHistory } from "vue-router"

const routes = [
  { path: "/login", component: () => import("@/views/LoginView.vue") },
  { path: "/my-proposal", component: () => import("@/views/MyProposalView.vue") },
  { path: "/", redirect: "/login" },
]

const router = createRouter({ history: createWebHistory("/"), routes })

router.beforeEach((to) => {
  const token = localStorage.getItem("access")
  if (!token && to.path !== "/login") return "/login"
  return true
})

export default router
