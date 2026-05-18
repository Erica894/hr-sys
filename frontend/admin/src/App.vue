<template>
  <el-config-provider>
    <el-container v-if="showNav" class="app-shell">
      <el-aside v-if="hasManagementMenu" width="220px" class="app-sidebar">
        <div class="app-sidebar__brand">
          <span class="app-sidebar__brand-mark">HR</span>
          <span class="app-sidebar__brand-text">薪酬管理系统</span>
        </div>
        <el-menu
          :default-active="route.path"
          background-color="transparent"
          text-color="var(--hr-color-sidebar-text)"
          active-text-color="var(--hr-color-sidebar-text-active)"
          router
          unique-opened
          class="app-sidebar__menu"
        >
          <!-- HR_ADMIN 菜单 -->
          <template v-if="isAdmin">
            <el-sub-menu index="admin-categories">
              <template #title>
                <el-icon><Collection /></el-icon>
                <span>员工类别</span>
              </template>
              <el-menu-item index="/admin/categories/schemes">类别方案</el-menu-item>
              <el-menu-item index="/admin/categories/assignments">员工赋类别</el-menu-item>
            </el-sub-menu>
            <el-sub-menu index="admin-plans">
              <template #title>
                <el-icon><Document /></el-icon>
                <span>方案设计</span>
              </template>
              <el-menu-item index="/admin/plans/adjustment">调薪方案</el-menu-item>
              <el-menu-item index="/admin/plans/lti">RSU 方案</el-menu-item>
              <el-menu-item index="/admin/plans/bonus">年终奖方案</el-menu-item>
            </el-sub-menu>
            <el-sub-menu index="admin-budgets">
              <template #title>
                <el-icon><Money /></el-icon>
                <span>预算管理</span>
              </template>
              <el-menu-item index="/admin/budgets/my">我的预算</el-menu-item>
              <el-menu-item index="/admin/budgets/derived-overview">派生预算总览</el-menu-item>
            </el-sub-menu>
            <el-menu-item index="/admin/org">
              <el-icon><OfficeBuilding /></el-icon>
              <template #title>组织人员</template>
            </el-menu-item>
            <el-menu-item index="/admin/salary-bands">
              <el-icon><Histogram /></el-icon>
              <template #title>薪酬区间</template>
            </el-menu-item>
            <el-sub-menu index="admin-approval">
              <template #title>
                <el-icon><CircleCheck /></el-icon>
                <span>审批中心</span>
              </template>
              <el-menu-item index="/approval">审批列表</el-menu-item>
              <el-menu-item index="/execute">执行下发</el-menu-item>
            </el-sub-menu>
          </template>

          <!-- DEPT_HEAD / CENTER_HEAD 菜单 -->
          <template v-if="isDeptHead || isCenterHead">
            <el-menu-item index="/admin/budgets/my">
              <el-icon><Money /></el-icon>
              <template #title>我的预算</template>
            </el-menu-item>
            <el-menu-item v-if="isDeptHead" index="/dept/available-budget">
              <el-icon><Wallet /></el-icon>
              <template #title>本部门预算</template>
            </el-menu-item>
            <el-menu-item v-if="isDeptHead" index="/allocation">
              <el-icon><DataLine /></el-icon>
              <template #title>薪酬分配</template>
            </el-menu-item>
            <el-menu-item v-if="isDeptHead" index="/dept/analysis">
              <el-icon><PieChart /></el-icon>
              <template #title>分配分析</template>
            </el-menu-item>
          </template>
        </el-menu>
      </el-aside>

      <el-container>
        <el-header class="app-header">
          <div v-if="!hasManagementMenu" class="app-header__brand">
            <span class="app-sidebar__brand-mark">HR</span>
            <span>{{ t("header.brand") }}</span>
          </div>
          <div v-else />
          <div class="app-header__right">
            <LangSwitcher />
            <el-dropdown trigger="click" @command="onCommand">
              <span class="app-header__user">
                <el-avatar :size="32" class="app-header__avatar">
                  {{ avatarText }}
                </el-avatar>
                <span class="app-header__user-meta">
                  <span class="app-header__user-name">{{ userName }}</span>
                  <span class="app-header__user-role">{{ roleLabel }}</span>
                </span>
                <el-icon class="app-header__caret"><CaretBottom /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="me">
                    <el-icon><User /></el-icon>{{ t("header.menu.my_compensation") }}
                  </el-dropdown-item>
                  <el-dropdown-item command="logout" divided>
                    <el-icon><SwitchButton /></el-icon>{{ t("header.menu.logout") }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>
        <el-main class="app-main">
          <router-view />
        </el-main>
      </el-container>
    </el-container>

    <el-container v-else class="app-shell">
      <el-main style="padding: 0">
        <router-view />
      </el-main>
    </el-container>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useI18n } from "vue-i18n"
import { useRoute, useRouter } from "vue-router"
import { useAuth } from "@/stores/auth"
import LangSwitcher from "@/components/LangSwitcher.vue"
import {
  CaretBottom,
  CircleCheck,
  Collection,
  DataLine,
  Document,
  Histogram,
  Money,
  OfficeBuilding,
  PieChart,
  SwitchButton,
  User,
  Wallet,
} from "@element-plus/icons-vue"

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuth()

const showNav = computed(() => route.path !== "/login")
const isAdmin = computed(() => auth.hasRole("HR_ADMIN"))
const isDeptHead = computed(() => auth.hasRole("DEPT_HEAD"))
const isCenterHead = computed(() => auth.hasRole("CENTER_HEAD"))
const hasManagementMenu = computed(() => isAdmin.value || isDeptHead.value || isCenterHead.value)
const roleLabel = computed(() => {
  const labels: string[] = []
  if (isAdmin.value) labels.push(t("header.user_role.HR_ADMIN"))
  if (isDeptHead.value) labels.push(t("header.user_role.DEPT_HEAD"))
  if (isCenterHead.value) labels.push(t("header.user_role.CENTER_HEAD"))
  if (!labels.length && auth.roles.length) labels.push(t("header.user_role.EMPLOYEE"))
  return labels.join(" / ")
})
const userName = computed(() => auth.user?.email?.split("@")[0] || "—")
const avatarText = computed(() => userName.value.charAt(0).toUpperCase() || "U")

function onCommand(cmd: string) {
  if (cmd === "me") {
    router.push("/me/compensation")
  } else if (cmd === "logout") {
    auth.logout()
    router.push("/login")
  }
}
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
}

/* ===== 侧边栏 ===== */
.app-sidebar {
  background: var(--hr-color-sidebar-bg);
  border-right: 1px solid rgba(255, 255, 255, 0.04);
  overflow-x: hidden;
}

.app-sidebar__brand {
  height: 56px;
  display: flex;
  align-items: center;
  gap: var(--hr-space-2);
  padding: 0 var(--hr-space-5);
  color: var(--hr-color-text-on-dark);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.app-sidebar__brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: var(--hr-color-brand);
  color: #fff;
  font-weight: var(--hr-font-weight-bold);
  font-size: var(--hr-font-size-xs);
  letter-spacing: 0.5px;
  border-radius: var(--hr-radius-sm);
}

.app-sidebar__brand-text {
  font-weight: var(--hr-font-weight-semibold);
  font-size: var(--hr-font-size-md);
  letter-spacing: 0.5px;
}

.app-sidebar__menu {
  border-right: none;
  padding: var(--hr-space-2) 0;
}

:deep(.app-sidebar__menu .el-menu-item),
:deep(.app-sidebar__menu .el-sub-menu__title) {
  font-size: var(--hr-font-size-md);
  height: 44px;
  line-height: 44px;
  color: var(--hr-color-sidebar-text);
}

:deep(.app-sidebar__menu .el-menu-item:hover),
:deep(.app-sidebar__menu .el-sub-menu__title:hover) {
  background: var(--hr-color-sidebar-bg-hover) !important;
  color: var(--hr-color-sidebar-text-active) !important;
}

:deep(.app-sidebar__menu .el-menu-item.is-active) {
  background: var(--hr-color-sidebar-bg-active) !important;
  color: var(--hr-color-sidebar-text-active) !important;
  position: relative;
}

:deep(.app-sidebar__menu .el-menu-item.is-active::before) {
  content: "";
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  background: var(--hr-color-sidebar-accent);
  border-radius: 0 var(--hr-radius-sm) var(--hr-radius-sm) 0;
}

:deep(.app-sidebar__menu .el-sub-menu .el-menu-item) {
  background: transparent !important;
  padding-left: 48px !important;
}

:deep(.app-sidebar__menu .el-icon) {
  vertical-align: middle;
  margin-right: var(--hr-space-2);
}

/* ===== 顶部 header (Workday) ===== */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--hr-color-topbar-bg);
  border-bottom: none;
  box-shadow: 0 2px 8px rgba(8, 25, 61, 0.18);
  height: 56px;
  padding: 0 var(--hr-space-6);
}

.app-header__brand {
  display: flex;
  align-items: center;
  gap: var(--hr-space-2);
  font-weight: var(--hr-font-weight-semibold);
  font-size: var(--hr-font-size-md);
  color: var(--hr-color-topbar-text);
}

.app-header__right {
  display: inline-flex;
  align-items: center;
  gap: var(--hr-space-2);
}

.app-header__user {
  display: inline-flex;
  align-items: center;
  gap: var(--hr-space-2);
  cursor: pointer;
  padding: var(--hr-space-1) var(--hr-space-2);
  border-radius: var(--hr-radius-md);
  transition: background var(--hr-transition-fast);
}

.app-header__user:hover {
  background: var(--hr-color-topbar-hover);
}

.app-header__avatar {
  background: var(--hr-color-brand-accent) !important;
  color: #fff;
  font-weight: var(--hr-font-weight-semibold);
}

.app-header__user-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.2;
}

.app-header__user-name {
  font-size: var(--hr-font-size-sm);
  font-weight: var(--hr-font-weight-medium);
  color: var(--hr-color-topbar-text);
}

.app-header__user-role {
  font-size: var(--hr-font-size-xs);
  color: var(--hr-color-topbar-text-hint);
}

.app-header__caret {
  font-size: 12px;
  color: var(--hr-color-topbar-text-hint);
}

/* ===== 主内容区 ===== */
.app-main {
  padding: 0;
  background: var(--hr-color-bg-page);
}
</style>
