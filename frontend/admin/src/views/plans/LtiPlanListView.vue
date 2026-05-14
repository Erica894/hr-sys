<template>
  <div class="hr-page">
    <PageHeader
      title="RSU 方案"
      subtitle="长期激励（LTI）方案模板，定义授予日、单价、归属规则"
    >
      <template #actions>
        <el-button type="primary" :icon="Plus" @click="$router.push('/admin/plans/lti/new')">
          新建方案
        </el-button>
      </template>
    </PageHeader>

    <div class="hr-section hr-section--flush">
      <el-table :data="rows" stripe v-loading="loading">
        <el-table-column prop="code" label="编码" width="160">
          <template #default="{ row }">
            <span class="hr-text-mono">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="220" />
        <el-table-column prop="grant_date" label="授予日" width="130" />
        <el-table-column label="总股数" width="140" align="right">
          <template #default="{ row }">
            <span class="hr-text-mono">{{ fmtInt(row.total_shares) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="授予单价" width="130" align="right">
          <template #default="{ row }">
            <span class="hr-text-mono">{{ fmtNum(row.unit_price_at_grant) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="stock_code" label="股票代码" width="120">
          <template #default="{ row }">
            <span class="hr-text-mono">{{ row.stock_code || "-" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(`/admin/plans/lti/${row.id}`)">
              编辑
            </el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <EmptyHint
            title="暂无 RSU 方案"
            description="点击右上角「新建方案」开始创建"
            icon="document"
          />
        </template>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { Plus } from "@element-plus/icons-vue"
import api from "@/api/client"
import PageHeader from "@/components/PageHeader.vue"
import EmptyHint from "@/components/EmptyHint.vue"
import { fmtInt, fmtNum } from "@/utils/format"

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
    await ElMessageBox.confirm(`确认删除方案"${row.name}"？`, "删除确认", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    })
  } catch {
    return
  }
  await api.delete(`/admin/lti-plans/${row.id}/`)
  ElMessage.success("已删除")
  await load()
}

onMounted(load)
</script>
