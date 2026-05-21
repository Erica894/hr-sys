<template>
  <div class="hr-page">
    <PageHeader title="部门维度对比" subtitle="双年五列对比 + Δ%" />

    <el-card class="hr-card" shadow="never">
      <el-form inline :model="filter">
        <el-form-item label="目标年">
          <el-input-number v-model="filter.year" :min="2000" :max="2100" />
        </el-form-item>
        <el-form-item label="对比年">
          <el-input-number v-model="filter.compareYear" :min="2000" :max="2100" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="load">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="data" class="hr-card" shadow="never" style="margin-top: 16px">
      <el-table :data="data.rows" border stripe size="small">
        <el-table-column prop="org_unit_name" label="部门" width="160" fixed />
        <el-table-column prop="headcount" label="人数" width="80" />
        <el-table-column
          v-for="key in FIVE_COL_KEYS"
          :key="key"
          :label="FIVE_COL_LABELS[key]"
          align="center"
        >
          <el-table-column label="对比年均" min-width="120">
            <template #default="{ row }">{{ formatCny(row[key]?.base_avg) }}</template>
          </el-table-column>
          <el-table-column label="目标年均" min-width="120">
            <template #default="{ row }">{{ formatCny(row[key]?.target_avg) }}</template>
          </el-table-column>
          <el-table-column label="Δ%" width="90">
            <template #default="{ row }">
              <span :class="deltaClass(row[key]?.delta)">{{ formatDelta(row[key]?.delta) }}</span>
            </template>
          </el-table-column>
        </el-table-column>
      </el-table>
    </el-card>

    <el-empty v-if="!loading && !data" description="请选择年份后查询" />
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue"
import { ElMessage } from "element-plus"
import PageHeader from "@/components/PageHeader.vue"
import {
  analyticsApi,
  FIVE_COL_KEYS,
  FIVE_COL_LABELS,
  type ByDeptResp,
} from "@/api/analytics"

const now = new Date().getFullYear()
const filter = reactive({ year: now, compareYear: now - 1 })
const data = ref<ByDeptResp | null>(null)
const loading = ref(false)

function formatCny(v: string | null | undefined): string {
  if (v == null) return "—"
  const n = Number(v)
  if (!isFinite(n)) return "—"
  return `¥${n.toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`
}
function formatDelta(v: string | null | undefined): string {
  if (v == null) return "—"
  const n = Number(v)
  if (!isFinite(n)) return "—"
  return `${(n * 100).toFixed(2)}%`
}
function deltaClass(v: string | null | undefined) {
  if (v == null) return ""
  const n = Number(v)
  if (!isFinite(n)) return ""
  if (n > 0) return "delta-positive"
  if (n < 0) return "delta-negative"
  return ""
}

async function load() {
  loading.value = true
  try {
    data.value = await analyticsApi.byDept(filter.year, filter.compareYear)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "查询失败")
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.delta-positive { color: var(--hr-color-success, #19a86b); font-weight: 600; }
.delta-negative { color: var(--hr-color-danger, #d94a4a); font-weight: 600; }
</style>
