# Assessment Qualité du Code — IDP Portal (branche develop)

**Date :** 6 février 2026  
**Branche :** `develop` (commit `6c77f7c`)  
**Portée :** Bonnes pratiques, conception, logique, opportunités de simplification

---

## 1. Vue d'ensemble

| Composant | Technologie | LOC | Fichiers |
|---|---|---:|---:|
| Django Backend | Python 3.12 / Django 5.x / DRF / drf-spectacular | 63 400 | 257 |
| Frontend | React 19 / TypeScript 5.9 / Ant Design 6 / Vite 7 | 65 700 | 313 |
| Base de données | Oracle 23ai / Flyway V001→V070+ | ~1 500 | 51 SQL |
| **Total** | | **~130 600** | **~620** |

**Évolution depuis la précédente évaluation :** Le backend FastAPI (~48 000 LOC) a été supprimé. Le code a presque doublé (+60k LOC) avec de nombreuses stories livrées (Epic 17-25). De multiples améliorations qualité ont été apportées (OracleJSONField, logger frontend, api_client refactorisé, feature flags, ErrorBoundary, mypy progressif, pre-commit, drf-spectacular, etc.).

---

## 2. Score global

| Catégorie | Note | Delta | Commentaire |
|---|:---:|:---:|---|
| **Architecture** | A- | ↑ | FastAPI supprimé, séparation claire des couches |
| **Backend** | B+ | = | Services bien découpés, mais `inventory/services.py` problématique |
| **Frontend** | B+ | ↑ | Wizard refactorisé, hooks extraits, logger créé |
| **Tests** | A- | = | 268 fichiers de tests (139 backend + 129 frontend) |
| **Sécurité** | A- | ↑ | Rate limiting, feature flags, throttling, pre-commit |
| **DevOps / CI** | B+ | ↑ | Docker, pre-commit, drf-spectacular, mypy progressif |
| **Maintenabilité** | B | = | Fichiers monster persistants, opportunités de simplification |

**Score global : B+ (Bon, en progression)**

---

## 3. Bonnes pratiques respectées

### 3.1 Patterns architecturaux solides

- **Service Layer** : Toute logique métier passe par des services (`CatalogService`, `ExecutionService`, `SchedulingService`, `InventoryService`, `ProfileService`). Les views sont des orchestrateurs minces.
- **Custom Manager/QuerySet** : `ActionQuerySet` avec `with_tags()`, `with_creator()`, `search_by_tags()` — chainable et réutilisable.
- **OracleJSONField** (`core/fields.py`) : Custom field Django éliminant les 7 paires getter/setter. Sérialisation/désérialisation transparente, gestion des edge cases (string vide, données corrompues). **Excellente amélioration.**
- **State Machine** implicite pour les transitions de statut (`_VALID_TRANSITIONS`, `ExecutionStatus`).
- **Audit trail** systématique avec `AuditService.create_entry()` sur toutes les opérations critiques.

### 3.2 Frontend bien structuré

- **Refactoring de `ExecutionWizard.tsx`** : De 1 661 à 635 lignes. Steps extraits en composants (`TargetSelectionStep`, `ParametersFormStep`, `ConfirmationStep`). Hooks extraits (`useExecutionSubmit`, `useSchedulingValidation`, `usePatternResolver`, `useDynamicForm`). **Excellente amélioration.**
- **API Client refactorisé** : Logique d'auth, retry 429, error parsing centralisée dans `handleAuthenticatedFetch()` et `parseErrorResponse()`. Plus de duplication de code.
- **Logger structuré** (`services/logger.ts`) : Debug/info en dev uniquement, warn/error en JSON structuré en prod.
- **Types API découpés** (`types/api/catalog.ts`, `types/api/executions.ts`, etc.) au lieu du monolithe `api.ts`.
- **AdminPage découpé** en sous-composants (`pages/admin/*.tsx`).
- **ErrorBoundary** React pour une gestion gracieuse des erreurs.
- **FeatureFlagContext** avec `FeatureGuard` et `FeatureToggle` pour le rollout progressif.

### 3.3 Sécurité renforcée

- **Rate limiting** avec `ExecutionThrottle` et `GeneralAPIThrottle` (DRF throttling).
- **Feature flags** avec anti-thundering herd lock, consistent hashing pour rollout, cache source-aware.
- **Pre-commit hooks** (`.pre-commit-config.yaml`) : detect-secrets, ruff.
- **Secrets baseline** (`.secrets.baseline`) pour le scan automatique.
- **API documentation** automatique via drf-spectacular.
- **SQL injection prevention** : `SAFE_TABLE_NAME_PATTERN` regex + bind parameters partout.

### 3.4 Tests de qualité

- **139 fichiers de tests backend** : unit, intégration, sécurité (SOC1, RBAC granulaire), performance, edge cases.
- **129 fichiers de tests frontend** : composants, services, hooks, contextes, intégration.
- **Factory pattern** (factory-boy) pour les fixtures backend.
- **CI enforced** : `--cov-fail-under=80`, ruff, mypy progressif.

---

## 4. Problèmes de conception et logique

### 4.1 CRITIQUE — `inventory/services.py` : 1 941 lignes, God Service

C'est le fichier le plus problématique du repo. `InventoryService` fait **tout** :
- Résolution de la source d'inventaire (API, DB schema, fallback)
- Lecture Oracle de 3 types d'entités (servers, instances, databases)
- RBAC filtering en mémoire (environnements, restrictions, patterns, attributs, exclusions)
- Normalisation d'environnements
- Cache TTL
- Multi-table config mapping

**Problèmes de logique :**

1. **`list_targets_for_user()` charge TOUT l'inventaire en mémoire** (~300 lignes). Pour chaque appel, il itère sur tous les profils, charge tous les serveurs par environnement, puis applique 4 couches de filtrage in-memory. Pour 10k serveurs × 5 environnements = potentiellement 50k objets en RAM.

2. **Duplication massive** : `list_servers()`, `list_instances()`, `list_databases()` ont le même squelette (validation → read from config → log → limit check → error handling). Les méthodes `_read_instances_from_config` et `_read_instances_from_config_multi` sont quasi-identiques (différence : single value vs IN clause).

3. **`_apply_attribute_filters_across_profiles()`** a une complexité O(n×m) documentée mais non mitigée.

**Simplification proposée :**
```python
# Extraire 3 services distincts :
class InventorySourceResolver:       # Résolution API/DB/fallback
class InventoryQueryExecutor:        # Exécution SQL config-driven
class InventoryRBACFilter:           # Filtrage RBAC multi-couche
```

### 4.2 HAUTE — `executions/views.py` : 1 375 lignes, trop de responsabilités

Ce fichier contient **11 classes APIView** dans un seul module. La méthode `ExecutionsView.post()` fait ~350 lignes et enchaîne :
- Validation du payload
- Résolution d'action
- Validation des targets (RBAC, inventaire, environnement)
- Lookup de configuration d'environnement (change_type, impact, approval)
- Validation mutex
- Détection de workflow vs action
- Validation de paramètres de workflow steps
- Création d'exécution
- Lancement du runtime (simulation, workflow, intégration)
- Gestion d'erreur avec state machine

**Problème de logique :** La méthode POST viole le Single Responsibility Principle. Une erreur à n'importe quelle étape nécessite de comprendre l'intégralité du flux.

**Simplification proposée :**
```python
# Extraire en modules distincts :
executions/views/list_views.py          # GET /executions, /stats, /timeseries, /tags
executions/views/execution_views.py     # POST /executions, GET/PATCH /{id}
executions/views/scheduled_views.py     # Tout /scheduled-executions
executions/views/approval_views.py      # GET /pending-approvals

# La méthode POST devrait devenir :
def post(self, request):
    payload = ExecutionPayloadValidator(request).validate()
    targets = TargetValidator(payload, request.user).validate()
    env_config = EnvironmentConfigResolver(payload.action, targets.environment).resolve()
    MutexValidator(payload.action, targets).validate()
    execution = ExecutionService().create_execution(...)
    ExecutionLauncher(execution).launch()
    return ExecutionResponseBuilder(execution).build()
```

### 4.3 HAUTE — `catalog/views.py` : 1 035 lignes avec fonctions helper globales

Les fonctions `_filter_by_rbac()`, `_check_rbac_for_action()`, `_get_cumulative_permissions_for_user()` sont des fonctions globales dans le module views. Elles devraient être dans un service RBAC dédié.

**Duplication logique :** `_filter_by_rbac()` et `_check_rbac_for_action()` partagent la même logique de vérification action_ids/tag_patterns mais sont implémentées séparément. La méthode `_check_rbac_for_action()` est littéralement un `_filter_by_rbac()` pour un seul élément.

**Simplification :**
```python
class CatalogRBACService:
    def get_permissions(self, user) -> CumulativePermissions | None: ...
    def filter_actions(self, actions, perms) -> list: ...
    def check_action(self, action, perms) -> bool:
        return len(self.filter_actions([action], perms)) > 0
```

### 4.4 HAUTE — Frontend : 3 fichiers encore au-delà de 900 lignes

| Fichier | Lignes | Problème |
|---|---:|---|
| `ExecutionsPage.tsx` | 1 023 | 20+ state variables, 500+ lignes de config Table columns |
| `WorkflowBuilderCanvas.tsx` | 994 | Logique ReactFlow + palette + validation + export |
| `CalendarPage.tsx` | 896 | FullCalendar + filtres + popover + modal edit |

**Simplification :** Chaque page devrait extraire les colonnes de table et la config en fichiers séparés (comme `actionsColumns.tsx` fait pour AdminPage). Les hooks custom devraient encapsuler les state variables et la logique de chargement.

### 4.5 MOYENNE — Environnement : normalisation incohérente

La normalisation d'environnements est répartie entre :
- `InventoryService._normalize_environment()` : aliases hardcodés (certif → staging)
- `_get_env_config_case_insensitive()` dans `executions/utils.py` : case-insensitive lookup
- `get_allowed_environments_for_user()` : ajoute raw ET normalized
- `list_targets_for_user()` : filtre case-insensitive

Chaque endroit fait sa propre version de la normalisation. Il n'y a pas de source unique de vérité pour "quel est l'environnement canonique".

**Simplification :** Créer un `EnvironmentNormalizer` unique utilisé partout :
```python
class EnvironmentNormalizer:
    ALIASES = {'certif': 'staging', 'stg': 'staging', ...}
    
    @staticmethod
    def canonical(raw: str) -> str: ...
    
    @staticmethod
    def matches(a: str, b: str) -> bool: ...
```

### 4.6 MOYENNE — `_is_dba_or_dbops()` : vérification de rôle fragile

```python
def _is_dba_or_dbops(user) -> bool:
    profile = (getattr(user, "profile", "") or "").lower()
    return profile == "dbops" or profile == "dba" or profile.startswith("dba")
```

Ce pattern est dupliqué dans `executions/views.py` et `executions/utils.py`. Le `startswith("dba")` est dangereux (matcherait un profil hypothétique `dba_readonly` qui ne devrait pas avoir accès).

Le check `(getattr(request.user, "profile", "") or "").lower() != "dbops"` est répété 4 fois dans `ScheduledExecutionsView` et `ScheduledExecutionUpdateView`.

**Simplification :** Utiliser le système RBAC existant (`core/permissions.py`) au lieu de vérifications ad-hoc :
```python
# Dans core/permissions.py :
class IsDBAOrDBOPS(BasePermission):
    ADMIN_PROFILES = {'dbops', 'dba', 'dba_applicatif', 'dba_infrastructure'}
    def has_permission(self, request, view):
        return (getattr(request.user, 'profile', '') or '').lower() in self.ADMIN_PROFILES
```

### 4.7 MOYENNE — Pattern de response inconsistant

Certains endpoints wrappent les données dans `{"data": ...}`, d'autres retournent un format mixte :

```python
# ScheduledExecutionsView.get() retourne :
{"data": {"data": [...], "pagination": {...}, "available_actions": [...]}}
# Soit data imbriqué dans data
```

```python
# ScheduledExecutionUpdateView.patch() retourne manuellement :
{"data": {"scheduled_execution_id": ..., "action_id": ..., ...}}
# Au lieu d'utiliser ScheduledExecutionSerializer
```

**Simplification :** Standardiser : toujours `{"data": serializer.data}` ou `{"data": [...], "pagination": {...}}`. Ne jamais imbriquer `data` dans `data`.

### 4.8 BASSE — Fonctions préfixées `_` exportées publiquement

`executions/utils.py` exporte via `__all__` des fonctions préfixées `_` :
```python
__all__ = [
    "_get_env_config_case_insensitive",
    "_parse_int",
    "_is_dba_or_dbops",
    ...
]
```

Le préfixe `_` en Python signifie "privé". Si ces fonctions sont dans `__all__`, elles sont publiques et ne devraient pas avoir le préfixe. C'est un signal de confusion sur la responsabilité du module.

### 4.9 BASSE — `CalendarPage.tsx` : logique métier dans le composant page

La page Calendar contient de la logique de manipulation de dates, de transformation d'événements FullCalendar, et de gestion d'état d'édition dans un seul composant de 896 lignes. Le modal d'édition de scheduled execution devrait être un composant séparé.

---

## 5. Opportunités de simplification concrètes

### 5.1 Éliminer la duplication dans InventoryService

Les méthodes `_read_*_from_config` et `_read_*_from_config_multi` partagent ~80% de code. Unifier :

```python
def _read_entity_from_config(
    self, entity: str, environment: str, 
    filters: dict | None = None,
    multi_filter: tuple[str, list[str]] | None = None
) -> list[dict]:
    """Unified config-driven entity reader for servers/instances/databases."""
    mapper = self._get_inventory_mapper()
    if mapper is None or not mapper.is_multi_table:
        return self._flat_fallback(entity, environment)
    
    table = mapper.get_table_name(entity)
    select = mapper.build_select_clause(entity)
    where_clause, params = mapper.build_where_clause(entity, filters or {})
    
    if multi_filter:
        col, values = multi_filter
        in_params = {f'p_{i}': v for i, v in enumerate(values)}
        in_clause = ', '.join(f':{k}' for k in in_params)
        where_clause += f" AND UPPER({col}) IN ({in_clause})"
        params.update(in_params)
    
    sql = f"SELECT * FROM (SELECT {select} FROM {table}"
    if where_clause:
        sql += f" WHERE {where_clause}"
    sql += f" ORDER BY name) WHERE ROWNUM <= {MAX_MULTI_TABLE_RESULTS}"
    
    return self._execute_mapped_query(sql, params)
```

**Impact :** Éliminerait ~600 lignes de code dupliqué dans `inventory/services.py`.

### 5.2 Standardiser la pagination

Le pattern de pagination est réimplémenté dans chaque view :
```python
total = qs.count()
page = (offset // limit) + 1
total_pages = (total + limit - 1) // limit if limit else 1
items = list(qs[offset: offset + limit])
```

**Simplification :** Un utilitaire réutilisable :
```python
def paginate_queryset(qs, offset, limit):
    total = qs.count()
    return {
        'items': list(qs[offset:offset+limit]),
        'pagination': {
            'page': (offset // limit) + 1,
            'page_size': limit,
            'total': total,
            'total_pages': max(1, (total + limit - 1) // limit),
        }
    }
```

### 5.3 Extraire les colonnes Table d'ExecutionsPage

Les définitions de colonnes Ant Design Table représentent ~300 lignes dans `ExecutionsPage.tsx`. Elles devraient être dans un fichier séparé comme c'est déjà fait pour `actionsColumns.tsx`.

### 5.4 Unifier les checks RBAC dans les views

Au lieu de `if execution.user_id != request.user.id and not _is_dba_or_dbops(request.user)` répété 5 fois, créer une permission DRF réutilisable ou un mixin.

### 5.5 Réduire les levels d'imbrication dans `list_targets_for_user()`

Cette méthode de 300 lignes a 4 niveaux d'imbrication et 15+ variables locales. Refactoriser en étapes nommées :

```python
def list_targets_for_user(self, user_id, ad_groups, ...):
    permissions = self._aggregate_profile_permissions(ad_groups)
    if not permissions.allowed_environments:
        return [], 0, False
    
    all_targets = self._load_targets(permissions)
    filtered = self._apply_rbac_chain(all_targets, permissions)
    return self._paginate(filtered, page, page_size)
```

---

## 6. Métriques

### Fichiers les plus volumineux (code, hors tests)

| Rang | Fichier | LOC | Action recommandée |
|:---:|---|---:|---|
| 1 | `inventory/services.py` | 1 941 | Split en 3 services |
| 2 | `executions/views.py` | 1 375 | Split en 4 modules |
| 3 | `catalog/views.py` | 1 035 | Extraire RBAC helpers |
| 4 | `executions/workflow_runtime.py` | 1 022 | Acceptable (domaine complexe) |
| 5 | `executions/services.py` | 1 032 | Acceptable (domaine complexe) |
| 6 | `ExecutionsPage.tsx` | 1 023 | Extraire colonnes et hooks |
| 7 | `WorkflowBuilderCanvas.tsx` | 994 | Extraire palette et validation |
| 8 | `CalendarPage.tsx` | 896 | Extraire modal edit et event transform |

### Ratio tests/code

| Composant | Code (LOC) | Tests (LOC) | Ratio |
|---|---:|---:|---:|
| Backend | ~35 000 | ~28 000 | 0.80 |
| Frontend | ~31 000 | ~35 000 | 1.13 |
| **Total** | **~66 000** | **~63 000** | **0.95** |

---

## 7. Conformité aux bonnes pratiques

| Pratique | Avant | Maintenant | Notes |
|---|:---:|:---:|---|
| Single backend | ❌ FastAPI+Django | ✅ Django seul | FastAPI supprimé |
| API documentation | ❌ | ✅ drf-spectacular | OpenAPI auto-généré |
| OracleJSONField | ❌ 7 getter/setter | ✅ Custom field | Transparence totale |
| Frontend logger | ❌ console.log | ✅ logger service | Structuré, level-aware |
| API client DRY | ❌ 4x duplication | ✅ handleAuthenticatedFetch | Centralisé |
| Rate limiting | ❌ | ✅ DRF throttling | ExecutionThrottle + GeneralAPIThrottle |
| Feature flags | ❌ | ✅ Système complet | DB/env, rollout %, cache, anti-thundering |
| Error boundary | ❌ | ✅ React ErrorBoundary | Crash gracieux |
| Pre-commit | ❌ | ✅ detect-secrets, ruff | Guard automatique |
| Types API découpés | ❌ 961 LOC monolithe | ✅ 10 modules | Par domaine |
| Docker | ❌ | ✅ docker-build.yml | CI build |
| Secrets startup check | ❌ | ✅ settings.py fail-fast | SECRET_KEY validé |
| mypy progressif | ❌ advisory | ⚠️ progressif | continue-on-error mais baseline tracking |
| Lock file dépendances | ❌ | ❌ | Toujours pas de lockfile |
| God services | ❌ | ❌ | inventory/services.py a grandi |

---

## 8. Recommandations prioritaires

### Court terme (1-2 sprints)

| # | Action | Impact | Effort |
|---|---|---|---|
| 1 | **Split `inventory/services.py`** en 3 classes | Maintenabilité | M |
| 2 | **Split `executions/views.py`** en 4 modules | Lisibilité | M |
| 3 | **Extraire RBAC catalog** dans un service dédié | Réutilisabilité | S |
| 4 | **Renommer fonctions `_` exportées** dans `executions/utils.py` | Convention | XS |
| 5 | **Standardiser le format de réponse** (éliminer `data.data`) | Contrat API | S |

### Moyen terme (1-2 mois)

| # | Action | Impact | Effort |
|---|---|---|---|
| 6 | **Créer `EnvironmentNormalizer`** unique | Cohérence | S |
| 7 | **Créer permission `IsDBAOrDBOPS`** DRF | DRY | S |
| 8 | **Extraire colonnes Table** d'ExecutionsPage dans un fichier | Lisibilité | S |
| 9 | **Refactoriser `CalendarPage.tsx`** et `WorkflowBuilderCanvas.tsx` | Maintenabilité | M |
| 10 | **Ajouter lockfile** (`pip-compile` ou `poetry.lock`) | Reproductibilité | S |

### Long terme (3+ mois)

| # | Action | Impact | Effort |
|---|---|---|---|
| 11 | **Implémenter RBAC SQL-side** dans InventoryService | Performance | L |
| 12 | **Passer mypy en strict** pour le backend | Fiabilité | L |
| 13 | **Monitoring APM** (Sentry, Datadog) | Opérations | M |

---

## 9. Conclusion

Le codebase a significativement progressé depuis la dernière évaluation. La suppression du backend FastAPI, le refactoring de l'API client et du wizard, l'introduction du logger structuré, de l'OracleJSONField, du système de feature flags, et du rate limiting montrent une vraie dynamique d'amélioration continue.

Les principaux axes de travail restants sont :
1. **`inventory/services.py`** qui concentre trop de responsabilités et de code dupliqué — c'est le point noir du repo
2. **`executions/views.py`** qui est un fichier orchestrateur trop volumineux
3. **3 composants frontend** qui dépassent encore 900 lignes

La qualité des tests reste excellente (ratio 0.95), la sécurité a été considérablement renforcée, et les conventions sont globalement bien respectées. Le projet est dans un bon état de santé pour une application en croissance active.
