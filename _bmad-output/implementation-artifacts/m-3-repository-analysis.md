# Analyse des Repositories FastAPI - Story M.3

**Date:** 2026-02-03  
**Objectif:** Documenter toutes les opérations des repositories FastAPI pour migration vers Django ORM

## 1. catalog_repository.py (~1839 lignes)

### Fonctions principales

#### CRUD Actions
- `create(action: ActionCreate, user_id: int) -> ActionResponse`
  - INSERT avec RETURNING ID (identity column)
  - Gestion CLOB: parameters_schema, impact_rules
  - Status par défaut: DRAFT
  - Support item_type (action/workflow)

- `get_by_id(action_id: int) -> ActionDetail | None`
  - SELECT avec 17 colonnes (après V031)
  - JOIN TAGS via ACTION_TAGS pour récupérer tags
  - Parse CLOB: execution_steps, change_type_config, remediation_rules
  - Support workflows (workflow_steps vs execution_steps)

- `list_all(status, tags_filter, item_type) -> list[ActionResponse]`
  - SELECT avec filtres dynamiques
  - Batch query pour tags (get_tags_for_actions)
  - Tri: CREATED_AT DESC

- `list_catalog(status, tags_filter, action_ids_filter, q, engine, environment, impact, item_type_filter) -> list[dict]`
  - SELECT avec EXECUTION_COUNT (sous-requête)
  - Recherche texte (LIKE sur NAME, DESCRIPTION, tags)
  - Filtre JSON: JSON_EXISTS pour environment
  - Tri: NAME ASC

- `update_action(action_id, action_update, user_id) -> ActionDetail | None`
  - UPDATE metadata (name, description, engine, platform, etc.)
  - Audit: ACTION_UPDATED
  - Pas de restriction de statut

- `update_execution_steps(action_id, steps, change_type_config) -> ActionDetail | None`
  - UPDATE EXECUTION_STEPS et CHANGE_TYPE_CONFIG
  - Restriction: STATUS='draft' uniquement
  - Validation race condition

- `update_status(action_id, transition, user_id) -> ActionDetail | None`
  - UPDATE STATUS avec validation transition
  - Audit: ACTION_PUBLISHED/DISABLED/ENABLED
  - Validation race condition (WHERE STATUS = current_status)

- `update_workflow_steps(workflow_id, steps) -> ActionDetail | None`
  - UPDATE EXECUTION_STEPS pour workflows
  - Validation: item_type='workflow', STATUS='draft'
  - Validation loops et références

#### Gestion Tags
- `get_all_tags() -> list[TagResponse]`
  - SELECT TAGS ORDER BY NAME

- `get_tags_for_action(action_id) -> list[str]`
  - JOIN ACTION_TAGS + TAGS

- `get_tags_for_actions(action_ids) -> dict[int, list[str]]`
  - Batch query pour éviter N+1

- `list_tags_with_counts(action_ids_filter) -> list[dict]`
  - GROUP BY avec COUNT
  - Filtre par action_ids (RBAC)

- `create_tag_if_not_exists(name) -> int`
  - INSERT avec gestion race condition (IntegrityError)

- `set_action_tags(action_id, tag_ids) -> None`
  - DELETE + INSERT multiples (transaction)

#### Requêtes complexes
- `list_all_admin(status, engine, item_type, page, page_size) -> tuple[list, PaginationInfo]`
  - Pagination OFFSET/FETCH
  - COUNT total pour pagination
  - EXECUTION_COUNT via sous-requête

- `validate_workflow_steps(workflow_id, steps) -> None`
  - Validation références actions
  - Détection loops récursive

- `get_requires_approval(action_id, environment) -> bool`
  - Parse impact_rules JSON
  - Logique: PROD + (critical OR high)

- `get_actions_with_remediation_rules() -> list[ActionDetail]`
  - WHERE REMEDIATION_RULES IS NOT NULL

### Opérations CRUD identifiées
- ✅ CREATE: create()
- ✅ READ: get_by_id(), list_all(), list_catalog(), list_all_admin()
- ✅ UPDATE: update_action(), update_execution_steps(), update_status(), update_workflow_steps(), update_remediation_rules()
- ❌ DELETE: Pas de fonction delete (soft delete via status)

### Requêtes avec JOINs
- JOIN ACTION_TAGS + TAGS (many-to-many)
- Sous-requête EXECUTION_COUNT (EXECUTION_LOG)
- JOIN ACTIONS_CATALOG pour validation workflows

### Transactions
- set_action_tags: DELETE + INSERT multiples dans même transaction
- create: INSERT + audit (pas de transaction explicite)

### Patterns de cache
- Aucun cache identifié dans repository

---

## 2. profile_repository.py (~240 lignes)

### Fonctions principales

#### CRUD Profiles
- `create(data: ProfileCreate) -> ProfileResponse`
  - INSERT avec RETURNING ID
  - Gestion IntegrityError (unicité nom)

- `get_by_id(profile_id: int) -> ProfileResponse | None`
  - SELECT simple

- `get_by_name(name: str) -> ProfileResponse | None`
  - SELECT WHERE NAME

- `get_all() -> list[ProfileListItem]`
  - SELECT + comptage permissions (appel autres repositories)
  - Batch queries: get_actions_permissions_for_profile_ids, get_target_permissions_for_profile_ids

- `find_by_ad_groups(ad_groups: list[str]) -> list[ProfileResponse]`
  - SELECT WHERE AD_GROUP IN (...)
  - Oracle IN clause avec placeholders multiples

- `update(profile_id, data) -> ProfileResponse | None`
  - UPDATE avec merge non-None fields
  - Gestion IntegrityError

- `delete(profile_id) -> bool`
  - DELETE simple

### Opérations CRUD identifiées
- ✅ CREATE: create()
- ✅ READ: get_by_id(), get_by_name(), get_all(), find_by_ad_groups()
- ✅ UPDATE: update()
- ✅ DELETE: delete()

### Requêtes avec JOINs
- Aucun JOIN direct
- Appels batch vers profile_action_permission_repository et profile_target_permission_repository

### Transactions
- Pas de transaction explicite

### Patterns de cache
- Aucun cache identifié

---

## 3. profile_action_permission_repository.py (~146 lignes)

### Fonctions principales

#### CRUD Permissions Actions
- `get_actions_permissions(profile_id) -> ProfileActionPermissionsResponse | None`
  - SELECT PROFILE_ACTION_PERMISSIONS
  - Parse CLOB JSON: action_ids_json, tag_patterns_json, environments_json

- `get_actions_permissions_for_profile_ids(profile_ids) -> dict[int, ProfileActionPermissionsResponse]`
  - Batch query avec IN clause
  - Retourne dict pour éviter N+1

- `set_actions_permissions(profile_id, payload) -> ProfileActionPermissionsResponse`
  - MERGE INTO (UPSERT)
  - Sérialisation JSON pour CLOB

### Opérations CRUD identifiées
- ✅ READ: get_actions_permissions(), get_actions_permissions_for_profile_ids()
- ✅ UPSERT: set_actions_permissions()
- ❌ DELETE: Pas de fonction delete explicite (suppression en cascade?)

### Requêtes avec JOINs
- Aucun JOIN

### Transactions
- MERGE INTO est atomique

### Patterns de cache
- Aucun cache identifié

---

## 4. profile_target_permission_repository.py (~165 lignes)

### Fonctions principales

#### CRUD Permissions Targets
- `get_target_permissions(profile_id) -> ProfileTargetPermissionsResponse | None`
  - SELECT PROFILE_TARGET_PERMISSIONS
  - Parse CLOB JSON: target_names_json, target_patterns_json

- `get_target_permissions_for_profile_ids(profile_ids) -> dict[int, ProfileTargetPermissionsResponse]`
  - Batch query avec IN clause

- `set_target_permissions(profile_id, payload) -> ProfileTargetPermissionsResponse`
  - MERGE INTO (UPSERT)

- `match_targets(user_permissions, available_targets) -> list[str]`
  - Fonction Python pure (pas de SQL)
  - Cumul permissions multi-profils
  - Pattern matching avec fnmatch

### Opérations CRUD identifiées
- ✅ READ: get_target_permissions(), get_target_permissions_for_profile_ids()
- ✅ UPSERT: set_target_permissions()
- ❌ DELETE: Pas de fonction delete explicite

### Requêtes avec JOINs
- Aucun JOIN

### Transactions
- MERGE INTO est atomique

### Patterns de cache
- Aucun cache identifié

---

## 5. integration_repository.py (~450 lignes)

### Fonctions principales

#### CRUD Integrations
- `create(integration: IntegrationCreate) -> IntegrationResponse`
  - INSERT avec RETURNING ID
  - Gestion CLOB: config (JSON)
  - Gestion IntegrityError (unicité nom)

- `get_by_id(integration_id) -> IntegrationResponse | None`
  - SELECT simple
  - Parse CLOB config

- `get_by_name(name) -> IntegrationResponse | None`
  - SELECT WHERE NAME

- `get_all() -> list[IntegrationResponse]`
  - SELECT ORDER BY NAME

- `get_by_type(integration_type) -> IntegrationResponse | None`
  - SELECT WHERE TYPE
  - FETCH FIRST 1 ROW ONLY

- `update(integration_id, integration) -> IntegrationResponse | None`
  - UPDATE dynamique (champs fournis)
  - Gestion IntegrityError

- `delete(integration_id) -> bool`
  - DELETE simple

### Opérations CRUD identifiées
- ✅ CREATE: create()
- ✅ READ: get_by_id(), get_by_name(), get_all(), get_by_type()
- ✅ UPDATE: update()
- ✅ DELETE: delete()

### Requêtes avec JOINs
- Aucun JOIN

### Transactions
- Pas de transaction explicite

### Patterns de cache
- Aucun cache identifié

---

## 6. user_repository.py (~125 lignes)

### Fonctions principales

#### CRUD Users
- `create_or_update(username, display_name, profile, saml_subject) -> dict`
  - MERGE INTO (UPSERT sur username)
  - Retourne dict (pas de modèle Pydantic)

- `get_by_username(username) -> dict | None`
  - SELECT WHERE USERNAME

- `get_by_id(user_id) -> dict | None`
  - SELECT WHERE ID

- `get_user_permissions(user_id) -> list[dict]`
  - SELECT USER_PERMISSIONS
  - Note: Table USER_PERMISSIONS semble obsolète (RBAC via profiles)

- `has_permission(user_id, action_id, environment) -> bool`
  - SELECT 1 FROM USER_PERMISSIONS
  - Note: Probablement obsolète

### Opérations CRUD identifiées
- ✅ UPSERT: create_or_update()
- ✅ READ: get_by_username(), get_by_id(), get_user_permissions(), has_permission()
- ❌ UPDATE: Pas de fonction update séparée (via create_or_update)
- ❌ DELETE: Pas de fonction delete

### Requêtes avec JOINs
- Aucun JOIN

### Transactions
- MERGE INTO est atomique

### Patterns de cache
- Aucun cache identifié

---

## 7. favorites_repository.py (~140 lignes)

### Fonctions principales

#### CRUD Favorites
- `list_favorites(user_id) -> list[dict]`
  - SELECT USER_FAVORITES ORDER BY CREATED_AT DESC

- `add_favorite(user_id, action_id) -> None`
  - MERGE INTO (idempotent)

- `remove_favorite(user_id, action_id) -> bool`
  - DELETE

- `is_favorite(user_id, action_id) -> bool`
  - SELECT 1 EXISTS

- `list_recent_actions(user_id, limit) -> list[dict]`
  - JOIN EXECUTION_LOG + ACTIONS_CATALOG
  - GROUP BY + MAX(STARTED_AT)
  - FETCH FIRST N ROWS

### Opérations CRUD identifiées
- ✅ READ: list_favorites(), is_favorite(), list_recent_actions()
- ✅ CREATE: add_favorite()
- ✅ DELETE: remove_favorite()

### Requêtes avec JOINs
- JOIN EXECUTION_LOG + ACTIONS_CATALOG (list_recent_actions)

### Transactions
- MERGE INTO est atomique

### Patterns de cache
- Aucun cache identifié

---

## 8. execution_repository.py (~3275 lignes)

### Fonctions principales (53 fonctions identifiées)

#### CRUD Executions
- `create_execution(user_id, action_id, environment, parameters, parent_execution_id) -> ExecutionCreateResponse`
  - INSERT avec RETURNING ID
  - Gestion CLOB: parameters
  - Support parent_execution_id (remediation)

- `get_by_id(execution_id) -> ExecutionResponse | None`
  - SELECT avec JOIN ACTIONS_CATALOG + USERS
  - Enrichissement: action_name, user_display_name
  - Support approval fields (Story 7.4)
  - Support remediation (parent_execution_id)
  - Support metadata (engine, platform, item_type, integration)

- `list_by_user(user_id, status, environment, action_id, date_range, limit, offset) -> list[ExecutionResponse]`
  - SELECT avec filtres dynamiques
  - JOIN ACTIONS_CATALOG + USERS
  - Pagination OFFSET/FETCH

- `list_all_executions(status, user_id, action_id, environment, date_range, limit, offset) -> list[ExecutionResponse]`
  - Même logique que list_by_user mais sans filtre user_id obligatoire

- `update_status(execution_id, new_status) -> ExecutionResponse | None`
  - UPDATE STATUS
  - Validation transitions

#### CRUD Execution Steps
- `create_execution_steps(execution_id, steps) -> list[ExecutionStepResponse]`
  - INSERT multiples dans transaction
  - Gestion CLOB: output

- `get_steps_by_execution_id(execution_id) -> list[ExecutionStepResponse]`
  - SELECT WHERE EXECUTION_ID ORDER BY ORDER

- `get_step_by_id(step_id) -> ExecutionStepResponse | None`
  - SELECT WHERE ID

- `update_step_status(step_id, status, output) -> ExecutionStepResponse | None`
  - UPDATE STATUS + OUTPUT

- `skip_remaining_steps(execution_id) -> int`
  - UPDATE STATUS='skipped' WHERE ORDER > current_order

#### Requêtes complexes
- `get_dashboard_stats(user_id, days) -> dict`
  - Agrégations: COUNT, SUM, AVG
  - GROUP BY STATUS, ENVIRONMENT
  - Sous-requêtes pour success_rate

- `list_recent_executions(limit) -> list[dict]`
  - SELECT avec JOIN
  - ORDER BY CREATED_AT DESC
  - FETCH FIRST N ROWS

- `get_dashboard_timeseries(user_id, days, interval) -> list[dict]`
  - Agrégations temporelles
  - GROUP BY date_trunc équivalent Oracle

- `get_action_stats(action_id) -> dict`
  - Agrégations par action
  - Sous-requêtes multiples

- `get_admin_analytics(days) -> dict`
  - Agrégations globales
  - Multiples sous-requêtes

- `get_stats_by_technology(days, environment) -> list[dict]`
  - JOIN ACTIONS_CATALOG pour ENGINE
  - GROUP BY ENGINE

- `get_stats_by_environment(days) -> list[dict]`
  - GROUP BY ENVIRONMENT

- `get_filter_options() -> dict`
  - DISTINCT queries pour filtres UI

- `get_execution_stats(user_id, days, filters) -> dict`
  - Agrégations avec filtres dynamiques

- `get_execution_timeseries(user_id, days, interval, filters) -> list[dict]`
  - Agrégations temporelles avec filtres

- `get_available_tags(user_id) -> list[str]`
  - JOIN EXECUTIONS + ACTIONS_CATALOG + ACTION_TAGS + TAGS
  - DISTINCT tags pour user

#### Approval Workflow (Story 7.4)
- `create_execution_pending_approval(...) -> ExecutionCreateResponse`
  - INSERT avec STATUS='pending_approval'

- `approve(execution_id, approved_by, comment) -> ExecutionResponse | None`
  - UPDATE STATUS + approval fields

- `reject(execution_id, rejected_by, comment) -> ExecutionResponse | None`
  - UPDATE STATUS='rejected'

- `list_pending_approvals(user_id, limit, offset) -> list[ExecutionResponse]`
  - SELECT WHERE STATUS='pending_approval'

- `count_pending_approvals() -> int`
  - COUNT WHERE STATUS='pending_approval'

### Opérations CRUD identifiées
- ✅ CREATE: create_execution(), create_execution_steps(), create_execution_pending_approval()
- ✅ READ: get_by_id(), list_by_user(), list_all_executions(), get_steps_by_execution_id(), get_step_by_id(), list_recent_executions(), list_pending_approvals()
- ✅ UPDATE: update_status(), update_step_status(), approve(), reject(), skip_remaining_steps()
- ❌ DELETE: Pas de fonction delete

### Requêtes avec JOINs
- JOIN ACTIONS_CATALOG (action_name, engine, platform, item_type)
- JOIN USERS (user_display_name)
- JOIN INTEGRATIONS (integration metadata)
- JOIN EXECUTION_LOG (pour list_recent_actions)
- JOIN ACTION_TAGS + TAGS (pour get_available_tags)

### Transactions
- create_execution_steps: INSERT multiples dans transaction atomique
- create_execution + create_steps: Devrait être atomique mais pas explicitement géré

### Patterns de cache
- Aucun cache identifié dans repository

---

## 9. scheduled_execution_repository.py (~935 lignes)

### Fonctions principales

#### CRUD Scheduled Executions
- `create_scheduled_execution(user_id, action_id, environment, parameters, scheduled_at, correlation_id, recurring_pattern) -> ScheduledExecutionCreateResult`
  - INSERT SCHEDULED_EXECUTIONS avec RETURNING ID
  - INSERT RECURRING_PATTERNS si recurring_pattern fourni
  - Transaction atomique pour les deux INSERTs

- `get_by_id(scheduled_execution_id) -> ScheduledExecutionWithAction | None`
  - SELECT avec JOIN ACTIONS_CATALOG
  - Enrichissement: action_name, action_description

- `list_scheduled_executions(user_id, status, action_id, scheduled_from, scheduled_to, limit, offset) -> list[ScheduledExecutionListItem]`
  - SELECT avec JOIN ACTIONS_CATALOG + USERS + LEFT JOIN RECURRING_PATTERNS
  - Filtres dynamiques
  - Pagination OFFSET/FETCH
  - Tri: COALESCE(scheduled_at, next_execution_date) ASC

- `count_scheduled_executions(...) -> int`
  - COUNT avec mêmes filtres

- `update_status(scheduled_execution_id, new_status) -> bool`
  - UPDATE STATUS

- `update_scheduled_execution_status_with_execution_id(scheduled_execution_id, new_status, execution_id) -> bool`
  - UPDATE STATUS + EXECUTION_ID

#### Recurring Patterns
- `get_recurring_pattern(scheduled_execution_id) -> RecurringPatternResponse | None`
  - SELECT RECURRING_PATTERNS
  - Parse CLOB: pattern_config

- `update_recurring_pattern_next_execution(scheduled_execution_id, new_next_execution_date) -> bool`
  - UPDATE NEXT_EXECUTION_DATE

- `update_recurring_pattern_status(scheduled_execution_id, is_active, new_next_execution_date) -> RecurringPatternResponse | None`
  - UPDATE IS_ACTIVE + optionnellement NEXT_EXECUTION_DATE

#### External Scheduler API (Story 11.10)
- `list_pending_executions(before, limit, offset) -> list`
  - SELECT avec JOINs
  - Filtre: STATUS='pending' AND (scheduled_at <= before OR next_execution_date <= before)
  - Tri: COALESCE(scheduled_at, next_execution_date) ASC

- `count_pending_executions(before) -> int`
  - COUNT avec mêmes filtres

### Opérations CRUD identifiées
- ✅ CREATE: create_scheduled_execution()
- ✅ READ: get_by_id(), list_scheduled_executions(), count_scheduled_executions(), get_recurring_pattern(), list_pending_executions(), count_pending_executions()
- ✅ UPDATE: update_status(), update_scheduled_execution_status_with_execution_id(), update_recurring_pattern_next_execution(), update_recurring_pattern_status()
- ❌ DELETE: Pas de fonction delete explicite (soft delete via status?)

### Requêtes avec JOINs
- JOIN ACTIONS_CATALOG (action metadata)
- JOIN USERS (user_name)
- LEFT JOIN RECURRING_PATTERNS (pour recurring patterns)

### Transactions
- create_scheduled_execution: INSERT SCHEDULED_EXECUTIONS + INSERT RECURRING_PATTERNS dans transaction atomique

### Patterns de cache
- Aucun cache identifié

---

## 10. audit_repository.py (~583 lignes)

### Fonctions principales

#### CRUD Audit Log
- `create_entry(user_id, action_type, entity_type, entity_id, details, ip_address, correlation_id) -> int`
  - INSERT AUDIT_LOG avec RETURNING ID
  - Gestion CLOB: details (JSON)
  - Append-only (pas de UPDATE/DELETE)

- `list_entries(entity_type, entity_id, action_type, limit, offset) -> list[dict]`
  - SELECT avec filtres dynamiques
  - Pagination OFFSET/FETCH
  - Parse CLOB details

- `get_by_entity(entity_type, entity_id) -> list[dict]`
  - Wrapper autour de list_entries

- `list_execution_audit_entries(from_date, to_date, user_id, environment, action_id, status, sort_field, sort_order, limit, offset) -> list[dict]`
  - SELECT avec ROW_NUMBER pour latest entry per execution
  - Filtres JSON: JSON_VALUE pour environment, action_id
  - Tri dynamique

- `count_execution_audit_entries(...) -> int`
  - COUNT DISTINCT ENTITY_ID avec mêmes filtres

- `log_remediation(parent_execution_id, child_execution_id, user_id, action_id, parent_action_id, parent_action_name, child_action_name, environment, error_context, ip_address, correlation_id) -> int`
  - Wrapper autour de create_entry avec action_type=REMEDIATION_EXECUTION_CREATED

### Opérations CRUD identifiées
- ✅ CREATE: create_entry(), log_remediation()
- ✅ READ: list_entries(), get_by_entity(), list_execution_audit_entries(), count_execution_audit_entries()
- ❌ UPDATE: Pas de fonction update (append-only)
- ❌ DELETE: Pas de fonction delete (append-only)

### Requêtes avec JOINs
- Aucun JOIN direct
- Utilise ROW_NUMBER pour latest entry per execution

### Transactions
- Pas de transaction explicite (INSERT simple)

### Patterns de cache
- Aucun cache identifié

---

## Résumé des opérations par type

### Opérations CRUD standards
- **CREATE**: Tous repositories sauf audit (append-only)
- **READ**: Tous repositories
- **UPDATE**: Tous repositories sauf audit
- **DELETE**: catalog (soft delete), profile, integration, favorites; pas pour execution, scheduled_execution, audit

### Requêtes avec JOINs complexes
1. **catalog_repository**: JOIN ACTION_TAGS + TAGS (many-to-many)
2. **execution_repository**: JOIN ACTIONS_CATALOG + USERS + INTEGRATIONS + ACTION_TAGS + TAGS
3. **scheduled_execution_repository**: JOIN ACTIONS_CATALOG + USERS + LEFT JOIN RECURRING_PATTERNS
4. **favorites_repository**: JOIN EXECUTION_LOG + ACTIONS_CATALOG

### Transactions multi-tables
1. **catalog_repository**: set_action_tags (DELETE + INSERT multiples)
2. **execution_repository**: create_execution_steps (INSERT multiples)
3. **scheduled_execution_repository**: create_scheduled_execution + create_recurring_pattern

### Gestion CLOB/JSON
Tous repositories gèrent des champs CLOB JSON:
- **catalog**: parameters_schema, impact_rules, execution_steps, change_type_config, remediation_rules, workflow_steps
- **profile_action_permission**: action_ids_json, tag_patterns_json, environments_json
- **profile_target_permission**: target_names_json, target_patterns_json
- **integration**: config
- **execution**: parameters, output (steps)
- **scheduled_execution**: parameters, pattern_config
- **audit**: details

### Patterns de cache
- **Aucun cache identifié** dans les repositories (cache probablement dans services ou middleware)

### Opérations métier complexes
1. **catalog**: Validation transitions statut, validation workflows (loops), recherche multi-tags
2. **profile**: Cumul permissions multi-profils, résolution AD groups
3. **execution**: Agrégations statistiques, timeseries, filtres dynamiques complexes
4. **scheduled_execution**: Calcul next_execution_date pour recurring patterns
5. **audit**: Dérivation status depuis action_type, filtres JSON complexes

---

## Prochaines étapes (Task 2+)

1. Créer Managers Django pour chaque modèle
2. Créer Services Django pour logique métier complexe
3. Implémenter équivalents Django ORM pour chaque fonction
4. Réécrire tests unitaires
5. Valider parité fonctionnelle
