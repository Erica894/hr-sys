<template>
  <div class="hr-page">
    <PageHeader
      title="执行下发"
      subtitle="审批通过后，HR 录入 MFA 验证码触发本周期最终下发动作"
    />

    <div class="execute-card">
      <div class="execute-card__header">
        <el-icon class="execute-card__icon"><Warning /></el-icon>
        <div>
          <div class="execute-card__title">注意：执行后不可撤销</div>
          <div class="execute-card__sub">
            将固化所有 AdjustmentProposal 与 LTIGrant，并写入 reclaim 字段
          </div>
        </div>
      </div>

      <el-descriptions
        v-if="cycle"
        :column="2"
        border
        size="default"
        class="execute-card__meta"
      >
        <el-descriptions-item label="周期 Code">
          <span class="hr-text-mono">{{ cycle.code }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="当前状态">
          <el-tag :type="statusType(cycle.status)" effect="plain" size="small">
            {{ cycle.status }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <el-form size="large" class="execute-card__form" @submit.prevent="doExecute">
        <el-form-item label="MFA 验证码">
          <el-input
            v-model="code"
            placeholder="请输入您的 6 位动态验证码"
            :prefix-icon="Key"
            maxlength="6"
          />
        </el-form-item>
        <el-button
          type="danger"
          size="large"
          @click="doExecute"
          :loading="loading"
          :disabled="!canExecute"
          style="width: 100%"
        >
          确认执行
        </el-button>
      </el-form>

      <el-alert
        v-if="msg"
        :title="msg"
        :type="msgType"
        :closable="false"
        show-icon
        class="execute-card__alert"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from "vue"
import { Key, Warning } from "@element-plus/icons-vue"
import api from "@/api/client"
import PageHeader from "@/components/PageHeader.vue"

const cycle = ref<any>(null)
const code = ref("")
const msg = ref("")
const msgType = ref<"success" | "error">("success")
const loading = ref(false)

const canExecute = computed(() => {
  const s = cycle.value?.status
  return s === "APPROVED_PENDING_EXECUTE" || s === "APPROVED"
})

function statusType(status: string): "success" | "warning" | "info" | "danger" | "primary" {
  if (status === "EXECUTED") return "success"
  if (status?.startsWith("APPROVED")) return "warning"
  if (status === "APPROVING") return "primary"
  return "info"
}

async function load() {
  const r = await api.get("/reward-cycle/")
  cycle.value = r.data[0] || r.data.results?.[0]
}

async function doExecute() {
  loading.value = true
  try {
    const r = await api.post(
      `/reward-cycle/${cycle.value.id}/execute/`,
      null,
      { headers: { "X-MFA-Code": code.value } }
    )
    msg.value = `执行成功（${r.data.executed_at || "刚刚"}）`
    msgType.value = "success"
    await load()
  } catch (e: any) {
    msg.value = e.response?.data?.detail || "执行失败，请检查 MFA 验证码"
    msgType.value = "error"
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.execute-card {
  max-width: 640px;
  margin: 0 auto;
  background: var(--hr-color-bg-surface);
  border: 1px solid var(--hr-color-border-light);
  border-radius: var(--hr-radius-lg);
  padding: var(--hr-space-8);
  box-shadow: var(--hr-shadow-card);
}
.execute-card__header {
  display: flex;
  align-items: flex-start;
  gap: var(--hr-space-3);
  padding: var(--hr-space-3) var(--hr-space-4);
  background: var(--hr-color-warning-light);
  border-radius: var(--hr-radius-md);
  margin-bottom: var(--hr-space-6);
}
.execute-card__icon {
  font-size: 22px;
  color: var(--hr-color-warning);
  flex-shrink: 0;
  margin-top: 2px;
}
.execute-card__title {
  font-size: var(--hr-font-size-md);
  font-weight: var(--hr-font-weight-semibold);
  color: var(--hr-color-text-primary);
}
.execute-card__sub {
  font-size: var(--hr-font-size-sm);
  color: var(--hr-color-text-secondary);
  margin-top: 2px;
}
.execute-card__meta {
  margin-bottom: var(--hr-space-6);
}
.execute-card__form :deep(.el-form-item) {
  margin-bottom: var(--hr-space-5);
}
.execute-card__alert {
  margin-top: var(--hr-space-4);
}
</style>
