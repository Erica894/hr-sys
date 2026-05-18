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
/* Workday-style: 白底 + 顶部 3px 色条 + 大轻字重数字 */
.stat-card {
  position: relative;
  background: var(--hr-color-bg-surface);
  border: 1px solid var(--hr-color-border-light);
  border-radius: var(--hr-radius-xl);
  padding: 24px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  display: flex;
  flex-direction: column;
  gap: var(--hr-space-2);
  min-width: 0;
  overflow: hidden;
  transition: box-shadow var(--hr-transition-fast),
    border-color var(--hr-transition-fast);
}
.stat-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--hr-color-border);
}
.stat-card:hover {
  border-color: var(--hr-color-border-strong);
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
}
.stat-card__label {
  font-size: 12px;
  font-weight: var(--hr-font-weight-medium);
  color: var(--hr-color-text-regular);
  letter-spacing: 0.3px;
  line-height: var(--hr-line-height-tight);
}
.stat-card__value {
  display: flex;
  align-items: baseline;
  gap: var(--hr-space-2);
  margin-top: 4px;
}
.stat-card__value-main {
  font-size: 36px;
  font-weight: 400;
  color: var(--hr-color-text-primary);
  line-height: 1.1;
  letter-spacing: -0.5px;
}
.stat-card__value-unit {
  font-size: 13px;
  color: var(--hr-color-text-regular);
}
.stat-card__footer {
  font-size: 12px;
  color: var(--hr-color-text-hint);
  margin-top: 2px;
}

/* tone 只决定顶部色条颜色,卡片本体保持白净 */
.stat-card--brand::before   { background: var(--hr-color-brand); }
.stat-card--success::before { background: #1f7a4a; }
.stat-card--warning::before { background: #c5832a; }
.stat-card--danger::before  { background: #c53b50; }
</style>
