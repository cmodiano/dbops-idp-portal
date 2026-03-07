# Comparatif schémas BD (Oracle) — `idp-portal` vs `dbops`

## Périmètre & sources

- **Périmètre**: schéma relationnel **+ logique DB** (vues, MViews, packages PL/SQL, jobs DBMS_SCHEDULER).
- **Sources `idp-portal`**: migrations Flyway dans `/Users/cyrille/Documents/Dev/test/idp-portal/database/migrations/`.
- **Sources `dbops`**: schéma consolidé `/Users/cyrille/Documents/Dev/dbops/dbops-operations/db/migration/V1.0.0__create_complete_schema.sql` + packages repeatables `R__pkg_*.sql`.

> Lecture rapide: `idp-portal` modélise un **portail de “catalogue d’actions”** et ses **exécutions**. `dbops` modélise un **moteur d’opérations** orienté **requests multi-cibles**, **chaînes**, **stratégies**, **RBAC rôles/clients**, et **observabilité/maintenance** côté BD.

## Résumé exécutif (diff fonctionnel)

- **`idp-portal` a**: une modélisation “produit portail” (actions, tags, favoris, documentation, intégrations d’exécution, exécutions et steps, audit orienté action/exécution, remédiation au niveau action).
- **`dbops` a**: une modélisation “moteur ops” (requests multi-cibles, targeting générique + registre de types, chaînes multi-étapes, stratégies de déploiement, scheduling complet avec historique, RBAC rôles + clients API + permissions par cible, partitionnement + MViews + rétention).
- **Écart central**: `idp-portal` n’a pas (dans le schéma) de **notion first-class de “cible”** (targets) ni de **requests multi-cibles**; `dbops` n’a pas (dans le schéma) de **catalogue orienté UX** (tags/favoris/docs) ni de **modèle d’étapes d’exécution détaillées** type `EXECUTION_STEPS` (il logge au fil de l’eau via `operation_log`).

## Points communs (capabilities similaires, mais implémentations différentes)

### Catalogue
- **`idp-portal`**: `ACTIONS_CATALOG` (métadonnées + paramètres JSON schema + statut draft/published/disabled, notion `ITEM_TYPE` action/workflow).
- **`dbops`**: `operation` (catalogue d’opérations + flags d’exigences, retry/backoff, dispatch_mode, restrictions d’environnements).

### Exécution / traçabilité
- **`idp-portal`**: `EXECUTIONS` + `EXECUTION_STEPS` + audit `AUDIT_LOG` (types d’événements action/exécution).
- **`dbops`**: `operation_request` + `operation_log` (logs), plus packages `pkg_requests`/`pkg_validation` pour orchestrer l’état.

### Scheduling
- **`idp-portal`**: `SCHEDULED_EXECUTIONS` + `RECURRING_PATTERNS` (prochaine exécution via `NEXT_EXECUTION_DATE`), modèle volontairement “léger” pour un scheduler externe.
- **`dbops`**: `scheduled_operation*` + `scheduled_operation_history` + package `pkg_scheduler` (génération de requests) + `maintenance_window`.

### RBAC
- **`idp-portal`**: profils dynamiques + permissions stockées en JSON (`PROFILES`, `PROFILE_ACTION_PERMISSIONS`, `PROFILE_TARGET_PERMISSIONS`) et table `USER_PERMISSIONS` (user/action/env).
- **`dbops`**: rôles + permissions par pattern (`role`, `role_permission`), mapping AD (`ad_group_role`), clients API (`api_client`, `api_client_target_permission`), package `pkg_security` + `pkg_apex_security`.

## Uniquement (ou surtout) dans `idp-portal`

### UX / “portail”
- **Tags**: `TAGS`, `ACTION_TAGS` pour classification flexible.
- **Favoris**: `USER_FAVORITES` (user ↔ action).
- **Documentation**: `ACTIONS_CATALOG.DOCUMENTATION_MD` (Markdown par action).

### Modèle d’exécution “step-by-step”
- `EXECUTION_STEPS`: étapes typées (`vault`, `servicenow`, `platform`, `prerequisite`, `verification`) avec `PLATFORM_JOB_ID`, output, erreurs.
- `EXECUTIONS`: statut détaillé (`SUBMITTED`, `PENDING_APPROVAL`, `RUNNING`, etc.), lien ServiceNow (`SERVICENOW_CHANGE_ID`), approbation (`APPROVED_BY`, `APPROVED_AT`, `APPROVAL_COMMENT`).

### Intégrations d’exécution (config métier)
- `INTEGRATIONS`: `BASE_URL`, `CREDENTIAL_REF`, `ICON`, `AUTH_FLOW`, `TOKEN_URL`, `CONFIG` (JSON de flow d’auth et appels).
- Lien direct action→intégration: `ACTIONS_CATALOG.INTEGRATION_ID`.

### Remédiation orientée “actions”
- Règles au niveau action: `ACTIONS_CATALOG.REMEDIATION_RULES` (JSON).
- Liens d’exécutions: `EXECUTIONS.PARENT_EXECUTION_ID`.
- Audit dédié: types `REMEDIATION_*` et `AUTO_REMEDIATION_*` dans `AUDIT_LOG`.

## Uniquement (ou surtout) dans `dbops`

### “Requests” robustes (queue + exécution asynchrone)
- **Objet pivot**: `operation_request` (statuts, retry/backoff, scheduling_mode, erreurs, next_retry_at, intégrations externes change/blackout/orchestrator, champs de dispatch).
- **Logs structurants**: `operation_log` (partitionné par référence).
- **API DB**: `pkg_requests` expose create/update/status/log/stats.

### Modèle multi-cibles + résolution générique
- `operation_request_target` et `scheduled_operation_target`: cibles génériques (`target_type`, `target_id`) + metadata optionnelle.
- `target_type_registry`: mapping `target_type` → tables inventaire (synonymes) + colonnes (id/name/env/tech) + `validate_exists`.
- **Synonymes inventaire**: `servers`, `instances`, `db`, `pdb`, etc. (délégation à un schéma inventory).

### Chaînes multi-étapes
- `operation_chain`, `operation_chain_step`, `operation_chain_execution` + package `pkg_chains`.
- Permet “N étapes” avec dépendances (`depends_on_request_id`) et orchestration d’avancement.

### Stratégies de déploiement / topologies
- `deployment_strategy`, `operation_strategy_mapping` + package `pkg_strategies`.
- Support natif: parallèle/sériel/rolling, batch size/%, validations, rollback, ordre d’exécution (JSON).

### Scheduling complet + historique
- `scheduled_operation`, `scheduled_operation_history` + `pkg_scheduler.generate_scheduled_requests`.
- `maintenance_window` et validations `pkg_validation` (fenêtres, env allowed, mutex, dépendances, compat techno).

### Sécurité “plateforme”
- RBAC patterns via `role_permission`, niveaux d’accès (READONLY/USER/ADMIN).
- **Clients API** (machines) + permissions fines par cible: `api_client_target_permission`.
- **Audit API**: `api_audit_log` (authz granted/denied + raisons).
- Helpers APEX (session items) via `pkg_apex_security`.

### Observabilité & exploitation BD
- **Partitionnement** (ex: `operation_request` par mois) pour volumétrie.
- **Materialized views** KPI (`mv_ops_dashboard_kpis`, `mv_ops_requests_daily_status`).
- **Rétention / maintenance**: `pkg_maintenance.purge_old_data`, logs `ops_maintenance_log`, compteurs, jobs DBMS_SCHEDULER.

## Impacts (ce que ça veut dire “fonctionnellement”)

### Si `idp-portal` veut “rattraper” `dbops`
Il manque principalement:
- **Targeting first-class** (targets normalisés, multi-cibles, registre de types + résolution inventaire).
- **Requests** plus riches (retry/backoff, mutex/dépendances, scheduling mode & history).
- **Chaînes / stratégies** (rolling, DataGuard/RAC, etc.) si le besoin est un moteur ops complet.
- **RBAC machine-to-machine** (clients API) + audit authz.
- **Rétention/partitionnement/MViews** si volumétrie élevée côté exécutions/logs.

### Si `dbops` veut “rattraper” `idp-portal`
Il manque principalement:
- Métadonnées UX: **tags**, **favoris**, **documentation**.
- Modèle d’exécution “steps” typés (ou équivalent) si on veut une traçabilité UI fine au niveau étape.
- Gestion d’“intégrations d’exécution” orientée produit (auth flows configurables, icônes, etc.) — aujourd’hui `dbops` référence plutôt un orchestrateur et l’inventaire.

## Annexes — inventaire d’objets (raccourci)

### `idp-portal` (tables principales)
`USERS`, `PROFILES`, `PROFILE_ACTION_PERMISSIONS`, `PROFILE_TARGET_PERMISSIONS`, `USER_PERMISSIONS`,  
`ACTIONS_CATALOG`, `INTEGRATIONS`, `TAGS`, `ACTION_TAGS`, `USER_FAVORITES`,  
`EXECUTIONS`, `EXECUTION_STEPS`, `EXECUTION_LOG`, `AUDIT_LOG`,  
`SCHEDULED_EXECUTIONS`, `RECURRING_PATTERNS`.

### `dbops` (tables/vues/packages principales)
- Tables: `operation`, `operation_parameter`, `operation_dependency`, `operation_environment_override`,  
  `operation_request`, `operation_request_target`, `operation_log`,  
  `operation_chain*`, `deployment_strategy`, `operation_strategy_mapping`,  
  `scheduled_operation*`, `maintenance_window`,  
  `role*`, `api_client*`, `ad_group_role`, `api_audit_log`,  
  `ops_maintenance_log`, `ops_maintenance_counter`, `target_type_registry` (+ synonymes inventaire).
- Vues/MViews: `v_executable_operation`, `v_chain_only_operation`, `mv_ops_dashboard_kpis`, `mv_ops_requests_daily_status`.
- Packages: `pkg_requests`, `pkg_validation`, `pkg_scheduler`, `pkg_chains`, `pkg_strategies`, `pkg_security`, `pkg_apex_security`, `pkg_orchestrator`, `pkg_maintenance`.

