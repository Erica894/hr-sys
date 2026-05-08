<template>
  <el-container direction="vertical" style="padding: 16px">
    <h3>My Pending Approvals</h3>
    <el-table :data="items" border>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="scenario" label="Scenario" width="150" />
      <el-table-column prop="target_type" label="Target" width="140" />
      <el-table-column prop="target_id" label="Target ID" width="100" />
      <el-table-column label="Step">
        <template #default="{ row }">
          {{ row.current_step }} / {{ row.steps?.length ?? "?" }}
        </template>
      </el-table-column>
      <el-table-column label="Over Budget">
        <template #default="{ row }">
          <el-tag v-if="row.over_budget_flag" type="warning">YES</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="Actions" width="320">
        <template #default="{ row }">
          <el-input
            v-model="comments[row.id]"
            placeholder="comment"
            size="small"
            style="width: 140px; margin-right: 8px"
          />
          <el-button size="small" type="success" @click="act(row, 'APPROVE')">
            Approve
          </el-button>
          <el-button size="small" type="danger" @click="act(row, 'REJECT')">
            Reject
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import api from "@/api/client"

const items = ref<any[]>([])
const comments = ref<Record<number, string>>({})

async function load() {
  const r = await api.get("/approval/my-pending/")
  items.value = r.data
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
