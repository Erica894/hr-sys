<template>
  <div class="hr-page">
    <PageHeader
      title="我的预算"
      subtitle="部门 / 中心负责人查看本单元已下发的调薪、RSU、年终奖额度"
    />

    <Toolbar>
      <span class="hr-text-secondary">薪酬周期</span>
      <el-select
        v-model="cycleId"
        style="width: 280px"
        placeholder="请选择"
        @change="loadAll"
      >
        <el-option
          v-for="c in cycles"
          :key="c.id"
          :label="`${c.code}（${c.budget_year}）`"
          :value="c.id"
        />
      </el-select>
    </Toolbar>

    <div v-if="cycleId" class="hr-section">
      <el-tabs v-model="activeTab" class="my-budget-tabs">
        <el-tab-pane name="adj">
          <template #label>
            <span class="my-budget-tabs__label">
              <el-icon><Money /></el-icon>现金调薪
              <el-tag v-if="adj.length" size="small" type="info" effect="plain">
                {{ adj.length }}
              </el-tag>
            </span>
          </template>
          <el-table
            :data="adj"
            stripe
            empty-text="暂无可见预算"
            v-loading="loadingAdj"
          >
            <el-table-column label="单元" min-width="180">
              <template #default="{ row }">
                <span class="my-budget-tabs__cell-name">
                  <el-tag
                    size="small"
                    :type="row.target_org_unit_type === 'CENTER' ? 'warning' : 'primary'"
                    effect="plain"
                  >
                    {{ row.target_org_unit_type === "CENTER" ? "中心" : "部门" }}
                  </el-tag>
                  {{ row.target_org_unit_name }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="类型" prop="adjustment_type" width="110">
              <template #default="{ row }">
                <span class="hr-text-secondary">
                  {{ row.adjustment_type === "ANNUAL" ? "年度" : "晋升" }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="员工类别" width="120">
              <template #default="{ row }">{{ catLabel(row.employee_category_1) }}</template>
            </el-table-column>
            <el-table-column label="预算" width="140" align="right">
              <template #default="{ row }">
                <span class="hr-text-mono">{{ fmtMoney(row.budget_amount_cny) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="已分配" width="140" align="right">
              <template #default="{ row }">
                <span class="hr-text-mono">{{ fmtMoney(row.allocated_amount_cny) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="剩余" width="140" align="right">
              <template #default="{ row }">
                <span class="hr-text-mono hr-text-success">
                  {{ fmtMoney(Number(row.budget_amount_cny) - Number(row.allocated_amount_cny || 0)) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="使用率" min-width="180">
              <template #default="{ row }">
                <el-progress
                  :percentage="pct(row.allocated_amount_cny, row.budget_amount_cny)"
                  :stroke-width="6"
                  :status="progressStatus(row.allocated_amount_cny, row.budget_amount_cny)"
                />
              </template>
            </el-table-column>
            <template #empty>
              <EmptyHint
                title="暂无可见预算"
                description="尚未有调薪预算下发到您管辖的单元"
              />
            </template>
          </el-table>
        </el-tab-pane>

        <el-tab-pane name="lti">
          <template #label>
            <span class="my-budget-tabs__label">
              <el-icon><Trophy /></el-icon>RSU
              <el-tag v-if="lti.length" size="small" type="info" effect="plain">
                {{ lti.length }}
              </el-tag>
            </span>
          </template>
          <el-table
            :data="lti"
            stripe
            v-loading="loadingLti"
          >
            <el-table-column label="单元" min-width="180">
              <template #default="{ row }">
                <span class="my-budget-tabs__cell-name">
                  <el-tag
                    size="small"
                    :type="row.target_org_unit_type === 'CENTER' ? 'warning' : 'primary'"
                    effect="plain"
                  >
                    {{ row.target_org_unit_type === "CENTER" ? "中心" : "部门" }}
                  </el-tag>
                  {{ row.target_org_unit_name }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="员工类别" width="120">
              <template #default="{ row }">{{ catLabel(row.employee_category_1) }}</template>
            </el-table-column>
            <el-table-column label="股数配额" width="130" align="right">
              <template #default="{ row }">
                <span class="hr-text-mono">{{ fmtInt(row.shares_quota_ads) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="已授予" width="130" align="right">
              <template #default="{ row }">
                <span class="hr-text-mono">{{ fmtInt(row.shares_used_ads) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="剩余" width="130" align="right">
              <template #default="{ row }">
                <span class="hr-text-mono hr-text-success">
                  {{ fmtInt(Number(row.shares_quota_ads) - Number(row.shares_used_ads || 0)) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="使用率" min-width="180">
              <template #default="{ row }">
                <el-progress
                  :percentage="pct(row.shares_used_ads, row.shares_quota_ads)"
                  :stroke-width="6"
                  :status="progressStatus(row.shares_used_ads, row.shares_quota_ads)"
                />
              </template>
            </el-table-column>
            <template #empty>
              <EmptyHint
                title="暂无可见 RSU 预算"
                description="尚未有 RSU 预算下发到您管辖的单元"
              />
            </template>
          </el-table>
        </el-tab-pane>

        <el-tab-pane name="bonus">
          <template #label>
            <span class="my-budget-tabs__label">
              <el-icon><Present /></el-icon>年终奖
              <el-tag v-if="bonus.length" size="small" type="info" effect="plain">
                {{ bonus.length }}
              </el-tag>
            </span>
          </template>
          <el-table
            :data="bonus"
            stripe
            v-loading="loadingBonus"
          >
            <el-table-column label="单元" min-width="180">
              <template #default="{ row }">
                <span class="my-budget-tabs__cell-name">
                  <el-tag
                    size="small"
                    :type="row.target_org_unit_type === 'CENTER' ? 'warning' : 'primary'"
                    effect="plain"
                  >
                    {{ row.target_org_unit_type === "CENTER" ? "中心" : "部门" }}
                  </el-tag>
                  {{ row.target_org_unit_name }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="员工类别" width="120">
              <template #default="{ row }">{{ catLabel(row.employee_category_1) }}</template>
            </el-table-column>
            <el-table-column label="预算（CNY）" width="160" align="right">
              <template #default="{ row }">
                <span class="hr-text-mono">{{ fmtMoney(row.budget_amount_cny) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="已分配" width="140" align="right">
              <template #default="{ row }">
                <span class="hr-text-mono">{{ fmtMoney(row.allocated_amount_cny) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="剩余" width="140" align="right">
              <template #default="{ row }">
                <span class="hr-text-mono hr-text-success">
                  {{ fmtMoney(Number(row.budget_amount_cny) - Number(row.allocated_amount_cny || 0)) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="使用率" min-width="180">
              <template #default="{ row }">
                <el-progress
                  :percentage="pct(row.allocated_amount_cny, row.budget_amount_cny)"
                  :stroke-width="6"
                  :status="progressStatus(row.allocated_amount_cny, row.budget_amount_cny)"
                />
              </template>
            </el-table-column>
            <template #empty>
              <EmptyHint
                title="暂无可见年终奖预算"
                description="尚未有年终奖预算下发到您管辖的单元"
              />
            </template>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { Money, Present, Trophy } from "@element-plus/icons-vue"
import api from "@/api/client"
import PageHeader from "@/components/PageHeader.vue"
import Toolbar from "@/components/Toolbar.vue"
import EmptyHint from "@/components/EmptyHint.vue"
import { fmtInt, fmtMoney } from "@/utils/format"

const cycles = ref<any[]>([])
const cycleId = ref<number | null>(null)
const activeTab = ref("adj")
const adj = ref<any[]>([])
const lti = ref<any[]>([])
const bonus = ref<any[]>([])
const loadingAdj = ref(false)
const loadingLti = ref(false)
const loadingBonus = ref(false)

function catLabel(c: string) {
  return c === "MANAGEMENT" ? "管理干部" : "员工"
}
function pct(used: any, quota: any) {
  const u = Number(used || 0)
  const q = Number(quota || 0)
  if (q <= 0) return 0
  return Math.min(100, Math.round((u / q) * 100))
}
function progressStatus(used: any, quota: any): "" | "warning" | "exception" | "success" {
  const p = pct(used, quota)
  if (p >= 100) return "exception"
  if (p >= 90) return "warning"
  return ""
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

async function loadBonus() {
  if (!cycleId.value) return
  loadingBonus.value = true
  try {
    const r = await api.get(`/budgets/my-bonus/?cycle_id=${cycleId.value}`)
    bonus.value = r.data.targets || []
  } finally {
    loadingBonus.value = false
  }
}

async function loadAll() {
  await Promise.all([loadAdj(), loadLti(), loadBonus()])
}

onMounted(async () => {
  await loadCycles()
  await loadAll()
})
</script>

<style scoped>
.my-budget-tabs__label {
  display: inline-flex;
  align-items: center;
  gap: var(--hr-space-1);
}
.my-budget-tabs__cell-name {
  display: inline-flex;
  align-items: center;
  gap: var(--hr-space-2);
}
:deep(.my-budget-tabs .el-tabs__nav-wrap::after) {
  background: var(--hr-color-border-light);
}
:deep(.my-budget-tabs .el-tabs__item) {
  font-size: var(--hr-font-size-md);
  height: 44px;
  line-height: 44px;
}
</style>
