<template>
  <el-card style="max-width: 420px; margin: 80px auto">
    <h2>HR-Sys Portal</h2>
    <el-form @submit.prevent="doLogin">
      <el-form-item label="Email">
        <el-input v-model="email" autocomplete="username" />
      </el-form-item>
      <el-form-item label="Password">
        <el-input v-model="pw" type="password" autocomplete="current-password" />
      </el-form-item>
      <el-button type="primary" native-type="submit" @click="doLogin">Sign in</el-button>
    </el-form>
    <el-alert v-if="err" :title="err" type="error" style="margin-top: 12px" />
  </el-card>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { useAuth } from "@/stores/auth"
import { useRouter } from "vue-router"

const store = useAuth()
const router = useRouter()
const email = ref("")
const pw = ref("")
const err = ref("")

async function doLogin() {
  err.value = ""
  try {
    await store.login(email.value, pw.value)
    router.push("/my-proposal")
  } catch (e: any) {
    err.value = e.response?.data?.detail || "Login failed"
  }
}
</script>
