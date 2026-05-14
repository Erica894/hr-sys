<template>
  <div class="hr-page">
    <PageHeader
      title="年终奖方案"
      subtitle="年终奖完整工作流将在 v1.5 上线，当前仅提供方案台账"
    />

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="占位页 — 年终奖完整工作流（BudgetCell + Proposal + 执行）将在 v1.5 上线"
      style="margin-bottom: var(--hr-space-4)"
    />

    <div class="hr-section hr-section--flush">
      <el-table :data="rows" stripe v-loading="loading">
        <el-table-column prop="code" label="编码" width="160">
          <template #default="{ row }">
            <span class="hr-text-mono">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="220" />
        <el-table-column prop="period" label="周期" width="120" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag effect="plain" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="预算总额（CNY）" width="180" align="right">
          <template #default="{ row }">
            <span class="hr-text-mono">{{ fmtMoney(row.budget_total_cny) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            <span class="hr-text-secondary">{{ fmtTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <EmptyHint
            title="暂无年终奖方案"
            description="完整工作流计划在 v1.5 上线"
            icon="document"
          />
        </template>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import api from "@/api/client"
import PageHeader from "@/components/PageHeader.vue"
import EmptyHint from "@/components/EmptyHint.vue"
import { fmtMoney, fmtTime } from "@/utils/format"

const rows = ref<any[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const r = await api.get("/admin/bonus-plans/")
    rows.value = Array.isArray(r.data) ? r.data : r.data.results || []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
