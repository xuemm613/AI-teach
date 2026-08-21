"""学习活跃度序列聚合（纯函数）单元测试。

可直接运行：`python -m pytest backend/tests/test_activity.py -v`
或（未装 pytest 时）：`python backend/tests/test_activity.py`
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.activity_stats import build_activity_series, week_monday


def test_day_period_returns_14_buckets():
    daily = {"2026-08-20": 1, "2026-08-21": 4}
    start = date(2026, 8, 8)
    items = build_activity_series(daily, "day", start)
    assert len(items) == 14
    assert items[0]["label"] == "08-08" and items[0]["count"] == 0
    assert items[12]["count"] == 1   # 08-20
    assert items[13]["count"] == 4   # 08-21


def test_day_series_sorted_ascending():
    start = date(2026, 8, 8)
    items = build_activity_series({}, "day", start)
    labels = [i["label"] for i in items]
    assert labels[0] == "08-08" and labels[-1] == "08-21"
    assert labels == sorted(labels)


def test_week_period_sums_within_week():
    # 2026-08-17 是周一，该周含 08-17 ~ 08-23
    daily = {"2026-08-18": 2, "2026-08-20": 3, "2026-08-24": 5}
    start = date(2026, 8, 17)  # 周一
    items = build_activity_series(daily, "week", start)
    assert len(items) == 8
    assert items[0]["count"] == 5   # 08-17~08-23 汇总 2+3
    assert items[1]["count"] == 5   # 08-24~08-30 汇总 5


def test_week_monday_alignment():
    assert week_monday(date(2026, 8, 20)).isoformat() == "2026-08-17"  # 周四 -> 周一
    assert week_monday(date(2026, 8, 17)).isoformat() == "2026-08-17"  # 周一不动
    assert week_monday(date(2026, 8, 23)).isoformat() == "2026-08-17"  # 周日 -> 周一


def test_month_period_returns_6_months():
    # 序列从 start(2026-08-01) 起向后 6 个月，08-20 落在首个周期
    daily = {"2026-08-20": 7}
    items = build_activity_series(daily, "month", date(2026, 8, 1))
    assert len(items) == 6
    assert items[0]["label"] == "2026-08"
    assert items[0]["count"] == 7
    assert items[-1]["label"] == "2027-01"


def test_month_rollover_year():
    # 起点 2025-12，近 6 个月应包含 2025-12, 2026-01 .. 2026-05
    items = build_activity_series({}, "month", date(2025, 12, 1))
    assert [i["label"] for i in items] == [
        "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05"
    ]


if __name__ == "__main__":
    tests = [v for n, v in globals().items() if n.startswith("test_") and callable(v)]
    for fn in sorted(tests, key=lambda f: f.__name__):
        fn()
        print("  PASS", fn.__name__)
    print("  %d passed" % len(tests))