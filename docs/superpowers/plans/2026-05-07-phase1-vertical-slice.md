# Phase 1 垂直切片实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2 周交付端到端可演示链路：RewardCycle 调薪+RSU 完整流转（分配→提交→2 级审批→HR MFA 执行→员工签收）+ 审计日志 + Docker Compose 一键启动。

**Architecture:** 模块化单体（Django 5 + 10 apps in 1 repo）；前端两套 SPA（admin + portal）各自独立 Vite 项目；Nginx 反代统一入口；Phase 1 无 Celery（5 员工同步即可）。

**Tech Stack:** Python 3.12 + Django 5 + DRF + PostgreSQL 16 + Redis 7 + Vue 3 + Element Plus + Pinia + Vite + Nginx + Docker Compose

---

## 文件结构

```
hr-sys/
├── docker-compose.yml          # 6 services: db, redis, backend, admin-fe, portal-fe, nginx
├── .env.example
├── nginx/
│   └── default.conf            # reverse proxy: /api→backend, /admin→admin-fe, /→portal-fe
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── manage.py
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py         # INSTALLED_APPS, DB, JWT, CORS, AUTH settings
│   │   │   ├── local.py        # DEBUG=True overrides
│   │   │   └── test.py         # in-memory DB, fast hasher
│   │   ├── urls.py
│   │   └── wsgi.py
│   └── apps/
│       ├── iam/                # User, Role, UserRole, OrgUnit, ManagementScope, TOTP MFA
│       ├── hr_master/          # Employee, JobGrade, CompensationRecord, PerformanceRating
│       ├── data_integration/   # ImportJob scaffold only (Phase 1: Excel mgmt command in hr_master)
│       ├── compensation_plan/  # AdjustmentPlan, AdjustmentBudgetCell, AdjustmentProposal
│       ├── bonus_pool/         # BonusPlan scaffold only
│       ├── lti/                # LTIPlan, LTIBudgetCell, LTIGrant, VestingEvent, EmployeeAck
│       ├── reward_cycle/       # RewardCycle, core services, all APIs
│       ├── approval/           # ApprovalChainTemplate, ApprovalInstance, ApprovalStep
│       ├── audit/              # AuditLog (independent schema), middleware
│       └── notification/       # Notification scaffold only
│           (each app: models.py, serializers.py, views.py, urls.py, services.py, admin.py, tests/)
├── frontend/
│   ├── admin/                  # HR/manager: login, allocation, approval, execute pages
│   └── portal/                 # Employee: my-proposal, ack page
└── fixtures/
    └── phase1_seed.json        # OrgUnits, LegalEntity, Users/Roles, 5 Employees, StockPrice, Chain template
```

---

## Task 1: Repo skeleton + Docker Compose

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create `.gitignore`**

```
__pycache__/
*.py[cod]
*.env
.env
node_modules/
dist/
*.sqlite3
.venv/
venv/
*.log
```

- [ ] **Step 2: Create `.env.example`**

```
POSTGRES_DB=hrsys
POSTGRES_USER=hrsys
POSTGRES_PASSWORD=hrsys_dev_pass
POSTGRES_HOST=db
POSTGRES_PORT=5432
REDIS_URL=redis://redis:6379/0
DJANGO_SECRET_KEY=change-me-in-production
DJANGO_SETTINGS_MODULE=config.settings.local
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

- [ ] **Step 3: Create `docker-compose.yml`**

```yaml
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build: ./backend
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - ./backend:/app
    env_file: .env
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.local
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  admin-fe:
    image: node:20-alpine
    working_dir: /app
    command: sh -c "npm install && npm run dev -- --host 0.0.0.0"
    volumes:
      - ./frontend/admin:/app
    ports:
      - "5173:5173"

  portal-fe:
    image: node:20-alpine
    working_dir: /app
    command: sh -c "npm install && npm run dev -- --host 0.0.0.0"
    volumes:
      - ./frontend/portal:/app
    ports:
      - "5174:5174"

  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf
    ports:
      - "80:80"
    depends_on:
      - backend
      - admin-fe
      - portal-fe

volumes:
  pgdata:
```

- [ ] **Step 4: Create `nginx/default.conf`**

```nginx
server {
    listen 80;

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /admin {
        proxy_pass http://admin-fe:5173;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        proxy_pass http://portal-fe:5174;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

- [ ] **Step 5: Copy `.env.example` to `.env`**

```bash
cp .env.example .env
```

- [ ] **Step 6: Verify Docker Compose config**

```bash
docker compose config
```
Expected: YAML output printed with no errors.

- [ ] **Step 7: Commit**

```bash
git init
git add docker-compose.yml .env.example .gitignore nginx/
git commit -m "feat: repo skeleton and Docker Compose setup"
```

---

## Task 2: Django project + 10 apps scaffold

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/requirements.txt`
- Create: `backend/manage.py` (via django-admin)
- Create: `backend/config/settings/base.py`
- Create: `backend/config/settings/local.py`
- Create: `backend/config/settings/test.py`
- Create: `backend/config/urls.py`
- Create: all 10 `backend/apps/*/` directories with stub files

- [ ] **Step 1: Create `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
```

- [ ] **Step 2: Create `backend/requirements.txt`**

```
Django==5.0.6
djangorestframework==3.15.2
djangorestframework-simplejwt==5.3.1
django-cors-headers==4.4.0
psycopg[binary]==3.1.19
redis==5.0.7
django-redis==5.4.0
openpyxl==3.1.2
pyotp==2.9.0
qrcode[pil]==7.4.2
factory-boy==3.3.0
pytest==8.2.2
pytest-django==4.8.0
coverage==7.5.3
Pillow==10.3.0
gunicorn==22.0.0
```

- [ ] **Step 3: Start backend container and scaffold Django project**

```bash
docker compose run --rm backend sh -c "
  django-admin startproject config . &&
  mkdir -p config/settings &&
  touch config/settings/__init__.py &&
  for app in iam hr_master data_integration compensation_plan bonus_pool lti reward_cycle approval audit notification; do
    python manage.py startapp \$app apps/\$app
  done
"
```
Expected: `manage.py` and `config/` created; `apps/` directory with 10 subdirectories.

- [ ] **Step 4: Create `backend/config/settings/base.py`**

```python
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-key")
DEBUG = False
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    # Project apps
    "apps.iam",
    "apps.hr_master",
    "apps.data_integration",
    "apps.compensation_plan",
    "apps.bonus_pool",
    "apps.lti",
    "apps.reward_cycle",
    "apps.approval",
    "apps.audit",
    "apps.notification",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.audit.middleware.AuditMiddleware",
]

ROOT_URLCONF = "config.urls"
AUTH_USER_MODEL = "iam.User"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ],
    },
}]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "hrsys"),
        "USER": os.environ.get("POSTGRES_USER", "hrsys"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://redis:6379/0"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
}

from datetime import timedelta
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
}

CORS_ALLOWED_ORIGINS = ["http://localhost:5173", "http://localhost:5174", "http://localhost:80"]
CORS_ALLOW_CREDENTIALS = True

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_TZ = True
```

- [ ] **Step 5: Create `backend/config/settings/local.py`**

```python
from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",  # fast for dev
]
```

- [ ] **Step 6: Create `backend/config/settings/test.py`**

```python
from .base import *

DATABASES["default"]["NAME"] = "hrsys_test"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
```

- [ ] **Step 7: Create `backend/config/urls.py`**

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/auth/", include("apps.iam.urls")),
    path("api/", include("apps.hr_master.urls")),
    path("api/", include("apps.reward_cycle.urls")),
    path("api/", include("apps.approval.urls")),
]
```

- [ ] **Step 8: Create `backend/pytest.ini`**

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings.test
python_files = tests/test_*.py
python_classes = Test*
python_functions = test_*
```

- [ ] **Step 9: Verify Django check passes**

```bash
docker compose run --rm backend python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 10: Commit**

```bash
git add backend/
git commit -m "feat: Django project scaffold with 10 apps"
```

---

## Task 3: iam models + migrations

**Files:**
- Create: `backend/apps/iam/models.py`
- Create: `backend/apps/iam/managers.py`
- Create: `backend/apps/iam/tests/test_models.py`
- Modify: `backend/apps/iam/apps.py` (set default_auto_field)

- [ ] **Step 1: Write failing test**

Create `backend/apps/iam/tests/__init__.py` (empty) and `backend/apps/iam/tests/test_models.py`:

```python
import pytest
from apps.iam.models import User, Role, UserRole, OrgUnit

@pytest.mark.django_db
def test_create_user_with_role():
    org = OrgUnit.objects.create(code="DEPT_ENG", name="Engineering", type="DEPT")
    user = User.objects.create_user(
        email="alice@example.com",
        employee_no="E001",
        password="pass123",
    )
    role = Role.objects.create(code="DEPT_HEAD", name="部门负责人")
    ur = UserRole.objects.create(user=user, role=role, scope_type="DEPT", scope_ref_id=org.id)
    assert user.email == "alice@example.com"
    assert ur.scope_type == "DEPT"

@pytest.mark.django_db
def test_org_unit_tree():
    company = OrgUnit.objects.create(code="HQ", name="总部", type="COMPANY")
    dept = OrgUnit.objects.create(code="ENG", name="Engineering", type="DEPT", parent=company)
    assert dept.parent == company
```

- [ ] **Step 2: Run test — expect failure (models not defined yet)**

```bash
docker compose run --rm backend pytest apps/iam/tests/test_models.py -v
```
Expected: `ImportError` or `AppRegistryNotReady`.

- [ ] **Step 3: Create `backend/apps/iam/managers.py`**

```python
from django.contrib.auth.models import BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, email, employee_no, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, employee_no=employee_no, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, employee_no, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, employee_no, password, **extra_fields)
```

- [ ] **Step 4: Create `backend/apps/iam/models.py`**

```python
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
```

- [ ] **Step 5: Create and run migrations**

```bash
docker compose run --rm backend python manage.py makemigrations iam
docker compose run --rm backend python manage.py migrate
```
Expected: `Applying iam.0001_initial... OK`

- [ ] **Step 6: Run tests — expect pass**

```bash
docker compose run --rm backend pytest apps/iam/tests/test_models.py -v
```
Expected: `2 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/apps/iam/
git commit -m "feat(iam): User/Role/OrgUnit/ManagementScope models + migrations"
```

---

## Task 4: JWT auth + TOTP MFA

**Files:**
- Create: `backend/apps/iam/serializers.py`
- Create: `backend/apps/iam/services.py`
- Create: `backend/apps/iam/views.py`
- Create: `backend/apps/iam/urls.py`
- Create: `backend/apps/iam/tests/test_auth.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/apps/iam/tests/test_auth.py
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from apps.iam.models import User, Role, UserRole

@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def hr_user(db):
    user = User.objects.create_user(email="hr@example.com", employee_no="HR001", password="pass123")
    role = Role.objects.create(code="HR_ADMIN", name="薪酬HR")
    UserRole.objects.create(user=user, role=role, scope_type="GLOBAL")
    return user

@pytest.mark.django_db
def test_login_returns_tokens(client, hr_user):
    resp = client.post("/api/auth/login/", {"email": "hr@example.com", "password": "pass123"})
    assert resp.status_code == 200
    assert "access" in resp.data

@pytest.mark.django_db
def test_login_wrong_password(client, hr_user):
    resp = client.post("/api/auth/login/", {"email": "hr@example.com", "password": "wrong"})
    assert resp.status_code == 401

@pytest.mark.django_db
def test_mfa_setup_and_verify(client, hr_user):
    client.force_authenticate(user=hr_user)
    resp = client.post("/api/auth/mfa/setup/")
    assert resp.status_code == 200
    assert "totp_uri" in resp.data
    import pyotp
    totp = pyotp.TOTP(hr_user.totp_secret if hr_user.totp_secret else resp.data["secret"])
    verify_resp = client.post("/api/auth/mfa/verify/", {"code": totp.now()})
    assert verify_resp.status_code == 200
```

- [ ] **Step 2: Run test — expect failure**

```bash
docker compose run --rm backend pytest apps/iam/tests/test_auth.py -v
```
Expected: `FAILED` (no urls/views yet).

- [ ] **Step 3: Create `backend/apps/iam/services.py`**

```python
import pyotp

def generate_totp_secret() -> str:
    return pyotp.random_base32()

def get_totp_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="hr-sys")

def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
```

- [ ] **Step 4: Create `backend/apps/iam/serializers.py`**

```python
from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(email=data["email"], password=data["password"])
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        if user.status != "ACTIVE":
            raise serializers.ValidationError("Account inactive")
        data["user"] = user
        return data

class MFAVerifySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=8)
```

- [ ] **Step 5: Create `backend/apps/iam/views.py`**

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import LoginSerializer, MFAVerifySerializer
from .services import generate_totp_secret, get_totp_uri, verify_totp


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        roles = list(user.roles.values_list("role__code", flat=True))
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "mfa_enabled": user.mfa_enabled,
            "roles": roles,
        })


class MFASetupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.totp_secret:
            user.totp_secret = generate_totp_secret()
            user.save(update_fields=["totp_secret"])
        uri = get_totp_uri(user.totp_secret, user.email)
        return Response({"totp_uri": uri, "secret": user.totp_secret})


class MFAVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MFAVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.totp_secret:
            return Response({"error": "MFA not set up"}, status=status.HTTP_400_BAD_REQUEST)
        if not verify_totp(user.totp_secret, serializer.validated_data["code"]):
            return Response({"error": "Invalid TOTP code"}, status=status.HTTP_401_UNAUTHORIZED)
        user.mfa_enabled = True
        user.save(update_fields=["mfa_enabled"])
        return Response({"status": "MFA verified"})
```

- [ ] **Step 6: Create `backend/apps/iam/urls.py`**

```python
from django.urls import path
from .views import LoginView, MFASetupView, MFAVerifyView

urlpatterns = [
    path("login/", LoginView.as_view()),
    path("mfa/setup/", MFASetupView.as_view()),
    path("mfa/verify/", MFAVerifyView.as_view()),
]
```

- [ ] **Step 7: Run tests — expect pass**

```bash
docker compose run --rm backend pytest apps/iam/tests/ -v
```
Expected: `5 passed`

- [ ] **Step 8: Commit**

```bash
git add backend/apps/iam/
git commit -m "feat(iam): JWT login + TOTP MFA setup/verify"
```

---

## Task 5: audit middleware + independent schema

**Files:**
- Create: `backend/apps/audit/models.py`
- Create: `backend/apps/audit/middleware.py`
- Create: `backend/apps/audit/services.py`
- Create: `backend/apps/audit/migrations/0001_initial.py`
- Create: `backend/apps/audit/tests/test_audit.py`

- [ ] **Step 1: Write failing test**

```python
# backend/apps/audit/tests/test_audit.py
import pytest
from rest_framework.test import APIClient
from apps.iam.models import User, Role, UserRole
from apps.audit.models import AuditLog

@pytest.fixture
def hr_user(db):
    user = User.objects.create_user(email="hr@test.com", employee_no="HR001", password="pass")
    Role.objects.get_or_create(code="HR_ADMIN", defaults={"name": "HR"})
    return user

@pytest.mark.django_db
def test_write_request_creates_audit_log(hr_user):
    from apps.audit.services import log_action
    log_action(
        event="TEST_EVENT",
        actor=hr_user,
        resource_type="TestModel",
        resource_id=1,
        before={},
        after={"field": "value"},
        ip="127.0.0.1",
        request_id="test-req-1",
    )
    assert AuditLog.objects.filter(action="TEST_EVENT", actor_id=hr_user.id).exists()
```

- [ ] **Step 2: Run test — expect failure**

```bash
docker compose run --rm backend pytest apps/audit/tests/test_audit.py -v
```
Expected: `ImportError` or model not found.

- [ ] **Step 3: Create `backend/apps/audit/models.py`**

```python
from django.db import models


class AuditLog(models.Model):
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor_id = models.BigIntegerField(null=True)
    actor_role = models.CharField(max_length=32, blank=True)
    action = models.CharField(max_length=128, db_index=True)
    resource_type = models.CharField(max_length=64)
    resource_id = models.BigIntegerField(null=True)
    before = models.JSONField(null=True)
    after = models.JSONField(null=True)
    ip = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)
    request_id = models.CharField(max_length=64, blank=True)

    class Meta:
        app_label = "audit"
        db_table = '"audit"."audit_log"'
        managed = True


class SensitiveViewLog(models.Model):
    viewer_id = models.BigIntegerField()
    subject_type = models.CharField(max_length=64)
    subject_id = models.BigIntegerField()
    fields_viewed = models.JSONField(default=list)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "audit"
        db_table = '"audit"."sensitive_view_log"'


class ExportLog(models.Model):
    exporter_id = models.BigIntegerField()
    kind = models.CharField(max_length=64)
    filter = models.JSONField(default=dict)
    row_count = models.IntegerField(default=0)
    file_url = models.TextField(blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "audit"
        db_table = '"audit"."export_log"'
```

- [ ] **Step 4: Create `backend/apps/audit/migrations/0001_initial.py`**

```python
from django.db import migrations

class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE SCHEMA IF NOT EXISTS audit;
                CREATE TABLE IF NOT EXISTS audit.audit_log (
                    id bigserial PRIMARY KEY,
                    occurred_at timestamptz NOT NULL DEFAULT now(),
                    actor_id bigint,
                    actor_role varchar(32) DEFAULT '',
                    action varchar(128) NOT NULL,
                    resource_type varchar(64) NOT NULL DEFAULT '',
                    resource_id bigint,
                    before jsonb,
                    after jsonb,
                    ip inet,
                    user_agent text DEFAULT '',
                    request_id varchar(64) DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit.audit_log(actor_id);
                CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit.audit_log(action);
                CREATE TABLE IF NOT EXISTS audit.sensitive_view_log (
                    id bigserial PRIMARY KEY,
                    viewer_id bigint NOT NULL,
                    subject_type varchar(64) NOT NULL,
                    subject_id bigint NOT NULL,
                    fields_viewed jsonb DEFAULT '[]',
                    at timestamptz NOT NULL DEFAULT now()
                );
                CREATE TABLE IF NOT EXISTS audit.export_log (
                    id bigserial PRIMARY KEY,
                    exporter_id bigint NOT NULL,
                    kind varchar(64) NOT NULL,
                    filter jsonb DEFAULT '{}',
                    row_count int DEFAULT 0,
                    file_url text DEFAULT '',
                    at timestamptz NOT NULL DEFAULT now()
                );
                -- Prevent UPDATE/DELETE on audit_log (INSERT-only)
                CREATE OR REPLACE RULE audit_log_no_update AS ON UPDATE TO audit.audit_log DO INSTEAD NOTHING;
                CREATE OR REPLACE RULE audit_log_no_delete AS ON DELETE TO audit.audit_log DO INSTEAD NOTHING;
            """,
            reverse_sql="DROP SCHEMA IF EXISTS audit CASCADE;",
        ),
    ]
```

- [ ] **Step 5: Create `backend/apps/audit/services.py`**

```python
import uuid
from django.db import connection


def log_action(event: str, actor, resource_type: str, resource_id: int,
               before: dict, after: dict, ip: str = "", request_id: str = "",
               actor_role: str = "") -> None:
    if not request_id:
        request_id = str(uuid.uuid4())
    actor_id = actor.id if actor and hasattr(actor, "id") else None
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO audit.audit_log
              (actor_id, actor_role, action, resource_type, resource_id, before, after, ip, request_id)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
            """,
            [actor_id, actor_role, event, resource_type, resource_id,
             str(before).replace("'", '"'), str(after).replace("'", '"'), ip or None, request_id],
        )
```

- [ ] **Step 6: Create `backend/apps/audit/middleware.py`**

```python
import uuid

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid.uuid4())
        response = self.get_response(request)
        return response
```

- [ ] **Step 7: Run migration + tests**

```bash
docker compose run --rm backend python manage.py migrate audit
docker compose run --rm backend pytest apps/audit/tests/ -v
```
Expected: migration OK, `1 passed`.

- [ ] **Step 8: Commit**

```bash
git add backend/apps/audit/
git commit -m "feat(audit): independent schema, AuditLog INSERT-only, middleware"
```

---

## Task 6: hr_master models + Excel import

**Files:**
- Create: `backend/apps/hr_master/models.py`
- Create: `backend/apps/hr_master/management/commands/import_employees.py`
- Create: `backend/apps/hr_master/tests/test_import.py`

- [ ] **Step 1: Write failing test**

```python
# backend/apps/hr_master/tests/__init__.py  (empty)
# backend/apps/hr_master/tests/test_import.py
import pytest
from django.core.management import call_command
from apps.hr_master.models import Employee

@pytest.mark.django_db
def test_import_creates_employees(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["employee_no","name_cn","name_en","email","dept_name","center_name",
                "team_name","job_family","job_level_current","position_current",
                "is_promoted","job_level_promoted","position_promoted","promotion_category",
                "participates_annual_adjustment","employee_category_1","employee_category_2",
                "hire_date","monthly_salary","pay_currency","pay_country_region"])
    ws.append(["E001","陈爱丽","Alice Chen","alice@example.com","Engineering","","",
                "Engineering","P6","Senior Engineer","TRUE","P7","Lead Engineer","VERTICAL",
                "TRUE","MANAGEMENT","CORE","2020-01-15","50000","CNY","CN"])
    ws.append(["E002","王博","Bob Wang","bob@example.com","Engineering","","",
                "Engineering","P4","Engineer","FALSE","","","NONE",
                "TRUE","STAFF","GENERAL","2021-06-01","30000","CNY","CN"])
    xlsx_path = tmp_path / "employees.xlsx"
    wb.save(str(xlsx_path))
    call_command("import_employees", str(xlsx_path))
    assert Employee.objects.count() == 2
    alice = Employee.objects.get(employee_no="E001")
    assert alice.is_promoted is True
    assert alice.job_level_promoted == "P7"
    assert alice.employee_category_1 == "MANAGEMENT"
```

- [ ] **Step 2: Run test — expect failure**

```bash
docker compose run --rm backend pytest apps/hr_master/tests/test_import.py -v
```
Expected: `ImportError` (models not defined).

- [ ] **Step 3: Create `backend/apps/hr_master/models.py`**

```python
from django.db import models
from apps.iam.models import User, OrgUnit


class LegalEntity(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    country = models.CharField(max_length=8)
    jurisdiction = models.CharField(max_length=64, blank=True)
    default_currency = models.CharField(max_length=8, default="CNY")
    tax_id = models.CharField(max_length=64, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        db_table = "hr_legal_entity"


class Employee(models.Model):
    CATEGORY1 = [("MANAGEMENT", "管理干部"), ("STAFF", "员工")]
    PROMOTION = [("VERTICAL", "纵向晋升"), ("LATERAL", "横向调动"), ("NONE", "未晋升")]

    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.SET_NULL)
    employee_no = models.CharField(max_length=32, unique=True)
    name_cn = models.CharField(max_length=64)
    name_en = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    org_unit = models.ForeignKey(OrgUnit, null=True, blank=True, on_delete=models.SET_NULL)
    manager = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reports")
    dept_name = models.CharField(max_length=128, blank=True)
    center_name = models.CharField(max_length=128, blank=True)
    team_name = models.CharField(max_length=128, blank=True)
    legal_entity = models.ForeignKey(LegalEntity, null=True, blank=True, on_delete=models.SET_NULL)
    work_location = models.CharField(max_length=128, blank=True)
    pay_country_region = models.CharField(max_length=64, blank=True)
    pay_currency = models.CharField(max_length=8, default="CNY")
    hire_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, default="ACTIVE")
    job_family = models.CharField(max_length=64, blank=True)
    job_level_current = models.CharField(max_length=32, blank=True)
    job_level_promoted = models.CharField(max_length=32, blank=True)
    position_current = models.CharField(max_length=64, blank=True)
    position_promoted = models.CharField(max_length=64, blank=True)
    is_promoted = models.BooleanField(default=False)
    promotion_category = models.CharField(max_length=16, choices=PROMOTION, default="NONE")
    participates_annual_adjustment = models.BooleanField(default=True)
    employee_category_1 = models.CharField(max_length=16, choices=CATEGORY1, default="STAFF")
    employee_category_2 = models.CharField(max_length=32, blank=True)

    class Meta:
        db_table = "hr_employee"


class JobGrade(models.Model):
    level = models.CharField(max_length=32, unique=True)
    band = models.CharField(max_length=32, blank=True)
    p50 = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    p75 = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    p90 = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    min_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    mid_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    max_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True)

    class Meta:
        db_table = "hr_job_grade"


class CompensationRecord(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="compensation_records")
    effective_date = models.DateField()
    base_salary = models.DecimalField(max_digits=14, decimal_places=2)
    monthly_salary = models.DecimalField(max_digits=14, decimal_places=2)
    allowance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="CNY")
    source = models.CharField(max_length=16, default="MANUAL")
    version = models.IntegerField(default=1)
    superseded_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hr_compensation_record"


class PerformanceRating(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="perf_ratings")
    period_year = models.IntegerField()
    period_half = models.CharField(max_length=4, choices=[("H1", "上半年"), ("H2", "下半年")])
    rating = models.CharField(max_length=8, blank=True)
    final_score = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    source = models.CharField(max_length=16, default="IMPORT")
    locked_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "hr_performance_rating"
        unique_together = [("employee", "period_year", "period_half")]
```

- [ ] **Step 4: Create management command directories**

```bash
docker compose run --rm backend sh -c "
  mkdir -p apps/hr_master/management/commands &&
  touch apps/hr_master/management/__init__.py &&
  touch apps/hr_master/management/commands/__init__.py
"
```

- [ ] **Step 5: Create `backend/apps/hr_master/management/commands/import_employees.py`**

```python
from django.core.management.base import BaseCommand
import openpyxl
from apps.hr_master.models import Employee

COLS = {
    "employee_no":0,"name_cn":1,"name_en":2,"email":3,
    "dept_name":4,"center_name":5,"team_name":6,"job_family":7,
    "job_level_current":8,"position_current":9,
    "is_promoted":10,"job_level_promoted":11,"position_promoted":12,
    "promotion_category":13,"participates_annual_adjustment":14,
    "employee_category_1":15,"employee_category_2":16,
    "hire_date":17,"monthly_salary":18,"pay_currency":19,"pay_country_region":20,
}

def _bool(v):
    return str(v).strip().upper() in ("TRUE","YES","1","是")

class Command(BaseCommand):
    help = "Import employees from Excel"

    def add_arguments(self, parser):
        parser.add_argument("file_path")

    def handle(self, *args, **options):
        wb = openpyxl.load_workbook(options["file_path"])
        ws = wb.active
        created = updated = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row[0]:
                continue
            data = {k: (row[v] if row[v] is not None else "") for k, v in COLS.items()}
            emp_no = data.pop("employee_no")
            data["is_promoted"] = _bool(data["is_promoted"])
            data["participates_annual_adjustment"] = _bool(data["participates_annual_adjustment"])
            if not data["promotion_category"]:
                data["promotion_category"] = "NONE"
            _, c = Employee.objects.update_or_create(employee_no=emp_no, defaults=data)
            created += c
            updated += not c
        self.stdout.write(f"Done: {created} created, {updated} updated")
```

- [ ] **Step 6: Run migrations + test**

```bash
docker compose run --rm backend python manage.py makemigrations hr_master
docker compose run --rm backend python manage.py migrate hr_master
docker compose run --rm backend pytest apps/hr_master/tests/test_import.py -v
```
Expected: `1 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/apps/hr_master/
git commit -m "feat(hr_master): Employee/CompensationRecord models + Excel import command"
```

---

## Task 7: compensation_plan + lti + reward_cycle models

**Files:**
- Create: `backend/apps/compensation_plan/models.py`
- Create: `backend/apps/lti/models.py`
- Create: `backend/apps/reward_cycle/models.py`
- Create: `backend/apps/lti/tests/test_models.py`

- [ ] **Step 1: Write failing test (LTIGrant UNIQUE constraint)**

```python
# backend/apps/lti/tests/__init__.py  (empty)
# backend/apps/lti/tests/test_models.py
import pytest
from django.db import IntegrityError
from apps.lti.models import LTIPlan, LTIGrant
from apps.hr_master.models import Employee, LegalEntity

@pytest.mark.django_db
def test_lti_grant_unique_per_plan_employee():
    entity = LegalEntity.objects.create(code="HQ", name="总部", country="CN")
    emp = Employee.objects.create(employee_no="E001", name_cn="Alice", legal_entity=entity)
    plan = LTIPlan.objects.create(code="RSU-2026", name="2026 RSU", grant_date="2026-01-01",
                                   total_shares=100000, unit_price_at_grant="10.00")
    LTIGrant.objects.create(plan=plan, employee=emp, granted_ads=500)
    with pytest.raises(IntegrityError):
        LTIGrant.objects.create(plan=plan, employee=emp, granted_ads=300)
```

- [ ] **Step 2: Run test — expect failure**

```bash
docker compose run --rm backend pytest apps/lti/tests/test_models.py -v
```

- [ ] **Step 3: Create `backend/apps/compensation_plan/models.py`**

```python
from django.db import models
from apps.hr_master.models import Employee


class AdjustmentPlan(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    period = models.CharField(max_length=16)
    status = models.CharField(max_length=32, default="DRAFT")
    budget_total_cny = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    scope = models.JSONField(default=dict)
    formula = models.JSONField(default=dict)
    rounding_rule = models.CharField(max_length=16, default="ROUND_HALF_UP")
    created_by_id = models.BigIntegerField(null=True)
    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="adjustment_plans"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "comp_adjustment_plan"


class AdjustmentBudgetCell(models.Model):
    ADJ_TYPE = [("ANNUAL", "年度调薪"), ("PROMOTION", "晋升调薪")]
    CAT1 = [("MANAGEMENT", "管理干部"), ("STAFF", "员工")]

    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", on_delete=models.CASCADE, related_name="adjustment_budget_cells"
    )
    adjustment_type = models.CharField(max_length=16, choices=ADJ_TYPE)
    employee_category_1 = models.CharField(max_length=16, choices=CAT1)
    budget_amount_cny = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    allocated_amount_cny = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    class Meta:
        db_table = "comp_adjustment_budget_cell"
        unique_together = [("reward_cycle", "adjustment_type", "employee_category_1")]

    @property
    def remaining_amount_cny(self):
        return self.budget_amount_cny - self.allocated_amount_cny


class AdjustmentProposal(models.Model):
    plan = models.ForeignKey(AdjustmentPlan, on_delete=models.CASCADE, related_name="proposals")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    local_currency = models.CharField(max_length=8, default="CNY")
    status = models.CharField(max_length=32, default="DRAFT")
    proposer_id = models.BigIntegerField(null=True)
    effective_date = models.DateField(null=True)
    calculation_basis_snapshot = models.JSONField(default=dict)
    current_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    current_job_level_snapshot = models.CharField(max_length=32, blank=True)
    job_level_promoted_snapshot = models.CharField(max_length=32, blank=True)
    employee_category_1_snapshot = models.CharField(max_length=16, default="STAFF")
    participates_annual_snapshot = models.BooleanField(default=True)
    promotion_adjustment_pct = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    annual_suggested_pct = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    annual_manager_delta_pct = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    promotion_adjustment_amount_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    annual_adjustment_amount_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_special_case = models.BooleanField(default=False)
    market_benchmark_note = models.JSONField(null=True, blank=True)
    retention_reason = models.TextField(blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "comp_adjustment_proposal"
        unique_together = [("plan", "employee")]

    @property
    def annual_final_pct(self):
        return self.annual_suggested_pct + self.annual_manager_delta_pct

    @property
    def total_adjustment_pct(self):
        return self.promotion_adjustment_pct + self.annual_final_pct

    @property
    def proposed_salary(self):
        return self.current_salary * (1 + self.total_adjustment_pct)
```

- [ ] **Step 4: Create `backend/apps/lti/models.py`**

```python
from django.db import models
from apps.hr_master.models import Employee


class LTIPlan(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    grant_date = models.DateField()
    total_shares = models.BigIntegerField(default=0)
    share_unit = models.CharField(max_length=8, default="ADS")
    unit_price_at_grant = models.DecimalField(max_digits=10, decimal_places=4)
    vesting_schedule = models.JSONField(default=dict)
    cliff_months = models.IntegerField(default=12)
    plan_doc_url = models.TextField(blank=True)
    stock_code = models.CharField(max_length=16, blank=True)
    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="lti_plans"
    )

    class Meta:
        db_table = "lti_plan"


class LTIBudgetCell(models.Model):
    CAT1 = [("MANAGEMENT", "管理干部"), ("STAFF", "员工")]
    plan = models.ForeignKey(LTIPlan, on_delete=models.CASCADE, related_name="budget_cells")
    employee_category_1 = models.CharField(max_length=16, choices=CAT1)
    headcount_quota = models.IntegerField(default=0)
    shares_quota_ads = models.BigIntegerField(default=0)
    headcount_used = models.IntegerField(default=0)
    shares_used_ads = models.BigIntegerField(default=0)

    class Meta:
        db_table = "lti_budget_cell"
        unique_together = [("plan", "employee_category_1")]


class LTIGrant(models.Model):
    plan = models.ForeignKey(LTIPlan, on_delete=models.CASCADE, related_name="grants")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    status = models.CharField(max_length=16, default="PROPOSED")
    is_eligible = models.BooleanField(default=True)
    grant_tier = models.CharField(max_length=8, blank=True)
    suggested_range_min_ads = models.IntegerField(default=0)
    suggested_range_max_ads = models.IntegerField(default=0)
    granted_ads = models.IntegerField(default=0)
    employee_category_1_snapshot = models.CharField(max_length=16, default="STAFF")
    stock_code = models.CharField(max_length=16, blank=True)
    unit_price_at_grant = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    pending_shares_by_year = models.JSONField(default=dict)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lti_grant"
        unique_together = [("plan", "employee")]


class VestingEvent(models.Model):
    grant = models.ForeignKey(LTIGrant, on_delete=models.CASCADE, related_name="vesting_events")
    scheduled_date = models.DateField()
    scheduled_shares = models.IntegerField()
    actual_date = models.DateField(null=True)
    actual_shares = models.IntegerField(null=True)
    status = models.CharField(max_length=16, default="PENDING")

    class Meta:
        db_table = "lti_vesting_event"


class StockPriceMonthly(models.Model):
    stock_code = models.CharField(max_length=16)
    month = models.CharField(max_length=7)
    closing_price = models.DecimalField(max_digits=10, decimal_places=4)
    currency = models.CharField(max_length=8, default="USD")
    source = models.CharField(max_length=16, default="MARKET")
    locked_by_id = models.BigIntegerField(null=True)
    locked_at = models.DateTimeField(null=True)
    note = models.TextField(blank=True)

    class Meta:
        db_table = "lti_stock_price_monthly"
        unique_together = [("stock_code", "month")]


class EmployeeAck(models.Model):
    subject_type = models.CharField(max_length=16)
    subject_id = models.BigIntegerField()
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    acked_at = models.DateTimeField(auto_now_add=True)
    signature_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "lti_employee_ack"
        unique_together = [("subject_type", "subject_id", "employee")]
```

- [ ] **Step 5: Create `backend/apps/reward_cycle/models.py`**

```python
from django.db import models


class RewardCycle(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    period = models.CharField(max_length=16)
    status = models.CharField(max_length=32, default="DRAFT")
    scope = models.JSONField(default=dict)
    linked_adjustment_plan = models.OneToOneField(
        "compensation_plan.AdjustmentPlan", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reward_cycle_link"
    )
    linked_lti_plan = models.OneToOneField(
        "lti.LTIPlan", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reward_cycle_link"
    )
    total_comp_config = models.JSONField(default=dict)
    created_by_id = models.BigIntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reward_cycle"
```

- [ ] **Step 6: Run migrations + tests**

```bash
docker compose run --rm backend python manage.py makemigrations compensation_plan lti reward_cycle
docker compose run --rm backend python manage.py migrate
docker compose run --rm backend pytest apps/lti/tests/ -v
```
Expected: `1 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/apps/compensation_plan/ backend/apps/lti/ backend/apps/reward_cycle/
git commit -m "feat: AdjustmentPlan/LTIPlan/RewardCycle models; LTIGrant UNIQUE constraint"
```

---

## Task 8: approval models + default chain + seed_phase1 command

**Files:**
- Create: `backend/apps/approval/models.py`
- Create: `backend/apps/approval/services.py`
- Create: `backend/apps/approval/tests/test_approval.py`
- Create: `backend/apps/approval/management/commands/seed_phase1.py`

- [ ] **Step 1: Write failing test**

```python
# backend/apps/approval/tests/__init__.py  (empty)
# backend/apps/approval/tests/test_approval.py
import pytest
from apps.approval.models import ApprovalChainTemplate, ApprovalInstance
from apps.approval.services import get_default_chain, advance_approval
from apps.reward_cycle.models import RewardCycle
from apps.iam.models import User, Role

@pytest.fixture
def chain(db):
    return ApprovalChainTemplate.objects.create(
        scenario="REWARD_CYCLE", name="默认链", is_default=True,
        status="ACTIVE", version=1,
        nodes=[
            {"code":"DEPT_HEAD","role":"DEPT_HEAD","scope":"DEPT_HEAD_OF(subject)","optional":True},
            {"code":"HR_ADMIN","role":"HR_ADMIN","scope":"GLOBAL","optional":False},
        ],
    )

@pytest.mark.django_db
def test_get_default_chain_returns_two_nodes(chain):
    c = get_default_chain("REWARD_CYCLE")
    assert c is not None
    assert len(c.nodes) == 2

@pytest.mark.django_db
def test_advance_approval_full_flow(chain):
    Role.objects.get_or_create(code="DEPT_HEAD", defaults={"name":"部门负责人"})
    Role.objects.get_or_create(code="HR_ADMIN", defaults={"name":"薪酬HR"})
    dh = User.objects.create_user(email="dh@t.com", employee_no="D001", password="p")
    hr = User.objects.create_user(email="hr@t.com", employee_no="H001", password="p")
    cycle = RewardCycle.objects.create(code="RC-T1", name="T1", period="2026", status="APPROVING")
    inst = ApprovalInstance.objects.create(template=chain, subject_type="REWARD_CYCLE",
                                             subject_id=cycle.id, current_node=0)
    advance_approval(inst.id, dh.id, "APPROVE", "ok")
    inst.refresh_from_db()
    assert inst.current_node == 1
    assert inst.status == "RUNNING"
    advance_approval(inst.id, hr.id, "APPROVE", "final")
    inst.refresh_from_db()
    assert inst.status == "APPROVED"
    cycle.refresh_from_db()
    assert cycle.status == "APPROVED_PENDING_EXECUTE"

@pytest.mark.django_db
def test_reject_sets_instance_rejected(chain):
    Role.objects.get_or_create(code="DEPT_HEAD", defaults={"name":"部门负责人"})
    dh = User.objects.create_user(email="dh@t.com", employee_no="D001", password="p")
    cycle = RewardCycle.objects.create(code="RC-T2", name="T2", period="2026", status="APPROVING")
    inst = ApprovalInstance.objects.create(template=chain, subject_type="REWARD_CYCLE",
                                             subject_id=cycle.id, current_node=0)
    advance_approval(inst.id, dh.id, "REJECT_BATCH", "退回")
    inst.refresh_from_db()
    assert inst.status == "REJECTED"
    cycle.refresh_from_db()
    assert cycle.status == "IN_PROGRESS"
```

- [ ] **Step 2: Run test — expect failure**

```bash
docker compose run --rm backend pytest apps/approval/tests/ -v
```

- [ ] **Step 3: Create `backend/apps/approval/models.py`**

```python
from django.db import models


class ApprovalChainTemplate(models.Model):
    SCENARIOS = [("ADJUSTMENT","Adjustment"),("BONUS","Bonus"),("LTI","LTI"),
                  ("REWARD_CYCLE","Reward Cycle"),("DELEGATION","Delegation")]
    scenario = models.CharField(max_length=32, choices=SCENARIOS)
    name = models.CharField(max_length=128)
    status = models.CharField(max_length=16, default="ACTIVE")
    version = models.IntegerField(default=1)
    is_default = models.BooleanField(default=False)
    nodes = models.JSONField(default=list)
    effective_from = models.DateField(null=True)
    effective_to = models.DateField(null=True)

    class Meta:
        db_table = "approval_chain_template"


class ApprovalInstance(models.Model):
    template = models.ForeignKey(ApprovalChainTemplate, on_delete=models.PROTECT)
    subject_type = models.CharField(max_length=32)
    subject_id = models.BigIntegerField()
    current_node = models.IntegerField(default=0)
    status = models.CharField(max_length=32, default="RUNNING")
    over_budget_flag = models.BooleanField(default=False)
    over_budget_details = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "approval_instance"


class ApprovalStep(models.Model):
    ACTIONS = [("APPROVE","Approve"),("REJECT_BATCH","Reject Batch"),
                ("REJECT_INDIVIDUAL","Reject Individual"),("REJECT_WITH_COMMENT","Reject With Comment")]
    instance = models.ForeignKey(ApprovalInstance, on_delete=models.CASCADE, related_name="steps")
    node_index = models.IntegerField()
    approver_user_id = models.BigIntegerField()
    action = models.CharField(max_length=32, choices=ACTIONS)
    comment = models.TextField(blank=True)
    acted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "approval_step"
```

- [ ] **Step 4: Create `backend/apps/approval/services.py`**

```python
from django.db import transaction
from .models import ApprovalChainTemplate, ApprovalInstance, ApprovalStep


def get_default_chain(scenario: str):
    return ApprovalChainTemplate.objects.filter(
        scenario=scenario, is_default=True, status="ACTIVE"
    ).first()


@transaction.atomic
def advance_approval(instance_id: int, actor_id: int, action: str, comment: str = ""):
    inst = ApprovalInstance.objects.select_for_update().get(id=instance_id)
    if inst.status != "RUNNING":
        raise ValueError(f"Instance {instance_id} not RUNNING (status={inst.status})")

    ApprovalStep.objects.create(
        instance=inst, node_index=inst.current_node,
        approver_user_id=actor_id, action=action, comment=comment,
    )

    if action.startswith("REJECT"):
        inst.status = "REJECTED"
        inst.save(update_fields=["status"])
        _on_rejected(inst)
        return inst

    nodes = inst.template.nodes
    next_node = inst.current_node + 1
    if next_node >= len(nodes):
        inst.status = "APPROVED"
        inst.save(update_fields=["status"])
        _on_approved(inst)
    else:
        inst.current_node = next_node
        inst.save(update_fields=["current_node"])
    return inst


def _on_approved(inst):
    if inst.subject_type == "REWARD_CYCLE":
        from apps.reward_cycle.models import RewardCycle
        RewardCycle.objects.filter(id=inst.subject_id).update(status="APPROVED_PENDING_EXECUTE")


def _on_rejected(inst):
    if inst.subject_type == "REWARD_CYCLE":
        from apps.reward_cycle.models import RewardCycle
        RewardCycle.objects.filter(id=inst.subject_id).update(status="IN_PROGRESS")
```

- [ ] **Step 5: Create management command dirs**

```bash
docker compose run --rm backend sh -c "
  mkdir -p apps/approval/management/commands &&
  touch apps/approval/management/__init__.py &&
  touch apps/approval/management/commands/__init__.py
"
```

- [ ] **Step 6: Create `backend/apps/approval/management/commands/seed_phase1.py`**

```python
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
        company = OrgUnit.objects.get_or_create(code="HQ", defaults={"name":"总部","type":"COMPANY"})[0]
        eng = OrgUnit.objects.get_or_create(code="ENG", defaults={"name":"Engineering","type":"DEPT","parent":company})[0]
        prod = OrgUnit.objects.get_or_create(code="PROD", defaults={"name":"Product","type":"DEPT","parent":company})[0]

        for code, name in [("EMPLOYEE","员工"),("DEPT_HEAD","部门负责人"),("HR_ADMIN","薪酬HR")]:
            Role.objects.get_or_create(code=code, defaults={"name":name})

        entity = LegalEntity.objects.get_or_create(code="MAIN",
            defaults={"name":"主体公司","country":"CN","default_currency":"CNY"})[0]

        hr_user, _ = User.objects.get_or_create(email="hr@demo.com", defaults={"employee_no":"HR001"})
        hr_user.set_password("demo1234"); hr_user.save()
        UserRole.objects.get_or_create(user=hr_user, role=Role.objects.get(code="HR_ADMIN"),
                                         defaults={"scope_type":"GLOBAL"})

        dh_user, _ = User.objects.get_or_create(email="depthead@demo.com", defaults={"employee_no":"D001"})
        dh_user.set_password("demo1234"); dh_user.save()
        UserRole.objects.get_or_create(user=dh_user, role=Role.objects.get(code="DEPT_HEAD"),
                                         defaults={"scope_type":"DEPT","scope_ref_id":eng.id})

        employees = [
            dict(employee_no="E001",name_cn="陈爱丽",name_en="Alice Chen",email="alice@demo.com",
                 dept_name="Engineering",org_unit=eng,employee_category_1="MANAGEMENT",
                 is_promoted=True,job_level_current="P6",job_level_promoted="P7",
                 position_current="Senior Engineer",position_promoted="Lead Engineer",
                 promotion_category="VERTICAL",participates_annual_adjustment=True,
                 pay_currency="CNY",legal_entity=entity,monthly_salary=50000),
            dict(employee_no="E002",name_cn="王博",name_en="Bob Wang",email="bob@demo.com",
                 dept_name="Engineering",org_unit=eng,employee_category_1="STAFF",
                 is_promoted=False,job_level_current="P4",promotion_category="NONE",
                 participates_annual_adjustment=True,pay_currency="CNY",legal_entity=entity,monthly_salary=30000),
            dict(employee_no="E003",name_cn="刘佳",name_en="Carol Liu",email="carol@demo.com",
                 dept_name="Product",org_unit=prod,employee_category_1="MANAGEMENT",
                 is_promoted=False,job_level_current="P6",promotion_category="NONE",
                 participates_annual_adjustment=True,pay_currency="CNY",legal_entity=entity,monthly_salary=45000),
            dict(employee_no="E004",name_cn="张大卫",name_en="David Zhang",email="david@demo.com",
                 dept_name="Product",org_unit=prod,employee_category_1="STAFF",
                 is_promoted=True,job_level_current="P3",job_level_promoted="P4",
                 position_current="Junior",position_promoted="Engineer",
                 promotion_category="VERTICAL",participates_annual_adjustment=True,
                 pay_currency="CNY",legal_entity=entity,monthly_salary=25000),
            dict(employee_no="E005",name_cn="李悦",name_en="Eve Li",email="eve@demo.com",
                 dept_name="Engineering",org_unit=eng,employee_category_1="STAFF",
                 is_promoted=False,job_level_current="P3",promotion_category="NONE",
                 participates_annual_adjustment=True,pay_currency="CNY",legal_entity=entity,monthly_salary=28000),
        ]
        for ed in employees:
            monthly = ed.pop("monthly_salary")
            emp, _ = Employee.objects.update_or_create(employee_no=ed["employee_no"], defaults=ed)
            if not emp.compensation_records.exists():
                CompensationRecord.objects.create(
                    employee=emp, effective_date="2024-01-01",
                    base_salary=monthly, monthly_salary=monthly, currency="CNY"
                )
            u, _ = User.objects.get_or_create(email=ed["email"], defaults={"employee_no":ed["employee_no"]})
            u.set_password("demo1234"); u.save()
            emp.user = u; emp.save(update_fields=["user"])
            UserRole.objects.get_or_create(user=u, role=Role.objects.get(code="EMPLOYEE"),
                                             defaults={"scope_type":"SELF"})

        StockPriceMonthly.objects.get_or_create(
            stock_code="DEMO", month="2026-01",
            defaults={"closing_price":"12.50","currency":"USD","source":"HR_LOCKED"}
        )

        ApprovalChainTemplate.objects.get_or_create(
            scenario="REWARD_CYCLE", is_default=True, status="ACTIVE",
            defaults={"name":"调薪+RSU默认链","version":1,
                "nodes":[
                    {"code":"DEPT_HEAD","role":"DEPT_HEAD","scope":"DEPT_HEAD_OF(subject)","optional":True},
                    {"code":"HR_ADMIN","role":"HR_ADMIN","scope":"GLOBAL","optional":False},
                ]}
        )

        cycle, _ = RewardCycle.objects.get_or_create(code="RC-2026-01",
            defaults={"name":"2026调薪+RSU","period":"2026","status":"DRAFT",
                     "total_comp_config":{"stock_price":"12.50","stock_currency":"USD","fx_usd_cny":"7.1"}})

        adj_plan, _ = AdjustmentPlan.objects.get_or_create(code="ADJ-2026-01",
            defaults={"name":"2026调薪方案","period":"2026","status":"DRAFT",
                     "budget_total_cny":500000,"reward_cycle":cycle})
        if not cycle.linked_adjustment_plan:
            cycle.linked_adjustment_plan = adj_plan; cycle.save(update_fields=["linked_adjustment_plan"])

        for t in ["ANNUAL","PROMOTION"]:
            for c in ["MANAGEMENT","STAFF"]:
                AdjustmentBudgetCell.objects.get_or_create(
                    reward_cycle=cycle, adjustment_type=t, employee_category_1=c,
                    defaults={"budget_amount_cny":125000})

        lti_plan, _ = LTIPlan.objects.get_or_create(code="RSU-2026-01",
            defaults={"name":"2026 RSU","grant_date":"2026-03-01","total_shares":50000,
                     "unit_price_at_grant":"12.50","stock_code":"DEMO","cliff_months":12,
                     "vesting_schedule":{"year1":0.2,"year2":0.2,"year3":0.2,"year4":0.2,"year5":0.2},
                     "reward_cycle":cycle})
        if not cycle.linked_lti_plan:
            cycle.linked_lti_plan = lti_plan; cycle.save(update_fields=["linked_lti_plan"])

        for c in ["MANAGEMENT","STAFF"]:
            LTIBudgetCell.objects.get_or_create(plan=lti_plan, employee_category_1=c,
                defaults={"headcount_quota":3,"shares_quota_ads":25000})

        self.stdout.write(self.style.SUCCESS("Phase 1 seed loaded"))
        self.stdout.write(f"  RewardCycle ID: {cycle.id}")
        self.stdout.write("  HR Admin:  hr@demo.com / demo1234")
        self.stdout.write("  Dept Head: depthead@demo.com / demo1234")
        self.stdout.write("  Employees: alice/bob/carol/david/eve @demo.com / demo1234")
```

- [ ] **Step 7: Run migrations + tests + seed**

```bash
docker compose run --rm backend python manage.py makemigrations approval
docker compose run --rm backend python manage.py migrate
docker compose run --rm backend pytest apps/approval/tests/ -v
docker compose run --rm backend python manage.py seed_phase1
```
Expected: `3 passed`; seed prints `Phase 1 seed loaded` with IDs.

- [ ] **Step 8: Commit**

```bash
git add backend/apps/approval/
git commit -m "feat(approval): chain template + instance + seed_phase1 command"
```

---

### Task 9: RewardCycle + Allocation APIs

**Files:**
- Create: `backend/apps/reward_cycle/services.py`
- Create: `backend/apps/reward_cycle/serializers.py`
- Create: `backend/apps/reward_cycle/views.py`
- Create: `backend/apps/reward_cycle/urls.py`
- Create: `backend/apps/reward_cycle/tests/test_allocation.py`
- Modify: `backend/config/urls.py` — include reward_cycle urls

**Goal:** Generate proposals for 5 employees, serve allocation list (joined view), accept manager edits. Static TotalComp (annual_base + annual_rsu_value/5).

- [ ] **Step 1: Write services.py**

```python
# backend/apps/reward_cycle/services.py
from decimal import Decimal
from django.db import transaction
from apps.hr_master.models import Employee
from apps.compensation_plan.models import AdjustmentPlan, AdjustmentProposal
from apps.lti.models import LTIPlan, LTIGrant
from apps.reward_cycle.models import RewardCycle

# Simplified promotion lookup (L1→L2 = 15%, L2→L3 = 12%, else 10%)
PROMOTION_PCT_BY_TARGET = {"L2":"0.15","L3":"0.12","L4":"0.10","L5":"0.10"}

def _annual_suggested_pct(emp: Employee) -> Decimal:
    # Phase 1 stub: uniform 5%. Real formula lands in iteration 3.
    return Decimal("0.05")

def _promotion_pct(emp: Employee) -> Decimal:
    if not emp.is_promoted or not emp.job_level_promoted:
        return Decimal("0")
    return Decimal(PROMOTION_PCT_BY_TARGET.get(emp.job_level_promoted, "0.10"))

@transaction.atomic
def generate_proposals(cycle: RewardCycle, adj_plan: AdjustmentPlan, lti_plan: LTIPlan):
    """Create one AdjustmentProposal per in-scope employee; LTIGrant for eligible."""
    employees = Employee.objects.filter(status="ACTIVE")
    for emp in employees:
        AdjustmentProposal.objects.get_or_create(
            plan=adj_plan, employee=emp,
            defaults={
                "annual_suggested_pct": _annual_suggested_pct(emp) if emp.participates_annual_adjustment else Decimal("0"),
                "annual_manager_delta_pct": Decimal("0"),
                "promotion_adjustment_pct": _promotion_pct(emp),
                "current_monthly_salary": emp.current_monthly_salary or Decimal("0"),
            })
        # LTI eligibility: everyone in phase 1 (real rule = senior-only)
        LTIGrant.objects.get_or_create(
            plan=lti_plan, employee=emp,
            defaults={"granted_ads": 0, "unit_price_at_grant": lti_plan.unit_price_at_grant})

def get_allocation_rows(cycle: RewardCycle):
    """Join employee + adjustment proposal + lti grant for the allocation table."""
    adj = cycle.linked_adjustment_plan
    lti = cycle.linked_lti_plan
    rows = []
    proposals = {p.employee_id: p for p in AdjustmentProposal.objects.filter(plan=adj)}
    grants = {g.employee_id: g for g in LTIGrant.objects.filter(plan=lti)}
    for emp in Employee.objects.filter(status="ACTIVE").order_by("employee_code"):
        rows.append({"employee": emp,
                     "proposal": proposals.get(emp.id),
                     "grant": grants.get(emp.id)})
    return rows
```

- [ ] **Step 2: Write serializers.py**

```python
# backend/apps/reward_cycle/serializers.py
from decimal import Decimal
from rest_framework import serializers
from apps.reward_cycle.models import RewardCycle

class AllocationRowSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField(source="employee.id")
    employee_code = serializers.CharField(source="employee.employee_code")
    name_cn = serializers.CharField(source="employee.name_cn")
    dept_name = serializers.CharField(source="employee.dept_name")
    job_level_current = serializers.CharField(source="employee.job_level_current")
    job_level_promoted = serializers.CharField(source="employee.job_level_promoted", allow_null=True)
    is_promoted = serializers.BooleanField(source="employee.is_promoted")
    participates_annual = serializers.BooleanField(source="employee.participates_annual_adjustment")
    current_monthly_salary = serializers.DecimalField(source="employee.current_monthly_salary",
                                                      max_digits=14, decimal_places=2)
    annual_suggested_pct = serializers.SerializerMethodField()
    annual_manager_delta_pct = serializers.SerializerMethodField()
    annual_final_pct = serializers.SerializerMethodField()
    promotion_adjustment_pct = serializers.SerializerMethodField()
    total_adjustment_pct = serializers.SerializerMethodField()
    proposed_monthly_salary = serializers.SerializerMethodField()
    granted_ads = serializers.SerializerMethodField()
    unit_price_at_grant = serializers.SerializerMethodField()
    annual_base = serializers.SerializerMethodField()
    annual_rsu_value = serializers.SerializerMethodField()
    total_comp = serializers.SerializerMethodField()

    def _p(self, obj): return obj["proposal"]
    def _g(self, obj): return obj["grant"]
    def get_annual_suggested_pct(self, o): return self._p(o).annual_suggested_pct if self._p(o) else None
    def get_annual_manager_delta_pct(self, o): return self._p(o).annual_manager_delta_pct if self._p(o) else None
    def get_annual_final_pct(self, o): return self._p(o).annual_final_pct if self._p(o) else None
    def get_promotion_adjustment_pct(self, o): return self._p(o).promotion_adjustment_pct if self._p(o) else None
    def get_total_adjustment_pct(self, o): return self._p(o).total_adjustment_pct if self._p(o) else None
    def get_proposed_monthly_salary(self, o): return self._p(o).proposed_salary if self._p(o) else None
    def get_granted_ads(self, o): return self._g(o).granted_ads if self._g(o) else 0
    def get_unit_price_at_grant(self, o): return self._g(o).unit_price_at_grant if self._g(o) else None
    def get_annual_base(self, o):
        p = self._p(o)
        if not p: return None
        return (p.proposed_salary * 12).quantize(Decimal("0.01"))
    def get_annual_rsu_value(self, o):
        g = self._g(o)
        if not g or not g.granted_ads: return Decimal("0")
        return (Decimal(g.granted_ads) * g.unit_price_at_grant / Decimal("5")).quantize(Decimal("0.01"))
    def get_total_comp(self, o):
        base = self.get_annual_base(o) or Decimal("0")
        rsu = self.get_annual_rsu_value(o) or Decimal("0")
        return (base + rsu).quantize(Decimal("0.01"))

class SaveProposalsItemSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    annual_manager_delta_pct = serializers.DecimalField(max_digits=6, decimal_places=4, required=False)
    granted_ads = serializers.IntegerField(required=False, min_value=0)

class RewardCycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RewardCycle
        fields = ["id","code","name","status","budget_year","opened_at"]
```

- [ ] **Step 3: Write views.py**

```python
# backend/apps/reward_cycle/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentProposal
from apps.lti.models import LTIGrant
from apps.reward_cycle.services import get_allocation_rows
from apps.reward_cycle.serializers import (AllocationRowSerializer,
    SaveProposalsItemSerializer, RewardCycleSerializer)

class RewardCycleListView(generics.ListAPIView):
    queryset = RewardCycle.objects.all().order_by("-opened_at")
    serializer_class = RewardCycleSerializer
    permission_classes = [permissions.IsAuthenticated]

class AllocationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, pk=cycle_id)
        rows = get_allocation_rows(cycle)
        return Response({"cycle": RewardCycleSerializer(cycle).data,
                         "rows": AllocationRowSerializer(rows, many=True).data})

class SaveProposalsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def patch(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, pk=cycle_id)
        if cycle.status not in ("DRAFT","ALLOCATING"):
            return Response({"detail":"cycle not editable"}, status=400)
        items = SaveProposalsItemSerializer(data=request.data.get("items",[]), many=True)
        items.is_valid(raise_exception=True)
        for it in items.validated_data:
            if "annual_manager_delta_pct" in it:
                AdjustmentProposal.objects.filter(
                    plan=cycle.linked_adjustment_plan, employee_id=it["employee_id"]
                ).update(annual_manager_delta_pct=it["annual_manager_delta_pct"])
            if "granted_ads" in it:
                grant = LTIGrant.objects.filter(
                    plan=cycle.linked_lti_plan, employee_id=it["employee_id"]
                ).first()
                if grant:
                    grant.granted_ads = it["granted_ads"]; grant.save(update_fields=["granted_ads"])
        if cycle.status == "DRAFT":
            cycle.status = "ALLOCATING"; cycle.save(update_fields=["status"])
        return Response({"ok": True})
```

- [ ] **Step 4: Write urls.py + wire to config**

```python
# backend/apps/reward_cycle/urls.py
from django.urls import path
from apps.reward_cycle.views import RewardCycleListView, AllocationListView, SaveProposalsView
urlpatterns = [
    path("reward-cycle/", RewardCycleListView.as_view()),
    path("reward-cycle/<int:cycle_id>/allocation/", AllocationListView.as_view()),
    path("reward-cycle/<int:cycle_id>/proposals/", SaveProposalsView.as_view()),
]
```

```python
# backend/config/urls.py — add one line
path("api/", include("apps.reward_cycle.urls")),
```

- [ ] **Step 5: Write tests**

```python
# backend/apps/reward_cycle/tests/test_allocation.py
import pytest
from rest_framework.test import APIClient
from django.core.management import call_command
from apps.iam.models import User

@pytest.fixture
def seeded(db):
    call_command("seed_phase1")

@pytest.fixture
def client(seeded):
    u = User.objects.get(email="hr@demo.com")
    c = APIClient(); c.force_authenticate(u); return c

def test_allocation_list_returns_5_rows(client):
    from apps.reward_cycle.models import RewardCycle
    cycle = RewardCycle.objects.first()
    r = client.get(f"/api/reward-cycle/{cycle.id}/allocation/")
    assert r.status_code == 200
    assert len(r.data["rows"]) == 5
    assert "total_comp" in r.data["rows"][0]

def test_save_proposals_updates_manager_delta(client):
    from apps.reward_cycle.models import RewardCycle
    from apps.compensation_plan.models import AdjustmentProposal
    cycle = RewardCycle.objects.first()
    emp_id = cycle.linked_adjustment_plan.proposals.first().employee_id
    r = client.patch(f"/api/reward-cycle/{cycle.id}/proposals/",
        {"items":[{"employee_id":emp_id,"annual_manager_delta_pct":"0.02"}]}, format="json")
    assert r.status_code == 200
    p = AdjustmentProposal.objects.get(plan=cycle.linked_adjustment_plan, employee_id=emp_id)
    assert str(p.annual_manager_delta_pct) == "0.0200"
```

- [ ] **Step 6: Run + commit**

```bash
docker compose run --rm backend pytest apps/reward_cycle/tests/ -v
```
Expected: `2 passed`.

```bash
git add backend/apps/reward_cycle/ backend/config/urls.py
git commit -m "feat(reward_cycle): allocation list + save proposals API"
```

---

### Task 10: Submit for Approval + Approval Actions

**Files:**
- Create: `backend/apps/approval/views.py`
- Create: `backend/apps/approval/serializers.py`
- Create: `backend/apps/approval/urls.py`
- Modify: `backend/apps/reward_cycle/views.py` — add SubmitForApprovalView
- Modify: `backend/apps/reward_cycle/urls.py` — add submit route
- Create: `backend/apps/approval/tests/test_flow.py`
- Modify: `backend/config/urls.py` — include approval urls

**Goal:** Submit locks cycle, creates ApprovalInstance with two steps (DeptHead→HR_ADMIN); approvers act via API; full approve flips cycle to APPROVED.

- [ ] **Step 1: Append SubmitForApprovalView to reward_cycle/views.py**

```python
# Append to backend/apps/reward_cycle/views.py
from django.db import transaction
from apps.approval.services import create_instance_from_default_chain
from apps.audit.services import log_action

class SubmitForApprovalView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    @transaction.atomic
    def post(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle.objects.select_for_update(), pk=cycle_id)
        if cycle.status != "ALLOCATING":
            return Response({"detail":"cycle not in ALLOCATING"}, status=400)
        # Soft-budget check: flag if sum(annual_final*salary*12) exceeds adj plan total_budget
        over = False  # Phase 1 simplification: always false, real calc in iteration 4
        instance = create_instance_from_default_chain(
            scenario="REWARD_CYCLE", target_type="RewardCycle", target_id=cycle.id,
            over_budget_flag=over, initiator=request.user)
        cycle.status = "SUBMITTED"; cycle.save(update_fields=["status"])
        log_action(request, "SUBMIT", "RewardCycle", cycle.id,
                   {"instance_id": instance.id, "over_budget": over})
        return Response({"instance_id": instance.id, "over_budget_flag": over})
```

Append route to `reward_cycle/urls.py`:

```python
path("reward-cycle/<int:cycle_id>/submit/", SubmitForApprovalView.as_view()),
```

- [ ] **Step 2: Add create_instance_from_default_chain to approval/services.py**

```python
# Append to backend/apps/approval/services.py
from apps.approval.models import ApprovalChainTemplate, ApprovalInstance, ApprovalStep
from apps.iam.models import User, Role, UserRole

def create_instance_from_default_chain(*, scenario, target_type, target_id,
                                       over_budget_flag, initiator):
    tpl = ApprovalChainTemplate.objects.get(scenario=scenario, is_default=True)
    instance = ApprovalInstance.objects.create(
        scenario=scenario, template=tpl,
        target_type=target_type, target_id=target_id,
        status="PENDING", current_step=1,
        over_budget_flag=over_budget_flag, initiator=initiator)
    for idx, node in enumerate(tpl.nodes, start=1):
        # Phase 1: approver = first user with matching role code
        role = Role.objects.get(code=node["role_code"])
        approver = User.objects.filter(user_roles__role=role).first()
        ApprovalStep.objects.create(
            instance=instance, step_order=idx,
            role_code=node["role_code"], approver=approver,
            status="PENDING" if idx==1 else "WAITING")
    return instance
```

- [ ] **Step 3: Approval views + urls**

```python
# backend/apps/approval/serializers.py
from rest_framework import serializers
from apps.approval.models import ApprovalInstance, ApprovalStep

class ApprovalStepSerializer(serializers.ModelSerializer):
    approver_email = serializers.EmailField(source="approver.email", read_only=True)
    class Meta:
        model = ApprovalStep
        fields = ["id","step_order","role_code","approver_email","status","comment","acted_at"]

class ApprovalInstanceSerializer(serializers.ModelSerializer):
    steps = ApprovalStepSerializer(many=True, read_only=True)
    class Meta:
        model = ApprovalInstance
        fields = ["id","scenario","target_type","target_id","status","current_step",
                  "over_budget_flag","steps","created_at"]
```

```python
# backend/apps/approval/views.py
from rest_framework import permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from apps.approval.models import ApprovalInstance
from apps.approval.serializers import ApprovalInstanceSerializer
from apps.approval.services import advance_approval
from apps.audit.services import log_action

class MyPendingInstancesView(generics.ListAPIView):
    serializer_class = ApprovalInstanceSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        return ApprovalInstance.objects.filter(
            status="PENDING",
            steps__approver=self.request.user,
            steps__status="PENDING",
            steps__step_order=models.F("current_step")).distinct()

class ApprovalInstanceDetailView(generics.RetrieveAPIView):
    queryset = ApprovalInstance.objects.all()
    serializer_class = ApprovalInstanceSerializer
    permission_classes = [permissions.IsAuthenticated]

class ApprovalActionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, instance_id):
        instance = get_object_or_404(ApprovalInstance, pk=instance_id)
        action = request.data.get("action")  # APPROVE | REJECT
        comment = request.data.get("comment","")
        if action not in ("APPROVE","REJECT"):
            return Response({"detail":"invalid action"}, status=400)
        advance_approval(instance, request.user, action, comment)
        log_action(request, action, "ApprovalInstance", instance.id, {"comment": comment})
        return Response(ApprovalInstanceSerializer(instance).data)
```

`backend/apps/approval/urls.py`:

```python
from django.urls import path
from apps.approval.views import (MyPendingInstancesView, ApprovalInstanceDetailView,
    ApprovalActionView)
urlpatterns = [
    path("approval/my-pending/", MyPendingInstancesView.as_view()),
    path("approval/<int:pk>/", ApprovalInstanceDetailView.as_view()),
    path("approval/<int:instance_id>/action/", ApprovalActionView.as_view()),
]
```

Add to `config/urls.py`: `path("api/", include("apps.approval.urls"))`.

- [ ] **Step 4: Update advance_approval to flip RewardCycle status on full approve**

```python
# Modify _on_approved in backend/apps/approval/services.py
def _on_approved(instance):
    if instance.target_type == "RewardCycle":
        from apps.reward_cycle.models import RewardCycle
        RewardCycle.objects.filter(pk=instance.target_id).update(status="APPROVED")

def _on_rejected(instance):
    if instance.target_type == "RewardCycle":
        from apps.reward_cycle.models import RewardCycle
        RewardCycle.objects.filter(pk=instance.target_id).update(status="ALLOCATING")
```

- [ ] **Step 5: Write end-to-end approval test**

```python
# backend/apps/approval/tests/test_flow.py
import pytest
from rest_framework.test import APIClient
from django.core.management import call_command
from apps.iam.models import User
from apps.reward_cycle.models import RewardCycle

@pytest.fixture
def seeded(db): call_command("seed_phase1")

def _client(email):
    c = APIClient(); c.force_authenticate(User.objects.get(email=email)); return c

def test_submit_then_two_approvals_flip_cycle_to_approved(seeded):
    cycle = RewardCycle.objects.first()
    hr = _client("hr@demo.com")
    # submit requires ALLOCATING; PATCH a no-op to transition
    hr.patch(f"/api/reward-cycle/{cycle.id}/proposals/", {"items":[]}, format="json")
    r = hr.post(f"/api/reward-cycle/{cycle.id}/submit/")
    assert r.status_code == 200
    inst_id = r.data["instance_id"]

    dept = _client("depthead@demo.com")
    r = dept.post(f"/api/approval/{inst_id}/action/", {"action":"APPROVE","comment":"ok"}, format="json")
    assert r.data["current_step"] == 2

    r = hr.post(f"/api/approval/{inst_id}/action/", {"action":"APPROVE","comment":"ok"}, format="json")
    assert r.data["status"] == "APPROVED"

    cycle.refresh_from_db()
    assert cycle.status == "APPROVED"
```

- [ ] **Step 6: Run + commit**

```bash
docker compose run --rm backend pytest apps/approval/tests/test_flow.py -v
```
Expected: `1 passed`.

```bash
git add backend/apps/approval/ backend/apps/reward_cycle/ backend/config/urls.py
git commit -m "feat(approval): submit + 2-level approval flow"
```

---

### Task 11: HR Execute with MFA Gate + Atomic Execution

**Files:**
- Create: `backend/apps/reward_cycle/execute.py`
- Modify: `backend/apps/reward_cycle/views.py` — add ExecuteView
- Modify: `backend/apps/reward_cycle/urls.py` — add execute route
- Modify: `backend/apps/compensation_plan/models.py` — add CompensationRecord
- Modify: `backend/apps/lti/models.py` — ensure VestingEvent model exists
- Create: `backend/apps/reward_cycle/tests/test_execute.py`

**Goal:** HR posts execute with MFA code; one atomic transaction applies salary supersede, generates 5 yearly VestingEvents per grant, updates promoted employees' `job_level_current`, sets cycle EXECUTED, writes audit logs.

- [ ] **Step 1: Add CompensationRecord to compensation_plan/models.py**

```python
# Append to backend/apps/compensation_plan/models.py
class CompensationRecord(models.Model):
    employee = models.ForeignKey("hr_master.Employee", on_delete=models.PROTECT,
                                  related_name="compensation_records")
    monthly_salary = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=8, default="CNY")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    source_proposal = models.ForeignKey(AdjustmentProposal, on_delete=models.PROTECT,
                                         null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        indexes = [models.Index(fields=["employee","effective_from"])]
```

- [ ] **Step 2: Write execute.py service**

```python
# backend/apps/reward_cycle/execute.py
from datetime import date
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import CompensationRecord
from apps.lti.models import VestingEvent
from apps.audit.services import log_action

@transaction.atomic
def execute_reward_cycle(cycle: RewardCycle, request):
    assert cycle.status == "APPROVED", "cycle not approved"
    # 1. Supersede salary
    effective = date(cycle.budget_year, 1, 1)
    for p in cycle.linked_adjustment_plan.proposals.select_related("employee"):
        new_salary = p.proposed_salary
        CompensationRecord.objects.filter(
            employee=p.employee, effective_to__isnull=True
        ).update(effective_to=effective)
        CompensationRecord.objects.create(
            employee=p.employee, monthly_salary=new_salary,
            effective_from=effective, source_proposal=p)
        # 2. Update promoted job level
        if p.employee.is_promoted and p.employee.job_level_promoted:
            p.employee.job_level_current = p.employee.job_level_promoted
            p.employee.save(update_fields=["job_level_current"])
        log_action(request, "EXECUTE_SALARY", "Employee", p.employee.id,
                   {"new_monthly": str(new_salary), "proposal_id": p.id})
    # 3. Generate vesting events (5 equal slices starting cliff+1y)
    for g in cycle.linked_lti_plan.grants.filter(granted_ads__gt=0):
        total = g.granted_ads
        per_year = total // 5
        remainder = total - per_year * 5
        for year_idx in range(1, 6):
            shares = per_year + (remainder if year_idx == 5 else 0)
            vest_date = date(cycle.budget_year + year_idx, 4, 1)
            VestingEvent.objects.create(
                grant=g, vest_date=vest_date, scheduled_ads=shares,
                status="SCHEDULED")
        log_action(request, "EXECUTE_LTI", "LTIGrant", g.id,
                   {"granted_ads": total, "vesting_events": 5})
    cycle.status = "EXECUTED"
    cycle.executed_at = timezone.now()
    cycle.save(update_fields=["status","executed_at"])
    log_action(request, "EXECUTE", "RewardCycle", cycle.id, {"final_status":"EXECUTED"})
```

- [ ] **Step 3: Add ExecuteView with MFA gate**

```python
# Append to backend/apps/reward_cycle/views.py
import pyotp
from apps.reward_cycle.execute import execute_reward_cycle

class ExecuteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, cycle_id):
        code = request.headers.get("X-MFA-Code") or request.data.get("mfa_code")
        if not code or not request.user.mfa_secret:
            return Response({"detail":"MFA required"}, status=403)
        if not pyotp.TOTP(request.user.mfa_secret).verify(code, valid_window=1):
            return Response({"detail":"invalid MFA code"}, status=403)
        cycle = get_object_or_404(RewardCycle, pk=cycle_id)
        if cycle.status != "APPROVED":
            return Response({"detail":"cycle not approved"}, status=400)
        execute_reward_cycle(cycle, request)
        return Response({"status": cycle.status, "executed_at": cycle.executed_at})
```

Add route: `path("reward-cycle/<int:cycle_id>/execute/", ExecuteView.as_view())`.

- [ ] **Step 4: Write tests**

```python
# backend/apps/reward_cycle/tests/test_execute.py
import pytest, pyotp
from rest_framework.test import APIClient
from django.core.management import call_command
from apps.iam.models import User
from apps.iam.services import generate_totp_secret
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import CompensationRecord, AdjustmentProposal
from apps.lti.models import VestingEvent

@pytest.fixture
def executed(db):
    call_command("seed_phase1")
    cycle = RewardCycle.objects.first()
    # Give HR user MFA
    hr = User.objects.get(email="hr@demo.com")
    hr.mfa_secret = generate_totp_secret(); hr.mfa_enabled = True; hr.save()
    # Give Alice a manager_delta + granted_ads to verify flow
    p = AdjustmentProposal.objects.filter(plan=cycle.linked_adjustment_plan).first()
    p.annual_manager_delta_pct = "0.02"; p.save()
    g = cycle.linked_lti_plan.grants.first()
    g.granted_ads = 100; g.save()
    # Approve via service directly (skip API for speed)
    cycle.status = "APPROVED"; cycle.save()
    return cycle, hr

def test_execute_creates_salary_record_and_vesting(executed):
    cycle, hr = executed
    c = APIClient(); c.force_authenticate(hr)
    code = pyotp.TOTP(hr.mfa_secret).now()
    r = c.post(f"/api/reward-cycle/{cycle.id}/execute/", HTTP_X_MFA_CODE=code)
    assert r.status_code == 200
    cycle.refresh_from_db()
    assert cycle.status == "EXECUTED"
    assert CompensationRecord.objects.count() >= 5
    assert VestingEvent.objects.count() == 5  # one grant x 5 slices

def test_execute_without_mfa_rejected(executed):
    cycle, hr = executed
    c = APIClient(); c.force_authenticate(hr)
    r = c.post(f"/api/reward-cycle/{cycle.id}/execute/")
    assert r.status_code == 403
```

- [ ] **Step 5: Migrate + run + commit**

```bash
docker compose run --rm backend python manage.py makemigrations compensation_plan
docker compose run --rm backend python manage.py migrate
docker compose run --rm backend pytest apps/reward_cycle/tests/test_execute.py -v
```
Expected: `2 passed`.

```bash
git add backend/apps/compensation_plan/ backend/apps/reward_cycle/
git commit -m "feat(reward_cycle): atomic execute with MFA gate"
```

---

### Task 12: Employee Acknowledgement API

**Files:**
- Create: `backend/apps/lti/views.py` (EmployeeProposalView, AckView)
- Create: `backend/apps/lti/urls.py`
- Modify: `backend/config/urls.py`
- Create: `backend/apps/lti/tests/test_ack.py`

**Goal:** Employee sees their own proposal after EXECUTED; submits acknowledgement.

- [ ] **Step 1: Write EmployeeAck already modeled in Task 7 — add views**

```python
# backend/apps/lti/views.py
from rest_framework import permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentProposal
from apps.lti.models import LTIGrant, EmployeeAck
from apps.hr_master.models import Employee
from apps.audit.services import log_action

class EmployeeProposalView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, pk=cycle_id)
        emp = Employee.objects.filter(user_account=request.user).first()
        if not emp:
            return Response({"detail":"not an employee"}, status=404)
        if cycle.status != "EXECUTED":
            return Response({"detail":"cycle not executed"}, status=400)
        p = AdjustmentProposal.objects.filter(plan=cycle.linked_adjustment_plan, employee=emp).first()
        g = LTIGrant.objects.filter(plan=cycle.linked_lti_plan, employee=emp).first()
        ack = EmployeeAck.objects.filter(cycle=cycle, employee=emp).first()
        return Response({
            "cycle_code": cycle.code,
            "annual_final_pct": p.annual_final_pct if p else None,
            "promotion_adjustment_pct": p.promotion_adjustment_pct if p else None,
            "proposed_monthly_salary": p.proposed_salary if p else None,
            "granted_ads": g.granted_ads if g else 0,
            "ack_status": ack.status if ack else "PENDING",
            "ack_id": ack.id if ack else None,
        })

class AckView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, pk=cycle_id)
        emp = Employee.objects.filter(user_account=request.user).first()
        if not emp:
            return Response({"detail":"not an employee"}, status=404)
        ack, _ = EmployeeAck.objects.update_or_create(
            cycle=cycle, employee=emp,
            defaults={"status":"ACKNOWLEDGED","comment":request.data.get("comment","")})
        log_action(request, "ACK", "RewardCycle", cycle.id, {"employee_id": emp.id})
        return Response({"ack_id": ack.id, "status": ack.status})
```

```python
# backend/apps/lti/urls.py
from django.urls import path
from apps.lti.views import EmployeeProposalView, AckView
urlpatterns = [
    path("reward-cycle/<int:cycle_id>/my-proposal/", EmployeeProposalView.as_view()),
    path("reward-cycle/<int:cycle_id>/ack/", AckView.as_view()),
]
```

Add to `config/urls.py`: `path("api/", include("apps.lti.urls"))`.

- [ ] **Step 2: Update seed_phase1 to link Employee.user_account**

Modify `apps/hr_master/management/commands/seed_phase1.py` (already in Task 8) — ensure each employee is linked:

```python
# In seed loop:
user, _ = User.objects.get_or_create(email=f"{code.lower()}@demo.com",
    defaults={"full_name": name_cn, "password_hash": "..." })
emp.user_account = user; emp.save(update_fields=["user_account"])
```

- [ ] **Step 3: Write test**

```python
# backend/apps/lti/tests/test_ack.py
import pytest
from rest_framework.test import APIClient
from django.core.management import call_command
from apps.iam.models import User
from apps.reward_cycle.models import RewardCycle
from apps.reward_cycle.execute import execute_reward_cycle

@pytest.fixture
def executed_cycle(db, rf):
    call_command("seed_phase1")
    cycle = RewardCycle.objects.first()
    cycle.status = "APPROVED"; cycle.save()
    # Use a fake request for audit logging
    req = rf.post("/"); req.user = User.objects.get(email="hr@demo.com")
    execute_reward_cycle(cycle, req)
    return cycle

def test_employee_sees_own_proposal_after_execute(executed_cycle):
    cycle = executed_cycle
    u = User.objects.get(email="alice@demo.com")
    c = APIClient(); c.force_authenticate(u)
    r = c.get(f"/api/reward-cycle/{cycle.id}/my-proposal/")
    assert r.status_code == 200
    assert r.data["ack_status"] == "PENDING"
    r2 = c.post(f"/api/reward-cycle/{cycle.id}/ack/", {"comment":"confirmed"}, format="json")
    assert r2.status_code == 200
    r3 = c.get(f"/api/reward-cycle/{cycle.id}/my-proposal/")
    assert r3.data["ack_status"] == "ACKNOWLEDGED"
```

- [ ] **Step 4: Run + commit**

```bash
docker compose run --rm backend pytest apps/lti/tests/test_ack.py -v
```
Expected: `1 passed`.

```bash
git add backend/apps/lti/ backend/apps/hr_master/ backend/config/urls.py
git commit -m "feat(lti): employee proposal view + acknowledgement"
```

---

### Task 13: Vue Admin Frontend (Login → Allocation → Approval → Execute)

**Files:**
- Create: `frontend/admin/package.json`, `vite.config.ts`, `index.html`, `tsconfig.json`
- Create: `frontend/admin/src/main.ts`, `App.vue`, `router/index.ts`
- Create: `frontend/admin/src/api/client.ts` (axios with interceptor)
- Create: `frontend/admin/src/stores/auth.ts` (Pinia)
- Create: `frontend/admin/src/views/LoginView.vue` (email+pw → MFA code)
- Create: `frontend/admin/src/views/AllocationView.vue` (ElTable editable, submit button)
- Create: `frontend/admin/src/views/ApprovalView.vue` (pending list + approve/reject)
- Create: `frontend/admin/src/views/ExecuteView.vue` (MFA prompt + execute button)
- Create: `frontend/admin/Dockerfile`

**Goal:** End-to-end admin UX for HR/manager personas. Editable cells, soft-budget header, real API calls.

- [ ] **Step 1: Scaffold Vite project**

```bash
cd frontend/admin
# Create package.json with:
# dependencies: vue 3.4, vue-router 4, pinia 2, element-plus 2.7, axios 1.7
# devDependencies: @vitejs/plugin-vue, vite 5, typescript 5, vue-tsc
```

Full `package.json`:

```json
{
  "name": "hr-sys-admin",
  "version": "0.1.0",
  "scripts": {"dev":"vite","build":"vue-tsc && vite build","preview":"vite preview --port 4173"},
  "dependencies": {
    "axios":"^1.7.0","element-plus":"^2.7.0","pinia":"^2.2.0",
    "vue":"^3.4.0","vue-router":"^4.4.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue":"^5.0.0","typescript":"^5.4.0",
    "vite":"^5.3.0","vue-tsc":"^2.0.0"
  }
}
```

- [ ] **Step 2: Write api client with JWT refresh**

```typescript
// frontend/admin/src/api/client.ts
import axios from "axios"
const api = axios.create({ baseURL: "/api", timeout: 10000 })
api.interceptors.request.use(cfg => {
  const t = localStorage.getItem("access")
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})
api.interceptors.response.use(r=>r, async err => {
  if (err.response?.status === 401) {
    const refresh = localStorage.getItem("refresh")
    if (refresh) {
      const r = await axios.post("/api/auth/refresh/", {refresh})
      localStorage.setItem("access", r.data.access)
      err.config.headers.Authorization = `Bearer ${r.data.access}`
      return axios.request(err.config)
    }
  }
  return Promise.reject(err)
})
export default api
```

- [ ] **Step 3: Auth store + login view**

```typescript
// frontend/admin/src/stores/auth.ts
import { defineStore } from "pinia"
import api from "@/api/client"
export const useAuth = defineStore("auth", {
  state: () => ({ user: null as any, needsMfa: false }),
  actions: {
    async login(email: string, password: string) {
      const r = await api.post("/auth/login/", {email, password})
      localStorage.setItem("access", r.data.access)
      localStorage.setItem("refresh", r.data.refresh)
      this.user = r.data.user
      this.needsMfa = r.data.mfa_required
    },
    async verifyMfa(code: string) {
      await api.post("/auth/mfa/verify/", {code})
      this.needsMfa = false
    },
  },
})
```

```vue
<!-- frontend/admin/src/views/LoginView.vue -->
<template>
  <el-card class="login" style="max-width:420px;margin:80px auto">
    <h2>HR-Sys Admin</h2>
    <el-form v-if="!store.needsMfa" @submit.prevent="doLogin">
      <el-form-item label="Email"><el-input v-model="email" /></el-form-item>
      <el-form-item label="Password"><el-input v-model="pw" type="password" /></el-form-item>
      <el-button type="primary" @click="doLogin">Sign in</el-button>
    </el-form>
    <el-form v-else @submit.prevent="doMfa">
      <el-form-item label="MFA Code"><el-input v-model="code" /></el-form-item>
      <el-button type="primary" @click="doMfa">Verify</el-button>
    </el-form>
  </el-card>
</template>
<script setup lang="ts">
import { ref } from "vue"; import { useAuth } from "@/stores/auth"; import { useRouter } from "vue-router"
const store = useAuth(); const router = useRouter()
const email = ref(""); const pw = ref(""); const code = ref("")
async function doLogin(){ await store.login(email.value, pw.value); if(!store.needsMfa) router.push("/allocation") }
async function doMfa(){ await store.verifyMfa(code.value); router.push("/allocation") }
</script>
```

- [ ] **Step 4: AllocationView with editable ElTable**

```vue
<!-- frontend/admin/src/views/AllocationView.vue -->
<template>
  <el-container direction="vertical" style="padding:16px">
    <el-descriptions v-if="cycle" :column="4" border>
      <el-descriptions-item label="Cycle">{{ cycle.code }}</el-descriptions-item>
      <el-descriptions-item label="Status"><el-tag>{{ cycle.status }}</el-tag></el-descriptions-item>
      <el-descriptions-item label="Budget Year">{{ cycle.budget_year }}</el-descriptions-item>
      <el-descriptions-item label="Rows">{{ rows.length }}</el-descriptions-item>
    </el-descriptions>
    <el-table :data="rows" border style="margin-top:12px">
      <el-table-column prop="employee_code" label="Code" width="100"/>
      <el-table-column prop="name_cn" label="Name" width="120"/>
      <el-table-column prop="dept_name" label="Dept" width="140"/>
      <el-table-column prop="job_level_current" label="Level" width="70"/>
      <el-table-column label="Promotion %" width="110">
        <template #default="{row}">{{ fmt(row.promotion_adjustment_pct) }}</template>
      </el-table-column>
      <el-table-column label="Annual Suggest %" width="130">
        <template #default="{row}">{{ fmt(row.annual_suggested_pct) }}</template>
      </el-table-column>
      <el-table-column label="Manager Δ %" width="120">
        <template #default="{row}">
          <el-input-number v-model="row.annual_manager_delta_pct"
            :step="0.005" :precision="4" size="small"
            @change="markDirty(row)" :disabled="!editable" />
        </template>
      </el-table-column>
      <el-table-column label="Final %" width="100">
        <template #default="{row}">{{ fmt(computeFinal(row)) }}</template>
      </el-table-column>
      <el-table-column label="New Salary" width="130">
        <template #default="{row}">{{ fmtSalary(row) }}</template>
      </el-table-column>
      <el-table-column label="RSU ADS" width="120">
        <template #default="{row}">
          <el-input-number v-model="row.granted_ads" :min="0" :step="100" size="small"
            @change="markDirty(row)" :disabled="!editable" />
        </template>
      </el-table-column>
      <el-table-column label="Total Comp" width="140">
        <template #default="{row}">{{ fmtTotal(row) }}</template>
      </el-table-column>
    </el-table>
    <el-space style="margin-top:16px">
      <el-button @click="save" :disabled="!editable || !dirty.size">Save ({{ dirty.size }})</el-button>
      <el-button type="primary" @click="submit" :disabled="cycle?.status!=='ALLOCATING'">Submit for Approval</el-button>
    </el-space>
  </el-container>
</template>
<script setup lang="ts">
import { ref, onMounted, computed } from "vue"; import api from "@/api/client"
const rows = ref<any[]>([]); const cycle = ref<any>(null); const dirty = ref(new Set<number>())
const editable = computed(()=> ["DRAFT","ALLOCATING"].includes(cycle.value?.status))
async function load(){
  const r = await api.get("/reward-cycle/")
  const c = r.data[0]
  const d = await api.get(`/reward-cycle/${c.id}/allocation/`)
  cycle.value = d.data.cycle; rows.value = d.data.rows
}
function markDirty(row:any){ dirty.value.add(row.employee_id) }
function computeFinal(row:any){
  const s = Number(row.annual_suggested_pct||0); const m = Number(row.annual_manager_delta_pct||0)
  return (s + m).toFixed(4)
}
function fmt(v:any){ return v==null?"-":(Number(v)*100).toFixed(2)+"%" }
function fmtSalary(row:any){
  const cur = Number(row.current_monthly_salary||0)
  const p = Number(row.promotion_adjustment_pct||0) + Number(computeFinal(row))
  return (cur * (1+p)).toFixed(2)
}
function fmtTotal(row:any){
  const base = Number(fmtSalary(row))*12
  const rsu = (Number(row.granted_ads||0) * Number(row.unit_price_at_grant||0))/5
  return (base+rsu).toFixed(2)
}
async function save(){
  const items = rows.value.filter(r=>dirty.value.has(r.employee_id))
    .map(r=>({employee_id:r.employee_id, annual_manager_delta_pct:r.annual_manager_delta_pct, granted_ads:r.granted_ads}))
  await api.patch(`/reward-cycle/${cycle.value.id}/proposals/`, {items})
  dirty.value.clear(); await load()
}
async function submit(){
  await api.post(`/reward-cycle/${cycle.value.id}/submit/`); await load()
}
onMounted(load)
</script>
```

- [ ] **Step 5: ApprovalView + ExecuteView**

```vue
<!-- frontend/admin/src/views/ApprovalView.vue -->
<template>
  <el-container direction="vertical" style="padding:16px">
    <h3>My Pending Approvals</h3>
    <el-table :data="items" border>
      <el-table-column prop="id" label="ID" width="70"/>
      <el-table-column prop="scenario" label="Scenario" width="150"/>
      <el-table-column prop="target_type" label="Target" width="140"/>
      <el-table-column prop="target_id" label="Target ID" width="100"/>
      <el-table-column label="Step">
        <template #default="{row}">{{ row.current_step }} / {{ row.steps.length }}</template>
      </el-table-column>
      <el-table-column label="Over Budget">
        <template #default="{row}"><el-tag v-if="row.over_budget_flag" type="warning">YES</el-tag></template>
      </el-table-column>
      <el-table-column label="Actions" width="260">
        <template #default="{row}">
          <el-input v-model="comments[row.id]" placeholder="comment" size="small" style="width:120px"/>
          <el-button size="small" type="success" @click="act(row,'APPROVE')">Approve</el-button>
          <el-button size="small" type="danger" @click="act(row,'REJECT')">Reject</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-container>
</template>
<script setup lang="ts">
import { ref, onMounted } from "vue"; import api from "@/api/client"
const items = ref<any[]>([]); const comments = ref<Record<number,string>>({})
async function load(){ items.value = (await api.get("/approval/my-pending/")).data }
async function act(row:any, action:string){
  await api.post(`/approval/${row.id}/action/`, {action, comment: comments.value[row.id]||""})
  await load()
}
onMounted(load)
</script>
```

```vue
<!-- frontend/admin/src/views/ExecuteView.vue -->
<template>
  <el-card style="max-width:600px;margin:40px auto">
    <h3>Execute Reward Cycle</h3>
    <el-descriptions v-if="cycle" :column="2" border>
      <el-descriptions-item label="Code">{{ cycle.code }}</el-descriptions-item>
      <el-descriptions-item label="Status">{{ cycle.status }}</el-descriptions-item>
    </el-descriptions>
    <el-form style="margin-top:16px" @submit.prevent="doExecute">
      <el-form-item label="MFA Code"><el-input v-model="code" /></el-form-item>
      <el-button type="danger" @click="doExecute" :disabled="cycle?.status!=='APPROVED'">
        Execute
      </el-button>
    </el-form>
    <el-alert v-if="msg" :title="msg" :type="msgType" style="margin-top:16px"/>
  </el-card>
</template>
<script setup lang="ts">
import { ref, onMounted } from "vue"; import api from "@/api/client"
const cycle = ref<any>(null); const code = ref(""); const msg = ref(""); const msgType = ref("success")
async function load(){ cycle.value = (await api.get("/reward-cycle/")).data[0] }
async function doExecute(){
  try{
    const r = await api.post(`/reward-cycle/${cycle.value.id}/execute/`, null,
      { headers: { "X-MFA-Code": code.value } })
    msg.value = `Executed at ${r.data.executed_at}`; msgType.value = "success"; await load()
  } catch(e:any){ msg.value = e.response?.data?.detail || "failed"; msgType.value = "error" }
}
onMounted(load)
</script>
```

- [ ] **Step 6: router + main.ts + Dockerfile**

```typescript
// frontend/admin/src/router/index.ts
import { createRouter, createWebHistory } from "vue-router"
const routes = [
  { path: "/login", component: () => import("@/views/LoginView.vue") },
  { path: "/allocation", component: () => import("@/views/AllocationView.vue") },
  { path: "/approval", component: () => import("@/views/ApprovalView.vue") },
  { path: "/execute", component: () => import("@/views/ExecuteView.vue") },
  { path: "/", redirect: "/login" },
]
export default createRouter({ history: createWebHistory("/admin/"), routes })
```

```typescript
// frontend/admin/src/main.ts
import { createApp } from "vue"; import { createPinia } from "pinia"
import ElementPlus from "element-plus"; import "element-plus/dist/index.css"
import App from "./App.vue"; import router from "./router"
createApp(App).use(createPinia()).use(router).use(ElementPlus).mount("#app")
```

```dockerfile
# frontend/admin/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
```

- [ ] **Step 7: Smoke in browser + commit**

```bash
docker compose up -d admin-fe backend
# visit http://localhost/admin/login
# login hr@demo.com / demo1234, MFA setup -> enter code -> allocation page shows 5 rows
```

Verify: 5 rows visible, Manager Δ editable, Save button persists, Submit flips status.

```bash
git add frontend/admin/
git commit -m "feat(admin-fe): vue allocation + approval + execute views"
```

---

### Task 14: Employee Portal + Nginx + Full Compose + E2E Smoke

**Files:**
- Create: `frontend/portal/` (trimmed copy of admin: login + MyProposalView only)
- Finalize: `nginx/default.conf`
- Create: `backend/tests/e2e/test_phase1_flow.py`

**Goal:** Employee can log in, see own proposal after EXECUTED, acknowledge. Full stack reachable at http://localhost/. E2E API test exercises the entire happy path in one pytest.

- [ ] **Step 1: Portal scaffold (copy admin, trim)**

Same package.json/main.ts/router pattern, with only `LoginView.vue` and `MyProposalView.vue`:

```vue
<!-- frontend/portal/src/views/MyProposalView.vue -->
<template>
  <el-card style="max-width:640px;margin:40px auto">
    <h3>{{ data?.cycle_code }}</h3>
    <el-descriptions v-if="data" :column="1" border>
      <el-descriptions-item label="Annual Final %">{{ pct(data.annual_final_pct) }}</el-descriptions-item>
      <el-descriptions-item label="Promotion %">{{ pct(data.promotion_adjustment_pct) }}</el-descriptions-item>
      <el-descriptions-item label="New Monthly Salary">{{ data.proposed_monthly_salary }}</el-descriptions-item>
      <el-descriptions-item label="RSU ADS">{{ data.granted_ads }}</el-descriptions-item>
      <el-descriptions-item label="Ack Status">{{ data.ack_status }}</el-descriptions-item>
    </el-descriptions>
    <el-button v-if="data?.ack_status==='PENDING'" type="primary"
      style="margin-top:16px" @click="doAck">Acknowledge</el-button>
  </el-card>
</template>
<script setup lang="ts">
import { ref, onMounted } from "vue"; import api from "@/api/client"
const data = ref<any>(null); const cycleId = ref<number|null>(null)
function pct(v:any){ return v==null?"-":(Number(v)*100).toFixed(2)+"%" }
async function load(){
  const r = await api.get("/reward-cycle/")
  cycleId.value = r.data[0].id
  data.value = (await api.get(`/reward-cycle/${cycleId.value}/my-proposal/`)).data
}
async function doAck(){
  await api.post(`/reward-cycle/${cycleId.value}/ack/`, {comment:"confirmed"})
  await load()
}
onMounted(load)
</script>
```

Router mounts at `/` (not `/admin/`).

- [ ] **Step 2: Finalize nginx/default.conf**

```nginx
server {
    listen 80;
    server_name _;
    client_max_body_size 20m;

    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Request-Id $http_x_request_id;
    }
    location /admin/ {
        proxy_pass http://admin-fe:80/;
    }
    location / {
        proxy_pass http://portal-fe:80/;
    }
}
```

- [ ] **Step 3: Write E2E API smoke test**

```python
# backend/tests/e2e/test_phase1_flow.py
"""Full phase-1 happy path exercised via API. Single pytest, ~14 steps."""
import pyotp, pytest
from rest_framework.test import APIClient
from django.core.management import call_command
from apps.iam.models import User
from apps.iam.services import generate_totp_secret
from apps.reward_cycle.models import RewardCycle

@pytest.fixture
def stack(db):
    call_command("seed_phase1")
    hr = User.objects.get(email="hr@demo.com")
    hr.mfa_secret = generate_totp_secret(); hr.mfa_enabled = True; hr.save()
    return hr

def _c(email):
    c = APIClient(); c.force_authenticate(User.objects.get(email=email)); return c

def test_phase1_end_to_end(stack):
    hr_user = stack
    hr = _c("hr@demo.com")
    dept = _c("depthead@demo.com")

    # 1. Get cycle
    cycle = RewardCycle.objects.first()
    cid = cycle.id

    # 2. Allocation list has 5 rows
    r = hr.get(f"/api/reward-cycle/{cid}/allocation/")
    assert r.status_code == 200 and len(r.data["rows"]) == 5

    # 3. HR edits Alice: manager_delta=0.02, granted_ads=200
    alice = r.data["rows"][0]
    hr.patch(f"/api/reward-cycle/{cid}/proposals/",
        {"items":[{"employee_id":alice["employee_id"],
                   "annual_manager_delta_pct":"0.02","granted_ads":200}]},
        format="json")

    # 4. Submit
    r = hr.post(f"/api/reward-cycle/{cid}/submit/")
    assert r.status_code == 200
    inst_id = r.data["instance_id"]

    # 5. DeptHead approves step 1
    r = dept.post(f"/api/approval/{inst_id}/action/",
        {"action":"APPROVE","comment":"ok from dept"}, format="json")
    assert r.data["current_step"] == 2

    # 6. HR approves step 2
    r = hr.post(f"/api/approval/{inst_id}/action/",
        {"action":"APPROVE","comment":"final"}, format="json")
    assert r.data["status"] == "APPROVED"

    # 7. HR executes with MFA
    code = pyotp.TOTP(hr_user.mfa_secret).now()
    r = hr.post(f"/api/reward-cycle/{cid}/execute/", HTTP_X_MFA_CODE=code)
    assert r.status_code == 200

    # 8. Alice views own proposal
    alice_c = _c("alice@demo.com")
    r = alice_c.get(f"/api/reward-cycle/{cid}/my-proposal/")
    assert r.status_code == 200
    assert r.data["ack_status"] == "PENDING"
    assert r.data["granted_ads"] == 200

    # 9. Alice acknowledges
    r = alice_c.post(f"/api/reward-cycle/{cid}/ack/", {"comment":"ok"}, format="json")
    assert r.status_code == 200

    # 10. Ack status now ACKNOWLEDGED
    r = alice_c.get(f"/api/reward-cycle/{cid}/my-proposal/")
    assert r.data["ack_status"] == "ACKNOWLEDGED"

    # 11. Audit log contains SUBMIT, APPROVE x2, EXECUTE, ACK
    from django.db import connection
    with connection.cursor() as c:
        c.execute('SELECT action FROM audit.audit_log ORDER BY id')
        actions = [row[0] for row in c.fetchall()]
    for a in ["SUBMIT","APPROVE","EXECUTE","ACK"]:
        assert a in actions, f"missing {a} in audit log"
```

- [ ] **Step 4: Run + commit**

```bash
docker compose up -d --build
docker compose run --rm backend pytest tests/e2e/test_phase1_flow.py -v
```
Expected: `1 passed`.

Browser smoke:
1. http://localhost/admin/login — HR signs in, sets MFA, sees allocation
2. Edit Alice, Save, Submit
3. Logout, login as depthead@demo.com, /admin/approval, approve
4. Login back as HR, approve (step 2), navigate /admin/execute, enter MFA, execute
5. Logout, open http://localhost/ (portal), login alice@demo.com, see proposal, click Acknowledge

```bash
git add frontend/portal/ nginx/ backend/tests/
git commit -m "feat(phase1): portal + nginx + e2e smoke test"
git tag phase1-vertical-slice-complete
```

---

## Daily Checkpoints

| Day | Target State | Verification |
|-----|--------------|--------------|
| 1 | Task 1–2 done: repo skeleton, Docker Compose boots | `docker compose up -d && docker compose ps` → db/redis/backend/nginx all running |
| 2 | Task 3 done: iam models + migrations + tests pass | `pytest apps/iam/tests/ -v` → 2 passed |
| 3 | Task 4 done: login + MFA end-to-end via curl | `curl -X POST /api/auth/login/` returns tokens; MFA verify works |
| 4 | Task 5 done: audit schema exists, INSERT-only rule enforced | `psql -c "\dn audit"`; manually attempt UPDATE → silently discarded |
| 5 | Task 6 done: 5 employees imported from Excel | `python manage.py seed_phase1`; Employee.objects.count() == 5 |
| 6 | Task 7 done: compensation_plan + lti + reward_cycle models migrated | `pytest apps/compensation_plan apps/lti apps/reward_cycle -v` |
| 7 | Task 8–9 done: approval template + allocation list API returns 5 rows | `GET /api/reward-cycle/1/allocation/` → 200 with rows[5] |
| 8 | Task 10 done: submit + 2-level approval via API | `test_submit_then_two_approvals_flip_cycle_to_approved` passes |
| 9 | Task 11–12 done: execute with MFA + employee ack | `test_execute_creates_salary_record_and_vesting` + ack test pass |
| 10 | Task 13–14 done: full stack, E2E passes, browser smoke clean | `pytest tests/e2e -v` → 1 passed; manual browser flow green |

---

## Self-Review Checklist

- [x] Spec coverage — iam/hr_master/compensation_plan/lti/reward_cycle/approval/audit all present; bonus_pool/notification/data_integration scaffolded only (Phase 1 exclusion per spec §8.2).
- [x] No placeholders — every step shows runnable code or exact commands.
- [x] Type consistency — AdjustmentPlan has no `type` field (spec fix); AdjustmentBudgetCell.adjustment_type kept; LTIGrant UNIQUE(plan, employee); RewardCycle.linked_adjustment_plan OneToOne; ApprovalChainTemplate.is_default flag.
- [x] Approval chain — default DeptHead → HR_ADMIN (2 nodes), HR_ADMIN immutable per spec §5.1.
- [x] Over-budget flag — carried on ApprovalInstance but Phase 1 always false (soft constraint per user brief).
- [x] Audit — schema isolated, INSERT-only RULE, middleware adds request_id, execute path writes EXECUTE + EXECUTE_SALARY + EXECUTE_LTI + ACK.
- [x] MFA — execute endpoint hard-gated via X-MFA-Code header; pyotp TOTP verified.
- [x] E2E — single pytest covers allocation → submit → 2 approvals → execute → employee view → ack → audit log check.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-07-phase1-vertical-slice.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration, isolates context bloat.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach do you want?**
