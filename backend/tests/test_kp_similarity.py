"""相似例题算法单元测试（纯函数，无需数据库）。

重点回归：彻底消除"李白题 → 《蒹葭》"的无关混入。
运行：python -m pytest backend/tests/test_kp_similarity.py -v
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest  # noqa: E402

from app.services.kp_similarity import ExerciseFeature, expanded_kps, select_similar  # noqa: E402


def feat(id_, **kw):
    base = dict(
        id=id_,
        type="single",
        difficulty="medium",
        subject="语文",
        chapter="",
        course_id=1,
        kps=[],
    )
    base.update(kw)
    return ExerciseFeature(**base)


# 李白原题（对应缺陷案例"李白诗风"）
def li_po():
    return feat(100, kps=["李白", "浪漫主义"], type="single", difficulty="medium", subject="语文")


# 相关候选：盛唐浪漫主义（同知识点语义命中）
def li_related():
    return feat(200, kps=["盛唐", "诗仙"], type="single", difficulty="medium", subject="语文")


# 无关候选：《蒹葭》（同科目/题型/难度，但知识点零语义重叠）
def jian_jia():
    return feat(300, kps=["《蒹葭》", "诗经"], type="single", difficulty="medium", subject="语文")


# 跨科目候选：数学无理数
def math_irrational():
    return feat(400, kps=["无理数"], type="single", difficulty="medium", subject="数学")


def test_kp_synonyms_expand_li_po():
    lis = sorted(expanded_kps(li_po().kps))
    assert "盛唐" in lis
    assert "诗仙" in lis


def test_eliminates_jianjia_when_kp_present():
    """原题有知识点时，《蒹葭》必须被剔除，相关候选保留。"""
    picked, level, insufficient = select_similar(
        li_po(), [jian_jia(), li_related()], limit=3, threshold=0.5
    )
    ids = [c.id for _, c in picked]
    assert jian_jia().id not in ids   # 关键回归断言
    assert li_related().id in ids
    assert level == "kp"
    assert insufficient is False


def test_excludes_cross_subject():
    """可判定科目不同时直接排除。"""
    picked, _, _ = select_similar(li_po(), [math_irrational()], limit=3, threshold=0.5)
    assert all(c.id != math_irrational().id for _, c in picked)


def test_insufficient_when_no_related():
    """只有无关题时可报不足，不硬凑。"""
    picked, level, insufficient = select_similar(
        li_po(), [jian_jia()], limit=3, threshold=0.5
    )
    assert picked == []
    assert insufficient is True
    assert level == "none"


def test_fallback_when_no_kps():
    """原题无知识点时，不再用粗泛的章节/课程做相似（改为由 AI 兜底）。"""
    orig_no_kp = feat(500, kps=[])
    same_course = feat(501, kps=[], chapter="第三章", course_id=7)
    diff_course = feat(502, kps=[], chapter="第三章", course_id=8)
    picked, level, insufficient = select_similar(
        orig_no_kp, [same_course, diff_course], limit=3, threshold=0.6
    )
    # 无标签时禁止用课程/章节糊弄相似题 → 交回 AI 生成
    assert picked == []
    assert insufficient is True
    assert level == "none"


def test_biolog_rejects_coarse_shared_tag():
    """用户回归场景：叶绿体题不得推荐"染色体/有丝分裂"（同科目但知识点仅 1 个粗泛共享）。"""
    orig = feat(600, kps=["叶绿体", "光合作用", "细胞"])
    cross = feat(601, kps=["染色体", "有丝分裂", "细胞"])   # 仅共享"细胞"
    real = feat(602, kps=["叶绿体", "光合作用"])             # 强相关
    picked, level, insufficient = select_similar(
        orig, [cross, real], limit=3, threshold=0.6
    )
    ids = {c.id for _, c in picked}
    assert cross.id not in ids   # 粗泛共享被剔除
    assert real.id in ids        # 强相关保留
    assert level == "kp"


def test_threshold_0_6_drops_weak():
    """高于门限的弱相关（如仅 1 个粗泛标签）应被剔除而非硬凑。"""
    orig = feat(700, kps=["叶绿体", "光合作用", "细胞"])
    weak = feat(701, kps=["细胞", "细胞呼吸"])
    picked, level, insufficient = select_similar(orig, [weak], limit=3, threshold=0.6)
    assert picked == []
    assert insufficient is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))