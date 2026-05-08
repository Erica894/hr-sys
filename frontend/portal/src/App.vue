<template>
  <el-container style="min-height: 100vh">
    <el-header
      v-if="showNav"
      style="display: flex; align-items: center; background: #304156; color: #fff"
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
