<template>
  <el-dropdown trigger="click" @command="onCommand">
    <span class="lang-switcher">
      <el-icon><Promotion /></el-icon>
      <span class="lang-switcher__label">{{ currentLabel }}</span>
      <el-icon class="lang-switcher__caret"><CaretBottom /></el-icon>
    </span>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="zh" :class="{ 'is-active': locale === 'zh' }">
          {{ t("lang.zh") }}
        </el-dropdown-item>
        <el-dropdown-item command="en" :class="{ 'is-active': locale === 'en' }">
          {{ t("lang.en") }}
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useI18n } from "vue-i18n"
import { CaretBottom, Promotion } from "@element-plus/icons-vue"
import { useLocaleStore } from "@/stores/locale"
import type { AppLocale } from "@/i18n"

const { t } = useI18n()
const localeStore = useLocaleStore()

const locale = computed(() => localeStore.locale)
const currentLabel = computed(() => (locale.value === "en" ? "EN" : "中"))

function onCommand(cmd: AppLocale) {
  localeStore.setLocale(cmd)
}
</script>

<style scoped>
.lang-switcher {
  display: inline-flex;
  align-items: center;
  gap: var(--hr-space-1);
  cursor: pointer;
  padding: var(--hr-space-1) var(--hr-space-2);
  border-radius: var(--hr-radius-md);
  color: var(--hr-color-topbar-text);
  font-size: var(--hr-font-size-sm);
  transition: background var(--hr-transition-fast);
}
.lang-switcher:hover {
  background: var(--hr-color-topbar-hover);
}
.lang-switcher__label {
  min-width: 18px;
  text-align: center;
}
.lang-switcher__caret {
  font-size: 12px;
  color: var(--hr-color-topbar-text-hint);
}
</style>
