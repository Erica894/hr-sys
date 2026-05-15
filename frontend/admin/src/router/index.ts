import { createRouter, createWebHistory } from "vue-router"
import { ElMessage } from "element-plus"
import { useAuth } from "@/stores/auth"

const routes = [
  { path: "/login", component: () => import("@/views/LoginView.vue") },

  // EMPLOYEE: 自查
  {
    path: "/me/compensation",
    component: () => import("@/views/me/MyCompensationView.vue"),
  },

  // DEPT_HEAD: 流程执行
  {
    path: "/allocation",
    component: () => import("@/views/AllocationView.vue"),
    meta: { requiresDeptHead: true },
  },
  {
    path: "/dept/available-budget",
    component: () => import("@/views/dept/AvailableBudgetView.vue"),
    meta: { requiresDeptHead: true },
  },
  {
    path: "/dept/analysis",
    component: () => import("@/views/dept/AllocationAnalysisView.vue"),
    meta: { requiresDeptHead: true },
  },

  // HR_ADMIN: 审批 / 执行
  {
    path: "/approval",
    component: () => import("@/views/ApprovalView.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/execute",
    component: () => import("@/views/ExecuteView.vue"),
    meta: { requiresAdmin: true },
  },

  // HR_ADMIN: 类别方案
  {
    path: "/admin/categories/schemes",
    component: () => import("@/views/categories/CategorySchemeView.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/admin/categories/assignments",
    component: () => import("@/views/categories/AssignmentView.vue"),
    meta: { requiresAdmin: true },
  },

  // HR_ADMIN: 方案设计
  {
    path: "/admin/plans/adjustment",
    component: () => import("@/views/plans/AdjustmentPlanListView.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/admin/plans/adjustment/new",
    component: () => import("@/views/plans/AdjustmentPlanEditView.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/admin/plans/adjustment/:id",
    component: () => import("@/views/plans/AdjustmentPlanEditView.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/admin/plans/lti",
    component: () => import("@/views/plans/LtiPlanListView.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/admin/plans/lti/new",
    component: () => import("@/views/plans/LtiPlanEditView.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/admin/plans/lti/:id",
    component: () => import("@/views/plans/LtiPlanEditView.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/admin/plans/bonus",
    component: () => import("@/views/plans/BonusPlanListView.vue"),
    meta: { requiresAdmin: true },
  },

  // HR_ADMIN: 预算管理
  {
    path: "/admin/budgets/adjustment",
    component: () => import("@/views/budgets/AdjustmentBudgetView.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/admin/budgets/lti",
    component: () => import("@/views/budgets/LtiBudgetView.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/admin/budgets/my",
    component: () => import("@/views/budgets/MyBudgetView.vue"),
    meta: { requiresAnyRole: ["DEPT_HEAD", "CENTER_HEAD", "HR_ADMIN"] },
  },

  // HR_ADMIN: 其他
  {
    path: "/admin/org",
    component: () => import("@/views/org/OrgManagementView.vue"),
    meta: { requiresAdmin: true },
  },
  {
    path: "/admin/salary-bands",
    component: () => import("@/views/salary/SalaryBandView.vue"),
    meta: { requiresAdmin: true },
  },

  { path: "/", redirect: "/login" },
]

const router = createRouter({ history: createWebHistory("/admin/"), routes })

router.beforeEach((to, from) => {
  const token = localStorage.getItem("access")
  if (!token && to.path !== "/login") return "/login"

  const auth = useAuth()
  const needAdmin = !!to.meta?.requiresAdmin
  const needDept = !!to.meta?.requiresDeptHead
  const needAny = (to.meta?.requiresAnyRole as string[] | undefined) || null

  if (needAdmin && !auth.hasRole("HR_ADMIN")) {
    ElMessage.error("无权限访问该页面")
    return from.name || from.path !== "/" ? false : "/"
  }
  if (needDept && !auth.hasRole("DEPT_HEAD")) {
    ElMessage.error("无权限访问该页面")
    return from.name || from.path !== "/" ? false : "/"
  }
  if (needAny && !needAny.some((r) => auth.hasRole(r))) {
    ElMessage.error("无权限访问该页面")
    return from.name || from.path !== "/" ? false : "/"
  }
  return true
})

export default router
