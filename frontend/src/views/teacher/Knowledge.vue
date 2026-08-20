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
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 16px">
          <h3>知识库文档</h3>
          <el-tag type="primary">当前学科：{{ subject || '未分配' }}</el-tag>
        </div>

        <el-upload drag multiple :show-file-list="false" :http-request="customUpload" accept=".pdf,.docx,.txt,.md" style="margin-bottom: 16px">
          <el-icon size="44" color="#8B5CF6"><UploadFilled /></el-icon>
          <div class="el-upload__text">拖拽文件到此处，或 <em>点击上传</em></div>
        </el-upload>

        <div v-loading="loading">
          <div v-if="files.length" class="file-list">
            <div v-for="f in files" :key="f.id" class="file-item">
              <div class="file-icon"><el-icon><Document /></el-icon></div>
              <div class="file-info">
                <div class="file-name">{{ f.filename }}</div>
                <div class="file-meta">{{ f.file_type }} · {{ new Date(f.created_at).toLocaleString() }}</div>
              </div>
              <div class="file-status">
                <el-tooltip v-if="f.error" :content="f.error" placement="top">
                  <el-tag :type="statusType[f.status]">{{ statusMap[f.status] }}</el-tag>
                </el-tooltip>
                <el-tag v-else :type="statusType[f.status]">{{ statusMap[f.status] }}</el-tag>
              </div>
              <div class="file-actions">
                <el-button type="primary" link @click="viewContent(f)">查看</el-button>
                <el-button type="danger" link @click="remove(f.id)">删除</el-button>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无文件" />
        </div>
      </div>
    </el-col>
    <el-col :span="9">
      <div class="page-card qa-card">
        <h3 style="margin-bottom: 20px; display:flex; align-items:center"><el-icon style="margin-right:6px"><ChatDotRound /></el-icon>知识库问答（RAG）</h3>
        <el-input v-model="qaQuestion" type="textarea" :rows="5" placeholder="请输入问题，基于已上传的知识库内容回答" />
        <el-button type="primary" style="margin-top: 16px; width: 100%" :loading="qaAsking" @click="doAsk">提问</el-button>
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
.file-list { display: flex; flex-direction: column; gap: 12px; }
.file-item { display: flex; align-items: center; gap: 14px; padding: 16px; border: 1px solid #E5E7EB; border-radius: 10px; background: #F9FAFB; transition: all .2s; }
.file-item:hover { border-color: #C4B5FD; box-shadow: 0 2px 8px rgba(139, 92, 246, 0.12); }
.file-icon { width: 40px; height: 40px; border-radius: 10px; background: #F3EDFB; color: #8B5CF6; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 20px; }
.file-info { flex: 1; min-width: 0; }
.file-name { font-weight: 600; font-size: 15px; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-meta { color: #909399; font-size: 13px; margin-top: 4px; }
.file-actions { flex-shrink: 0; }
.qa-card { height: 100%; display: flex; flex-direction: column; }
.qa-box { margin-top: 18px; padding: 16px; background: #F4F6F9; border: 1px solid #D0D5DD; border-radius: 8px; flex: 1; overflow-y: auto; }
.content-box pre { white-space: pre-wrap; word-break: break-all; font-size: 13px; line-height: 1.7; max-height: 60vh; overflow-y: auto; }
</style>
