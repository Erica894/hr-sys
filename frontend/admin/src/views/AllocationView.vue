<template>
  <el-container direction="vertical" style="padding: 16px">
    <el-descriptions v-if="cycle" :column="4" border>
      <el-descriptions-item label="周期">{{ cycle.code }}</el-descriptions-item>
      <el-descriptions-item label="状态">
        <el-tag>{{ statusLabel(cycle.status) }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="预算年度">{{ cycle.budget_year ?? "-" }}</el-descriptions-item>
      <el-descriptions-item label="行数">{{ rows.length }}</el-descriptions-item>
    </el-descriptions>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      style="margin-top: 12px"
      title="表头按 §4.5.2 设计规范分组"
      description="部分列（待归属 ADS / 薪酬区间桶 / 历年总包 / 涨幅 Δ%）所需的后端服务在 Sprint 2 实现，当前以 - 占位。"
    />

    <el-table
      :data="rows"
      border
      stripe
      size="small"
      style="margin-top: 12px"
      :max-height="640"
      show-overflow-tooltip
    >
      <!-- 固定列 -->
      <el-table-column type="index" label="序号" width="60" fixed="left" />
      <el-table-column prop="employee_no" label="工号" width="100" fixed="left" />
      <el-table-column prop="name_cn" label="姓名" width="100" fixed="left" />

      <!-- 基础信息 -->
      <el-table-column label="基础信息" align="center">
        <el-table-column prop="dept_name" label="部门" width="140" />
        <el-table-column prop="center_name" label="中心" width="120">
          <template #default="{ row }">{{ dash(row.center_name) }}</template>
        </el-table-column>
        <el-table-column prop="job_level_current" label="当前职级" width="90">
          <template #default="{ row }">{{ dash(row.job_level_current) }}</template>
        </el-table-column>
        <el-table-column prop="job_level_promoted" label="晋升后职级" width="100">
          <template #default="{ row }">{{ dash(row.job_level_promoted) }}</template>
        </el-table-column>
        <el-table-column prop="position_promoted" label="职务（晋升后）" width="140">
          <template #default="{ row }">
            {{ dash(row.position_promoted || row.position_current) }}
          </template>
        </el-table-column>
        <el-table-column label="人员类别1" width="100">
          <template #default="{ row }">{{ category1Label(row.employee_category_1) }}</template>
        </el-table-column>
        <el-table-column prop="employee_category_2" label="人员类别2" width="110">
          <template #default="{ row }">{{ dash(row.employee_category_2) }}</template>
        </el-table-column>
        <el-table-column prop="hire_date" label="入职日期" width="110">
          <template #default="{ row }">{{ dash(row.hire_date) }}</template>
        </el-table-column>
        <el-table-column prop="pay_country_region" label="发薪国家(地区)" width="130">
          <template #default="{ row }">{{ dash(row.pay_country_region) }}</template>
        </el-table-column>
        <el-table-column prop="pay_currency" label="币种" width="80">
          <template #default="{ row }">{{ dash(row.pay_currency) }}</template>
        </el-table-column>
      </el-table-column>

      <!-- 绩效 -->
      <el-table-column label="绩效" align="center">
        <el-table-column label="Y-1 上半年" width="100">
          <template #default="{ row }">{{ dash(row.perf_y_minus_1_h1) }}</template>
        </el-table-column>
        <el-table-column label="Y-1 下半年" width="100">
          <template #default="{ row }">{{ dash(row.perf_y_minus_1_h2) }}</template>
        </el-table-column>
      </el-table-column>

      <!-- 参与标志 -->
      <el-table-column label="参与标志" align="center">
        <el-table-column label="是否参与年调" width="110">
          <template #default="{ row }">
            <el-tag :type="row.participates_annual ? 'success' : 'info'" size="small">
              {{ row.participates_annual ? "是" : "否" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="晋升类别" width="100">
          <template #default="{ row }">{{ promotionLabel(row.promotion_category) }}</template>
        </el-table-column>
      </el-table-column>

      <!-- 参考·未来5年待归属 ADS -->
      <el-table-column label="参考·未来5年待归属 ADS" align="center">
        <el-table-column label="Y" width="80"><template #default>-</template></el-table-column>
        <el-table-column label="Y+1" width="80"><template #default>-</template></el-table-column>
        <el-table-column label="Y+2" width="80"><template #default>-</template></el-table-column>
        <el-table-column label="Y+3" width="80"><template #default>-</template></el-table-column>
        <el-table-column label="Y+4" width="80"><template #default>-</template></el-table-column>
      </el-table-column>

      <!-- 参考·其他 -->
      <el-table-column label="参考·其他" align="center">
        <el-table-column label="Y年待归属RSU占比" width="140">
          <template #default>-</template>
        </el-table-column>
        <el-table-column label="建议关注" width="100"><template #default>-</template></el-table-column>
        <el-table-column label="月薪P50" width="100"><template #default>-</template></el-table-column>
        <el-table-column label="月薪P75" width="100"><template #default>-</template></el-table-column>
        <el-table-column label="月薪P90" width="100"><template #default>-</template></el-table-column>
        <el-table-column label="Y年总包水平" width="120">
          <template #default>-</template>
        </el-table-column>
        <el-table-column label="建议年度调薪范围" width="140">
          <template #default>-</template>
        </el-table-column>
      </el-table-column>

      <!-- 当前月薪 -->
      <el-table-column label="当前月薪" width="120">
        <template #default="{ row }">{{ fmtMoney(row.current_monthly_salary) }}</template>
      </el-table-column>

      <!-- 调薪分配·晋升调薪 -->
      <el-table-column label="调薪分配·晋升调薪" align="center">
        <el-table-column label="晋升调薪比例" width="120">
          <template #default="{ row }">{{ fmtPct(row.promotion_adjustment_pct) }}</template>
        </el-table-column>
      </el-table-column>

      <!-- 调薪分配·年度调薪 -->
      <el-table-column label="调薪分配·年度调薪" align="center">
        <el-table-column label="建议比例" width="100">
          <template #default="{ row }">{{ fmtPct(row.annual_suggested_pct) }}</template>
        </el-table-column>
        <el-table-column label="管理者调整" width="140">
          <template #default="{ row }">
            <el-input-number
              v-model="row.annual_manager_delta_pct"
              :step="0.005"
              :precision="4"
              size="small"
              :disabled="!editable"
              @change="markDirty(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="调整后比例" width="100">
          <template #default="{ row }">{{ fmtPct(computeFinal(row)) }}</template>
        </el-table-column>
      </el-table-column>

      <!-- 调薪分配·总调薪 -->
      <el-table-column label="调薪分配·总调薪" align="center">
        <el-table-column label="总调薪比例" width="100">
          <template #default="{ row }">{{ fmtPct(computeTotalPct(row)) }}</template>
        </el-table-column>
        <el-table-column label="调整后月薪" width="120">
          <template #default="{ row }">{{ fmtMoney(computeNewSalary(row)) }}</template>
        </el-table-column>
        <el-table-column label="总调薪额" width="120">
          <template #default>-</template>
        </el-table-column>
      </el-table-column>

      <!-- Y年股票授予 -->
      <el-table-column label="Y年股票授予 (ADS)" align="center">
        <el-table-column label="是否具资格" width="100"><template #default>-</template></el-table-column>
        <el-table-column label="授予档位" width="100"><template #default>-</template></el-table-column>
        <el-table-column label="建议区间" width="120"><template #default>-</template></el-table-column>
        <el-table-column label="授予ADS" width="140">
          <template #default="{ row }">
            <el-input-number
              v-model="row.granted_ads"
              :min="0"
              :step="100"
              size="small"
              :disabled="!editable"
              @change="markDirty(row)"
            />
          </template>
        </el-table-column>
      </el-table-column>

      <!-- 分配后待归属 -->
      <el-table-column label="分配后待归属" align="center">
        <el-table-column label="Y+1 待归属ADS" width="120"><template #default>-</template></el-table-column>
        <el-table-column label="Y+2 待归属ADS" width="120"><template #default>-</template></el-table-column>
      </el-table-column>

      <!-- Y+1 年薪酬总包 -->
      <el-table-column label="Y+1 年薪酬总包" align="center">
        <el-table-column label="现金·固薪" width="110"><template #default>-</template></el-table-column>
        <el-table-column label="现金·奖金" width="110"><template #default>-</template></el-table-column>
        <el-table-column label="小计" width="100"><template #default>-</template></el-table-column>
        <el-table-column label="长期激励·Y+1 待归属" width="160"><template #default>-</template></el-table-column>
        <el-table-column label="合计" width="110"><template #default>-</template></el-table-column>
        <el-table-column label="长期激励占比" width="120"><template #default>-</template></el-table-column>
        <el-table-column label="RSU占比指引" width="120"><template #default>-</template></el-table-column>
      </el-table-column>

      <!-- Y 年薪酬总包 -->
      <el-table-column label="Y 年薪酬总包" align="center">
        <el-table-column label="现金·固薪" width="120">
          <template #default="{ row }">{{ fmtMoney(row.annual_base) }}</template>
        </el-table-column>
        <el-table-column label="现金·奖金" width="110"><template #default>-</template></el-table-column>
        <el-table-column label="小计" width="120">
          <template #default="{ row }">{{ fmtMoney(row.annual_base) }}</template>
        </el-table-column>
        <el-table-column label="长期激励·Y 待归属" width="150">
          <template #default="{ row }">{{ fmtMoney(row.annual_rsu_value) }}</template>
        </el-table-column>
        <el-table-column label="合计" width="120">
          <template #default="{ row }">{{ fmtMoney(row.total_comp) }}</template>
        </el-table-column>
        <el-table-column label="长期激励占比" width="120">
          <template #default="{ row }">{{ fmtLtiRatio(row) }}</template>
        </el-table-column>
        <el-table-column label="RSU占比指引" width="120"><template #default>-</template></el-table-column>
      </el-table-column>

      <!-- Y-1 年薪酬总包 -->
      <el-table-column label="Y-1 年薪酬总包" align="center">
        <el-table-column label="年现金薪酬" width="120"><template #default>-</template></el-table-column>
        <el-table-column label="长期激励·Y-1 已归属" width="160"><template #default>-</template></el-table-column>
        <el-table-column label="合计" width="110"><template #default>-</template></el-table-column>
      </el-table-column>

      <!-- 全面薪酬涨幅 -->
      <el-table-column label="全面薪酬涨幅" align="center">
        <el-table-column label="Y+1 vs Y 长期激励Δ%" width="160"><template #default>-</template></el-table-column>
        <el-table-column label="Y+1 vs Y 总包Δ%" width="140"><template #default>-</template></el-table-column>
        <el-table-column label="Y vs Y-1 现金Δ%" width="140"><template #default>-</template></el-table-column>
        <el-table-column label="Y vs Y-1 长期激励Δ%" width="160"><template #default>-</template></el-table-column>
        <el-table-column label="Y vs Y-1 总包Δ%" width="140"><template #default>-</template></el-table-column>
      </el-table-column>
    </el-table>

    <el-space style="margin-top: 16px">
      <el-button @click="save" :disabled="!editable || !dirty.size">
        保存（{{ dirty.size }}）
      </el-button>
      <el-button
        type="primary"
        @click="submit"
        :disabled="cycle?.status !== 'ALLOCATING' && cycle?.status !== 'DRAFT'"
      >
        提交审批
      </el-button>
    </el-space>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue"
import api from "@/api/client"

const rows = ref<any[]>([])
const cycle = ref<any>(null)
const dirty = ref(new Set<number>())
const editable = computed(() => ["DRAFT", "ALLOCATING"].includes(cycle.value?.status))

async function load() {
  const r = await api.get("/reward-cycle/")
  const c = r.data[0] || r.data.results?.[0]
  if (!c) return
  const d = await api.get(`/reward-cycle/${c.id}/allocation/`)
  cycle.value = d.data.cycle
  rows.value = d.data.rows
}
function markDirty(row: any) {
  dirty.value.add(row.employee_id)
}
function dash(v: any) {
  return v == null || v === "" ? "-" : v
}
function fmtPct(v: any) {
  if (v == null || v === "") return "-"
  return (Number(v) * 100).toFixed(2) + "%"
}
function fmtMoney(v: any) {
  if (v == null || v === "") return "-"
  return Number(v).toLocaleString("zh-CN", { maximumFractionDigits: 2 })
}
function statusLabel(s: string) {
  const m: Record<string, string> = {
    DRAFT: "草稿",
    ALLOCATING: "分配中",
    APPROVING: "审批中",
    APPROVED_PENDING_EXECUTE: "待执行",
    EXECUTED: "已执行",
    REJECTED: "已驳回",
  }
  return m[s] || s
}
function category1Label(s: string) {
  if (!s) return "-"
  return s === "MANAGEMENT" ? "管理干部" : s === "STAFF" ? "员工" : s
}
function promotionLabel(s: string) {
  if (!s) return "-"
  const m: Record<string, string> = { VERTICAL: "纵向晋升", LATERAL: "横向调动", NONE: "未晋升" }
  return m[s] || s
}
function computeFinal(row: any) {
  const s = Number(row.annual_suggested_pct || 0)
  const m = Number(row.annual_manager_delta_pct || 0)
  return s + m
}
function computeTotalPct(row: any) {
  return Number(row.promotion_adjustment_pct || 0) + computeFinal(row)
}
function computeNewSalary(row: any) {
  const cur = Number(row.current_monthly_salary || 0)
  return cur * (1 + computeTotalPct(row))
}
function fmtLtiRatio(row: any) {
  const total = Number(row.total_comp || 0)
  const rsu = Number(row.annual_rsu_value || 0)
  if (!total) return "-"
  return ((rsu / total) * 100).toFixed(2) + "%"
}
async function save() {
  const items = rows.value
    .filter((r) => dirty.value.has(r.employee_id))
    .map((r) => ({
      employee_id: r.employee_id,
      annual_manager_delta_pct: r.annual_manager_delta_pct,
      granted_ads: r.granted_ads,
    }))
  await api.patch(`/reward-cycle/${cycle.value.id}/proposals/`, { items })
  dirty.value.clear()
  await load()
}
async function submit() {
  await api.post(`/reward-cycle/${cycle.value.id}/submit/`)
  await load()
}
onMounted(load)
</script>
