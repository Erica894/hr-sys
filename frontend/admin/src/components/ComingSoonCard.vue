<template>
  <div class="coming-soon">
    <div class="coming-soon__inner">
      <div class="coming-soon__badge">
        <el-icon><Clock /></el-icon>
        <span>{{ expected || "敬请期待" }}</span>
      </div>
      <h2 class="coming-soon__title">{{ title }}</h2>
      <p v-if="description" class="coming-soon__desc">{{ description }}</p>
      <ul v-if="bullets && bullets.length" class="coming-soon__bullets">
        <li v-for="(b, i) in bullets" :key="i">
          <el-icon class="coming-soon__bullet-icon"><Check /></el-icon>
          <span>{{ b }}</span>
        </li>
      </ul>
      <div v-if="$slots.default" class="coming-soon__action">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Check, Clock } from "@element-plus/icons-vue"

defineProps<{
  title: string
  description?: string
  expected?: string
  bullets?: string[]
}>()
</script>

<style scoped>
.coming-soon {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--hr-space-8) var(--hr-space-4);
  min-height: 60vh;
}
.coming-soon__inner {
  max-width: 640px;
  width: 100%;
  background: var(--hr-color-bg-surface);
  border: 1px solid var(--hr-color-border-light);
  border-radius: var(--hr-radius-lg);
  padding: var(--hr-space-10) var(--hr-space-8);
  box-shadow: var(--hr-shadow-elevated);
  text-align: center;
}
.coming-soon__badge {
  display: inline-flex;
  align-items: center;
  gap: var(--hr-space-1);
  padding: var(--hr-space-1) var(--hr-space-3);
  background: var(--hr-color-brand-light);
  color: var(--hr-color-brand);
  font-size: var(--hr-font-size-xs);
  font-weight: var(--hr-font-weight-medium);
  border-radius: var(--hr-radius-full);
  margin-bottom: var(--hr-space-4);
}
.coming-soon__title {
  font-size: var(--hr-font-size-2xl);
  font-weight: var(--hr-font-weight-semibold);
  color: var(--hr-color-text-primary);
  margin: 0 0 var(--hr-space-3);
}
.coming-soon__desc {
  font-size: var(--hr-font-size-md);
  color: var(--hr-color-text-regular);
  line-height: var(--hr-line-height-relaxed);
  margin: 0 0 var(--hr-space-6);
}
.coming-soon__bullets {
  display: flex;
  flex-direction: column;
  gap: var(--hr-space-2);
  margin: 0 auto;
  padding: 0;
  list-style: none;
  text-align: left;
  max-width: 420px;
}
.coming-soon__bullets li {
  display: flex;
  align-items: flex-start;
  gap: var(--hr-space-2);
  padding: var(--hr-space-2) var(--hr-space-3);
  background: var(--hr-color-bg-subtle);
  border-radius: var(--hr-radius-md);
  font-size: var(--hr-font-size-sm);
  color: var(--hr-color-text-secondary);
}
.coming-soon__bullet-icon {
  color: var(--hr-color-success);
  flex-shrink: 0;
  margin-top: 2px;
}
.coming-soon__action {
  margin-top: var(--hr-space-6);
}
</style>
