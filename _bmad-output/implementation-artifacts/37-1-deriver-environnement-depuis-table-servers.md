# Story 37.1 : Dériver l'environnement depuis la table servers

Status: done

## Change Log

- 2026-02-23 : Code review adversarial — 1 bug CRITIQUE (double-préfixe `d.d.DB_NAME` dans `_read_databases_via_instances`), 2 HIGH (aliasing `str.replace` fragile → helper `_build_aliased_select`, 3 blocs code mort supprimés), 2 MEDIUM (except re-wrap, ORDER BY), 3 tests régression ajoutés. 33/33 tests passent.
- 2026-02-23 : Implémentation complète Story 37.1 — environnement dérivé depuis table servers via JOIN. 5 méthodes modifiées dans `query_executor.py`, 7 nouveaux tests + 3 mis à jour, docstring mapper enrichie. 30/30 tests story + 1455 tests régression passent.

## Story

En tant qu'équipe backend / produit,
je veux que le filtre `environment` sur les listes **instances** et **databases** soit appliqué via la table **servers** (JOIN),
afin de refléter le modèle où c'est le serveur qui porte l'environnement (database → instance → server).

## Acceptance Criteria

1. **Given** le mapper multi-tables est configuré avec entités servers, instances, databases
   **When** on appelle `read_instances(environment='dev')`
   **Then** la requête joint la table **instances** à la table **servers** (`instances.server_ref_col → servers.name_col`)
   **And** le filtre `WHERE` applique `UPPER(srv.{srv_env_col}) = UPPER(:p_environment)` (colonne environment mappée pour servers)
   **And** les résultats ne contiennent que des instances dont le serveur est dans l'environnement demandé

2. **Given** le mapper multi-tables est configuré
   **When** on appelle `read_databases(environment='dev')` sans filtre serveur
   **Then** la requête joint **databases → instances → servers** et filtre sur **servers.environment = 'dev'**
   **And** les résultats ne contiennent que des bases dont le serveur est dans cet environnement

3. **Given** on appelle `read_databases(environment='dev', server_names=['srv01'])`
   **Then** la requête joint databases → instances → servers
   **And** les filtres appliqués sont : `servers.environment = 'dev'` ET `instances.server_ref IN ('srv01')`
   **And** la structure JOIN servers est préparée pour accueillir engine_type (Story 37.2, même jointure réutilisable)

4. **Given** une config où instances ou databases ont encore une colonne `environment` mappée
   **Then** le comportement est d'utiliser la jointure avec servers pour le filtre environment (pas de filtre sur la colonne locale)
   **And** le mapper reste valide ; documenter en commentaire que pour « environnement porté par le serveur », la colonne environment locale sur instances/databases est ignorée

## Tasks / Subtasks

- [x] Task 1 : Modifier `_read_entity_from_config` — chemin instances standard (AC: #1, #4)
  - [x] 1.1 Pour entity_type='instance' avec environment fourni : construire JOIN instances → servers (via `server_ref_col` → `srv_name_col`) et filtrer sur `srv.{srv_env_col}` au lieu de la colonne locale
  - [x] 1.2 Conserver le filtre `server_ref` existant pour le filtre par serveur unique (cumul avec env)
  - [x] 1.3 Annoter `# nosec B608` + commentaire expliquant la validation mapper

- [x] Task 2 : Modifier `_read_entity_from_config` — chemin databases standard sans server_name/server_names (AC: #2, #4)
  - [x] 2.1 Pour entity_type='database' sans server_name/server_names : si servers config disponible, construire JOIN databases → instances → servers et filtrer environment sur servers
  - [x] 2.2 Fallback gracieux si servers config absent : comportement actuel (filtre colonne locale databases si mappée)
  - [x] 2.3 Annoter le SQL généré

- [x] Task 3 : Modifier `_read_entity_multi_server` — chemin instances multi-serveurs (AC: #1, #3)
  - [x] 3.1 Remplacer le filtre `UPPER(env_col) = UPPER(:p_environment)` sur la colonne instances par un JOIN sur la table servers et filtre sur `UPPER(srv.{srv_env_col}) = UPPER(:p_environment)`
  - [x] 3.2 Conserver le filtre `IN (server_names)` sur `instances.server_ref_col`

- [x] Task 4 : Modifier `_read_databases_multi_server` (AC: #3, #4)
  - [x] 4.1 Remplacer le filtre `UPPER(d.{db_env_col})` par un JOIN supplémentaire vers servers : `i.{inst_server_ref_col} → srv.{srv_name_col}`, filtre sur `UPPER(srv.{srv_env_col})`
  - [x] 4.2 Conserver le filtre `IN (server_names)` sur `i.{inst_server_ref_col}`

- [x] Task 5 : Modifier `_read_databases_via_instances` (AC: #1, #4)
  - [x] 5.1 Remplacer le filtre environment sur `d.{db_env_col}` par JOIN vers servers et filtre sur `srv.{srv_env_col}`
  - [x] 5.2 La jointure `i.{inst_server_ref_col} = srv.{srv_name_col}` s'ajoute à la clause FROM

- [x] Task 6 : Écrire les tests (AC: #1–#4)
  - [x] 6.1 `test_read_instances_env_from_servers_join` — vérifier SQL contient JOIN servers, filtre sur colonne env servers, **pas** sur colonne env instances
  - [x] 6.2 `test_read_databases_env_from_servers_join` — chemin standard sans server_name
  - [x] 6.3 `test_read_databases_multi_server_env_from_servers_join` — chemin multi-serveurs
  - [x] 6.4 `test_read_databases_via_instances_env_from_servers_join` — chemin via instances
  - [x] 6.5 `test_read_instances_multi_server_env_from_servers_join` — chemin instances multi-server
  - [x] 6.6 `test_no_regression_servers_env_filter` — servers utilisent toujours leur propre env colonne (pas de JOIN)

- [x] Task 7 : Documenter dans mapper.py (AC: #4)
  - [x] 7.1 Ajouter commentaire dans la docstring de `InventoryMapper` ou dans le docstring de config format : pour instances/databases, la colonne `environment` locale est optionnelle si on utilise le mode « env porté par le serveur »

## Dev Notes

### Analyse du code actuel

**Fichier principal :** `inventory/query_executor.py`

**Chemin standard `_read_entity_from_config` (lignes 259–382) :**
```python
# Pour instances — filtre actuel sur colonne locale (À CHANGER)
filters = {}
if environment:
    filters['environment'] = environment  # ← mappe sur instances.ENV (incorrect)
if engine_type and entity_type == 'server':
    filters['engine_type'] = engine_type
if server_name and entity_type in ('instance',):
    filters['server_ref'] = server_name

where_clause, params = mapper.build_where_clause(entity_plural, filters)
# Produit: WHERE UPPER(ENV) = UPPER(:p_environment)
# Doit devenir: WHERE UPPER(srv.ENV) = UPPER(:p_environment) avec JOIN servers
```

**Chemin multi-server instances `_read_entity_multi_server` (lignes 418–424) :**
```python
# Requête actuelle — filtre environment sur instances.ENV (À CHANGER)
inner_sql = (
    f"SELECT {select} FROM {table} "
    f"WHERE UPPER({env_col}) = UPPER(:p_environment) "  # ← colonne locale
    f"AND UPPER({server_ref_col}) IN ({in_placeholders}) "
    f"ORDER BY name"
)
```

**Chemin `_read_databases_multi_server` (lignes 478–485) :**
```python
# Filtre actuel sur d.ENV (databases env column) — À CHANGER
f"WHERE UPPER(d.{db_env_col}) = UPPER(:p_environment) "
f"AND UPPER(i.{inst_server_ref_col}) IN ({in_placeholders}) "
```

**Chemin `_read_databases_via_instances` (lignes 549–551) :**
```python
# Filtre actuel sur d.ENV (databases env column) — À CHANGER
if environment:
    db_env_col = mapper.get_column('databases', 'environment')
    inner_sql += f" AND UPPER(d.{db_env_col}) = UPPER(:p_environment)"
```

### Pattern de JOIN à implémenter

```python
# Variables à récupérer via le mapper :
srv_table = mapper.get_table_name('servers')            # ex: DBOPS_SERVERS
srv_name_col = mapper.get_column('servers', 'name')    # ex: HOSTNAME
srv_env_col = mapper.get_column('servers', 'environment')  # ex: ENV

# Pour instances → servers :
inst_server_ref_col = mapper.get_column('instances', 'server_ref')  # ex: SERVER_NAME

# JOIN : INNER JOIN {srv_table} srv ON UPPER(inst.{inst_server_ref_col}) = UPPER(srv.{srv_name_col})
# Filter : WHERE UPPER(srv.{srv_env_col}) = UPPER(:p_environment)
```

**Exemple de SQL généré (instances standard avec environment) :**
```sql
SELECT * FROM (
  SELECT inst.INSTANCE_ID AS id, inst.INSTANCE_NAME AS name, ...
  FROM DBOPS_INSTANCES inst
  INNER JOIN DBOPS_SERVERS srv ON UPPER(inst.SERVER_NAME) = UPPER(srv.HOSTNAME)
  WHERE UPPER(srv.ENV) = UPPER(:p_environment)
  ORDER BY name
) WHERE ROWNUM <= 10000
```

**Exemple de SQL généré (databases_multi_server avec environment) :**
```sql
SELECT * FROM (
  SELECT DISTINCT d.DB_ID AS id, d.DB_NAME AS name, ...
  FROM DBOPS_DATABASES d
  INNER JOIN DBOPS_INSTANCES i ON UPPER(i.DB_NAME) = UPPER(d.DB_NAME)
  INNER JOIN DBOPS_SERVERS srv ON UPPER(i.SERVER_NAME) = UPPER(srv.HOSTNAME)
  WHERE UPPER(srv.ENV) = UPPER(:p_environment)
  AND UPPER(i.SERVER_NAME) IN (:p_server_0, :p_server_1, ...)
  ORDER BY d.DB_NAME
) WHERE ROWNUM <= 10000
```

### Fallback gracieux

Si servers entity n'est pas configuré dans le mapper (rare, mais possible) :
- Pour instances : tomber dans le comportement actuel (filtre sur colonne locale si mappée)
- Logger un avertissement : `"environment_filter_fallback_to_local_column"`
- Ne pas lever d'exception

Condition de vérification :
```python
has_servers_config = mapper.get_entity_config('servers') is not None
if environment and has_servers_config:
    # JOIN servers approach
else:
    # Fallback : filtre local si colonne présente
```

### Considérations sécurité SQL

- Tous les identifiants (table/colonne) passent par `mapper.get_table_name()` et `mapper.get_column()` qui appellent `_validate_table_name()` / `_validate_column_name()` (regex + longueur Oracle 30 chars)
- Annoter chaque f-string SQL avec `# nosec B608 - table/columns validated by mapper`
- Les paramètres bind restent nommés (`:p_environment`, etc.) — pas de concaténation directe de valeurs

### Structure des tests

**Fichier de test recommandé :** `inventory/tests/test_inventory_multi_tables.py` (fichier existant, ajouter une classe `ReadInstancesEnvFromServersTests` et `ReadDatabasesEnvFromServersTests`)

**Pattern de test à suivre** (extrait de `ReadServersFromConfigTests`) :
```python
@patch('inventory.services.connection')
def test_read_instances_env_from_servers_join(self, mock_conn):
    """AC1: Environment filter uses JOIN instances → servers."""
    self._create_inventory_db(MULTI_TABLE_CONFIG)
    mock_cursor = MagicMock()
    mock_cursor.description = [...]
    mock_cursor.fetchall.return_value = [...]
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    results = self.service.read_instances(environment='dev')

    sql = mock_cursor.execute.call_args[0][0]
    params = mock_cursor.execute.call_args[0][1]

    # JOIN doit être présent
    self.assertIn('DBOPS_SERVERS', sql)
    self.assertIn('JOIN', sql.upper())
    # Filtre sur servers.ENV
    self.assertIn('srv.ENV', sql)
    # Pas de filtre sur instances.ENV (colonne locale)
    self.assertNotIn('UPPER(ENV)', sql.split('srv.ENV')[0])  # env col avant le srv.
    # Paramètre bind
    self.assertEqual(params['p_environment'], 'dev')
```

**Config de test à mettre à jour** — ajouter `server_ref` aux instances (déjà présent dans `MULTI_TABLE_CONFIG`) et s'assurer que `servers` a `environment` mappée.

### Project Structure Notes

- Fichiers modifiés : `inventory/query_executor.py` (méthodes `_read_entity_from_config`, `_read_entity_multi_server`, `_read_databases_multi_server`, `_read_databases_via_instances`)
- Tests : `inventory/tests/test_inventory_multi_tables.py` (nouvelles classes/méthodes)
- Optionnel : `inventory/mapper.py` (docstring config format)

**Aucune migration DB requise** — changement purement au niveau des requêtes SQL générées.

**Aucune modification d'API** — les endpoints, serializers et services ne changent pas. L'impact est interne au `InventoryQueryExecutor`.

### Compatibilité ascendante

- Les configs existantes avec colonne `environment` sur instances/databases **restent valides** — la colonne peut exister dans le mapper mais sera ignorée pour le filtre environment.
- Si `servers` entity n'a pas de colonne `environment` mappée → `MapperValidationError` levée via `get_column()`. Logger un warning et tomber sur fallback colonne locale pour éviter une régression.
- Story 37.2 (engine_type) pourra réutiliser la même jointure instances → servers, ce qui simplifie l'implémentation future.

### References

- `inventory/query_executor.py` lignes 259–382 (`_read_entity_from_config`), 384–434 (`_read_entity_multi_server`), 436–498 (`_read_databases_multi_server`), 500–566 (`_read_databases_via_instances`)
- `inventory/mapper.py` — `get_table_name()`, `get_column()`, `build_select_clause()`, `build_where_clause()`
- `inventory/tests/test_inventory_multi_tables.py` — patterns de test et `MULTI_TABLE_CONFIG` fixture
- `_bmad-output/planning-artifacts/epic-37-inventaire-environnement-serveur-colonne-engine.md` — Story 37.1
- `_bmad-output/planning-artifacts/spec-inventaire-environnement-serveur-colonne-engine.md` — §1 « Environnement dérivé du serveur »

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_Aucun blocage rencontré._

### Completion Notes List

- **Task 1+2** : `_read_entity_from_config` modifié — chemin instances et databases standard utilisent désormais JOIN vers `servers` pour le filtre environment. Fallback gracieux (warning + filtre local) si servers config absent.
- **Task 3** : `_read_entity_multi_server` modifié — chemin instances multi-serveurs remplace filtre local `instances.ENV` par JOIN `servers`. Alias `inst.` ajouté pour éviter ambiguïté.
- **Task 4** : `_read_databases_multi_server` modifié — JOIN `databases → instances → servers` remplace filtre `d.db_env_col`. Fallback si servers config absent.
- **Task 5** : `_read_databases_via_instances` modifié — JOIN `instances → servers` ajouté dans clause FROM lorsque environment fourni. Fallback local si servers absent.
- **Task 6** : 7 nouveaux tests ajoutés (6.1–6.6 + test_instances_env_with_server_name_cumulated). 3 tests existants mis à jour pour refléter le nouveau comportement.
- **Task 7** : Docstring `mapper.py` enrichie avec note sur le mode « env-from-server ».
- **Résultats** : 30/30 tests `test_inventory_multi_tables.py` passent. 347/347 tests inventaire passent. 1455 tests régression passent (0 régression).
- **Sécurité** : Toutes les f-strings SQL annotées `# nosec B608`, identifiants validés via mapper.
- **Compatibilité ascendante** : configs existantes avec colonne `environment` locale restent valides — colonne peut exister mais est ignorée pour le filtre environment en mode multi-table avec servers.

### Senior Developer Review (AI)

**Date :** 2026-02-23 | **Résultat :** Approuvé avec corrections auto-appliquées

**Résumé des findings et corrections :**

| # | Sévérité | Problème | Correction |
|---|----------|----------|------------|
| 1 | CRITIQUE | Bug double-préfixe `d.d.DB_NAME` dans `_read_databases_via_instances` — le bloc `replace(..., 1)` initial suivi du loop de remplacement produisait un SQL invalide (ORA-00904 en production), masqué par les tests qui ne vérifient pas la clause SELECT | Suppression du bloc `replace(..., 1)` initial ; utilisation du helper `_build_aliased_select` |
| 2 | HIGH | Aliasing via `str.replace` fragile dans 4 endroits — risque de corruption SQL si un nom de colonne est sous-string d'un autre | Extraction de la méthode statique `_build_aliased_select(entity_cfg, alias)` et remplacement dans les 4 localisations |
| 3 | HIGH | Code mort : blocs `else` dans `_read_entity_multi_server` et `_read_databases_multi_server` — `has_servers_config` est toujours `True` dans ces méthodes (chemin protégé par `is_multi_table`) | Suppression des blocs `else` et simplification des méthodes |
| 4 | MEDIUM | `except InventoryServiceError: raise InventoryServiceError(...)` re-wrappait en perdant le message d'erreur original | Remplacé par `raise` (propagation directe) |
| 5 | MEDIUM | Code mort : bloc fallback warning instances `_read_entity_from_config` lignes 372-379 | Supprimé (même analyse `has_servers_config` toujours True) |
| 6 | LOW | Tests ne vérifiaient pas la clause SELECT — bug double-préfixe invisible | 3 tests de régression ajoutés (`test_*_select_clause_no_double_prefix`) |

**Tests :** 33/33 passent (3 nouveaux tests de régression ajoutés)

### File List

- `idp-portal/django_backend/inventory/query_executor.py`
- `idp-portal/django_backend/inventory/mapper.py`
- `idp-portal/django_backend/inventory/tests/test_inventory_multi_tables.py`
