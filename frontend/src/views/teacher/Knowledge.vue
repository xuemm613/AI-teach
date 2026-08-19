<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { askKnowledge, deleteFile, getFileContent, listFiles, uploadFile } from '@/api/knowledge'
import MarkdownView from '@/components/MarkdownView.vue'

const userStore = useUserStore()
const files = ref([])
const loading = ref(false)

// 学科固定为当前登录教师负责的学科（一位老师只负责一门学科）
const subject = computed(() => (userStore.user?.subjects || [])[0] || '')

const statusMap = { pending: '待处理', processing: '处理中', indexed: '已完成', failed: '失败' }
const statusType = { pending: 'info', processing: 'warning', indexed: 'success', failed: 'danger' }

// ---- RAG 问答 ----
const qaQuestion = ref('')
const qaAnswer = ref('')
const qaAsking = ref(false)

// ---- 查看文件内容 ----
const contentDialog = ref(false)
const contentLoading = ref(false)
const currentFileName = ref('')
const currentContent = ref('')

async function viewContent(row) {
  contentLoading.value = true
  currentFileName.value = row.filename
  try {
    const data = await getFileContent(row.id)
    currentContent.value = data.content || '（文件内容为空或暂不可解析）'
    contentDialog.value = true
  } catch (e) {
    ElMessage.error('文件内容加载失败：' + (e.message || '未知错误'))
  } finally {
    contentLoading.value = false
  }
}

let pollTimer = null

async function load() {
  loading.value = true
  try {
    const data = await listFiles({ page: 1, size: 100, subject: subject.value || undefined })
    files.value = data.items
  } finally { loading.value = false }
  // 有文件仍在处理中时自动轮询，完成后自动刷新状态（无需手动刷新）
  const processing = files.value.some((f) => f.status === 'pending' || f.status === 'processing')
  if (processing && !pollTimer) {
    pollTimer = setInterval(async () => {
      const data = await listFiles({ page: 1, size: 100, subject: subject.value || undefined })
      files.value = data.items
      if (!files.value.some((f) => f.status === 'pending' || f.status === 'processing')) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    }, 2000)
  } else if (!processing && pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function customUpload({ file, onSuccess, onError }) {
  if (!subject.value) { ElMessage.warning('当前账号未分配学科'); onError(new Error('no subject')); return }
  const fd = new FormData()
  fd.append('file', file)
  fd.append('subject', subject.value)
  try {
    await uploadFile(fd)
    ElMessage.success('上传成功，正在后台解析入库')
    onSuccess()
    await load()   // 上传后自动刷新并轮询处理状态
  } catch (e) { onError(e) }
}

async function remove(id) {
  await ElMessageBox.confirm('删除后该文件的分块与引用将一并移除，确定吗？', '提示', { type: 'warning' })
  await deleteFile(id)
  ElMessage.success('删除成功')
  await load()
}

async function doAsk() {
  if (!qaQuestion.value.trim()) { ElMessage.warning('请输入问题'); return }
  qaAsking.value = true
  try {
    const res = await askKnowledge({ question: qaQuestion.value.trim(), subject: subject.value || null })
    qaAnswer.value = res.answer
  } finally { qaAsking.value = false }
}

onMounted(load)
onBeforeUnmount(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<template>
  <el-row :gutter="16">
    <el-col :span="15">
      <div class="page-card">
        <div style="display:flex; gap:10px; margin-bottom: 12px; align-items:center">
          <span>当前学科：</span>
          <el-tag type="primary">{{ subject || '未分配' }}</el-tag>
        </div>

        <el-upload drag multiple :show-file-list="false" :http-request="customUpload" accept=".pdf,.docx,.txt,.md" style="margin-bottom: 16px">
          <el-icon size="40" color="#a67b5b"><UploadFilled /></el-icon>
          <div class="el-upload__text">拖拽文件到此处，或 <em>点击上传</em></div>
        </el-upload>

        <el-table :data="files" v-loading="loading" stripe>
          <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
          <el-table-column prop="file_type" label="类型" width="80" />
          <el-table-column label="上传时间" width="170"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template></el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tooltip v-if="row.error" :content="row.error" placement="top">
                <el-tag :type="statusType[row.status]">{{ statusMap[row.status] }}</el-tag>
              </el-tooltip>
              <el-tag v-else :type="statusType[row.status]">{{ statusMap[row.status] }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <el-button type="primary" link @click="viewContent(row)">查看</el-button>
              <el-button type="danger" link @click="remove(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!files.length" description="暂无文件" />
      </div>
    </el-col>
    <el-col :span="9">
      <div class="page-card">
        <h3 style="margin-bottom: 12px">知识库问答（RAG）</h3>
        <el-input v-model="qaQuestion" type="textarea" :rows="3" placeholder="请输入问题" />
        <el-button type="primary" style="margin-top: 10px; width: 100%" :loading="qaAsking" @click="doAsk">提问</el-button>
        <template v-if="qaAnswer">
          <div class="qa-box">
            <MarkdownView :content="qaAnswer" />
          </div>
        </template>
        <el-empty v-else description="上传文件后，在此提问知识库内容" :image-size="60" />
      </div>
    </el-col>
  </el-row>

  <el-dialog v-model="contentDialog" :title="currentFileName" width="720px">
    <div v-loading="contentLoading" class="content-box">
      <pre>{{ currentContent }}</pre>
    </div>
  </el-dialog>
</template>

<style scoped>
.gray { color: #909399; font-size: 12px; }
.qa-box { margin-top: 14px; padding: 12px; background: #fbf6ed; border: 1px solid #eadfcb; border-radius: 8px; }
.content-box pre { white-space: pre-wrap; word-break: break-all; font-size: 13px; line-height: 1.7; max-height: 60vh; overflow-y: auto; }
</style>
