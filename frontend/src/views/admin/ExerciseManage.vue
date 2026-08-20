<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createExercise, deleteExercise, listCourses, listExercises, updateExercise } from '@/api/admin'
import { SUBJECTS } from '@/constants'

const items = ref([])
const total = ref(0)
const courses = ref([])
const loading = ref(false)
const subjectOptions = ref(SUBJECTS)
const query = reactive({ page: 1, size: 20, course_id: null, difficulty: '', knowledge_point: '', subject: '' })
const dialog = ref(false)
const editing = ref(false)
const formRef = ref()

const form = reactive({ id: null, course_id: null, subject: '', content: '', options_text: '', answer: '', analysis: '', difficulty: 'medium', knowledge_points_text: '' })
const difficultyMap = { easy: '基础', medium: '提高', hard: '拓展' }
const difficultyType = { easy: 'success', medium: 'warning', hard: 'danger' }

function parseOptions(text) { return (text || '').split('\n').map((l) => l.trim()).filter(Boolean).map((line, i) => { const idx = line.indexOf('.'); const key = idx > 0 ? line.slice(0, idx).trim().toUpperCase() : String.fromCharCode(65 + i); return { key, text: idx > 0 ? line.slice(idx + 1).trim() : line } }) }
function optionsToText(options) { return (options || []).map((o) => `${o.key}. ${o.text}`).join('\n') }

async function load() {
  loading.value = true
  try {
    const data = await listExercises(query)
    items.value = data.items
    total.value = data.total
  } finally { loading.value = false }
}
function openCreate() {
  editing.value = false
  Object.assign(form, { id: null, course_id: null, subject: '', content: '', options_text: '', answer: '', analysis: '', difficulty: 'medium', knowledge_points_text: '' })
  dialog.value = true
}
function openEdit(row) {
  editing.value = true
  Object.assign(form, {
    id: row.id, course_id: row.course_id, subject: row.subject || '', 
    content: row.content, options_text: optionsToText(row.options), answer: row.answer || '',
    analysis: row.analysis || '', difficulty: row.difficulty, knowledge_points_text: (row.knowledge_points || []).join(',')
  })
  dialog.value = true
}
async function save() {
  await formRef.value.validate()
  const payload = { subject: form.subject || null, type: 'single', content: form.content, options: parseOptions(form.options_text), answer: form.answer, analysis: form.analysis, difficulty: form.difficulty, knowledge_points: (form.knowledge_points_text || '').split(',').map((s) => s.trim()).filter(Boolean) }
  if (editing.value) { await updateExercise(form.id, payload); ElMessage.success('更新成功') } else { await createExercise(payload); ElMessage.success('创建成功') }
  dialog.value = false
  await load()
}
async function remove(row) {
  await ElMessageBox.confirm('确定删除该题目吗？', '提示', { type: 'warning' })
  await deleteExercise(row.id)
  ElMessage.success('删除成功')
  await load()
}
const rules = { content: [{ required: true, message: '请输入题目内容', trigger: 'blur' }] }
onMounted(async () => { courses.value = await listCourses(); await load() })
</script>

<template>
  <div class="page-card">
    <div class="toolbar">
      <el-select v-model="query.subject" clearable placeholder="科目" style="width: 120px" @change="query.page=1; load()"><el-option v-for="s in subjectOptions" :key="s" :label="s" :value="s" /></el-select>
      <el-select v-model="query.course_id" clearable placeholder="课程" style="width: 180px" @change="query.page=1; load()"><el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" /></el-select>
      <el-input v-model="query.knowledge_point" placeholder="知识点" clearable style="width: 140px" @keyup.enter="query.page=1; load()" />
      <el-select v-model="query.difficulty" clearable placeholder="难度" style="width: 110px" @change="query.page=1; load()"><el-option label="基础" value="easy" /><el-option label="提高" value="medium" /><el-option label="拓展" value="hard" /></el-select>
      <el-button type="primary" @click="query.page=1; load()">查询</el-button>
      <el-button type="success" @click="openCreate">新增题目</el-button>
    </div>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="content" label="题目" min-width="240" show-overflow-tooltip />
      <el-table-column prop="subject" label="科目" width="100">
        <template #default="{ row }">{{ row.subject || '-' }}</template>
      </el-table-column>
      <el-table-column label="难度" width="90"><template #default="{ row }"><el-tag :type="difficultyType[row.difficulty]" size="small">{{ difficultyMap[row.difficulty] }}</el-tag></template></el-table-column>
      <el-table-column label="知识点" min-width="150"><template #default="{ row }"><el-tag v-for="kp in row.knowledge_points || []" :key="kp" size="small" style="margin-right:4px">{{ kp }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="140"><template #default="{ row }"><el-button type="info" link @click="openEdit(row)">编辑</el-button><el-button type="danger" link @click="remove(row)">删除</el-button></template></el-table-column>
    </el-table>

    <el-pagination style="margin-top:16px; justify-content:flex-end" layout="total, prev, pager, next" :total="total" :page-size="query.size" v-model:current-page="query.page" @current-change="load" />

    <el-dialog v-model="dialog" :title="editing ? '编辑题目' : '新增题目'" width="640px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="科目">
          <el-select v-model="form.subject" clearable placeholder="选择科目" style="width:100%">
            <el-option v-for="s in subjectOptions" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="题目" prop="content"><el-input v-model="form.content" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="选项"><el-input v-model="form.options_text" type="textarea" :rows="4" placeholder="每行一个选项" /></el-form-item>
        <el-form-item label="答案"><el-input v-model="form.answer" /></el-form-item>
        <el-form-item label="解析"><el-input v-model="form.analysis" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="难度"><el-radio-group v-model="form.difficulty"><el-radio-button value="easy">基础</el-radio-button><el-radio-button value="medium">提高</el-radio-button><el-radio-button value="hard">拓展</el-radio-button></el-radio-group></el-form-item>
        <el-form-item label="知识点"><el-input v-model="form.knowledge_points_text"  /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>

  </div>
</template>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
</style>
