# Story 12.1: Documentation backend implementation

Status: done

<!-- Story context engine analysis completed - comprehensive developer guide created -->

## Story

As a développeur rejoignant l'équipe,
I want une documentation détaillée de l'implémentation backend (Django),
So that je peux comprendre rapidement l'architecture, les patterns utilisés et comment contribuer.

## Acceptance Criteria

**Given** la migration Django est complétée
**When** la documentation backend est rédigée
**Then** elle inclut : structure des apps Django, modèles et relations, services et managers, endpoints API et serializers, gestion des permissions RBAC, intégration SAML, middleware et logging, tests et couverture

**Given** un développeur consulte la documentation
**When** il cherche une information spécifique (ex: comment ajouter un endpoint)
**Then** il trouve un guide pas-à-pas avec exemples de code

**And** la documentation inclut des diagrammes d'architecture (couches, flux de données)
**And** la documentation inclut un guide de contribution (setup dev, conventions de code, processus de review)
**And** la documentation est maintenue à jour avec les changements majeurs

## Tasks / Subtasks

- [x] Task 1: Documenter la structure des apps Django (AC: 1)
  - [x] Documenter les apps installées et leurs responsabilités
  - [x] Documenter l'organisation des dossiers et fichiers
  - [x] Créer un diagramme de dépendances entre apps
- [x] Task 2: Documenter les modèles et relations (AC: 1)
  - [x] Documenter tous les modèles Django avec leurs champs
  - [x] Documenter les relations ForeignKey, OneToOne, ManyToMany
  - [x] Documenter les managers personnalisés et leurs méthodes
  - [x] Documenter les helpers JSON pour les champs CLOB
  - [x] Créer un diagramme ER simplifié
- [x] Task 3: Documenter les services et logique métier (AC: 1)
  - [x] Documenter CatalogService et ses méthodes
  - [x] Documenter ProfileService et gestion RBAC
  - [x] Documenter ExecutionService (si existant)
  - [x] Documenter AuditService
  - [x] Documenter les patterns de transaction et validation
- [x] Task 4: Documenter les endpoints API et serializers (AC: 1)
  - [x] Documenter tous les ViewSets et leurs actions
  - [x] Documenter les serializers et validation
  - [x] Documenter la pagination personnalisée
  - [x] Documenter le format de réponse (snake_case, wrapper data/error)
  - [x] Documenter les codes HTTP et gestion d'erreurs
- [x] Task 5: Documenter la gestion des permissions RBAC (AC: 1)
  - [x] Documenter le système de profils et permissions
  - [x] Documenter les permissions DRF (DBOPSProfilePermission, OptionalUserPermission)
  - [x] Documenter le filtrage RBAC dans les ViewSets
  - [x] Documenter le cumul des permissions multi-profils
- [x] Task 6: Documenter l'intégration SAML (AC: 1)
  - [x] Documenter le flow d'authentification SAML (si implémenté)
  - [x] Documenter la gestion des sessions JWT
  - [x] Documenter la résolution des profils depuis AD groups
- [x] Task 7: Documenter le middleware et logging (AC: 1)
  - [x] Documenter le middleware CORS
  - [x] Documenter le middleware de correlation ID
  - [x] Documenter le logging structuré JSON
  - [x] Documenter l'intégration avec Splunk
- [x] Task 8: Documenter les tests et couverture (AC: 1)
  - [x] Documenter la structure des tests (unit, integration)
  - [x] Documenter les fixtures et mocks utilisés
  - [x] Documenter la couverture de code actuelle
  - [x] Documenter comment exécuter les tests
- [x] Task 9: Créer des guides pas-à-pas avec exemples (AC: 2)
  - [x] Guide: Comment ajouter un nouvel endpoint API
  - [x] Guide: Comment ajouter un nouveau modèle
  - [x] Guide: Comment ajouter une nouvelle permission RBAC
  - [x] Guide: Comment ajouter un nouveau service
- [x] Task 10: Créer des diagrammes d'architecture (AC: 3)
  - [x] Diagramme des couches (API → Services → Repositories → Models → DB)
  - [x] Diagramme de flux de données pour une exécution
  - [x] Diagramme de flux d'authentification et RBAC
- [x] Task 11: Créer un guide de contribution (AC: 4)
  - [x] Setup environnement de développement
  - [x] Conventions de code (naming, structure, format)
  - [x] Processus de review et validation
  - [x] Comment maintenir la documentation à jour

## Dev Notes

### Architecture Django actuelle

**Apps Django installées:**
- `catalog`: Gestion du catalogue d'actions (CRUD, tags, statuts)
- `profiles`: Gestion des profils utilisateurs et permissions RBAC
- `idp_auth`: Authentification et gestion des utilisateurs
- `integrations`: Gestion des intégrations avec plateformes externes
- `core`: Fonctionnalités transverses (audit, pagination, exceptions, permissions)
- `executions`: Gestion des exécutions d'actions et steps

**Structure des apps:**
Chaque app Django suit la structure standard:
```
{app_name}/
├── models.py          # Modèles Django mappés sur Oracle
├── serializers.py     # Serializers DRF pour validation et sérialisation
├── views.py           # ViewSets DRF pour endpoints API
├── services.py        # Logique métier (transactions, validations, audit)
├── urls.py            # Routes URL de l'app
├── admin.py           # Configuration Django admin (optionnel)
├── tests/             # Tests unitaires et d'intégration
└── migrations/        # Migrations Django (cohabitation avec Flyway)
```

**Patterns architecturaux:**
1. **Repository Pattern via Managers**: Chaque modèle a un manager personnalisé avec méthodes de requête (`ActionManager`, `ExecutionManager`, etc.)
2. **Service Layer**: Logique métier dans `services.py` (CatalogService, ProfileService, AuditService)
3. **ViewSets DRF**: Endpoints API organisés par ViewSet (ActionViewSet, CatalogActionViewSet, etc.)
4. **Serializers DRF**: Validation et sérialisation avec serializers dédiés par action
5. **Transactions**: Utilisation de `@transaction.atomic` pour opérations critiques
6. **Audit automatique**: Chaque mutation importante loggée via AuditService

**Mapping Oracle → Django:**
- Tables Oracle en UPPER_SNAKE_CASE mappées sur modèles Django avec `db_column`
- Champs CLOB stockant JSON utilisent des helpers (`get_*`, `set_*`) pour sérialisation/désérialisation
- Enums Oracle CHECK constraints mappés sur `models.TextChoices`
- Relations ForeignKey mappées avec `on_delete` approprié

**Gestion des permissions RBAC:**
- Profils liés aux AD groups via `Profile.ad_group`
- Permissions cumulatives calculées via `ProfileService.get_cumulative_permissions()`
- Filtrage RBAC dans ViewSets via `_filter_by_rbac()` et `_check_rbac_for_action()`
- Permissions DRF: `DBOPSProfilePermission` (admin), `OptionalUserPermission` (public avec RBAC)

**Format API:**
- Toutes les réponses wrappées dans `{"data": ...}` ou `{"error": ...}`
- Champs en snake_case (pas camelCase)
- Pagination via `CustomPageNumberPagination` (page_size=25)
- Codes HTTP standards: 200, 201, 400, 401, 403, 404, 500

**Gestion d'erreurs:**
- Exceptions custom dans `core.exceptions` (NotFoundError, BadRequestError, InvalidStateError)
- Handler global dans `REST_FRAMEWORK['EXCEPTION_HANDLER']` → `core.exceptions.custom_exception_handler`
- Format d'erreur: `{"error": {"code": "...", "message": "...", "details": {...}}}`

**Tests:**
- Structure: `tests/unit/` et `tests/integration/`
- Framework: pytest + pytest-django
- Fixtures: conftest.py avec mocks DB, auth, etc.
- Couverture: À documenter (objectif: au moins égal à FastAPI)

**Migration Flyway → Django:**
- Cohabitation temporaire: Flyway continue de gérer le schéma, Django migrations marquées `--fake initial`
- Stratégie documentée dans `MIGRATION_STRATEGY.md`
- Après Epic M: bascule complète vers Django migrations

### Source tree components à documenter

**Modèles principaux:**
- `catalog/models.py`: Action, Tag, ActionTag, UserFavorite
- `profiles/models.py`: Profile, ProfileActionPermission, ProfileTargetPermission
- `idp_auth/models.py`: User, UserManager
- `executions/models.py`: Execution, ExecutionStep, ScheduledExecution, RecurringPattern
- `core/models.py`: AuditLog, AuditActionType, AuditEntityType
- `integrations/models.py`: Integration

**Services principaux:**
- `catalog/services.py`: CatalogService (CRUD actions, tags, statuts)
- `profiles/services.py`: ProfileService (RBAC, permissions cumulatives)
- `core/services.py`: AuditService (logs immutables, export CSV/PDF)
- `executions/services.py`: ExecutionService (si existant)

**ViewSets principaux:**
- `catalog/views.py`: ActionViewSet (admin CRUD), CatalogActionViewSet (public avec RBAC), TagViewSet
- `profiles/views.py`: ProfileViewSet, ProfilePermissionViewSet
- `executions/views.py`: ExecutionViewSet, ScheduledExecutionViewSet
- `core/views.py`: HealthCheckView

**Serializers:**
- `catalog/serializers.py`: ActionSerializer, ActionCreateSerializer, ActionListSerializer, TagSerializer
- `profiles/serializers.py`: ProfileSerializer, ProfilePermissionSerializer
- `executions/serializers.py`: ExecutionSerializer, ExecutionStepSerializer
- `core/serializers.py`: HealthStatusSerializer

**Permissions:**
- `core/permissions.py`: DBOPSProfilePermission, OptionalUserPermission

**Exceptions:**
- `core/exceptions.py`: NotFoundError, BadRequestError, InvalidStateError, custom_exception_handler

**Pagination:**
- `core/pagination.py`: CustomPageNumberPagination

**URLs:**
- `idp_backend/urls.py`: Routes principales
- `catalog/urls.py`: Routes catalogue
- `core/urls.py`: Routes core (health)

### Testing standards summary

**Structure:**
- Tests unitaires: `{app}/tests/test_{module}.py`
- Tests d'intégration: `{app}/tests/integration/test_{feature}.py`
- Fixtures partagées: `conftest.py` à la racine

**Framework:**
- pytest + pytest-django
- Client DRF pour tests API: `from rest_framework.test import APIClient`

**Patterns de test:**
- Mock de la DB: Utiliser `@pytest.mark.django_db`
- Mock de l'auth: Créer des utilisateurs de test
- Mock des services externes: Mock Vault, ServiceNow, etc.
- Assertions: Vérifier statut HTTP, corps de réponse, cas d'erreur

**Couverture:**
- Objectif: Au moins égal à la couverture FastAPI
- Mesure: `pytest-cov` ou équivalent
- CI: Exécution automatique des tests à chaque push

### Project Structure Notes

**Alignement avec architecture:**
- Structure conforme à l'architecture documentée dans `architecture.md`
- Apps Django alignées sur les domaines fonctionnels (catalog, executions, profiles)
- Services alignés sur la logique métier (pas de SQL dans les ViewSets)
- Modèles alignés sur le schéma Oracle existant

**Conventions de code:**
- Naming: snake_case pour fichiers Python, PascalCase pour classes
- Imports: Organisés par standard library → third-party → local
- Docstrings: Format Google style pour classes et méthodes publiques
- Type hints: Utilisés pour les signatures de méthodes

**Détections de variances:**
- Cohabitation Flyway/Django: Temporaire, documentée dans MIGRATION_STRATEGY.md
- SAML 2.0 implémenté dans Story M-7 (code review complété 2026-02-04)
- Backend Django déclaré PRODUCTION-READY après Epic M (2026-02-05)

### Contexte Epic M - Rétrospective

L'Epic M (migration FastAPI → Django REST) est terminé avec succès. Points clés de la rétrospective (2026-02-05):

**Métriques:**
- 10/10 stories complétées en 3 jours
- 42 endpoints migrés
- 82% couverture tests (objectif: 85%)
- ~70 issues code review détectées et corrigées

**Patterns récurrents identifiés (à éviter):**
| Pattern | Occurrences | Sévérité |
|---------|-------------|----------|
| Types d'audit hardcodés vs enums | 4/10 stories | MEDIUM |
| N+1 queries | 3/10 stories | HIGH |
| Validation paramètres manquante | 3/10 stories | MEDIUM |
| Failles sécurité | 2/10 stories | CRITICAL |

**Actions recommandées pour la documentation:**
1. Créer une checklist standard pour nouveaux endpoints (validations, sécurité)
2. Documenter les décisions architecturales (ADRs)
3. Inclure un guide de migration FastAPI → Django pour référence future
4. Documenter les patterns ORM (éviter N+1 avec select_related/prefetch_related)

### Documentation Existante à Intégrer

Ces documents dans `django_backend/docs/` doivent être référencés et intégrés:
- `django-orm-migration-notes.md` - Migration SQL brut → ORM (13 KB, détaillé)
- `drf-api-migration-notes.md` - Migration API FastAPI → DRF (16 KB, détaillé)
- `TRANSACTION_AUDIT_STRATEGY.md` - Stratégie transactions/audit (8 KB)
- `sso-architecture.md` / `sso-runbook.md` - Architecture SAML (11 KB / 6 KB)
- `observability-architecture.md` / `observability-runbook.md` - Logging (9 KB / 5 KB)
- `logging-conventions.md` - Conventions structlog JSON (5 KB)

### Technical Stack Versions (Février 2026)

| Technologie | Version | Notes |
|-------------|---------|-------|
| Django | 5.2.11 | Framework principal |
| Django REST Framework | 3.15+ | API REST |
| python-oracledb | 3.4.1 (mode Thin) | Connexion Oracle |
| structlog | dernière | Logging JSON structuré |
| pytest-django | dernière | Tests |
| gunicorn | 23.0.0 | Production WSGI |

### References

**Architecture:**
- [Source: _bmad-output/planning-artifacts/architecture.md] - Architecture complète du projet
- [Source: idp-portal/django_backend/MIGRATION_STRATEGY.md] - Stratégie de migration Flyway → Django

**Modèles Django:**
- [Source: idp-portal/django_backend/catalog/models.py] - Modèles catalogue (Action, Tag, etc.)
- [Source: idp-portal/django_backend/profiles/models.py] - Modèles profils et permissions RBAC
- [Source: idp-portal/django_backend/executions/models.py] - Modèles exécutions et scheduled executions
- [Source: idp-portal/django_backend/core/models.py] - Modèles core (AuditLog, etc.)
- [Source: idp-portal/django_backend/idp_auth/models.py] - Modèle User

**Services:**
- [Source: idp-portal/django_backend/catalog/services.py] - CatalogService (CRUD actions, tags, statuts)
- [Source: idp-portal/django_backend/core/services.py] - AuditService (logs immutables, export)
- [Source: idp-portal/django_backend/profiles/services.py] - ProfileService (RBAC, permissions cumulatives)

**ViewSets et API:**
- [Source: idp-portal/django_backend/catalog/views.py] - ActionViewSet, CatalogActionViewSet, TagViewSet
- [Source: idp-portal/django_backend/core/views.py] - HealthCheckView
- [Source: idp-portal/django_backend/idp_backend/settings.py] - Configuration DRF, CORS, pagination

**Permissions et sécurité:**
- [Source: idp-portal/django_backend/core/permissions.py] - DBOPSProfilePermission, OptionalUserPermission
- [Source: idp-portal/django_backend/catalog/views.py#_filter_by_rbac] - Filtrage RBAC dans ViewSets

**Exceptions et erreurs:**
- [Source: idp-portal/django_backend/core/exceptions.py] - Exceptions custom et handler global

**Tests:**
- [Source: idp-portal/django_backend/tests/README.md] - Structure et conventions de tests

**Epic et contexte:**
- [Source: _bmad-output/planning-artifacts/epics.md#Epic-12] - Epic 12: Documentation technique
- [Source: _bmad-output/planning-artifacts/prd.md] - PRD avec exigences fonctionnelles et non-fonctionnelles

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- 2026-02-05: All 11 tasks completed - comprehensive Django backend documentation created
- Created 10 documentation files in `idp-portal/docs/backend/`
- ASCII diagrams used for architecture, ER, and SAML flow (compatible with all markdown renderers)
- All acceptance criteria validated:
  - AC1: All backend components documented (apps, models, services, endpoints, RBAC, SAML, middleware, tests)
  - AC2: Step-by-step guides with code examples included in contributing.md
  - AC3: Architecture diagrams included (layers, ER, SAML flow, RBAC flow)
  - AC4: Contribution guide with dev setup, conventions, and PR process

### File List

**Documentation créée dans `idp-portal/docs/backend/`:**
- `README.md` - Point d'entrée avec vue d'ensemble et index de navigation
- `apps-structure.md` - Structure des 6 apps Django et leurs responsabilités
- `models.md` - Modèles, relations, managers personnalisés, helpers JSON, diagramme ER
- `services.md` - CatalogService, ProfileService, AuditService, patterns transaction
- `api-reference.md` - Tous les endpoints, serializers, pagination, codes d'erreur
- `rbac.md` - Système de profils, permissions DRF, filtrage, cumul multi-profils
- `authentication.md` - Flow SAML complet, JWT utils, endpoints auth, mode dev bypass
- `observability.md` - Middleware (ordre, correlation ID, logging), health check, CORS, Splunk
- `testing.md` - Structure tests, fixtures, factories, markers, couverture
- `contributing.md` - Setup dev, conventions, 4 guides pas-à-pas (endpoint, modèle, permission, service)

**Diagrammes inclus (format ASCII):**
- Diagramme des couches backend (README.md, apps-structure.md)
- Diagramme ER des modèles (models.md)
- Diagramme de séquence authentification SAML (authentication.md)
- Diagramme de flux RBAC (rbac.md)

### Change Log

| Date | Changement | Fichiers |
|------|------------|----------|
| 2026-02-05 | Initial: 10 fichiers documentation créés | Tous |
| 2026-02-05 | Code review: 7 fixes (3 HIGH + 4 MEDIUM) | rbac.md, services.md, models.md, api-reference.md, authentication.md, testing.md |

### Code Review Fixes Applied (2026-02-05)

**HIGH-1:** rbac.md - DBOPSProfilePermission documentation complétée avec l'implémentation réelle (multi-méthode: profile attr, M2M, AD groups, superuser fallback)

**HIGH-2:** services.md - Ajout de la méthode `get_by_id()` manquante dans CatalogService

**HIGH-3:** services.md - AuditService.create_entry signature corrigée (enums AuditActionType/AuditEntityType au lieu de strings) + exemple d'utilisation

**MEDIUM-1:** testing.md - Fixtures clarifiées: `force_authenticate()` par défaut + nouvelle fixture `api_client_with_jwt` pour tests d'intégration auth

**MEDIUM-2:** models.md - ProfileManager complété avec méthode `list_with_permissions_count()`

**MEDIUM-3:** api-reference.md - Endpoint `/api/v1/tags/catalog` documenté correctement (action DRF avec url_path)

**MEDIUM-4:** authentication.md - `decode_token_unsafe` warning sécurité renforcé avec tableau cas d'usage

**Issues LOW non corrigées (cosmétiques):**
- LOW-1: Alignement diagramme ASCII
- LOW-2: Version ruff non spécifiée
- LOW-3: Référence settings.py manquante
- LOW-4: .coveragerc vs pyproject.toml
