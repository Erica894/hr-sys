"""按 cycle 派生年度快照。

用法：
  python manage.py build_current_snapshot --cycle-id=1                # ACTUAL，年=cycle.period 年
  python manage.py build_current_snapshot --cycle-id=1 --kind PROJECTED   # Y+1 预测
"""
from django.core.management.base import BaseCommand, CommandError

from apps.analytics.services.snapshot_builder import build_for_cycle
from apps.reward_cycle.models import RewardCycle


class Command(BaseCommand):
    help = "Build EmployeeCompensationSnapshot for a given cycle/year."

    def add_arguments(self, parser):
        parser.add_argument("--cycle-id", type=int, required=True)
        parser.add_argument(
            "--kind",
            choices=["ACTUAL", "PROJECTED"],
            default="ACTUAL",
            help="ACTUAL=Y, PROJECTED=Y+1",
        )

    def handle(self, *, cycle_id, kind, **opts):
        try:
            cycle = RewardCycle.objects.get(pk=cycle_id)
        except RewardCycle.DoesNotExist:
            raise CommandError(f"RewardCycle id={cycle_id} 不存在")

        try:
            base_year = int(str(cycle.period)[:4])
        except (ValueError, TypeError):
            raise CommandError(f"cycle.period={cycle.period!r} 无法解析为年份")

        year = base_year + (1 if kind == "PROJECTED" else 0)
        n = build_for_cycle(cycle, year=year, snapshot_kind=kind)
        self.stdout.write(self.style.SUCCESS(f"built {n} snapshots for {year}/{kind}"))
