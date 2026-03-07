# Notes de Migration : SQL Brut vers Django ORM

> **📦 Document d'archivage — Migration terminée**
> Ce document est conservé pour référence historique. La migration FastAPI→Django est complète (février 2026).
> Voir [MIGRATION_ARCHIVE.md](./migration/MIGRATION_ARCHIVE.md) pour accéder au code FastAPI archivé.

## Vue d'ensemble

Ce document décrit les différences entre l'implémentation FastAPI avec SQL brut et l'implémentation Django ORM, ainsi que les décisions techniques prises lors de la migration.

## 1. Différences SQL Brut vs ORM

### Requêtes simples

**Avant (FastAPI - SQL brut):**
```python
async def get_by_id(action_id: int):
    query = "SELECT * FROM ACTIONS_CATALOG WHERE ID = :id"
    cursor.execute(query, {"id": action_id})
    row = cursor.fetchone()
    return dict(zip([col[0] for col in cursor.description], row))
```

**Après (Django ORM):**
```python
def get_by_id(action_id: int):
    return Action.objects.get(id=action_id)
```

**Avantages ORM:**
- Code plus concis et lisible
- Protection contre les injections SQL
- Gestion automatique des types Python
- Support des relations (ForeignKey, ManyToMany)

### Requêtes avec JOINs

**Avant (FastAPI - SQL brut):**
```python
query = """
    SELECT a.*, u.USERNAME, u.DISPLAY_NAME
    FROM ACTIONS_CATALOG a
    JOIN USERS u ON a.CREATED_BY = u.ID
    WHERE a.ID = :id
"""
```

**Après (Django ORM):**
```python
action = Action.objects.select_related('created_by').get(id=action_id)
# Accès: action.created_by.username
```

**Avantages ORM:**
- `select_related()` évite les requêtes N+1
- Accès aux relations via attributs Python
- Code plus maintenable

### Requêtes avec agrégations

**Avant (FastAPI - SQL brut):**
```python
query = """
    SELECT STATUS, COUNT(*) as count
    FROM EXECUTIONS
    WHERE CREATED_AT >= :date_from
    GROUP BY STATUS
"""
```

**Après (Django ORM):**
```python
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta

date_from = timezone.now() - timedelta(days=30)
stats = Execution.objects.filter(
    created_at__gte=date_from
).values('status').annotate(count=Count('id'))
```

**Avantages ORM:**
- Syntaxe Python native
- Type-safe (détection d'erreurs à l'exécution)
- Support des agrégations complexes

### Pagination

**Avant (FastAPI - SQL brut):**
```python
query = """
    SELECT * FROM ACTIONS_CATALOG
    ORDER BY CREATED_AT DESC
    OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
"""
```

**Après (Django ORM):**
```python
start_index = (page - 1) * page_size
end_index = start_index + page_size
results = Action.objects.all().order_by('-created_at')[start_index:end_index]
total = Action.objects.count()
```

**Avantages ORM:**
- Syntaxe Python slice native
- Compatible avec DRF pagination
- Gestion automatique des limites

## 2. Requêtes Complexes Nécessitant .raw() ou extra()

### Cas où .raw() pourrait être nécessaire

**Note:** Dans cette migration, aucune requête n'a nécessité `.raw()` car toutes les opérations peuvent être exprimées avec l'ORM Django.

**Exemples où .raw() pourrait être nécessaire:**
- Requêtes avec fonctions Oracle spécifiques non supportées par Django
- Requêtes avec CTEs (Common Table Expressions) complexes
- Requêtes avec window functions avancées

**Exemple hypothétique:**
```python
# Si nécessaire (non utilisé dans cette migration)
actions = Action.objects.raw("""
    SELECT a.*, 
           ROW_NUMBER() OVER (PARTITION BY a.ENGINE ORDER BY a.CREATED_AT DESC) as rn
    FROM ACTIONS_CATALOG a
    WHERE rn <= 5
""")
```

### Utilisation de .extra() pour requêtes spécifiques

**Note:** `.extra()` n'a pas été nécessaire dans cette migration. Toutes les requêtes peuvent être exprimées avec l'ORM standard.

**Si nécessaire:**
```python
# Exemple hypothétique pour filtrage JSON complexe
actions = Action.objects.extra(
    where=["JSON_EXISTS(IMPACT_RULES, '$.PROD.level')"]
)
```

## 3. Optimisations de Performance

### select_related() - Éviter les requêtes N+1 pour ForeignKey

**Problème N+1:**
```python
# Sans optimisation: 1 + N requêtes
actions = Action.objects.all()
for action in actions:
    print(action.created_by.username)  # Requête supplémentaire par action
```

**Solution avec select_related():**
```python
# Avec optimisation: 1 seule requête avec JOIN
actions = Action.objects.select_related('created_by').all()
for action in actions:
    print(action.created_by.username)  # Pas de requête supplémentaire
```

**Utilisé dans:**
- `Action.objects.select_related('created_by')`
- `Execution.objects.select_related('action', 'user')`
- `ScheduledExecution.objects.select_related('action', 'user')`

### prefetch_related() - Éviter les requêtes N+1 pour ManyToMany/Reverse ForeignKey

**Problème N+1:**
```python
# Sans optimisation: 1 + N requêtes
actions = Action.objects.all()
for action in actions:
    tags = [at.tag.name for at in action.actiontag_set.all()]  # Requête par action
```

**Solution avec prefetch_related():**
```python
# Avec optimisation: 2 requêtes totales (1 pour actions, 1 pour tags)
actions = Action.objects.prefetch_related('actiontag_set__tag').all()
for action in actions:
    tags = [at.tag.name for at in action.actiontag_set.all()]  # Pas de requête supplémentaire
```

**Utilisé dans:**
- `Action.objects.prefetch_related('actiontag_set__tag')`
- `Execution.objects.prefetch_related('executionstep_set')`
- `Profile.objects.prefetch_related('profileactionpermission', 'profiletargetpermission')`

### annotate() - Agrégations sans requêtes supplémentaires

**Exemple:**
```python
from django.db.models import Count

# Compter les permissions par profil en une seule requête
profiles = Profile.objects.annotate(
    permissions_count=Count('profileactionpermission') + Count('profiletargetpermission')
)
```

**Utilisé dans:**
- `Profile.objects.list_with_permissions_count()` - Comptage des permissions

## 4. Stratégie d'Audit

### Choix: Appels explicites vs Signals Django

**Décision:** Appels explicites à `AuditService.create_entry()` dans les services métier.

**Rationale:** Voir `docs/TRANSACTION_AUDIT_STRATEGY.md` pour détails complets.

**Résumé:**
- ✅ Contrôle précis du moment et du contexte d'audit
- ✅ Enrichissement du contexte métier dans les détails
- ✅ Performance (pas de surcharge signals)
- ✅ Debuggabilité (facile de tracer l'origine)
- ✅ Testabilité (facile de mocker)

**Exemple:**
```python
@transaction.atomic
def create_action(self, action_data, created_by_user):
    action = Action.objects.create(...)
    
    # Audit explicite avec contexte enrichi
    AuditService.create_entry(
        user_id=str(created_by_user.id),
        action_type='ACTION_CREATED',
        entity_type='action',
        entity_id=action.id,
        details={
            'name': action.name,
            'status': action.status,
            'engine': action.engine,
        }
    )
    
    return action
```

## 5. Patterns de Cache

### État actuel

**Note:** Aucun pattern de cache n'a été identifié dans les repositories FastAPI originaux. La migration Django ORM n'a donc pas réimplémenté de cache.

**Si nécessaire à l'avenir:**
- Utiliser `django.core.cache` pour cache en mémoire/Redis
- Utiliser `@cached_property` pour cache au niveau instance
- Utiliser `django-cacheops` pour cache automatique des QuerySets

## 6. Gestion des Champs CLOB/JSON

### Approche: TextField + Helpers

**Décision:** Utiliser `TextField` avec méthodes helper `get_*()` et `set_*()` plutôt que `JSONField` natif.

**Raison:**
- Django 5.2+ supporte `JSONField` avec Oracle, mais nécessite `oracledb` en mode Thick
- Le projet utilise `oracledb` en mode Thin (pas de client Oracle requis)
- `TextField` + helpers offre plus de contrôle et compatibilité

**Implémentation:**
```python
class Action(models.Model):
    parameters_schema = models.TextField(null=True, blank=True, db_column='PARAMETERS_SCHEMA')
    
    def get_parameters_schema(self):
        """Deserialize JSON from CLOB."""
        if self.parameters_schema:
            try:
                return json.loads(self.parameters_schema)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize: {e}")
                return None
        return None
    
    def set_parameters_schema(self, value):
        """Serialize JSON to CLOB."""
        if value is not None:
            self.parameters_schema = json.dumps(value)
        else:
            self.parameters_schema = None
```

**Centralisation:** Helpers centralisés dans `utils/json_helpers.py` pour réutilisation.

## 7. Transactions

### Utilisation de @transaction.atomic

**Toutes les opérations multi-tables utilisent `@transaction.atomic`:**

```python
@transaction.atomic
def create_execution_with_steps(self, user, action, environment, steps_data):
    execution = Execution.objects.create(...)
    for step_data in steps_data:
        ExecutionStep.objects.create(execution=execution, ...)
    return execution
```

**Avantages:**
- Rollback automatique en cas d'exception
- Support des transactions imbriquées
- Gestion efficace par Oracle

## 8. Mapping des Noms de Colonnes

### Convention: db_column explicite

**Tous les modèles utilisent `db_column` pour mapper les noms Oracle:**

```python
class Action(models.Model):
    name = models.CharField(max_length=255, db_column='NAME')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
```

**Raison:**
- Les colonnes Oracle sont en UPPERCASE
- Django utilise snake_case par défaut
- `db_column` permet de garder les noms Oracle existants

## 9. Enums et Choix

### Utilisation de TextChoices

**Tous les enums utilisent `models.TextChoices`:**

```python
class ActionStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    PUBLISHED = 'published', 'Published'
    DISABLED = 'disabled', 'Disabled'

class Action(models.Model):
    status = models.CharField(
        max_length=20,
        choices=ActionStatus.choices,
        default=ActionStatus.DRAFT,
        db_column='STATUS'
    )
```

**Avantages:**
- Validation au niveau Django
- Support dans l'admin Django
- Type-safe avec IDE

## 10. Parité Fonctionnelle

### Opérations CRUD

**Toutes les opérations CRUD FastAPI ont un équivalent Django:**

| FastAPI Repository | Django Equivalent |
|---------------------|-------------------|
| `catalog_repository.create_action()` | `CatalogService.create_action()` |
| `catalog_repository.get_by_id()` | `CatalogService.get_by_id()` |
| `catalog_repository.list_all()` | `CatalogService.list_all()` |
| `catalog_repository.update_action()` | `CatalogService.update_action()` |
| `catalog_repository.delete_action()` | `CatalogService.delete_action()` |

### Filtres et Recherche

**Tous les filtres FastAPI sont supportés:**
- Filtrage par status, engine, platform, item_type
- Recherche par nom/description
- Filtrage par tags (AND logic)
- Pagination avec page/page_size

### Relations

**Toutes les relations sont gérées via ForeignKey/ManyToMany:**
- Action → User (created_by)
- Action → Integration
- Action → Tag (via ActionTag)
- Execution → Action
- Execution → User
- Profile → Permissions

## 11. Tests

### Structure de Tests

**Tests organisés par app avec séparation managers/services:**

```
catalog/tests/
  ├── test_managers.py      # Tests pour ActionManager
  ├── test_services.py     # Tests pour CatalogService
  └── test_edge_cases.py   # Tests cas limites (Task 13)
```

**Framework:** pytest-django avec `@pytest.mark.django_db`

**Couverture:** Structure en place pour atteindre 80%+ de couverture

## 12. Migration Progressive

### Cohabitation FastAPI / Django

**Pendant la migration:**
- Les repositories FastAPI continuent de fonctionner
- Les services Django sont créés en parallèle
- Les tests FastAPI continuent de passer
- Les tests Django sont créés en parallèle

**Bascule progressive:**
- Story M.4: Migration endpoints API catalog vers DRF
- Story M.5: Migration endpoints API profiles vers DRF
- Story M.6: Migration endpoints API executions vers DRF
- Story M.10: Décommissionnement FastAPI

## 13. Points d'Attention

### Limitations connues

1. **Filtrage JSON complexe:** Certains filtres JSON complexes (ex: `JSON_EXISTS`) peuvent nécessiter `.extra()` ou `.raw()` si ajoutés plus tard
2. **Performance:** Pour très grandes tables, considérer l'indexation et l'optimisation des requêtes
3. **Migrations:** Les migrations Django doivent être synchronisées avec Flyway (voir MIGRATION_STRATEGY.md)

### Recommandations Futures

1. **Monitoring:** Ajouter monitoring des requêtes lentes avec `django-debug-toolbar` ou `django-silk`
2. **Cache:** Considérer cache pour requêtes fréquentes (ex: list_published)
3. **Index:** Vérifier que les index Oracle sont optimaux pour les requêtes Django ORM

## 14. Références

- [Django ORM Documentation](https://docs.djangoproject.com/en/5.2/topics/db/)
- [Django QuerySet API](https://docs.djangoproject.com/en/5.2/ref/models/querysets/)
- [pytest-django Documentation](https://pytest-django.readthedocs.io/)
- `docs/TRANSACTION_AUDIT_STRATEGY.md` - Stratégie détaillée transactions/audit
- `MIGRATION_STRATEGY.md` - Stratégie de migration Django
