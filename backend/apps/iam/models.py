from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    employee_no = models.CharField(max_length=32, unique=True)
    email = models.EmailField(unique=True)
    status = models.CharField(
        max_length=16,
        choices=[("ACTIVE", "Active"), ("INACTIVE", "Inactive"), ("LOCKED", "Locked")],
        default="ACTIVE",
    )
    mfa_enabled = models.BooleanField(default=False)
    totp_secret = models.CharField(max_length=64, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["employee_no"]

    class Meta:
        db_table = "iam_user"


class Role(models.Model):
    ROLE_CHOICES = [
        ("HR_ADMIN", "薪酬 HR"),
        ("DEPT_HEAD", "部门负责人"),
        ("CENTER_HEAD", "中心负责人"),
        ("GROUP_LEAD", "组长"),
        ("EMPLOYEE", "员工"),
        ("FINANCE", "财务"),
        ("AUDITOR", "审计员"),
        ("HRBP", "HRBP"),         # 兼容已存在的 fixture/测试
        ("EXEC", "高管"),          # 兼容
        ("SYS_ADMIN", "系统管理员"),  # 兼容
    ]
    code = models.CharField(max_length=32, unique=True, choices=ROLE_CHOICES)
    name = models.CharField(max_length=64)
    base_field_set = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "iam_role"


class OrgUnit(models.Model):
    TYPE_CHOICES = [
        ("COMPANY", "公司"),
        ("SUBSIDIARY", "分公司"),
        ("DEPT", "部门"),
        ("CENTER", "中心"),
        ("TEAM", "组"),
        ("EMPLOYEE_LEAF", "员工节点"),
    ]
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    leader_user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="主负责人冗余字段；兼任与多负责人通过 OrgUnitManager 表达",
    )

    class Meta:
        db_table = "iam_org_unit"


class UserRole(models.Model):
    SCOPE_CHOICES = [
        ("GLOBAL", "全局"),
        ("CHARGE", "分管范围"),
        ("DEPT", "部门"),
        ("CENTER", "中心"),
        ("SELF", "本人"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    scope_type = models.CharField(max_length=16, choices=SCOPE_CHOICES, default="SELF")
    scope_ref_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "iam_user_role"
        unique_together = [("user", "role", "scope_type", "scope_ref_id")]


class ManagementScope(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    owner_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="managed_scopes")
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=[("ACTIVE", "Active"), ("ARCHIVED", "Archived")], default="ACTIVE")

    class Meta:
        db_table = "iam_management_scope"


class ManagementScopeMember(models.Model):
    scope = models.ForeignKey(ManagementScope, on_delete=models.CASCADE, related_name="members")
    org_unit = models.ForeignKey(OrgUnit, on_delete=models.CASCADE)
    included_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "iam_management_scope_member"
        unique_together = [("scope", "org_unit")]


class FieldPermissionGrant(models.Model):
    """部门负责人 → 中心负责人 的字段级权限扩展授予。

    硬约束：grant 只能扩字段，永远不能扩数据范围（grantee 永远只看自己中心）。
    """
    STATUS_CHOICES = [("ACTIVE", "Active"), ("REVOKED", "Revoked")]

    granter = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="grants_issued",
        help_text="部门负责人 user_id",
    )
    grantee = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="grants_received",
        help_text="中心负责人 user_id",
    )
    center = models.ForeignKey(
        OrgUnit, on_delete=models.PROTECT, related_name="field_grants",
        help_text="被授权范围限定为此中心",
    )
    extra_fields = models.JSONField(default=list, help_text="必须是 RSU_FIELD_GROUP 子集")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="ACTIVE")
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "iam_field_permission_grant"
        constraints = [
            models.UniqueConstraint(
                fields=["grantee", "center"],
                condition=models.Q(status="ACTIVE"),
                name="uniq_active_grant_per_grantee_center",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        from apps.iam.constants import RSU_FIELD_GROUP

        if not isinstance(self.extra_fields, list):
            raise ValidationError({"extra_fields": "must be a list"})
        if not self.extra_fields:
            raise ValidationError({"extra_fields": "must be non-empty"})
        invalid = set(self.extra_fields) - set(RSU_FIELD_GROUP)
        if invalid:
            raise ValidationError({"extra_fields": f"fields outside RSU whitelist: {invalid}"})
        if self.center.type != "CENTER":
            raise ValidationError({"center": "grant scope must be a CENTER unit"})


class OrgUnitManager(models.Model):
    """组织单元负责人多对多表，支持兼任。

    一个 unit 可有 1 个 is_primary=True + N 个 is_primary=False（副 / 兼任）。
    一个 manager 可同时管多个 unit（兼任）。
    主任唯一性只在「当前生效」的记录上强制，历史记录 (effective_to 已结束) 不占位。
    """
    ROLE_IN_UNIT_CHOICES = [
        ("DEPT_HEAD", "部门负责人"),
        ("CENTER_HEAD", "中心负责人"),
        ("GROUP_LEAD", "组长"),
    ]

    org_unit = models.ForeignKey(
        OrgUnit, on_delete=models.CASCADE, related_name="managers"
    )
    manager = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="managed_units"
    )
    role_in_unit = models.CharField(max_length=16, choices=ROLE_IN_UNIT_CHOICES)
    is_primary = models.BooleanField(default=False)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "iam_org_unit_manager"
        constraints = [
            models.UniqueConstraint(
                fields=["org_unit"],
                condition=models.Q(is_primary=True, effective_to__isnull=True),
                name="uniq_active_primary_per_unit",
            ),
        ]


class MfaChallenge(models.Model):
    """MFA 验证挑战记录。

    敏感动作（登录 / 导出 / 终审 / 角色变更）发起时建一行 PENDING；
    用户提交 TOTP 后改 VERIFIED/FAILED；超过 expires_at 视为 EXPIRED。
    code 永远不存明文，只存哈希便于审计追溯。
    """
    PURPOSE_CHOICES = [
        ("LOGIN", "登录"),
        ("EXPORT", "导出敏感数据"),
        ("FINAL_APPROVE", "终审审批"),
        ("ROLE_ASSIGN", "角色变更"),
    ]
    STATUS_CHOICES = [
        ("PENDING", "待验证"),
        ("VERIFIED", "已通过"),
        ("FAILED", "失败"),
        ("EXPIRED", "已过期"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mfa_challenges")
    purpose = models.CharField(max_length=16, choices=PURPOSE_CHOICES)
    code_hash = models.CharField(max_length=128, blank=True, help_text="TOTP 不存明文")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="PENDING")
    attempts = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "iam_mfa_challenge"
        indexes = [models.Index(fields=["user", "status"])]

    @property
    def is_expired(self) -> bool:
        from django.utils import timezone
        return timezone.now() >= self.expires_at


class SessionRevocation(models.Model):
    """JWT 黑名单：登出 / 强制踢人 / MFA 失败连锁 / 角色变更等场景写入。

    业务层在 JWT 校验后查 `is_revoked(jti)`；过了 expires_at 的记录可被定时清理。
    expires_at 一般等于 token 的自然过期时间，过期后查询自动认为未撤销。
    """
    REASON_CHOICES = [
        ("LOGOUT", "用户登出"),
        ("ADMIN_KICK", "管理员强制下线"),
        ("MFA_FAIL", "MFA 连续失败"),
        ("ROLE_CHANGE", "角色变更"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="revocations")
    jti = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    reason = models.CharField(max_length=16, choices=REASON_CHOICES)
    revoked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "iam_session_revocation"

    @classmethod
    def is_revoked(cls, jti: str) -> bool:
        from django.utils import timezone
        return cls.objects.filter(jti=jti, expires_at__gt=timezone.now()).exists()
