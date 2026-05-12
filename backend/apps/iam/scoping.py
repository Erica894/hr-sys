"""数据范围解析：取用户主管单元的子树并集。

数据范围是 IAM 体系的硬约束：任何外部 grant（如 FieldPermissionGrant）只能扩
「字段集」，永远不能扩这个集合。用户能查到的对象，必须 org_unit ∈ 子树并集。
"""
from datetime import date as _date
from typing import Iterable, Optional

from django.db.models import Q

from apps.iam.models import OrgUnit, OrgUnitManager, User


def _descendant_ids(root_ids: Iterable[int]) -> set[int]:
    """BFS 收集 root 集合的所有子孙 id（含自身）。"""
    collected = set(root_ids)
    frontier = list(collected)
    while frontier:
        children = OrgUnit.objects.filter(parent_id__in=frontier).values_list("id", flat=True)
        new = set(children) - collected
        if not new:
            break
        collected.update(new)
        frontier = list(new)
    return collected


def resolve_user_org_scope(user: User, as_of: Optional[_date] = None):
    """返回 user 在 as_of 日期下可见的所有 OrgUnit QuerySet。

    规则：
    - 取 OrgUnitManager 中所有当前生效的任命
      （effective_from <= as_of 且 (effective_to is null or effective_to > as_of)）
    - 对每个任命的 org_unit 展开整个子树
    - 合并去重
    """
    if as_of is None:
        as_of = _date.today()

    active_assignments = OrgUnitManager.objects.filter(
        manager=user,
        effective_from__lte=as_of,
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gt=as_of)
    )
    root_ids = list(active_assignments.values_list("org_unit_id", flat=True))
    if not root_ids:
        return OrgUnit.objects.none()

    all_ids = _descendant_ids(root_ids)
    return OrgUnit.objects.filter(id__in=all_ids)


class DataScopedQuerysetMixin:
    """供业务 ViewSet 复用：在 get_queryset 中调用 self.scope_to_org(qs, user)。

    子类需指定 `org_unit_field`（外键字段名，默认 'org_unit'）。
    superuser 不受范围限制；其他用户按 OrgUnitManager 任命收敛。
    """

    org_unit_field = "org_unit"

    def scope_to_org(self, qs, user):
        if getattr(user, "is_superuser", False):
            return qs
        scope = resolve_user_org_scope(user)
        return qs.filter(**{f"{self.org_unit_field}__in": scope})
