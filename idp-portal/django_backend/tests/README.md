# Django Backend Tests

**Story M.9: Tests unitaires et d'intégration**

## Vue d'ensemble

Cette suite de tests fournit une couverture complète pour le backend Django. Les tests sont organisés pour être maintenables, rapides et donner confiance dans le code.

## Stratégie de Tests & Patterns

### Types de Tests

| Type | Marker | Description |
|------|--------|-------------|
| **Unit** | `@pytest.mark.unit` | Tests rapides et isolés pour composants individuels |
| **Integration** | `@pytest.mark.integration` | Tests vérifiant les interactions multi-composants |
| **Security** | `@pytest.mark.security` | Tests RBAC, authentification et autorisation |
| **Transaction** | `@pytest.mark.transaction` | Tests pour opérations atomiques et rollback |
| **Benchmark** | `@pytest.mark.benchmark` | Tests de performance avec pytest-benchmark |
| **Slow** | `@pytest.mark.slow` | Tests longs (exclus par défaut) |

### Organisation des Tests

```
django_backend/
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Fixtures globales
│   ├── factories.py         # Factories factory-boy
│   ├── README.md            # Ce fichier
│   └── integration/         # Tests d'intégration
│       ├── test_action_lifecycle.py
│       ├── test_profile_resolution.py
│       ├── test_execution_flow.py
│       ├── test_audit_trail.py
│       ├── test_parametrized.py
│       ├── test_transaction_handling.py
│       ├── test_rbac_security.py
│       └── test_performance.py
├── catalog/tests/           # Tests app Catalog (TestCase + APIClient + UserFactory/ActionFactory; voir drf-api-migration-notes.md)
├── profiles/tests/          # Tests app Profiles
├── integrations/tests/      # Tests app Integrations
├── executions/tests/        # Tests app Executions
├── idp_auth/tests/          # Tests app Auth
└── core/tests/              # Tests app Core
```

## Prérequis

### Installation

1. Créer un environnement virtuel:
```bash
python -m venv venv
```

2. Activer l'environnement virtuel:
```bash
# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

3. Installer les dépendances:
```bash
pip install uv
uv pip install -r requirements-dev.lock
```

### Configuration Base de Données

Les tests utilisent SQLite en mémoire par défaut. Pour Oracle:
```bash
export ORACLE_DSN="your_oracle_dsn"
export ORACLE_USER="your_user"
export ORACLE_PASSWORD="your_password"
```

## Exécution des Tests

### Commandes Rapides

```bash
# Tous les tests (sauf slow/benchmark)
pytest

# Avec couverture
pytest --cov --cov-report=html

# Tests unitaires uniquement
pytest -m unit

# Tests d'intégration uniquement
pytest -m integration

# Tests de sécurité uniquement
pytest -m security

# Benchmarks de performance
pytest -m benchmark --benchmark-only

# App spécifique
pytest catalog/tests/

# Fichier de test spécifique
pytest catalog/tests/test_managers.py

# Test spécifique
pytest catalog/tests/test_managers.py::TestActionManager::test_list_published

# Sortie verbeuse
pytest -v

# Exécution parallèle (nécessite pytest-xdist)
pytest -n auto
```

### Utilisation de run_tests.sh

```bash
# Tous les tests avec couverture
./run_tests.sh --cov

# Tests d'intégration uniquement
./run_tests.sh --integration

# Benchmarks de performance
./run_tests.sh --benchmark

# Module spécifique avec couverture
./run_tests.sh --cov --module catalog/tests/
```

## Fixtures

### Fixtures Globales (conftest.py)

| Fixture | Description |
|---------|-------------|
| `db_user` | Utilisateur standard avec profil DBA |
| `admin_user` | Utilisateur admin avec profil DBOPS |
| `auditor_user` | Utilisateur auditeur avec accès lecture seule |
| `api_client` | APIClient DRF non authentifié |
| `api_client_authenticated` | APIClient authentifié avec db_user |
| `api_client_admin` | APIClient authentifié avec admin_user |
| `sample_integration` | Intégration AAP pour tests |
| `sample_action_published` | Action publiée dans le catalogue |
| `sample_profile` | Profil DBA standard |
| `sample_execution_running` | Exécution en cours |
| `sample_audit_entry` | Entrée d'audit |

### Exemple d'Utilisation

```python
import pytest

@pytest.mark.django_db
def test_example(api_client_authenticated, sample_action_published):
    """Test utilisant les fixtures."""
    response = api_client_authenticated.get(
        f'/api/v1/catalog/actions/{sample_action_published.id}'
    )
    assert response.status_code == 200
```

## Factories

### Factories Disponibles (factories.py)

| Factory | Modèle |
|---------|--------|
| `UserFactory` | idp_auth.User |
| `ActionFactory` | catalog.Action |
| `TagFactory` | catalog.Tag |
| `IntegrationFactory` | integrations.Integration |
| `ProfileFactory` | profiles.Profile |
| `ExecutionFactory` | executions.Execution |
| `ExecutionStepFactory` | executions.ExecutionStep |
| `ScheduledExecutionFactory` | executions.ScheduledExecution |
| `AuditLogFactory` | core.AuditLog |

### Exemple d'Utilisation

```python
from tests.factories import ActionFactory, UserFactory

@pytest.mark.django_db
def test_with_factory():
    """Test utilisant les factories."""
    user = UserFactory.create(profile='DBOPS')
    action = ActionFactory.create(
        status='published',
        created_by=user
    )
    assert action.created_by == user
```

### Création en Lot

```python
from tests.factories import ActionBatchFactory

@pytest.mark.django_db
def test_bulk_creation(db_user, sample_integration):
    """Test avec plusieurs actions."""
    actions = ActionBatchFactory.create_batch(
        100,
        user=db_user,
        integration=sample_integration,
        status='published'
    )
    assert len(actions) == 100
```

## Tests Paramétrés

Utilisez `@pytest.mark.parametrize` pour tester plusieurs entrées:

```python
@pytest.mark.parametrize('status,expected_count', [
    ('draft', 1),
    ('published', 1),
    ('disabled', 1),
])
@pytest.mark.django_db
def test_filter_by_status(status, expected_count):
    """Test filtrage par différents statuts."""
    ActionFactory.create(status=status)
    results = Action.objects.list_by_status(status)
    assert results.count() == expected_count
```

## Mocking des Services Externes

### Service Vault

```python
@pytest.fixture
def mock_vault_service(mocker):
    """Mock du service Vault."""
    mock = mocker.patch('core.services.vault_service')
    mock.get_credentials.return_value = {
        'username': 'test_user',
        'password': 'test_password'
    }
    return mock
```

### ServiceNow

```python
@pytest.fixture
def mock_servicenow_service(mocker):
    """Mock du service ServiceNow."""
    mock = mocker.patch('core.services.servicenow_service')
    mock.create_change.return_value = {'sys_id': 'CHG0001234'}
    return mock
```

### Adaptateur AAP

```python
@pytest.fixture
def mock_aap_adapter(mocker):
    """Mock de l'adaptateur AAP."""
    mock = mocker.patch('executions.adapters.aap_adapter')
    mock.submit_job.return_value = {'job_id': 12345}
    return mock
```

## Tests de Transaction

Pour les tests vérifiant le comportement de rollback:

```python
@pytest.mark.django_db(transaction=True)
@pytest.mark.transaction
class TestTransactions(TransactionTestCase):

    def test_rollback_on_error(self):
        """Test que les erreurs causent un rollback."""
        try:
            with transaction.atomic():
                Action.objects.create(name='Test')
                raise ValueError("Force rollback")
        except ValueError:
            pass

        assert Action.objects.filter(name='Test').count() == 0
```

## Couverture

### Exigences Minimales

- **Objectif:** ≥90% de couverture par module
- **Rapports:** HTML, XML, terminal

### Générer les Rapports

```bash
# Générer tous les rapports
pytest --cov --cov-report=html --cov-report=xml --cov-report=term-missing

# Voir le rapport HTML
open htmlcov/index.html
```

### Configuration de Couverture

Voir `.coveragerc` pour les exclusions et la configuration.

## Intégration CI/CD

Les tests s'exécutent automatiquement sur:
- Push vers `main` (avec enforcement seuil couverture 90 %)
- Pull requests vers `main` (avec enforcement seuil couverture 90 %)
- Changements dans `django_backend/**`

> **Note :** `django-tests.yml` exclut la branche `develop` pour éviter de bloquer les commits de développement. La couverture est enforced uniquement lors des PRs/push vers `main`.

Voir `.github/workflows/django-tests.yml` pour la configuration.

### Vérifications CI

1. **Tests Unitaires** - Tests rapides avec couverture (échec sous 90%)
2. **Tests d'Intégration** - Tests multi-composants
3. **Linting** - Vérifications qualité code ruff
4. **Vérification Types** - Analyse statique mypy (consultatif)

## Conventions de Nommage

### Fichiers de Test

- `test_managers.py` - Tests Manager/QuerySet
- `test_services.py` - Tests services logique métier
- `test_views.py` - Tests vues API
- `test_models.py` - Tests validation modèles

### Fonctions de Test

```python
# Utiliser des noms descriptifs
def test_list_published_returns_only_published_actions():
    ...

def test_filter_by_tags_with_multiple_tags_uses_and_logic():
    ...

def test_unauthenticated_request_returns_401():
    ...
```

## Bonnes Pratiques

### À FAIRE

- ✅ Utiliser fixtures plutôt que setUp() pour meilleure isolation
- ✅ Utiliser factories pour création données de test
- ✅ Utiliser parametrize pour cas de test multiples
- ✅ Ajouter markers pour catégorisation des tests
- ✅ Mocker services externes (Vault, ServiceNow, AAP)
- ✅ Tester cas limites et conditions d'erreur
- ✅ Vérifier piste d'audit pour opérations CRUD
- ✅ **TOUJOURS** ajouter trailing slash aux URLs API dans tests (`/api/v1/executions/`)
- ✅ **TOUJOURS** utiliser `UserFactory` pour créer utilisateurs tests

### À ÉVITER

- ❌ Accéder aux vrais services externes dans les tests
- ❌ Créer données de test au niveau module
- ❌ Sauter des tests sans bonne raison
- ❌ Laisser des print/debug statements
- ❌ Créer des dépendances entre tests
- ❌ **JAMAIS** utiliser `User.objects.create(is_staff=True)` (champ n'existe pas)
- ❌ **JAMAIS** créer `Action` manuellement avec JSON strings — utiliser `ActionFactory`
- ❌ **JAMAIS** utiliser URLs sans trailing slash dans tests (`/api/v1/executions` → 301 redirect)

---

## ⚠️ Common Testing Pitfalls (Stories 18.7, 20.1)

**Updated:** 2026-02-08 — Lessons learned from Stories 18.7 and 20.1 test fixes

### ❌ PIÈGE 1: User Fixtures avec Champs Django Auth Standard

**Problème:** Le modèle `User` custom ne possède **PAS** les champs Django auth standard (`is_staff`, `is_active`, `is_superuser`, `password`). L'authentification se fait via SAML 2.0, pas Django auth.

**❌ MAUVAIS (provoque TypeError):**
```python
from idp_auth.models import User

def test_example():
    user = User.objects.create(
        username='testuser',
        profile='DBA',
        is_staff=True,        # ❌ TypeError: Unknown field 'is_staff'
        is_active=True,       # ❌ TypeError: Unknown field 'is_active'
        is_superuser=False    # ❌ TypeError: Unknown field 'is_superuser'
    )
```

**✅ CORRECT (utiliser UserFactory):**
```python
from tests.factories import UserFactory

def test_example():
    user = UserFactory(
        username='testuser',
        profile='DBA'
    )
    # Champs valides: username, profile, display_name, saml_subject
```

**Variantes UserFactory:**
```python
# Profils différents
dba_user = UserFactory(profile='DBA')
dbops_user = UserFactory(profile='DBOPS')
business_user = UserFactory(profile='BUSINESS')

# Traits factory
dbops_user = UserFactory(dbops=True)  # Trait pour DBOPS
business_user = UserFactory(business=True)  # Trait pour BUSINESS

# Override display_name et saml_subject
user = UserFactory(
    username='john.doe',
    display_name='John Doe',
    saml_subject='john.doe@example.com'
)
```

---

### ❌ PIÈGE 2: Créer Action Manuellement avec JSON Fields

**Problème:** Depuis Story 17.4 (OracleJSONField refactor), les champs JSON (`parameters_schema`, `impact_rules`, etc.) doivent être passés comme `dict`/`list`, pas comme JSON `string`. Créer manuellement provoque erreurs de sérialisation.

**❌ MAUVAIS (JSON strings manuelles):**
```python
from catalog.models import Action

def test_example():
    action = Action.objects.create(
        name='Test Action',
        status='published',
        parameters_schema='{"type": "object"}',  # ❌ String, pas dict
        impact_rules='[{"condition": "env==prod"}]'  # ❌ String, pas list
    )
    # Fragile, verbose, prone to errors
```

**✅ CORRECT (utiliser ActionFactory):**
```python
from tests.factories import ActionFactory

def test_example():
    action = ActionFactory(
        name='Test Action',
        status='published',
        parameters_schema={'type': 'object'},  # ✅ Dict, factory gère JSON
        impact_rules=[{'condition': 'env==prod'}]  # ✅ List, factory gère JSON
    )
    # Clean, maintainable, type-safe
```

**Variantes ActionFactory:**
```python
# Action publiée (default)
action = ActionFactory()  # status='published', item_type='action'

# Workflow (item_type='workflow')
workflow = ActionFactory(workflow=True)  # Trait pour workflow

# Action désactivée
disabled_action = ActionFactory(disabled=True)  # Trait pour disabled

# Avec intégration spécifique
from tests.factories import IntegrationFactory
integration = IntegrationFactory(platform_type='AAP')
action = ActionFactory(integration=integration)
```

---

### ❌ PIÈGE 3: URLs Sans Trailing Slash dans Tests

**Problème:** Django `APPEND_SLASH=True` redirige les URLs sans trailing slash vers URLs avec trailing slash (301 redirect). Les tests d'authentification échouent car le redirect (301) arrive **AVANT** la vérification auth (401).

**❌ MAUVAIS (301 redirect avant auth check):**
```python
def test_unauthenticated_returns_401(anon_client):
    response = anon_client.get('/api/v1/executions')  # ❌ Sans trailing slash
    # Résultat: 301 Redirect (vers /api/v1/executions/)
    # Expected: 401 Unauthorized
    assert response.status_code == 401  # ❌ ÉCHEC (301 != 401)
```

**✅ CORRECT (trailing slash évite redirect):**
```python
def test_unauthenticated_returns_401(anon_client):
    response = anon_client.get('/api/v1/executions/')  # ✅ Trailing slash
    # Résultat: 401 Unauthorized (pas de redirect, auth check exécuté)
    assert response.status_code == 401  # ✅ PASSE
```

**Pattern Paramétrisé:**
```python
import pytest

PROTECTED_ENDPOINTS = [
    ('GET', '/api/v1/executions/'),          # ✅ Trailing slash
    ('POST', '/api/v1/executions/'),         # ✅ Trailing slash
    ('GET', '/api/v1/scheduled-executions/'),  # ✅ Trailing slash
]

@pytest.mark.parametrize('method,url', PROTECTED_ENDPOINTS)
def test_unauthenticated_returns_401(anon_client, method, url):
    response = getattr(anon_client, method.lower())(url)
    assert response.status_code == 401
```

---

### ❌ PIÈGE 4: Soft Delete Constraint CHECK Oracle vs SQLite

**Problème:** Migration V004 ajoute contrainte CHECK Oracle pour soft delete consistency:
```sql
CHECK (
    (IS_DELETED = 1 AND DELETED_AT IS NOT NULL) OR
    (IS_DELETED = 0 AND DELETED_AT IS NULL)
)
```
SQLite enforce cette contrainte, mais code tests peut la violer si `is_deleted` et `deleted_at` sont définis séparément.

**❌ MAUVAIS (viole constraint):**
```python
from django.utils import timezone

def test_soft_delete():
    action = Action.objects.create(name='Test', status='published')
    action.is_deleted = True
    action.save()  # ❌ IntegrityError: CHECK constraint failed
    # Cause: is_deleted=True mais deleted_at=NULL (incohérent)
```

**✅ CORRECT (définir ensemble):**
```python
from django.utils import timezone

def test_soft_delete():
    action = Action.objects.create(name='Test', status='published')
    action.is_deleted = True
    action.deleted_at = timezone.now()  # ✅ Cohérent avec is_deleted=True
    action.save()  # OK, constraint satisfaite
```

**Ou utiliser méthode soft_delete() si elle existe:**
```python
def test_soft_delete():
    action = Action.objects.create(name='Test', status='published')
    action.soft_delete()  # ✅ Méthode model gère les deux champs ensemble
```

**Ou ActionFactory avec trait:**
```python
from tests.factories import ActionFactory

def test_soft_delete():
    action = ActionFactory(is_deleted=True, deleted_at=timezone.now())
    # ✅ Factory s'assure de cohérence
```

---

### ❌ PIÈGE 5: Double Transition de Statut Action (Story 20.1)

**Problème:** Créer une action avec `status=PUBLISHED` puis appeler `update_status('publish')` provoque une `InvalidTransitionError` car l'action est déjà au statut `PUBLISHED`.

**❌ MAUVAIS (double transition):**
```python
from catalog.services import CatalogService

def test_tags_on_published_action():
    service = CatalogService()
    action = service.create_action({
        'name': 'Test',
        'engine': 'Oracle',
        'platform': 'AAP',
        'status': ActionStatus.PUBLISHED,  # ❌ Déjà PUBLISHED
    }, user)
    service.update_status(action.id, 'publish', user)  # ❌ InvalidTransitionError
```

**✅ CORRECT (créer DRAFT puis publier):**
```python
def test_tags_on_published_action():
    service = CatalogService()
    action = service.create_action({
        'name': 'Test',
        'engine': 'Oracle',
        'platform': 'AAP',
        'status': ActionStatus.DRAFT,  # ✅ Créer en DRAFT
    }, user)
    service.update_status(action.id, 'publish', user)  # ✅ DRAFT → PUBLISHED
```

---

### ❌ PIÈGE 6: API CatalogService.list_all() Obsolète (Story 20.1)

**Problème:** `CatalogService.list_all()` n'accepte plus les kwargs `engine` ni `search_query`. La signature actuelle est: `list_all(status=None, tags_filter=None, item_type=None, page=1, page_size=25)`. De plus, la valeur de retour est `(list, dict)` et non `(list, int)`.

**❌ MAUVAIS (kwargs obsolètes):**
```python
# ❌ TypeError: list_all() got an unexpected keyword argument 'engine'
results, count = service.list_all(engine='Oracle')

# ❌ TypeError: list_all() got an unexpected keyword argument 'search_query'
results, count = service.list_all(search_query='oracle')

# ❌ pagination_info est un dict, pas un int
results, total_count = service.list_all()
self.assertEqual(total_count, 5)  # ❌ Comparing dict to int
```

**✅ CORRECT (signature actuelle):**
```python
# ✅ Filtrer par status, tags, item_type uniquement
results, pagination_info = service.list_all(status='published')
results, pagination_info = service.list_all(tags_filter=['oracle', 'dba'])
results, pagination_info = service.list_all(item_type='action', page=1, page_size=10)

# ✅ pagination_info est un dict avec 'total'
self.assertEqual(pagination_info['total'], 5)
```

---

### ❌ PIÈGE 7: Désactivation/Réactivation d'Action (Story 20.1)

**Problème:** `update_status('disable')` ne gère pas les champs soft-delete (`deleted_at`, `deleted_by`, `is_deleted`), ce qui viole la contrainte CHECK `ck_actions_soft_delete_consistency`. Utiliser `deactivate_action()` et `reactivate_action()` à la place.

**❌ MAUVAIS (viole contrainte CHECK):**
```python
# ❌ IntegrityError: CHECK constraint ck_actions_soft_delete_consistency
service.update_status(action.id, 'disable', user)

# ❌ Même problème pour réactivation
service.update_status(action.id, 'enable', user)
```

**✅ CORRECT (méthodes dédiées):**
```python
# ✅ deactivate_action gère soft-delete fields automatiquement
service.deactivate_action(action.id, user)

# ✅ reactivate_action nettoie les champs soft-delete
service.reactivate_action(action.id, user)
```

---

### ❌ PIÈGE 8: delete_action() Attend un Objet User (Story 20.1)

**Problème:** `CatalogService.delete_action(action_id, user)` attend un objet `User`, pas un `str(user.id)`. Passer un string provoque `AttributeError: 'str' object has no attribute 'id'`.

**❌ MAUVAIS:**
```python
service.delete_action(action.id, str(user.id))  # ❌ AttributeError
service.delete_action(action.id, 'user123')      # ❌ AttributeError
```

**✅ CORRECT:**
```python
service.delete_action(action.id, user)  # ✅ Objet User
```

---

### ❌ PIÈGE 9: RefEngine/IntegrationTypeCatalogue Requis pour Admin API (Story 20.1, 31.9)

**Problème:** Les endpoints admin (`/api/v1/admin/actions/`) utilisent un serializer qui valide `engine` contre `RefEngine` et `platform` contre `IntegrationTypeCatalogue` (role=platform). Sans ces données, les requêtes POST/PUT retournent 400.

**❌ MAUVAIS (données de référence manquantes):**
```python
def setUp(self):
    self.client = APIClient()
    self.user = UserFactory(profile='DBOPS')
    # ❌ Pas de RefEngine/IntegrationTypeCatalogue
    # POST /api/v1/admin/actions/ → 400 "Invalid engine 'Oracle'"
```

**✅ CORRECT (créer données de référence):**
```python
from reference.models import RefEngine
from integrations.models import IntegrationTypeCatalogue, IntegrationRole

def setUp(self):
    self.client = APIClient()
    self.user = UserFactory(profile='DBOPS')
    # ✅ Créer les données de référence
    RefEngine.objects.get_or_create(code='Oracle', defaults={'label': 'Oracle', 'display_order': 1})
    IntegrationTypeCatalogue.objects.get_or_create(
        code='aap', defaults={'name': 'AAP', 'integration_role': IntegrationRole.PLATFORM, 'is_active': True}
    )
```

---

### ❌ PIÈGE 10: Workflow Steps Sans referenced_action_id (Story 20.1)

**Problème:** Depuis Story 4.12, tous les steps de workflow doivent avoir un `referenced_action_id` pointant vers une Action existante. Sans ce champ, le moteur de workflow lève une erreur de validation `"missing referenced_action_id"`.

**❌ MAUVAIS (step sans referenced_action_id):**
```python
workflow_steps = [
    {
        "step_id": "step-1",
        "order": 1,
        "name": "First Step",
        # ❌ Pas de referenced_action_id
        "on_success_step_id": "step-2",
        "on_failure_step_id": None
    }
]
```

**✅ CORRECT (step avec referenced_action_id):**
```python
from catalog.models import Action, ActionStatus

# Créer l'action référencée
ref_action = Action.objects.create(
    name="Referenced Action",
    engine="Oracle",
    platform="AAP",
    status=ActionStatus.PUBLISHED,
    created_by=user
)

workflow_steps = [
    {
        "step_id": "step-1",
        "order": 1,
        "name": "First Step",
        "referenced_action_id": ref_action.id,  # ✅ Requis depuis Story 4.12
        "on_success_step_id": "step-2",
        "on_failure_step_id": None
    }
]
```

---

## 📝 Quick Reference Checklist

Avant de soumettre un test:

- [ ] ✅ J'utilise `UserFactory` (pas `User.objects.create()`)
- [ ] ✅ J'utilise `ActionFactory` (pas `Action.objects.create()`)
- [ ] ✅ Mes URLs API ont trailing slash (`/api/v1/executions/`)
- [ ] ✅ Si soft delete, je définis `is_deleted` **ET** `deleted_at` ensemble
- [ ] ✅ Je mocke services externes (Vault, ServiceNow, AAP)
- [ ] ✅ J'ajoute `@pytest.mark.django_db` si j'accède à la DB
- [ ] ✅ Je catégorise avec markers (`@pytest.mark.unit`, `@security`, etc.)
- [ ] ✅ Je crée Actions en DRAFT avant d'appeler `update_status('publish')`
- [ ] ✅ J'utilise `deactivate_action()`/`reactivate_action()` (pas `update_status('disable')`)
- [ ] ✅ Je passe un objet `User` à `delete_action()` (pas `str(user.id)`)
- [ ] ✅ Je crée `RefEngine` + `IntegrationTypeCatalogue` (role=platform) avant les tests admin API
- [ ] ✅ J'ajoute `referenced_action_id` aux workflow steps
- [ ] ✅ J'utilise `pagination_info['total']` (dict, pas int) pour `list_all()`
- [ ] ❌ Je n'utilise PAS de champs Django auth (`is_staff`, `is_active`)
- [ ] ❌ Je ne crée PAS de JSON fields avec strings manuelles
- [ ] ❌ Je ne laisse PAS de `print()` ou debug statements
- [ ] ❌ Je ne passe PAS `engine` ou `search_query` à `list_all()`

## Dépannage

### Problèmes Courants

**Base de données non disponible:**
```bash
# S'assurer que DJANGO_SETTINGS_MODULE est défini
export DJANGO_SETTINGS_MODULE=idp_backend.settings
```

**Erreurs d'import:**
```bash
# Exécuter depuis le répertoire django_backend
cd django_backend
pytest
```

**Tests lents:**
```bash
# Exclure les tests lents
pytest -m "not slow and not benchmark"
```

## Références

- [Documentation pytest-django](https://pytest-django.readthedocs.io/)
- [Documentation factory-boy](https://factoryboy.readthedocs.io/)
- [Documentation pytest-benchmark](https://pytest-benchmark.readthedocs.io/)
- [Documentation tests Django](https://docs.djangoproject.com/en/5.0/topics/testing/)
