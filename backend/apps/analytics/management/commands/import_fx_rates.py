"""导入月度汇率（Excel）。

列：quote_currency | target_currency | month | rate | note
重复 (quote, target, month) → upsert（更新 rate 与 note，source=IMPORT）。
"""
from decimal import Decimal, InvalidOperation

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.analytics.models import FxRateMonthly

COLS = {
    "quote_currency": 0,
    "target_currency": 1,
    "month": 2,
    "rate": 3,
    "note": 4,
}


class Command(BaseCommand):
    help = "Import monthly FX rates from Excel."

    def add_arguments(self, parser):
        parser.add_argument("file_path")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        path = options["file_path"]
        try:
            wb = openpyxl.load_workbook(path)
        except FileNotFoundError as e:
            raise CommandError(str(e))
        ws = wb.active

        created = updated = errors = 0
        with transaction.atomic():
            sp = transaction.savepoint()
            for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                if not row or row[0] is None:
                    continue
                quote = str(row[COLS["quote_currency"]]).strip().upper()
                target = str(row[COLS["target_currency"]]).strip().upper()
                month = str(row[COLS["month"]]).strip()
                try:
                    rate = Decimal(str(row[COLS["rate"]]))
                except (InvalidOperation, TypeError, ValueError):
                    self.stderr.write(f"row {idx}: rate 解析失败")
                    errors += 1
                    continue
                note = row[COLS["note"]] or ""
                _, c = FxRateMonthly.objects.update_or_create(
                    quote_currency=quote, target_currency=target, month=month,
                    defaults={"rate": rate, "note": str(note), "source": "IMPORT"},
                )
                if c:
                    created += 1
                else:
                    updated += 1

            if options["dry_run"]:
                transaction.savepoint_rollback(sp)
            else:
                transaction.savepoint_commit(sp)

        self.stdout.write(self.style.SUCCESS(
            f"created={created} updated={updated} errors={errors}"
        ))
