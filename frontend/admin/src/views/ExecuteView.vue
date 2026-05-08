<template>
  <el-card style="max-width: 600px; margin: 40px auto">
    <h3>Execute Reward Cycle</h3>
    <el-descriptions v-if="cycle" :column="2" border>
      <el-descriptions-item label="Code">{{ cycle.code }}</el-descriptions-item>
      <el-descriptions-item label="Status">{{ cycle.status }}</el-descriptions-item>
    </el-descriptions>
    <el-form style="margin-top: 16px" @submit.prevent="doExecute">
      <el-form-item label="MFA Code">
        <el-input v-model="code" />
      </el-form-item>
      <el-button
        type="danger"
        @click="doExecute"
        :disabled="cycle?.status !== 'APPROVED_PENDING_EXECUTE' && cycle?.status !== 'APPROVED'"
      >
        Execute
      </el-button>
    </el-form>
    <el-alert v-if="msg" :title="msg" :type="msgType" style="margin-top: 16px" />
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import api from "@/api/client"

const cycle = ref<any>(null)
const code = ref("")
const msg = ref("")
const msgType = ref<"success" | "error">("success")

async function load() {
  const r = await api.get("/reward-cycle/")
  cycle.value = r.data[0] || r.data.results?.[0]
}
async function doExecute() {
  try {
    const r = await api.post(
      `/reward-cycle/${cycle.value.id}/execute/`,
      null,
      { headers: { "X-MFA-Code": code.value } }
    )
    msg.value = `Executed at ${r.data.executed_at || "now"}`
    msgType.value = "success"
    await load()
  } catch (e: any) {
    msg.value = e.response?.data?.detail || "failed"
    msgType.value = "error"
  }
}
onMounted(load)
</script>
