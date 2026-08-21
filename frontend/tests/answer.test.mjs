/**
 * 答题判题单元测试（无外部依赖，直接 `node tests/answer.test.mjs` 即可运行）。
 * 覆盖：多选数组归一化、单选/判断/填空判题、空答案防御。
 */
import assert from 'node:assert/strict'
import {
  isAnswerCorrect,
  normalizePracticeAnswer,
  normAnswer,
} from '../src/utils/answer.js'

let passed = 0
function t(name, fn) {
  fn()
  passed++
  console.log('  \u2713', name)
}

console.log('answer.test.mjs')

// --- 多选归一化 ---
t('多选数组排序拼接（BA → AB）', () => {
  assert.equal(normalizePracticeAnswer('multiple', ['B', 'A']), 'AB')
})
t('多选重复项保留（AAB）', () => {
  assert.equal(normalizePracticeAnswer('multiple', ['A', 'A', 'B']), 'AAB')
})
t('单选字符串透传', () => {
  assert.equal(normalizePracticeAnswer('single', 'B'), 'B')
})
t('填空字符串透传', () => {
  assert.equal(normalizePracticeAnswer('fill', '3.14'), '3.14')
})

// --- 判题 ---
t('单选题正确匹配（大小写/空白）', () => {
  assert.equal(isAnswerCorrect('single', ' b ', 'B'), true)
})
t('单选题错误匹配', () => {
  assert.equal(isAnswerCorrect('single', 'B', 'A'), false)
})
t('判断题（对/错 与 a/b）', () => {
  assert.equal(isAnswerCorrect('judge', '对', 'a'), true)
  assert.equal(isAnswerCorrect('judge', '错', 'b'), true)
  assert.equal(isAnswerCorrect('judge', '正确', 'a'), true)
})
t('多选题答案与作答打乱等价', () => {
  assert.equal(isAnswerCorrect('multiple', ['B', 'A', 'C'], 'ACB'), true)
  assert.equal(isAnswerCorrect('multiple', ['B', 'A'], 'AC'), false)
})
t('填空题归一化判题', () => {
  assert.equal(isAnswerCorrect('fill', ' 3.14 ', '3.14'), true)
})
t('空答案防御', () => {
  assert.equal(isAnswerCorrect('single', '', 'B'), false)
})
t('normAnswer 去标点', () => {
  assert.equal(normAnswer('A, B；C。'), 'abc')
})

console.log(`  \u2713 ${passed} passed`)