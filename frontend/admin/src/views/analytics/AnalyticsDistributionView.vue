<template>
  <div class="hr-page">
    <PageHeader title="桶分布" subtitle="按矩阵基线 ± 系数区间分桶" />

    <el-card class="hr-card" shadow="never">
      <el-form inline :model="filter">
        <el-form-item label="周期 ID">
          <el-input-number v-model="filter.cycleId" :min="1" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="load">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="data" class="hr-card" shadow="never" style="margin-top: 16px">
      <div class="distrib-meta">
        年窗: {{ data.year_from }} → {{ data.year_to }}
      </div>
      <el-table :data="matrixRows" border stripe size="small" style="margin-top: 12px">
        <el-table-column prop="category" label="员工类别" width="160" fixed />
        <el-table-column
          v-for="bucket in data.buckets"
          :key="bucket"
          :label="bucketLabel(bucket)"
          align="center"
        >
          <template #default="{ row }">
            <span :class="bucketClass(bucket)">{{ row[bucket] || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="合计" width="90">
          <template #default="{ row }">{{ row.__total }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-empty v-if="!loading && !data" description="请选择周期后查询" />
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue"
import { ElMessage } from "element-plus"
import PageHeader from "@/components/PageHeader.vue"
import { analyticsApi, type DistributionResp } from "@/api/analytics"

const filter = reactive({ cycleId: 1 })
const data = ref<DistributionResp | null>(null)
const loading = ref(false)

const BUCKET_LABEL: Record<string, string> = {
  LOW: "偏低",
  IN_RANGE: "区间内",
  HIGH: "偏高",
  UNKNOWN: "未知",
}
function bucketLabel(b: string) {
  return BUCKET_LABEL[b] || b
}
function bucketClass(b: string) {
  if (b === "LOW") return "bucket-low"
  if (b === "HIGH") return "bucket-high"
  if (b === "UNKNOWN") return "bucket-unknown"
  return "bucket-in"
}

const matrixRows = computed(() => {
  if (!data.value) return []
  const byCat: Record<string, Record<string, number>> = {}
  for (const r of data.value.rows) {
    byCat[r.category] = byCat[r.category] || {}
    byCat[r.category][r.bucket] = (byCat[r.category][r.bucket] || 0) + r.count
  }
  return Object.entries(byCat).map(([cat, m]) => {
    const total = Object.values(m).reduce((a, b) => a + b, 0)
    return { category: cat, ...m, __total: total }
  })
})

async function load() {
  loading.value = true
  try {
    data.value = await analyticsApi.distribution(filter.cycleId)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "查询失败")
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.distrib-meta {
  font-size: var(--hr-font-size-sm);
  color: var(--hr-color-text-secondary);
}
.bucket-low { color: var(--hr-color-warning, #d9892a); font-weight: 600; }
.bucket-high { color: var(--hr-color-danger, #d94a4a); font-weight: 600; }
.bucket-in { color: var(--hr-color-success, #19a86b); font-weight: 600; }
.bucket-unknown { color: var(--hr-color-text-secondary); }
</style>
