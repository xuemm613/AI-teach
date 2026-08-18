<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listClasses, transferStudent } from '@/api/admin'
import { createUser, deleteUser, listUsers, updateUser } from '@/api/user'
import { SUBJECTS } from '@/constants'

const tab = ref('teacher')
const loading = ref(false)
const items = ref([])
const total = ref(0)
const query = reactive({ role: 'teacher', keyword: '', page: 1, size: 20 })
const classes = ref([])
const subjectOptions = ref(SUBJECTS)
const titleOptions = ref(['正高级教师', '高级教师', '一级教师', '二级教师', '三级教师'])
const departmentOptions = ref(SUBJECTS.map((s) => `${s}教研组`))

const dialog = ref(false)
const editing = ref(false)
const formRef = ref()
const form = reactive({
  id: null, username: '', password: '', role: 'teacher', full_name: '', email: '',
  employee_no: '', subject: '', title: '', department: '', grade: '', student_no: '',
  student_id: null, class_id: null, is_active: true, new_password: ''
})

const roleMap = { admin: '管理员', teacher: '教师', student: '学生' }
const roleType = { admin: 'danger', teacher: 'warning', student: 'success' }

async function load() {
  loading.value = true
  query.role = tab.value
  try {
    const data = await listUsers(query)
    items.value = data.items
    total.value = data.total
  } finally { loading.value = false }
}

function switchTab(t) { tab.value = t; query.page = 1; query.keyword = ''; load() }

function openCreate() {
  editing.value = false
  Object.assign(form, { id: null, username: '', password: '', role: tab.value, full_name: '', email: '', employee_no: '', subject: '', title: '', department: '', grade: '', student_no: '', student_id: null, class_id: null, is_active: true, new_password: '' })
  dialog.value = true
}
function openEdit(row) {
  editing.value = true
  Object.assign(form, {
    id: row.id, username: row.username, password: '', role: row.role, full_name: row.full_name || '',
    email: row.email || '', employee_no: row.employee_no || '', subject: (row.subjects || [])[0] || '', title: row.title || '',
    department: row.department || '', grade: row.grade || '',
    student_no: row.student_no || '', student_id: row.student_id || null, class_id: null, is_active: row.is_active, new_password: ''
  })
  dialog.value = true
}


async function save() {
  await formRef.value.validate()
  try {
    if (editing.value) {
      const payload = { role: form.role, is_active: form.is_active, full_name: form.full_name, email: form.email }
      if (form.new_password) payload.new_password = form.new_password
      if (form.role === 'teacher') {
        payload.subjects = form.subject ? [form.subject] : []
        payload.title = form.title
        payload.department = form.department
      } else {
        payload.grade = form.grade
      }
      await updateUser(form.id, payload)
      // 编辑学生时若选择了转入班级，则同步转班（仅同年级，保持年级一致）
      if (form.role === 'student' && form.class_id && form.student_id) {
        await transferStudent(form.student_id, { to_class_id: form.class_id })
      }
      ElMessage.success('更新成功')
    } else {
      const payload = {
        username: form.username,
        password: form.password,
        role: form.role,
        full_name: form.full_name || undefined,
        email: form.email || undefined,
        employee_no: form.employee_no || undefined,
        subjects: form.role === 'teacher' ? (form.subject ? [form.subject] : []) : undefined,
        title: form.title || undefined,
        department: form.department || undefined,
        grade: form.grade || undefined,
        student_no: form.student_no || undefined
      }
      const created = await createUser(payload)
      if (form.class_id && created?.student_id) {
        await transferStudent(created.student_id, { to_class_id: form.class_id })
      }
      ElMessage.success('创建成功')
    }
    dialog.value = false
    await load()   // 保存成功后刷新列表
  } catch (e) {
    // 失败原因已由接口层弹出提示，保持弹窗打开便于修改
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除用户「${row.username}」吗？`, '提示', { type: 'warning' })
  await deleteUser(row.id)
  ElMessage.success('删除成功')
  await load()
}

// 新建学生分配班级时，仅显示与所填年级一致的班级
const createClassOptions = computed(() => {
  if (!form.grade) return classes.value
  return classes.value.filter((c) => c.grade === form.grade)
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 64, message: '用户名至少 2 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' }
  ]
}

onMounted(async () => {
  classes.value = await listClasses()
  await load()
})
</script>

<template>
  <div class="page-card">
    <el-tabs v-model="tab" @tab-change="switchTab">
      <el-tab-pane label="教师管理" name="teacher" />
      <el-tab-pane label="学生管理" name="student" />
    </el-tabs>

    <div class="toolbar">
      <el-input v-model="query.keyword" placeholder="用户名 / 姓名" clearable style="width: 200px" @keyup.enter="query.page=1; load()" />
      <el-button type="primary" @click="query.page=1; load()">查询</el-button>
      <el-button type="success" @click="openCreate">新增{{ tab === 'teacher' ? '教师' : '学生' }}</el-button>
    </div>

    <el-table :data="items" v-loading="loading" stripe style="width: 100%">
      <template v-if="tab === 'teacher'">
        <el-table-column prop="employee_no" label="工号" width="140" />
      </template>
      <template v-else>
        <el-table-column prop="student_no" label="学号" width="140" />
      </template>
      <el-table-column prop="username" label="用户名" min-width="120" />
      <el-table-column prop="full_name" label="姓名" min-width="100" />
      <template v-if="tab === 'teacher'">
        <el-table-column prop="title" label="职称" width="100" />
        <el-table-column prop="department" label="教研组" min-width="120" />
      </template>
      <template v-else>
        <el-table-column prop="grade" label="年级" width="100" />
        <el-table-column label="班级" min-width="120">
          <template #default="{ row }">{{ row.class_name || '未分班' }}</template>
        </el-table-column>
      </template>
      <el-table-column label="状态" width="90">
        <template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '正常' : '禁用' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="openEdit(row)">编辑</el-button>
          <el-button type="danger" link size="small" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination style="margin-top:16px; justify-content:flex-end" layout="total, prev, pager, next" :total="total" :page-size="query.size" v-model:current-page="query.page" @current-change="load" />

    <el-dialog v-model="dialog" :title="editing ? '编辑' : '新增'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="用户名" prop="username"><el-input v-model="form.username" :disabled="editing" /></el-form-item>
        <el-form-item v-if="!editing" label="密码" prop="password"><el-input v-model="form.password" type="password" show-password /></el-form-item>
        <el-form-item v-if="editing" label="新密码"><el-input v-model="form.new_password" type="password" show-password  /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.full_name" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
        <template v-if="tab === 'teacher'">
          <el-form-item label="负责科目">
            <el-select v-model="form.subject" clearable filterable placeholder="选择科目" style="width:100%">
              <el-option v-for="s in subjectOptions" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="职称">
            <el-select v-model="form.title" clearable placeholder="选择职称" style="width:100%">
              <el-option v-for="t in titleOptions" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
          <el-form-item label="教研组">
            <el-select v-model="form.department" clearable placeholder="选择教研组" style="width:100%">
              <el-option v-for="d in departmentOptions" :key="d" :label="d" :value="d" />
            </el-select>
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="年级"><el-input v-model="form.grade" /></el-form-item>
          <el-form-item :label="editing ? '转入班级' : '分配班级'">
            <el-select v-model="form.class_id" clearable :placeholder="editing ? '选择转入班级' : '选择班级'" style="width:100%">
              <el-option v-for="c in createClassOptions" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
          </el-form-item>
        </template>
        <el-form-item v-if="editing" label="状态"><el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>

  </div>
</template>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 16px; }
.gray { color: #909399; font-size: 12px; }
</style>
