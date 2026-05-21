<template>
  <div class="hr-page">
    <PageHeader
      :title="isNew ? '新建年终奖方案' : '编辑年终奖方案'"
      subtitle="区域规则 → 类别系数 → 派生预算 → 部门池下发"
    />

    <el-tabs v-model="activeTab" class="bonus-plan-tabs" v-loading="loading">
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
              <el-input v-model="form.code" placeholder="如 BONUS-2026-01" />
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
                placeholder="必选 (规则与系数挂在 cycle 上)"
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
            <el-form-item>
              <el-button type="primary" @click="submitBase" :loading="saving">保存基础信息</el-button>
              <el-button @click="$router.push('/admin/plans/bonus')">返回列表</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>

      <!-- Tab 2: 区域规则 -->
      <el-tab-pane name="rules" :disabled="isNew || !form.reward_cycle">
        <template #label><span><el-icon><Setting /></el-icon> 区域规则</span></template>
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
            员工年终奖建议金额 = monthly_salary × base_months(国家) × factor(类别)。
            本表配置每个国家的基准月数。
          </p>

          <h3 class="hr-section-title">区域基准年终奖月数</h3>
          <el-table :data="rules" border v-loading="loadingRules">
            <el-table-column label="国家代码" width="160">
              <template #default="{ row }">
                <el-input v-model="row.country" size="small" placeholder="CN/US/SG" @change="markRuleDirty(row)" />
              </template>
            </el-table-column>
            <el-table-column label="基准月数" width="240">
              <template #default="{ row }">
                <el-input-number
                  v-model="row.base_months"
                  :min="0"
                  :max="24"
                  :step="0.1"
                  :precision="4"
                  size="small"
                  @change="markRuleDirty(row)"
                />
                <span style="margin-left: 8px; color: #909399; font-size: 12px">
                  ×{{ Number(row.base_months || 0).toFixed(2) }} 个月薪
                </span>
              </template>
            </el-table-column>
            <el-table-column label="备注" min-width="240">
              <template #default="{ row }">
                <el-input v-model="row.notes" size="small" @change="markRuleDirty(row)" />
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
        </template>
      </el-tab-pane>

      <!-- Tab 3: 类别系数 -->
      <el-tab-pane name="factors" :disabled="isNew || !form.reward_cycle">
        <template #label><span><el-icon><DataLine /></el-icon> 类别系数</span></template>
        <el-alert
          v-if="!form.reward_cycle"
          type="warning"
          :closable="false"
          show-icon
          title="请先在「基础信息」绑定 Reward Cycle 并保存。"
          style="margin-bottom: 16px"
        />
        <template v-else>
          <p class="hr-text-secondary">
            员工类别系数叠乘在区域基准月数之上，例如管理干部 1.20 = 比基准高 20%。
          </p>

          <h3 class="hr-section-title">员工类别系数（管理干部 / 员工）</h3>
          <el-table :data="factors" border v-loading="loadingFactors">
            <el-table-column label="员工类别" width="240">
              <template #default="{ row }">
                <el-select
                  v-model="row.employee_category_1"
                  size="small"
                  style="width: 100%"
                  @change="markFactorDirty(row)"
                >
                  <el-option label="管理干部 MANAGEMENT" value="MANAGEMENT" />
                  <el-option label="员工 STAFF" value="STAFF" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="系数" width="240">
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

type Rule = { id?: number; reward_cycle: number; country: string; base_months: number; notes?: string }
type Factor = { id?: number; reward_cycle: number; employee_category_1: string; factor: number; notes?: string }

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
  reward_cycle: null as number | null,
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
  if (isNew.value) return
  loading.value = true
  try {
    const r = await api.get(`/admin/bonus-plans/${id.value}/`)
    const d = r.data
    form.value = {
      code: d.code,
      name: d.name,
      period: d.period,
      status: d.status,
      reward_cycle: d.reward_cycle,
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
      reward_cycle: form.value.reward_cycle,
    }
    if (isNew.value) {
      const r = await api.post("/admin/bonus-plans/", payload)
      ElMessage.success("已创建")
      router.replace(`/admin/plans/bonus/${r.data.id}`)
    } else {
      await api.put(`/admin/bonus-plans/${id.value}/`, payload)
      ElMessage.success("已保存")
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || JSON.stringify(e?.response?.data) || "保存失败")
  } finally {
    saving.value = false
  }
}

// ============ Tab 2 · 区域规则 ============
const rules = ref<Rule[]>([])
const ruleDirtyIds = ref<Set<number | string>>(new Set())
const loadingRules = ref(false)
const savingRules = ref(false)

const unsavedRuleCount = computed(
  () => rules.value.filter((r) => !r.id || ruleDirtyIds.value.has(r.id)).length,
)

async function loadRules() {
  if (!form.value.reward_cycle) return
  loadingRules.value = true
  try {
    const r = await api.get("/admin/regional-bonus-rules/", {
      params: { cycle: form.value.reward_cycle },
    })
    rules.value = (Array.isArray(r.data) ? r.data : r.data.results || []).map((x: any) => ({
      ...x,
      base_months: Number(x.base_months),
    }))
    ruleDirtyIds.value = new Set()
  } finally {
    loadingRules.value = false
  }
}

function markRuleDirty(r: Rule) {
  if (r.id != null) ruleDirtyIds.value = new Set([...ruleDirtyIds.value, r.id])
}

function addRule() {
  if (!form.value.reward_cycle) return
  rules.value.push({
    reward_cycle: form.value.reward_cycle,
    country: "CN",
    base_months: 1.5,
    notes: "",
  })
}

async function saveRules() {
  savingRules.value = true
  try {
    for (const r of rules.value) {
      if (!r.id) {
        const resp = await api.post("/admin/regional-bonus-rules/", r)
        Object.assign(r, resp.data)
      } else if (ruleDirtyIds.value.has(r.id)) {
        await api.put(`/admin/regional-bonus-rules/${r.id}/`, r)
      }
    }
    ElMessage.success("已保存")
    await loadRules()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || JSON.stringify(e?.response?.data) || "保存失败")
  } finally {
    savingRules.value = false
  }
}

async function deleteRule(r: Rule) {
  if (!r.id) return
  try {
    await ElMessageBox.confirm(`确定删除 ${r.country} 规则?`, "提示", { type: "warning" })
  } catch {
    return
  }
  await api.delete(`/admin/regional-bonus-rules/${r.id}/`)
  await loadRules()
}

// ============ Tab 3 · 类别系数 ============
const factors = ref<Factor[]>([])
const factorDirtyIds = ref<Set<number | string>>(new Set())
const loadingFactors = ref(false)
const savingFactors = ref(false)

const unsavedFactorCount = computed(
  () => factors.value.filter((f) => !f.id || factorDirtyIds.value.has(f.id)).length,
)

async function loadFactors() {
  if (!form.value.reward_cycle) return
  loadingFactors.value = true
  try {
    const r = await api.get("/admin/bonus-category-factors/", {
      params: { cycle: form.value.reward_cycle },
    })
    factors.value = (Array.isArray(r.data) ? r.data : r.data.results || []).map((x: any) => ({
      ...x,
      factor: Number(x.factor),
    }))
    factorDirtyIds.value = new Set()
  } finally {
    loadingFactors.value = false
  }
}

function markFactorDirty(f: Factor) {
  if (f.id != null) factorDirtyIds.value = new Set([...factorDirtyIds.value, f.id])
}

function addFactor() {
  if (!form.value.reward_cycle) return
  factors.value.push({
    reward_cycle: form.value.reward_cycle,
    employee_category_1: "STAFF",
    factor: 1.0,
    notes: "",
  })
}

async function saveFactors() {
  savingFactors.value = true
  try {
    for (const f of factors.value) {
      if (!f.id) {
        const resp = await api.post("/admin/bonus-category-factors/", f)
        Object.assign(f, resp.data)
      } else if (factorDirtyIds.value.has(f.id)) {
        await api.put(`/admin/bonus-category-factors/${f.id}/`, f)
      }
    }
    ElMessage.success("已保存")
    await loadFactors()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || JSON.stringify(e?.response?.data) || "保存失败")
  } finally {
    savingFactors.value = false
  }
}

async function deleteFactor(f: Factor) {
  if (!f.id) return
  try {
    await ElMessageBox.confirm(`确定删除该系数?`, "提示", { type: "warning" })
  } catch {
    return
  }
  await api.delete(`/admin/bonus-category-factors/${f.id}/`)
  await loadFactors()
}

// ============ 初始化 ============
watch(
  () => form.value.reward_cycle,
  (v) => {
    if (v) {
      loadRules()
      loadFactors()
    } else {
      rules.value = []
      factors.value = []
    }
  },
)

watch(activeTab, (v) => {
  if (!form.value.reward_cycle) return
  if (v === "rules") loadRules()
  if (v === "factors") loadFactors()
})

onMounted(async () => {
  await loadCycles()
  await loadPlan()
})
</script>

<style scoped>
.bonus-plan-tabs {
  background: var(--hr-bg-elevated);
  padding: var(--hr-space-3);
  border-radius: var(--hr-radius-lg);
}

.hr-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--hr-text-primary);
  margin: 0 0 12px;
}
</style>
