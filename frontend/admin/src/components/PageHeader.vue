<template>
  <div class="hr-page-header">
    <div class="hr-page-header__main">
      <h1 class="hr-page-title">
        <slot name="title">{{ title }}</slot>
      </h1>
      <p v-if="$slots.subtitle || subtitle" class="hr-page-subtitle">
        <slot name="subtitle">{{ subtitle }}</slot>
      </p>
    </div>
    <div v-if="$slots.actions" class="hr-page-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title?: string
  subtitle?: string
}>()
</script>
