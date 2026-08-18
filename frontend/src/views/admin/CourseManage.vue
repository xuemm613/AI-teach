<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'
import { getTimetableOverview, listClasses, listTeachers } from '@/api/admin'
import { SUBJECTS } from '@/constants'

const classes = ref([])
const teachers = ref([])
const overview = ref([])        // 全部班级课表总览（用于选课时实时冲突检测）
const classId = ref(null)
const periods = 8   // 课表固定 8 节，不提供可变行数
const weekdays = 5
const cells = ref([])
const loading = ref(false)
const saving = ref(false)
const weekNames = ['周一', '周二', '周三', '周四', '周五']
const subjectOptions = ref(SUBJECTS)

// 科目配色（仅用于界面展示）
const subjectColors = {
  '语文': '#e6a23c', '数学': '#409eff', '英语': '#67c23a', '物理': '#909399',
  '化学': '#b88230', '生物': '#67c23a', '政治': '#f56c6c', '地理': '#36cfc9',
  '历史': '#722ed1', '体育': '#fa8c16', '音乐': '#eb2f96', '美术': '#a67b5b', '劳动': '#8c8c8c'
}
function subjectColor(s) { return subjectColors[s] || '#a67b5b' }

const cellDialog = ref(false)
const cellPos = ref(null)       // { period: 第几节下标, weekday: 星期下标 }
const cellForm = ref({ subject: '', teacher_user_id: null })

function emptyRow() {
  return Array(weekdays).fill(null).map(() => ({ subject: '', teacher_user_id: null }))
}

async function loadClasses() {
  classes.value = await listClasses()
  teachers.value = await listTeachers()
  overview.value = await getTimetableOverview()
}

async function loadTimetable() {
  if (!classId.value) { ElMessage.warning('请先选择班级'); return }
  loading.value = true
  try {
    const data = await request.get(`/admin/classes/${classId.value}/timetable`).then((r) => r.data)
    cells.value = (data.cells || []).map((row) =>
      row.map((c) => ({ subject: c.subject || '', teacher_user_id: c.teacher_user_id || null }))
    )
    while (cells.value.length < periods) cells.value.push(emptyRow())
    while (cells.value.length > periods) cells.value.pop()
  } finally { loading.value = false }
}

// 当前弹窗对应星期（1-7）/节次（1-N）
function currentWeekday() { return (cellPos.value?.weekday || 0) + 1 }
function currentPeriod() { return (cellPos.value?.period || 0) + 1 }

// 该时段已占用（在其它班级上课）的老师 id 集合
const busyTeacherIds = computed(() => {
  if (!cellPos.value) return new Set()
  const w = currentWeekday()
  const p = currentPeriod()
  const busy = new Set()
  for (const item of overview.value) {
    if (item.class_id !== classId.value && item.weekday === w && item.period === p && item.teacher_user_id) {
      busy.add(item.teacher_user_id)
    }
  }
  return busy
})

// 上课老师可选项：仅选择负责该科目的老师（其他科目老师不可代课）
const teacherOptions = computed(() => {
  if (!cellForm.value.subject) return []
  return teachers.value.filter((t) => (t.subjects || []).includes(cellForm.value.subject))
})

function teacherName(id) {
  const t = teachers.value.find((x) => x.user_id === id)
  return t ? (t.full_name || t.username) : id
}

// 选课时实时冲突检测
function onTeacherChange(tid) {
  if (!tid) return
  const w = currentWeekday()
  const p = currentPeriod()
  const conflict = overview.value.find(
    (item) => item.class_id !== classId.value && item.weekday === w && item.period === p && item.teacher_user_id === tid
  )
  if (conflict) {
    const t = teachers.value.find((x) => x.user_id === tid)
    ElMessage.error(`老师「${t?.full_name || t?.username || tid}」该时段已在班级「${conflict.class_name}」上课，请选择其他老师`)
    cellForm.value.teacher_user_id = null
  }
}

function openCell(periodIdx, weekdayIdx) {
  const cell = cells.value[periodIdx][weekdayIdx]
  cellPos.value = { period: periodIdx, weekday: weekdayIdx }
  cellForm.value = { subject: cell.subject, teacher_user_id: cell.teacher_user_id || null }
  cellDialog.value = true
}

function saveCell() {
  if (!cellPos.value) return
  if (cellForm.value.subject && !cellForm.value.teacher_user_id) {
    ElMessage.warning('请选择上课老师')
    return
  }
  if (cellForm.value.teacher_user_id && busyTeacherIds.value.has(cellForm.value.teacher_user_id)) {
    ElMessage.error('该老师该时段已在其他班级上课，请更换老师')
    return
  }
  const { period, weekday } = cellPos.value
  cells.value[period][weekday] = {
    subject: cellForm.value.subject,
    teacher_user_id: cellForm.value.teacher_user_id || null
  }
  cellDialog.value = false
}

async function save() {
  if (!classId.value) return
  saving.value = true
  try {
    const res = await request.put(`/admin/classes/${classId.value}/timetable`, { cells: cells.value, periods, weekdays }).then((r) => r.data)
    if (res.code === 0) {
      ElMessage.success(res.message || '课表已保存')
      overview.value = await getTimetableOverview()   // 刷新冲突总览
      await loadTimetable()
    } else {
      ElMessage.warning(res.message || '保存失败')
    }
  } finally { saving.value = false }
}

onMounted(async () => {
  await loadClasses()
  if (classes.value.length) {
    classId.value = classes.value[0].id
    await loadTimetable()
  }
})
</script>

<template>
  <div class="page-card">
    <h3 style="margin-bottom: 12px">班级课表管理</h3>

    <div style="display:flex; gap:10px; align-items:center; margin: 14px 0">
      <span>班级：</span>
      <el-select v-model="classId" placeholder="选择班级" style="width: 220px" @change="loadTimetable">
        <el-option v-for="c in classes" :key="c.id" :label="`${c.name}（${c.class_no || '-'}）`" :value="c.id" />
      </el-select>
      <el-button type="primary" :loading="loading" @click="loadTimetable">加载课表</el-button>
      <el-button type="success" :loading="saving" @click="save">保存课表</el-button>
    </div>

    <el-table :data="cells" v-loading="loading" border>
      <el-table-column label="节次" width="70" align="center">
        <template #default="{ $index }">第 {{ $index + 1 }} 节</template>
      </el-table-column>
      <el-table-column v-for="(w, wi) in weekNames" :key="w" :label="w" align="center">
        <template #default="{ row, $index }">
          <div class="cell" @click="openCell($index, wi)">
            <template v-if="row[wi].subject">
              <el-tag :color="subjectColor(row[wi].subject)" style="color:#fff;border:none" size="small" effect="dark">{{ row[wi].subject }}</el-tag>
              <div v-if="row[wi].teacher_user_id" class="teachers">{{ teacherName(row[wi].teacher_user_id) }}</div>
            </template>
            <div v-else class="empty">点击设置课程</div>
          </div>
        </template>
      </el-table-column>
    </el-table>


    <el-dialog v-model="cellDialog" title="设置课程" width="460px">
      <p style="margin-bottom: 10px">
        第 {{ (cellPos?.period || 0) + 1 }} 节 · {{ weekNames[cellPos?.weekday || 0] }}
      </p>
      <el-form label-width="80px">
        <el-form-item label="科目">
          <el-select v-model="cellForm.subject" clearable placeholder="选择科目" style="width: 100%">
            <el-option v-for="s in subjectOptions" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="上课老师">
          <el-select v-model="cellForm.teacher_user_id" clearable filterable placeholder="选择上课老师" style="width: 100%" @change="onTeacherChange">
            <el-option
              v-for="t in teacherOptions"
              :key="t.user_id"
              :label="`${t.full_name || t.username}${busyTeacherIds.has(t.user_id) ? '（该时段已在其他班上课）' : ''}`"
              :value="t.user_id"
              :disabled="busyTeacherIds.has(t.user_id)"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cellDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCell">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.gray { color: #909399; font-size: 13px; }
.cell { cursor: pointer; min-height: 44px; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 2px; border-radius: 6px; padding: 4px; transition: background .2s; }
.cell:hover { background: #f4ebdd; }
.cell .subject { font-weight: 600; }
.cell .teachers { color: #a67b5b; font-size: 12px; }
.cell .empty { color: #c0c4cc; }
</style>
