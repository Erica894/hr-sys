import { createI18n } from "vue-i18n"
import zh from "../locales/zh.json"
import en from "../locales/en.json"

export type AppLocale = "zh" | "en"

const STORAGE_KEY = "hr-sys.locale"

function detectInitialLocale(): AppLocale {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === "zh" || stored === "en") return stored
  const nav = navigator.language?.toLowerCase() ?? ""
  return nav.startsWith("en") ? "en" : "zh"
}

export const i18n = createI18n({
  legacy: false,
  locale: detectInitialLocale(),
  fallbackLocale: "zh",
  messages: { zh, en },
})

export function persistLocale(locale: AppLocale) {
  localStorage.setItem(STORAGE_KEY, locale)
}
