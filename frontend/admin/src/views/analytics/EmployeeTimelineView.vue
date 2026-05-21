<template>
  <div class="hr-page">
    <PageHeader title="员工时间线" subtitle="Y-1 / Y / Y+1 三年五列" />

    <el-card class="hr-card" shadow="never">
      <el-form inline :model="filter">
        <el-form-item label="员工 ID">
          <el-input-number v-model="filter.employeeId" :min="1" />
        </el-form-item>
        <el-form-item label="周期 ID">
          <el-input-number v-model="filter.cycleId" :min="1" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="load">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="data" class="hr-card" shadow="never" style="margin-top: 16px">
      <div class="timeline-meta">员工 ID: <b>{{ data.employee_id }}</b></div>
      <el-table :data="data.timeline" border stripe size="small" style="margin-top: 12px">
        <el-table-column prop="year" label="年份" width="80" fixed />
        <el-table-column label="快照" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.kind" size="small">{{ row.kind }}</el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column
          v-for="key in FIVE_COL_KEYS"
          :key="key"
          :label="FIVE_COL_LABELS[key]"
          min-width="130"
        >
          <template #default="{ row }">{{ formatCny(row[key]) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-empty v-if="!loading && !data" description="请输入员工 ID 与周期 ID 后查询" />
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
  type TimelineResp,
} from "@/api/analytics"

const filter = reactive({ employeeId: 1, cycleId: 1 })
const data = ref<TimelineResp | null>(null)
const loading = ref(false)

function formatCny(v: string | null | undefined): string {
  if (v == null) return "—"
  const n = Number(v)
  if (!isFinite(n)) return "—"
  return `¥${n.toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`
}

async function load() {
  loading.value = true
  try {
    data.value = await analyticsApi.employeeTimeline(filter.employeeId, filter.cycleId)
  } catch (e: any) {
    if (e?.response?.status === 404) {
      data.value = null
      ElMessage.warning("未找到该员工的可见数据")
    } else {
      ElMessage.error(e?.response?.data?.detail || "查询失败")
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.timeline-meta {
  font-size: var(--hr-font-size-sm);
  color: var(--hr-color-text-secondary);
}
</style>
