# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack (locked — do not switch)

- **Backend**: Django 5.0 + DRF 3.15 + SimpleJWT, PostgreSQL 16, Redis 7 (`django_redis` cache).
- **Frontend**: Vue 3 + Element Plus + vue-router + Pinia + Vite + TypeScript. No Tailwind config in repo despite global memo — admin uses Element Plus + custom design tokens under `frontend/admin/src/styles/`.
- **Two frontends**: `frontend/admin/` (HR/admin, served at `/admin/`, port 5173) and `frontend/portal/` (employee/manager self-service, port 5174). They share the same backend.
- `AUTH_USER_MODEL = "iam.User"`. Locale is `zh-hans` / `Asia/Shanghai`.

## Commands

### Backend (run from `backend/`)

- **Local dev (preferred, no Docker)**: `dev.bat` — activates `.venv`, overrides `POSTGRES_HOST=localhost` (the `.env` has `host=db` for compose; do not change it), runs `migrate` → `seed_phase1` → `runserver 8000`.
- **Migrations**: `python manage.py makemigrations <app>` / `migrate`.
- **Seed Phase 1 fixtures**: `python manage.py seed_phase1` (in `apps/approval/management/commands/`).
- **Import employees**: `python manage.py import_employees <xlsx>` (in `apps/hr_master/management/commands/`).
- **Tests**: `pytest` (uses `config.settings.test`, DB `hrsys_test`).
  - **Important**: when running pytest locally without Docker, prefix with `POSTGRES_HOST=localhost` — `.env` defaults to `db` (the compose service name) and tests will fail to connect otherwise. On Windows cmd: `set POSTGRES_HOST=localhost && pytest`.
  - Single test: `pytest backend/apps/iam/tests/test_auth.py::TestLogin::test_ok`.
  - E2E flow test: `pytest backend/tests/e2e/test_phase1_flow.py`.
- **Settings layers**: `config.settings.base` (shared) → `local` (DEBUG, MD5 hasher) / `test` (DB=hrsys_test). `manage.py` defaults to `local`.

### Frontend admin (run from `frontend/admin/`)

- `dev.bat` or `npm run dev` — Vite at `http://localhost:5173/admin/`, proxies `/api` → `http://127.0.0.1:8000/`.
- Build: `npm run build` (runs `vue-tsc -b` then `vite build`).
- Path alias: `@` → `frontend/admin/src/`.

### Full stack via Docker (alternative)

- `docker compose up` brings up `db`, `redis`, `backend` (8000), `admin-fe` (5173), `portal-fe` (5174), `nginx` (80). In this mode `POSTGRES_HOST=db` is correct.

## Architecture (big picture)

This is a **compensation & incentive allocation system** replacing Excel + email approval flows for ~2000 employees. Three reward types — **年终奖 (bonus)**, **调薪 (salary adjustment)**, **长期激励 RSU (LTI)** — flow through a single unified pipeline driven by `RewardCycle`.

### Backend apps (all under `backend/apps/`)

| App | Role |
| --- | --- |
| `iam` | Custom `User` model, JWT auth, MFA (pyotp/qrcode), RBAC roles, **field-level permission grants**, **ScopeOfCharge / management scope** (a manager can be assigned multiple OrgUnits — see `scoping.py`, `permissions.py`). |
| `hr_master` | Employees, OrgUnits, job levels — the master data. Employee importer lives here. |
| `data_integration` | External HR system / file-based ingest. |
| `compensation_plan` | **Unified salary-adjustment plan** (annual + promotion in one `AdjustmentProposal`), 3-tab "调薪方案" config, **derived budgets** (see Budget Model v2 below), allocation matrix. |
| `bonus_pool` | Year-end bonus pool definition + allocation. |
| `lti` | RSU plans, grants, vesting calendar. |
| `reward_cycle` | The orchestrator: 1 `RewardCycle` ties together one `AdjustmentPlan` + bonus + LTI for a period; carries the discretionary % and execution gate. |
| `approval` | Multi-level configurable approval chains (default chain + condition nodes + HR-editable). Two reject granularities: whole batch vs. single employee. Phase-1 seed lives here. |
| `audit` | App-layer audit log (separate concern from Django admin log). `AuditMiddleware` is wired in `MIDDLEWARE`. |
| `notification` | Async messages / signoffs. |

### URL structure (`config/urls.py`)

- `/django-admin/` — Django's built-in admin (HR_ADMIN/SYS_ADMIN only).
- `/api/auth/` → `apps.iam.urls` (login, MFA, refresh).
- `/api/` → `reward_cycle`, `approval`, `lti` public endpoints.
- `/api/admin/` → admin-only endpoints split across `hr_master`, `compensation_plan`, `lti`, `bonus_pool`.
- `/api/budgets/` → `compensation_plan.budget_urls` (derived budget views).

### Frontend admin layout

- `src/views/`: top-level routes — `LoginView`, `AllocationView` (manager allocation page with 3-year total-comp simulation), `ApprovalView`, `ExecuteView`, plus subfolders `me/`, `dept/`, `org/`, `plans/`, `budgets/`, `categories/`, `salary/`.
- `src/stores/auth.ts` drives route guards (`requiresDeptHead`, `requiresAdmin` etc. in `router/index.ts`).
- `src/api/` wraps axios with the JWT interceptor.

### Domain rules that aren't obvious from code alone

- **Budget Model v2 (2026-05-15)**: 调薪预算 is **derived from rules**, not HR-typed. `BudgetOverride` exists as the single editable lever; company/department pools are read-only views computed in `compensation_plan/services/budget_derivation.py`. Don't add HR-typed budget UIs.
- **Promotion vs. annual adjustment**: A single `AdjustmentProposal` carries both — `promotion_*` fields are system-derived from job-level changes (not editable), `annual_manager_delta_pct` is the only manager-editable lever. Budget cells split by `adjustment_type ∈ {PROMOTION, ANNUAL}` × `{管理干部, 员工}`.
- **Promotion decisions are out of scope**: this system never originates promotions; it consumes `is_promoted` / `job_level_promoted` from the employee record.
- **Execution gate**: HR must click "执行" twice — approval ≠ execution.
- **ScopeOfCharge**: org tree has no BU layer. Multi-OrgUnit "分管范围" is modeled as a per-user collection in `iam`. Most permission decisions for managers route through it.

## Working in this repo

- **Specs and plans live in `docs/superpowers/`** (`specs/` for design docs, `plans/` for sprint plans). Read the relevant spec before changing the salary/incentive flow — the `2026-05-07-salary-incentive-system-design.md` spec is the source of truth for domain rules.
- The user runs no research/dev team — Claude owns codegen end-to-end. After plan approval, drive forward commit-by-commit without re-asking for option selections.
- **MVP scope is locked**: v1 = 6 modules; v1.5 modules (e.g. extended LTI tools, CTC cost view) are explicitly out — don't add them unsolicited.
- **Analysis-module 6 dimensions hard deadline**: 2026-06-10. Surface this proactively around 2026-06-03.

## Behavioral guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
