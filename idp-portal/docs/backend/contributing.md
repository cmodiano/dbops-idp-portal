# Guide de Contribution

## Setup de l'environnement de développement

### Prérequis

- Python 3.11+
- Oracle Database (local via Docker ou distant)
- Git

### Installation

```bash
# 1. Cloner le repo
git clone <repo-url>
cd idp-portal/django_backend

# 2. Créer l'environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# 3. Installer les dépendances
pip install uv
uv pip install -r requirements-dev.lock

# 4. Configurer les variables d'environnement
cp .env.template .env
# Éditer .env avec vos valeurs

# 5. Vérifier la connexion DB
python manage.py check

# 6. Exécuter les tests
pytest

# 7. Lancer le serveur de développement
python manage.py runserver
```

### Docker Compose (Oracle local)

```bash
# Démarrer Oracle XE
docker-compose -f docker/oracle-dev.yml up -d

# Attendre que Oracle soit prêt (quelques minutes)
docker logs -f oracle-dev

# Les migrations Flyway sont appliquées automatiquement
```

## Conventions de code

### Style Python

Nous utilisons `ruff` pour le linting et le formatage:

```bash
# Vérifier le code
ruff check .

# Formater le code
ruff format .
```

### Nommage

| Élément | Convention | Exemple |
|---------|------------|---------|
| Fichiers Python | snake_case | `catalog_service.py` |
| Classes | PascalCase | `CatalogService` |
| Fonctions/méthodes | snake_case | `create_action()` |
| Variables | snake_case | `action_data` |
| Constantes | UPPER_SNAKE_CASE | `MAX_PAGE_SIZE` |
| Champs API | snake_case | `created_at` |

### Imports

Ordre des imports (géré par ruff):

```python
# 1. Standard library
import json
import logging
from datetime import datetime

# 2. Third-party
from django.db import models, transaction
from rest_framework import viewsets

# 3. Local
from catalog.models import Action
from core.services import AuditService
```

### Docstrings

Style Google:

```python
def create_action(self, action_data: dict, created_by_user: User) -> Action:
    """
    Crée une nouvelle action avec tags et audit.

    Args:
        action_data: Dict avec champs (name, description, engine, etc.)
        created_by_user: Utilisateur créateur

    Returns:
        Action instance

    Raises:
        ValueError: Si statut initial invalide

    Example:
        >>> service.create_action({'name': 'Test'}, user)
        <Action: Test>
    """
```

### Type hints

Utiliser les type hints pour les signatures:

```python
def get_cumulative_permissions(
    self,
    user_id: int,
    ad_groups: list[str]
) -> dict:
    ...
```

## Workflow de développement

### Branches

| Branche | Usage |
|---------|-------|
| `main` | Production |
| `develop` | Intégration |
| `feature/xxx` | Nouvelles fonctionnalités |
| `fix/xxx` | Corrections de bugs |

### Commits

Format du message:

```
type(scope): description courte

Corps optionnel avec plus de détails.

Refs: #123
```

Types:
- `feat`: Nouvelle fonctionnalité
- `fix`: Correction de bug
- `refactor`: Refactoring
- `docs`: Documentation
- `test`: Tests
- `chore`: Maintenance

### Pull Request

1. Créer une branche depuis `develop`
2. Implémenter la fonctionnalité
3. Écrire/mettre à jour les tests
4. Vérifier la couverture (≥80%)
5. Exécuter `ruff check .`
6. Créer la PR vers `develop`
7. Attendre la review

## Guides pas-à-pas

### Comment ajouter un nouvel endpoint API

#### 1. Définir le serializer

```python
# catalog/serializers.py

class MyNewSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False)

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Name cannot be empty")
        return value
```

#### 2. Implémenter la logique dans le service

```python
# catalog/services.py

class CatalogService:

    @transaction.atomic
    def do_something(self, data: dict, user: User) -> Model:
        """
        Effectue l'opération métier.

        Args:
            data: Données validées
            user: Utilisateur

        Returns:
            Instance créée/modifiée
        """
        # Validation métier
        # Opération
        # Audit
        AuditService.create_entry(...)
        return result
```

#### 3. Créer le ViewSet ou ajouter une action

```python
# catalog/views.py

class MyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, DBOPSProfilePermission]

    @action(detail=True, methods=['post'], url_path='my-action')
    def my_action(self, request, pk=None):
        serializer = MyNewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = CatalogService().do_something(
            data=serializer.validated_data,
            user=request.user
        )

        return Response({"data": ResultSerializer(result).data})
```

#### 4. Ajouter la route

```python
# catalog/urls.py

router = DefaultRouter()
router.register(r'my-resource', views.MyViewSet, basename='my-resource')

urlpatterns = [
    path('', include(router.urls)),
]
```

#### 5. Écrire les tests

```python
# catalog/tests/test_my_views.py

@pytest.mark.django_db
class TestMyEndpoint:

    def test_my_action_success(self, api_client_admin):
        response = api_client_admin.post(
            '/api/v1/my-resource/1/my-action',
            {'name': 'Test'},
            format='json'
        )
        assert response.status_code == 200

    def test_my_action_validation_error(self, api_client_admin):
        response = api_client_admin.post(
            '/api/v1/my-resource/1/my-action',
            {'name': ''},
            format='json'
        )
        assert response.status_code == 400
```

### Comment ajouter un nouveau modèle

#### 1. Définir le modèle

```python
# myapp/models.py

class MyModel(models.Model):
    """
    Description du modèle.

    Table Oracle: MY_TABLE
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    name = models.CharField(max_length=255, unique=True, db_column='NAME')
    # Champ JSON dans CLOB
    config = models.TextField(null=True, db_column='CONFIG')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')

    objects = MyModelManager()

    class Meta:
        db_table = 'MY_TABLE'

    def get_config(self):
        """Deserialize JSON."""
        return json.loads(self.config) if self.config else None

    def set_config(self, value):
        """Serialize JSON."""
        self.config = json.dumps(value) if value else None
```

#### 2. Créer le manager

```python
class MyModelManager(models.Manager):

    def list_active(self):
        return self.filter(is_active=True)
```

#### 3. Créer la migration Flyway

```sql
-- V042__create_my_table.sql

CREATE TABLE MY_TABLE (
    ID NUMBER(19) GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    NAME VARCHAR2(255 CHAR) NOT NULL UNIQUE,
    CONFIG CLOB,
    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IDX_MY_TABLE_NAME ON MY_TABLE(NAME);
```

#### 4. Créer la migration Django (fake)

```bash
python manage.py makemigrations myapp
python manage.py migrate --fake myapp
```

### Comment ajouter une nouvelle permission RBAC

#### 1. Ajouter à ProfileActionPermission ou créer nouveau modèle

```python
# Pour un nouveau type de permission
class ProfileMyPermission(models.Model):
    profile = models.OneToOneField(Profile, primary_key=True)
    permission_type = models.CharField(choices=[...])
    # ...
```

#### 2. Mettre à jour ProfileService

```python
def get_my_permissions(self, profile_id: int):
    ...

def set_my_permissions(self, profile_id: int, data: dict, user=None):
    ...

def get_cumulative_permissions(self, user_id, ad_groups):
    # Ajouter la nouvelle permission à l'agrégation
    ...
```

#### 3. Implémenter le filtrage dans le ViewSet

```python
def _filter_by_my_permission(items, permissions):
    ...
```

### Comment ajouter un nouveau service

#### 1. Créer le fichier service

```python
# myapp/services.py

import structlog
from django.db import transaction
from core.services import AuditService
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)


class MyService:
    """
    Service pour [description].

    Responsabilités:
    - [liste]
    """

    @transaction.atomic
    def create(self, data: dict, user) -> Model:
        correlation_id = get_correlation_id()

        logger.info(
            "my_entity_created",
            user_id=user.id,
            correlation_id=correlation_id
        )

        instance = MyModel.objects.create(**data)

        AuditService.create_entry(
            user_id=str(user.id),
            action_type=AuditActionType.MY_ENTITY_CREATED,
            entity_type=AuditEntityType.MY_ENTITY,
            entity_id=instance.id,
            correlation_id=correlation_id,
        )

        return instance
```

#### 2. Ajouter les types d'audit

```python
# core/models.py

class AuditActionType(models.TextChoices):
    # Existing...
    MY_ENTITY_CREATED = 'MY_ENTITY_CREATED', 'My Entity Created'
    MY_ENTITY_UPDATED = 'MY_ENTITY_UPDATED', 'My Entity Updated'

class AuditEntityType(models.TextChoices):
    # Existing...
    MY_ENTITY = 'my_entity', 'My Entity'
```

#### 3. Écrire les tests

```python
# myapp/tests/test_services.py

@pytest.mark.django_db
class TestMyService:

    def test_create_success(self):
        user = UserFactory.create()
        service = MyService()

        result = service.create({'name': 'Test'}, user)

        assert result.name == 'Test'
        # Vérifier l'audit
        audit = AuditLog.objects.filter(
            entity_type='my_entity',
            entity_id=result.id
        ).first()
        assert audit.action_type == 'MY_ENTITY_CREATED'
```

## Mise à jour de la documentation

Quand mettre à jour la documentation:

1. **Nouvel endpoint:** Ajouter à `api-reference.md`
2. **Nouveau modèle:** Ajouter à `models.md`
3. **Nouveau service:** Ajouter à `services.md`
4. **Changement d'architecture:** Mettre à jour `apps-structure.md`
5. **Changement de sécurité:** Mettre à jour `rbac.md` ou `authentication.md`

## Checklist PR

Avant de soumettre une PR:

- [ ] Tests écrits et passent
- [ ] Couverture ≥80%
- [ ] `ruff check .` sans erreur
- [ ] Documentation mise à jour si nécessaire
- [ ] Audit ajouté pour les mutations
- [ ] Pas de secrets dans le code
- [ ] Pas de `print()` ou `console.log()`
- [ ] Migration Flyway si nouveau schéma
