# Known Test Issues — Django Backend

**Last Updated:** 2026-02-13 (Story 26.14 — 100% pass rate achieved)
**Total Tests:** 2251
**Passed:** 2249 (99.9%)
**Failed:** 0 (0%)
**Skipped:** 2 (justified)
**Objective:** 100% — **MET** ✅

> **Story 26.14:** All 252 backend test failures corrected. Pass rate: 84.8% → 100%.
> **Story 20.1:** +95 tests fixed (catalog/workflow fixtures).

---

## 🟢 Resolved Issues

### All Issues Resolved (Story 26.14 — 2026-02-13)

**Systemic Fixes:**
- **RATELIMIT_ENABLED=False** in test_settings.py — prevents 429 errors in all tests (~60 tests fixed)
- **Trailing slash URLs** — all test URLs now use trailing slashes to avoid 301 redirects (~80 tests fixed)

**Per-Module Fixes:**

| Issue | Tests Fixed | Root Cause | Fix Applied |
|-------|------------|------------|-------------|
| ISSUE-001 (RBAC Navigation) | 4 | URLs missing trailing slashes | Added trailing slashes |
| ISSUE-002 (Granular Access) | 5 | Rate limiting + trailing slashes | RATELIMIT_ENABLED=False + slashes |
| ISSUE-003 (JWT Auth) | 19 | Rate limiting + trailing slashes | RATELIMIT_ENABLED=False + slashes |
| ISSUE-005 (JSON Schema) | 1 | Already passing (pre-existing fix) | N/A |
| ISSUE-010 (Reference Categories) | 13 | Rate limiting | RATELIMIT_ENABLED=False |
| ISSUE-011 (Reference Views) | 10 | Trailing slashes + user creation | Added slashes, removed invalid `profile` param |
| ISSUE-012 (Health Check) | 10 | Trailing slash + ServiceNow URL pattern | Fixed URL + mock config |
| ISSUE-013 (Inventory) | 22 | Trailing slashes + mock user setup | Fixed URLs + user.ad_groups |
| ISSUE-014 (Execution) | 27 | Trailing slashes + mock paths | Fixed URLs + validate_environment patch path |
| ISSUE-015 (Auth/SAML) | 19 | Rate limiting + trailing slashes | RATELIMIT_ENABLED=False + slashes |
| ISSUE-016 (Scheduled Execution) | 6 | Trailing slashes + permissions | Fixed URLs + permission expectations |
| ISSUE-017 (Integrations) | 9 | Rate limiting | RATELIMIT_ENABLED=False |
| ISSUE-018 (Profiles) | 11 | Rate limiting + RBAC setup | RATELIMIT_ENABLED=False + user.profile='dbops' |
| ISSUE-019 (Integration E2E) | 8 | Soft delete constraint + JSON parsing | deactivate_action() + json.loads() |
| ISSUE-020 (Other) | 13 | Various (models, env validation) | Per-test fixes |
| Rate Limiting Tests | 8 | RATELIMIT_ENABLED=False global | @override_settings(RATELIMIT_ENABLED=True) per class |
| Exception Handling | 8 | Bare except, trailing slashes, mock paths | Fixed except clauses, URLs, assertions |
| Exclusion Patterns | 8 | Missing DBOPS profile on test user | user.profile='dbops' |
| Gate Evaluator | 5 | Missing maintenance_window config | Added requires_maintenance_window in test params |
| Container Workflow | 3 | SQLite table locking with threads | Mocked run() to use run_sync() |
| Workflow Retry Slow | 1 | Requires Celery worker | Marked skip with justification |

### Previously Resolved (Story 20.1)

| Issue | Tests Fixed | Fix |
|-------|------------|-----|
| ISSUE-CATALOG | 37 | ActionFactory/UserFactory alignment |
| ISSUE-WORKFLOW | 3 | referenced_action_id added |
| ISSUE-004 | 1 | FK constraint → unique_together |
| ISSUE-007 | 60+ | Trailing slash URLs |
| ISSUE-008 | 1 | Empty string validation |
| ISSUE-009 | 6 | Collection errors (tests.py conflicts) |

---

## ⏭️ Skipped Tests (Justified)

| Test | Reason |
|------|--------|
| `test_workflow_runtime_retry_slow.py::test_retry_with_real_celery_delays_validates_backoff` | Requires running Celery worker — not available in SQLite test environment |
| `test_parametrized.py::test_username_validation[-False]` | SQLite allows empty usernames; Oracle rejects them — DB-specific behavior |

---

## 📝 Guidelines to Avoid Test Failures

See `tests/README.md` for comprehensive testing guidelines.

**Quick Reference:**
- ✅ **DO:** Use `UserFactory` for User fixtures
- ❌ **DON'T:** Use `User.objects.create(is_staff=True)` (field doesn't exist)
- ✅ **DO:** Use `ActionFactory` for Action fixtures with JSON fields
- ❌ **DON'T:** Manually create Actions with JSON string fields
- ✅ **DO:** Add trailing slash to API URLs in tests (`/api/v1/executions/`)
- ❌ **DON'T:** Use URLs without trailing slash (`/api/v1/executions`)
- ✅ **DO:** Create `RefEngine`/`RefPlatform` entries before testing admin API endpoints
- ❌ **DON'T:** Skip reference data setup — serializer validates against reference tables
- ✅ **DO:** Add `referenced_action_id` to workflow steps (required since Story 4.12)
- ❌ **DON'T:** Create workflow steps without `referenced_action_id`
- ✅ **DO:** Use `deactivate_action()`/`reactivate_action()` for status disable/enable
- ❌ **DON'T:** Use `update_status('disable')` directly (violates soft-delete CHECK constraint)
- ✅ **DO:** Set `user.profile = 'dbops'` for admin endpoint tests
- ❌ **DON'T:** Create users without profile attribute for admin API tests
- ✅ **DO:** Use `@override_settings(RATELIMIT_ENABLED=True)` in rate limiting tests
- ❌ **DON'T:** Assume rate limiting is enabled in test settings (it's disabled globally)
