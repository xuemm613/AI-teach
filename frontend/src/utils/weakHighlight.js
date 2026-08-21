// 雷达图「薄弱点高亮」辅助：从按掌握度升序的知识点值中选出需高亮的序列
// 非薄弱项以 NaN 占位（ECharts 雷达会跳过该顶点），实现「弱化已掌握、突出最薄弱」。
export const WEAK_THRESHOLD = 50

/**
 * @param {number[]} fullVals 按掌握度升序的值序列
 * @param {number}  threshold 视为薄弱的阈值
 * @returns {number[]} 高亮序列：掌握度 < threshold 保留原值，其余为 NaN
 */
export function selectWeakValues(fullVals, threshold = WEAK_THRESHOLD) {
  if (!Array.isArray(fullVals) || !fullVals.length) return []
  // 先归一化为有限数值（非有限值一律视为无效）
  const nums = fullVals.map((v) => (typeof v === 'number' && isFinite(v) ? v : NaN))
  if (!nums.some((v) => !isNaN(v))) return fullVals.map(() => NaN)
  const weak = nums.map((v) => (v < threshold ? v : NaN))
  if (weak.some((v) => !isNaN(v))) return weak
  // 无薄弱项时，高亮掌握度最低的一项
  const firstFinite = nums.findIndex((v) => !isNaN(v))
  const minIdx = nums.reduce((mi, v, i) => (v < nums[mi] ? i : mi), firstFinite)
  return nums.map((v, i) => (i === minIdx ? v : NaN))
}