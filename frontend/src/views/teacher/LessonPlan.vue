<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deletePlan, exportPlan, generateLesson, listPlans, updatePlan } from '@/api/lesson'
import { SUBJECTS } from '@/constants'

const formRef = ref()
const generating = ref(false)
const plan = ref(null)
const plans = ref([])
const saving = ref(false)
const range = ref([])
const keyword = ref('')

const form = reactive({ grade: '七年级', subject: '数学', chapter: '', teaching_objectives: '' })
const rules = {
  grade: [{ required: true, message: '请输入年级', trigger: 'blur' }],
  subject: [{ required: true, message: '请输入学科', trigger: 'blur' }],
  chapter: [{ required: true, message: '请输入章节', trigger: 'blur' }]
}

async function generate() {
  await formRef.value.validate()
  generating.value = true
  plan.value = null
  try {
    plan.value = await generateLesson({ ...form })
    ElMessage.success('教案生成成功')
    await loadPlans()
  } finally { generating.value = false }
}

async function loadPlans() {
  const params = { keyword: keyword.value || undefined }
  if (range.value && range.value.length === 2) { params.start = range.value[0]; params.end = range.value[1] }
  plans.value = await listPlans(params)
}

async function saveEdit() {
  saving.value = true
  try {
    await updatePlan(plan.value.id, { content: plan.value.content })
    ElMessage.success('已保存编辑')
    await loadPlans()   // 保存后刷新历史列表，重新打开时显示最新内容
  } finally { saving.value = false }
}

async function remove(id) {
  await ElMessageBox.confirm('确定删除该教案吗？', '提示', { type: 'warning' })
  await deletePlan(id)
  await loadPlans()
  if (plan.value && plan.value.id === id) plan.value = null
}

function layerList(layer) { return plan.value?.content?.layered_exercises?.[layer] || [] }

onMounted(() => {
  form.subject = SUBJECTS[0]
  loadPlans()
})
</script>

<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="14">
        <div class="page-card">
          <h3 style="margin-bottom: 16px">智能备课</h3>
          <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
            <el-form-item label="年级" prop="grade"><el-input v-model="form.grade" /></el-form-item>
            <el-form-item label="学科" prop="subject">
              <el-select v-model="form.subject" style="width:100%" placeholder="选择学科">
                <el-option v-for="s in SUBJECTS" :key="s" :label="s" :value="s" />
              </el-select>
            </el-form-item>
            <el-form-item label="章节" prop="chapter"><el-input v-model="form.chapter" /></el-form-item>
            <el-form-item label="教学目标"><el-input v-model="form.teaching_objectives" type="textarea" :rows="3"  /></el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="generating" @click="generate">生成教案</el-button>
              <el-button v-if="plan" :loading="saving" @click="saveEdit">保存手动编辑</el-button>
              <el-button v-if="plan" @click="exportPlan(plan.id, `${plan.subject}_${plan.chapter}_教案.docx`)">导出 Word</el-button>
            </el-form-item>
          </el-form>
        </div>

        <div class="page-card" style="margin-top: 16px" v-loading="generating">
          <h3 style="margin-bottom: 12px">教案展示</h3>
          <el-empty v-if="!plan && !generating" description="生成后将在此结构化展示教案" />
          <template v-if="plan">
            <el-alert type="success" :closable="false" style="margin-bottom: 12px">
              {{ plan.subject }} · {{ plan.grade }} · {{ plan.chapter }}
            </el-alert>
            <div class="section">
              <h4>📌 教学目标</h4>
              <div v-for="(o, i) in plan.content.teaching_objectives" :key="i">
                <el-input v-model="plan.content.teaching_objectives[i]" size="small" style="margin-bottom:4px" />
              </div>
            </div>
            <div class="section">
              <h4>🎬 课堂导入</h4>
              <el-input v-model="plan.content.introduction" type="textarea" :rows="2" />
            </div>
            <div class="section">
              <h4>📋 讲授提纲</h4>
              <div v-for="(o, i) in plan.content.outline" :key="i">
                <el-input v-model="plan.content.outline[i]" size="small" style="margin-bottom:4px" />
              </div>
            </div>
            <div class="section">
              <h4>💬 互动问题</h4>
              <div v-for="(q, i) in plan.content.interactive_questions" :key="i" class="qa-item">
                <el-input v-model="plan.content.interactive_questions[i].question" size="small" style="margin-bottom:4px" />
                <el-input v-model="plan.content.interactive_questions[i].answer" size="small" placeholder="答案" />
              </div>
            </div>
            <div class="section">
              <h4>🖊 板书设计</h4>
              <el-input v-model="plan.content.board_design" type="textarea" :rows="3" />
            </div>
            <div class="section">
              <h4>✏️ 分层练习</h4>
              <el-row :gutter="12">
                <el-col :span="8"><b>基础</b><div v-for="(e, i) in layerList('basic')" :key="i"><el-input v-model="plan.content.layered_exercises.basic[i]" size="small" style="margin:2px 0" /></div></el-col>
                <el-col :span="8"><b>提高</b><div v-for="(e, i) in layerList('medium')" :key="i"><el-input v-model="plan.content.layered_exercises.medium[i]" size="small" style="margin:2px 0" /></div></el-col>
                <el-col :span="8"><b>拓展</b><div v-for="(e, i) in layerList('advanced')" :key="i"><el-input v-model="plan.content.layered_exercises.advanced[i]" size="small" style="margin:2px 0" /></div></el-col>
              </el-row>
            </div>
          </template>
        </div>
      </el-col>

      <el-col :span="10">
        <div class="page-card">
          <h3 style="margin-bottom: 12px">生成历史</h3>
          <div style="display:flex; gap:8px; margin-bottom:12px">
            <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" size="small" />
            <el-input v-model="keyword" placeholder="按章节检索" size="small" clearable @keyup.enter="loadPlans" />
            <el-button size="small" type="primary" @click="loadPlans">查询</el-button>
          </div>
          <div v-for="p in plans" :key="p.id" class="plan-item">
            <div class="plan-info" @click="plan = p">
              <div class="plan-title">{{ p.subject }} · {{ p.chapter }}</div>
              <div class="plan-meta">{{ p.grade }} · {{ new Date(p.created_at).toLocaleString() }}</div>
            </div>
            <div>
              <el-button size="small" type="primary" link @click="plan = p">查看</el-button>
              <el-button size="small" type="danger" link @click="remove(p.id)">删除</el-button>
            </div>
          </div>
          <el-empty v-if="!plans.length" description="暂无教案" :image-size="60" />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.section { margin-bottom: 14px; }
.section h4 { margin-bottom: 6px; color: #303133; }
.qa-item { margin-bottom: 8px; }
.plan-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #DEE3EA; }
.plan-info { cursor: pointer; flex: 1; min-width: 0; }
.plan-title { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.plan-meta { color: #909399; font-size: 12px; margin-top: 2px; }
</style>