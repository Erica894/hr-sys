<template>
  <el-container direction="vertical" style="padding: 16px">
    <h3 style="margin: 0 0 12px">年终奖方案</h3>
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="占位页 — 年终奖完整工作流在 Sprint 2 交付"
      style="margin-bottom: 12px"
    />
    <el-table :data="rows" border v-loading="loading">
      <el-table-column prop="code" label="编码" width="140" />
      <el-table-column prop="name" label="名称" min-width="200" />
      <el-table-column prop="period" label="周期" width="120" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column label="预算总额(CNY)" width="160" align="right">
        <template #default="{ row }">{{ fmtMoney(row.budget_total_cny) }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <template #empty>暂无数据</template>
    </el-table>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import api from "@/api/client"

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

function fmtMoney(v: any) {
  if (v == null) return "-"
  return Number(v).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtTime(v: any) {
  if (!v) return "-"
  return new Date(v).toLocaleString("zh-CN")
}

onMounted(load)
</script>
