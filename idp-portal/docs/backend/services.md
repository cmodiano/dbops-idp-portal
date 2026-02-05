# Services et Logique Métier

## Vue d'ensemble

La couche services contient la logique métier de l'application. Elle:

- Encapsule les opérations complexes (transactions, validations)
- Gère l'audit automatique des mutations
- Utilise les managers pour les requêtes
- Est appelée par les ViewSets

## Pattern Service Layer

```
ViewSet                Service                 Manager/Model
   │                      │                         │
   │  create_action()     │                         │
   ├─────────────────────►│                         │
   │                      │  @transaction.atomic    │
   │                      │  validate + create      │
   │                      ├────────────────────────►│
   │                      │                         │
   │                      │  AuditService.create()  │
   │                      ├────────────────────────►│
   │                      │                         │
   │  Action             │                         │
   │◄─────────────────────┤                         │
```

## CatalogService

**Fichier:** `catalog/services.py`

Gère le cycle de vie des actions: création, modification, transitions de statut, gestion des tags.

### Méthodes principales

#### get_by_id

```python
def get_by_id(self, action_id: int) -> Action | None:
    """
    Récupère une action par son ID avec relations prefetchées.

    Args:
        action_id: ID de l'action

    Returns:
        Action instance avec tags et creator prefetchés, ou None si non trouvée

    Note: Utilisé par les ViewSets après create/update pour recharger l'action
          avec toutes ses relations pour la réponse API.
    """
```

#### create_action

```python
@transaction.atomic
def create_action(self, action_data: dict, created_by_user: User) -> Action:
    """
    Crée une nouvelle action avec tags et audit.

    Args:
        action_data: Dict avec champs (name, description, engine, platform, etc.)
        created_by_user: Utilisateur créateur

    Returns:
        Action instance

    Raises:
        ValueError: Si statut initial invalide

    Audit: ACTION_CREATED
    """
```

**Exemple d'utilisation:**

```python
service = CatalogService()
action = service.create_action(
    action_data={
        'name': 'Oracle Patching',
        'description': 'Patching Oracle Database',
        'engine': 'Oracle',
        'platform': 'AAP',
        'category': 'Patching',
        'status': 'draft',
        'tags': ['oracle', 'patching'],
    },
    created_by_user=request.user
)
```

#### update_status

```python
@transaction.atomic
def update_status(self, action_id: int, transition: str, user: User) -> Action:
    """
    Change le statut via une transition valide.

    Transitions autorisées:
        draft → published (publish)
        published → disabled (disable)
        disabled → published (enable)

    Args:
        action_id: ID de l'action
        transition: Nom de la transition (publish, disable, enable)
        user: Utilisateur effectuant la transition

    Returns:
        Action mise à jour

    Raises:
        InvalidTransitionError: Si transition invalide

    Audit: ACTION_PUBLISHED, ACTION_DISABLED, ACTION_ENABLED
    """
```

**Machine à états:**

```
         ┌─────────────────┐
         │                 │
         ▼                 │
    ┌─────────┐       ┌────┴────┐
    │  DRAFT  │──────►│PUBLISHED│
    └─────────┘       └────┬────┘
      publish              │
                          │ disable
                          ▼
                    ┌──────────┐
                    │ DISABLED │
                    └────┬─────┘
                         │
                         │ enable
                         │
                         └───────► PUBLISHED
```

#### sync_tags

```python
def sync_tags(self, action_id: int, tag_names: list[str]) -> Action:
    """
    Synchronise les tags (remplace tous les tags existants).

    Args:
        action_id: ID de l'action
        tag_names: Liste des noms de tags

    Returns:
        Action mise à jour

    Note: Les tags sont normalisés (lowercase, sans espaces)
    """
```

#### update_execution_steps

```python
@transaction.atomic
def update_execution_steps(self, action_id: int, steps: list[dict],
                           change_type_config: dict | None, user: User) -> Action:
    """
    Met à jour les étapes d'exécution (uniquement pour actions en draft).

    Args:
        action_id: ID de l'action
        steps: Liste des étapes d'exécution
        change_type_config: Configuration ServiceNow optionnelle
        user: Utilisateur pour audit

    Returns:
        Action mise à jour

    Raises:
        ValueError: Si action pas en draft

    Audit: ACTION_UPDATED
    """
```

### Exemple complet

```python
from catalog.services import CatalogService, InvalidTransitionError

service = CatalogService()

# Créer une action
action = service.create_action(
    action_data={
        'name': 'DB Backup',
        'engine': 'Oracle',
        'platform': 'AAP',
        'category': 'Administration',
    },
    created_by_user=user
)

# Ajouter des tags
service.sync_tags(action.id, ['oracle', 'backup', 'production'])

# Publier l'action
try:
    action = service.update_status(action.id, 'publish', user)
except InvalidTransitionError as e:
    print(f"Transition invalide: {e}")

# Désactiver l'action
action = service.update_status(action.id, 'disable', user)
```

## ProfileService

**Fichier:** `profiles/services.py`

Gère les profils utilisateurs et les permissions RBAC.

### Méthodes principales

#### create_profile

```python
@transaction.atomic
def create_profile(self, profile_data: dict, user: User = None) -> Profile:
    """
    Crée un nouveau profil.

    Args:
        profile_data: Dict avec (name, description, ad_group, is_admin, is_auditor)
        user: Optionnel pour audit

    Returns:
        Profile instance

    Raises:
        ValueError: Si nom déjà existant

    Audit: PROFILE_CREATED
    """
```

#### set_action_permissions

```python
@transaction.atomic
def set_action_permissions(self, profile_id: int, permission_data: dict, user=None):
    """
    Configure les permissions d'actions pour un profil (UPSERT).

    Args:
        profile_id: ID du profil
        permission_data: Dict avec:
            - actions_type: 'all' | 'list' | 'pattern'
            - action_ids: Liste d'IDs d'actions (si type=list)
            - tag_patterns: Liste de patterns de tags (si type=pattern)
            - environments: Liste d'environnements autorisés
        user: Optionnel pour audit

    Returns:
        ProfileActionPermission instance
    """
```

#### get_cumulative_permissions

```python
def get_cumulative_permissions(self, user_id: int, ad_groups: list[str]) -> dict:
    """
    Calcule les permissions cumulées pour un utilisateur.

    Un utilisateur peut appartenir à plusieurs AD groups, donc plusieurs profils.
    Les permissions sont agrégées (union des action_ids, tag_patterns, environments).

    Args:
        user_id: ID de l'utilisateur
        ad_groups: Liste des AD groups de l'utilisateur (depuis JWT)

    Returns:
        Dict avec:
            - action_permissions: Liste des permissions d'actions
            - target_permissions: Liste des permissions de targets

    Raises:
        ValueError: Si user_id est None
    """
```

**Exemple de résultat:**

```python
{
    'action_permissions': [
        {
            'actions_type': 'pattern',
            'action_ids': [],
            'tag_patterns': ['oracle', 'patching'],
            'environments': ['dev', 'staging'],
        },
        {
            'actions_type': 'list',
            'action_ids': [1, 2, 3],
            'tag_patterns': [],
            'environments': ['dev', 'staging', 'prod'],
        }
    ],
    'target_permissions': [
        {
            'targets_type': 'all',
            'target_names': [],
            'target_patterns': [],
        }
    ]
}
```

### Export/Import YAML

**Fichier:** `profiles/services_export_import.py`

```python
def export_profiles_to_yaml(profile_ids: list[int] | None = None) -> str:
    """
    Exporte les profils au format YAML pour GitOps.

    Args:
        profile_ids: Liste optionnelle d'IDs (None = tous les profils)

    Returns:
        String YAML
    """

def import_profiles_from_yaml(yaml_content: str, user: User) -> dict:
    """
    Importe les profils depuis YAML (upsert).

    Args:
        yaml_content: Contenu YAML
        user: Utilisateur pour audit

    Returns:
        Dict avec statistiques (created, updated, errors)
    """
```

## AuditService

**Fichier:** `core/services.py`

Gère les logs d'audit immutables.

### Méthodes principales

#### create_entry

```python
from core.models import AuditActionType, AuditEntityType

@staticmethod
def create_entry(user_id: str, action_type: AuditActionType, entity_type: AuditEntityType,
                 entity_id: int, details: dict = None, ip_address: str = None,
                 correlation_id: str = None) -> AuditLog:
    """
    Crée une entrée d'audit (immutable).

    Args:
        user_id: ID de l'utilisateur (string)
        action_type: Type d'action (AuditActionType enum, ex: AuditActionType.ACTION_CREATED)
        entity_type: Type d'entité (AuditEntityType enum, ex: AuditEntityType.ACTION)
        entity_id: ID de l'entité
        details: Détails optionnels (dict sérialisé en JSON)
        ip_address: Adresse IP optionnelle
        correlation_id: ID de corrélation optionnel

    Returns:
        AuditLog instance

    IMPORTANT: Toujours utiliser les enums, pas des strings!
    """
```

**Exemple d'utilisation:**

```python
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.middleware import get_correlation_id

AuditService.create_entry(
    user_id=str(user.id),
    action_type=AuditActionType.PROFILE_CREATED,  # Enum, pas string!
    entity_type=AuditEntityType.PROFILE,           # Enum, pas string!
    entity_id=profile.id,
    details={'name': profile.name},
    correlation_id=get_correlation_id()
)
```

**Types d'actions audit:**

```python
class AuditActionType(models.TextChoices):
    # Actions
    ACTION_CREATED = 'ACTION_CREATED'
    ACTION_UPDATED = 'ACTION_UPDATED'
    ACTION_PUBLISHED = 'ACTION_PUBLISHED'
    ACTION_DISABLED = 'ACTION_DISABLED'
    ACTION_ENABLED = 'ACTION_ENABLED'
    ACTION_DELETED = 'ACTION_DELETED'

    # Profils
    PROFILE_CREATED = 'PROFILE_CREATED'
    PROFILE_UPDATED = 'PROFILE_UPDATED'
    PROFILE_DELETED = 'PROFILE_DELETED'

    # Intégrations
    INTEGRATION_CREATED = 'INTEGRATION_CREATED'
    INTEGRATION_UPDATED = 'INTEGRATION_UPDATED'
    INTEGRATION_DELETED = 'INTEGRATION_DELETED'

    # Exécutions
    EXECUTION_SUBMITTED = 'EXECUTION_SUBMITTED'
    EXECUTION_RUNNING = 'EXECUTION_RUNNING'
    EXECUTION_COMPLETED = 'EXECUTION_COMPLETED'
    EXECUTION_FAILED = 'EXECUTION_FAILED'
    # ...
```

#### list_all

```python
@staticmethod
def list_all(user_id=None, action_type=None, entity_type=None,
             entity_id=None, date_from=None, date_to=None,
             page=1, page_size=25) -> tuple[list, int]:
    """
    Liste les entrées d'audit avec filtres et pagination.

    Returns:
        Tuple (liste d'entrées, total count)
    """
```

#### export_to_csv

```python
@staticmethod
def export_to_csv(user_id=None, action_type=None, entity_type=None,
                  date_from=None, date_to=None) -> StringIO:
    """
    Exporte les entrées d'audit en CSV.

    Returns:
        StringIO buffer avec contenu CSV
    """
```

## Patterns de transaction

### Atomic transactions

```python
from django.db import transaction

class MyService:

    @transaction.atomic
    def complex_operation(self, data, user):
        """
        Opération complexe avec rollback automatique en cas d'erreur.

        Si une exception est levée, toutes les modifications DB sont annulées.
        """
        # Modification 1
        action = Action.objects.create(name=data['name'])

        # Modification 2
        self._sync_tags(action, data['tags'])

        # Modification 3 (audit)
        AuditService.create_entry(
            user_id=str(user.id),
            action_type=AuditActionType.ACTION_CREATED,
            entity_type=AuditEntityType.ACTION,
            entity_id=action.id,
        )

        # Si erreur ici → rollback de tout
        return action
```

### Nested transactions (savepoints)

```python
@transaction.atomic
def parent_operation(self):
    # Modification parent
    profile = Profile.objects.create(name='Test')

    try:
        with transaction.atomic():
            # Sous-transaction (savepoint)
            self._set_permissions(profile)  # Peut échouer
    except IntegrityError:
        # Seule la sous-transaction est rollback
        # profile est toujours créé
        pass
```

## Bonnes pratiques

### 1. Toujours utiliser les services pour les mutations

```python
# ❌ Mauvais: mutation directe dans ViewSet
def create(self, request):
    action = Action.objects.create(**request.data)
    return Response({"data": ActionSerializer(action).data})

# ✅ Bon: déléguer au service
def create(self, request):
    action = CatalogService().create_action(
        action_data=serializer.validated_data,
        created_by_user=request.user
    )
    return Response({"data": ActionSerializer(action).data})
```

### 2. Audit automatique

```python
# ❌ Mauvais: oublier l'audit
def delete_action(self, action_id):
    action = Action.objects.get(id=action_id)
    action.delete()

# ✅ Bon: audit intégré
@transaction.atomic
def delete_action(self, action_id, user):
    action = Action.objects.get(id=action_id)
    action_name = action.name

    action.delete()

    AuditService.create_entry(
        user_id=str(user.id),
        action_type=AuditActionType.ACTION_DELETED,
        entity_type=AuditEntityType.ACTION,
        entity_id=action_id,
        details={'name': action_name},
    )
```

### 3. Validation avant mutation

```python
@transaction.atomic
def update_status(self, action_id, transition, user):
    action = Action.objects.get(id=action_id)

    # ✅ Validation AVANT modification
    new_status = self._validate_transition(action.status, transition)

    # Modification seulement si validation OK
    action.status = new_status
    action.save()
```

### 4. Logging structuré

```python
import structlog

logger = structlog.get_logger(__name__)

class CatalogService:

    @transaction.atomic
    def create_action(self, action_data, created_by_user):
        correlation_id = get_correlation_id()

        # Log au début de l'opération
        logger.info(
            "action_created",
            action_name=action_data['name'],
            user_id=created_by_user.id,
            correlation_id=correlation_id
        )

        # ... opération ...

        return action
```
