<template>
  <el-container direction="vertical" style="padding: 16px">
    <h3 style="margin: 0 0 16px">我的预算</h3>
    <el-form inline>
      <el-form-item label="Reward Cycle">
        <el-select v-model="cycleId" style="width: 320px" @change="loadAll">
          <el-option
            v-for="c in cycles"
            :key="c.id"
            :label="`${c.code} (${c.budget_year})`"
            :value="c.id"
          />
        </el-select>
      </el-form-item>
    </el-form>

    <el-tabs v-model="activeTab" v-if="cycleId" style="margin-top: 12px">
      <el-tab-pane label="现金调薪" name="adj">
        <el-table :data="adj" border empty-text="暂无可见预算" v-loading="loadingAdj">
          <el-table-column label="单元" min-width="160">
            <template #default="{ row }">
              <el-tag size="small" :type="row.target_org_unit_type === 'CENTER' ? 'warning' : 'primary'">
                {{ row.target_org_unit_type }}
              </el-tag>
              <span style="margin-left: 6px">{{ row.target_org_unit_name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="类型" prop="adjustment_type" width="110" />
          <el-table-column label="员工类别" width="120">
            <template #default="{ row }">{{ catLabel(row.employee_category_1) }}</template>
          </el-table-column>
          <el-table-column label="预算" width="140">
            <template #default="{ row }">{{ fmt(row.budget_amount_cny) }}</template>
          </el-table-column>
          <el-table-column label="已分配" width="140">
            <template #default="{ row }">{{ fmt(row.allocated_amount_cny) }}</template>
          </el-table-column>
          <el-table-column label="剩余" width="140">
            <template #default="{ row }">
              {{ fmt(Number(row.budget_amount_cny) - Number(row.allocated_amount_cny || 0)) }}
            </template>
          </el-table-column>
          <el-table-column label="使用率" width="180">
            <template #default="{ row }">
              <el-progress
                :percentage="pct(row.allocated_amount_cny, row.budget_amount_cny)"
                :stroke-width="8"
              />
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="LTI" name="lti">
        <el-table :data="lti" border empty-text="暂无可见 LTI 预算" v-loading="loadingLti">
          <el-table-column label="单元" min-width="160">
            <template #default="{ row }">
              <el-tag size="small" :type="row.target_org_unit_type === 'CENTER' ? 'warning' : 'primary'">
                {{ row.target_org_unit_type }}
              </el-tag>
              <span style="margin-left: 6px">{{ row.target_org_unit_name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="员工类别" width="120">
            <template #default="{ row }">{{ catLabel(row.employee_category_1) }}</template>
          </el-table-column>
          <el-table-column label="股数配额" width="130">
            <template #default="{ row }">{{ fmtInt(row.shares_quota_ads) }}</template>
          </el-table-column>
          <el-table-column label="已授予" width="130">
            <template #default="{ row }">{{ fmtInt(row.shares_used_ads) }}</template>
          </el-table-column>
          <el-table-column label="剩余" width="130">
            <template #default="{ row }">
              {{ fmtInt(Number(row.shares_quota_ads) - Number(row.shares_used_ads || 0)) }}
            </template>
          </el-table-column>
          <el-table-column label="使用率" width="180">
            <template #default="{ row }">
              <el-progress
                :percentage="pct(row.shares_used_ads, row.shares_quota_ads)"
                :stroke-width="8"
              />
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="年终奖" name="bonus">
        <el-empty description="本期未启用 / 待后续 sprint" />
      </el-tab-pane>
    </el-tabs>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import api from "@/api/client"

const cycles = ref<any[]>([])
const cycleId = ref<number | null>(null)
const activeTab = ref("adj")
const adj = ref<any[]>([])
const lti = ref<any[]>([])
const loadingAdj = ref(false)
const loadingLti = ref(false)

function catLabel(c: string) {
  return c === "MANAGEMENT" ? "管理干部" : "员工"
}
function fmt(v: any) {
  return Number(v || 0).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}
function fmtInt(v: any) {
  return Number(v || 0).toLocaleString("zh-CN")
}
function pct(used: any, quota: any) {
  const u = Number(used || 0)
  const q = Number(quota || 0)
  if (q <= 0) return 0
  return Math.min(100, Math.round((u / q) * 100))
}

async function loadCycles() {
  const r = await api.get("/reward-cycle/")
  cycles.value = Array.isArray(r.data) ? r.data : r.data.results || []
  if (cycles.value.length && cycleId.value == null) cycleId.value = cycles.value[0].id
}

async function loadAdj() {
  if (!cycleId.value) return
  loadingAdj.value = true
  try {
    const r = await api.get(`/budgets/my-adjustment/?cycle_id=${cycleId.value}`)
    adj.value = r.data.targets || []
  } finally {
    loadingAdj.value = false
  }
}

async function loadLti() {
  if (!cycleId.value) return
  loadingLti.value = true
  try {
    const r = await api.get(`/budgets/my-lti/?cycle_id=${cycleId.value}`)
    lti.value = r.data.targets || []
  } finally {
    loadingLti.value = false
  }
}

async function loadAll() {
  await Promise.all([loadAdj(), loadLti()])
}

onMounted(async () => {
  await loadCycles()
  await loadAll()
})
</script>
