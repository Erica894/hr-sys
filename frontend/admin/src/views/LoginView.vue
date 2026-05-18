<template>
  <div class="login-page">
    <div class="login-page__bg" />
    <div class="login-page__lang">
      <LangSwitcher />
    </div>
    <div class="login-card">
      <div class="login-card__brand">
        <div class="login-card__brand-mark">HR</div>
        <div class="login-card__brand-text">
          <div class="login-card__brand-title">{{ t("login.brand_title") }}</div>
          <div class="login-card__brand-sub">{{ t("login.brand_sub") }}</div>
        </div>
      </div>

      <div class="login-card__heading">
        <h1>{{ store.needsMfa ? t("login.heading_mfa") : t("login.heading_normal") }}</h1>
        <p>{{ store.needsMfa ? t("login.sub_mfa") : t("login.sub_normal") }}</p>
      </div>

      <el-form
        v-if="!store.needsMfa"
        :model="loginForm"
        size="large"
        class="login-form"
        @submit.prevent="doLogin"
      >
        <el-form-item :label="t('login.field_email')">
          <el-input
            v-model="email"
            autocomplete="username"
            :placeholder="t('login.ph_email')"
            :prefix-icon="Message"
          />
        </el-form-item>
        <el-form-item :label="t('login.field_password')">
          <el-input
            v-model="pw"
            type="password"
            autocomplete="current-password"
            :placeholder="t('login.ph_password')"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          native-type="submit"
          :loading="loading"
          class="login-form__submit"
          @click="doLogin"
        >
          {{ t("login.submit_login") }}
        </el-button>
      </el-form>

      <el-form
        v-else
        size="large"
        class="login-form"
        @submit.prevent="doMfa"
      >
        <el-form-item :label="t('login.field_otp')">
          <el-input
            v-model="code"
            :placeholder="t('login.ph_otp')"
            :prefix-icon="Key"
            maxlength="6"
          />
        </el-form-item>
        <el-button
          type="primary"
          native-type="submit"
          :loading="loading"
          class="login-form__submit"
          @click="doMfa"
        >
          {{ t("login.submit_mfa") }}
        </el-button>
      </el-form>

      <el-alert
        v-if="err"
        :title="err"
        type="error"
        :closable="false"
        show-icon
        class="login-form__alert"
      />

      <div class="login-card__footer">
        {{ t("login.footer") }} · {{ year }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue"
import { useI18n } from "vue-i18n"
import { useAuth } from "@/stores/auth"
import { useRouter } from "vue-router"
import { Key, Lock, Message } from "@element-plus/icons-vue"
import LangSwitcher from "@/components/LangSwitcher.vue"

const { t } = useI18n()
const store = useAuth()
const router = useRouter()
const email = ref("")
const pw = ref("")
const code = ref("")
const err = ref("")
const loading = ref(false)
const loginForm = reactive({})
const year = computed(() => new Date().getFullYear())

function landingFor() {
  if (store.hasRole("HR_ADMIN")) return "/admin/plans/adjustment"
  if (store.hasRole("DEPT_HEAD")) return "/allocation"
  return "/me/compensation"
}

async function doLogin() {
  err.value = ""
  loading.value = true
  try {
    await store.login(email.value, pw.value)
    if (!store.needsMfa) router.push(landingFor())
  } catch (e: any) {
    err.value = e.response?.data?.detail || t("login.err_default_login")
  } finally {
    loading.value = false
  }
}

async function doMfa() {
  err.value = ""
  loading.value = true
  try {
    await store.verifyMfa(code.value)
    router.push(landingFor())
  } catch (e: any) {
    err.value = e.response?.data?.detail || t("login.err_default_mfa")
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--hr-space-6);
  background: linear-gradient(135deg, #1e3a8a 0%, #1e5fbf 50%, #2563eb 100%);
  overflow: hidden;
}

.login-page__bg {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle at 20% 20%, rgba(255, 255, 255, 0.08) 0%, transparent 50%),
    radial-gradient(circle at 80% 80%, rgba(255, 255, 255, 0.06) 0%, transparent 50%);
  pointer-events: none;
}

.login-page__lang {
  position: absolute;
  top: var(--hr-space-5);
  right: var(--hr-space-6);
  z-index: 2;
}
.login-page__lang :deep(.lang-switcher) {
  color: rgba(255, 255, 255, 0.92);
}
.login-page__lang :deep(.lang-switcher:hover) {
  background: rgba(255, 255, 255, 0.12);
}
.login-page__lang :deep(.lang-switcher__caret) {
  color: rgba(255, 255, 255, 0.7);
}

.login-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  background: var(--hr-color-bg-surface);
  border-radius: var(--hr-radius-xl);
  box-shadow: var(--hr-shadow-floating);
  padding: var(--hr-space-10) var(--hr-space-8) var(--hr-space-6);
}

.login-card__brand {
  display: flex;
  align-items: center;
  gap: var(--hr-space-3);
  margin-bottom: var(--hr-space-8);
}

.login-card__brand-mark {
  width: 44px;
  height: 44px;
  background: var(--hr-color-brand);
  color: #fff;
  border-radius: var(--hr-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: var(--hr-font-weight-bold);
  font-size: var(--hr-font-size-md);
  letter-spacing: 0.5px;
}

.login-card__brand-title {
  font-size: var(--hr-font-size-lg);
  font-weight: var(--hr-font-weight-semibold);
  color: var(--hr-color-text-primary);
  line-height: 1.2;
}

.login-card__brand-sub {
  font-size: var(--hr-font-size-xs);
  color: var(--hr-color-text-hint);
  margin-top: 2px;
}

.login-card__heading {
  margin-bottom: var(--hr-space-6);
}

.login-card__heading h1 {
  font-size: var(--hr-font-size-2xl);
  font-weight: var(--hr-font-weight-semibold);
  color: var(--hr-color-text-primary);
  margin: 0 0 var(--hr-space-1);
}

.login-card__heading p {
  font-size: var(--hr-font-size-sm);
  color: var(--hr-color-text-regular);
}

.login-form :deep(.el-form-item__label) {
  font-size: var(--hr-font-size-sm);
  color: var(--hr-color-text-secondary);
  font-weight: var(--hr-font-weight-medium);
  padding-bottom: var(--hr-space-1);
}

.login-form :deep(.el-form-item) {
  margin-bottom: var(--hr-space-5);
}

.login-form__submit {
  width: 100%;
  height: 44px;
  font-size: var(--hr-font-size-md);
  font-weight: var(--hr-font-weight-medium);
  letter-spacing: 4px;
}

.login-form__alert {
  margin-top: var(--hr-space-4);
}

.login-card__footer {
  margin-top: var(--hr-space-8);
  text-align: center;
  font-size: var(--hr-font-size-xs);
  color: var(--hr-color-text-hint);
}
</style>
