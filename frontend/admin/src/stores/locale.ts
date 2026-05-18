import { defineStore } from "pinia"
import { i18n, persistLocale, type AppLocale } from "../i18n"
import api from "../api/client"

export const useLocaleStore = defineStore("locale", {
  state: () => ({
    locale: (i18n.global.locale.value as AppLocale) ?? "zh",
  }),
  actions: {
    setLocale(next: AppLocale) {
      if (next === this.locale) return
      this.locale = next
      i18n.global.locale.value = next
      persistLocale(next)
      const access = localStorage.getItem("access")
      if (access) {
        api.patch("/auth/me/language/", { preferred_language: next }).catch(() => {})
      }
    },
    syncFromServer(serverLocale: AppLocale | null | undefined) {
      if (!serverLocale) return
      if (serverLocale === this.locale) return
      this.locale = serverLocale
      i18n.global.locale.value = serverLocale
      persistLocale(serverLocale)
    },
  },
})
