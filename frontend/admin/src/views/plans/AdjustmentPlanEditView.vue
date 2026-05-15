<template>
  <div class="hr-page">
    <PageHeader
      :title="isNew ? '新建调薪方案' : '编辑调薪方案'"
      subtitle="规则先建好 → 矩阵在规则之上配置调节系数 → 公式只读串联三层"
    />

    <el-tabs v-model="activeTab" class="adj-plan-tabs" v-loading="loading">
      <!-- Tab 1: 基础信息 -->
      <el-tab-pane name="base">
        <template #label><span><el-icon><Document /></el-icon> 基础信息</span></template>
        <div class="hr-section" style="max-width: 860px">
          <el-form
            ref="formRef"
            :model="form"
            label-width="140px"
            :rules="formRules"
          >
            <el-form-item label="编码" prop="code">
              <el-input v-model="form.code" placeholder="如 ADJ-2026-01" />
            </el-form-item>
            <el-form-item label="名称" prop="name">
              <el-input v-model="form.name" />
            </el-form-item>
            <el-form-item label="周期 (年)" prop="period">
              <el-date-picker
                v-model="periodDate"
                type="year"
                value-format="YYYY"
                placeholder="选择年份"
                @update:model-value="onPeriodChange"
              />
            </el-form-item>
            <el-form-item label="状态" prop="status">
              <el-select v-model="form.status">
                <el-option label="草稿 DRAFT" value="DRAFT" />
                <el-option label="启用 ACTIVE" value="ACTIVE" />
                <el-option label="关闭 CLOSED" value="CLOSED" />
              </el-select>
            </el-form-item>
            <el-form-item label="关联 Reward Cycle" prop="reward_cycle">
              <el-select
                v-model="form.reward_cycle"
                clearable
                placeholder="必选 (规则与矩阵均挂在 cycle 上)"
                style="width: 320px"
              >
                <el-option
                  v-for="c in cycles"
                  :key="c.id"
                  :label="`${c.code} (${c.budget_year || '-'})`"
                  :value="c.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="舍入规则" prop="rounding_rule">
              <el-select v-model="form.rounding_rule">
                <el-option label="四舍五入 ROUND_HALF_UP" value="ROUND_HALF_UP" />
                <el-option label="银行家舍入 ROUND_HALF_EVEN" value="ROUND_HALF_EVEN" />
                <el-option label="向下取整 ROUND_FLOOR" value="ROUND_FLOOR" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="submitBase" :loading="saving">保存基础信息</el-button>
              <el-button @click="$router.push('/admin/plans/adjustment')">返回列表</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>

      <!-- Tab 2: 规则配置 -->
      <el-tab-pane name="rules" :disabled="isNew || !form.reward_cycle">
        <template #label><span><el-icon><Setting /></el-icon> 规则配置</span></template>
        <el-alert
          v-if="!form.reward_cycle"
          type="warning"
          :closable="false"
          show-icon
          title="请先在「基础信息」绑定 Reward Cycle 并保存，规则才能配置。"
          style="margin-bottom: 16px"
        />
        <template v-else>
          <p class="hr-text-secondary">
            员工最终调薪比例 = base_pct(国家, 类型) × factor(员工类别, 类型)。
            预算池由系统按规则自下而上派生，HR 不需要手填公司池/部门池金额。
          </p>

          <h3 class="hr-section-title">区域基准比例 (按 LegalEntity.country)</h3>
          <el-table :data="rules" border v-loading="loadingRules">
            <el-table-column label="国家" prop="country" width="160" />
            <el-table-column label="调薪类型" width="180">
              <template #default="{ row }">
                <el-select v-model="row.adjustment_type" size="small" @change="markRuleDirty(row)">
                  <el-option label="年度 ANNUAL" value="ANNUAL" />
                  <el-option label="晋升 PROMOTION" value="PROMOTION" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="基准比例" width="220">
              <template #default="{ row }">
                <el-input-number
                  v-model="row.base_pct"
                  :min="0"
                  :max="1"
                  :step="0.005"
                  :precision="4"
                  size="small"
                  @change="markRuleDirty(row)"
                />
                <span style="margin-left: 8px; color: #909399; font-size: 12px">
                  = {{ pctLabel(row.base_pct) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="备注" min-width="240">
              <template #default="{ row }">
                <el-input v-model="row.notes" size="small" @change="markRuleDirty(row)" />
              </template>
            </el-table-column>
            <el-table-column label="国家代码" width="120">
              <template #default="{ row }">
                <el-input v-model="row.country" size="small" placeholder="CN/US/SG" @change="markRuleDirty(row)" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row, $index }">
                <el-button v-if="row.id" size="small" link type="danger" @click="deleteRule(row)">删除</el-button>
                <el-button v-else size="small" link @click="rules.splice($index, 1)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div style="margin-top: 12px; display: flex; gap: 12px">
            <el-button @click="addRule">+ 添加</el-button>
            <el-button
              type="primary"
              :disabled="!ruleDirtyIds.size && !rules.some((r) => !r.id)"
              :loading="savingRules"
              @click="saveRules"
            >
              保存 ({{ unsavedRuleCount }})
            </el-button>
          </div>

          <h3 class="hr-section-title" style="margin-top: 24px">员工类别系数</h3>
          <el-table :data="factors" border v-loading="loadingRules">
            <el-table-column label="员工类别" min-width="200">
              <template #default="{ row }">
                <el-select v-model="row.category" style="width: 100%" size="small" @change="markFactorDirty(row)">
                  <el-option
                    v-for="c in cats"
                    :key="c.id"
                    :label="`${c.code} - ${c.name}`"
                    :value="c.id"
                  />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="调薪类型" width="180">
              <template #default="{ row }">
                <el-select v-model="row.adjustment_type" size="small" @change="markFactorDirty(row)">
                  <el-option label="年度 ANNUAL" value="ANNUAL" />
                  <el-option label="晋升 PROMOTION" value="PROMOTION" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="系数" width="220">
              <template #default="{ row }">
                <el-input-number
                  v-model="row.factor"
                  :min="0"
                  :max="5"
                  :step="0.05"
                  :precision="4"
                  size="small"
                  @change="markFactorDirty(row)"
                />
                <span style="margin-left: 8px; color: #909399; font-size: 12px">
                  ×{{ Number(row.factor || 0).toFixed(2) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="备注" min-width="240">
              <template #default="{ row }">
                <el-input v-model="row.notes" size="small" @change="markFactorDirty(row)" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row, $index }">
                <el-button v-if="row.id" size="small" link type="danger" @click="deleteFactor(row)">删除</el-button>
                <el-button v-else size="small" link @click="factors.splice($index, 1)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div style="margin-top: 12px; display: flex; gap: 12px">
            <el-button @click="addFactor">+ 添加</el-button>
            <el-button
              type="primary"
              :disabled="!factorDirtyIds.size && !factors.some((f) => !f.id)"
              :loading="savingFactors"
              @click="saveFactors"
            >
              保存 ({{ unsavedFactorCount }})
            </el-button>
          </div>
        </template>
      </el-tab-pane>

      <!-- Tab 3: 公式与矩阵 -->
      <el-tab-pane name="matrix" :disabled="isNew || !form.reward_cycle">
        <template #label><span><el-icon><DataLine /></el-icon> 公式与矩阵</span></template>
        <el-alert
          v-if="!form.reward_cycle"
          type="warning"
          :closable="false"
          show-icon
          title="请先在「基础信息」绑定 Reward Cycle 并保存。"
        />
        <template v-else>
          <!-- 公式只读卡 -->
          <el-card shadow="never" class="formula-card">
            <template #header><span class="hr-section-title" style="margin: 0">计算公式（系统派生）</span></template>
            <pre class="formula-text">基础调薪比例 = base_pct(国家, ANNUAL) × factor(类别, ANNUAL)
调节系数区间 = matrix(类别)[薪酬分位, 绩效] = [c_low, c_high]
个人建议区间 = 基础调薪比例 × [c_low, c_high]
晋升调薪    = base_pct(国家, PROMOTION) × factor(类别, PROMOTION)
最终比例    = 个人建议区间内取值（越界需说明理由）+ 晋升调薪
新月薪      = 当前月薪 × (1 + 最终比例)，按舍入规则取整</pre>
          </el-card>

          <!-- 绩效档位编辑器 -->
          <h3 class="hr-section-title" style="margin-top: 24px">绩效档位（H2 下半年绩效）</h3>
          <p class="hr-text-secondary" style="margin-top: 0">
            档位列表用于矩阵的"行"。可灵活增删改；改完点击"保存绩效档位"生效，矩阵表会同步刷新。
          </p>
          <el-table :data="form.perf_grades" border size="small" style="max-width: 720px">
            <el-table-column label="排序" width="100">
              <template #default="{ row, $index }">
                <el-input-number v-model="row.sort_order" :min="0" :step="1" :precision="0" size="small" style="width: 90px" @change="markPerfDirty()" />
                <span style="margin-left: 4px; display: inline-flex; gap: 2px">
                  <el-button size="small" link :disabled="$index === 0" @click="movePerf($index, -1)">↑</el-button>
                  <el-button size="small" link :disabled="$index === form.perf_grades.length - 1" @click="movePerf($index, 1)">↓</el-button>
                </span>
              </template>
            </el-table-column>
            <el-table-column label="代码 (code)" width="180">
              <template #default="{ row }">
                <el-input v-model="row.code" size="small" placeholder="STAR_5" @change="markPerfDirty()" />
              </template>
            </el-table-column>
            <el-table-column label="显示名 (label)" min-width="200">
              <template #default="{ row }">
                <el-input v-model="row.label" size="small" placeholder="5星" @change="markPerfDirty()" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ $index }">
                <el-button size="small" link type="danger" @click="removePerf($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div style="margin-top: 12px; display: flex; gap: 12px">
            <el-button @click="addPerf">+ 添加档位</el-button>
            <el-button @click="restoreDefaultPerf">恢复默认 5 档</el-button>
            <el-button type="primary" :disabled="!perfDirty" :loading="savingPerf" @click="savePerfGrades">
              保存绩效档位
            </el-button>
          </div>

          <!-- 调薪矩阵 -->
          <h3 class="hr-section-title" style="margin-top: 24px">调薪矩阵（按员工类别分别配置）</h3>
          <p class="hr-text-secondary" style="margin-top: 0">
            每格填两个数 <code>[c_low, c_high]</code>。个人建议年度调薪区间 = 基础调薪比例 × 该格区间。
            "基础"取该类别的 ANNUAL 系数 × 当前国家的 ANNUAL 基准比例。
          </p>
          <el-segmented v-model="activeCatId" :options="catOptions" v-if="cats.length" />
          <div v-else style="color: #f56c6c">该周期未绑定类别方案，请先在「员工类别 → 类别方案」中配置。</div>

          <el-table
            v-if="cats.length && form.perf_grades.length"
            :data="sortedPerfGrades"
            border
            size="small"
            style="margin-top: 12px"
            v-loading="loadingMatrix"
          >
            <el-table-column label="绩效 / 薪酬分位" min-width="140" fixed="left">
              <template #default="{ row }">
                <strong>{{ row.label }}</strong>
                <div style="font-size: 12px; color: #909399">{{ row.code }}</div>
              </template>
            </el-table-column>
            <el-table-column
              v-for="band in PAY_BANDS"
              :key="band.code"
              :label="band.label"
              min-width="260"
            >
              <template #default="{ row }">
                <div class="cell-inputs">
                  <el-input-number
                    :model-value="getCell(row.code, band.code).coef_low"
                    :min="0"
                    :max="5"
                    :step="0.05"
                    :precision="4"
                    size="small"
                    style="width: 100px"
                    @update:model-value="(v: number) => setCell(row.code, band.code, 'coef_low', v)"
                  />
                  <span class="hr-text-secondary">~</span>
                  <el-input-number
                    :model-value="getCell(row.code, band.code).coef_high"
                    :min="0"
                    :max="5"
                    :step="0.05"
                    :precision="4"
                    size="small"
                    style="width: 100px"
                    @update:model-value="(v: number) => setCell(row.code, band.code, 'coef_high', v)"
                  />
                </div>
                <div class="cell-preview">{{ cellPreview(row.code, band.code) }}</div>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="cats.length" style="margin-top: 12px; display: flex; gap: 12px">
            <el-button
              type="primary"
              :disabled="!matrixDirty"
              :loading="savingMatrix"
              @click="saveMatrix"
            >
              保存矩阵 ({{ matrixDirtyCount }})
            </el-button>
            <span class="hr-text-secondary" style="line-height: 32px">
              基础 ANNUAL 比例（用于回显示例）：{{ baseHintText }}
            </span>
          </div>
        </template>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { ElMessage, ElMessageBox, type FormInstance } from "element-plus"
import { Document, Setting, DataLine } from "@element-plus/icons-vue"
import api from "@/api/client"
import PageHeader from "@/components/PageHeader.vue"

type PerfGrade = { code: string; label: string; sort_order: number }
type Rule = { id?: number; reward_cycle: number; country: string; adjustment_type: string; base_pct: number; notes?: string }
type Factor = { id?: number; reward_cycle: number; category: number; adjustment_type: string; factor: number; notes?: string }
type Cat = { id: number; code: string; name: string; sort_order: number; scheme: number }
type Scheme = { id: number; code: string; name: string; categories: Cat[] }
type Cell = { id?: number; reward_cycle: number; category: number; perf_grade_code: string; pay_band: string; coef_low: number; coef_high: number; notes?: string }

const PAY_BANDS = [
  { code: "BELOW_P50", label: "P50 以下" },
  { code: "P50_P75", label: "P50 – P75" },
  { code: "ABOVE_P75", label: "P75 以上" },
]

const DEFAULT_PERF: PerfGrade[] = [
  { code: "STAR_5", label: "5星", sort_order: 1 },
  { code: "STAR_4", label: "4星", sort_order: 2 },
  { code: "STAR_3", label: "3星", sort_order: 3 },
  { code: "STAR_2", label: "2星", sort_order: 4 },
  { code: "STAR_1", label: "1星", sort_order: 5 },
]

const route = useRoute()
const router = useRouter()
const id = computed(() => route.params.id as string | undefined)
const isNew = computed(() => !id.value)

const formRef = ref<FormInstance>()
const loading = ref(false)
const saving = ref(false)
const cycles = ref<any[]>([])
const periodDate = ref<string>("")
const activeTab = ref("base")

const form = ref({
  code: "",
  name: "",
  period: "",
  status: "DRAFT",
  rounding_rule: "ROUND_HALF_UP",
  reward_cycle: null as number | null,
  perf_grades: [] as PerfGrade[],
})

const formRules = {
  code: [{ required: true, message: "请输入编码", trigger: "blur" }],
  name: [{ required: true, message: "请输入名称", trigger: "blur" }],
  period: [{ required: true, message: "请选择周期", trigger: "change" }],
  status: [{ required: true, message: "请选择状态", trigger: "change" }],
  reward_cycle: [{ required: true, message: "请绑定 Reward Cycle", trigger: "change" }],
}

function onPeriodChange(v: string) {
  form.value.period = v || ""
}

async function loadCycles() {
  const r = await api.get("/reward-cycle/")
  cycles.value = Array.isArray(r.data) ? r.data : r.data.results || []
}

async function loadPlan() {
  if (isNew.value) {
    form.value.perf_grades = DEFAULT_PERF.map((g) => ({ ...g }))
    return
  }
  loading.value = true
  try {
    const r = await api.get(`/admin/adjustment-plans/${id.value}/`)
    const d = r.data
    form.value = {
      code: d.code,
      name: d.name,
      period: d.period,
      status: d.status,
      rounding_rule: d.rounding_rule,
      reward_cycle: d.reward_cycle,
      perf_grades: (d.perf_grades || DEFAULT_PERF).map((g: PerfGrade) => ({ ...g })),
    }
    periodDate.value = d.period
  } finally {
    loading.value = false
  }
}

async function submitBase() {
  if (!formRef.value) return
  const ok = await formRef.value.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    const payload = {
      code: form.value.code,
      name: form.value.name,
      period: form.value.period,
      status: form.value.status,
      rounding_rule: form.value.rounding_rule,
      reward_cycle: form.value.reward_cycle,
      perf_grades: form.value.perf_grades,
    }
    if (isNew.value) {
      const r = await api.post("/admin/adjustment-plans/", payload)
      ElMessage.success("已创建")
      router.replace(`/admin/plans/adjustment/${r.data.id}`)
    } else {
      await api.put(`/admin/adjustment-plans/${id.value}/`, payload)
      ElMessage.success("已保存")
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || JSON.stringify(e?.response?.data) || "保存失败")
  } finally {
    saving.value = false
  }
}

// ============ Tab 2 · 规则配置 ============
const schemes = ref<Scheme[]>([])
const rules = ref<Rule[]>([])
const factors = ref<Factor[]>([])
const ruleDirtyIds = ref<Set<number | string>>(new Set())
const factorDirtyIds = ref<Set<number | string>>(new Set())
const loadingRules = ref(false)
const savingRules = ref(false)
const savingFactors = ref(false)

const cats = computed<Cat[]>(() => {
  const c = cycles.value.find((x) => x.id === form.value.reward_cycle)
  if (!c?.category_scheme) return []
  const s = schemes.value.find((x) => x.id === c.category_scheme)
  return s ? s.categories : []
})

const unsavedRuleCount = computed(
  () => rules.value.filter((r) => !r.id || ruleDirtyIds.value.has(r.id)).length,
)
const unsavedFactorCount = computed(
  () => factors.value.filter((f) => !f.id || factorDirtyIds.value.has(f.id)).length,
)

function pctLabel(v: number) {
  return `${(Number(v || 0) * 100).toFixed(2)}%`
}

async function loadSchemes() {
  const r = await api.get("/admin/category-schemes/")
  schemes.value = Array.isArray(r.data) ? r.data : r.data.results || []
}

async function loadRulesAndFactors() {
  if (!form.value.reward_cycle) return
  loadingRules.value = true
  try {
    const [r1, r2] = await Promise.all([
      api.get("/admin/regional-adjustment-rules/", { params: { cycle: form.value.reward_cycle } }),
      api.get("/admin/employee-category-factors/", { params: { cycle: form.value.reward_cycle } }),
    ])
    rules.value = (Array.isArray(r1.data) ? r1.data : r1.data.results || []).map((x: any) => ({
      ...x,
      base_pct: Number(x.base_pct),
    }))
    factors.value = (Array.isArray(r2.data) ? r2.data : r2.data.results || []).map((x: any) => ({
      ...x,
      factor: Number(x.factor),
    }))
    ruleDirtyIds.value = new Set()
    factorDirtyIds.value = new Set()
  } finally {
    loadingRules.value = false
  }
}

function markRuleDirty(r: Rule) {
  if (r.id != null) ruleDirtyIds.value = new Set([...ruleDirtyIds.value, r.id])
}
function markFactorDirty(f: Factor) {
  if (f.id != null) factorDirtyIds.value = new Set([...factorDirtyIds.value, f.id])
}

function addRule() {
  if (!form.value.reward_cycle) return
  rules.value.push({
    reward_cycle: form.value.reward_cycle,
    country: "CN",
    adjustment_type: "ANNUAL",
    base_pct: 0.05,
    notes: "",
  })
}
function addFactor() {
  if (!form.value.reward_cycle || !cats.value.length) {
    ElMessage.warning("请先为该周期绑定类别方案并配置类别")
    return
  }
  factors.value.push({
    reward_cycle: form.value.reward_cycle,
    category: cats.value[0].id,
    adjustment_type: "ANNUAL",
    factor: 1.0,
    notes: "",
  })
}

async function saveRules() {
  savingRules.value = true
  try {
    for (const r of rules.value) {
      if (!r.id) {
        const resp = await api.post("/admin/regional-adjustment-rules/", r)
        Object.assign(r, resp.data)
      } else if (ruleDirtyIds.value.has(r.id)) {
        await api.put(`/admin/regional-adjustment-rules/${r.id}/`, r)
      }
    }
    ElMessage.success("已保存")
    await loadRulesAndFactors()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || JSON.stringify(e?.response?.data) || "保存失败")
  } finally {
    savingRules.value = false
  }
}

async function saveFactors() {
  savingFactors.value = true
  try {
    for (const f of factors.value) {
      if (!f.id) {
        const resp = await api.post("/admin/employee-category-factors/", f)
        Object.assign(f, resp.data)
      } else if (factorDirtyIds.value.has(f.id)) {
        await api.put(`/admin/employee-category-factors/${f.id}/`, f)
      }
    }
    ElMessage.success("已保存")
    await loadRulesAndFactors()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || JSON.stringify(e?.response?.data) || "保存失败")
  } finally {
    savingFactors.value = false
  }
}

async function deleteRule(r: Rule) {
  if (!r.id) return
  try {
    await ElMessageBox.confirm(`确定删除 ${r.country}/${r.adjustment_type} 规则?`, "提示", { type: "warning" })
  } catch {
    return
  }
  await api.delete(`/admin/regional-adjustment-rules/${r.id}/`)
  await loadRulesAndFactors()
}

async function deleteFactor(f: Factor) {
  if (!f.id) return
  try {
    await ElMessageBox.confirm(`确定删除该系数?`, "提示", { type: "warning" })
  } catch {
    return
  }
  await api.delete(`/admin/employee-category-factors/${f.id}/`)
  await loadRulesAndFactors()
}

// ============ Tab 3 · 公式与矩阵 ============
const perfDirty = ref(false)
const savingPerf = ref(false)
const matrixCells = ref<Cell[]>([])
const loadingMatrix = ref(false)
const savingMatrix = ref(false)
const activeCatId = ref<number | null>(null)
const matrixDirtyKeys = ref<Set<string>>(new Set())

const sortedPerfGrades = computed(() =>
  [...form.value.perf_grades].sort((a, b) => a.sort_order - b.sort_order),
)

const catOptions = computed(() =>
  cats.value.map((c) => ({ label: `${c.code} - ${c.name}`, value: c.id })),
)

const matrixDirtyCount = computed(() => matrixDirtyKeys.value.size)
const matrixDirty = computed(() => matrixDirtyCount.value > 0)

function markPerfDirty() {
  perfDirty.value = true
}

function addPerf() {
  const maxSort = form.value.perf_grades.reduce((m, g) => Math.max(m, g.sort_order || 0), 0)
  form.value.perf_grades.push({ code: "", label: "", sort_order: maxSort + 1 })
  markPerfDirty()
}

function removePerf(idx: number) {
  form.value.perf_grades.splice(idx, 1)
  markPerfDirty()
}

function movePerf(idx: number, delta: number) {
  const sorted = [...form.value.perf_grades].sort((a, b) => a.sort_order - b.sort_order)
  const target = idx + delta
  if (target < 0 || target >= sorted.length) return
  const a = sorted[idx]
  const b = sorted[target]
  const tmp = a.sort_order
  a.sort_order = b.sort_order
  b.sort_order = tmp
  markPerfDirty()
}

function restoreDefaultPerf() {
  form.value.perf_grades = DEFAULT_PERF.map((g) => ({ ...g }))
  markPerfDirty()
}

async function savePerfGrades() {
  if (!id.value) return
  for (const g of form.value.perf_grades) {
    if (!g.code || !g.label) {
      ElMessage.error("绩效档位的 code 和 label 不能为空")
      return
    }
  }
  savingPerf.value = true
  try {
    await api.patch(`/admin/adjustment-plans/${id.value}/`, {
      perf_grades: form.value.perf_grades,
    })
    ElMessage.success("已保存绩效档位")
    perfDirty.value = false
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || JSON.stringify(e?.response?.data) || "保存失败")
  } finally {
    savingPerf.value = false
  }
}

async function loadMatrix() {
  if (!form.value.reward_cycle) return
  loadingMatrix.value = true
  try {
    const r = await api.get("/admin/adjustment-matrix-cells/", {
      params: { cycle: form.value.reward_cycle },
    })
    matrixCells.value = (Array.isArray(r.data) ? r.data : r.data.results || []).map((x: any) => ({
      ...x,
      coef_low: Number(x.coef_low),
      coef_high: Number(x.coef_high),
    }))
    matrixDirtyKeys.value = new Set()
  } finally {
    loadingMatrix.value = false
  }
}

function cellKey(perfCode: string, payBand: string) {
  return `${activeCatId.value}|${perfCode}|${payBand}`
}

function getCell(perfCode: string, payBand: string): Cell {
  const found = matrixCells.value.find(
    (c) =>
      c.category === activeCatId.value &&
      c.perf_grade_code === perfCode &&
      c.pay_band === payBand,
  )
  if (found) return found
  return {
    reward_cycle: form.value.reward_cycle as number,
    category: activeCatId.value as number,
    perf_grade_code: perfCode,
    pay_band: payBand,
    coef_low: 1,
    coef_high: 1,
  }
}

function setCell(perfCode: string, payBand: string, field: "coef_low" | "coef_high", v: number) {
  let found = matrixCells.value.find(
    (c) =>
      c.category === activeCatId.value &&
      c.perf_grade_code === perfCode &&
      c.pay_band === payBand,
  )
  if (!found) {
    found = {
      reward_cycle: form.value.reward_cycle as number,
      category: activeCatId.value as number,
      perf_grade_code: perfCode,
      pay_band: payBand,
      coef_low: 1,
      coef_high: 1,
    }
    matrixCells.value.push(found)
  }
  found[field] = v
  matrixDirtyKeys.value = new Set([...matrixDirtyKeys.value, cellKey(perfCode, payBand)])
}

const baseAnnualPct = computed(() => {
  // 取当前类别的 ANNUAL factor × 第一条 ANNUAL 规则
  if (!activeCatId.value) return null
  const factor = factors.value.find(
    (f) => f.category === activeCatId.value && f.adjustment_type === "ANNUAL",
  )
  const rule = rules.value.find((r) => r.adjustment_type === "ANNUAL")
  if (!factor || !rule) return null
  return Number(rule.base_pct) * Number(factor.factor)
})

const baseHintText = computed(() => {
  if (baseAnnualPct.value == null) return "（需先在 Tab 2 配置规则）"
  return `${pctLabel(baseAnnualPct.value)} (取第一条 ANNUAL 规则 × 当前类别系数)`
})

function cellPreview(perfCode: string, payBand: string): string {
  const cell = getCell(perfCode, payBand)
  if (baseAnnualPct.value == null) return ""
  const lo = (baseAnnualPct.value * cell.coef_low * 100).toFixed(2)
  const hi = (baseAnnualPct.value * cell.coef_high * 100).toFixed(2)
  return `→ ${lo}% – ${hi}%`
}

async function saveMatrix() {
  savingMatrix.value = true
  try {
    for (const key of matrixDirtyKeys.value) {
      const [catIdStr, perfCode, payBand] = key.split("|")
      const catId = Number(catIdStr)
      const cell = matrixCells.value.find(
        (c) => c.category === catId && c.perf_grade_code === perfCode && c.pay_band === payBand,
      )
      if (!cell) continue
      if (cell.id) {
        await api.put(`/admin/adjustment-matrix-cells/${cell.id}/`, cell)
      } else {
        const resp = await api.post("/admin/adjustment-matrix-cells/", cell)
        Object.assign(cell, resp.data)
      }
    }
    ElMessage.success("矩阵已保存")
    matrixDirtyKeys.value = new Set()
    await loadMatrix()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || JSON.stringify(e?.response?.data) || "保存失败")
  } finally {
    savingMatrix.value = false
  }
}

watch(
  () => cats.value,
  (cs) => {
    if (cs.length && !cs.find((c) => c.id === activeCatId.value)) {
      activeCatId.value = cs[0].id
    }
  },
  { immediate: true },
)

watch(
  () => form.value.reward_cycle,
  async (cycleId) => {
    if (cycleId) {
      await loadRulesAndFactors()
      await loadMatrix()
    }
  },
)

onMounted(async () => {
  await Promise.all([loadCycles(), loadSchemes()])
  await loadPlan()
})

</script>

<style scoped>
.adj-plan-tabs {
  margin-top: var(--hr-space-3);
}
:deep(.adj-plan-tabs .el-tabs__item) {
  font-size: var(--hr-font-size-md);
  height: 44px;
  line-height: 44px;
}
.formula-card {
  border: 1px solid var(--hr-color-border-light);
}
.formula-text {
  margin: 0;
  font-family: var(--hr-font-family-mono, monospace);
  white-space: pre-wrap;
  font-size: 13px;
  color: var(--hr-color-text-secondary);
  line-height: 1.7;
}
.cell-inputs {
  display: flex;
  align-items: center;
  gap: 6px;
}
.cell-preview {
  margin-top: 4px;
  font-size: 12px;
  color: #67c23a;
  min-height: 16px;
}
.hr-section-title {
  font-size: var(--hr-font-size-md);
  font-weight: var(--hr-font-weight-semibold);
  margin: 0 0 12px;
}
</style>
