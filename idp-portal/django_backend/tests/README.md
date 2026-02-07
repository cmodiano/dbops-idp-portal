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
├── catalog/tests/           # Tests app Catalog
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

- **Objectif:** ≥80% de couverture par module
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
- Push vers `main` ou `develop`
- Pull requests vers `main` ou `develop`
- Changements dans `django_backend/**`

Voir `.github/workflows/django-tests.yml` pour la configuration.

### Vérifications CI

1. **Tests Unitaires** - Tests rapides avec couverture (échec sous 80%)
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

### À ÉVITER

- ❌ Accéder aux vrais services externes dans les tests
- ❌ Créer données de test au niveau module
- ❌ Sauter des tests sans bonne raison
- ❌ Laisser des print/debug statements
- ❌ Créer des dépendances entre tests

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
