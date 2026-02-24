# Story 37.2 : Filtre engine_type pour instances et databases (backend)

Status: done

## Story

En tant qu'utilisateur du portail,
je veux que les API inventaire **instances** et **databases** acceptent un paramètre optionnel `engine_type`,
afin de ne recevoir que des instances/bases dont le serveur est de la technologie indiquée (ex. Oracle, SQL Server).

## Acceptance Criteria

1. **Given** l'endpoint GET `/api/v1/inventory/instances/`
   **When** le client envoie `environment=dev&engine_type=oracle`
   **Then** le backend accepte le paramètre `engine_type` (validation serializer)
   **And** le service appelle le query executor avec `engine_type='oracle'`
   **And** la requête joint **instances → servers** (si pas déjà fait pour environment) et ajoute un filtre sur **servers.engine_type** (colonne mappée)
   **And** seules les instances dont le serveur est de type oracle sont retournées

2. **Given** l'endpoint GET `/api/v1/inventory/databases/`
   **When** le client envoie `environment=dev&engine_type=oracle` (avec ou sans server_names)
   **Then** le backend accepte le paramètre `engine_type`
   **And** la requête (chemin « databases seules » ou « via instances / multi-server ») joint **servers** (via instances) et filtre sur **servers.engine_type**
   **And** seules les databases liées à des instances sur des serveurs oracle sont retournées

3. **Given** `engine_type` est absent dans la requête
   **Then** aucun filtre sur engine_type n'est appliqué (comportement actuel)
   **And** pas de régression sur les appels existants

4. **Given** une valeur `engine_type` non reconnue ou vide
   **Then** le backend l'ignore (ne retourne pas 400) — comportement aligné avec servers (simple CharField pass-through)
   **And** si la colonne `engine_type` n'est pas mappée dans la config servers, un warning est loggué et le filtre est ignoré gracieusement (pas d'exception)

## Tasks / Subtasks

- [x] Task 1 : Sérializers — ajouter `engine_type` (AC: #1, #2, #3)
  - [x] 1.1 `InstanceFilterParamsSerializer` : ajouter `engine_type = serializers.CharField(required=False, max_length=20, help_text="Filter by engine type")`
  - [x] 1.2 `DatabaseFilterParamsSerializer` : idem
  - [x] 1.3 Pas de validation enum — pass-through comme `ServerFilterParamsSerializer` existant

- [x] Task 2 : Views — extraire et propager engine_type (AC: #1, #2)
  - [x] 2.1 `list_instances` : `engine_type = params.get('engine_type')` puis passer `engine_type=engine_type` à `inventory_service.list_instances(...)`
  - [x] 2.2 `list_databases` : idem pour `list_databases`
  - [x] 2.3 Mettre à jour les `@extend_schema` parameters pour ajouter `OpenApiParameter('engine_type', str, required=False, description="Filter by engine type")` aux deux endpoints
  - [x] 2.4 Logger `engine_type` dans les log structlog des deux views (cohérence avec `list_servers`)

- [x] Task 3 : Services — propager engine_type (AC: #1, #2)
  - [x] 3.1 `list_instances` : ajouter `engine_type: str | None = None` et passer à `self.query_executor.read_instances(environment, engine_type=engine_type, ...)`
  - [x] 3.2 `list_databases` : idem
  - [x] 3.3 `_read_instances_from_config` (backward compat) : ajouter `engine_type: str | None = None` et passer à `read_instances`
  - [x] 3.4 `_read_databases_from_config` (backward compat) : idem

- [x] Task 4 : QueryExecutor — public methods (AC: #1, #2, #3)
  - [x] 4.1 `read_instances` : ajouter `engine_type: str | None = None`, passer à `_read_entity_from_config`
  - [x] 4.2 `read_databases` : idem

- [x] Task 5 : QueryExecutor — `_read_entity_from_config` — chemin instances (AC: #1, #3, #4)
  - [x] 5.1 Refactoriser le bloc 37.1 `if entity_type == 'instance' and environment and has_servers_config:` en `if entity_type == 'instance' and (environment or engine_type) and has_servers_config:`
  - [x] 5.2 Construire les conditions WHERE en liste (`inst_conditions: list[str]`, `inst_params: dict`) au lieu de strings fixes
  - [x] 5.3 Si `engine_type` : récupérer `srv_engine_col = mapper.get_column('servers', 'engine_type')` (dans un try/except MapperValidationError → warning + skip si non mappée) et ajouter la condition
  - [x] 5.4 Construire la clause WHERE finale : `"WHERE " + " AND ".join(inst_conditions)` (vide si aucune condition)
  - [x] 5.5 Annoter `# nosec B608` sur la f-string ajoutée

- [x] Task 6 : QueryExecutor — `_read_entity_from_config` — chemin databases standard (AC: #2, #3, #4)
  - [x] 6.1 Refactoriser le bloc 37.1 `if entity_type == 'database' and environment and has_servers_config and has_instances_config:` en `if entity_type == 'database' and (environment or engine_type) and has_servers_config and has_instances_config:`
  - [x] 6.2 Même approche liste de conditions pour WHERE : `db_conditions = []; db_params = {}`
  - [x] 6.3 Si `engine_type` : récupérer `srv_engine_col` avec try/except et ajouter la condition
  - [x] 6.4 Construire WHERE finale en joinant les conditions

- [x] Task 7 : QueryExecutor — `_read_entity_multi_server` (chemin instances multi-serveurs) (AC: #1, #3)
  - [x] 7.1 Ajouter `engine_type: str | None = None` à la signature
  - [x] 7.2 Mettre à jour l'appel depuis `_read_entity_from_config` pour passer `engine_type`
  - [x] 7.3 Après la condition `AND UPPER(inst.{server_ref_col}) IN ({in_placeholders})` : si engine_type, récupérer `srv_engine_col` (try/except) et ajouter `AND UPPER(srv.{srv_engine_col}) = UPPER(:p_engine_type)`, et `params['p_engine_type'] = engine_type`

- [x] Task 8 : QueryExecutor — `_read_databases_multi_server` (AC: #2, #3)
  - [x] 8.1 Ajouter `engine_type: str | None = None` à la signature
  - [x] 8.2 Mettre à jour l'appel depuis `_read_entity_multi_server`
  - [x] 8.3 Si engine_type : récupérer `srv_engine_col` (try/except), ajouter condition `AND UPPER(srv.{srv_engine_col}) = UPPER(:p_engine_type)`, `params['p_engine_type'] = engine_type`

- [x] Task 9 : QueryExecutor — `_read_databases_via_instances` (AC: #2, #3)
  - [x] 9.1 Ajouter `engine_type: str | None = None` à la signature
  - [x] 9.2 Mettre à jour l'appel depuis `_read_entity_from_config` (ligne 332)
  - [x] 9.3 Quand `environment` est fourni et `has_servers_config` : la jointure vers servers existe déjà → ajouter la condition engine_type si présent
  - [x] 9.4 Quand `environment` est absent mais `engine_type` est fourni et `has_servers_config` : ajouter la jointure vers servers + filtre engine_type (nouveau sous-cas)
  - [x] 9.5 Dans le cas sans environment et sans engine_type : comportement inchangé

- [x] Task 10 : Tests (AC: #1–#4)
  - [x] 10.1 `test_list_instances_engine_type_accepted` — View : engine_type dans query_params → 200, engine_type propagé au service
  - [x] 10.2 `test_read_instances_engine_type_join_servers` — query_executor : SQL contient JOIN servers + filtre srv.ENGINE, pas de filtre engine direct sur instances
  - [x] 10.3 `test_read_instances_engine_type_and_environment_combined` — les deux filtres dans le même JOIN
  - [x] 10.4 `test_read_instances_multi_server_engine_type` — chemin multi-server avec engine_type
  - [x] 10.5 `test_read_databases_engine_type_join_servers` — chemin standard databases
  - [x] 10.6 `test_read_databases_multi_server_engine_type` — chemin multi-server databases
  - [x] 10.7 `test_read_databases_via_instances_engine_type` — chemin via instances
  - [x] 10.8 `test_no_engine_type_no_filter` — absence de engine_type → aucune condition engine dans SQL (régression AC3)
  - [x] 10.9 `test_engine_type_not_mapped_warning_skipped` — colonne engine_type absente du config servers → warning loggué, pas d'exception, résultat non filtré par engine

## Dev Notes

### Contexte et dépendances

Story 37.2 s'appuie directement sur Story 37.1 (déjà done) :
- La jointure `instances → servers` pour le filtre `environment` est **déjà en place** dans toutes les méthodes du query_executor
- Story 37.2 **réutilise la même jointure** — il faut juste ajouter un filtre supplémentaire sur `servers.engine_type`
- La structure JOIN est prête ; c'est essentiellement une extension non destructive

### Analyse du code actuel post-37.1

**`_read_entity_from_config` — chemin instances (lignes ~347–382) :**
```python
# Condition actuelle (37.1) — à élargir
if entity_type == 'instance' and environment and has_servers_config:
    srv_table = mapper.get_table_name('servers')
    srv_name_col = mapper.get_column('servers', 'name')
    srv_env_col = mapper.get_column('servers', 'environment')
    inst_server_ref_col = mapper.get_column(entity_plural, 'server_ref')
    entity_cfg = mapper.get_entity_config(entity_plural) or {}
    aliased_select = self._build_aliased_select(entity_cfg, 'inst')

    inst_params: dict[str, Any] = {'p_environment': environment}
    inst_inner = (
        f"SELECT {aliased_select} "
        f"FROM {table} inst "
        f"INNER JOIN {srv_table} srv "
        f"ON UPPER(inst.{inst_server_ref_col}) = UPPER(srv.{srv_name_col}) "
        f"WHERE UPPER(srv.{srv_env_col}) = UPPER(:p_environment)"
    )
    if server_name:
        inst_inner += f" AND UPPER(inst.{inst_server_ref_col}) = UPPER(:p_server_ref)"
        inst_params['p_server_ref'] = server_name
    inst_inner += " ORDER BY name"
```

**Transformation Story 37.2 — pattern conditions list :**
```python
# Nouvelle condition : environment OU engine_type (au moins un des deux)
if entity_type == 'instance' and (environment or engine_type) and has_servers_config:
    srv_table = mapper.get_table_name('servers')
    srv_name_col = mapper.get_column('servers', 'name')
    inst_server_ref_col = mapper.get_column(entity_plural, 'server_ref')
    entity_cfg = mapper.get_entity_config(entity_plural) or {}
    aliased_select = self._build_aliased_select(entity_cfg, 'inst')

    inst_conditions: list[str] = []
    inst_params: dict[str, Any] = {}

    if environment:
        srv_env_col = mapper.get_column('servers', 'environment')
        inst_conditions.append(f"UPPER(srv.{srv_env_col}) = UPPER(:p_environment)")  # nosec B608
        inst_params['p_environment'] = environment

    if engine_type:
        try:
            srv_engine_col = mapper.get_column('servers', 'engine_type')
            inst_conditions.append(f"UPPER(srv.{srv_engine_col}) = UPPER(:p_engine_type)")  # nosec B608
            inst_params['p_engine_type'] = engine_type
        except MapperValidationError:
            logger.warning(
                "engine_type_not_mapped_in_servers",
                entity=entity_plural,
                engine_type=engine_type,
                correlation_id=correlation_id,
            )

    if server_name:
        inst_conditions.append(f"UPPER(inst.{inst_server_ref_col}) = UPPER(:p_server_ref)")  # nosec B608
        inst_params['p_server_ref'] = server_name

    where_str = ("WHERE " + " AND ".join(inst_conditions)) if inst_conditions else ""

    inst_inner = (
        f"SELECT {aliased_select} "  # nosec B608
        f"FROM {table} inst "  # nosec B608
        f"INNER JOIN {srv_table} srv "  # nosec B608
        f"ON UPPER(inst.{inst_server_ref_col}) = UPPER(srv.{srv_name_col}) "  # nosec B608
        f"{where_str} ORDER BY name"
    )
    inst_sql = f"SELECT * FROM ({inst_inner}) WHERE ROWNUM <= {MAX_MULTI_TABLE_RESULTS}"  # nosec B608
    ...
    return self.execute_mapped_query(inst_sql, inst_params)
```

**Même pattern pour le bloc databases standard (37.1 lignes ~388–421).**

**`_read_entity_multi_server` — ajout engine_type (lignes ~535–541) :**
```python
# Après la condition AND UPPER(inst.{server_ref_col}) IN (...) :
if engine_type:
    try:
        srv_engine_col = mapper.get_column('servers', 'engine_type')
        inner_sql += f" AND UPPER(srv.{srv_engine_col}) = UPPER(:p_engine_type)"  # nosec B608
        params['p_engine_type'] = engine_type
    except MapperValidationError:
        logger.warning("engine_type_not_mapped_in_servers", entity=entity_plural, ...)
```

**`_read_databases_multi_server` — même pattern (lignes ~605–610).**

**`_read_databases_via_instances` — cas environment + engine_type :**
```python
# Dans le bloc if environment and has_servers_config (existe déjà pour 37.1) :
# Ajouter après le WHERE srv.env = :p_environment si engine_type présent :
if engine_type:
    try:
        srv_engine_col = mapper.get_column('servers', 'engine_type')
        inner_sql += f" AND UPPER(srv.{srv_engine_col}) = UPPER(:p_engine_type)"  # nosec B608
        params['p_engine_type'] = engine_type
    except MapperValidationError:
        logger.warning(...)

# Cas engine_type sans environment (nouveau sous-cas) :
elif engine_type and has_servers_config:
    # Ajouter la jointure servers + filtre engine_type
    try:
        srv_engine_col = mapper.get_column('servers', 'engine_type')
        srv_table = mapper.get_table_name('servers')
        srv_name_col = mapper.get_column('servers', 'name')
        inner_sql = (
            inner_sql_base +
            f"INNER JOIN {srv_table} srv "  # nosec B608
            f"ON UPPER(i.{inst_server_ref_col}) = UPPER(srv.{srv_name_col}) "  # nosec B608
            f"WHERE UPPER(i.{inst_server_ref_col}) = UPPER(:p_server_name) "  # nosec B608
            f"AND UPPER(srv.{srv_engine_col}) = UPPER(:p_engine_type)"  # nosec B608
        )
        params['p_engine_type'] = engine_type
    except MapperValidationError:
        logger.warning(...)
        inner_sql = inner_sql_base + f"WHERE UPPER(i.{inst_server_ref_col}) = UPPER(:p_server_name)"
else:
    inner_sql = inner_sql_base + f"WHERE UPPER(i.{inst_server_ref_col}) = UPPER(:p_server_name)"
```

### Règle de comportement engine_type invalide

Conformément à l'AC4 et au modèle existant `ServerFilterParamsSerializer` :
- **Pas de validation enum** — le serializer accepte toute chaîne max 20 chars
- La valeur est passée telle quelle au SQL comme bind parameter UPPER comparison
- Si aucun serveur n'a cette valeur : résultat vide (comportement naturel)
- Si colonne `engine_type` absente du config servers : **warning** + filtre ignoré (résultats non filtrés par engine)

### SQL généré — exemples attendus

**Instances avec environment + engine_type :**
```sql
SELECT * FROM (
  SELECT inst.INSTANCE_ID AS id, inst.INSTANCE_NAME AS name, ...
  FROM DBOPS_INSTANCES inst
  INNER JOIN DBOPS_SERVERS srv ON UPPER(inst.SERVER_NAME) = UPPER(srv.HOSTNAME)
  WHERE UPPER(srv.ENV) = UPPER(:p_environment)
  AND UPPER(srv.ENGINE) = UPPER(:p_engine_type)
  ORDER BY name
) WHERE ROWNUM <= 10000
```

**Instances avec engine_type seul (sans environment) :**
```sql
SELECT * FROM (
  SELECT inst.INSTANCE_ID AS id, inst.INSTANCE_NAME AS name, ...
  FROM DBOPS_INSTANCES inst
  INNER JOIN DBOPS_SERVERS srv ON UPPER(inst.SERVER_NAME) = UPPER(srv.HOSTNAME)
  WHERE UPPER(srv.ENGINE) = UPPER(:p_engine_type)
  ORDER BY name
) WHERE ROWNUM <= 10000
```

**Databases multi-server avec engine_type :**
```sql
SELECT * FROM (
  SELECT DISTINCT d.DB_ID AS id, d.DB_NAME AS name, ...
  FROM DBOPS_DATABASES d
  INNER JOIN DBOPS_INSTANCES i ON UPPER(i.DB_NAME) = UPPER(d.DB_NAME)
  INNER JOIN DBOPS_SERVERS srv ON UPPER(i.SERVER_NAME) = UPPER(srv.HOSTNAME)
  WHERE UPPER(srv.ENV) = UPPER(:p_environment)
  AND UPPER(i.SERVER_NAME) IN (:p_server_0, :p_server_1, ...)
  AND UPPER(srv.ENGINE) = UPPER(:p_engine_type)
  ORDER BY d.DB_NAME
) WHERE ROWNUM <= 10000
```

### Structure des tests

**Fichier :** `inventory/tests/test_inventory_multi_tables.py` (existant — ajouter de nouvelles classes)

**Config de test :** `MULTI_TABLE_CONFIG` existante (serveurs avec `engine_type` mappé sur `"ENGINE"`)

**Pattern de test à suivre** (identique à 37.1) :
```python
class EngineTypeFilterInstancesTests(TestCase):
    """Story 37.2: engine_type filter for instances via servers JOIN."""

    def setUp(self):
        self.service = InventoryService()

    def _create_inventory_db(self, config):
        return Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config=json.dumps(config),
        )

    @patch('inventory.services.connection')
    def test_read_instances_engine_type_join_servers(self, mock_conn):
        """AC1: engine_type filter uses JOIN instances → servers."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)
        mock_cursor = MagicMock()
        mock_cursor.description = [('ID',), ('NAME',), ('ENVIRONMENT',), ('SERVER_REF',), ('DB_REF',)]
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        self.service.list_instances(environment='dev', engine_type='oracle')

        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]

        # JOIN servers doit être présent
        self.assertIn('DBOPS_SERVERS', sql)
        self.assertIn('JOIN', sql.upper())
        # Filtre sur srv.ENGINE (colonne engine_type de servers dans MULTI_TABLE_CONFIG)
        self.assertIn('srv.ENGINE', sql)
        # Pas de filtre engine_type direct sur instances
        self.assertNotIn('inst.ENGINE', sql)
        # Paramètre bind engine_type
        self.assertEqual(params['p_engine_type'], 'oracle')
        self.assertEqual(params['p_environment'], 'dev')
```

**Test régression AC3 :**
```python
@patch('inventory.services.connection')
def test_no_engine_type_no_filter(self, mock_conn):
    """AC3: absence de engine_type → aucune condition engine dans SQL."""
    ...
    self.service.list_instances(environment='dev')
    sql = mock_cursor.execute.call_args[0][0]
    self.assertNotIn('p_engine_type', sql)
    self.assertNotIn('ENGINE', sql.split('HOSTNAME')[1] if 'HOSTNAME' in sql else sql)
    # Ou plus simple :
    self.assertNotIn(':p_engine_type', sql)
```

**Test engine_type non mappé (AC4) :**
```python
@patch('inventory.services.connection')
def test_engine_type_not_mapped_logs_warning(self, mock_conn):
    """AC4: colonne engine_type absente du config servers → warning, pas d'exception."""
    config_without_engine = {
        "entities": {
            "servers": {
                "table": "DBOPS_SERVERS",
                "id_column": "SERVER_ID",
                "columns": {"name": "HOSTNAME", "environment": "ENV"},
                # engine_type absent intentionnellement
            },
            "instances": { ... },
        }
    }
    self._create_inventory_db(config_without_engine)
    ...
    # Ne doit pas lever d'exception
    result = self.service.list_instances(environment='dev', engine_type='oracle')
    # Filtre engine_type ignoré → SQL sans condition engine
    sql = mock_cursor.execute.call_args[0][0]
    self.assertNotIn(':p_engine_type', sql)
```

### Project Structure Notes

**Fichiers à modifier :**
- `inventory/serializers.py` (tâches 1.1–1.3) — `InstanceFilterParamsSerializer`, `DatabaseFilterParamsSerializer`
- `inventory/views.py` (tâches 2.1–2.4) — `list_instances`, `list_databases`
- `inventory/services.py` (tâches 3.1–3.4) — `list_instances`, `list_databases`, backward compat
- `inventory/query_executor.py` (tâches 4–9) — méthodes multiples

**Fichier de test :**
- `inventory/tests/test_inventory_multi_tables.py` (tâche 10) — nouvelles classes

**Aucune migration DB requise** — changement purement au niveau des serializers, views, services et requêtes SQL générées.

**Aucune modification de URLs requise** — les routes existantes `/api/v1/inventory/instances/` et `/api/v1/inventory/databases/` sont inchangées.

### Compatibilité ascendante

- Les appels existants sans `engine_type` continuent à fonctionner exactement comme avant (AC3)
- Les backward compat methods de services.py (`_read_instances_from_config`, `_read_databases_from_config`) doivent avoir `engine_type` avec valeur par défaut `None` pour ne pas casser les tests existants qui les appellent directement
- Le paramètre `engine_type` dans `read_instances` et `read_databases` (query_executor) est optionnel avec défaut `None`

### Sécurité SQL

- `engine_type` est passé comme **bind parameter** (`:p_engine_type`) — **jamais** concaténé directement dans le SQL
- La colonne `srv_engine_col` est obtenue via `mapper.get_column('servers', 'engine_type')` qui valide le nom de colonne (regex + longueur Oracle 30 chars) — annoter `# nosec B608`
- Annoter chaque nouvelle f-string SQL avec `# nosec B608 - column validated by mapper, value as bind param`

### References

- `inventory/query_executor.py` lignes 276–487 (`_read_entity_from_config`), 489–555 (`_read_entity_multi_server`), 557–624 (`_read_databases_multi_server`), 626–712 (`_read_databases_via_instances`), 768–788 (`read_instances`), 790–810 (`read_databases`)
- `inventory/serializers.py` — `InstanceFilterParamsSerializer` (lignes 121–146), `DatabaseFilterParamsSerializer` (lignes 149–174), `ServerFilterParamsSerializer` (lignes 107–119) comme modèle pour engine_type
- `inventory/views.py` — `list_servers` (lignes 385–448) comme modèle pour engine_type dans la view
- `inventory/services.py` — `list_instances` (lignes 291–378), `list_databases` (lignes 380–467), `list_servers` (lignes 218–289) comme modèle
- `inventory/tests/test_inventory_multi_tables.py` — `MULTI_TABLE_CONFIG` fixture, `ReadServersFromConfigTests`, `ReadInstancesEnvFromServersTests` (pattern 37.1)
- `_bmad-output/implementation-artifacts/37-1-deriver-environnement-depuis-table-servers.md` — story précédente avec patterns JOIN établis
- `_bmad-output/planning-artifacts/epic-37-inventaire-environnement-serveur-colonne-engine.md` — Story 37.2 AC complets
- `_bmad-output/planning-artifacts/spec-inventaire-environnement-serveur-colonne-engine.md` — §3 « Utilisation de engine_type dans les filtres inventaire »

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Toutes les tâches 1–10 implémentées et testées (362 tests inventory passent, 0 régression).
- `engine_type` propagé de la couche View → Service → QueryExecutor via le pattern existant `ServerFilterParamsSerializer`.
- `_read_entity_from_config` instances et databases : conditions WHERE refactorisées en liste pour combiner `environment` et `engine_type`.
- Méthodes `_read_entity_multi_server`, `_read_databases_multi_server`, `_read_databases_via_instances` étendues avec `engine_type`.
- Gestion AC4 : `MapperValidationError` lors du `mapper.get_column('servers', 'engine_type')` → warning structlog + filtre ignoré gracieusement.
- Tests existants corrigés (`engine_type=None` ajouté aux assertions `assert_called_once_with`).

### Senior Developer Review (AI) — 2026-02-23

**Résultat : APPROUVÉ avec corrections appliquées**

**Problèmes corrigés :**

- **[MEDIUM] M1 — `_read_entity_multi_server` / `_read_databases_multi_server` : environment toujours dans WHERE même vide** : La clause WHERE incluait inconditionnellement `UPPER(srv.ENV) = UPPER(:p_environment)` même quand `environment=""` (passé via `environment or ""`), ce qui retournait 0 résultats au lieu de ne pas filtrer. Corrigé : `environment` est maintenant conditionnel dans la liste des conditions WHERE, cohérent avec le chemin single-entity. (`query_executor.py`)
- **[MEDIUM] M2 — Tests manquants pour `engine_type` dans `InstanceFilterParamsSerializer` et `DatabaseFilterParamsSerializer`** : 4 tests ajoutés couvrant validation réussie et max_length. (`tests/test_views_multi_tables.py`)
- **[LOW] L1 — Variable `db_select` inutilisée** : Supprimée de `_read_databases_via_instances`. (`query_executor.py`)
- **[LOW] L2 — `help_text` incohérent sur `engine_type`** : Instance et Database serializers alignés sur le modèle Server. (`serializers.py`)

**Problèmes non corrigés :**

- **[MEDIUM] M3 — 3 fichiers frontend modifiés non documentés** : `useExecutionsData.ts`, `useExecutionsData.test.ts`, `executionsColumns.tsx` sont des modifications en attente de la story 36.3, non liées à cette story. Ces fichiers NE font PAS partie de la story 37.2.

**Résultat des tests après corrections : 104 passent, 0 échec.**

### File List

- `inventory/serializers.py`
- `inventory/views.py`
- `inventory/services.py`
- `inventory/query_executor.py`
- `inventory/tests/test_inventory_multi_tables.py`
- `inventory/tests/test_views_multi_tables.py`
- `inventory/tests/test_integration_multi_tables.py`
