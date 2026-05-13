"""OrgUnit 目标集校验与子树成员展开。

预算下发的目标必须互相不重叠：不能同时给 DEPT-A 和它的子节点 CENTER-A1 各开一
个 cell（会双重计数）。本模块提供一次性校验 + 成员查询。
"""
from typing import Iterable

from apps.iam.models import OrgUnit
from apps.hr_master.models import Employee


def _ancestor_ids(unit_id: int) -> list[int]:
    chain = []
    cur = OrgUnit.objects.filter(id=unit_id).values("parent_id").first()
    while cur and cur["parent_id"]:
        chain.append(cur["parent_id"])
        cur = OrgUnit.objects.filter(id=cur["parent_id"]).values("parent_id").first()
    return chain


def validate_target_set(org_unit_ids: Iterable[int]) -> None:
    """若任意两个 id 间存在祖先-后代关系则抛 ValueError。"""
    ids = list({int(i) for i in org_unit_ids})
    if len(ids) <= 1:
        return
    id_set = set(ids)
    for uid in ids:
        for anc in _ancestor_ids(uid):
            if anc in id_set:
                raise ValueError(
                    f"target set overlaps: {uid} is descendant of {anc}"
                )


def descendant_ids(unit_id: int) -> set[int]:
    """BFS 收集 unit 的所有子孙（含自身）。"""
    collected = {unit_id}
    frontier = [unit_id]
    while frontier:
        children = OrgUnit.objects.filter(parent_id__in=frontier).values_list("id", flat=True)
        new = set(children) - collected
        if not new:
            break
        collected.update(new)
        frontier = list(new)
    return collected


def members_under(unit_id: int):
    """该单元（含子树）下的所有 Employee QuerySet。"""
    sub = descendant_ids(unit_id)
    return Employee.objects.filter(org_unit_id__in=sub)


def resolve_owning_target(employee, target_ids: set[int]) -> int | None:
    """沿员工的 org_unit 向上找第一个落在 target_ids 中的祖先；找不到返 None。"""
    if not employee.org_unit_id:
        return None
    cur_id = employee.org_unit_id
    if cur_id in target_ids:
        return cur_id
    for anc in _ancestor_ids(cur_id):
        if anc in target_ids:
            return anc
    return None
