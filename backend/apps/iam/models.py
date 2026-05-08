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
        ("EMPLOYEE", "员工"),
        ("DEPT_HEAD", "部门负责人"),
        ("CENTER_HEAD", "中心负责人"),
        ("HRBP", "HRBP"),
        ("HR_ADMIN", "薪酬 HR"),
        ("EXEC", "高管"),
        ("SYS_ADMIN", "系统管理员"),
    ]
    code = models.CharField(max_length=32, unique=True, choices=ROLE_CHOICES)
    name = models.CharField(max_length=64)

    class Meta:
        db_table = "iam_role"


class OrgUnit(models.Model):
    TYPE_CHOICES = [
        ("COMPANY", "公司"),
        ("SUBSIDIARY", "分公司"),
        ("DEPT", "部门"),
        ("CENTER", "中心"),
        ("TEAM", "组"),
    ]
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    leader_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

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
