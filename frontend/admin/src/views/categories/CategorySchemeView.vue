<template>
  <div class="hr-page">
    <PageHeader
      title="员工类别方案"
      subtitle="按年度灵活定义员工类别（如 干部/员工 / 基干/中干/高干 等），各方案独立管理"
    />

    <Toolbar>
      <el-button type="primary" @click="openSchemeDialog()">+ 新建方案</el-button>
    </Toolbar>

    <el-table :data="schemes" v-loading="loading" border>
      <el-table-column label="方案码" prop="code" width="200" />
      <el-table-column label="名称" prop="name" min-width="200" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="row.status === 'ACTIVE' ? 'success' : 'info'">
            {{ row.status === "ACTIVE" ? "启用" : "归档" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="类别数" width="100" align="right">
        <template #default="{ row }">{{ (row.categories || []).length }}</template>
      </el-table-column>
      <el-table-column label="已赋类别人数" width="120" align="right">
        <template #default="{ row }">{{ row.assignment_count }}</template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="selectScheme(row)">管理类别</el-button>
          <el-button size="small" link @click="openSchemeDialog(row)">编辑</el-button>
          <el-button
            size="small"
            link
            type="danger"
            :disabled="row.assignment_count > 0"
            @click="removeScheme(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="activeScheme" class="hr-card" style="margin-top: 24px">
      <h3 class="hr-section-title">类别配置 - {{ activeScheme.code }} / {{ activeScheme.name }}</h3>
      <el-table :data="categories" border size="small">
        <el-table-column label="类别码" prop="code" width="180" />
        <el-table-column label="名称" prop="name" min-width="200" />
        <el-table-column label="排序" prop="sort_order" width="100" align="right" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" link @click="openCatDialog(row)">编辑</el-button>
            <el-button size="small" link type="danger" @click="removeCat(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 12px">
        <el-button type="primary" @click="openCatDialog()">+ 新增类别</el-button>
      </div>
    </div>

    <el-dialog v-model="schemeDialog" :title="editingScheme?.id ? '编辑方案' : '新建方案'" width="520">
      <el-form label-width="92px" :model="schemeForm">
        <el-form-item label="方案码" required>
          <el-input v-model="schemeForm.code" placeholder="如 2027-scheme" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="schemeForm.name" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="schemeForm.status">
            <el-option label="启用" value="ACTIVE" />
            <el-option label="归档" value="ARCHIVED" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="schemeForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="schemeDialog = false">取消</el-button>
        <el-button type="primary" @click="saveScheme" :loading="savingScheme">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="catDialog" :title="editingCat?.id ? '编辑类别' : '新增类别'" width="480">
      <el-form label-width="80px" :model="catForm">
        <el-form-item label="类别码" required>
          <el-input v-model="catForm.code" placeholder="如 MGMT / SENIOR / JUNIOR" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="catForm.name" placeholder="如 管理干部 / 高级员工" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="catForm.sort_order" :min="0" :step="1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="catDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCat" :loading="savingCat">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import api from "@/api/client"
import PageHeader from "@/components/PageHeader.vue"
import Toolbar from "@/components/Toolbar.vue"

type Cat = { id?: number; scheme?: number; code: string; name: string; sort_order: number }
type Scheme = {
  id: number
  code: string
  name: string
  status: string
  description?: string
  categories?: Cat[]
  assignment_count: number
}

const schemes = ref<Scheme[]>([])
const loading = ref(false)
const activeScheme = ref<Scheme | null>(null)
const categories = ref<Cat[]>([])

const schemeDialog = ref(false)
const editingScheme = ref<Scheme | null>(null)
const schemeForm = ref({ code: "", name: "", status: "ACTIVE", description: "" })
const savingScheme = ref(false)

const catDialog = ref(false)
const editingCat = ref<Cat | null>(null)
const catForm = ref<Cat>({ code: "", name: "", sort_order: 0 })
const savingCat = ref(false)

async function loadSchemes() {
  loading.value = true
  try {
    const r = await api.get("/admin/category-schemes/")
    schemes.value = Array.isArray(r.data) ? r.data : r.data.results || []
    if (activeScheme.value) {
      const refreshed = schemes.value.find((s) => s.id === activeScheme.value!.id)
      if (refreshed) {
        activeScheme.value = refreshed
        categories.value = (refreshed.categories || []).slice().sort((a, b) => a.sort_order - b.sort_order)
      }
    }
  } finally {
    loading.value = false
  }
}

function selectScheme(s: Scheme) {
  activeScheme.value = s
  categories.value = (s.categories || []).slice().sort((a, b) => a.sort_order - b.sort_order)
}

function openSchemeDialog(s?: Scheme) {
  editingScheme.value = s || null
  schemeForm.value = s
    ? { code: s.code, name: s.name, status: s.status, description: s.description || "" }
    : { code: "", name: "", status: "ACTIVE", description: "" }
  schemeDialog.value = true
}

async function saveScheme() {
  if (!schemeForm.value.code || !schemeForm.value.name) {
    ElMessage.warning("方案码和名称必填")
    return
  }
  savingScheme.value = true
  try {
    if (editingScheme.value?.id) {
      await api.put(`/admin/category-schemes/${editingScheme.value.id}/`, schemeForm.value)
    } else {
      await api.post("/admin/category-schemes/", schemeForm.value)
    }
    ElMessage.success("已保存")
    schemeDialog.value = false
    await loadSchemes()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.response?.data?.code?.[0] || "保存失败")
  } finally {
    savingScheme.value = false
  }
}

async function removeScheme(s: Scheme) {
  try {
    await ElMessageBox.confirm(`确定删除方案 ${s.code}?`, "提示", { type: "warning" })
  } catch {
    return
  }
  try {
    await api.delete(`/admin/category-schemes/${s.id}/`)
    if (activeScheme.value?.id === s.id) activeScheme.value = null
    await loadSchemes()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "删除失败")
  }
}

function openCatDialog(c?: Cat) {
  if (!activeScheme.value) {
    ElMessage.warning("请先在上方选择方案")
    return
  }
  editingCat.value = c || null
  catForm.value = c
    ? { ...c }
    : { code: "", name: "", sort_order: categories.value.length }
  catDialog.value = true
}

async function saveCat() {
  if (!activeScheme.value) return
  if (!catForm.value.code || !catForm.value.name) {
    ElMessage.warning("类别码和名称必填")
    return
  }
  savingCat.value = true
  try {
    const payload = { ...catForm.value, scheme: activeScheme.value.id }
    if (editingCat.value?.id) {
      await api.put(`/admin/employee-categories/${editingCat.value.id}/`, payload)
    } else {
      await api.post("/admin/employee-categories/", payload)
    }
    ElMessage.success("已保存")
    catDialog.value = false
    await loadSchemes()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || JSON.stringify(e?.response?.data) || "保存失败")
  } finally {
    savingCat.value = false
  }
}

async function removeCat(c: Cat) {
  try {
    await ElMessageBox.confirm(`确定删除类别 ${c.code}?`, "提示", { type: "warning" })
  } catch {
    return
  }
  try {
    await api.delete(`/admin/employee-categories/${c.id}/`)
    await loadSchemes()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "删除失败")
  }
}

onMounted(loadSchemes)
</script>
