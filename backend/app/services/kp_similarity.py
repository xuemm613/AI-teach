"""相似例题推荐核心算法（P0 门限/硬过滤/回退 + P1 知识点归一化与同义词扩展）。

设计原则：
- 纯函数，不读写数据库，便于单元验证与版本回滚；
- P0：硬过滤 = 题型必须一致 + 可判定科目必须一致；原题有知识点时，
  候选必须与原题至少命中一个语义知识点（直接掐断"《蒹葭》 vs 李白"这类
  只靠"同题型同科目"混入的无关题）；归一化相似度低于门限者一律不推；
  质量不足时逐级回退，宁缺毋滥；
- P1：对 knowledge_points 做规范化 + 学科同义词/上下位别名扩展，
  "语义命中"而非"字符串精确相等"作为相关性信号。

注意：本模块不修改数据库结构/数据模型/存储，仅在内存中计算相似度。
"""
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

# ---------------- P1：学科同义词/上下位映射 ----------------
# key = 规范知识点，value = 别名/上下位（写入时建议 aligned 到系统章节树）。
# 可在此持续扩充而无须改库。
KP_SYNONYMS: dict = {
    # 语文 · 古诗
    "李白": ["诗仙", "盛唐", "浪漫主义", "盛唐浪漫豪放", "想像瑰丽"],
    "盛唐浪漫主义": ["李白", "诗仙", "想象瑰丽", "气势磅礴"],
    "浪漫主义诗歌": ["诗仙", "想象瑰丽", "夸张想象"],
    "诗经": ["诗经", "风雅颂", "先秦诗歌", "现实主义源头", "赋比兴"],
    "《蒹葭》": ["诗经", "秦风", "风雅颂", "重章叠句", "比兴手法", "伊人"],
    # 数学
    "无理数": ["根号", "无限不循环小数", "实数分类"],
    "平方根": ["算术平方根", "二次根式", "根号计算"],
    "一元二次方程": ["二次方程", "判别式", "求根公式"],
    "幂运算": ["同底数幂", "指数运算", "幂法则"],
    # 英语
    "一般现在时": ["简单现在时", "三单", "present simple"],
    "一般过去时": ["过去时", "past simple", "过去式"],
    # 物理
    "牛顿第一定律": ["惯性", "受力平衡", "匀速直线运动"],
}

DIFF_LEVEL = {"easy": 1, "medium": 2, "hard": 3}


def _norm(tag) -> str:
    return "".join((tag or "").strip().split()).lower()


def _build_alias_map():
    alias_map = {}
    for canonical, aliases in KP_SYNONYMS.items():
        nc = _norm(canonical)
        alias_map[nc] = nc
        for a in aliases:
            alias_map[_norm(a)] = nc
    return alias_map


_ALIAS_MAP = _build_alias_map()


def canonical_kps(kps: Optional[list]) -> Set[str]:
    """知识点规范化：去空白 → 同义词聚合到规范条目。"""
    out = set()
    for t in kps or []:
        n = _norm(t)
        if n:
            out.add(_ALIAS_MAP.get(n, n))
    return out


def expanded_kps(kps: Optional[list]) -> Set[str]:
    """规范知识点 + 各自别名（用于语义命中，可放大到上下位）。"""
    canon = canonical_kps(kps)
    out = set(canon)
    for c in canon:
        for a in KP_SYNONYMS.get(c, []):
            n = _norm(a)
            if n:
                out.add(n)
    return out


def _difficulty_level(d: Optional[str]) -> int:
    return DIFF_LEVEL.get((d or "").lower(), 2)


@dataclass
class ExerciseFeature:
    """由端点从 DB 行构造的特征（不持有 DB 对象，方便单测）。"""
    id: int
    type: str
    difficulty: str
    subject: str
    chapter: str
    course_id: Optional[int]
    kps: list = field(default_factory=list)

    @property
    def has_kps(self) -> bool:
        return bool(self.kps)

    @property
    def canon(self) -> Set[str]:
        return canonical_kps(self.kps)

    @property
    def exp(self) -> Set[str]:
        return expanded_kps(self.kps)


def _score(orig: ExerciseFeature, cand: ExerciseFeature, level: str) -> Optional[float]:
    """单对打分。命中硬过滤规则或低于相关最低要求时返回 None。
    返回值为归一化 0~1 相似度（越高越相似）。"""
    o_subj, c_subj = orig.subject, cand.subject
    # 硬过滤 1：题型结构必须一致
    if cand.type != orig.type:
        return None
    # 硬过滤 2：可判定科目必须一致（杜绝跨学科）
    if o_subj and c_subj and o_subj != c_subj:
        return None

    # 各回退层级的准入
    if level == "kp":
        if not orig.exp:
            return None
        if not (orig.exp & cand.exp):
            return None  # 语义零重叠：无关题，直接剔除（解决《蒹葭》混入）
    elif level == "chapter":
        chapter_ok = bool(orig.chapter and cand.chapter and orig.chapter == cand.chapter)
        course_ok = bool(
            orig.course_id and cand.course_id and orig.course_id == cand.course_id
        )
        if not (chapter_ok or course_ok):
            return None
    elif level == "course":
        if not (orig.course_id and cand.course_id and orig.course_id == cand.course_id):
            return None
    else:
        return None

    # 相似度计算（归一化 0~1；KP 用 Jaccard，对"单一粗泛共享标签"惩罚明显）
    kp_term = 0.0
    if level == "kp":
        semantic = len(orig.exp & cand.exp)
        union = len(orig.exp | cand.exp) or 1
        jac = semantic / union
        kp_term = 0.7 * jac

    gap = abs(_difficulty_level(cand.difficulty) - _difficulty_level(orig.difficulty))
    diff_score = {0: 1.0, 1: 0.6}.get(gap, 0.3)
    subj_score = 1.0 if (o_subj and c_subj and o_subj == c_subj) else (0.8 if (o_subj or c_subj) else 0.8)

    return kp_term + 0.20 * diff_score + 0.10 * subj_score


def _select_level(
    orig: ExerciseFeature,
    cands: List[ExerciseFeature],
    level: str,
    limit: int,
    threshold: float,
) -> List[Tuple[float, ExerciseFeature]]:
    scored = []
    for c in cands:
        if c.id == orig.id:
            continue
        s = _score(orig, c, level)
        if s is None or s < threshold or s <= 0:
            continue
        scored.append((s, c))
    scored.sort(key=lambda x: (-x[0], -x[1].id))
    return scored[:limit]


def select_similar(
    orig: ExerciseFeature,
    cands: List[ExerciseFeature],
    limit: int = 3,
    threshold: float = 0.5,
) -> Tuple[List[Tuple[float, ExerciseFeature]], str, bool]:
    """多级回退选择。

    返回：(results, used_level, insufficient)
    - used_level: kp / chapter / course / none
    - insufficient: True 表示高质量相似题不足（可由 P2 兜底）。
    原题有知识点时走 kp 层且不刑事下层（避免把同课程无关题当相似题）；
    原题没有知识点时才回退到章节/课程结构层。
    """
    if orig.has_kps:
        res = _select_level(orig, cands, "kp", limit, threshold)
        if res:
            if len(res) < limit:
                return res, "kp", True
            return res, "kp", False
        return [], "none", True
    for level in ("chapter", "course"):
        res = _select_level(orig, cands, level, limit, threshold)
        if res:
            return res, level, False
    return [], "none", True