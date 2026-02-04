# Story 12.1: Documentation backend implementation

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

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

- [ ] Task 1: Documenter la structure des apps Django (AC: 1)
  - [ ] Documenter les apps installées et leurs responsabilités
  - [ ] Documenter l'organisation des dossiers et fichiers
  - [ ] Créer un diagramme de dépendances entre apps
- [ ] Task 2: Documenter les modèles et relations (AC: 1)
  - [ ] Documenter tous les modèles Django avec leurs champs
  - [ ] Documenter les relations ForeignKey, OneToOne, ManyToMany
  - [ ] Documenter les managers personnalisés et leurs méthodes
  - [ ] Documenter les helpers JSON pour les champs CLOB
  - [ ] Créer un diagramme ER simplifié
- [ ] Task 3: Documenter les services et logique métier (AC: 1)
  - [ ] Documenter CatalogService et ses méthodes
  - [ ] Documenter ProfileService et gestion RBAC
  - [ ] Documenter ExecutionService (si existant)
  - [ ] Documenter AuditService
  - [ ] Documenter les patterns de transaction et validation
- [ ] Task 4: Documenter les endpoints API et serializers (AC: 1)
  - [ ] Documenter tous les ViewSets et leurs actions
  - [ ] Documenter les serializers et validation
  - [ ] Documenter la pagination personnalisée
  - [ ] Documenter le format de réponse (snake_case, wrapper data/error)
  - [ ] Documenter les codes HTTP et gestion d'erreurs
- [ ] Task 5: Documenter la gestion des permissions RBAC (AC: 1)
  - [ ] Documenter le système de profils et permissions
  - [ ] Documenter les permissions DRF (DBOPSProfilePermission, OptionalUserPermission)
  - [ ] Documenter le filtrage RBAC dans les ViewSets
  - [ ] Documenter le cumul des permissions multi-profils
- [ ] Task 6: Documenter l'intégration SAML (AC: 1)
  - [ ] Documenter le flow d'authentification SAML (si implémenté)
  - [ ] Documenter la gestion des sessions JWT
  - [ ] Documenter la résolution des profils depuis AD groups
- [ ] Task 7: Documenter le middleware et logging (AC: 1)
  - [ ] Documenter le middleware CORS
  - [ ] Documenter le middleware de correlation ID
  - [ ] Documenter le logging structuré JSON
  - [ ] Documenter l'intégration avec Splunk
- [ ] Task 8: Documenter les tests et couverture (AC: 1)
  - [ ] Documenter la structure des tests (unit, integration)
  - [ ] Documenter les fixtures et mocks utilisés
  - [ ] Documenter la couverture de code actuelle
  - [ ] Documenter comment exécuter les tests
- [ ] Task 9: Créer des guides pas-à-pas avec exemples (AC: 2)
  - [ ] Guide: Comment ajouter un nouvel endpoint API
  - [ ] Guide: Comment ajouter un nouveau modèle
  - [ ] Guide: Comment ajouter une nouvelle permission RBAC
  - [ ] Guide: Comment ajouter un nouveau service
- [ ] Task 10: Créer des diagrammes d'architecture (AC: 3)
  - [ ] Diagramme des couches (API → Services → Repositories → Models → DB)
  - [ ] Diagramme de flux de données pour une exécution
  - [ ] Diagramme de flux d'authentification et RBAC
- [ ] Task 11: Créer un guide de contribution (AC: 4)
  - [ ] Setup environnement de développement
  - [ ] Conventions de code (naming, structure, format)
  - [ ] Processus de review et validation
  - [ ] Comment maintenir la documentation à jour

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
- Pas de SAML implémenté encore: Story M.7 prévue pour l'authentification complète
- Certains services manquants: ExecutionService à documenter si existant, sinon à créer

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

[À compléter lors de l'implémentation]

### Debug Log References

[À compléter lors de l'implémentation]

### Completion Notes List

[À compléter lors de l'implémentation]

### File List

[À compléter lors de l'implémentation]
