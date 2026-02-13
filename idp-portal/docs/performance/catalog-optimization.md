# Rapport d'optimisation — Page Catalogue

**Story:** 17.17 — Optimisation requêtes BD page Catalogue
**Date:** 2026-02-07
**Auteur:** Dev Agent (Claude Opus 4.6)

## Résumé exécutif

Audit de performance et optimisation des 3 endpoints alimentant la page Catalogue. Les optimisations ORM (N+1 fixes) du commit `5452b95` (story m-3) étaient déjà en place. Cette story ajoute des **index Oracle** sur les colonnes filtrées et un **cache TTL 5min** sur l'endpoint tags.

## Baseline avant optimisation

| Endpoint | Query count (cache miss) | N+1 | Cache | Notes |
|---|---|---|---|---|
| `GET /catalog/actions/` | 3 | Aucun | Oui (5min) | prefetch_related + select_related OK |
| `GET /catalog/actions/?tags=X` | 3 | Aucun | Oui (5min) | Subquery tag filter OK |
| `GET /catalog/actions/?engine=X` | 3 | Aucun | Oui (5min) | Simple filter |
| `GET /catalog/actions/?q=X` | 3 | Aucun | Oui (5min) | icontains sur name/description |
| `GET /catalog/tags/` | 1 | Aucun | **Non** | Requête avec annotate, pas de cache |
| `GET /users/me/favorites/` | 1 | Aucun | Non | select_related('action') |

**Constat baseline :** Les optimisations ORM étaient excellentes (3 queries seulement pour actions). Le principal gap était l'absence d'**index Oracle** et de **cache sur l'endpoint tags**.

## Optimisations appliquées

### 1. Index Oracle (migration V056)

| Index | Table | Colonnes | Justification |
|---|---|---|---|
| `IDX_ACTIONS_STATUS` | ACTIONS_CATALOG | STATUS | Filtré dans chaque requête (`status='published'`) |
| `IDX_ACTIONS_STATUS_ENGINE` | ACTIONS_CATALOG | STATUS, ENGINE | Filtre combiné fréquent |
| `IDX_ACTIONS_STATUS_CREATED` | ACTIONS_CATALOG | STATUS, CREATED_AT | Tri par date + filtre status |
| `IDX_EXEC_ACTION_CREATED` | EXECUTIONS | ACTION_ID, CREATED_AT | Subquery correlated `execution_count` |

**Fichiers modifiés :**
- `catalog/models.py` : `Meta.indexes` ajouté au modèle `Action`
- `executions/models.py` : `Meta.indexes` ajouté au modèle `Execution`
- `database/migrations/V056__add_catalog_performance_indexes.sql` : SQL Flyway

### 2. Cache endpoint tags (TTL 5min)

- Cache `_tags_cache` (TTLCache, maxsize=200, TTL=300s) ajouté à `list_catalog_tags()`
- Clé cache : `tags_user_{user_id}_cat_{category}` (user-specific pour RBAC)
- Invalidation : Toutes les opérations write (create/update/delete action, tags sync, status change) invalident les deux caches

**Impact :** Endpoint tags passe de 1 query (cache miss) à 0 queries (cache hit) pour les appels répétés dans la fenêtre de 5 minutes.

### 3. Évaluations sans changement

| Élément analysé | Décision | Raison |
|---|---|---|
| RBAC queryset→list→queryset (lignes 599-607) | Acceptable, pas touché | Cache 5min mitige le coût; complexité SQL alternative élevée |
| Text search `__icontains` | Acceptable | VARCHAR colonnes (name 255, description 4000), rapide même sans full-text |
| Environment filter sur CLOB JSON | Acceptable | Index STATUS filtre d'abord, petit dataset résiduel, < 200ms seuil |
| `defer()`/`only()` sur CLOB | Non appliqué | Le serializer a besoin de tous les champs; deferred fields causeraient des queries individuelles |

## Métriques après optimisation

| Endpoint | Query count (cache miss) | Query count (cache hit) | Gain |
|---|---|---|---|
| `GET /catalog/actions/` | 3 | 0 | Cache déjà en place |
| `GET /catalog/tags/` | 1 | **0** | **Nouveau : -100% en cache hit** |
| `GET /users/me/favorites/` | 1 | N/A | Déjà optimal |

### Gains supplémentaires (index Oracle, mesurables en production)

Les index ne changent pas le query count en SQLite test, mais réduisent significativement le temps d'exécution sur Oracle :

- `IDX_ACTIONS_STATUS` : Accélère le filtre `WHERE STATUS = 'published'` (évite full table scan)
- `IDX_ACTIONS_STATUS_ENGINE` : Accélère les filtres combinés
- `IDX_ACTIONS_STATUS_CREATED` : Accélère `ORDER BY CREATED_AT` avec filtre status
- `IDX_EXEC_ACTION_CREATED` : Accélère la subquery correlated `execution_count`

**⚠️ Gain estimé en production :** 30-70% réduction temps requête sur Oracle avec dataset > 100 actions (dépend de la sélectivité et du volume).

**IMPORTANT (Story 17.17 FIX#3):** Ces gains sont des **estimations théoriques** basées sur les best practices d'indexation Oracle. Les tests SQLite ne mesurent PAS l'impact réel des index. **Validation requise en environnement production Oracle** avec monitoring des slow queries avant/après pour confirmer les gains.

## Tests automatisés ajoutés

| Test | Fichier | Vérification |
|---|---|---|
| `test_catalog_actions_query_count_baseline` | test_performance.py | Query count actions ≤ 10 |
| `test_catalog_actions_cache_hit_zero_queries` | test_performance.py | Cache hit = 0 queries |
| `test_catalog_actions_with_filters_query_count` | test_performance.py | Filtres tags/engine/text ≤ 12 queries |
| `test_catalog_tags_query_count_baseline` | test_performance.py | Tags ≤ 6 queries |
| `test_catalog_tags_cache_hit_zero_queries` | test_performance.py | **Nouveau** : Tags cache hit = 0 queries |
| `test_favorites_query_count_baseline` | test_performance.py | Favoris ≤ 5 queries |
| `test_no_n_plus_one_on_catalog_actions` | test_performance.py | Détection N+1 (query count ≤ 10) |
| `test_no_n_plus_one_on_catalog_tags` | test_performance.py | Tags N+1 (query count ≤ 6) |

**Total : 10 tests de performance/régression automatisés.**

## Instructions déploiement production Oracle

**Story 17.17 FIX#2:** Les migrations Django créent les index pour SQLite (dev/test). Pour Oracle production, les index doivent être créés manuellement via SQL :

```sql
-- V056: Add performance indexes for catalog page optimization
CREATE INDEX IDX_ACTIONS_STATUS ON ACTIONS_CATALOG(STATUS);
CREATE INDEX IDX_ACTIONS_STATUS_ENGINE ON ACTIONS_CATALOG(STATUS, ENGINE);
CREATE INDEX IDX_ACTIONS_STATUS_CREATED ON ACTIONS_CATALOG(STATUS, CREATED_AT);
CREATE INDEX IDX_EXEC_ACTION_CREATED ON EXECUTIONS(ACTION_ID, CREATED_AT);
```

**Validation post-déploiement :**
1. Vérifier les index créés : `SELECT INDEX_NAME, TABLE_NAME FROM USER_INDEXES WHERE TABLE_NAME IN ('ACTIONS_CATALOG', 'EXECUTIONS');`
2. Analyser les plans d'exécution : `EXPLAIN PLAN FOR <query catalog>; SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);`
3. Comparer temps requête avant/après avec APM/slow query logs

## Recommandations futures

1. **Monitoring production :** Activer le logging des slow queries (> 500ms) pour détecter les régressions
2. **Serializer list :** Évaluer `ActionListSerializer` pour le catalog list (exclure CLOB fields du listing)
3. **Oracle Text :** Si le volume d'actions dépasse 1000, évaluer Oracle Text Index pour la recherche full-text
4. **Denormalization :** Si le filtre `environment` est utilisé fréquemment, évaluer une colonne dénormalisée `environments` (TEXT array)
5. **Cache granulaire (Story 17.17 FIX#7):** Évaluer invalidation sélective par clé de cache au lieu de `.clear()` global si contention détectée
