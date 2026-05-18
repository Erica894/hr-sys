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
  border-radius: var(--hr-radius-xl);
  padding: var(--hr-space-5) var(--hr-space-5);
  box-shadow: var(--hr-shadow-card);
  display: flex;
  flex-direction: column;
  gap: var(--hr-space-2);
  min-width: 0;
  transition: box-shadow var(--hr-transition-fast),
    border-color var(--hr-transition-fast),
    transform var(--hr-transition-fast);
}
.stat-card:hover {
  border-color: var(--hr-color-border-strong);
  box-shadow: var(--hr-shadow-elevated);
  transform: translateY(-1px);
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
  font-size: var(--hr-font-size-3xl);
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

/* Workday 渐变 KPI: 4 个 tone 各对应一个色系 */
.stat-card--brand,
.stat-card--success,
.stat-card--warning,
.stat-card--danger {
  border: none;
  color: #fff;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12);
}
.stat-card--brand:hover,
.stat-card--success:hover,
.stat-card--warning:hover,
.stat-card--danger:hover {
  border-color: transparent;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.18);
}
.stat-card--brand   { background: var(--hr-gradient-kpi-blue); }
.stat-card--success { background: var(--hr-gradient-kpi-green); }
.stat-card--warning { background: var(--hr-gradient-kpi-orange); }
.stat-card--danger  { background: var(--hr-gradient-kpi-red); }

.stat-card--brand .stat-card__label,
.stat-card--success .stat-card__label,
.stat-card--warning .stat-card__label,
.stat-card--danger .stat-card__label {
  color: rgba(255, 255, 255, 0.82);
}
.stat-card--brand .stat-card__value-main,
.stat-card--success .stat-card__value-main,
.stat-card--warning .stat-card__value-main,
.stat-card--danger .stat-card__value-main {
  color: #fff;
}
.stat-card--brand .stat-card__value-unit,
.stat-card--success .stat-card__value-unit,
.stat-card--warning .stat-card__value-unit,
.stat-card--danger .stat-card__value-unit,
.stat-card--brand .stat-card__footer,
.stat-card--success .stat-card__footer,
.stat-card--warning .stat-card__footer,
.stat-card--danger .stat-card__footer {
  color: rgba(255, 255, 255, 0.78);
}
</style>
