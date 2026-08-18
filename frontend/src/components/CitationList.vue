<script setup>
defineProps({
  sources: { type: Array, default: () => [] }
})
</script>

<template>
  <div v-if="sources && sources.length" class="citations">
    <span class="label">引用来源：</span>
    <el-tag
      v-for="(s, i) in sources"
      :key="i"
      size="small"
      type="info"
      class="cite"
    >
      {{ s.filename }}{{ s.page ? ` 第${s.page}页` : '' }}（{{ s.score }}）
    </el-tag>
  </div>
</template>

<style scoped>
.citations {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.label {
  font-size: 12px;
  color: #909399;
}
</style>