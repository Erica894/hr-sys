<template>
  <div class="hr-page">
    <PageHeader
      title="调薪方案"
      subtitle="HR 维护的调薪方案模板，绑定 Reward Cycle 后内置规则与矩阵"
    >
      <template #actions>
        <el-button type="primary" :icon="Plus" @click="$router.push('/admin/plans/adjustment/new')">
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
        <el-table-column prop="period" label="周期" width="100" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="tagType(row.status)" effect="plain" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="绑定 Cycle" width="180">
          <template #default="{ row }">
            <span v-if="row.reward_cycle" class="hr-text-mono">{{ cycleCode(row.reward_cycle) }}</span>
            <span v-else class="hr-text-secondary">未绑定</span>
          </template>
        </el-table-column>
        <el-table-column label="矩阵单元格" width="140" align="right">
          <template #default="{ row }">
            <el-tag v-if="row.matrix_cell_count > 0" type="success" effect="plain" size="small">
              {{ row.matrix_cell_count }} 格
            </el-tag>
            <span v-else class="hr-text-secondary">未配置</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            <span class="hr-text-secondary">{{ fmtTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(`/admin/plans/adjustment/${row.id}`)">
              编辑
            </el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <EmptyHint
            title="暂无调薪方案"
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
import { fmtTime } from "@/utils/format"

const rows = ref<any[]>([])
const cycles = ref<any[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const [r1, r2] = await Promise.all([
      api.get("/admin/adjustment-plans/"),
      api.get("/reward-cycle/"),
    ])
    rows.value = Array.isArray(r1.data) ? r1.data : r1.data.results || []
    cycles.value = Array.isArray(r2.data) ? r2.data : r2.data.results || []
  } finally {
    loading.value = false
  }
}

function cycleCode(id: number) {
  const c = cycles.value.find((x) => x.id === id)
  return c ? c.code : `#${id}`
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
  await api.delete(`/admin/adjustment-plans/${row.id}/`)
  ElMessage.success("已删除")
  await load()
}

function tagType(s: string) {
  if (s === "ACTIVE") return "success"
  if (s === "CLOSED") return "info"
  return "warning"
}

function statusLabel(s: string) {
  return { ACTIVE: "生效中", CLOSED: "已关闭", DRAFT: "草稿" }[s] || s
}

onMounted(load)
</script>
