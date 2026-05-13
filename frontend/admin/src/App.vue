<template>
  <el-config-provider>
    <el-container v-if="showNav" style="min-height: 100vh">
      <el-aside v-if="hasManagementMenu" width="220px" style="background: #304156">
        <div
          style="
            height: 56px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            font-weight: 600;
            font-size: 16px;
            letter-spacing: 1px;
            border-bottom: 1px solid #1f2d3d;
          "
        >
          HR-Sys
        </div>
        <el-menu
          :default-active="route.path"
          background-color="#304156"
          text-color="#bfcbd9"
          active-text-color="#409EFF"
          router
          unique-opened
        >
          <!-- HR_ADMIN 菜单 -->
          <template v-if="isAdmin">
            <el-sub-menu index="admin-plans">
              <template #title>方案设计</template>
              <el-menu-item index="/admin/plans/adjustment">调薪方案</el-menu-item>
              <el-menu-item index="/admin/plans/lti">RSU 方案</el-menu-item>
              <el-menu-item index="/admin/plans/bonus">年终奖方案</el-menu-item>
            </el-sub-menu>
            <el-sub-menu index="admin-budgets">
              <template #title>预算管理</template>
              <el-menu-item index="/admin/budgets/adjustment">调薪预算</el-menu-item>
              <el-menu-item index="/admin/budgets/lti">RSU 预算</el-menu-item>
              <el-menu-item index="/admin/budgets/my">我的预算（多租户预览）</el-menu-item>
            </el-sub-menu>
            <el-menu-item index="/admin/org">组织人员</el-menu-item>
            <el-menu-item index="/admin/salary-bands">薪酬区间</el-menu-item>
            <el-sub-menu index="admin-approval">
              <template #title>审批</template>
              <el-menu-item index="/approval">审批列表</el-menu-item>
              <el-menu-item index="/execute">执行下发</el-menu-item>
            </el-sub-menu>
          </template>

          <!-- DEPT_HEAD / CENTER_HEAD 菜单 -->
          <template v-if="isDeptHead || isCenterHead">
            <el-menu-item index="/admin/budgets/my">我的预算</el-menu-item>
            <el-menu-item v-if="isDeptHead" index="/dept/available-budget">本部门预算</el-menu-item>
            <el-menu-item v-if="isDeptHead" index="/allocation">薪酬分配</el-menu-item>
            <el-menu-item v-if="isDeptHead" index="/dept/analysis">分配分析</el-menu-item>
          </template>
        </el-menu>
      </el-aside>

      <el-container>
        <el-header
          style="
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #fff;
            border-bottom: 1px solid #e4e7ed;
            height: 56px;
            padding: 0 20px;
          "
        >
          <div
            v-if="!hasManagementMenu"
            style="font-weight: 600; font-size: 16px; letter-spacing: 1px"
          >
            HR-Sys
          </div>
          <div v-else></div>
          <el-dropdown trigger="click" @command="onCommand">
            <span
              style="
                display: inline-flex;
                align-items: center;
                cursor: pointer;
                color: #606266;
                font-size: 13px;
              "
            >
              <el-avatar :size="28" style="margin-right: 8px; background: #409eff">
                {{ avatarText }}
              </el-avatar>
              {{ roleLabel }}
              <span style="margin-left: 4px; font-size: 10px">▼</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="me">我的薪酬</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </el-header>
        <el-main style="padding: 0; background: #f5f7fa">
          <router-view />
        </el-main>
      </el-container>
    </el-container>

    <el-container v-else style="min-height: 100vh">
      <el-main style="padding: 0">
        <router-view />
      </el-main>
    </el-container>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useAuth } from "@/stores/auth"

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
  if (isAdmin.value) labels.push("HR 管理员")
  if (isDeptHead.value) labels.push("部门负责人")
  if (isCenterHead.value) labels.push("中心负责人")
  if (!labels.length && auth.roles.length) labels.push("员工")
  return labels.join(" / ")
})
const avatarText = computed(() => roleLabel.value.charAt(0) || "U")

function onCommand(cmd: string) {
  if (cmd === "me") {
    router.push("/me/compensation")
  } else if (cmd === "logout") {
    auth.logout()
    router.push("/login")
  }
}
</script>
