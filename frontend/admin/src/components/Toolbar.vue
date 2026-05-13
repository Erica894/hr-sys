<template>
  <div :class="['hr-toolbar', { 'hr-toolbar--plain': plain }]">
    <slot />
    <div v-if="$slots.right" class="hr-toolbar__spacer" />
    <slot name="right" />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  plain?: boolean
}>()
</script>
