<template>
  <div class="hr-page">
    <PageHeader
      :title="isNew ? '新建调薪方案' : '编辑调薪方案'"
      subtitle="维护方案编码、预算总额、适用范围、公式"
    />
    <div class="hr-section" style="max-width: 860px">
    <el-form
      ref="formRef"
      :model="form"
      label-width="140px"
      :rules="rules"
      v-loading="loading"
    >
      <el-form-item label="编码" prop="code">
        <el-input v-model="form.code" placeholder="如 ADJ-2026" />
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
      <el-form-item label="预算总额 (CNY)" prop="budget_total_cny">
        <el-input-number
          v-model="form.budget_total_cny"
          :min="0"
          :step="10000"
          :precision="2"
          style="width: 220px"
        />
      </el-form-item>
      <el-form-item label="舍入规则" prop="rounding_rule">
        <el-select v-model="form.rounding_rule">
          <el-option label="四舍五入 ROUND_HALF_UP" value="ROUND_HALF_UP" />
          <el-option label="银行家舍入 ROUND_HALF_EVEN" value="ROUND_HALF_EVEN" />
          <el-option label="向下取整 ROUND_FLOOR" value="ROUND_FLOOR" />
        </el-select>
      </el-form-item>
      <el-form-item label="关联 Reward Cycle">
        <el-select
          v-model="form.reward_cycle"
          clearable
          placeholder="可选"
          style="width: 320px"
        >
          <el-option
            v-for="c in cycles"
            :key="c.id"
            :label="`${c.code} (${c.budget_year})`"
            :value="c.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="适用范围 (JSON)" prop="scopeText">
        <el-input
          v-model="form.scopeText"
          type="textarea"
          :rows="4"
          placeholder='{"depts": ["ALL"], "levels": ["M1-M4"]}'
        />
      </el-form-item>
      <el-form-item label="公式 (JSON)" prop="formulaText">
        <el-input
          v-model="form.formulaText"
          type="textarea"
          :rows="4"
          placeholder='{"method": "percentage", "base": "annual_salary"}'
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="submit" :loading="saving">保存</el-button>
        <el-button @click="$router.push('/admin/plans/adjustment')">取消</el-button>
      </el-form-item>
    </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import { useRoute, useRouter } from "vue-router"
import { ElMessage, type FormInstance } from "element-plus"
import api from "@/api/client"
import PageHeader from "@/components/PageHeader.vue"

const route = useRoute()
const router = useRouter()

const id = computed(() => route.params.id as string | undefined)
const isNew = computed(() => !id.value)

const formRef = ref<FormInstance>()
const loading = ref(false)
const saving = ref(false)
const cycles = ref<any[]>([])
const periodDate = ref<string>("")

const form = ref({
  code: "",
  name: "",
  period: "",
  status: "DRAFT",
  budget_total_cny: 0,
  rounding_rule: "ROUND_HALF_UP",
  reward_cycle: null as number | null,
  scopeText: "{}",
  formulaText: "{}",
})

const rules = {
  code: [{ required: true, message: "请输入编码", trigger: "blur" }],
  name: [{ required: true, message: "请输入名称", trigger: "blur" }],
  period: [{ required: true, message: "请选择周期", trigger: "change" }],
  status: [{ required: true, message: "请选择状态", trigger: "change" }],
  scopeText: [{ validator: validateJson, trigger: "blur" }],
  formulaText: [{ validator: validateJson, trigger: "blur" }],
}

function validateJson(_: any, value: string, cb: (e?: Error) => void) {
  if (!value || !value.trim()) return cb()
  try {
    JSON.parse(value)
    cb()
  } catch {
    cb(new Error("JSON 格式错误"))
  }
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
    const r = await api.get(`/admin/adjustment-plans/${id.value}/`)
    const d = r.data
    form.value = {
      code: d.code,
      name: d.name,
      period: d.period,
      status: d.status,
      budget_total_cny: Number(d.budget_total_cny),
      rounding_rule: d.rounding_rule,
      reward_cycle: d.reward_cycle,
      scopeText: JSON.stringify(d.scope || {}, null, 2),
      formulaText: JSON.stringify(d.formula || {}, null, 2),
    }
    periodDate.value = d.period
  } finally {
    loading.value = false
  }
}

async function submit() {
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
      budget_total_cny: form.value.budget_total_cny,
      rounding_rule: form.value.rounding_rule,
      reward_cycle: form.value.reward_cycle,
      scope: JSON.parse(form.value.scopeText || "{}"),
      formula: JSON.parse(form.value.formulaText || "{}"),
    }
    if (isNew.value) {
      await api.post("/admin/adjustment-plans/", payload)
      ElMessage.success("已创建")
    } else {
      await api.put(`/admin/adjustment-plans/${id.value}/`, payload)
      ElMessage.success("已保存")
    }
    router.push("/admin/plans/adjustment")
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadCycles()
  await loadPlan()
})
</script>
