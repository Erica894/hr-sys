def resolve_window(cycle):
    """Return (Y-1, Y, Y+1) integer triple from cycle.period.

    cycle.period 必须是 4 位年份（"2026"）。其它格式抛 ValueError，
    避免静默把 "2026Q1" 之类切成 "2026" 后默默过去。
    """
    period = (cycle.period or "").strip()
    if len(period) != 4 or not period.isdigit():
        raise ValueError(f"cycle.period 不是 4 位年份: {period!r}")
    y = int(period)
    return (y - 1, y, y + 1)
