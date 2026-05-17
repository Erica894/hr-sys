"""导入年度快照（双用途）。

Excel 列顺序：
  employee_no | year | annual_fixed_cny | annual_bonus_cny | annual_rsu_value_cny
  | perf_grade_code | pay_band

用途：
1. 历史回填(Y-1)：5 列齐全 → 创建 ACTUAL 行，source=IMPORT
2. 当年实发奖金补录(Y)：仅 annual_bonus_cny 一列 → 在已存在的 DERIVED 行上
   覆盖 bonus + 重算 cash/total，固薪/RSU 不动；source 改为 DERIVED+MANUAL_BONUS

行解析规则：
- annual_fixed_cny / annual_rsu_value_cny 任一非空 → 视为"历史回填"模式
- 仅 annual_bonus_cny 非空 → 视为"补录奖金"模式
- 缺 employee_no/year → 报错收集到 stderr，不中断后续行
"""
from decimal import Decimal, InvalidOperation

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.analytics.models import EmployeeCompensationSnapshot
from apps.hr_master.models import Employee

COLS = {
    "employee_no": 0,
    "year": 1,
    "annual_fixed_cny": 2,
    "annual_bonus_cny": 3,
    "annual_rsu_value_cny": 4,
    "perf_grade_code": 5,
    "pay_band": 6,
}


def _dec(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


class Command(BaseCommand):
    help = "Import historical snapshots (Y-1 backfill) or actual bonus (Y bonus column)."

    def add_arguments(self, parser):
        parser.add_argument("file_path")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        path = options["file_path"]
        dry = options["dry_run"]
        try:
            wb = openpyxl.load_workbook(path)
        except FileNotFoundError as e:
            raise CommandError(str(e))
        ws = wb.active

        backfilled = bonus_updated = errors = 0
        with transaction.atomic():
            sp = transaction.savepoint()
            for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                if not row or row[COLS["employee_no"]] is None:
                    continue
                emp_no = str(row[COLS["employee_no"]]).strip()
                try:
                    year = int(row[COLS["year"]])
                except (ValueError, TypeError):
                    self.stderr.write(f"row {idx}: year 解析失败")
                    errors += 1
                    continue
                fixed = _dec(row[COLS["annual_fixed_cny"]])
                bonus = _dec(row[COLS["annual_bonus_cny"]])
                rsu = _dec(row[COLS["annual_rsu_value_cny"]])
                perf = (row[COLS["perf_grade_code"]] or "")
                band = (row[COLS["pay_band"]] or "")

                try:
                    emp = Employee.objects.get(employee_no=emp_no)
                except Employee.DoesNotExist:
                    self.stderr.write(f"row {idx}: 员工 {emp_no} 不存在")
                    errors += 1
                    continue

                is_backfill = fixed is not None or rsu is not None
                if is_backfill:
                    f = fixed or Decimal("0")
                    b = bonus or Decimal("0")
                    r = rsu or Decimal("0")
                    EmployeeCompensationSnapshot.objects.update_or_create(
                        employee=emp, year=year, snapshot_kind="ACTUAL",
                        defaults=dict(
                            annual_fixed_cny=f, annual_bonus_cny=b,
                            annual_rsu_value_cny=r,
                            annual_cash_cny=f + b,
                            annual_total_comp_cny=f + b + r,
                            perf_grade_code=str(perf),
                            pay_band=str(band),
                            employee_category_1_snapshot=emp.employee_category_1 or "",
                            org_unit_snapshot_id=emp.org_unit_id,
                            source="IMPORT",
                            derived_from_cycle=None,
                        ),
                    )
                    backfilled += 1
                else:
                    if bonus is None:
                        self.stderr.write(f"row {idx}: 没有任何金额列，跳过")
                        errors += 1
                        continue
                    try:
                        snap = EmployeeCompensationSnapshot.objects.get(
                            employee=emp, year=year, snapshot_kind="ACTUAL",
                        )
                    except EmployeeCompensationSnapshot.DoesNotExist:
                        self.stderr.write(
                            f"row {idx}: 补录奖金但 {emp_no}/{year}/ACTUAL 行不存在"
                        )
                        errors += 1
                        continue
                    snap.annual_bonus_cny = bonus
                    snap.annual_cash_cny = snap.annual_fixed_cny + bonus
                    snap.annual_total_comp_cny = snap.annual_cash_cny + snap.annual_rsu_value_cny
                    if "MANUAL_BONUS" not in snap.source:
                        snap.source = (
                            "DERIVED+MANUAL_BONUS" if snap.source == "DERIVED" else snap.source
                        )
                    snap.save()
                    bonus_updated += 1

            if dry:
                transaction.savepoint_rollback(sp)
            else:
                transaction.savepoint_commit(sp)

        self.stdout.write(self.style.SUCCESS(
            f"backfilled={backfilled} bonus_updated={bonus_updated} errors={errors} dry={dry}"
        ))
