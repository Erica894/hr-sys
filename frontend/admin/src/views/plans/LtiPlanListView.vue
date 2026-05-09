<template>
  <el-container direction="vertical" style="padding: 16px">
    <div style="display: flex; align-items: center; margin-bottom: 12px">
      <h3 style="margin: 0; flex: 1">RSU 方案</h3>
      <el-button type="primary" @click="$router.push('/admin/plans/lti/new')">新建</el-button>
    </div>
    <el-table :data="rows" border v-loading="loading">
      <el-table-column prop="code" label="编码" width="140" />
      <el-table-column prop="name" label="名称" min-width="200" />
      <el-table-column prop="grant_date" label="授予日" width="130" />
      <el-table-column label="总股数" width="140" align="right">
        <template #default="{ row }">{{ fmtInt(row.total_shares) }}</template>
      </el-table-column>
      <el-table-column label="单价" width="120" align="right">
        <template #default="{ row }">{{ fmtNum(row.unit_price_at_grant) }}</template>
      </el-table-column>
      <el-table-column prop="stock_code" label="股票代码" width="120" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="$router.push(`/admin/plans/lti/${row.id}`)">
            编辑
          </el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import api from "@/api/client"

const rows = ref<any[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const r = await api.get("/admin/lti-plans/")
    rows.value = Array.isArray(r.data) ? r.data : r.data.results || []
  } finally {
    loading.value = false
  }
}

async function remove(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除方案 "${row.name}" ?`, "删除确认", { type: "warning" })
  } catch {
    return
  }
  await api.delete(`/admin/lti-plans/${row.id}/`)
  ElMessage.success("已删除")
  await load()
}

function fmtInt(v: any) {
  return v == null ? "-" : Number(v).toLocaleString("zh-CN")
}
function fmtNum(v: any) {
  return v == null ? "-" : Number(v).toFixed(4)
}

onMounted(load)
</script>
