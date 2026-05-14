<template>
  <div class="hr-page">
    <PageHeader
      title="调薪预算池"
      subtitle="按员工类别 × 调薪类型配置公司层调薪预算，并下发到部门 / 中心"
    />

    <Toolbar>
      <span class="hr-text-secondary">Reward Cycle</span>
      <el-select
        v-model="cycleId"
        placeholder="选择周期"
        style="width: 320px"
        @change="load"
      >
        <el-option
          v-for="c in cycles"
          :key="c.id"
          :label="`${c.code} (${c.budget_year})`"
          :value="c.id"
        />
      </el-select>
    </Toolbar>

    <h3 class="hr-section-title">公司层预算</h3>
    <el-table
      v-if="cycleId"
      :data="tableRows"
      border
      v-loading="loading"
    >
      <el-table-column label="员工类别" prop="label" width="140" fixed />
      <el-table-column label="年度调薪 ANNUAL">
        <template #default="{ row }">
          <BudgetCell
            :cell="row.ANNUAL"
            :disabled="loading || saving"
            @update:budget="(v: number) => (row.ANNUAL.budget_amount_cny = v)"
            @distribute="() => openDistribute('ANNUAL', row.ANNUAL.employee_category_1, row.ANNUAL)"
          />
        </template>
      </el-table-column>
      <el-table-column label="晋升调薪 PROMOTION">
        <template #default="{ row }">
          <BudgetCell
            :cell="row.PROMOTION"
            :disabled="loading || saving"
            @update:budget="(v: number) => (row.PROMOTION.budget_amount_cny = v)"
            @distribute="() => openDistribute('PROMOTION', row.PROMOTION.employee_category_1, row.PROMOTION)"
          />
        </template>
      </el-table-column>
    </el-table>

    <div v-if="cycleId" class="hr-row-2" style="margin-top: var(--hr-space-4)">
      <el-button type="primary" @click="save" :loading="saving">保存预算</el-button>
    </div>

    <h3 v-if="cycleId" class="hr-section-title" style="margin-top: var(--hr-space-6)">
      已下发到部门 / 中心
    </h3>
    <el-table
      v-if="cycleId"
      :data="targets"
      stripe
      v-loading="loading"
    >
      <el-table-column label="单元" min-width="200">
        <template #default="{ row }">
          <el-tag
            size="small"
            effect="plain"
            :type="row.target_org_unit_type === 'CENTER' ? 'warning' : 'primary'"
          >
            {{ row.target_org_unit_type }}
          </el-tag>
          <span style="margin-left: var(--hr-space-2)">{{ row.target_org_unit_name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="类型" prop="adjustment_type" width="120">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ row.adjustment_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="员工类别" width="120">
        <template #default="{ row }">
          {{ row.employee_category_1 === "MANAGEMENT" ? "管理干部" : "员工" }}
        </template>
      </el-table-column>
      <el-table-column label="预算（CNY）" width="160" align="right">
        <template #default="{ row }">
          <span class="hr-text-mono">{{ fmt(row.budget_amount_cny) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="已分配" width="160" align="right">
        <template #default="{ row }">
          <span class="hr-text-mono">{{ fmt(row.allocated_amount_cny) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="剩余" width="160" align="right">
        <template #default="{ row }">
          <span class="hr-text-mono">
            {{ fmt(Number(row.budget_amount_cny) - Number(row.allocated_amount_cny || 0)) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="回收（执行后）" width="160" align="right">
        <template #default="{ row }">
          <span class="hr-text-mono hr-text-secondary">
            {{ fmt(row.reclaimed_amount_cny) }}
          </span>
        </template>
      </el-table-column>
      <template #empty>
        <EmptyHint
          title="暂未下发"
          description="尚未将公司层预算切到部门 / 中心，请使用上方下发按钮"
          icon="box"
        />
      </template>
    </el-table>

    <el-dialog
      v-model="distDialog"
      :title="`下发 ${distAdj} / ${distCatLabel}`"
      width="720"
    >
      <el-form label-width="92px">
        <el-form-item label="规则">
          <el-radio-group v-model="distMode" @change="onModeChange">
            <el-radio-button value="MANUAL">手动</el-radio-button>
            <el-radio-button value="HEADCOUNT">按人头</el-radio-button>
            <el-radio-button value="SALARY_TOTAL">按薪资基数</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="目标层级">
          <el-checkbox-group v-model="distTypeFilter" @change="onTypeFilterChange">
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
        <el-form-item v-if="distMode === 'MANUAL' && distSelectedIds.length" label="手填金额">
          <div style="display: flex; flex-direction: column; gap: 6px; width: 100%">
            <div
              v-for="id in distSelectedIds"
              :key="id"
              style="display: flex; align-items: center; gap: 8px"
            >
              <span style="width: 160px">{{ orgLabel(id) }}</span>
              <el-input-number
                v-model="distManual[id]"
                :min="0"
                :step="10000"
                :precision="2"
                size="small"
              />
            </div>
            <div style="font-size: 12px; color: #909399">
              合计 {{ fmt(manualSum) }} / 公司层预算 {{ fmt(distSourceBudget) }}
              <span v-if="manualSum > Number(distSourceBudget)" style="color: #f56c6c">
                超出公司层预算
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
          <el-table-column label="拟分配金额" width="200">
            <template #default="{ row }">{{ fmt(row.amount_cny) }}</template>
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
import { ref, computed, onMounted, h, defineComponent, type PropType } from "vue"
import { ElMessage, ElMessageBox, ElInputNumber, ElProgress, ElButton } from "element-plus"
import api from "@/api/client"
import { PageHeader, Toolbar, EmptyHint } from "@/components"

type Cell = {
  adjustment_type: string
  employee_category_1: string
  budget_amount_cny: number
  allocated_amount_cny: number
  remaining_amount_cny: number
  distribution_rule?: string
}

type Target = {
  id: number
  target_org_unit_id: number
  target_org_unit_name: string
  target_org_unit_type: string
  adjustment_type: string
  employee_category_1: string
  budget_amount_cny: string | number
  allocated_amount_cny: string | number
  reclaimed_amount_cny: string | number
}

type OrgUnitDTO = { id: number; code: string; name: string; type: string; parent_id: number | null }

const cycles = ref<any[]>([])
const cycleId = ref<number | null>(null)
const rows = ref<Cell[]>([])
const targets = ref<Target[]>([])
const loading = ref(false)
const saving = ref(false)

const BudgetCell = defineComponent({
  props: {
    cell: { type: Object as PropType<Cell>, required: true },
    disabled: Boolean,
  },
  emits: ["update:budget", "distribute"],
  setup(props, { emit }) {
    return () => {
      const c = props.cell
      const budget = Number(c.budget_amount_cny || 0)
      const allocated = Number(c.allocated_amount_cny || 0)
      const pct = budget > 0 ? Math.min(100, Math.round((allocated / budget) * 100)) : 0
      return h("div", { style: "display: flex; flex-direction: column; gap: 4px" }, [
        h("div", { style: "display: flex; align-items: center; gap: 8px" }, [
          h("span", { style: "width: 52px; color: #909399" }, "预算"),
          h(ElInputNumber, {
            modelValue: Number(c.budget_amount_cny),
            min: 0,
            step: 10000,
            precision: 2,
            size: "small",
            disabled: props.disabled,
            "onUpdate:modelValue": (v: number | undefined) => emit("update:budget", v ?? 0),
          }),
          h(
            ElButton,
            {
              size: "small",
              type: "primary",
              link: true,
              onClick: () => emit("distribute"),
            },
            () => "下发 ▾",
          ),
        ]),
        h("div", { style: "font-size: 12px; color: #606266" }, [
          `已分配 ${fmt(c.allocated_amount_cny)} / 剩余 ${fmt(c.remaining_amount_cny)}`,
          c.distribution_rule
            ? h("span", { style: "margin-left: 8px; color: #67c23a" }, `规则: ${ruleLabel(c.distribution_rule)}`)
            : null,
        ]),
        h(ElProgress, { percentage: pct, strokeWidth: 6 }),
      ])
    }
  },
})

function fmt(v: any) {
  return Number(v || 0).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function ruleLabel(r?: string) {
  return r === "HEADCOUNT" ? "按人头" : r === "SALARY_TOTAL" ? "按薪资基数" : "手动"
}

type Row = { label: string; ANNUAL: Cell; PROMOTION: Cell }
const tableRows = ref<Row[]>([])

function rebuildRows() {
  const map: Record<string, Record<string, Cell>> = { MANAGEMENT: {}, STAFF: {} }
  for (const r of rows.value) {
    map[r.employee_category_1] = map[r.employee_category_1] || {}
    map[r.employee_category_1][r.adjustment_type] = r
  }
  const mk = (cat: string, type: string): Cell =>
    map[cat]?.[type] || {
      adjustment_type: type,
      employee_category_1: cat,
      budget_amount_cny: 0,
      allocated_amount_cny: 0,
      remaining_amount_cny: 0,
    }
  tableRows.value = [
    { label: "管理干部", ANNUAL: mk("MANAGEMENT", "ANNUAL"), PROMOTION: mk("MANAGEMENT", "PROMOTION") },
    { label: "员工", ANNUAL: mk("STAFF", "ANNUAL"), PROMOTION: mk("STAFF", "PROMOTION") },
  ]
}

async function loadCycles() {
  const r = await api.get("/reward-cycle/")
  cycles.value = Array.isArray(r.data) ? r.data : r.data.results || []
  if (cycles.value.length && cycleId.value == null) cycleId.value = cycles.value[0].id
}

async function load() {
  if (!cycleId.value) return
  loading.value = true
  try {
    const r = await api.get(`/admin/reward-cycles/${cycleId.value}/adjustment-budget/`)
    rows.value = r.data.company || r.data.rows || []
    targets.value = r.data.targets || []
    rebuildRows()
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!cycleId.value) return
  saving.value = true
  try {
    const payload = {
      rows: tableRows.value.flatMap((r) => [
        { adjustment_type: "ANNUAL", employee_category_1: r.ANNUAL.employee_category_1, budget_amount_cny: r.ANNUAL.budget_amount_cny },
        { adjustment_type: "PROMOTION", employee_category_1: r.PROMOTION.employee_category_1, budget_amount_cny: r.PROMOTION.budget_amount_cny },
      ]),
    }
    await api.put(`/admin/reward-cycles/${cycleId.value}/adjustment-budget/`, payload)
    ElMessage.success("预算已保存")
    await load()
  } finally {
    saving.value = false
  }
}

// 下发对话框 ----
const distDialog = ref(false)
const distAdj = ref<"ANNUAL" | "PROMOTION">("ANNUAL")
const distCat = ref<"MANAGEMENT" | "STAFF">("STAFF")
const distMode = ref<"MANUAL" | "HEADCOUNT" | "SALARY_TOTAL">("HEADCOUNT")
const distSourceBudget = ref<number>(0)
const distTypeFilter = ref<string[]>(["DEPT", "CENTER"])
const distSelectedIds = ref<number[]>([])
const distManual = ref<Record<number, number>>({})
const distPreview = ref<{ target_org_unit_id: number; amount_cny: string }[]>([])
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
    byParent[k].push({ id: o.id, name: `${o.name} (${o.type})`, code: o.code, type: o.type, parent_id: o.parent_id, children: [] as any[] })
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
  if (distMode.value === "MANUAL" && manualSum.value > Number(distSourceBudget.value)) return false
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

async function openDistribute(adj: "ANNUAL" | "PROMOTION", cat: "MANAGEMENT" | "STAFF", cell: Cell) {
  await ensureOrgUnits()
  distAdj.value = adj
  distCat.value = cat
  distSourceBudget.value = Number(cell.budget_amount_cny || 0)
  distMode.value = "HEADCOUNT"
  distTypeFilter.value = ["DEPT", "CENTER"]
  distSelectedIds.value = []
  distManual.value = {}
  distPreview.value = []
  distDialog.value = true
}

function onModeChange() {
  distPreview.value = []
}

function onTypeFilterChange() {
  // Tree rebuilds from computed; clear selections that filtered out
  setTimeout(() => {
    if (treeRef.value) treeRef.value.setCheckedKeys(distSelectedIds.value)
  }, 0)
}

function onTreeCheck() {
  if (!treeRef.value) return
  distSelectedIds.value = treeRef.value
    .getCheckedNodes()
    .filter((n: any) => !n.children || n.children.length === 0 || treeRef.value.getCheckedKeys().includes(n.id))
    .map((n: any) => n.id)
  for (const id of distSelectedIds.value) {
    if (distManual.value[id] == null) distManual.value[id] = 0
  }
}

async function distributeDryRun() {
  if (!cycleId.value) return
  try {
    const r = await api.post(
      `/admin/reward-cycles/${cycleId.value}/adjustment-budget/distribute/`,
      buildPayload(true),
    )
    distPreview.value = r.data.distribution || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || "预览失败")
  }
}

async function distributeCommit() {
  if (!cycleId.value) return
  if (distMode.value !== "MANUAL") {
    try {
      await ElMessageBox.confirm(
        `确认按"${ruleLabel(distMode.value)}"将公司层 ${fmt(distSourceBudget.value)} CNY 切到 ${distSelectedIds.value.length} 个目标?`,
        "下发确认",
      )
    } catch {
      return
    }
  }
  try {
    await api.post(
      `/admin/reward-cycles/${cycleId.value}/adjustment-budget/distribute/`,
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
    adjustment_type: distAdj.value,
    employee_category_1: distCat.value,
    mode: distMode.value,
    target_org_unit_ids: distSelectedIds.value,
    manual_amounts: distMode.value === "MANUAL" ? distManual.value : undefined,
    dry_run: dry,
  }
}

onMounted(async () => {
  await loadCycles()
  await load()
})
</script>
