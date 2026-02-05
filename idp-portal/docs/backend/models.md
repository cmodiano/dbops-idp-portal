# Modèles Django et Relations

## Vue d'ensemble

Les modèles Django sont mappés sur les tables Oracle existantes. La convention de nommage Oracle (UPPER_SNAKE_CASE) est préservée via l'attribut `db_column`.

## Mapping Oracle → Django

### Conventions

| Oracle | Django |
|--------|--------|
| Table `ACTIONS_CATALOG` | `class Action` avec `db_table = 'ACTIONS_CATALOG'` |
| Colonne `CREATED_AT` | Champ avec `db_column='CREATED_AT'` |
| CLOB (JSON) | `TextField` + helpers `get_*/set_*` pour sérialisation |
| NUMBER(1) CHECK | `IntegerField` avec valeurs 0/1 |
| CHECK constraint | `TextChoices` enum |

## Diagramme ER simplifié

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     USERS       │     │    PROFILES     │     │  INTEGRATIONS   │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ ID (PK)         │     │ ID (PK)         │     │ ID (PK)         │
│ USERNAME        │     │ NAME            │     │ TYPE            │
│ DISPLAY_NAME    │     │ AD_GROUP        │     │ NAME            │
│ PROFILE         │     │ IS_ADMIN        │     │ BASE_URL        │
│ SAML_SUBJECT    │     │ IS_AUDITOR      │     │ CONFIG (CLOB)   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │              ┌────────┴────────┐              │
         │              ▼                 ▼              │
         │    ┌─────────────────┐ ┌─────────────────┐   │
         │    │PROFILE_ACTION_  │ │PROFILE_TARGET_  │   │
         │    │  PERMISSIONS    │ │  PERMISSIONS    │   │
         │    ├─────────────────┤ ├─────────────────┤   │
         │    │ PROFILE_ID (PK) │ │ PROFILE_ID (PK) │   │
         │    │ PERMISSION_TYPE │ │ PERMISSION_TYPE │   │
         │    │ ACTION_IDS_JSON │ │ TARGET_NAMES_JSON   │
         │    │ TAG_PATTERNS_JSON││ TARGET_PATTERNS_JSON│
         │    │ ENVIRONMENTS_JSON││                 │   │
         │    └─────────────────┘ └─────────────────┘   │
         │                                              │
         ▼                                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     ACTIONS_CATALOG                          │
├─────────────────────────────────────────────────────────────┤
│ ID (PK)           │ CREATED_BY (FK → USERS)                 │
│ NAME              │ INTEGRATION_ID (FK → INTEGRATIONS)      │
│ DESCRIPTION       │ STATUS (draft/published/disabled)       │
│ ENGINE            │ ITEM_TYPE (action/workflow)             │
│ PLATFORM          │ PARAMETERS_SCHEMA (CLOB)                │
│ CATEGORY          │ IMPACT_RULES (CLOB)                     │
│                   │ EXECUTION_STEPS (CLOB)                  │
│                   │ REMEDIATION_RULES (CLOB)                │
└────────┬──────────┴─────────────────────────────────────────┘
         │
    ┌────┴────┐                    ┌─────────────────┐
    ▼         ▼                    │   AUDIT_LOG     │
┌────────┐ ┌─────────┐             ├─────────────────┤
│ TAGS   │ │ACTION_  │             │ ID (PK)         │
├────────┤ │ TAGS    │             │ USER_ID         │
│ID (PK) │ ├─────────┤             │ ACTION_TYPE     │
│NAME    │ │ACTION_ID│             │ ENTITY_TYPE     │
└────────┘ │TAG_ID   │             │ ENTITY_ID       │
           └─────────┘             │ DETAILS (CLOB)  │
                                   │ CORRELATION_ID  │
                                   └─────────────────┘
```

## Modèles par app

### catalog/models.py

#### Action

```python
class Action(models.Model):
    """Représente une action ou workflow dans le catalogue."""

    id = models.BigAutoField(primary_key=True, db_column='ID')
    name = models.CharField(max_length=255, unique=True, db_column='NAME')
    description = models.CharField(max_length=4000, null=True, db_column='DESCRIPTION')
    category = models.CharField(choices=ActionCategory.choices, db_column='CATEGORY')
    engine = models.CharField(choices=ActionEngine.choices, db_column='ENGINE')
    platform = models.CharField(choices=ActionPlatform.choices, db_column='PLATFORM')
    status = models.CharField(choices=ActionStatus.choices, default='draft', db_column='STATUS')
    item_type = models.CharField(choices=ActionItemType.choices, default='action', db_column='ITEM_TYPE')

    # Champs CLOB (JSON sérialisé)
    parameters_schema = models.TextField(null=True, db_column='PARAMETERS_SCHEMA')
    impact_rules = models.TextField(null=True, db_column='IMPACT_RULES')
    execution_steps = models.TextField(null=True, db_column='EXECUTION_STEPS')
    change_type_config = models.TextField(null=True, db_column='CHANGE_TYPE_CONFIG')
    remediation_rules = models.TextField(null=True, db_column='REMEDIATION_RULES')
    documentation_md = models.TextField(null=True, db_column='DOCUMENTATION_MD')

    # Relations
    created_by = models.ForeignKey('idp_auth.User', on_delete=models.SET_NULL, null=True)
    integration = models.ForeignKey('integrations.Integration', on_delete=models.SET_NULL, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(null=True, db_column='UPDATED_AT')

    # Manager
    objects = ActionManager()

    class Meta:
        db_table = 'ACTIONS_CATALOG'
```

**Helpers JSON pour CLOB:**

```python
def get_parameters_schema(self):
    """Deserialize JSON from CLOB."""
    if self.parameters_schema:
        return json.loads(self.parameters_schema)
    return None

def set_parameters_schema(self, value):
    """Serialize JSON to CLOB."""
    self.parameters_schema = json.dumps(value) if value else None
```

#### Enums

```python
class ActionStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    PUBLISHED = 'published', 'Published'
    DISABLED = 'disabled', 'Disabled'

class ActionEngine(models.TextChoices):
    ORACLE = 'Oracle', 'Oracle'
    SQL_SERVER = 'SQL Server', 'SQL Server'
    DB2 = 'DB2', 'DB2'

class ActionPlatform(models.TextChoices):
    AAP = 'AAP', 'AAP'
    GITHUB_ACTIONS = 'GitHub Actions', 'GitHub Actions'
    AZURE_DEVOPS = 'Azure DevOps', 'Azure DevOps'
    TERRAFORM = 'Terraform', 'Terraform'
```

#### Tag et ActionTag

```python
class Tag(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    name = models.CharField(max_length=255, unique=True, db_column='NAME')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')

    class Meta:
        db_table = 'TAGS'

class ActionTag(models.Model):
    """Table de liaison Many-to-Many Action ↔ Tag."""
    action = models.ForeignKey(Action, on_delete=models.CASCADE, db_column='ACTION_ID')
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, db_column='TAG_ID')

    class Meta:
        db_table = 'ACTION_TAGS'
        unique_together = [['action', 'tag']]
```

#### UserFavorite

```python
class UserFavorite(models.Model):
    """Favoris utilisateur."""
    user = models.ForeignKey('idp_auth.User', on_delete=models.CASCADE, db_column='USER_ID')
    action = models.ForeignKey(Action, on_delete=models.CASCADE, db_column='ACTION_ID')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')

    class Meta:
        db_table = 'USER_FAVORITES'
        unique_together = [['user', 'action']]
```

### profiles/models.py

#### Profile

```python
class Profile(models.Model):
    """Profil utilisateur lié à un AD group."""

    id = models.BigAutoField(primary_key=True, db_column='ID')
    name = models.CharField(max_length=255, unique=True, db_column='NAME')
    description = models.CharField(max_length=4000, null=True, db_column='DESCRIPTION')
    ad_group = models.CharField(max_length=512, db_column='AD_GROUP')
    is_admin = models.IntegerField(default=0, db_column='IS_ADMIN')      # 0 ou 1
    is_auditor = models.IntegerField(default=0, db_column='IS_AUDITOR')  # 0 ou 1

    objects = ProfileManager()

    class Meta:
        db_table = 'PROFILES'
```

#### ProfileActionPermission

```python
class ProfileActionPermission(models.Model):
    """Permissions d'actions pour un profil (OneToOne)."""

    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, primary_key=True)
    permission_type = models.CharField(choices=[('LIST', 'List'), ('PATTERN', 'Pattern'), ('ALL', 'All')])

    # JSON dans CLOB
    action_ids_json = models.TextField(null=True, db_column='ACTION_IDS_JSON')
    tag_patterns_json = models.TextField(null=True, db_column='TAG_PATTERNS_JSON')
    environments_json = models.TextField(null=True, db_column='ENVIRONMENTS_JSON')

    class Meta:
        db_table = 'PROFILE_ACTION_PERMISSIONS'
```

#### ProfileTargetPermission

```python
class ProfileTargetPermission(models.Model):
    """Permissions de targets pour un profil (OneToOne)."""

    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, primary_key=True)
    permission_type = models.CharField(choices=[('LIST', 'List'), ('PATTERN', 'Pattern'), ('ALL', 'All')])

    # JSON dans CLOB
    target_names_json = models.TextField(null=True, db_column='TARGET_NAMES_JSON')
    target_patterns_json = models.TextField(null=True, db_column='TARGET_PATTERNS_JSON')

    class Meta:
        db_table = 'PROFILE_TARGET_PERMISSIONS'
```

### executions/models.py

#### Execution

```python
class Execution(models.Model):
    """Exécution d'une action."""

    id = models.BigAutoField(primary_key=True, db_column='ID')
    action = models.ForeignKey('catalog.Action', on_delete=models.CASCADE)
    user = models.ForeignKey('idp_auth.User', on_delete=models.CASCADE)
    environment = models.CharField(choices=ExecutionEnvironment.choices)
    parameters = models.TextField(null=True)  # JSON
    status = models.CharField(choices=ExecutionStatus.choices, default='SUBMITTED')
    servicenow_change_id = models.CharField(max_length=100, null=True)

    # Approbation
    approved_by = models.ForeignKey('idp_auth.User', null=True, related_name='approved_executions')
    approved_at = models.DateTimeField(null=True)
    approval_comment = models.CharField(max_length=1000, null=True)

    # Remédiation
    parent_execution = models.ForeignKey('self', null=True, related_name='child_executions')

    objects = ExecutionManager()

    class Meta:
        db_table = 'EXECUTIONS'
```

#### ScheduledExecution et RecurringPattern

```python
class ScheduledExecution(models.Model):
    """Exécution planifiée (one-time ou recurring)."""

    id = models.BigAutoField(primary_key=True)
    action = models.ForeignKey('catalog.Action', on_delete=models.CASCADE)
    user = models.ForeignKey('idp_auth.User', on_delete=models.CASCADE)
    environment = models.CharField(choices=ExecutionEnvironment.choices)
    parameters = models.TextField(null=True)
    scheduled_at = models.DateTimeField(null=True)
    status = models.CharField(choices=ScheduledExecutionStatus.choices, default='pending')

    class Meta:
        db_table = 'SCHEDULED_EXECUTIONS'

class RecurringPattern(models.Model):
    """Configuration de récurrence."""

    scheduled_execution = models.OneToOneField(ScheduledExecution, on_delete=models.CASCADE)
    pattern_type = models.CharField(choices=[('one_time', 'One Time'), ('daily', 'Daily'), ('weekly', 'Weekly'), ('cron', 'Cron')])
    pattern_config = models.TextField(null=True)  # JSON
    next_execution_date = models.DateTimeField()
    is_active = models.IntegerField(default=1)

    class Meta:
        db_table = 'RECURRING_PATTERNS'
```

### core/models.py

#### AuditLog

```python
class AuditLog(models.Model):
    """Log d'audit immutable."""

    id = models.BigAutoField(primary_key=True, db_column='ID')
    timestamp = models.DateTimeField(auto_now_add=True, db_column='TIMESTAMP')
    user_id = models.CharField(max_length=100, db_column='USER_ID')
    action_type = models.CharField(choices=AuditActionType.choices, db_column='ACTION_TYPE')
    entity_type = models.CharField(choices=AuditEntityType.choices, db_column='ENTITY_TYPE')
    entity_id = models.BigIntegerField(db_column='ENTITY_ID')
    details = models.TextField(null=True, db_column='DETAILS')  # JSON
    ip_address = models.CharField(max_length=45, null=True, db_column='IP_ADDRESS')
    correlation_id = models.CharField(max_length=64, null=True, db_column='CORRELATION_ID')

    objects = AuditLogManager()

    class Meta:
        db_table = 'AUDIT_LOG'
```

## Managers personnalisés

### ActionManager

```python
class ActionManager(models.Manager):
    """Manager pour Action avec méthodes de requête optimisées."""

    def list_published(self):
        """Actions publiées uniquement."""
        return self.filter(status=ActionStatus.PUBLISHED)

    def search_by_tags(self, tag_names: list[str]):
        """Recherche par tags (logique AND)."""
        queryset = self.filter(status=ActionStatus.PUBLISHED)
        for tag_name in tag_names:
            queryset = queryset.filter(actiontag__tag__name=tag_name)
        return queryset.distinct()

    def with_tags(self):
        """Prefetch tags pour éviter N+1."""
        return self.prefetch_related('actiontag_set__tag')

    def with_creator(self):
        """Select related creator pour éviter N+1."""
        return self.select_related('created_by')
```

### ProfileManager

```python
class ProfileManager(models.Manager):

    def find_by_ad_groups(self, ad_groups: list[str]):
        """Trouve les profils dont AD_GROUP est dans la liste."""
        if not ad_groups:
            return self.none()
        return self.filter(ad_group__in=ad_groups).order_by('name')

    def list_with_permissions_count(self):
        """
        Liste tous les profils avec compteur de permissions.

        Returns:
            QuerySet annoté avec permissions_count
        """
        from django.db.models import Count
        return self.annotate(
            permissions_count=Count('profileactionpermission', distinct=True) +
                              Count('profiletargetpermission', distinct=True)
        ).order_by('name')
```

### AuditLogManager

```python
class AuditLogManager(models.Manager):

    def create_entry(self, user_id, action_type, entity_type, entity_id,
                     details=None, ip_address=None, correlation_id=None):
        """Crée une entrée d'audit."""
        details_json = json.dumps(details) if details else None
        return self.create(
            user_id=user_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details_json,
            ip_address=ip_address,
            correlation_id=correlation_id,
        )

    def list_by_entity(self, entity_type, entity_id):
        """Liste l'historique d'une entité."""
        return self.filter(entity_type=entity_type, entity_id=entity_id).order_by('-timestamp')
```

## Bonnes pratiques

### Éviter les N+1 queries

```python
# ❌ Mauvais: N+1 queries
actions = Action.objects.all()
for action in actions:
    print(action.created_by.username)  # 1 query par action

# ✅ Bon: select_related
actions = Action.objects.select_related('created_by').all()
for action in actions:
    print(action.created_by.username)  # 0 query supplémentaire

# ✅ Bon: prefetch_related pour M2M
actions = Action.objects.prefetch_related('actiontag_set__tag').all()
for action in actions:
    for at in action.actiontag_set.all():  # 0 query supplémentaire
        print(at.tag.name)
```

### Utiliser les managers

```python
# Via manager
Action.objects.list_published()
Action.objects.search_by_tags(['oracle', 'patching'])
Action.objects.with_tags().with_creator()

# Vs requêtes manuelles répétées
Action.objects.filter(status='published').prefetch_related('actiontag_set__tag').select_related('created_by')
```

### JSON dans les champs CLOB

```python
# Toujours utiliser les helpers
action = Action.objects.get(id=1)

# ❌ Mauvais
data = json.loads(action.parameters_schema)
action.parameters_schema = json.dumps(new_data)

# ✅ Bon
data = action.get_parameters_schema()
action.set_parameters_schema(new_data)
action.save()
```
