"""分析模块只读 API。

四个入口：
- overview: 单年 5 列均值/中位数 + 头数
- by-dept: 双年部门维度 5 列 + 5 列 Δ%
- distribution: 周期内桶分布（LOW/IN_RANGE/HIGH × category）
- employee/{id}/timeline: 单员工 Y-1/Y/Y+1 三年三列时间线

数据范围：HR_ADMIN/SYS_ADMIN 全可见，DEPT_HEAD 仅本部门子树。
"""
from collections import defaultdict
from decimal import Decimal
from statistics import median

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.models import EmployeeCompensationSnapshot
from apps.analytics.permissions import scope_snapshot_qs
from apps.analytics.services.bucketing import (
    BUCKET_HIGH,
    BUCKET_IN_RANGE,
    BUCKET_LOW,
    bucket_by_matrix_tier,
)
from apps.analytics.services.delta import FIVE_COLS, compute_5col_delta
from apps.analytics.services.year_window import resolve_window
from apps.iam.models import OrgUnit
from apps.reward_cycle.models import RewardCycle


def _avg(values):
    if not values:
        return None
    return (sum(values) / Decimal(len(values))).quantize(Decimal("0.01"))


def _median(values):
    if not values:
        return None
    return Decimal(median(values)).quantize(Decimal("0.01"))


def _aggregate_5col(qs):
    """返回 {col: {avg, median}}，外加 headcount。"""
    rows = list(qs.values(*FIVE_COLS))
    out = {"headcount": len(rows)}
    for col in FIVE_COLS:
        vals = [Decimal(r[col] or 0) for r in rows]
        out[col] = {"avg": _avg(vals), "median": _median(vals)}
    return out


class AnalyticsOverview(APIView):
    """GET /api/analytics/overview/?year=2026"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            year = int(request.query_params.get("year", ""))
        except ValueError:
            return Response({"detail": "year required"}, status=status.HTTP_400_BAD_REQUEST)
        qs = scope_snapshot_qs(
            EmployeeCompensationSnapshot.objects.filter(year=year),
            request.user,
        )
        return Response({"year": year, **_aggregate_5col(qs)})


class AnalyticsByDept(APIView):
    """GET /api/analytics/by-dept/?year=2026&compare_year=2025"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            year = int(request.query_params.get("year", ""))
            compare = int(request.query_params.get("compare_year", ""))
        except ValueError:
            return Response(
                {"detail": "year + compare_year required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_qs = scope_snapshot_qs(
            EmployeeCompensationSnapshot.objects.filter(year__in=[year, compare]),
            request.user,
        )

        # group by org_unit_snapshot_id × year
        grouped: dict[tuple[int, int], list] = defaultdict(list)
        for snap in base_qs:
            grouped[(snap.org_unit_snapshot_id, snap.year)].append(snap)

        ou_ids = {k[0] for k in grouped if k[0] is not None}
        ou_names = dict(
            OrgUnit.objects.filter(id__in=ou_ids).values_list("id", "name")
        )

        rows = []
        for ou_id in ou_ids:
            row = {
                "org_unit_id": ou_id,
                "org_unit_name": ou_names.get(ou_id, ""),
                "headcount": len(grouped.get((ou_id, year), [])),
            }
            base_snaps = grouped.get((ou_id, compare), [])
            target_snaps = grouped.get((ou_id, year), [])
            for col in FIVE_COLS:
                base_avg = _avg([Decimal(getattr(s, col) or 0) for s in base_snaps])
                target_avg = _avg([Decimal(getattr(s, col) or 0) for s in target_snaps])
                if base_avg and target_avg and base_avg != 0:
                    delta = ((target_avg - base_avg) / base_avg).quantize(Decimal("0.0001"))
                else:
                    delta = None
                row[col] = {
                    "base_avg": base_avg, "target_avg": target_avg, "delta": delta,
                }
            rows.append(row)

        return Response({"year": year, "compare_year": compare, "rows": rows})


class AnalyticsDistribution(APIView):
    """GET /api/analytics/distribution/?cycle_id=N

    仅按 annual_fixed_cny 计算 Δ% 后落桶（v1 单列）。
    跨周期数据走年窗 (Y-1, Y) 对比。
    缺失矩阵或 0 基线 → UNKNOWN 桶。
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            cycle_id = int(request.query_params.get("cycle_id", ""))
        except ValueError:
            return Response({"detail": "cycle_id required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            cycle = RewardCycle.objects.get(id=cycle_id)
        except RewardCycle.DoesNotExist:
            return Response({"detail": "cycle not found"}, status=status.HTTP_404_NOT_FOUND)

        from apps.compensation_plan.models import AdjustmentMatrixCell
        y_minus_1, y, _ = resolve_window(cycle)

        target_qs = scope_snapshot_qs(
            EmployeeCompensationSnapshot.objects.filter(year=y).select_related("employee"),
            request.user,
        )

        matrix_by_key = {
            (c.category_id, c.perf_grade_code, c.pay_band): c
            for c in AdjustmentMatrixCell.objects.filter(reward_cycle=cycle)
        }

        # 简化：base_pct 5%、factor 1.0 — 真实 v1 应从规则推算，目前留位
        base_pct = Decimal("0.05")
        factor = Decimal("1.0")

        counts: dict[tuple[str, str], int] = defaultdict(int)
        for snap in target_qs:
            cat = snap.employee_category_1_snapshot or "STAFF"
            try:
                deltas = compute_5col_delta(snap.employee_id, y_minus_1, y)
            except LookupError:
                counts[(cat, "UNKNOWN")] += 1
                continue
            d = deltas.get("annual_fixed_cny")
            if d is None:
                counts[(cat, "UNKNOWN")] += 1
                continue
            cell = matrix_by_key.get(
                (None, snap.perf_grade_code, snap.pay_band)
            )
            if cell is None:
                # category lookup may differ; for v1 simplicity skip strict match
                counts[(cat, "UNKNOWN")] += 1
                continue
            bucket = bucket_by_matrix_tier(
                d, base_pct, factor, cell.coef_low, cell.coef_high
            )
            counts[(cat, bucket)] += 1

        rows = [
            {"category": cat, "bucket": b, "count": n}
            for (cat, b), n in counts.items()
        ]
        return Response({
            "cycle_id": cycle_id,
            "year_from": y_minus_1, "year_to": y,
            "buckets": [BUCKET_LOW, BUCKET_IN_RANGE, BUCKET_HIGH, "UNKNOWN"],
            "rows": rows,
        })


class EmployeeTimeline(APIView):
    """GET /api/analytics/employee/<id>/timeline/?cycle_id=N"""
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id):
        try:
            cycle_id = int(request.query_params.get("cycle_id", ""))
        except ValueError:
            return Response({"detail": "cycle_id required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            cycle = RewardCycle.objects.get(id=cycle_id)
        except RewardCycle.DoesNotExist:
            return Response({"detail": "cycle not found"}, status=status.HTTP_404_NOT_FOUND)

        years = resolve_window(cycle)
        qs = scope_snapshot_qs(
            EmployeeCompensationSnapshot.objects.filter(
                employee_id=employee_id, year__in=years
            ),
            request.user,
        )
        if not qs.exists():
            return Response({"detail": "no data in scope"}, status=status.HTTP_404_NOT_FOUND)

        by_year = {s.year: s for s in qs}
        out = []
        for y in years:
            s = by_year.get(y)
            if s is None:
                out.append({"year": y, "kind": None})
                continue
            out.append({
                "year": y,
                "kind": s.snapshot_kind,
                **{col: getattr(s, col) for col in FIVE_COLS},
            })
        return Response({"employee_id": employee_id, "timeline": out})
