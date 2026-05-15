<template>
  <div class="hr-page">
    <PageHeader
      title="员工类别分配"
      subtitle="把员工赋类别到指定方案中；同一方案下每位员工只能落在一个类别"
    />

    <Toolbar>
      <span class="hr-text-secondary">方案</span>
      <el-select v-model="schemeId" style="width: 280px" @change="onSchemeChange">
        <el-option
          v-for="s in schemes"
          :key="s.id"
          :label="`${s.code} - ${s.name}`"
          :value="s.id"
        />
      </el-select>
      <span class="hr-text-secondary">部门</span>
      <el-select
        v-model="deptFilter"
        clearable
        placeholder="全部"
        style="width: 200px"
        @change="loadAssignments"
      >
        <el-option v-for="d in deptOptions" :key="d" :label="d" :value="d" />
      </el-select>
      <span class="hr-text-secondary">类别</span>
      <el-select
        v-model="catFilter"
        clearable
        placeholder="全部"
        style="width: 180px"
        @change="loadAssignments"
      >
        <el-option
          v-for="c in cats"
          :key="c.id"
          :label="`${c.code} - ${c.name}`"
          :value="c.id"
        />
      </el-select>
      <el-button type="primary" :disabled="!schemeId" @click="bulkDialog = true">
        批量按个人标签赋类别
      </el-button>
      <el-button :disabled="!schemeId" @click="loadMissing">
        未赋类别员工 ({{ missing.length }})
      </el-button>
    </Toolbar>

    <el-table :data="assignments" v-loading="loading" border>
      <el-table-column label="工号" prop="employee_no" width="140" />
      <el-table-column label="姓名" prop="employee_name" width="140" />
      <el-table-column label="部门" prop="dept_name" min-width="160" />
      <el-table-column label="当前类别" min-width="200">
        <template #default="{ row }">
          <el-select
            v-model="row.category"
            size="small"
            style="width: 220px"
            @change="(v: number) => updateAssignment(row, v)"
          >
            <el-option
              v-for="c in cats"
              :key="c.id"
              :label="`${c.code} - ${c.name}`"
              :value="c.id"
            />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="200">
        <template #default="{ row }">{{ row.updated_at?.slice(0, 19).replace("T", " ") }}</template>
      </el-table-column>
    </el-table>

    <h3 v-if="missing.length" class="hr-section-title" style="margin-top: 24px">
      未赋类别员工 ({{ missing.length }})
    </h3>
    <el-table v-if="missing.length" :data="missing" border size="small">
      <el-table-column label="工号" prop="employee_no" width="140" />
      <el-table-column label="姓名" prop="name_cn" width="140" />
      <el-table-column label="部门" prop="dept_name" min-width="160" />
      <el-table-column label="历史类别" prop="employee_category_1" width="140" />
      <el-table-column label="赋类别" min-width="220">
        <template #default="{ row }">
          <el-select
            v-model="missingPick[row.id]"
            placeholder="选类别"
            size="small"
            style="width: 200px"
          >
            <el-option
              v-for="c in cats"
              :key="c.id"
              :label="`${c.code} - ${c.name}`"
              :value="c.id"
            />
          </el-select>
          <el-button
            size="small"
            type="primary"
            link
            :disabled="!missingPick[row.id]"
            @click="assignMissing(row)"
          >
            保存
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="bulkDialog" title="批量按个人标签赋类别" width="720" @open="onBulkOpen">
      <p class="hr-text-secondary" style="margin-top: 0">
        类别是个人标签：按 <b>职级 / 岗位族 / 是否有下属 / 岗位关键词</b> 多条件筛选员工，
        命中的员工统一赋到目标类别；同一员工后改类别以最新一次为准。
      </p>
      <el-form label-width="120px" :model="bulk">
        <el-form-item label="目标类别" required>
          <el-select v-model="bulk.category_code" style="width: 280px">
            <el-option
              v-for="c in cats"
              :key="c.code"
              :label="`${c.code} - ${c.name}`"
              :value="c.code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="职级 (多选)">
          <el-select
            v-model="bulk.filters.job_levels"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="如 P5 / P6 / M1"
            style="width: 100%"
          >
            <el-option v-for="lv in facets.job_levels" :key="lv" :label="lv" :value="lv" />
          </el-select>
        </el-form-item>
        <el-form-item label="岗位族 (多选)" v-if="facets.job_families.length">
          <el-select
            v-model="bulk.filters.job_families"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="可选"
            style="width: 100%"
          >
            <el-option v-for="fa in facets.job_families" :key="fa" :label="fa" :value="fa" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门 (多选)">
          <el-select
            v-model="bulk.filters.depts"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="可选, 不选则全部"
            style="width: 100%"
          >
            <el-option v-for="d in facets.depts" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="是否有直接下属">
          <el-radio-group v-model="bulk.filters.has_reports">
            <el-radio :value="null">不限</el-radio>
            <el-radio :value="true">有 (管理职务)</el-radio>
            <el-radio :value="false">无</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="岗位关键词">
          <el-input
            v-model="bulk.filters.position_contains"
            placeholder="如 Manager / Director, 子串匹配"
          />
        </el-form-item>
      </el-form>

      <div style="margin: 8px 0 12px">
        <el-button @click="previewBulk" :loading="bulkPreviewing">预览命中</el-button>
        <span style="margin-left: 12px" :style="{ color: bulkMatched.length ? '#67c23a' : '#909399' }">
          命中 {{ bulkMatched.length }} 名员工
        </span>
      </div>

      <el-table v-if="bulkMatched.length" :data="bulkMatched" border size="small" max-height="280">
        <el-table-column label="工号" prop="employee_no" width="100" />
        <el-table-column label="姓名" prop="name_cn" width="100" />
        <el-table-column label="部门" prop="dept_name" min-width="120" />
        <el-table-column label="职级" prop="job_level_current" width="80" />
        <el-table-column label="岗位" prop="position_current" min-width="160" />
      </el-table>

      <template #footer>
        <el-button @click="bulkDialog = false">取消</el-button>
        <el-button
          type="primary"
          :loading="bulkSaving"
          :disabled="!bulkMatched.length || !bulk.category_code"
          @click="submitBulk"
        >
          确认赋类别 ({{ bulkMatched.length }})
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import { ElMessage } from "element-plus"
import api from "@/api/client"
import PageHeader from "@/components/PageHeader.vue"
import Toolbar from "@/components/Toolbar.vue"

type Cat = { id: number; code: string; name: string; sort_order: number; scheme: number }
type Scheme = { id: number; code: string; name: string; categories: Cat[] }
type Assignment = {
  id: number
  employee: number
  scheme: number
  category: number
  employee_no: string
  employee_name: string
  dept_name: string
  updated_at: string
}
type Missing = {
  id: number
  employee_no: string
  name_cn: string
  dept_name: string
  employee_category_1: string
}

const schemes = ref<Scheme[]>([])
const schemeId = ref<number | null>(null)
const assignments = ref<Assignment[]>([])
const missing = ref<Missing[]>([])
const missingPick = ref<Record<number, number>>({})
const loading = ref(false)
const deptFilter = ref<string>("")
const catFilter = ref<number | null>(null)

const bulkDialog = ref(false)
const bulkSaving = ref(false)
const bulkPreviewing = ref(false)
type BulkFilters = {
  job_levels: string[]
  job_families: string[]
  depts: string[]
  position_contains: string
  has_reports: boolean | null
}
const bulk = ref<{ category_code: string; filters: BulkFilters }>({
  category_code: "",
  filters: {
    job_levels: [], job_families: [], depts: [],
    position_contains: "", has_reports: null,
  },
})
const bulkMatched = ref<any[]>([])
const facets = ref<{ job_levels: string[]; job_families: string[]; depts: string[] }>({
  job_levels: [], job_families: [], depts: [],
})

const cats = computed<Cat[]>(() => {
  const s = schemes.value.find((x) => x.id === schemeId.value)
  return s ? s.categories : []
})

const deptOptions = computed(() => {
  const seen = new Set<string>()
  for (const a of assignments.value) if (a.dept_name) seen.add(a.dept_name)
  return Array.from(seen).sort()
})

async function loadSchemes() {
  const r = await api.get("/admin/category-schemes/")
  schemes.value = Array.isArray(r.data) ? r.data : r.data.results || []
  if (schemes.value.length && schemeId.value == null) schemeId.value = schemes.value[0].id
}

async function onSchemeChange() {
  catFilter.value = null
  await loadAssignments()
  missing.value = []
}

async function loadAssignments() {
  if (!schemeId.value) return
  loading.value = true
  try {
    const params: any = { scheme: schemeId.value }
    if (deptFilter.value) params.dept = deptFilter.value
    if (catFilter.value) params.category = catFilter.value
    const r = await api.get("/admin/employee-category-assignments/", { params })
    assignments.value = Array.isArray(r.data) ? r.data : r.data.results || []
  } finally {
    loading.value = false
  }
}

async function loadMissing() {
  if (!schemeId.value) return
  const r = await api.get("/admin/employee-category-assignments/missing/", {
    params: { scheme: schemeId.value },
  })
  missing.value = r.data || []
  missingPick.value = {}
}

async function updateAssignment(a: Assignment, newCatId: number) {
  try {
    await api.patch(`/admin/employee-category-assignments/${a.id}/`, { category: newCatId })
    ElMessage.success(`${a.employee_name} 已更新`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "更新失败")
    await loadAssignments()
  }
}

async function assignMissing(row: Missing) {
  const catId = missingPick.value[row.id]
  if (!catId || !schemeId.value) return
  try {
    await api.post("/admin/employee-category-assignments/", {
      employee: row.id,
      scheme: schemeId.value,
      category: catId,
    })
    ElMessage.success(`${row.name_cn} 已赋类别`)
    missing.value = missing.value.filter((x) => x.id !== row.id)
    await loadAssignments()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败")
  }
}

async function onBulkOpen() {
  if (!schemeId.value) return
  bulk.value = {
    category_code: "",
    filters: {
      job_levels: [], job_families: [], depts: [],
      position_contains: "", has_reports: null,
    },
  }
  bulkMatched.value = []
  try {
    const r = await api.get(
      `/admin/category-schemes/${schemeId.value}/filter-facets/`,
    )
    facets.value = r.data
  } catch {
    // facets 加载失败不阻断
  }
}

async function previewBulk() {
  if (!schemeId.value || !bulk.value.category_code) {
    ElMessage.warning("请先选目标类别")
    return
  }
  bulkPreviewing.value = true
  try {
    const r = await api.post(
      `/admin/category-schemes/${schemeId.value}/bulk-assign/`,
      { ...bulk.value, dry_run: true },
    )
    bulkMatched.value = r.data.matched || []
    if (!bulkMatched.value.length) ElMessage.info("没有命中员工")
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "预览失败")
  } finally {
    bulkPreviewing.value = false
  }
}

async function submitBulk() {
  if (!schemeId.value || !bulk.value.category_code) return
  bulkSaving.value = true
  try {
    const r = await api.post(
      `/admin/category-schemes/${schemeId.value}/bulk-assign/`,
      { ...bulk.value, dry_run: false },
    )
    ElMessage.success(`已更新 ${r.data.updated} 名员工`)
    bulkDialog.value = false
    await loadAssignments()
    if (missing.value.length) await loadMissing()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "批量赋类别失败")
  } finally {
    bulkSaving.value = false
  }
}

onMounted(async () => {
  await loadSchemes()
  await loadAssignments()
})
</script>
