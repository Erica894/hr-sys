<template>
  <div class="hr-page">
    <PageHeader title="薪酬总览" subtitle="单年五列均值/中位数 + 头数" />

    <el-card class="hr-card" shadow="never">
      <el-form inline :model="filter">
        <el-form-item label="年份">
          <el-input-number v-model="filter.year" :min="2000" :max="2100" :step="1" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="load">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="data" class="hr-card" shadow="never" style="margin-top: 16px">
      <div class="overview-meta">
        <span>年份: <b>{{ data.year }}</b></span>
        <span style="margin-left: 24px">在册人数: <b>{{ data.headcount }}</b></span>
      </div>
      <el-row :gutter="16" style="margin-top: 16px">
        <el-col v-for="key in FIVE_COL_KEYS" :key="key" :span="24 / 5" :xs="24" :sm="12" :md="8" :lg="24 / 5">
          <el-card class="kpi-card" shadow="never">
            <div class="kpi-card__label">{{ FIVE_COL_LABELS[key] }}</div>
            <div class="kpi-card__value">
              均值: {{ formatCny(data[key]?.avg) }}
            </div>
            <div class="kpi-card__sub">
              中位: {{ formatCny(data[key]?.median) }}
            </div>
          </el-card>
        </el-col>
      </el-row>
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
  type OverviewResp,
} from "@/api/analytics"

const filter = reactive({ year: new Date().getFullYear() })
const data = ref<OverviewResp | null>(null)
const loading = ref(false)

function formatCny(v: string | null | undefined): string {
  if (!v) return "—"
  const n = Number(v)
  if (!isFinite(n)) return "—"
  return `¥${n.toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`
}

async function load() {
  loading.value = true
  try {
    data.value = await analyticsApi.overview(filter.year)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "查询失败")
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.overview-meta {
  font-size: var(--hr-font-size-sm);
  color: var(--hr-color-text-secondary);
}
.kpi-card {
  border: 1px solid var(--hr-color-border);
}
.kpi-card__label {
  font-size: var(--hr-font-size-xs);
  color: var(--hr-color-text-secondary);
  margin-bottom: 6px;
}
.kpi-card__value {
  font-size: var(--hr-font-size-lg);
  font-weight: var(--hr-font-weight-semibold);
  color: var(--hr-color-text-primary);
}
.kpi-card__sub {
  font-size: var(--hr-font-size-sm);
  color: var(--hr-color-text-secondary);
  margin-top: 4px;
}
</style>
