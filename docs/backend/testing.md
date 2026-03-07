# Tests et Couverture

## Vue d'ensemble

Le backend utilise pytest avec pytest-django pour les tests. La couverture cible est ≥80%.

## Structure des tests

```
django_backend/
├── tests/                      # Tests d'intégration globaux
│   ├── conftest.py             # Fixtures globales
│   ├── factories.py            # Factories factory-boy
│   └── integration/
│       ├── test_action_lifecycle.py
│       ├── test_profile_resolution.py
│       ├── test_execution_flow.py
│       ├── test_audit_trail.py
│       ├── test_rbac_security.py
│       └── test_performance.py
├── catalog/tests/              # Tests app Catalog
│   ├── test_services.py
│   ├── test_admin_views.py
│   ├── test_catalog_views.py
│   └── test_tags_views.py
├── profiles/tests/             # Tests app Profiles
│   ├── test_services.py
│   ├── test_profile_views.py
│   └── test_import_export_views.py
├── idp_auth/tests/             # Tests app Auth
│   ├── test_jwt_utils.py
│   ├── test_jwt_authentication.py
│   └── test_saml_views.py
├── integrations/tests/         # Tests app Integrations
│   └── test_integration_views.py
├── executions/tests/           # Tests app Executions
│   └── test_services.py
└── core/tests/                 # Tests app Core
    ├── test_managers.py
    └── test_services.py
```

## Exécution des tests

### Commandes de base

```bash
# Tous les tests
pytest

# Avec couverture
pytest --cov --cov-report=html

# Tests unitaires uniquement
pytest -m unit

# Tests d'intégration
pytest -m integration

# Tests de sécurité
pytest -m security

# Module spécifique
pytest catalog/tests/

# Test spécifique
pytest catalog/tests/test_services.py::TestCatalogService::test_create_action

# Verbeux
pytest -v

# Parallèle
pytest -n auto
```

### Markers

| Marker | Description |
|--------|-------------|
| `@pytest.mark.unit` | Tests unitaires rapides |
| `@pytest.mark.integration` | Tests d'intégration |
| `@pytest.mark.security` | Tests de sécurité/RBAC |
| `@pytest.mark.transaction` | Tests transactionnels |
| `@pytest.mark.benchmark` | Benchmarks de performance |
| `@pytest.mark.slow` | Tests lents (exclus par défaut) |

## Fixtures

### Fixtures globales (conftest.py)

```python
@pytest.fixture
def db_user(db):
    """Utilisateur standard avec profil DBA."""
    from tests.factories import UserFactory
    return UserFactory.create(profile='DBA')

@pytest.fixture
def admin_user(db):
    """Utilisateur admin avec profil DBOPS."""
    from tests.factories import UserFactory
    return UserFactory.create(profile='DBOPS')

@pytest.fixture
def api_client():
    """APIClient DRF non authentifié."""
    from rest_framework.test import APIClient
    return APIClient()

@pytest.fixture
def api_client_authenticated(api_client, db_user):
    """
    APIClient authentifié avec db_user.

    Note: Utilise force_authenticate() pour simplifier les tests.
    Pour tester le flow JWT complet, utiliser api_client_with_jwt.
    """
    api_client.force_authenticate(user=db_user)
    return api_client

@pytest.fixture
def api_client_admin(api_client, admin_user):
    """
    APIClient authentifié avec admin_user (profil DBOPS).

    Note: Utilise force_authenticate() pour simplifier les tests.
    """
    api_client.force_authenticate(user=admin_user)
    return api_client

@pytest.fixture
def api_client_with_jwt(db_user):
    """
    APIClient authentifié avec JWT réel (pour tests d'intégration auth).

    Utilise create_token() pour générer un vrai token JWT.
    """
    from rest_framework.test import APIClient
    from idp_auth.jwt_utils import create_token

    client = APIClient()
    token = create_token(db_user.id, db_user.username, ['DBA-DEV'])
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client

@pytest.fixture
def sample_action_published(db_user):
    """Action publiée pour tests."""
    from tests.factories import ActionFactory
    return ActionFactory.create(status='published', created_by=db_user)

@pytest.fixture
def sample_profile(db):
    """Profil DBA standard."""
    from tests.factories import ProfileFactory
    return ProfileFactory.create(name='DBA-DEV', ad_group='CN=DBA-DEV,OU=Groups')
```

### Utilisation des fixtures

```python
import pytest

@pytest.mark.django_db
def test_list_actions(api_client_authenticated, sample_action_published):
    """Test listing actions."""
    response = api_client_authenticated.get('/api/v1/catalog/actions')

    assert response.status_code == 200
    assert len(response.data['data']) >= 1
```

## Factories

### Fichier factories.py

```python
import factory
from factory.django import DjangoModelFactory
from catalog.models import Action, Tag
from profiles.models import Profile
from idp_auth.models import User

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user_{n}')
    display_name = factory.LazyAttribute(lambda obj: f'User {obj.username}')
    profile = 'DBA'

class ActionFactory(DjangoModelFactory):
    class Meta:
        model = Action

    name = factory.Sequence(lambda n: f'Action {n}')
    description = 'Test action description'
    engine = 'Oracle'
    platform = 'AAP'
    category = 'Administration'
    status = 'draft'
    created_by = factory.SubFactory(UserFactory)

class TagFactory(DjangoModelFactory):
    class Meta:
        model = Tag

    name = factory.Sequence(lambda n: f'tag_{n}')

class ProfileFactory(DjangoModelFactory):
    class Meta:
        model = Profile

    name = factory.Sequence(lambda n: f'Profile {n}')
    ad_group = factory.LazyAttribute(lambda obj: f'CN={obj.name},OU=Groups')
    is_admin = 0
    is_auditor = 0
```

### Utilisation des factories

```python
from tests.factories import ActionFactory, UserFactory

@pytest.mark.django_db
def test_create_action():
    user = UserFactory.create(profile='DBOPS')
    action = ActionFactory.create(
        name='Test Action',
        status='published',
        created_by=user,
    )

    assert action.name == 'Test Action'
    assert action.status == 'published'

# Création en lot
@pytest.mark.django_db
def test_bulk_actions():
    actions = ActionFactory.create_batch(10, status='published')
    assert len(actions) == 10
```

## Tests d'API

### Test de création (POST)

```python
@pytest.mark.django_db
class TestActionViewSet:

    def test_create_action_success(self, api_client_admin):
        """Test création d'action avec admin."""
        data = {
            'name': 'New Action',
            'description': 'Description',
            'engine': 'Oracle',
            'platform': 'AAP',
            'category': 'Administration',
        }

        response = api_client_admin.post(
            '/api/v1/admin/actions',
            data,
            format='json'
        )

        assert response.status_code == 201
        assert response.data['data']['name'] == 'New Action'

    def test_create_action_unauthorized(self, api_client_authenticated):
        """Test création d'action sans permission admin."""
        data = {'name': 'Test'}

        response = api_client_authenticated.post(
            '/api/v1/admin/actions',
            data,
            format='json'
        )

        assert response.status_code == 403
```

### Test de liste avec filtres (GET)

```python
@pytest.mark.django_db
def test_list_actions_with_filters(api_client_authenticated):
    """Test filtrage des actions."""
    # Setup
    ActionFactory.create(name='Oracle Backup', status='published')
    ActionFactory.create(name='SQL Server Backup', status='published')
    ActionFactory.create(name='Draft Action', status='draft')

    # Test filter by status
    response = api_client_authenticated.get(
        '/api/v1/catalog/actions?status=published'
    )

    assert response.status_code == 200
    assert all(a['status'] == 'published' for a in response.data['data'])

    # Test search
    response = api_client_authenticated.get(
        '/api/v1/catalog/actions?q=Oracle'
    )

    assert response.status_code == 200
    assert any('Oracle' in a['name'] for a in response.data['data'])
```

### Test d'erreur

```python
@pytest.mark.django_db
def test_get_nonexistent_action(api_client_authenticated):
    """Test 404 pour action inexistante."""
    response = api_client_authenticated.get('/api/v1/catalog/actions/99999')

    assert response.status_code == 404
    assert response.data['error']['code'] == 'NOT_FOUND'
```

## Tests de services

```python
import pytest
from catalog.services import CatalogService, InvalidTransitionError
from tests.factories import ActionFactory, UserFactory

@pytest.mark.django_db
class TestCatalogService:

    def test_create_action(self):
        user = UserFactory.create()
        service = CatalogService()

        action = service.create_action(
            action_data={
                'name': 'Test Action',
                'engine': 'Oracle',
                'platform': 'AAP',
                'category': 'Administration',
            },
            created_by_user=user
        )

        assert action.name == 'Test Action'
        assert action.status == 'draft'
        assert action.created_by == user

    def test_update_status_publish(self):
        user = UserFactory.create()
        action = ActionFactory.create(status='draft')
        service = CatalogService()

        updated = service.update_status(action.id, 'publish', user)

        assert updated.status == 'published'

    def test_update_status_invalid_transition(self):
        user = UserFactory.create()
        action = ActionFactory.create(status='draft')
        service = CatalogService()

        with pytest.raises(InvalidTransitionError):
            service.update_status(action.id, 'disable', user)  # draft → disable invalid
```

## Tests de sécurité/RBAC

```python
@pytest.mark.security
@pytest.mark.django_db
class TestRBACFiltering:

    def test_rbac_filters_actions_by_permission(self, api_client_authenticated):
        """Vérifie que RBAC filtre les actions."""
        # Setup: créer actions avec différents tags
        action1 = ActionFactory.create(status='published')
        action2 = ActionFactory.create(status='published')
        # Configurer permissions pour user...

        response = api_client_authenticated.get('/api/v1/catalog/actions')

        # Vérifier que seules les actions autorisées sont retournées
        action_ids = [a['id'] for a in response.data['data']]
        # assertions...

    def test_admin_endpoints_require_dbops_profile(self, api_client_authenticated):
        """Vérifie que endpoints admin requièrent profil DBOPS."""
        response = api_client_authenticated.post(
            '/api/v1/admin/actions',
            {'name': 'Test'},
            format='json'
        )

        assert response.status_code == 403
```

## Tests transactionnels

```python
import pytest
from django.db import transaction
from django.test import TransactionTestCase

@pytest.mark.django_db(transaction=True)
@pytest.mark.transaction
class TestTransactionBehavior(TransactionTestCase):

    def test_rollback_on_error(self):
        """Test que les erreurs causent un rollback."""
        from catalog.models import Action

        initial_count = Action.objects.count()

        try:
            with transaction.atomic():
                Action.objects.create(name='Will be rolled back')
                raise ValueError("Force rollback")
        except ValueError:
            pass

        assert Action.objects.count() == initial_count
```

## Mocking

### Mock de services externes

```python
@pytest.fixture
def mock_vault_service(mocker):
    """Mock du service Vault."""
    mock = mocker.patch('integrations.services.vault_client')
    mock.get_secret.return_value = {'username': 'test', 'password': 'test'}
    return mock

@pytest.mark.django_db
def test_execution_with_vault(mock_vault_service, api_client_admin):
    """Test exécution avec credentials Vault."""
    # ... test utilisant le mock ...
    mock_vault_service.get_secret.assert_called_once()
```

### Mock de la DB (rare)

```python
@pytest.fixture
def mock_action_manager(mocker):
    """Mock du manager Action (pour tests unitaires sans DB)."""
    mock = mocker.patch.object(Action.objects, 'get')
    mock.return_value = Action(id=1, name='Mocked')
    return mock
```

## Couverture

### Configuration (.coveragerc)

```ini
[run]
source = .
omit =
    */migrations/*
    */tests/*
    manage.py
    */admin.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if __name__ == .__main__.:
```

### Générer les rapports

```bash
# HTML report
pytest --cov --cov-report=html
open htmlcov/index.html

# Terminal report
pytest --cov --cov-report=term-missing

# XML (CI)
pytest --cov --cov-report=xml
```

### Objectifs

| Module | Objectif |
|--------|----------|
| `catalog/services.py` | ≥90% |
| `profiles/services.py` | ≥90% |
| `*/views.py` | ≥80% |
| `*/models.py` | ≥80% |
| **Global** | ≥80% |

## Bonnes pratiques

### À faire

- ✅ Utiliser fixtures pour isolation
- ✅ Utiliser factories pour création de données
- ✅ Nommer les tests de manière descriptive
- ✅ Tester les cas d'erreur
- ✅ Mocker les services externes
- ✅ Vérifier l'audit pour les mutations

### À éviter

- ❌ Accéder aux vrais services externes
- ❌ Dépendances entre tests
- ❌ Laisser des `print()` dans les tests
- ❌ Tests qui échouent aléatoirement
