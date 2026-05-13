<template>
  <div :class="['stat-card', `stat-card--${tone}`]">
    <div class="stat-card__label">
      <slot name="label">{{ label }}</slot>
    </div>
    <div class="stat-card__value">
      <span class="stat-card__value-main hr-text-mono">
        <slot>{{ value }}</slot>
      </span>
      <span v-if="unit" class="stat-card__value-unit">{{ unit }}</span>
    </div>
    <div v-if="$slots.footer || hint" class="stat-card__footer">
      <slot name="footer">{{ hint }}</slot>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label?: string
    value?: string | number
    unit?: string
    hint?: string
    tone?: "default" | "brand" | "success" | "warning" | "danger"
  }>(),
  { tone: "default" }
)
</script>

<style scoped>
.stat-card {
  background: var(--hr-color-bg-surface);
  border: 1px solid var(--hr-color-border-light);
  border-radius: var(--hr-radius-md);
  padding: var(--hr-space-4) var(--hr-space-5);
  box-shadow: var(--hr-shadow-card);
  display: flex;
  flex-direction: column;
  gap: var(--hr-space-2);
  min-width: 0;
  transition: box-shadow var(--hr-transition-fast),
    border-color var(--hr-transition-fast);
}
.stat-card:hover {
  border-color: var(--hr-color-border-strong);
  box-shadow: var(--hr-shadow-elevated);
}
.stat-card__label {
  font-size: var(--hr-font-size-sm);
  color: var(--hr-color-text-regular);
  line-height: var(--hr-line-height-tight);
}
.stat-card__value {
  display: flex;
  align-items: baseline;
  gap: var(--hr-space-2);
}
.stat-card__value-main {
  font-size: var(--hr-font-size-2xl);
  font-weight: var(--hr-font-weight-semibold);
  color: var(--hr-color-text-primary);
  line-height: var(--hr-line-height-tight);
}
.stat-card__value-unit {
  font-size: var(--hr-font-size-sm);
  color: var(--hr-color-text-regular);
}
.stat-card__footer {
  font-size: var(--hr-font-size-xs);
  color: var(--hr-color-text-hint);
}
.stat-card--brand .stat-card__value-main { color: var(--hr-color-brand); }
.stat-card--success .stat-card__value-main { color: var(--hr-color-success); }
.stat-card--warning .stat-card__value-main { color: var(--hr-color-warning); }
.stat-card--danger .stat-card__value-main { color: var(--hr-color-danger); }
</style>
