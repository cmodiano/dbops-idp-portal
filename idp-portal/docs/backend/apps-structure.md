# Structure des Apps Django

## Vue d'ensemble

Le backend est organisé en 6 apps Django, chacune responsable d'un domaine fonctionnel spécifique.

```
django_backend/
├── idp_backend/           # Configuration projet Django
│   ├── settings.py        # Configuration (DB, DRF, CORS, JWT, SAML)
│   ├── urls.py            # Routes principales
│   ├── wsgi.py            # Point d'entrée WSGI
│   └── asgi.py            # Point d'entrée ASGI
├── catalog/               # App: Catalogue d'actions
├── profiles/              # App: Profils et permissions RBAC
├── idp_auth/              # App: Authentification SAML/JWT
├── integrations/          # App: Plateformes distantes
├── executions/            # App: Exécutions d'actions
├── core/                  # App: Fonctionnalités transverses
├── tests/                 # Tests d'intégration globaux
├── manage.py              # Script Django management
├── pyproject.toml         # Métadonnées et dépendances Python
├── requirements.lock      # Lockfile runtime (production)
└── requirements-dev.lock  # Lockfile dev (runtime + outils)
```

## Structure standard d'une app

Chaque app Django suit cette structure:

```
{app_name}/
├── __init__.py
├── admin.py           # Configuration Django admin
├── apps.py            # Configuration app
├── models.py          # Modèles Django (mappés sur Oracle)
├── serializers.py     # Serializers DRF pour validation/sérialisation
├── services.py        # Logique métier (transactions, validations)
├── views.py           # ViewSets DRF pour endpoints API
├── urls.py            # Routes URL de l'app
├── migrations/        # Migrations Django (cohabitation Flyway)
│   ├── __init__.py
│   └── 0001_initial.py
└── tests/             # Tests unitaires et d'intégration
    ├── __init__.py
    ├── test_services.py
    └── test_views.py
```

## Apps détaillées

### 1. catalog

**Responsabilité:** Gestion du catalogue d'actions (CRUD, tags, statuts, favoris)

| Fichier | Contenu |
|---------|---------|
| `models.py` | `Action`, `Tag`, `ActionTag`, `UserFavorite`, `ActionManager` |
| `serializers.py` | `ActionSerializer`, `ActionCreateSerializer`, `ActionListSerializer`, `TagSerializer` |
| `services.py` | `CatalogService` (create, update, delete, status transitions, tags sync) |
| `views.py` | `ActionViewSet` (admin), `CatalogActionViewSet` (public), `TagViewSet` |
| `urls.py` | Routes admin/actions, catalog/actions, tags |

**Endpoints:**
- `POST/GET/PUT/DELETE /api/v1/admin/actions` - CRUD admin
- `GET /api/v1/catalog/actions` - Liste catalogue (RBAC)
- `GET /api/v1/tags` - Liste tous les tags

### 2. profiles

**Responsabilité:** Gestion des profils utilisateurs et permissions RBAC

| Fichier | Contenu |
|---------|---------|
| `models.py` | `Profile`, `ProfileActionPermission`, `ProfileTargetPermission`, `ProfileManager` |
| `serializers.py` | `ProfileSerializer`, `ProfilePermissionSerializer` |
| `services.py` | `ProfileService` (CRUD, permissions, cumulative permissions) |
| `services_export_import.py` | Export/Import YAML des profils |
| `views.py` | `ProfileViewSet`, `ProfileExportView`, `ProfileImportView` |
| `urls.py` | Routes admin/profiles |

**Endpoints:**
- `POST/GET/PUT/DELETE /api/v1/admin/profiles` - CRUD profils
- `GET/PUT /api/v1/admin/profiles/{id}/action-permissions` - Permissions actions
- `GET/PUT /api/v1/admin/profiles/{id}/target-permissions` - Permissions targets
- `GET /api/v1/admin/profiles/export` - Export YAML
- `POST /api/v1/admin/profiles/import` - Import YAML

### 3. idp_auth

**Responsabilité:** Authentification SAML 2.0 et sessions JWT

| Fichier | Contenu |
|---------|---------|
| `models.py` | `User`, `UserManager` |
| `serializers.py` | `LoginRequestSerializer`, `UserSerializer` |
| `authentication.py` | `JWTAuthentication` (backend DRF) |
| `jwt_utils.py` | `create_token`, `verify_token`, `decode_token_unsafe` |
| `saml_config.py` | Configuration pysaml2 |
| `saml_utils.py` | Helpers SAML |
| `middleware.py` | `AuditAuthMiddleware` |
| `views.py` | `SAMLLoginView`, `SAMLCallbackView`, `RefreshView`, `MeView` |
| `urls.py` | Routes auth/saml, auth/refresh, auth/me |

**Endpoints:**
- `GET /api/v1/auth/saml/login` - Initiation SAML
- `POST /api/v1/auth/saml/callback` - Callback IdP
- `POST /api/v1/auth/refresh` - Rafraîchir token
- `GET /api/v1/auth/me` - Profil utilisateur courant

### 4. integrations

**Responsabilité:** Configuration des plateformes distantes (AAP, Terraform, ServiceNow, etc.)

| Fichier | Contenu |
|---------|---------|
| `models.py` | `Integration`, `IntegrationManager`, enums `IntegrationType`, `AuthFlow` |
| `serializers.py` | `IntegrationSerializer`, `IntegrationCreateSerializer` |
| `validation.py` | Validation JSON Schema pour config |
| `upload_views.py` | Upload icônes |
| `views.py` | `IntegrationViewSet` |
| `urls.py` | Routes admin/integrations |

**Endpoints:**
- `POST/GET/PUT/DELETE /api/v1/integrations` - CRUD intégrations
- `POST /api/v1/integrations/{id}/icon` - Upload icône

### 5. executions

**Responsabilité:** Gestion des exécutions d'actions, steps et scheduling

| Fichier | Contenu |
|---------|---------|
| `models.py` | `Execution`, `ExecutionStep`, `ScheduledExecution`, `RecurringPattern` + managers |
| `serializers.py` | `ExecutionSerializer`, `ExecutionStepSerializer`, `ScheduledExecutionSerializer` |
| `services.py` | Services d'exécution (si implémenté) |
| `views.py` | `ExecutionViewSet`, `ScheduledExecutionViewSet` |
| `urls.py` | Routes executions, scheduled-executions |

**Endpoints:**
- `POST/GET /api/v1/executions` - Soumettre/Lister exécutions
- `GET /api/v1/executions/{id}` - Détails exécution
- `POST/GET /api/v1/scheduled-executions` - Scheduled executions
- `GET /api/v1/scheduled-executions/pending` - Pour scheduler externe

### 6. core

**Responsabilité:** Fonctionnalités transverses (audit, exceptions, pagination, middleware)

| Fichier | Contenu |
|---------|---------|
| `models.py` | `AuditLog`, `AuditLogManager`, enums `AuditActionType`, `AuditEntityType` |
| `serializers.py` | `HealthStatusSerializer` |
| `services.py` | `AuditService` (create_entry, list, export CSV/PDF) |
| `exceptions.py` | `NotFoundError`, `BadRequestError`, `InvalidStateError`, `custom_exception_handler` |
| `pagination.py` | `CustomPageNumberPagination` |
| `permissions.py` | `AdminProfilePermission`, `OptionalUserPermission` (alias: `DBOPSProfilePermission`) |
| `rbac.py` | Helpers RBAC |
| `middleware.py` | `CorrelationIdMiddleware`, `RequestResponseLoggingMiddleware`, `SecurityHeadersMiddleware` |
| `views.py` | `health_check` |
| `urls.py` | Route health |

**Endpoints:**
- `GET /api/v1/health` - Health check (DB + services externes)

## Diagramme de dépendances

```
                    ┌──────────────┐
                    │   core       │
                    │ (transverse) │
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
  │  idp_auth   │  │ integrations│  │   catalog   │
  │   (auth)    │  │ (platforms) │  │  (actions)  │
  └──────┬──────┘  └─────────────┘  └──────┬──────┘
         │                                  │
         │         ┌─────────────┐          │
         └────────►│  profiles   │◄─────────┘
                   │   (RBAC)    │
                   └──────┬──────┘
                          │
                          ▼
                   ┌─────────────┐
                   │ executions  │
                   │  (runtime)  │
                   └─────────────┘
```

## Configuration (settings.py)

### Apps installées

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'corsheaders',
    # Local apps
    'catalog',
    'profiles',
    'idp_auth',
    'integrations',
    'core',
    'executions',
]
```

### Middleware

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.CorrelationIdMiddleware',       # Correlation ID
    'core.middleware.RequestResponseLoggingMiddleware', # Request logging
    'core.middleware.SecurityHeadersMiddleware',      # Security headers
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',         # CORS
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'idp_auth.middleware.AuditAuthMiddleware',       # Auth audit
]
```

### Configuration DRF

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'idp_auth.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.CustomPageNumberPagination',
    'PAGE_SIZE': 25,
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
}
```
