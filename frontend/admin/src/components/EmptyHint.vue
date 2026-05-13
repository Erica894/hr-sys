<template>
  <div class="empty-hint">
    <el-icon class="empty-hint__icon"><component :is="iconComp" /></el-icon>
    <div class="empty-hint__title">{{ title }}</div>
    <div v-if="description" class="empty-hint__desc">{{ description }}</div>
    <div v-if="$slots.default" class="empty-hint__action">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Box, DocumentRemove, Files, Search } from "@element-plus/icons-vue"

const props = withDefaults(
  defineProps<{
    title: string
    description?: string
    icon?: "box" | "document" | "files" | "search"
  }>(),
  { icon: "box" }
)

const iconComp = computed(() => {
  switch (props.icon) {
    case "document": return DocumentRemove
    case "files": return Files
    case "search": return Search
    default: return Box
  }
})
</script>

<style scoped>
.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--hr-space-2);
  padding: var(--hr-space-10) var(--hr-space-6);
  color: var(--hr-color-text-hint);
  text-align: center;
}
.empty-hint__icon {
  font-size: 48px;
  color: var(--hr-color-border-strong);
  margin-bottom: var(--hr-space-2);
}
.empty-hint__title {
  font-size: var(--hr-font-size-md);
  color: var(--hr-color-text-secondary);
  font-weight: var(--hr-font-weight-medium);
}
.empty-hint__desc {
  font-size: var(--hr-font-size-sm);
  color: var(--hr-color-text-hint);
  max-width: 360px;
}
.empty-hint__action {
  margin-top: var(--hr-space-3);
}
</style>
