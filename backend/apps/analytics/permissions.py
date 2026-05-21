"""分析模块数据范围：DEPT_HEAD 仅本部门可见，跨部门完全脱敏（决策 D）。

HR_ADMIN / SYS_ADMIN 全可见；DEPT_HEAD/CENTER_HEAD 走 OrgUnitManager 任命树。
"""
from apps.iam.scoping import resolve_user_org_scope


GLOBAL_ROLES = {"HR_ADMIN", "SYS_ADMIN"}


def is_global_visibility(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.roles.filter(role__code__in=GLOBAL_ROLES).exists()


def visible_org_unit_ids(user) -> set[int] | None:
    """返回用户可见的 org_unit_id 集合；None 表示无限制（全可见）。"""
    if is_global_visibility(user):
        return None
    scope_qs = resolve_user_org_scope(user)
    return set(scope_qs.values_list("id", flat=True))


def scope_snapshot_qs(qs, user):
    """对 EmployeeCompensationSnapshot 类查询应用数据范围。

    优先按 org_unit_snapshot_id（写入时冻结），跨部门脱敏。
    """
    ids = visible_org_unit_ids(user)
    if ids is None:
        return qs
    if not ids:
        return qs.none()
    return qs.filter(org_unit_snapshot_id__in=ids)
