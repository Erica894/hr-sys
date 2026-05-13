from django.core.management.base import BaseCommand
from django.db import transaction
from apps.iam.models import User, Role, UserRole, OrgUnit
from apps.hr_master.models import Employee, LegalEntity, CompensationRecord
from apps.compensation_plan.models import AdjustmentPlan, AdjustmentBudgetCell
from apps.lti.models import LTIPlan, LTIBudgetCell, StockPriceMonthly
from apps.reward_cycle.models import RewardCycle
from apps.approval.models import ApprovalChainTemplate


class Command(BaseCommand):
    help = "Seed Phase 1 demo data: users, 5 employees, RewardCycle, default chain"

    @transaction.atomic
    def handle(self, *args, **opts):
        company = OrgUnit.objects.get_or_create(code="HQ", defaults={"name": "总部", "type": "COMPANY"})[0]
        eng = OrgUnit.objects.get_or_create(
            code="ENG", defaults={"name": "Engineering", "type": "DEPT", "parent": company}
        )[0]
        prod = OrgUnit.objects.get_or_create(
            code="PROD", defaults={"name": "Product", "type": "DEPT", "parent": company}
        )[0]

        for code, name in [("EMPLOYEE", "员工"), ("DEPT_HEAD", "部门负责人"), ("HR_ADMIN", "薪酬HR")]:
            Role.objects.get_or_create(code=code, defaults={"name": name})

        entity = LegalEntity.objects.get_or_create(
            code="MAIN",
            defaults={"name": "主体公司", "country": "CN", "default_currency": "CNY"},
        )[0]

        hr_user, _ = User.objects.get_or_create(email="hr@demo.com", defaults={"employee_no": "HR001"})
        hr_user.set_password("demo1234")
        hr_user.save()
        UserRole.objects.get_or_create(
            user=hr_user, role=Role.objects.get(code="HR_ADMIN"),
            defaults={"scope_type": "GLOBAL"},
        )

        dh_user, _ = User.objects.get_or_create(email="depthead@demo.com", defaults={"employee_no": "D001"})
        dh_user.set_password("demo1234")
        dh_user.save()
        UserRole.objects.get_or_create(
            user=dh_user, role=Role.objects.get(code="DEPT_HEAD"),
            defaults={"scope_type": "DEPT", "scope_ref_id": eng.id},
        )

        employees = [
            dict(employee_no="E001", name_cn="陈爱丽", name_en="Alice Chen", email="alice@demo.com",
                 dept_name="Engineering", org_unit=eng, employee_category_1="MANAGEMENT",
                 is_promoted=True, job_level_current="P6", job_level_promoted="P7",
                 position_current="Senior Engineer", position_promoted="Lead Engineer",
                 promotion_category="VERTICAL", participates_annual_adjustment=True,
                 pay_currency="CNY", legal_entity=entity, monthly_salary=50000),
            dict(employee_no="E002", name_cn="王博", name_en="Bob Wang", email="bob@demo.com",
                 dept_name="Engineering", org_unit=eng, employee_category_1="STAFF",
                 is_promoted=False, job_level_current="P4", promotion_category="NONE",
                 participates_annual_adjustment=True, pay_currency="CNY", legal_entity=entity, monthly_salary=30000),
            dict(employee_no="E003", name_cn="刘佳", name_en="Carol Liu", email="carol@demo.com",
                 dept_name="Product", org_unit=prod, employee_category_1="MANAGEMENT",
                 is_promoted=False, job_level_current="P6", promotion_category="NONE",
                 participates_annual_adjustment=True, pay_currency="CNY", legal_entity=entity, monthly_salary=45000),
            dict(employee_no="E004", name_cn="张大卫", name_en="David Zhang", email="david@demo.com",
                 dept_name="Product", org_unit=prod, employee_category_1="STAFF",
                 is_promoted=True, job_level_current="P3", job_level_promoted="P4",
                 position_current="Junior", position_promoted="Engineer",
                 promotion_category="VERTICAL", participates_annual_adjustment=True,
                 pay_currency="CNY", legal_entity=entity, monthly_salary=25000),
            dict(employee_no="E005", name_cn="李悦", name_en="Eve Li", email="eve@demo.com",
                 dept_name="Engineering", org_unit=eng, employee_category_1="STAFF",
                 is_promoted=False, job_level_current="P3", promotion_category="NONE",
                 participates_annual_adjustment=True, pay_currency="CNY", legal_entity=entity, monthly_salary=28000),
        ]
        for ed in employees:
            monthly = ed.pop("monthly_salary")
            emp, _ = Employee.objects.update_or_create(employee_no=ed["employee_no"], defaults=ed)
            if not emp.compensation_records.exists():
                CompensationRecord.objects.create(
                    employee=emp, effective_date="2024-01-01",
                    base_salary=monthly, monthly_salary=monthly, currency="CNY",
                )
            u, _ = User.objects.get_or_create(email=ed["email"], defaults={"employee_no": ed["employee_no"]})
            u.set_password("demo1234")
            u.save()
            emp.user = u
            emp.save(update_fields=["user"])
            UserRole.objects.get_or_create(
                user=u, role=Role.objects.get(code="EMPLOYEE"),
                defaults={"scope_type": "SELF"},
            )

        StockPriceMonthly.objects.get_or_create(
            stock_code="DEMO", month="2026-01",
            defaults={"closing_price": "12.50", "currency": "USD", "source": "HR_LOCKED"},
        )

        ApprovalChainTemplate.objects.get_or_create(
            scenario="REWARD_CYCLE", is_default=True, status="ACTIVE",
            defaults={"name": "调薪+RSU默认链", "version": 1,
                      "nodes": [
                          {"code": "DEPT_HEAD", "role": "DEPT_HEAD", "scope": "DEPT_HEAD_OF(subject)", "optional": True},
                          {"code": "HR_ADMIN", "role": "HR_ADMIN", "scope": "GLOBAL", "optional": False},
                      ]},
        )

        cycle, _ = RewardCycle.objects.get_or_create(
            code="RC-2026-01",
            defaults={"name": "2026调薪+RSU", "period": "2026", "status": "DRAFT",
                      "total_comp_config": {"stock_price": "12.50", "stock_currency": "USD", "fx_usd_cny": "7.1"}},
        )

        adj_plan, _ = AdjustmentPlan.objects.get_or_create(
            code="ADJ-2026-01",
            defaults={"name": "2026调薪方案", "period": "2026", "status": "DRAFT",
                      "budget_total_cny": 500000, "reward_cycle": cycle},
        )
        if not cycle.linked_adjustment_plan:
            cycle.linked_adjustment_plan = adj_plan
            cycle.save(update_fields=["linked_adjustment_plan"])

        for t in ["ANNUAL", "PROMOTION"]:
            for c in ["MANAGEMENT", "STAFF"]:
                AdjustmentBudgetCell.objects.get_or_create(
                    reward_cycle=cycle, adjustment_type=t, employee_category_1=c,
                    defaults={"budget_amount_cny": 125000},
                )

        lti_plan, _ = LTIPlan.objects.get_or_create(
            code="RSU-2026-01",
            defaults={"name": "2026 RSU", "grant_date": "2026-03-01", "total_shares": 50000,
                      "unit_price_at_grant": "12.50", "stock_code": "DEMO", "cliff_months": 12,
                      "vesting_schedule": {"year1": 0.2, "year2": 0.2, "year3": 0.2, "year4": 0.2, "year5": 0.2},
                      "reward_cycle": cycle},
        )
        if not cycle.linked_lti_plan:
            cycle.linked_lti_plan = lti_plan
            cycle.save(update_fields=["linked_lti_plan"])

        for c in ["MANAGEMENT", "STAFF"]:
            LTIBudgetCell.objects.get_or_create(
                plan=lti_plan, employee_category_1=c,
                defaults={"headcount_quota": 3, "shares_quota_ads": 25000},
            )

        # 二级下发演示：把 ANNUAL/PROMOTION × MANAGEMENT/STAFF 公司池按人头切到 ENG/PROD
        from apps.compensation_plan.services.budget_distribution import (
            compute_distribution,
        )
        from decimal import Decimal as _D
        from apps.lti.models import LTIBudgetCell as _LtiCell

        target_ids = [eng.id, prod.id]
        for adj_type in ("ANNUAL", "PROMOTION"):
            for cat in ("MANAGEMENT", "STAFF"):
                company = AdjustmentBudgetCell.objects.get(
                    reward_cycle=cycle, adjustment_type=adj_type,
                    employee_category_1=cat, department__isnull=True,
                )
                dist = compute_distribution(
                    total=_D(company.budget_amount_cny),
                    cat1=cat, mode="HEADCOUNT",
                    target_unit_ids=target_ids,
                )
                if not dist:
                    continue
                for ou_id, amount in dist.items():
                    AdjustmentBudgetCell.objects.update_or_create(
                        reward_cycle=cycle, adjustment_type=adj_type,
                        employee_category_1=cat, department_id=ou_id,
                        defaults={"budget_amount_cny": amount},
                    )
                company.distribution_rule = "HEADCOUNT"
                company.save(update_fields=["distribution_rule"])

        for cat in ("MANAGEMENT", "STAFF"):
            company = _LtiCell.objects.get(
                plan=lti_plan, employee_category_1=cat, target_org_unit__isnull=True,
            )
            dist = compute_distribution(
                total=_D(company.shares_quota_ads),
                cat1=cat, mode="HEADCOUNT",
                target_unit_ids=target_ids, integer_units=True,
            )
            if not dist:
                continue
            for ou_id, shares in dist.items():
                _LtiCell.objects.update_or_create(
                    plan=lti_plan, employee_category_1=cat, target_org_unit_id=ou_id,
                    defaults={"shares_quota_ads": int(shares)},
                )
            company.distribution_rule = "HEADCOUNT"
            company.save(update_fields=["distribution_rule"])

        self.stdout.write(self.style.SUCCESS("Phase 1 seed loaded"))
        self.stdout.write(f"  RewardCycle ID: {cycle.id}")
        self.stdout.write("  HR Admin:  hr@demo.com / demo1234")
        self.stdout.write("  Dept Head: depthead@demo.com / demo1234")
        self.stdout.write("  Employees: alice/bob/carol/david/eve @demo.com / demo1234")
