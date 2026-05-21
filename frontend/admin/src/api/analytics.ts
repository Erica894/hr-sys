import api from "./client"

export type FiveColKey =
  | "annual_fixed_cny"
  | "annual_bonus_cny"
  | "annual_cash_cny"
  | "annual_rsu_value_cny"
  | "annual_total_comp_cny"

export const FIVE_COL_KEYS: FiveColKey[] = [
  "annual_fixed_cny",
  "annual_bonus_cny",
  "annual_cash_cny",
  "annual_rsu_value_cny",
  "annual_total_comp_cny",
]

export const FIVE_COL_LABELS: Record<FiveColKey, string> = {
  annual_fixed_cny: "年度固定",
  annual_bonus_cny: "年度奖金",
  annual_cash_cny: "年度现金",
  annual_rsu_value_cny: "RSU 价值",
  annual_total_comp_cny: "年度总薪",
}

export interface ColAggregate {
  avg: string | null
  median: string | null
}

export interface OverviewResp {
  year: number
  headcount: number
  annual_fixed_cny: ColAggregate
  annual_bonus_cny: ColAggregate
  annual_cash_cny: ColAggregate
  annual_rsu_value_cny: ColAggregate
  annual_total_comp_cny: ColAggregate
}

export interface ByDeptColCell {
  base_avg: string | null
  target_avg: string | null
  delta: string | null
}

export interface ByDeptRow {
  org_unit_id: number
  org_unit_name: string
  headcount: number
  annual_fixed_cny: ByDeptColCell
  annual_bonus_cny: ByDeptColCell
  annual_cash_cny: ByDeptColCell
  annual_rsu_value_cny: ByDeptColCell
  annual_total_comp_cny: ByDeptColCell
}

export interface ByDeptResp {
  year: number
  compare_year: number
  rows: ByDeptRow[]
}

export interface DistributionRow {
  category: string
  bucket: string
  count: number
}

export interface DistributionResp {
  cycle_id: number
  year_from: number
  year_to: number
  buckets: string[]
  rows: DistributionRow[]
}

export interface TimelineRow {
  year: number
  kind: string | null
  annual_fixed_cny?: string | null
  annual_bonus_cny?: string | null
  annual_cash_cny?: string | null
  annual_rsu_value_cny?: string | null
  annual_total_comp_cny?: string | null
}

export interface TimelineResp {
  employee_id: number
  timeline: TimelineRow[]
}

export const analyticsApi = {
  overview(year: number) {
    return api
      .get<OverviewResp>(`/analytics/overview/`, { params: { year } })
      .then((r) => r.data)
  },
  byDept(year: number, compareYear: number) {
    return api
      .get<ByDeptResp>(`/analytics/by-dept/`, {
        params: { year, compare_year: compareYear },
      })
      .then((r) => r.data)
  },
  distribution(cycleId: number) {
    return api
      .get<DistributionResp>(`/analytics/distribution/`, {
        params: { cycle_id: cycleId },
      })
      .then((r) => r.data)
  },
  employeeTimeline(employeeId: number, cycleId: number) {
    return api
      .get<TimelineResp>(`/analytics/employee/${employeeId}/timeline/`, {
        params: { cycle_id: cycleId },
      })
      .then((r) => r.data)
  },
}
