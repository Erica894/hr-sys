<template>
  <el-config-provider>
    <el-container style="min-height: 100vh">
      <el-header v-if="showNav" style="display: flex; align-items: center; background: #304156">
        <span style="color: #fff; font-weight: 600; margin-right: 24px">HR-Sys Admin</span>
        <el-menu
          mode="horizontal"
          background-color="#304156"
          text-color="#fff"
          active-text-color="#409EFF"
          :default-active="route.path"
          router
          style="flex: 1; border: none"
        >
          <el-menu-item index="/allocation">Allocation</el-menu-item>
          <el-menu-item index="/approval">Approval</el-menu-item>
          <el-menu-item index="/execute">Execute</el-menu-item>
        </el-menu>
        <el-button size="small" @click="logout">Logout</el-button>
      </el-header>
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

function logout() {
  auth.logout()
  router.push("/login")
}
</script>
