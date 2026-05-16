<template>
  <div class="hr-page">
    <PageHeader
      title="派生预算总览"
      subtitle="部门池为预算下发单位；展开行可见部门内 (国家 × 员工类别 × 调薪类型) 切片"
    >
      <template #actions>
        <el-button :icon="Download" @click="downloadTemplate" :disabled="!cycleId">
          下载模板
        </el-button>
        <el-button
          type="primary"
          :icon="Upload"
          @click="importDrawerOpen = true"
          :disabled="!cycleId"
        >
          批量导入
        </el-button>
        <el-button :icon="Refresh" @click="load" :loading="loading">刷新</el-button>
      </template>
    </PageHeader>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      style="margin: 0 0 var(--hr-space-4)"
    >
      <template #title>
        派生公式: <span class="hr-text-mono">月薪 × 区域基准比例 × 类别系数</span>
        （<b>月度增量额</b>，不年化）。部门池 = 该部门下所有切片之和。
        <span style="margin-left: 8px">
          90/10 分池: 矩阵建议占
          <b>{{ ((1 - Number(discretionaryPct)) * 100).toFixed(0) }}%</b>，部门 head 机动盘占
          <b>{{ (Number(discretionaryPct) * 100).toFixed(0) }}%</b>。
        </span>
      </template>
    </el-alert>

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
          :label="`${c.code}${c.period ? ` (${c.period})` : ''}`"
          :value="c.id"
        />
      </el-select>
    </Toolbar>

    <div v-if="cycleId" class="hr-row-4" style="margin-bottom: var(--hr-space-4)">
      <StatCard label="参与员工数" :value="employeeTotal" tone="default" :hint="skippedTotal > 0 ? skippedHint : '全员已计入'" />
      <StatCard
        label="月度池总额 (CNY)"
        :value="fmt(Number(annualTotal) + Number(promotionTotal))"
        tone="brand"
        :hint="`年度 ${fmt(annualTotal)} / 晋升 ${fmt(promotionTotal)}`"
      />
      <StatCard
        label="矩阵建议池 (CNY)"
        :value="fmt(totalMatrix)"
        tone="success"
        :hint="`占 ${((1 - Number(discretionaryPct)) * 100).toFixed(0)}%`"
      />
      <StatCard
        label="部门 head 机动盘 (CNY)"
        :value="fmt(totalDiscretionary)"
        tone="warning"
        :hint="`占 ${(Number(discretionaryPct) * 100).toFixed(0)}%`"
      />
    </div>

    <div class="hr-section hr-section--flush">
      <el-table
        v-if="cycleId"
        :data="departments"
        stripe
        v-loading="loading"
        row-key="department_id_or_unassigned"
        :default-sort="{ prop: 'department_name', order: 'ascending' }"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="dept-slice-wrap">
              <el-table
                :data="slicesByDept(row.department_id)"
                size="small"
                :show-header="true"
                stripe
              >
                <el-table-column prop="country" label="国家" width="100">
                  <template #default="{ row: s }">
                    <span class="hr-text-mono">{{ s.country }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="员工类别" min-width="160">
                  <template #default="{ row: s }">
                    <span>{{ s.category_name }}</span>
                    <span class="hr-text-secondary" style="margin-left: 6px">
                      <span class="hr-text-mono">{{ s.category_code }}</span>
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="调薪类型" width="120">
                  <template #default="{ row: s }">
                    <el-tag
                      size="small"
                      effect="plain"
                      :type="s.adjustment_type === 'ANNUAL' ? 'primary' : 'warning'"
                    >
                      {{ s.adjustment_type === "ANNUAL" ? "年度调薪" : "晋升调薪" }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="员工数" prop="employee_count" width="80" align="right" />
                <el-table-column label="月薪小计 (CNY)" min-width="140" align="right">
                  <template #default="{ row: s }">
                    <span class="hr-text-mono">{{ fmt(s.salary_sum_cny) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="基准比例" width="100" align="right">
                  <template #default="{ row: s }">
                    <span v-if="s.base_pct != null" class="hr-text-mono">
                      {{ pct(s.base_pct) }}
                    </span>
                    <span v-else class="hr-text-secondary">—</span>
                  </template>
                </el-table-column>
                <el-table-column label="类别系数" width="100" align="right">
                  <template #default="{ row: s }">
                    <span v-if="s.factor != null" class="hr-text-mono">
                      {{ Number(s.factor).toFixed(4) }}
                    </span>
                    <span v-else class="hr-text-secondary">—</span>
                  </template>
                </el-table-column>
                <el-table-column label="月度派生额 (CNY)" min-width="180" align="right">
                  <template #default="{ row: s }">
                    <span class="hr-text-mono">{{ fmt(s.derived_amount_cny) }}</span>
                    <div
                      v-if="s.base_pct != null && s.factor != null && Number(s.salary_sum_cny) > 0"
                      class="hr-text-secondary"
                      style="font-size: 12px; line-height: 1.4"
                    >
                      {{ fmt(s.salary_sum_cny) }} × {{ pct(s.base_pct) }} × {{ Number(s.factor).toFixed(4) }}
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="备注" min-width="220">
                  <template #default="{ row: s }">
                    <el-tag
                      v-if="s.missing_rule"
                      size="small"
                      type="danger"
                      effect="plain"
                      style="margin-right: 6px"
                    >
                      缺 RegionalAdjustmentRule
                    </el-tag>
                    <el-tag
                      v-if="s.missing_factor"
                      size="small"
                      type="danger"
                      effect="plain"
                    >
                      缺 EmployeeCategoryFactor
                    </el-tag>
                    <span
                      v-if="!s.missing_rule && !s.missing_factor"
                      class="hr-text-secondary"
                    >—</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="部门" prop="department_name" min-width="200" sortable>
          <template #default="{ row }">
            <span :class="row.department_id == null ? 'hr-text-secondary' : ''">
              {{ row.department_name }}
            </span>
            <el-tag
              v-if="row.department_id == null"
              size="small"
              type="info"
              effect="plain"
              style="margin-left: 8px"
            >
              未分配
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="员工数" prop="employee_count" width="100" align="right" />
        <el-table-column label="ANNUAL 月度池 (CNY)" min-width="240" align="right">
          <template #default="{ row }">
            <div class="pool-cell">
              <span class="hr-text-mono">{{ fmt(row.effective_annual_cny) }}</span>
              <el-tag
                size="small"
                :type="row.annual_source === 'IMPORTED' ? 'warning' : 'info'"
                effect="plain"
                class="src-tag"
              >
                {{ row.annual_source === "IMPORTED" ? "已覆盖" : "派生" }}
              </el-tag>
            </div>
            <div class="hr-text-secondary pool-split">
              矩阵 {{ fmt(row.matrix_annual_cny) }} / 机动 {{ fmt(row.discretionary_annual_cny) }}
            </div>
            <div
              v-if="row.annual_source === 'IMPORTED'"
              class="hr-text-secondary pool-derived"
            >
              派生原值: {{ fmt(row.derived_annual_cny) }}
              <el-link
                v-if="row.department_id != null"
                type="danger"
                :underline="false"
                style="margin-left: 4px; font-size: 12px"
                @click="clearOverride(row.department_id, 'ANNUAL')"
              >清空</el-link>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="PROMOTION 月度池 (CNY)" min-width="240" align="right">
          <template #default="{ row }">
            <div class="pool-cell">
              <span class="hr-text-mono">{{ fmt(row.effective_promotion_cny) }}</span>
              <el-tag
                size="small"
                :type="row.promotion_source === 'IMPORTED' ? 'warning' : 'info'"
                effect="plain"
                class="src-tag"
              >
                {{ row.promotion_source === "IMPORTED" ? "已覆盖" : "派生" }}
              </el-tag>
            </div>
            <div class="hr-text-secondary pool-split">
              矩阵 {{ fmt(row.matrix_promotion_cny) }} / 机动 {{ fmt(row.discretionary_promotion_cny) }}
            </div>
            <div
              v-if="row.promotion_source === 'IMPORTED'"
              class="hr-text-secondary pool-derived"
            >
              派生原值: {{ fmt(row.derived_promotion_cny) }}
              <el-link
                v-if="row.department_id != null"
                type="danger"
                :underline="false"
                style="margin-left: 4px; font-size: 12px"
                @click="clearOverride(row.department_id, 'PROMOTION')"
              >清空</el-link>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="部门池合计 (CNY)" min-width="200" align="right">
          <template #default="{ row }">
            <b class="hr-text-mono">{{ fmt(row.effective_total_cny) }}</b>
            <div class="hr-text-secondary pool-split">
              矩阵 {{ fmt(row.matrix_pool_cny) }} / 机动 {{ fmt(row.discretionary_pool_cny) }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="160">
          <template #default="{ row }">
            <el-tag
              v-if="row.has_missing_rule || row.has_missing_factor"
              size="small"
              type="danger"
              effect="plain"
            >
              规则不全
            </el-tag>
            <el-tag v-else size="small" type="success" effect="plain">规则齐备</el-tag>
          </template>
        </el-table-column>
        <template #empty>
          <EmptyHint
            v-if="!cycleSchemeBound"
            title="该周期尚未绑定类别方案"
            description="请先在「Reward Cycle」里给该周期绑定 CategoryScheme，再回此页查看派生"
            icon="document"
          />
          <EmptyHint
            v-else
            title="暂无可派生数据"
            description="尚无员工被分类到本方案下的桶，或该方案下无任何 ACTIVE 员工"
            icon="document"
          />
        </template>
      </el-table>
    </div>

    <el-drawer
      v-model="importDrawerOpen"
      title="批量导入部门池覆盖值"
      direction="rtl"
      size="520px"
      :before-close="closeImportDrawer"
    >
      <div class="import-body">
        <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
          <template #title>
            上传 .xlsx，列：<span class="hr-text-mono">department_code, department_name, adjustment_type(ANNUAL/PROMOTION), override_amount_cny</span>。
            未分配部门不可导入；任一行校验失败 → 整批拒绝。
          </template>
        </el-alert>

        <el-upload
          drag
          :auto-upload="false"
          :limit="1"
          accept=".xlsx"
          :on-change="onFileChange"
          :on-remove="onFileRemove"
          :file-list="fileList"
        >
          <el-icon class="el-icon--upload"><Upload /></el-icon>
          <div class="el-upload__text">
            拖拽到此或<em>点击选择 .xlsx</em>
          </div>
        </el-upload>

        <div v-if="importErrors.length" class="import-errors">
          <div class="import-errors-title">校验失败 ({{ importErrors.length }} 行)</div>
          <el-table :data="importErrors" size="small" stripe max-height="280">
            <el-table-column prop="row" label="行号" width="70" align="center" />
            <el-table-column prop="field" label="字段" width="140" />
            <el-table-column prop="msg" label="错误信息" />
          </el-table>
        </div>

        <div v-if="importResult" class="import-success">
          <el-result icon="success" title="导入成功">
            <template #sub-title>
              新增 {{ importResult.created }} 条 / 更新 {{ importResult.updated }} 条
            </template>
          </el-result>
        </div>
      </div>
      <template #footer>
        <el-button @click="closeImportDrawer">取消</el-button>
        <el-button
          type="primary"
          :loading="importing"
          :disabled="!stagedFile"
          @click="submitImport"
        >提交导入</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import { Refresh, Upload, Download } from "@element-plus/icons-vue"
import { ElMessage, ElMessageBox } from "element-plus"
import type { UploadFile } from "element-plus"
import api from "@/api/client"
import { PageHeader, Toolbar, StatCard, EmptyHint } from "@/components"

type Slice = {
  department_id: number | null
  department_name: string
  country: string
  category_id: number
  category_code: string
  category_name: string
  adjustment_type: "ANNUAL" | "PROMOTION"
  employee_count: number
  salary_sum_cny: string
  base_pct: string | null
  factor: string | null
  derived_amount_cny: string
  missing_rule: boolean
  missing_factor: boolean
}

type Department = {
  department_id: number | null
  department_name: string
  employee_count: number
  derived_annual_cny: string
  derived_promotion_cny: string
  derived_total_cny: string
  override_annual_cny: string | null
  override_promotion_cny: string | null
  effective_annual_cny: string
  effective_promotion_cny: string
  effective_total_cny: string
  matrix_annual_cny: string
  matrix_promotion_cny: string
  matrix_pool_cny: string
  discretionary_annual_cny: string
  discretionary_promotion_cny: string
  discretionary_pool_cny: string
  annual_source: "DERIVED" | "IMPORTED"
  promotion_source: "DERIVED" | "IMPORTED"
  has_missing_rule: boolean
  has_missing_factor: boolean
  department_id_or_unassigned?: string
}

const cycles = ref<any[]>([])
const cycleId = ref<number | null>(null)
const departments = ref<Department[]>([])
const slices = ref<Slice[]>([])
const employeeTotal = ref(0)
const skippedNoSalary = ref(0)
const skippedNoCountry = ref(0)
const cycleSchemeBound = ref(true)
const loading = ref(false)
const totalMatrix = ref("0")
const totalDiscretionary = ref("0")
const discretionaryPct = ref("0.1000")

const annualTotal = computed(() =>
  departments.value.reduce((s, d) => s + Number(d.effective_annual_cny || 0), 0),
)
const promotionTotal = computed(() =>
  departments.value.reduce((s, d) => s + Number(d.effective_promotion_cny || 0), 0),
)
const skippedTotal = computed(() => skippedNoSalary.value + skippedNoCountry.value)
const skippedHint = computed(() => {
  const parts: string[] = []
  if (skippedNoSalary.value) parts.push(`${skippedNoSalary.value} 名缺薪酬记录`)
  if (skippedNoCountry.value) parts.push(`${skippedNoCountry.value} 名缺国家信息`)
  return parts.join(" / ") || "全员已计入"
})

function slicesByDept(deptId: number | null): Slice[] {
  return slices.value.filter((s) => s.department_id === deptId)
}

function fmt(v: any) {
  return Number(v || 0).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function pct(v: any) {
  return `${(Number(v || 0) * 100).toFixed(2)}%`
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
    const r = await api.get(
      `/admin/reward-cycles/${cycleId.value}/derived-budget/`,
    )
    const depts: Department[] = r.data.departments || []
    depts.forEach((d) => {
      d.department_id_or_unassigned =
        d.department_id == null ? "unassigned" : `d-${d.department_id}`
    })
    departments.value = depts
    slices.value = r.data.rows || []
    employeeTotal.value = r.data.employee_total || 0
    skippedNoSalary.value = r.data.skipped_no_salary_count || 0
    skippedNoCountry.value = r.data.skipped_no_country_count || 0
    totalMatrix.value = r.data.total_matrix_cny || "0"
    totalDiscretionary.value = r.data.total_discretionary_cny || "0"
    discretionaryPct.value = r.data.discretionary_pct || "0.1000"
    const cyc = cycles.value.find((c) => c.id === cycleId.value)
    cycleSchemeBound.value = !!cyc?.category_scheme
  } finally {
    loading.value = false
  }
}

// ============ 批量导入 ============
const importDrawerOpen = ref(false)
const stagedFile = ref<File | null>(null)
const fileList = ref<any[]>([])
const importing = ref(false)
const importErrors = ref<{ row: number; field: string; msg: string }[]>([])
const importResult = ref<{ created: number; updated: number; total_rows: number } | null>(null)

function onFileChange(file: UploadFile) {
  stagedFile.value = (file.raw as File) || null
  importErrors.value = []
  importResult.value = null
}

function onFileRemove() {
  stagedFile.value = null
  importErrors.value = []
  importResult.value = null
}

function closeImportDrawer() {
  importDrawerOpen.value = false
  stagedFile.value = null
  fileList.value = []
  importErrors.value = []
  importResult.value = null
}

async function submitImport() {
  if (!stagedFile.value || !cycleId.value) return
  importing.value = true
  importErrors.value = []
  importResult.value = null
  const fd = new FormData()
  fd.append("file", stagedFile.value)
  try {
    const r = await api.post(
      `/admin/reward-cycles/${cycleId.value}/budget-overrides/import/`,
      fd,
      { headers: { "Content-Type": "multipart/form-data" } },
    )
    importResult.value = r.data
    ElMessage.success(`导入成功：新增 ${r.data.created}，更新 ${r.data.updated}`)
    await load()
  } catch (e: any) {
    if (e?.response?.status === 400 && Array.isArray(e.response.data?.errors)) {
      importErrors.value = e.response.data.errors
      ElMessage.error("校验失败，请查看错误清单")
    } else {
      ElMessage.error(e?.response?.data?.detail || "导入失败")
    }
  } finally {
    importing.value = false
  }
}

async function downloadTemplate() {
  if (!cycleId.value) return
  const r = await api.get(
    `/admin/reward-cycles/${cycleId.value}/budget-overrides/template/`,
    { responseType: "blob" },
  )
  const url = URL.createObjectURL(r.data)
  const a = document.createElement("a")
  a.href = url
  a.download = `budget-override-template-cycle-${cycleId.value}.xlsx`
  a.click()
  URL.revokeObjectURL(url)
}

async function clearOverride(deptId: number, adj: "ANNUAL" | "PROMOTION") {
  await ElMessageBox.confirm(
    `确认清空该部门 ${adj === "ANNUAL" ? "年度调薪" : "晋升调薪"} 的覆盖值，回到派生原值？`,
    "确认操作",
    { type: "warning" },
  )
  await api.delete(
    `/admin/reward-cycles/${cycleId.value}/budget-overrides/clear/`,
    { params: { department_id: deptId, adjustment_type: adj } },
  )
  ElMessage.success("已清空")
  await load()
}

onMounted(async () => {
  await loadCycles()
  await load()
})
</script>

<style scoped>
.dept-slice-wrap {
  padding: 12px 24px 16px 48px;
  background: var(--hr-bg-subtle, #fafbfc);
}
.pool-cell {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}
.src-tag {
  font-size: 11px;
}
.pool-derived {
  font-size: 12px;
  margin-top: 2px;
}
.pool-split {
  font-size: 12px;
  margin-top: 2px;
  line-height: 1.4;
}
.import-body {
  padding: 0 4px;
}
.import-errors {
  margin-top: 16px;
}
.import-errors-title {
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--el-color-danger);
}
.import-success {
  margin-top: 16px;
}
</style>
