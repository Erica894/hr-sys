<template>
  <div class="hr-page">
    <PageHeader
      title="审批列表"
      subtitle="待您处理的薪酬调整与执行下发审批任务"
    />
    <div class="hr-section hr-section--flush">
      <el-table
        :data="items"
        stripe
        v-loading="loading"
      >
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="scenario" label="场景" width="150" />
        <el-table-column prop="target_type" label="目标对象" width="140" />
        <el-table-column prop="target_id" label="目标 ID" width="100" />
        <el-table-column label="审批步骤">
          <template #default="{ row }">
            {{ row.current_step }} / {{ row.steps?.length ?? "?" }}
          </template>
        </el-table-column>
        <el-table-column label="超预算">
          <template #default="{ row }">
            <el-tag v-if="row.over_budget_flag" type="warning" effect="plain">是</el-tag>
            <span v-else class="hr-text-hint">否</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="360" align="right">
          <template #default="{ row }">
            <el-input
              v-model="comments[row.id]"
              placeholder="审批意见"
              size="small"
              style="width: 160px; margin-right: 8px"
            />
            <el-button size="small" type="success" @click="act(row, 'APPROVE')">
              通过
            </el-button>
            <el-button size="small" type="danger" @click="act(row, 'REJECT')">
              驳回
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <EmptyHint
            title="暂无待审批任务"
            description="所有审批任务已处理完毕"
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

const items = ref<any[]>([])
const comments = ref<Record<number, string>>({})
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const r = await api.get("/approval/my-pending/")
    items.value = r.data
  } finally {
    loading.value = false
  }
}
async function act(row: any, action: string) {
  await api.post(`/approval/${row.id}/action/`, {
    action,
    comment: comments.value[row.id] || "",
  })
  await load()
}
onMounted(load)
</script>
