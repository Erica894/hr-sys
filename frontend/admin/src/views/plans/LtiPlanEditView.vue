<template>
  <div class="hr-page">
    <PageHeader
      :title="isNew ? '新建 RSU 方案' : '编辑 RSU 方案'"
      subtitle="维护授予日、总股数、单价、Cliff、Vesting schedule"
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
        <el-input v-model="form.code" placeholder="如 RSU-2026" />
      </el-form-item>
      <el-form-item label="名称" prop="name">
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item label="授予日" prop="grant_date">
        <el-date-picker
          v-model="form.grant_date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
        />
      </el-form-item>
      <el-form-item label="总股数" prop="total_shares">
        <el-input-number v-model="form.total_shares" :min="0" :step="1000" style="width: 220px" />
      </el-form-item>
      <el-form-item label="股份单位" prop="share_unit">
        <el-select v-model="form.share_unit" style="width: 160px">
          <el-option label="ADS" value="ADS" />
          <el-option label="普通股" value="COMMON" />
        </el-select>
      </el-form-item>
      <el-form-item label="授予时单价" prop="unit_price_at_grant">
        <el-input-number
          v-model="form.unit_price_at_grant"
          :min="0"
          :step="0.1"
          :precision="4"
          style="width: 220px"
        />
      </el-form-item>
      <el-form-item label="Cliff (月)" prop="cliff_months">
        <el-input-number v-model="form.cliff_months" :min="0" :max="60" style="width: 160px" />
      </el-form-item>
      <el-form-item label="股票代码">
        <el-input v-model="form.stock_code" placeholder="如 BABA" style="width: 220px" />
      </el-form-item>
      <el-form-item label="方案文档 URL">
        <el-input v-model="form.plan_doc_url" placeholder="https://..." />
      </el-form-item>
      <el-form-item label="关联 Reward Cycle">
        <el-select v-model="form.reward_cycle" clearable placeholder="可选" style="width: 320px">
          <el-option
            v-for="c in cycles"
            :key="c.id"
            :label="`${c.code} (${c.budget_year})`"
            :value="c.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="Vesting (JSON)" prop="vestingText">
        <el-input
          v-model="form.vestingText"
          type="textarea"
          :rows="5"
          placeholder='{"schedule": [{"month": 12, "pct": 0.25}, {"month": 24, "pct": 0.25}]}'
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="submit" :loading="saving">保存</el-button>
        <el-button @click="$router.push('/admin/plans/lti')">取消</el-button>
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

const form = ref({
  code: "",
  name: "",
  grant_date: "",
  total_shares: 0,
  share_unit: "ADS",
  unit_price_at_grant: 0,
  cliff_months: 12,
  stock_code: "",
  plan_doc_url: "",
  reward_cycle: null as number | null,
  vestingText: "{}",
})

function validateJsonObject(_: any, value: string, cb: (e?: Error) => void) {
  if (!value || !value.trim()) return cb()
  try {
    const v = JSON.parse(value)
    if (typeof v !== "object" || v === null || Array.isArray(v)) {
      return cb(new Error("必须为 JSON 对象"))
    }
    cb()
  } catch {
    cb(new Error("JSON 格式错误"))
  }
}

const rules = {
  code: [{ required: true, message: "请输入编码", trigger: "blur" }],
  name: [{ required: true, message: "请输入名称", trigger: "blur" }],
  grant_date: [{ required: true, message: "请选择授予日", trigger: "change" }],
  unit_price_at_grant: [{ required: true, message: "请输入单价", trigger: "blur" }],
  vestingText: [{ validator: validateJsonObject, trigger: "blur" }],
}

async function loadCycles() {
  const r = await api.get("/reward-cycle/")
  cycles.value = Array.isArray(r.data) ? r.data : r.data.results || []
}

async function loadPlan() {
  if (isNew.value) return
  loading.value = true
  try {
    const r = await api.get(`/admin/lti-plans/${id.value}/`)
    const d = r.data
    form.value = {
      code: d.code,
      name: d.name,
      grant_date: d.grant_date,
      total_shares: Number(d.total_shares),
      share_unit: d.share_unit,
      unit_price_at_grant: Number(d.unit_price_at_grant),
      cliff_months: Number(d.cliff_months),
      stock_code: d.stock_code || "",
      plan_doc_url: d.plan_doc_url || "",
      reward_cycle: d.reward_cycle,
      vestingText: JSON.stringify(d.vesting_schedule || {}, null, 2),
    }
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
      grant_date: form.value.grant_date,
      total_shares: form.value.total_shares,
      share_unit: form.value.share_unit,
      unit_price_at_grant: form.value.unit_price_at_grant,
      cliff_months: form.value.cliff_months,
      stock_code: form.value.stock_code,
      plan_doc_url: form.value.plan_doc_url,
      reward_cycle: form.value.reward_cycle,
      vesting_schedule: JSON.parse(form.value.vestingText || "{}"),
    }
    if (isNew.value) {
      await api.post("/admin/lti-plans/", payload)
      ElMessage.success("已创建")
    } else {
      await api.put(`/admin/lti-plans/${id.value}/`, payload)
      ElMessage.success("已保存")
    }
    router.push("/admin/plans/lti")
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadCycles()
  await loadPlan()
})
</script>
