"""月度汇率折算服务。

口径：
- 1 quote = N target，所以 amount(quote) * rate = amount(target)
- quote == target 时直通返回原值，不查表
- 缺月抛 MissingFxRate，不静默用上月（避免历史数据失真）
"""
from decimal import Decimal

from apps.analytics.models import FxRateMonthly


class MissingFxRate(Exception):
    """指定 (quote, target, month) 在 FxRateMonthly 中不存在。"""


def convert(amount: Decimal, quote_ccy: str, target_ccy: str, month: str) -> Decimal:
    if quote_ccy == target_ccy:
        return Decimal(amount)
    try:
        rate = FxRateMonthly.objects.get(
            quote_currency=quote_ccy,
            target_currency=target_ccy,
            month=month,
        ).rate
    except FxRateMonthly.DoesNotExist as exc:
        raise MissingFxRate(f"{quote_ccy}->{target_ccy} {month}") from exc
    return (Decimal(amount) * rate).quantize(Decimal("0.01"))
