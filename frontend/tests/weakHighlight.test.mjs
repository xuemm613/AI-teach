/**
 * 雷达图「薄弱点高亮」单元测试（无外部依赖，直接 `node tests/weakHighlight.test.mjs` 即可运行）。
 * 覆盖：升序输入、阈值判定、无薄弱时兜底最低项、空输入防御。
 */
import assert from 'node:assert/strict'
import { selectWeakValues } from '../src/utils/weakHighlight.js'

let passed = 0
function t(name, fn) {
  fn()
  passed++
  console.log('  \u2713', name)
}

console.log('weakHighlight.test.mjs')

t('低于阈值项保留，其余置 NaN', () => {
  // 升序掌握度 [30,58,82,90]：仅 30 < 50
  assert.deepEqual(selectWeakValues([30, 58, 82, 90]), [30, NaN, NaN, NaN])
})
t('多项薄弱全部保留', () => {
  assert.deepEqual(selectWeakValues([20, 40, 60, 70]), [20, 40, NaN, NaN])
})
t('无薄弱时高亮最低一项（此处 60 最低）', () => {
  assert.deepEqual(selectWeakValues([60, 70, 80]), [60, NaN, NaN])
})
t('空数组返回空数组', () => {
  assert.deepEqual(selectWeakValues([]), [])
})
t('非数组输入防御', () => {
  assert.deepEqual(selectWeakValues(null), [])
  assert.deepEqual(selectWeakValues(undefined), [])
})
t('存在无效值时忽略并高亮有限最小项', () => {
  assert.deepEqual(selectWeakValues([NaN, 80, 90]), [NaN, 80, NaN])
})
t('全部无效返回全 NaN', () => {
  const r = selectWeakValues([NaN, NaN])
  assert.equal(r.length, 2)
  assert.ok(r.every((v) => isNaN(v)))
})

console.log(`  \u2713 ${passed} passed`)