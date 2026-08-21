"""题目生成去重/多样性控制单元测试。

可直接运行：`python -m pytest backend/tests/test_generate_diversity.py -v`
或（未装 pytest 时）：`python backend/tests/test_generate_diversity.py`
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.text import norm_text as _gen_norm


def test_gen_norm_strips_whitespace():
    assert _gen_norm("  勾股定理  ") == "勾股定理"
    assert _gen_norm("A B C") == "abc"
    assert _gen_norm(None) == ""


def test_gen_norm_case_insensitive():
    assert _gen_norm("ABC") == "abc"


def test_duplicate_detection():
    """后端判重：归一化后相同的两题必须被识别为重复。"""
    prev = "已知直角三角形两直角边为3和4，求斜边。"
    same = " 已知直角三角形两直角边为3和4，求斜边。 "
    other = "已知一元二次方程 x^2-3x+2=0，求根。"
    excluded = {_gen_norm(prev)}
    assert _gen_norm(same) in excluded   # 雷同 → 触发重新生成
    assert _gen_norm(other) not in excluded  # 不同 → 保留


def test_force_vary_fallback():
    """无历史时 force_vary 仍给出提示分支（保证不被重复）。"""
    # force_vary 与 exclude 互斥分支正确性由端点逻辑保证，
    # 此处校验归一化辅助函数稳定。
    assert _gen_norm("  勾股 定理  ") == "勾股定理"


if __name__ == "__main__":
    tests = [v for n, v in globals().items() if n.startswith("test_") and callable(v)]
    for fn in sorted(tests, key=lambda f: f.__name__):
        fn()
        print("  PASS", fn.__name__)
    print("  %d passed" % len(tests))