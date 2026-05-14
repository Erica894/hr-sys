<template>
  <div class="hr-page">
    <PageHeader
      title="RSU 预算池"
      subtitle="按 RSU 方案维度配置公司层股数与人数配额，并下发到部门 / 中心"
    />

    <Toolbar>
      <span class="hr-text-secondary">RSU 方案</span>
      <el-select v-model="planId" placeholder="选择方案" style="width: 320px" @change="load">
        <el-option
          v-for="p in plans"
          :key="p.id"
          :label="`${p.code} - ${p.name}`"
          :value="p.id"
        />
      </el-select>
    </Toolbar>

    <h3 class="hr-section-title">公司层预算</h3>
    <el-table v-if="planId" :data="rows" border v-loading="loading" style="margin-top: 4px">
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
            <div style="display: flex; gap: 8px; align-items: center">
              <el-input-number
                v-model="row.shares_quota_ads"
                :min="0"
                :step="1000"
                size="small"
                :disabled="loading || saving"
              />
              <el-button size="small" type="primary" link @click="openDistribute(row)">
                下发 ▾
              </el-button>
            </div>
            <div style="font-size: 12px; color: #606266">
              已使用 {{ fmtInt(row.shares_used_ads) }}
              <span v-if="row.distribution_rule" style="margin-left: 8px; color: #67c23a">
                规则: {{ ruleLabel(row.distribution_rule) }}
              </span>
            </div>
            <el-progress :percentage="pct(row.shares_used_ads, row.shares_quota_ads)" :stroke-width="6" />
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="planId" style="margin-top: 16px">
      <el-button type="primary" @click="save" :loading="saving">保存预算</el-button>
    </div>

    <h4 v-if="planId" style="margin: 24px 0 8px">已下发到部门 / 中心</h4>
    <el-table v-if="planId" :data="targets" border empty-text="暂未下发" v-loading="loading">
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
      <el-table-column label="回收(执行后)" width="130">
        <template #default="{ row }">{{ fmtInt(row.reclaimed_shares_ads) }}</template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="distDialog"
      :title="`下发 RSU / ${distCatLabel}`"
      width="720"
    >
      <el-form label-width="92px">
        <el-form-item label="规则">
          <el-radio-group v-model="distMode" @change="distPreview = []">
            <el-radio-button value="MANUAL">手动</el-radio-button>
            <el-radio-button value="HEADCOUNT">按人头</el-radio-button>
            <el-radio-button value="SALARY_TOTAL">按薪资基数</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="目标层级">
          <el-checkbox-group v-model="distTypeFilter">
            <el-checkbox value="DEPT">部门 DEPT</el-checkbox>
            <el-checkbox value="CENTER">中心 CENTER</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="选目标">
          <el-tree
            ref="treeRef"
            :data="orgTreeData"
            show-checkbox
            node-key="id"
            :default-expand-all="true"
            :props="{ label: 'name' }"
            @check="onTreeCheck"
            style="max-height: 280px; overflow: auto; width: 100%"
          />
        </el-form-item>
        <el-form-item v-if="distMode === 'MANUAL' && distSelectedIds.length" label="手填股数">
          <div style="display: flex; flex-direction: column; gap: 6px; width: 100%">
            <div
              v-for="id in distSelectedIds"
              :key="id"
              style="display: flex; align-items: center; gap: 8px"
            >
              <span style="width: 160px">{{ orgLabel(id) }}</span>
              <el-input-number v-model="distManual[id]" :min="0" :step="100" size="small" />
            </div>
            <div style="font-size: 12px; color: #909399">
              合计 {{ fmtInt(manualSum) }} / 公司层 {{ fmtInt(distSourceShares) }}
              <span v-if="manualSum > Number(distSourceShares)" style="color: #f56c6c">
                超出公司层配额
              </span>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <div v-if="distPreview.length" style="margin-top: 12px">
        <h5 style="margin: 0 0 6px">分配预览</h5>
        <el-table :data="distPreview" border size="small">
          <el-table-column label="单元">
            <template #default="{ row }">{{ orgLabel(row.target_org_unit_id) }}</template>
          </el-table-column>
          <el-table-column label="拟分配股数" width="200">
            <template #default="{ row }">{{ fmtInt(row.shares_ads) }}</template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="distDialog = false">取消</el-button>
        <el-button @click="distributeDryRun" :disabled="!canSubmit">预览</el-button>
        <el-button type="primary" @click="distributeCommit" :disabled="!canSubmit">
          确认下发
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import api from "@/api/client"
import PageHeader from "@/components/PageHeader.vue"
import Toolbar from "@/components/Toolbar.vue"
import { fmtInt } from "@/utils/format"

type LtiCell = {
  employee_category_1: string
  headcount_quota: number
  shares_quota_ads: number
  headcount_used: number
  shares_used_ads: number
  distribution_rule?: string
}

type LtiTarget = {
  id: number
  target_org_unit_id: number
  target_org_unit_name: string
  target_org_unit_type: string
  employee_category_1: string
  shares_quota_ads: number | string
  shares_used_ads: number | string
  reclaimed_shares_ads: number | string
}

type OrgUnitDTO = { id: number; code: string; name: string; type: string; parent_id: number | null }

const plans = ref<any[]>([])
const planId = ref<number | null>(null)
const rows = ref<LtiCell[]>([])
const targets = ref<LtiTarget[]>([])
const loading = ref(false)
const saving = ref(false)

function catLabel(c: string) {
  return c === "MANAGEMENT" ? "管理干部" : "员工"
}
function pct(used: number, quota: number) {
  const u = Number(used || 0)
  const q = Number(quota || 0)
  if (q <= 0) return 0
  return Math.min(100, Math.round((u / q) * 100))
}
function ruleLabel(r?: string) {
  return r === "HEADCOUNT" ? "按人头" : r === "SALARY_TOTAL" ? "按薪资基数" : "手动"
}

async function loadPlans() {
  const r = await api.get("/admin/lti-plans/")
  plans.value = Array.isArray(r.data) ? r.data : r.data.results || []
  if (plans.value.length && planId.value == null) planId.value = plans.value[0].id
}

async function load() {
  if (!planId.value) return
  loading.value = true
  try {
    const r = await api.get(`/admin/lti-plans/${planId.value}/budget/`)
    const data: LtiCell[] = r.data.company || r.data.rows || []
    const order = ["MANAGEMENT", "STAFF"]
    rows.value = order.map(
      (cat) =>
        data.find((d) => d.employee_category_1 === cat) || {
          employee_category_1: cat,
          headcount_quota: 0,
          shares_quota_ads: 0,
          headcount_used: 0,
          shares_used_ads: 0,
        },
    )
    targets.value = r.data.targets || []
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

// 下发对话框 ----
const distDialog = ref(false)
const distCat = ref<"MANAGEMENT" | "STAFF">("STAFF")
const distMode = ref<"MANUAL" | "HEADCOUNT" | "SALARY_TOTAL">("HEADCOUNT")
const distSourceShares = ref<number>(0)
const distTypeFilter = ref<string[]>(["DEPT", "CENTER"])
const distSelectedIds = ref<number[]>([])
const distManual = ref<Record<number, number>>({})
const distPreview = ref<{ target_org_unit_id: number; shares_ads: number }[]>([])
const orgUnits = ref<OrgUnitDTO[]>([])
const treeRef = ref<any>(null)

const distCatLabel = computed(() => (distCat.value === "MANAGEMENT" ? "管理干部" : "员工"))

const orgTreeData = computed(() => {
  const types = new Set(distTypeFilter.value)
  const filtered = orgUnits.value.filter((o) => types.has(o.type))
  const byParent: Record<string, any[]> = {}
  for (const o of filtered) {
    const k = String(o.parent_id ?? "ROOT")
    byParent[k] = byParent[k] || []
    byParent[k].push({ id: o.id, name: `${o.name} (${o.type})`, type: o.type, children: [] })
  }
  for (const list of Object.values(byParent)) {
    for (const node of list) {
      node.children = byParent[String(node.id)] || []
    }
  }
  return byParent["ROOT"] || []
})

const manualSum = computed(() =>
  distSelectedIds.value.reduce((s, id) => s + Number(distManual.value[id] || 0), 0),
)

const canSubmit = computed(() => {
  if (!distSelectedIds.value.length) return false
  if (distMode.value === "MANUAL" && manualSum.value > Number(distSourceShares.value)) return false
  return true
})

function orgLabel(id: number) {
  const ou = orgUnits.value.find((o) => o.id === id)
  return ou ? `${ou.name} [${ou.type}]` : `#${id}`
}

async function ensureOrgUnits() {
  if (orgUnits.value.length) return
  const r = await api.get("/iam/org-units/?type=DEPT,CENTER")
  orgUnits.value = r.data
}

async function openDistribute(row: LtiCell) {
  await ensureOrgUnits()
  distCat.value = row.employee_category_1 as "MANAGEMENT" | "STAFF"
  distSourceShares.value = Number(row.shares_quota_ads || 0)
  distMode.value = "HEADCOUNT"
  distTypeFilter.value = ["DEPT", "CENTER"]
  distSelectedIds.value = []
  distManual.value = {}
  distPreview.value = []
  distDialog.value = true
}

function onTreeCheck() {
  if (!treeRef.value) return
  const checked: any[] = treeRef.value.getCheckedNodes()
  distSelectedIds.value = checked.map((n: any) => n.id)
  for (const id of distSelectedIds.value) {
    if (distManual.value[id] == null) distManual.value[id] = 0
  }
}

async function distributeDryRun() {
  if (!planId.value) return
  try {
    const r = await api.post(
      `/admin/lti-plans/${planId.value}/budget/distribute/`,
      buildPayload(true),
    )
    distPreview.value = r.data.distribution || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || "预览失败")
  }
}

async function distributeCommit() {
  if (!planId.value) return
  if (distMode.value !== "MANUAL") {
    try {
      await ElMessageBox.confirm(
        `确认按"${ruleLabel(distMode.value)}"将公司层 ${fmtInt(distSourceShares.value)} ADS 切到 ${distSelectedIds.value.length} 个目标?`,
        "下发确认",
      )
    } catch {
      return
    }
  }
  try {
    await api.post(
      `/admin/lti-plans/${planId.value}/budget/distribute/`,
      buildPayload(false),
    )
    ElMessage.success("已下发")
    distDialog.value = false
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || e?.response?.data?.detail || "下发失败")
  }
}

function buildPayload(dry: boolean) {
  return {
    employee_category_1: distCat.value,
    mode: distMode.value,
    target_org_unit_ids: distSelectedIds.value,
    manual_amounts: distMode.value === "MANUAL" ? distManual.value : undefined,
    dry_run: dry,
  }
}

onMounted(async () => {
  await loadPlans()
  await load()
})
</script>
