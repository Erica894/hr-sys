<template>
  <el-container direction="vertical" style="padding: 16px">
    <el-descriptions v-if="cycle" :column="4" border>
      <el-descriptions-item label="Cycle">{{ cycle.code }}</el-descriptions-item>
      <el-descriptions-item label="Status">
        <el-tag>{{ cycle.status }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="Budget Year">{{ cycle.budget_year }}</el-descriptions-item>
      <el-descriptions-item label="Rows">{{ rows.length }}</el-descriptions-item>
    </el-descriptions>
    <el-table :data="rows" border style="margin-top: 12px">
      <el-table-column prop="employee_code" label="Code" width="100" />
      <el-table-column prop="name_cn" label="Name" width="120" />
      <el-table-column prop="dept_name" label="Dept" width="140" />
      <el-table-column prop="job_level_current" label="Level" width="70" />
      <el-table-column label="Promotion %" width="110">
        <template #default="{ row }">{{ fmt(row.promotion_adjustment_pct) }}</template>
      </el-table-column>
      <el-table-column label="Annual Suggest %" width="130">
        <template #default="{ row }">{{ fmt(row.annual_suggested_pct) }}</template>
      </el-table-column>
      <el-table-column label="Manager Δ %" width="120">
        <template #default="{ row }">
          <el-input-number
            v-model="row.annual_manager_delta_pct"
            :step="0.005"
            :precision="4"
            size="small"
            :disabled="!editable"
            @change="markDirty(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="Final %" width="100">
        <template #default="{ row }">{{ fmt(computeFinal(row)) }}</template>
      </el-table-column>
      <el-table-column label="New Salary" width="130">
        <template #default="{ row }">{{ fmtSalary(row) }}</template>
      </el-table-column>
      <el-table-column label="RSU ADS" width="120">
        <template #default="{ row }">
          <el-input-number
            v-model="row.granted_ads"
            :min="0"
            :step="100"
            size="small"
            :disabled="!editable"
            @change="markDirty(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="Total Comp" width="140">
        <template #default="{ row }">{{ fmtTotal(row) }}</template>
      </el-table-column>
    </el-table>
    <el-space style="margin-top: 16px">
      <el-button @click="save" :disabled="!editable || !dirty.size">
        Save ({{ dirty.size }})
      </el-button>
      <el-button
        type="primary"
        @click="submit"
        :disabled="cycle?.status !== 'ALLOCATING' && cycle?.status !== 'DRAFT'"
      >
        Submit for Approval
      </el-button>
    </el-space>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue"
import api from "@/api/client"

const rows = ref<any[]>([])
const cycle = ref<any>(null)
const dirty = ref(new Set<number>())
const editable = computed(() => ["DRAFT", "ALLOCATING"].includes(cycle.value?.status))

async function load() {
  const r = await api.get("/reward-cycle/")
  const c = r.data[0] || r.data.results?.[0]
  if (!c) return
  const d = await api.get(`/reward-cycle/${c.id}/allocation/`)
  cycle.value = d.data.cycle
  rows.value = d.data.rows
}
function markDirty(row: any) {
  dirty.value.add(row.employee_id)
}
function computeFinal(row: any) {
  const s = Number(row.annual_suggested_pct || 0)
  const m = Number(row.annual_manager_delta_pct || 0)
  return (s + m).toFixed(4)
}
function fmt(v: any) {
  return v == null ? "-" : (Number(v) * 100).toFixed(2) + "%"
}
function fmtSalary(row: any) {
  const cur = Number(row.current_monthly_salary || 0)
  const p = Number(row.promotion_adjustment_pct || 0) + Number(computeFinal(row))
  return (cur * (1 + p)).toFixed(2)
}
function fmtTotal(row: any) {
  const base = Number(fmtSalary(row)) * 12
  const rsu = (Number(row.granted_ads || 0) * Number(row.unit_price_at_grant || 0)) / 5
  return (base + rsu).toFixed(2)
}
async function save() {
  const items = rows.value
    .filter((r) => dirty.value.has(r.employee_id))
    .map((r) => ({
      employee_id: r.employee_id,
      annual_manager_delta_pct: r.annual_manager_delta_pct,
      granted_ads: r.granted_ads,
    }))
  await api.patch(`/reward-cycle/${cycle.value.id}/proposals/`, { items })
  dirty.value.clear()
  await load()
}
async function submit() {
  await api.post(`/reward-cycle/${cycle.value.id}/submit/`)
  await load()
}
onMounted(load)
</script>
