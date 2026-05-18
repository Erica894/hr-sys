<template>
  <el-container style="min-height: 100vh">
    <el-header
      v-if="showNav"
      style="display: flex; align-items: center; background: #1d4380; color: #fff; box-shadow: 0 2px 8px rgba(8, 25, 61, 0.18)"
    >
      <span style="font-weight: 600; flex: 1">HR-Sys Employee Portal</span>
      <el-button size="small" @click="logout">Logout</el-button>
    </el-header>
    <el-main style="padding: 0">
      <router-view />
    </el-main>
  </el-container>
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
