# Guide de Migration FastAPI → Django — IDP Portal

## 1. Différences clés FastAPI vs Django/DRF

| Aspect | FastAPI (ancien) | Django + DRF (actuel) |
|--------|------------------|-----------------------|
| **Framework** | FastAPI + Uvicorn | Django 5.2 + DRF 3.16 + Gunicorn |
| **ORM** | SQL brut (python-oracledb) | Django ORM (django-oracledb) |
| **Validation** | Pydantic models | DRF Serializers |
| **Routing** | `@app.get("/path")` | `urlpatterns` + `ViewSet` / `APIView` |
| **Auth** | Custom middleware | DRF `authentication_classes` + `permission_classes` |
| **Injection de deps** | `Depends(get_current_user)` | `permission_classes = [IsAuthenticated]` |
| **Transactions** | `async with connection.transaction()` | `@transaction.atomic` |
| **Migrations DB** | Flyway (SQL scripts) | Flyway (SQL scripts) — pas de Django migrations |
| **Tests** | pytest + httpx | pytest-django + DRF `APIClient` |

> **Note** : Les migrations DB restent gérées par Flyway (`database/migrations/V*.sql`), pas par `manage.py migrate`.

## 2. Patterns équivalents

### 2.1. Repository FastAPI → Service Django

**Avant (FastAPI)** :
```python
# catalog_repository.py
class CatalogRepository:
    async def get_action_by_id(self, action_id: int) -> dict | None:
        async with get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM ACTIONS_CATALOG WHERE ID = :1", [action_id])
            return await cursor.fetchone()
```

**Après (Django)** :
```python
# catalog/services.py
class CatalogService:
    def get_by_id(self, action_id: int) -> Action | None:
        try:
            return Action.objects.get(id=action_id)
        except Action.DoesNotExist:
            return None
```

**Conventions** :
- Un fichier `services.py` par app (voir ADR-003)
- Le service encapsule toute la logique métier
- Les vues n'appellent jamais l'ORM directement

### 2.2. Validation Pydantic → DRF Serializers

**Avant (FastAPI)** :
```python
class ActionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    platform: PlatformEnum
```

**Après (DRF)** :
```python
class ActionCreateSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=1, max_length=255)
    description = serializers.CharField(required=False, allow_null=True)
    platform = serializers.ChoiceField(choices=PlatformType.choices)
```

**Différences notables** :
- DRF : `is_valid(raise_exception=True)` pour valider (Pydantic valide au constructeur)
- DRF : `validated_data` dict vs attributs Pydantic
- DRF : Validateurs custom via `validate_<field>()` ou `validate()` sur le serializer

### 2.3. Depends → Permission classes

**Avant (FastAPI)** :
```python
@app.get("/admin/actions")
async def list_actions(user: User = Depends(require_dbops)):
    ...
```

**Après (DRF)** :
```python
class ActionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, DBOPSProfilePermission]

    def list(self, request):
        ...
```

Le système RBAC est dans `core/permissions.py`. La permission `DBOPSProfilePermission` vérifie `request.user.profile == 'dbops'`.

### 2.4. Gestion des erreurs

**Avant** : Exceptions HTTPException FastAPI
**Après** : Exceptions custom dans `core/exceptions.py`

```python
from core.exceptions import NotFoundError, InvalidStateError, BadRequestError, ForbiddenError

# 404
raise NotFoundError(code="NOT_FOUND", message="Action introuvable", details={"id": action_id})

# 400
raise InvalidStateError(code="INVALID_CONFIG", message="Config invalide", details={})

# 403
raise ForbiddenError(code="NO_PROFILE", message="Aucun profil", details={})
```

Le handler global (`core/exceptions.py`) convertit ces exceptions en réponses JSON `{"error": {"code": ..., "message": ..., "details": ...}}`.

## 3. Structure du projet Django IDP

```
django_backend/
├── idp_backend/        # Projet Django (settings, urls, wsgi)
│   ├── settings.py     # Config production (Oracle, Redis, SAML)
│   ├── test_settings.py # Config tests (SQLite, LocMemCache)
│   └── urls.py         # URL root → inclut les apps
│
├── core/               # Utilitaires partagés (importable par toutes les apps)
│   ├── exceptions.py   # NotFoundError, InvalidStateError, etc.
│   ├── permissions.py  # DBOPSProfilePermission, IsAuditorPermission
│   ├── rbac.py         # Navigation tabs, business profile check
│   ├── throttling.py   # Rate limiting (GeneralAPIThrottle, etc.)
│   ├── services.py     # AuditService
│   ├── models.py       # AuditLog, AuditActionType, AuditEntityType
│   └── middleware.py   # Correlation ID, request logging
│
├── catalog/            # Actions, tags, workflows, CRUD admin
│   ├── models.py       # Action, Tag, WorkflowStep, RefCategory, etc.
│   ├── services.py     # CatalogService
│   ├── views.py        # ActionViewSet, TagViewSet
│   ├── serializers.py  # ActionSerializer, ActionCreateSerializer, etc.
│   └── tests/          # Tests par domaine
│
├── profiles/           # Profils dynamiques, permissions actions/targets, export YAML
│   ├── models.py       # Profile, ProfileActionPermission, ProfileTargetPermission
│   ├── services.py     # ProfileService
│   ├── services_export_import.py  # export_profiles_yaml, import_profiles_yaml
│   └── views.py        # ProfileViewSet, ProfileExportView, ProfileImportView
│
├── idp_auth/           # Auth SAML 2.0, JWT, refresh token, logout
│   ├── views.py        # SAMLLoginView, SAMLCallbackView, CurrentUserProfileView
│   ├── authentication.py  # JWTAuthentication (DRF backend)
│   ├── jwt_utils.py    # create_access_token, create_refresh_token, verify_token
│   ├── saml_config.py  # Configuration SAML (python3-saml)
│   └── services.py     # AuthService (create_or_update_user, favorites)
│
├── executions/         # Moteur d'exécution, timeline, scheduling
│   ├── models.py       # Execution, ScheduledExecution
│   └── services.py     # ExecutionService
│
├── integrations/       # Plateformes externes (AAP, ServiceNow, Terraform)
│   ├── models.py       # Integration, IntegrationType, AuthFlow
│   ├── services.py     # IntegrationService
│   ├── validation.py   # Config JSON Schema validation
│   └── upload_views.py # UploadIconView
│
└── tests/              # Tests transversaux et fixtures
    ├── conftest.py     # Fixtures pytest globales (UserFactory, etc.)
    ├── factories.py    # factory_boy factories
    └── security/       # Tests de sécurité (RBAC, injection, etc.)
```

### Convention de nommage

| Fichier | Rôle |
|---------|------|
| `models.py` | Modèles Django ORM (un par table Oracle) |
| `services.py` | Logique métier (le seul point d'entrée) |
| `views.py` | ViewSets DRF (appelle services, jamais l'ORM) |
| `serializers.py` | Validation entrée/sortie DRF |
| `urls.py` | Routes DRF (router + explicit paths) |
| `tests/` | Répertoire de tests (pas de `tests.py` à la racine) |

### Flux d'une requête

```
Client → URL router → DRF ViewSet → Permission check → Serializer validation → Service → ORM → DB
                                                                                   ↓
                                                                              AuditService.create_entry()
```

## 4. Conventions de tests

### Framework et configuration

- **Runner** : `pytest` avec `pytest-django` (pas `manage.py test`)
- **Settings** : `idp_backend.test_settings` (SQLite en mémoire, LocMemCache)
- **Factories** : `factory_boy` (`tests/factories.py`)
- **Coverage** : `pytest-cov`, seuil ≥80% (`setup.cfg`)

### Commandes

```bash
# Depuis django_backend/
.venv/bin/python -m pytest                           # Tous les tests
.venv/bin/python -m pytest catalog/tests/            # Tests d'une app
.venv/bin/python -m pytest catalog/tests/test_services.py -v  # Un fichier
.venv/bin/python -m pytest -k "test_create"          # Par nom
.venv/bin/python -m pytest --cov=catalog --cov-report=term-missing  # Avec couverture
```

### Structure des fichiers de test

```
app/tests/
├── __init__.py
├── test_models.py          # Tests modèles et managers
├── test_services.py        # Tests logique métier (service)
├── test_<name>_views.py    # Tests endpoints (APIClient)
├── test_serializers.py     # Tests validation serializers
└── test_edge_cases.py      # Tests cas limites
```

### Patterns de test

**Test de service** (sans HTTP) :
```python
@pytest.mark.django_db
class TestCatalogService(TestCase):
    def setUp(self):
        self.service = CatalogService()
        self.user = UserFactory(profile='dbops')

    def test_create_action(self):
        data = {'name': 'Test', 'engine': 'aap', 'platform': 'aap'}
        action = self.service.create_action(data, user=self.user)
        self.assertIsNotNone(action.id)
```

**Test de vue** (avec HTTP) :
```python
@pytest.mark.django_db
class TestActionViewSet(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dbops_user = User.objects.create(username='dbops', profile='dbops')

    def test_list_actions(self):
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get('/api/v1/admin/actions/')
        self.assertEqual(response.status_code, 200)
```

### Pièges connus

| Piège | Solution |
|-------|----------|
| `tests.py` conflit avec `tests/` | Supprimer `tests.py`, utiliser `tests/` directory |
| Redis `ConnectionRefusedError` | `test_settings.py` override `CACHES` avec `LocMemCache` |
| Throttle rates non overridés | `patch.object(SimpleRateThrottle, 'THROTTLE_RATES', ...)` |
| URL sans trailing slash → 301 | Toujours terminer les URLs par `/` dans les tests |
| `AuditLog` query avec string au lieu d'enum | Utiliser `AuditActionType.PROFILE_CREATED` (pas `'PROFILE_CREATED'`) |
| Audit non créé sans `user=` | Passer `user=self.user` au service si audit attendu |
