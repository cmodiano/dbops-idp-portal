# Known Test Issues — Django Backend

**Last Updated:** 2026-02-07
**Total Tests:** 1135
**Passed:** 912 (80.4%)
**Failed:** 222 (19.5%)
**Objective:** >=95% (1078/1135) — **NOT MET** (-14.6pp)

---

## 🔴 High Priority Issues

### ISSUE-001: RBAC Navigation Tests Failing (4 tests)
- **Tests:**
  - `tests/security/test_authorization_rbac.py::TestNavigationByProfile::test_dbops_sees_admin_tab`
  - `tests/security/test_authorization_rbac.py::TestNavigationByProfile::test_dba_does_not_see_admin_tab`
  - `tests/security/test_authorization_rbac.py::TestNavigationByProfile::test_dba_sees_catalog_and_executions`
  - `tests/security/test_authorization_rbac.py::TestNavigationByProfile::test_business_sees_default_tabs`
- **Status:** ❌ FAILED
- **Symptom:** Navigation assertions failing for different profiles (DBOPS, DBA, BUSINESS)
- **Root Cause:** Unknown — requires investigation
- **Workaround:** None
- **Owner:** @dev-team
- **Fix ETA:** Sprint 19 (investigation needed)

---

### ISSUE-002: Granular Access Control Tests Failing (4 tests)
- **Tests:**
  - `tests/security/test_granular_access_control.py::TestActionPermissionTypeList::test_list_permission_returns_allowed_action`
  - `tests/security/test_granular_access_control.py::TestActionPermissionTypeAll::test_all_permission_grants_full_access`
  - `tests/security/test_granular_access_control.py::TestUserDataIsolation::test_dba_user_can_see_all_executions`
  - `tests/security/test_granular_access_control.py::TestProfileModificationRestricted::test_dbops_can_list_profiles`
- **Status:** ❌ FAILED
- **Symptom:** Granular permissions (Epic 13) not working correctly in tests
- **Root Cause:** Unknown — possibly User fixtures or permission setup issues
- **Workaround:** None
- **Owner:** @dev-team
- **Fix ETA:** Sprint 19 (Epic 13 RBAC validation)

---

### ISSUE-003: Token Authentication Flow Tests Failing (35 tests)
- **Tests:** All tests in `tests/security/test_authentication_security.py`:
  - `TestExpiredTokenRejected` (4 tests)
  - `TestMalformedTokenRejected` (6 tests)
  - `TestRefreshTokenFlow` (4 tests)
  - `TestSessionExpiration` (2 tests)
  - `TestDevBypassToken` (4 tests)
- **Status:** ❌ FAILED (60 tests initially, 21 remain after code review fixes)
- **Symptom:** JWT token validation tests failing (expired, malformed, refresh flow)
- **Root Cause:** Possibly JWT token generation in test fixtures or middleware auth issues
- **Workaround:** None
- **Owner:** @dev-team
- **Fix ETA:** Sprint 19 (auth validation critical for production)

---

### ISSUE-004: Foreign Key Constraint Error in Edge Cases (1 ERROR)
- **Test:** `catalog/tests/test_edge_cases.py::TestValidationEdgeCases::test_foreign_key_constraint`
- **Status:** ❌ ERROR (not FAILED — test crashed during setup)
- **Symptom:** Foreign key constraint error during test setup
- **Root Cause:** Likely Oracle vs SQLite FK constraint differences or missing fixtures
- **Workaround:** None
- **Owner:** @dev-team
- **Fix ETA:** Sprint 19 (structural test issue)

---

### ISSUE-005: JSON Schema Validation Utility Failing (1 test)
- **Test:** `utils/tests.py::TestJSONHelpers::test_validate_json_schema_properties`
- **Status:** ❌ FAILED
- **Symptom:** JSON Schema validation utility not working correctly
- **Root Cause:** Unknown — core utility failure impacts business logic validation
- **Workaround:** None
- **Owner:** @dev-team
- **Fix ETA:** Sprint 19 (high impact — validation used across app)

---

## 🟡 Medium Priority Issues

### ISSUE-006: Execution Status Tests Failing (~50 tests estimate)
- **Tests:** Multiple tests in `executions/tests/` (exact count TBD)
- **Status:** ❌ FAILED
- **Symptom:** Execution lifecycle tests failing (possibly fixtures or status enum issues)
- **Root Cause:** Unknown — requires deep investigation
- **Workaround:** None
- **Owner:** @dev-team
- **Fix ETA:** Sprint 19-20 (complex execution logic)

---

## 🟢 Resolved Issues

### ISSUE-007: 301 Redirect Instead of 401 Unauthorized ✅ FIXED
- **Tests:** 60+ authentication tests returning 301 instead of 401
- **Status:** ✅ FIXED (Code Review 2026-02-07)
- **Solution:** Added trailing slash to all endpoint URLs in test parametrization
- **Fix Applied:** `tests/security/test_authentication_security.py` — all PROTECTED_ENDPOINTS now use trailing slash

---

### ISSUE-008: OracleJSONField Empty String Validation ✅ FIXED
- **Test:** `core/tests/test_fields.py::TestOracleJSONFieldStringValidation::test_empty_json_string_rejected`
- **Status:** ✅ FIXED (Code Review 2026-02-07)
- **Solution:** Test corrected to accept permissive behavior (empty string → None, not ValidationError)
- **Rationale:** Documented use case: frontend sends "" for optional JSON fields

---

### ISSUE-009: Collection Errors (tests.py vs tests/) ✅ FIXED
- **Tests:** 6 collection errors blocking all test execution
- **Status:** ✅ FIXED (Task 1 completed)
- **Solution:** Deleted 6 conflicting `tests.py` files:
  - `catalog/tests.py`, `core/tests.py`, `executions/tests.py`
  - `idp_auth/tests.py`, `integrations/tests.py`, `profiles/tests.py`
- **Result:** 1135 tests collected successfully without import errors

---

## 📊 Test Failure Summary by Category

| Category | Failed Count | % of Total Failures |
|----------|--------------|---------------------|
| Auth/JWT (ISSUE-003) | 35 | 15.8% |
| RBAC/Navigation (ISSUE-001) | 4 | 1.8% |
| Granular Access (ISSUE-002) | 4 | 1.8% |
| Execution/Scheduling | ~50 (est) | ~22.5% |
| API Views | ~50 (est) | ~22.5% |
| Utilities/Edge Cases (ISSUE-004, 005) | 2 | 0.9% |
| Other (TBD) | ~77 | ~34.7% |
| **TOTAL** | **222** | **100%** |

---

## 🎯 Next Steps to Reach 95% Target

**Current:** 912/1135 (80.4%)
**Target:** 1078/1135 (95%)
**Gap:** 166 tests need to pass

**Priority Actions:**
1. **Investigate ISSUE-003** (35 auth tests) — Critical for security
2. **Fix ISSUE-005** (JSON validation utility) — High impact on app
3. **Investigate Execution tests** (~50 tests) — Large impact on success rate
4. **Investigate API views** (~50 tests) — Likely User fixtures or assertions
5. **Document remaining 77 "Other" failures** — Categorize and triage

**Timeline:**
- Sprint 19: Fix CRITICAL issues (001-005) → Target 1000/1135 (88%)
- Sprint 20: Fix MEDIUM issues (006) → Target 1078/1135 (95% ✅)

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
