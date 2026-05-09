<template>
  <el-container direction="vertical" style="padding: 16px">
    <h3 style="margin: 0 0 16px">调薪预算池</h3>
    <el-form inline>
      <el-form-item label="Reward Cycle">
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
      </el-form-item>
    </el-form>

    <el-table
      v-if="cycleId"
      :data="tableRows"
      border
      v-loading="loading"
      style="margin-top: 12px"
    >
      <el-table-column label="员工类别" prop="label" width="140" fixed />
      <el-table-column label="年度调薪 ANNUAL">
        <template #default="{ row }">
          <BudgetCell
            :cell="row.ANNUAL"
            :disabled="loading || saving"
            @update:budget="(v: number) => (row.ANNUAL.budget_amount_cny = v)"
          />
        </template>
      </el-table-column>
      <el-table-column label="晋升调薪 PROMOTION">
        <template #default="{ row }">
          <BudgetCell
            :cell="row.PROMOTION"
            :disabled="loading || saving"
            @update:budget="(v: number) => (row.PROMOTION.budget_amount_cny = v)"
          />
        </template>
      </el-table-column>
    </el-table>

    <div v-if="cycleId" style="margin-top: 16px">
      <el-button type="primary" @click="save" :loading="saving">保存预算</el-button>
    </div>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, h, defineComponent, type PropType } from "vue"
import { ElMessage, ElInputNumber, ElProgress } from "element-plus"
import api from "@/api/client"

type Cell = {
  adjustment_type: string
  employee_category_1: string
  budget_amount_cny: number
  allocated_amount_cny: number
  remaining_amount_cny: number
}

const cycles = ref<any[]>([])
const cycleId = ref<number | null>(null)
const rows = ref<Cell[]>([])
const loading = ref(false)
const saving = ref(false)

const BudgetCell = defineComponent({
  props: {
    cell: { type: Object as PropType<Cell>, required: true },
    disabled: Boolean,
  },
  emits: ["update:budget"],
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
        ]),
        h("div", { style: "font-size: 12px; color: #606266" }, [
          `已分配 ${fmt(c.allocated_amount_cny)} / 剩余 ${fmt(c.remaining_amount_cny)}`,
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

type Row = {
  label: string
  ANNUAL: Cell
  PROMOTION: Cell
}
const tableRows = ref<Row[]>([])

function rebuildRows() {
  const map: Record<string, Record<string, Cell>> = {
    MANAGEMENT: {},
    STAFF: {},
  }
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
  if (cycles.value.length && cycleId.value == null) {
    cycleId.value = cycles.value[0].id
  }
}

async function load() {
  if (!cycleId.value) return
  loading.value = true
  try {
    const r = await api.get(`/admin/reward-cycles/${cycleId.value}/adjustment-budget/`)
    rows.value = r.data.rows || []
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
        {
          adjustment_type: "ANNUAL",
          employee_category_1: r.ANNUAL.employee_category_1,
          budget_amount_cny: r.ANNUAL.budget_amount_cny,
        },
        {
          adjustment_type: "PROMOTION",
          employee_category_1: r.PROMOTION.employee_category_1,
          budget_amount_cny: r.PROMOTION.budget_amount_cny,
        },
      ]),
    }
    await api.put(`/admin/reward-cycles/${cycleId.value}/adjustment-budget/`, payload)
    ElMessage.success("预算已保存")
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadCycles()
  await load()
})
</script>
