<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { addClassStudents, classStudents, createClass, deleteClass, listClasses, listStudents, listTeachers, removeClassStudent, updateClass } from '@/api/admin'

const classes = ref([])
const teachers = ref([])
const allStudents = ref([])
const loading = ref(false)
const keyword = ref('')

const dialog = ref(false)
const editing = ref(false)
const formRef = ref()
const form = reactive({ id: null, name: '', class_no: '', grade: '', teacher_id: null, description: '' })

const detailDialog = ref(false)
const detail = ref(null)
const detailStudents = ref([])
const selectedAdd = ref([])

async function load() {
  loading.value = true
  try {
    classes.value = await listClasses({ keyword: keyword.value || undefined })
  } finally { loading.value = false }
}

// 输入班级名称时自动识别年级（如“九年级1班”-> 九年级）
const gradeKeywords = ['一年级','二年级','三年级','四年级','五年级','六年级','七年级','八年级','九年级','初一','初二','初三','高一','高二','高三']
function detectGrade(name) {
  return gradeKeywords.find((k) => (name || '').startsWith(k)) || ''
}
watch(() => form.name, (val) => {
  const g = detectGrade(val)
  if (g) form.grade = g
})

function openCreate() {
  editing.value = false
  Object.assign(form, { id: null, name: '', class_no: '', grade: '', teacher_id: null, description: '' })
  dialog.value = true
}
function openEdit(row) {
  editing.value = true
  Object.assign(form, { id: row.id, name: row.name, class_no: row.class_no || '', grade: row.grade || '', teacher_id: row.teacher_id, description: row.description || '' })
  dialog.value = true
}

async function save() {
  await formRef.value.validate()
  const payload = { name: form.name, class_no: form.class_no, grade: form.grade, teacher_id: form.teacher_id, description: form.description }
  if (editing.value) { await updateClass(form.id, payload); ElMessage.success('更新成功') }
  else { await createClass(payload); ElMessage.success('创建成功') }
  dialog.value = false
  await load()
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除班级「${row.name}」吗？`, '提示', { type: 'warning' })
  await deleteClass(row.id)
  ElMessage.success('删除成功')
  await load()
}

async function openDetail(row) {
  detail.value = row
  detailStudents.value = await classStudents(row.id)
  detailDialog.value = true
}

// 已是其它班级班主任的老师（一位老师只能担任一个班级的班主任）
const usedTeacherIds = computed(() => {
  const used = new Set()
  for (const c of classes.value) {
    if (editing.value && c.id === form.id) continue   // 当前编辑班级的班主任不算占用
    if (c.teacher_id) used.add(c.teacher_id)
  }
  return used
})

// 可选学生：不在任何班级，且年级与当前班级一致
const availableStudents = computed(() => {
  if (!detail.value) return []
  const grade = detail.value.grade
  return allStudents.value.filter((s) => {
    if ((s.class_ids || []).length) return false
    if (!grade) return true
    return s.grade === grade
  })
})

async function refreshAll() {
  await load()                              // 刷新班级列表（学生数）
  allStudents.value = await listStudents()  // 刷新全部学生（班级归属），使加入/移出后下拉立即可用
  detailStudents.value = await classStudents(detail.value.id)
}

async function doAddStudents() {
  if (!selectedAdd.value.length) { ElMessage.warning('请选择学生'); return }
  await addClassStudents(detail.value.id, selectedAdd.value)
  ElMessage.success('已添加')
  selectedAdd.value = []
  await refreshAll()
}

async function doRemoveStudent(sid) {
  await ElMessageBox.confirm('确定将该学生移出班级吗？（不影响学生账号）', '提示', { type: 'warning' })
  await removeClassStudent(detail.value.id, sid)
  ElMessage.success('已移出班级')
  await refreshAll()
}

const rules = { name: [{ required: true, message: '请输入班级名称', trigger: 'blur' }], teacher_id: [{ required: true, message: '请选择教师', trigger: 'change' }] }

onMounted(async () => {
  teachers.value = await listTeachers()
  allStudents.value = await listStudents()
  await load()
})
</script>

<template>
  <div class="page-card">
    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :span="8"><div class="stat-card" style="background: linear-gradient(135deg,#a67b5b,#2f6fd0)"><span>班级总数</span><span class="num">{{ classes.length }}</span></div></el-col>
      <el-col :span="8"><div class="stat-card" style="background: linear-gradient(135deg,#c4a484,#a67b5b)"><span>班级学生总数</span><span class="num">{{ classes.reduce((s, c) => s + (c.student_count || 0), 0) }}</span></div></el-col>
      <el-col :span="8"><div class="stat-card" style="background: linear-gradient(135deg,#8a6247,#6e4f38)"><span>任课教师</span><span class="num">{{ teachers.length }}</span></div></el-col>
    </el-row>
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索" clearable style="width: 220px" @keyup.enter="load" />
      <el-button type="primary" @click="load">查询</el-button>
      <el-button type="success" @click="openCreate">创建新班级</el-button>
    </div>

    <el-table :data="classes" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="班级名称" width="180" />
      <el-table-column prop="class_no" label="班级编号" width="120" />
      <el-table-column prop="grade" label="年级" width="110" />
      <el-table-column label="班主任/任课教师" min-width="140">
        <template #default="{ row }">
          {{ teachers.find((t) => t.user_id === row.teacher_id)?.full_name || row.teacher_id }}
        </template>
      </el-table-column>
      <el-table-column prop="student_count" label="学生数" width="90" />
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button type="primary" link @click="openDetail(row)">详情/成员</el-button>
          <el-button type="primary" link @click="openEdit(row)">编辑</el-button>
          <el-button type="danger" link @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!classes.length" description="暂无班级" />

    <el-dialog v-model="dialog" :title="editing ? '编辑班级' : '创建班级'" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="班级名称" prop="name"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="班级编号"><el-input v-model="form.class_no" /></el-form-item>
        <el-form-item label="年级"><el-input v-model="form.grade" /></el-form-item>
        <el-form-item label="任课教师" prop="teacher_id">
          <el-select v-model="form.teacher_id" filterable placeholder="选择任课教师" style="width:100%">
            <el-option
              v-for="t in teachers"
              :key="t.user_id"
              :label="`${t.full_name || t.username}${usedTeacherIds.has(t.user_id) ? '（已是其他班班主任）' : ''}`"
              :value="t.user_id"
              :disabled="usedTeacherIds.has(t.user_id)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="detailDialog" :title="`${detail?.name || ''} - 班级详情`" width="640px">
      <h4 style="margin-bottom: 8px">班级学生列表（{{ detailStudents.length }}）</h4>
      <el-table :data="detailStudents" size="small" stripe max-height="300">
        <el-table-column prop="full_name" label="姓名" width="110" />
        <el-table-column prop="student_no" label="学号" width="110" />
        <el-table-column prop="username" label="用户名" width="110" />
        <el-table-column prop="grade" label="年级" width="90" />
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button type="danger" link size="small" @click="doRemoveStudent(row.student_id)">移出</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 12px; display:flex; gap:8px">
        <el-select v-model="selectedAdd" multiple filterable placeholder="选择学生" style="flex:1">
          <el-option
            v-for="s in availableStudents"
            :key="s.id"
            :label="`${s.full_name}（${s.student_no}）${s.grade || '无年级'}`"
            :value="s.id"
          />
        </el-select>
        <el-button type="primary" @click="doAddStudents">加入班级</el-button>
      </div>
      <template #footer><el-button @click="detailDialog=false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 16px; }
.gray { color: #909399; font-size: 12px; }
</style>