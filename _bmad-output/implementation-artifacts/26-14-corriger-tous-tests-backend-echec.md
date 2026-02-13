# Story 26.14: Corriger tous les tests backend en échec

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que **développeur**,
je veux **corriger tous les tests backend actuellement en échec**,
afin de **avoir une suite de tests backend 100 % verte et garantir la non-régression**.

## Acceptance Criteria

**Given** la suite de tests backend (`pytest`)
**When** tous les tests sont exécutés
**Then** 100 % des tests passent (0 failure)
**And** les échecs documentés dans KNOWN_ISSUES.md sont corrigés ou documentés comme obsolètes (avec ticket de suppression)
**And** les fixtures (UserFactory, ActionFactory, etc.) sont alignées et réutilisables
**And** aucun test n'est marqué `@pytest.mark.skip` sans justification dans KNOWN_ISSUES.md
**And** KNOWN_ISSUES.md est mis à jour : section "Resolved" pour les corrections, ou suppression si vide

## Contexte

**Référence :** Epic 26 — Qualité du Code — Correctifs Assessment 6 février 2026 (planning-artifacts/epic-26-qualite-code-assessment-fev-2026.md)

**État actuel des tests backend :**
- **Total:** 1189 tests
- **Réussis:** 1007 (84.8%)
- **Échecs:** 181 tests (15.2%)
- **Skipped:** 1 test
- **Objectif:** >=95% (1130/1189) — **NON ATTEINT** (-10.2pp)

**Référence :** `idp-portal/django_backend/tests/KNOWN_ISSUES.md` (Last Updated: 2026-02-08)

**Catégories de problèmes identifiés :**

### 🔴 **Haute Priorité** (48 tests — 26.8% des échecs)
1. **ISSUE-003:** Token Authentication Flow (19 tests) — JWT validation, expiry, refresh flow
2. **ISSUE-001:** RBAC Navigation Tests (4 tests) — Profile-based tab visibility
3. **ISSUE-002:** Granular Access Control (5 tests) — Epic 13 permission tests
4. **ISSUE-005:** JSON Schema Validation Utility (1 test) — Core utility failure
5. **ISSUE-015:** Auth/SAML Tests (19 tests) — SAML config, authentication flow

### 🟡 **Moyenne Priorité** (133 tests — 73.2% des échecs)
6. **ISSUE-010:** Reference/Categories Tests (13 tests)
7. **ISSUE-011:** Reference Views Tests (10 tests)
8. **ISSUE-012:** Health Check Tests (10 tests)
9. **ISSUE-013:** Inventory Tests (22 tests) — API + environments
10. **ISSUE-014:** Execution Tests (27 tests) — Story 13.5, 4.11, exception handling
11. **ISSUE-016:** Scheduled Execution Tests (6 tests) — PUT/PATCH endpoints
12. **ISSUE-017:** Integration Upload & Services (9 tests)
13. **ISSUE-018:** Profile Import/Export Tests (11 tests)
14. **ISSUE-019:** Integration Tests (8 tests) — E2E, RBAC, performance
15. **ISSUE-020:** Other Failures (13 tests) — models, environment validation

**Progrès récent (Story 20.1) :**
- ✅ Catalog tests: 37 failures → 0 (100% fixed)
- ✅ Workflow runtime tests: 3 failures → 0 (100% fixed)
- 📊 Gain total: +95 tests (912 → 1007 passants, 80.4% → 84.8%)

**Gap vers l'objectif :** 123 tests doivent passer pour atteindre 95%

## Tasks / Subtasks

- [x] Task 1: Analyser et catégoriser tous les échecs actuels (AC: #1)
  - [x] 1.1. Exécuter pytest avec --tb=short et capturer tous les échecs
  - [x] 1.2. Catégoriser les échecs par module (auth, rbac, inventory, execution, etc.)
  - [x] 1.3. Identifier les patterns communs (fixtures, API changes, migrations)
  - [x] 1.4. Créer un rapport détaillé des root causes par catégorie
  - [x] 1.5. Prioriser les correctifs par impact (High → Medium → Low)

- [x] Task 2: Corriger les tests Auth/JWT (ISSUE-003, ISSUE-015) — 38 tests (AC: #2)
  - [x] 2.1. **ISSUE-003:** Corriger JWT token validation tests (19 tests)
    - [x] 2.1.1. Investiguer `test_authentication_security.py` — expired, malformed, refresh flow
    - [x] 2.1.2. Vérifier JWT token generation dans fixtures (correlation_id, claims, expiry)
    - [x] 2.1.3. Aligner middleware auth avec logique de test
    - [x] 2.1.4. Corriger dev bypass mode tests si applicable
  - [x] 2.2. **ISSUE-015:** Corriger Auth/SAML tests (19 tests)
    - [x] 2.2.1. Investiguer `test_auth_views.py` (14 tests), `test_saml_views.py` (4), `test_jwt_authentication.py` (1)
    - [x] 2.2.2. Vérifier SAML config fixtures et mock responses
    - [x] 2.2.3. Aligner tests avec implémentation actuelle SAML (Story m-7)
    - [x] 2.2.4. Valider tous tests auth/SAML passent

- [x] Task 3: Corriger les tests RBAC/Permissions (ISSUE-001, ISSUE-002) — 9 tests (AC: #2)
  - [x] 3.1. **ISSUE-001:** Corriger RBAC Navigation tests (4 tests)
    - [x] 3.1.1. Investiguer `test_authorization_rbac.py::TestNavigationByProfile`
    - [x] 3.1.2. Vérifier profile fixtures (DBOPS, DBA, BUSINESS) et navigation_tabs logic
    - [x] 3.1.3. Aligner avec implémentation actuelle (Story 6.5 restauration menu Audit)
  - [x] 3.2. **ISSUE-002:** Corriger Granular Access Control tests (5 tests)
    - [x] 3.2.1. Investiguer `test_granular_access_control.py` — Epic 13 permissions
    - [x] 3.2.2. Vérifier permission setup (action_id, environment, target filters)
    - [x] 3.2.3. Aligner avec Story 13.3 (RBAC environment du target)

- [x] Task 4: Corriger les tests Reference (ISSUE-010, ISSUE-011) — 23 tests (AC: #2)
  - [x] 4.1. Investiguer `reference/tests/test_categories.py` (13 tests)
  - [x] 4.2. Investiguer `reference/tests/test_views.py` (10 tests)
  - [x] 4.3. Vérifier RefEngine, RefPlatform fixtures (Story 13.7)
  - [x] 4.4. Aligner tests avec Category model (Story 2.30)
  - [x] 4.5. Valider tous tests reference passent

- [x] Task 5: Corriger les tests Inventory (ISSUE-013) — 22 tests (AC: #2)
  - [x] 5.1. Investiguer `inventory/tests/test_views.py` (17 tests)
  - [x] 5.2. Investiguer `inventory/tests/test_environments.py` (5 tests)
  - [x] 5.3. Aligner avec Story 21.1-21.6 (environnements dynamiques, valeurs brutes)
  - [x] 5.4. Vérifier InventoryService refactoring (Story 26.1)
  - [x] 5.5. Valider tous tests inventory passent

- [x] Task 6: Corriger les tests Execution (ISSUE-014, ISSUE-016, ISSUE-020) — 40 tests (AC: #2)
  - [x] 6.1. **ISSUE-014:** Corriger execution tests (27 tests)
    - [x] 6.1.1. Investiguer `test_story_13_5.py` (16 tests) — API standalone execution
    - [x] 6.1.2. Investiguer `test_story_4_11.py` (6 tests) — RBAC validation workflows
    - [x] 6.1.3. Investiguer `test_exception_handling.py` (5 tests)
    - [x] 6.1.4. Aligner avec ExecutionsView refactoring (Story 26.2)
  - [x] 6.2. **ISSUE-016:** Corriger scheduled execution tests (6 tests)
    - [x] 6.2.1. Investiguer `test_scheduled_execution_put.py`
    - [x] 6.2.2. Aligner avec Epic 11 (scheduling) et Celery migration (Story 20.3)
  - [x] 6.3. **ISSUE-020:** Corriger other execution tests (7 tests)
    - [x] 6.3.1. Investiguer `test_models.py` (3), `test_environment_validation.py` (3), `test_story_4_12.py` (4)
    - [x] 6.3.2. Aligner avec Story 13.4 (target_names required)

- [x] Task 7: Corriger les tests Health Check (ISSUE-012) — 10 tests (AC: #2)
  - [x] 7.1. Investiguer `core/tests/test_health_check.py`
  - [x] 7.2. Vérifier health check dependencies (DB, Vault, ServiceNow)
  - [x] 7.3. Aligner avec Story m-8 (middleware logging, health extended)
  - [x] 7.4. Valider tous tests health check passent

- [x] Task 8: Corriger les tests Integrations (ISSUE-017) — 9 tests (AC: #2)
  - [x] 8.1. Investiguer `integrations/tests/test_upload_icon_view.py` (7 tests)
  - [x] 8.2. Investiguer `integrations/tests/test_services.py` (2 tests)
  - [x] 8.3. Aligner avec Epic 24 (integration types, validation)
  - [x] 8.4. Valider tous tests integrations passent

- [x] Task 9: Corriger les tests Profiles (ISSUE-018) — 11 tests (AC: #2)
  - [x] 9.1. Investiguer `profiles/tests/test_import_export_views.py` (6 tests)
  - [x] 9.2. Investiguer `profiles/tests/test_services.py` (5 tests)
  - [x] 9.3. Aligner avec Story 2.13 (import/export YAML)
  - [x] 9.4. Valider tous tests profiles passent

- [x] Task 10: Corriger les tests Integration E2E (ISSUE-019) — 8 tests (AC: #2)
  - [x] 10.1. Investiguer `tests/integration/` (8 tests, 5 fichiers)
  - [x] 10.2. Aligner avec Epic 15 (audit trail, sécurité)
  - [x] 10.3. Vérifier fixtures pour tests E2E (user profiles, actions, executions)
  - [x] 10.4. Valider tous tests integration passent

- [x] Task 11: Corriger le test JSON Schema Utility (ISSUE-005) — 1 test (AC: #2)
  - [x] 11.1. Investiguer `utils/tests.py::TestJSONHelpers::test_validate_json_schema_properties`
  - [x] 11.2. Vérifier OracleJSONField validation (Story 17.4)
  - [x] 11.3. Corriger root cause (validation logic ou test assertion)

- [x] Task 12: Valider 100% des tests backend passent (AC: #1)
  - [x] 12.1. Exécuter `pytest` complet et confirmer 0 échec (2249/2251 pass, 2 skip justifiés)
  - [x] 12.2. Valider qu'aucun test n'est skip sans justification documentée
  - [x] 12.3. Confirmer 0 collection errors

- [x] Task 13: Mettre à jour KNOWN_ISSUES.md et documentation (AC: #2, #3, #4)
  - [x] 13.1. Déplacer tous issues corrigés dans section "Resolved Issues"
  - [x] 13.2. KNOWN_ISSUES.md mis à jour avec baseline 100%
  - [x] 13.3. Documenter tout test skip restant avec justification (AC: #4)
  - [x] 13.4. Créer rapport final de baseline (nombre tests, durée, couverture)

## Dev Notes

### État actuel et objectif

**Baseline actuelle (2026-02-13) :**
- **Tests passants:** 1007/1189 (84.8%)
- **Tests échoués:** 181 (15.2%)
- **Tests skipped:** 1
- **Gap vers 95%:** 123 tests supplémentaires requis
- **Gap vers 100%:** 181 tests à corriger

**Progrès récent (Story 20.1) :**
Story 20.1 a corrigé 95 tests (37 catalog + 3 workflow + 55 autres), passant de 80.4% → 84.8%. Toutes les fixtures UserFactory/ActionFactory sont maintenant alignées pour les modules catalog et workflow.

**Frontend équivalent (Story 26.13) :**
La story frontend 26.13 a réussi à atteindre **100% pass rate (2018/2018 tests)** en corrigeant :
- Problèmes d3-zoom/d3-drag JSDOM (mocks + error suppression)
- Assertions Ant Design 6.2 obsolètes
- Mocks incomplets
- Warnings React 19 `act()`

Le même pattern doit être appliqué au backend : analyse méthodique, correction par catégorie, validation 100%.

### Catégorisation des échecs

**CRITIQUE (48 tests — 26.8%):**
- Auth/JWT + SAML : 38 tests (ISSUE-003, ISSUE-015)
- RBAC/Permissions : 9 tests (ISSUE-001, ISSUE-002)
- JSON Schema : 1 test (ISSUE-005)

**IMPORTANTE (133 tests — 73.2%):**
- Reference : 23 tests (ISSUE-010, ISSUE-011)
- Inventory : 22 tests (ISSUE-013)
- Execution : 40 tests (ISSUE-014, ISSUE-016, ISSUE-020)
- Health Check : 10 tests (ISSUE-012)
- Integrations : 9 tests (ISSUE-017)
- Profiles : 11 tests (ISSUE-018)
- Integration E2E : 8 tests (ISSUE-019)

### Root Causes anticipées

**1. API Changes récents (Epic M, Epic 21, Epic 26) :**
- **InventoryService** (Story 26.1) : Refactoring majeur — 3 classes distinctes
- **ExecutionsView** (Story 26.2) : Split en 4 modules
- **Environnements** (Epic 21) : Valeurs brutes (lab, dev, staging, prod) sans normalisation
- **Reference tables** (Story 13.7, 2.30) : RefEngine, RefPlatform, Category

**2. Fixtures incompatibles :**
- **UserFactory** : `is_staff` field n'existe plus (Story 20.1 a corrigé catalog/workflow)
- **ActionFactory** : JSON fields, `status` transitions, `referenced_action_id` workflow
- **ProfileFactory** : Environnements dynamiques, permissions par attribut (Epic 23)

**3. Migrations manquantes ou incomplètes :**
- Celery retry async (Story 20.3) impact scheduled executions
- Middleware JWT (Story m-7) impact auth tests
- ExecutionTarget table (Story 25.1) impact execution tests

**4. Test environment configuration :**
- JWT tokens expiry/refresh flow
- SAML mock responses
- Health check dependencies (DB, Vault, ServiceNow)
- Integration icon upload (file handling)

### Stack technique tests backend

**Framework :**
- **pytest 8.3.5** — Test runner
- **pytest-django 4.10.0** — Django integration
- **pytest-cov 6.0.0** — Coverage
- **Factory Boy 3.3.1** — Fixtures factories
- **Faker 34.0.0** — Fake data generation

**Configuration :**
- **pytest.ini** — Test discovery, settings module (idp_backend.test_settings)
- **conftest.py** — Shared fixtures
- **test_settings.py** — Test-specific Django config
- **KNOWN_ISSUES.md** — Issue tracking

**Run commands :**
- `pytest` — Run all tests
- `pytest --cov` — Run with coverage
- `pytest -v` — Verbose output
- `pytest --tb=short` — Short traceback
- `pytest -k test_name` — Run specific test
- `pytest --maxfail=1` — Stop after first failure

### Stratégie de correction

**Phase 1 : Critique (48 tests)** — Impact maximal
1. Corriger ISSUE-003 (JWT auth, 19 tests) — Bloque toute authentification
2. Corriger ISSUE-015 (SAML, 19 tests) — Bloque login SAML
3. Corriger ISSUE-001, ISSUE-002 (RBAC, 9 tests) — Validation sécurité
4. Corriger ISSUE-005 (JSON Schema, 1 test) — Utilitaire core

**Phase 2 : Importante (133 tests)** — Volume élevé
5. Corriger ISSUE-014, ISSUE-016, ISSUE-020 (Execution, 40 tests) — Plus grand volume
6. Corriger ISSUE-010, ISSUE-011 (Reference, 23 tests)
7. Corriger ISSUE-013 (Inventory, 22 tests)
8. Corriger ISSUE-012 (Health Check, 10 tests)
9. Corriger ISSUE-017, ISSUE-018, ISSUE-019 (28 tests) — Intégrations

**Phase 3 : Validation finale**
10. Exécution complète `pytest` — Confirmer 1189/1189
11. Coverage verification — Maintenir ≥85%
12. Documentation — Mettre à jour KNOWN_ISSUES.md, tests/README.md

### Patterns de correction (d'après Story 20.1)

**UserFactory :**
```python
# ❌ INCORRECT (is_staff n'existe pas)
user = User.objects.create(username="test", is_staff=True)

# ✅ CORRECT
from core.factories import UserFactory
user = UserFactory(profile=ProfileFactory(name="dbops"))
```

**ActionFactory :**
```python
# ❌ INCORRECT (double transition)
action = ActionFactory(status=ActionStatus.PUBLISHED)
action.update_status('publish')

# ✅ CORRECT
action = ActionFactory(status=ActionStatus.DRAFT)
action.update_status('publish')
```

**Workflow steps :**
```python
# ❌ INCORRECT (missing referenced_action_id)
WorkflowStepFactory(workflow=wf, step_number=1)

# ✅ CORRECT
WorkflowStepFactory(
    workflow=wf,
    step_number=1,
    referenced_action_id=ActionFactory().id
)
```

**API URLs :**
```python
# ❌ INCORRECT (missing trailing slash → 301 redirect)
response = client.get('/api/v1/executions')

# ✅ CORRECT
response = client.get('/api/v1/executions/')
```

**Reference data :**
```python
# ❌ INCORRECT (missing RefEngine/RefPlatform)
ActionFactory(engine="oracle", platform="aap")

# ✅ CORRECT
RefEngine.objects.create(name="oracle", display_name="Oracle")
RefPlatform.objects.create(name="aap", display_name="AAP")
ActionFactory(engine="oracle", platform="aap")
```

### Architecture backend alignée

**Django 5.2 + DRF 3.16 :**
- Models : Django ORM (Oracle DB)
- Views : DRF APIView, ViewSets
- Serializers : DRF serializers
- Permissions : DRF permissions (IsDBAOrDBOPS, IsOwnerOrDBA)
- Middleware : JWT auth, logging, CORS

**Modules :**
```
idp-portal/django_backend/
├── core/                 # Shared utilities, permissions, fields
├── idp_auth/             # SAML, JWT authentication
├── catalog/              # Actions, tags, categories
├── executions/           # Execution lifecycle, workflows
│   ├── views/           # Split en 4 modules (Story 26.2)
│   └── utils.py         # Utilitaires (Story 26.10)
├── inventory/            # Servers, instances, databases
│   └── services.py      # Split en 3 classes (Story 26.1)
├── profiles/             # Profiles, permissions
├── integrations/         # Integration configs
├── reference/            # RefEngine, RefPlatform, Category
├── audit/                # Audit logs
├── scheduled_executions/ # Scheduled tasks (Epic 11)
└── tests/               # Shared test utilities, KNOWN_ISSUES.md
```

**Factories existantes :**
- `core/factories.py` : UserFactory, ProfileFactory, ActionFactory, etc.
- Tests doivent utiliser ces factories (alignées Story 20.1)

### Standards de test

**DO :**
- ✅ Utiliser UserFactory, ActionFactory, ProfileFactory pour cohérence
- ✅ Ajouter trailing slash aux URLs API (`/api/v1/.../ `)
- ✅ Créer RefEngine/RefPlatform avant ActionFactory si nécessaire
- ✅ Ajouter `referenced_action_id` aux WorkflowStepFactory
- ✅ Utiliser `deactivate_action()` pour disable, pas `update_status('disable')`
- ✅ Tester comportement utilisateur, pas implémentation
- ✅ Documenter tout test skip avec justification dans KNOWN_ISSUES.md

**DON'T :**
- ❌ Créer User avec `is_staff=True` (field n'existe pas)
- ❌ Créer Actions avec transition status invalide
- ❌ Oublier trailing slash sur URLs API (301 redirect au lieu de 200/401)
- ❌ Skip tests sans justification documentée
- ❌ Tester détails d'implémentation (state interne, méthodes privées)
- ❌ Dupliquer fixtures — utiliser factories partagées

### Références techniques

**Documentation Django 5.2 :**
- Models : https://docs.djangoproject.com/en/5.2/topics/db/models/
- Testing : https://docs.djangoproject.com/en/5.2/topics/testing/

**Documentation DRF 3.16 :**
- Serializers : https://www.django-rest-framework.org/api-guide/serializers/
- Permissions : https://www.django-rest-framework.org/api-guide/permissions/
- Testing : https://www.django-rest-framework.org/api-guide/testing/

**Documentation pytest-django :**
- Fixtures : https://pytest-django.readthedocs.io/en/latest/helpers.html
- Database access : https://pytest-django.readthedocs.io/en/latest/database.html

**Documentation Factory Boy :**
- Factories : https://factoryboy.readthedocs.io/en/stable/
- Subfactories : https://factoryboy.readthedocs.io/en/stable/reference.html#subfactory

### Project Structure Notes

**Backend structure (aligné Epic M, Epic 26) :**
- Django 5.2 + DRF 3.16 (Epic M — Migration FastAPI → Django complète)
- Oracle DB avec OracleJSONField custom (Story 17.4)
- SAML 2.0 + JWT auth (Story m-7)
- Celery + Redis pour retry async (Story 20.3)
- Middleware logging structuré (structlog, Story m-8)

**Fichiers de configuration :**
- `pytest.ini` — Test discovery, test_settings
- `idp_backend/test_settings.py` — Django config for tests
- `conftest.py` — Shared fixtures
- `tests/KNOWN_ISSUES.md` — Issue tracking (à mettre à jour)
- `tests/README.md` — Testing guidelines (Story 20.1)

**Working directory :**
- `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend`

**Python venv :**
- `.venv/bin/python`

**Test runner :**
- `.venv/bin/python -m pytest`

### Références

- [Source: planning-artifacts/epic-26-qualite-code-assessment-fev-2026.md#Story 26.14]
- [Source: idp-portal/django_backend/tests/KNOWN_ISSUES.md — 84.8% pass rate, 181 failures]
- [Source: implementation-artifacts/26-13-corriger-tous-tests-frontend-echec.md — Frontend équivalent (100% success)]
- [Source: implementation-artifacts/20-1-corriger-fixtures-user-tests-catalog-workflow.md — +95 tests fixed]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

Analyse initiale : 252 échecs identifiés via `pytest --tb=line -q`

### Completion Notes List

**Résultats finaux :** 2249/2251 tests passent (99.9%), 2 skips justifiés, 0 collection errors

**Corrections systémiques (135 tests corrigés) :**
- `RATELIMIT_ENABLED = False` dans test_settings.py — désactive le rate limiting pour tous les tests (~60 tests)
- Trailing slashes ajoutés aux URLs de test manquantes (~80 tests)

**Corrections par module :**
- Auth/JWT (ISSUE-003, ISSUE-015) : trailing slashes + rate limiting désactivé
- RBAC (ISSUE-001, ISSUE-002) : trailing slashes dans test_authorization_rbac.py
- Reference (ISSUE-010, ISSUE-011) : trailing slashes, user creation corrigée, ordering corrigé
- Inventory (ISSUE-013) : trailing slashes, mock user setup (ad_groups), cache clearing
- Execution (ISSUE-014, ISSUE-016, ISSUE-020) : trailing slashes, mock paths (validate_environment), soft delete
- Health Check (ISSUE-012) : trailing slash, ServiceNow URL pattern fix
- Integrations (ISSUE-017) : rate limiting désactivé
- Profiles (ISSUE-018) : rate limiting, user.profile='dbops' pour admin endpoints
- Integration E2E (ISSUE-019) : deactivate_action(), json.loads() pour steps
- JSON Schema (ISSUE-005) : déjà passant
- Rate limiting tests : @override_settings(RATELIMIT_ENABLED=True) par classe
- Exception handling : bare `except Exception:` → `except Exception as e:`, URLs, mock paths
- Gate evaluator : requires_maintenance_window dans test params
- Container workflow : mock run() → run_sync() (SQLite threading)

**Corrections code production (4 fichiers) :**
- `integrations/signals.py` : 2x `except Exception:` → `except Exception as e:` (lignes 56, 81) ✅
- `executions/container_workflow_runtime.py` : `except Exception:` → `except Exception as cleanup_error:` (ligne 421) ✅
- `inventory/rbac_filter.py` : retourner [] quand pas ALL access et pas de restrictions ✅ SECURITY FIX
- `profiles/serializers.py` : retirer `default=list` sur 6 champs ListField (exclusion_patterns, action_ids, tag_patterns, environments, target_names, target_patterns) pour cohérence - code review fix

### Change Log

- 2026-02-13: Story 26.14 — 252 tests corrigés, pass rate 84.8% → 99.9% (2249/2251)
- 2026-02-13: Code review adversarial — 1 issue corrigé (MEDIUM-1: suppression default=list sur 5 champs supplémentaires pour cohérence), MEDIUM-2 rejeté (projet enforce 'except Exception as e'), MEDIUM-3 acknowledged as design choice

### File List

**Test settings :**
- `idp-portal/django_backend/idp_backend/test_settings.py` — RATELIMIT_ENABLED=False

**Code production modifié :**
- `idp-portal/django_backend/integrations/signals.py` — except Exception as e
- `idp-portal/django_backend/executions/container_workflow_runtime.py` — except Exception as cleanup_error
- `idp-portal/django_backend/inventory/rbac_filter.py` — empty restrictions = no targets
- `idp-portal/django_backend/profiles/serializers.py` — remove default=list on exclusion_patterns

**Tests corrigés :**
- `idp-portal/django_backend/core/tests/test_health_check.py`
- `idp-portal/django_backend/core/tests/test_models.py`
- `idp-portal/django_backend/executions/tests/test_container_workflow_integration.py`
- `idp-portal/django_backend/executions/tests/test_environment_validation.py`
- `idp-portal/django_backend/executions/tests/test_exception_handling.py`
- `idp-portal/django_backend/executions/tests/test_execution_targets.py`
- `idp-portal/django_backend/executions/tests/test_gate_evaluator.py`
- `idp-portal/django_backend/executions/tests/test_models.py`
- `idp-portal/django_backend/executions/tests/test_scheduled_execution_put.py`
- `idp-portal/django_backend/executions/tests/test_story_13_5.py`
- `idp-portal/django_backend/executions/tests/test_story_25_5_mutex_validation.py`
- `idp-portal/django_backend/executions/tests/test_story_4_11.py`
- `idp-portal/django_backend/executions/tests/test_story_4_12.py`
- `idp-portal/django_backend/executions/tests/test_workflow_runtime_retry_slow.py`
- `idp-portal/django_backend/inventory/tests/test_environments.py`
- `idp-portal/django_backend/inventory/tests/test_views.py`
- `idp-portal/django_backend/profiles/tests/test_api_exclusion_patterns.py`
- `idp-portal/django_backend/reference/tests/test_views.py`
- `idp-portal/django_backend/tests/integration/test_action_lifecycle.py`
- `idp-portal/django_backend/tests/integration/test_audit_trail.py`
- `idp-portal/django_backend/tests/integration/test_parametrized.py`
- `idp-portal/django_backend/tests/integration/test_performance.py`
- `idp-portal/django_backend/tests/security/test_authentication_security.py`
- `idp-portal/django_backend/tests/security/test_authorization_rbac.py`
- `idp-portal/django_backend/tests/security/test_rate_limiting_security.py`

**Documentation :**
- `idp-portal/django_backend/tests/KNOWN_ISSUES.md`

**Sprint tracking :**
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
