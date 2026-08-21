"""学习活跃度时间窗口聚合（纯函数，无重型依赖，便于单元测试）。"""
from datetime import date, timedelta


def week_monday(d: date) -> date:
    """返回 d 所在周的周一（周一为一周起点）。"""
    return d - timedelta(days=d.weekday())


def build_activity_series(daily: dict, period: str, start: date) -> list:
    """把按日期聚合的 {iso_date: count} 汇总为日/周/月序列（纯函数，便于单测）。

    - daily: {"2026-08-20": 3, ...}
    - period: day(近14天) | week(近8周) | month(近6个月)
    - start: 期望序列的起始日期（含当天）
    返回按时间升序的 [{"label": str, "count": int}, ...]。
    """
    from calendar import monthrange

    result = []
    if period == "day":
        for i in range(14):
            d = start + timedelta(days=i)
            result.append({"label": d.strftime("%m-%d"), "count": daily.get(d.isoformat(), 0)})
    elif period == "week":
        for w in range(8):
            begin = start + timedelta(weeks=w)
            total = sum(daily.get((begin + timedelta(days=k)).isoformat(), 0) for k in range(7))
            result.append({
                "label": "%s~%s" % (begin.strftime("%m-%d"), (begin + timedelta(days=6)).strftime("%m-%d")),
                "count": total,
            })
    else:  # month: 近6个月（含当月）
        year, month = start.year, start.month
        for _ in range(6):
            ym = "%04d-%02d" % (year, month)
            _, last = monthrange(year, month)
            total = sum(
                daily.get("%04d-%02d-%02d" % (year, month, d), 0) for d in range(1, last + 1)
            )
            result.append({"label": ym, "count": total})
            month += 1
            if month > 12:
                month = 1
                year += 1
    return result