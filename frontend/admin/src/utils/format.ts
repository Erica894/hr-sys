/* 统一的数字 / 货币 / 时间 / 百分比格式化 */

const DASH = "-"

function isBlank(v: unknown): boolean {
  return v === null || v === undefined || v === ""
}

/** 货币：保留 2 位小数，CNY 千分位。空值返回 "-"。 */
export function fmtMoney(v: unknown, fallback = DASH): string {
  if (isBlank(v)) return fallback
  return Number(v).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

/** 整数千分位。空值返回 "-"。 */
export function fmtInt(v: unknown, fallback = DASH): string {
  if (isBlank(v)) return fallback
  return Number(v).toLocaleString("zh-CN")
}

/** 任意数字千分位（最多 2 位小数）。空值返回 "-"。 */
export function fmtNum(v: unknown, digits = 4, fallback = DASH): string {
  if (isBlank(v)) return fallback
  return Number(v).toFixed(digits)
}

/** 0.0125 → "1.25%"。空值返回 "-"。 */
export function fmtPercent(v: unknown, digits = 2, fallback = DASH): string {
  if (isBlank(v)) return fallback
  return (Number(v) * 100).toFixed(digits) + "%"
}

/** 已是百分数的值（如 12.5）→ "12.50%"。 */
export function fmtPercentRaw(v: unknown, digits = 2, fallback = DASH): string {
  if (isBlank(v)) return fallback
  return Number(v).toFixed(digits) + "%"
}

/** ISO 时间 → "2026/05/13 14:23:45"（zh-CN）。空值返回 "-"。 */
export function fmtTime(v: unknown, fallback = DASH): string {
  if (isBlank(v)) return fallback
  return new Date(v as string | number).toLocaleString("zh-CN")
}

/** ISO 日期 → "2026/05/13"。空值返回 "-"。 */
export function fmtDate(v: unknown, fallback = DASH): string {
  if (isBlank(v)) return fallback
  return new Date(v as string | number).toLocaleDateString("zh-CN")
}
