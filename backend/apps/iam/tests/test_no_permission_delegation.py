"""守护测试：PermissionDelegation 模型/表必须永远不出现。

spec 修订 2026-05-11 §1.4 已正式删除「权限委托」概念，改用 FieldPermissionGrant
表达「字段级扩授但数据范围不变」。本守护测试防止以后有人不读规范又把它加回来。
"""
import inspect

from apps.iam import models as iam_models


def test_permission_delegation_class_does_not_exist():
    assert not hasattr(iam_models, "PermissionDelegation"), (
        "PermissionDelegation must NOT be reintroduced; "
        "use FieldPermissionGrant for field-level grants without scope expansion"
    )


def test_no_db_table_named_iam_permission_delegation():
    for _, member in inspect.getmembers(iam_models, inspect.isclass):
        meta = getattr(member, "_meta", None)
        if meta is None:
            continue
        assert getattr(meta, "db_table", "") != "iam_permission_delegation", (
            f"{member.__name__} reuses the forbidden db_table 'iam_permission_delegation'"
        )
