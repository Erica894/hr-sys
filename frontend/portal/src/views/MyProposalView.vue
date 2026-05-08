<template>
  <el-card style="max-width: 640px; margin: 40px auto">
    <h3>{{ data?.cycle_code || "My Proposal" }}</h3>
    <el-descriptions v-if="data" :column="1" border>
      <el-descriptions-item label="Annual Final %">
        {{ pct(data.annual_final_pct) }}
      </el-descriptions-item>
      <el-descriptions-item label="Promotion %">
        {{ pct(data.promotion_adjustment_pct) }}
      </el-descriptions-item>
      <el-descriptions-item label="New Monthly Salary">
        {{ data.proposed_monthly_salary }}
      </el-descriptions-item>
      <el-descriptions-item label="RSU ADS">{{ data.granted_ads }}</el-descriptions-item>
      <el-descriptions-item label="Ack Status">
        <el-tag :type="data.ack_status === 'ACKNOWLEDGED' ? 'success' : 'warning'">
          {{ data.ack_status }}
        </el-tag>
      </el-descriptions-item>
    </el-descriptions>
    <el-button
      v-if="data?.ack_status === 'PENDING'"
      type="primary"
      style="margin-top: 16px"
      @click="doAck"
    >
      Acknowledge
    </el-button>
    <el-alert v-if="err" :title="err" type="info" style="margin-top: 12px" />
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import api from "@/api/client"

const data = ref<any>(null)
const cycleId = ref<number | null>(null)
const err = ref("")

function pct(v: any) {
  return v == null ? "-" : (Number(v) * 100).toFixed(2) + "%"
}

async function load() {
  err.value = ""
  try {
    const r = await api.get("/reward-cycle/")
    const list = r.data[0] ? r.data : r.data.results || []
    if (!list.length) {
      err.value = "No cycle yet"
      return
    }
    cycleId.value = list[0].id
    const p = await api.get(`/reward-cycle/${cycleId.value}/my-proposal/`)
    data.value = p.data
  } catch (e: any) {
    err.value = e.response?.data?.detail || "Failed to load proposal"
  }
}

async function doAck() {
  await api.post(`/reward-cycle/${cycleId.value}/ack/`, { comment: "confirmed" })
  await load()
}

onMounted(load)
</script>
