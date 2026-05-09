<template>
  <el-container direction="vertical" style="padding: 16px">
    <div style="display: flex; align-items: center; margin-bottom: 12px">
      <h3 style="margin: 0; flex: 1">调薪方案</h3>
      <el-button type="primary" @click="$router.push('/admin/plans/adjustment/new')">新建</el-button>
    </div>
    <el-table :data="rows" border v-loading="loading">
      <el-table-column prop="code" label="编码" width="140" />
      <el-table-column prop="name" label="名称" min-width="200" />
      <el-table-column prop="period" label="周期" width="120" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="tagType(row.status)">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="预算总额(CNY)" width="160" align="right">
        <template #default="{ row }">{{ fmtMoney(row.budget_total_cny) }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="$router.push(`/admin/plans/adjustment/${row.id}`)">
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
    const r = await api.get("/admin/adjustment-plans/")
    rows.value = Array.isArray(r.data) ? r.data : r.data.results || []
  } finally {
    loading.value = false
  }
}

async function remove(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除方案 "${row.name}" ?`, "删除确认", {
      type: "warning",
    })
  } catch {
    return
  }
  await api.delete(`/admin/adjustment-plans/${row.id}/`)
  ElMessage.success("已删除")
  await load()
}

function tagType(s: string) {
  if (s === "ACTIVE") return "success"
  if (s === "CLOSED") return "info"
  return "warning"
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
