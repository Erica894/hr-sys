"""IAM 共享常量：字段集白名单 + 角色基线字段集。

修改这些常量需要同步加迁移（Role.base_field_set 是数据库列）。
"""

# RSU 相关字段：默认对 CENTER_HEAD 不可见，可通过 FieldPermissionGrant 扩展
RSU_FIELD_GROUP = [
    "rsu_grant_amount",
    "rsu_vesting_schedule",
    "rsu_unvested_value",
    "rsu_strike_price",
    "rsu_grant_date",
]

# 现金分配相关字段：CENTER_HEAD 默认可见
CASH_FIELD_GROUP = [
    "base_salary",
    "monthly_salary",
    "annual_bonus_amount",
    "salary_adjustment_amount",
    "salary_adjustment_pct",
    "performance_rating",
    "level_band",
    "position_grade",
]

# 部门负责人字段集 = 现金 + RSU + 部门管理字段
DEPT_HEAD_EXTRA = [
    "rsu_grant_amount",
    "rsu_vesting_schedule",
    "rsu_unvested_value",
    "rsu_strike_price",
    "rsu_grant_date",
    "promotion_category",
    "department_budget_total",
    "department_budget_reserve",
]

# 7 常驻角色基线字段集
ROLE_BASE_FIELD_SETS = {
    "HR_ADMIN": CASH_FIELD_GROUP + DEPT_HEAD_EXTRA + ["audit_log", "all_company_view"],
    "DEPT_HEAD": CASH_FIELD_GROUP + DEPT_HEAD_EXTRA,
    "CENTER_HEAD": list(CASH_FIELD_GROUP),  # 默认不含 RSU
    "GROUP_LEAD": ["base_salary", "performance_rating", "level_band", "position_grade"],
    "EMPLOYEE": ["base_salary", "performance_rating", "annual_bonus_amount"],
    "FINANCE": CASH_FIELD_GROUP + ["payroll_export", "tax_breakdown"],
    "AUDITOR": CASH_FIELD_GROUP + DEPT_HEAD_EXTRA + ["audit_log_full"],
}
