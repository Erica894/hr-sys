<template>
  <el-container style="min-height: 100vh">
    <el-header
      v-if="showNav"
      class="portal-header"
    >
      <span class="portal-header__brand">{{ t("header.brand") }}</span>
      <div class="portal-header__right">
        <el-dropdown v-if="I18N_PUBLIC" trigger="click" @command="onLang">
          <span class="portal-lang">
            {{ locale === "en" ? "EN" : "中" }}
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="zh">{{ t("lang.zh") }}</el-dropdown-item>
              <el-dropdown-item command="en">{{ t("lang.en") }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button size="small" @click="logout">{{ t("header.logout") }}</el-button>
      </div>
    </el-header>
    <el-main style="padding: 0">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useI18n } from "vue-i18n"
import { useRoute, useRouter } from "vue-router"
import { useAuth } from "@/stores/auth"
import { useLocaleStore } from "@/stores/locale"
import type { AppLocale } from "@/i18n"

const I18N_PUBLIC = false
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuth()
const localeStore = useLocaleStore()

const showNav = computed(() => route.path !== "/login")
const locale = computed(() => localeStore.locale)

function logout() {
  auth.logout()
  router.push("/login")
}

function onLang(cmd: AppLocale) {
  localeStore.setLocale(cmd)
}
</script>

<style scoped>
.portal-header {
  display: flex;
  align-items: center;
  background: #1d4380;
  color: #fff;
  box-shadow: 0 2px 8px rgba(8, 25, 61, 0.18);
}
.portal-header__brand {
  font-weight: 600;
  flex: 1;
}
.portal-header__right {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}
.portal-lang {
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  transition: background 150ms ease;
}
.portal-lang:hover {
  background: rgba(255, 255, 255, 0.12);
}
</style>
