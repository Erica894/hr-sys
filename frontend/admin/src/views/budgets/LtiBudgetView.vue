<template>
  <el-container direction="vertical" style="padding: 16px">
    <h3 style="margin: 0 0 16px">RSU 预算池</h3>
    <el-form inline>
      <el-form-item label="RSU 方案">
        <el-select v-model="planId" placeholder="选择方案" style="width: 320px" @change="load">
          <el-option
            v-for="p in plans"
            :key="p.id"
            :label="`${p.code} - ${p.name}`"
            :value="p.id"
          />
        </el-select>
      </el-form-item>
    </el-form>

    <el-table v-if="planId" :data="rows" border v-loading="loading" style="margin-top: 12px">
      <el-table-column label="员工类别" width="140">
        <template #default="{ row }">{{ catLabel(row.employee_category_1) }}</template>
      </el-table-column>
      <el-table-column label="人数配额">
        <template #default="{ row }">
          <div style="display: flex; flex-direction: column; gap: 4px">
            <el-input-number
              v-model="row.headcount_quota"
              :min="0"
              :step="1"
              size="small"
              :disabled="loading || saving"
            />
            <div style="font-size: 12px; color: #606266">
              已使用 {{ row.headcount_used || 0 }}
            </div>
            <el-progress :percentage="pct(row.headcount_used, row.headcount_quota)" :stroke-width="6" />
          </div>
        </template>
      </el-table-column>
      <el-table-column label="股数配额 (ADS)">
        <template #default="{ row }">
          <div style="display: flex; flex-direction: column; gap: 4px">
            <el-input-number
              v-model="row.shares_quota_ads"
              :min="0"
              :step="1000"
              size="small"
              :disabled="loading || saving"
            />
            <div style="font-size: 12px; color: #606266">
              已使用 {{ fmtInt(row.shares_used_ads) }}
            </div>
            <el-progress :percentage="pct(row.shares_used_ads, row.shares_quota_ads)" :stroke-width="6" />
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="planId" style="margin-top: 16px">
      <el-button type="primary" @click="save" :loading="saving">保存预算</el-button>
    </div>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { ElMessage } from "element-plus"
import api from "@/api/client"

type LtiCell = {
  employee_category_1: string
  headcount_quota: number
  shares_quota_ads: number
  headcount_used: number
  shares_used_ads: number
}

const plans = ref<any[]>([])
const planId = ref<number | null>(null)
const rows = ref<LtiCell[]>([])
const loading = ref(false)
const saving = ref(false)

function catLabel(c: string) {
  return c === "MANAGEMENT" ? "管理干部" : "员工"
}

function fmtInt(v: any) {
  return Number(v || 0).toLocaleString("zh-CN")
}

function pct(used: number, quota: number) {
  const u = Number(used || 0)
  const q = Number(quota || 0)
  if (q <= 0) return 0
  return Math.min(100, Math.round((u / q) * 100))
}

async function loadPlans() {
  const r = await api.get("/admin/lti-plans/")
  plans.value = Array.isArray(r.data) ? r.data : r.data.results || []
  if (plans.value.length && planId.value == null) {
    planId.value = plans.value[0].id
  }
}

async function load() {
  if (!planId.value) return
  loading.value = true
  try {
    const r = await api.get(`/admin/lti-plans/${planId.value}/budget/`)
    const data: LtiCell[] = r.data.rows || []
    const order = ["MANAGEMENT", "STAFF"]
    rows.value = order.map(
      (cat) =>
        data.find((d) => d.employee_category_1 === cat) || {
          employee_category_1: cat,
          headcount_quota: 0,
          shares_quota_ads: 0,
          headcount_used: 0,
          shares_used_ads: 0,
        }
    )
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!planId.value) return
  saving.value = true
  try {
    const payload = {
      rows: rows.value.map((r) => ({
        employee_category_1: r.employee_category_1,
        headcount_quota: r.headcount_quota,
        shares_quota_ads: r.shares_quota_ads,
      })),
    }
    await api.put(`/admin/lti-plans/${planId.value}/budget/`, payload)
    ElMessage.success("预算已保存")
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadPlans()
  await load()
})
</script>
