from decimal import Decimal

BUCKET_LOW = "LOW"
BUCKET_IN_RANGE = "IN_RANGE"
BUCKET_HIGH = "HIGH"


def compute_tier_interval(base_pct, factor, coef_low, coef_high):
    """返回 (区间下限, 区间上限) = base × factor × (coef_low, coef_high)."""
    base = Decimal(base_pct) * Decimal(factor)
    low = (base * Decimal(coef_low)).quantize(Decimal("0.0001"))
    high = (base * Decimal(coef_high)).quantize(Decimal("0.0001"))
    return low, high


def bucket_by_matrix_tier(actual_delta, base_pct, factor, coef_low, coef_high):
    """按矩阵区间把实际 Δ% 落桶 LOW / IN_RANGE / HIGH。"""
    low, high = compute_tier_interval(base_pct, factor, coef_low, coef_high)
    d = Decimal(actual_delta)
    if d < low:
        return BUCKET_LOW
    if d > high:
        return BUCKET_HIGH
    return BUCKET_IN_RANGE
