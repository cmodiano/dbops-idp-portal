# Baseline Schema V121 — IDP Portal

## Contexte

Ce dossier contient le script de **baseline** du schéma Oracle de l'IDP Portal. Il consolide les migrations Flyway V000–V129 en un seul script d'initialisation pour les **nouveaux environnements**.

| Fichier | Description |
|---------|-------------|
| `baseline_flyway.sql` | Script DDL+DML : tables, indexes, contraintes, trigger, package PKG_IDP_MAINTENANCE, données de référence (état V129) |
| `README.md` | Ce fichier — procédure de déploiement et validation |

> **⚠️ IMPORTANT** : Ce script s'applique **UNIQUEMENT** sur une base Oracle vierge.
> Les environnements existants (dev, staging, prod) sont **inchangés** — ils continuent d'utiliser la chaîne V000–V120 via Flyway normalement.

---

## Procédure de déploiement — Nouveaux environnements

### Étape 1 : Appliquer le script baseline via SQL\*Plus

```bash
# Connexion à la base vierge et exécution du script
sqlplus idp_user/password@NEW_ENV:1521/XEPDB1 @database/baseline/baseline_flyway.sql
```

> Le script crée les 40 tables (dont EXECUTIONS, EXECUTION_STEPS, AUDIT_LOG partitionnées, WORKFLOW_DEFINITIONS, WORKFLOW_STEPS, WORKFLOW_STEP_EDGES, et les tables Django auth/session/API), indexes, contraintes, le trigger d'immutabilité, le package PKG_IDP_MAINTENANCE et insère les données de référence (REF_ENGINES, REF_CATEGORIES).

### Étape 2 : Déclarer la base au niveau V121 (commande Flyway `baseline`)

```bash
flyway \
  -url=jdbc:oracle:thin:@NEW_ENV:1521/XEPDB1 \
  -user=idp_user \
  -password=password \
  -baselineVersion=129 \
  -baselineDescription=baseline_flyway \
  baseline
```

> Cette commande enregistre une ligne dans `flyway_schema_history` indiquant que la base est déjà au niveau V129 (success=true). Flyway ne re-jouera pas V000–V129. **Aucune migration incrémentale n'est nécessaire pour V000–V129.** Les migrations futures (V130 et au-delà) devront être appliquées via `flyway migrate`.

### Étape 3 : Vérifier le résultat

```bash
flyway \
  -url=jdbc:oracle:thin:@NEW_ENV:1521/XEPDB1 \
  -user=idp_user \
  -password=password \
  info
```

Le résultat attendu :

```text
+------------+---------+-------------------------------+--------+---------------------+----------+
| Category   | Version | Description                   | Type   | Installed On        | State    |
+------------+---------+-------------------------------+--------+---------------------+----------+
| Versioned  | 129     | baseline schema v088          | BASELN | ...                 | Baseline |
+------------+---------+-------------------------------+--------+---------------------+----------+
```

---

## Environnements existants — Aucune action requise

```bash
# Comportement normal — aucune modification
flyway migrate  # Applique uniquement les nouvelles migrations (V120+ futures)
```

Les environnements existants ont déjà V000–V120 (ou V121) dans `flyway_schema_history`. Ce script ne les affecte pas. Ils appliquent V121 via `flyway migrate`.

---

## Contenu de baseline_flyway.sql

### Convention timestamps (UTC)

Tous les colonnes `TIMESTAMP` avec valeur par défaut utilisent :
```sql
TO_TIMESTAMP(TO_CHAR(SYSTIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.FF6'), 'YYYY-MM-DD HH24:MI:SS.FF6')
```
Cela garantit un stockage en UTC quel que soit le timezone de la base ou de la session.

### Tables créées (40)

| Phase | Tables |
|-------|--------|
| Phase 1 — Sans FK entrantes | USERS, TAGS, PROFILES, INTEGRATIONS, REF_ENGINES, REF_CATEGORIES, INTEGRATION_TYPE_CATALOGUE, CORE_FEATURE_FLAGS, BUSINESS_RULE_POLICIES, OUTPUT_SCHEMAS, ACTIONS_CATALOG |
| Phase 2 — Dépendantes d'ACTIONS_CATALOG/USERS | ACTION_TAGS, USER_FAVORITES, ACTION_MUTEX, PROFILE_ACTION_PERMISSIONS, PROFILE_TARGET_PERMISSIONS, INTEGRATION_ACTIONS, AUDIT_LOG (partitionnée) |
| Phase 3 — Exécutions | EXECUTIONS (partitionnée), EXECUTION_STEPS (reference partitioned), EXECUTION_TARGETS, SCHEDULED_EXECUTIONS, RECURRING_PATTERNS |
| Phase 4 — Trigger | TRG_AUDIT_LOG_IMMUTABLE |
| Phase 4b — Maintenance | IDP_MAINTENANCE_LOG, PKG_IDP_MAINTENANCE |
| Phase 4c — V113–V129 | WORKFLOW_EVENTS, WORKFLOW_EVENT_COUNTER, RUNNABLE_STEPS (V123 leases), WORKFLOW_COMMANDS, EXECUTION_OUTBOX, WORKFLOW_DEFINITIONS, WORKFLOW_STEPS, WORKFLOW_STEP_EDGES |

### Données de référence insérées

| Table | Lignes | Source |
|-------|--------|--------|
| REF_ENGINES | 6 | V049 + V078 : Oracle, SQL Server, DB2, PostgreSQL, MySQL, Workflow |
| REF_CATEGORIES | 6 | V059 : provisioning, patching, administration, monitoring, backup, autres |
| INTEGRATION_TYPE_CATALOGUE | 0 | Gérées par l'application (fixtures Django) |
| INTEGRATION_ACTIONS | 0 | Gérées par l'application (fixtures Django) |

### Ajouts V112–V129 (inclus dans le baseline)

| Élément | Description |
|---------|-------------|
| `LAST_SYNCED_AT` + `LAST_SYNCED_HASH` sur 8 tables | IaC sync tracking |
| 8 optimized indexes (GLOBAL indexes sur EXECUTIONS, EXECUTION_STEPS, etc.) | Index optimisés |
| `WORKFLOW_EVENTS` table + 3 indexes | Event sourcing, purge 7 jours |
| `WORKFLOW_EVENT_COUNTER` table (V122) | Allocation séquence atomique |
| `RUNNABLE_STEPS` table + leases (V123: CLAIMED_UNTIL, ATTEMPT_NO, MAX_ATTEMPTS) | File d'attente avec reclaim |
| `WORKFLOW_COMMANDS` table (V124) | Command Store durable |
| `EXECUTION_OUTBOX` table (V125) | Transactional outbox |
| `WORKFLOW_DEFINITIONS`, `WORKFLOW_STEPS`, `WORKFLOW_STEP_EDGES` (V127–V129) | Définitions workflow normalisées |
| CONFIG_SYNC_* audit types, reference_data/tags entity types | IaC Config Sync |
| `OUTPUT_SCHEMA_ID` sur ACTIONS_CATALOG | Schéma d'output déclaré |
| `CONFIG_STEP_ID` sur EXECUTION_STEPS | Correspondance étape ↔ définition workflow |
| `REJECTED_BY`, `REJECTED_AT` sur EXECUTION_STEPS | Audit trail rejet gate |
| `CORRELATION_ID` sur EXECUTIONS + index | Traçage sur tout le cycle d'exécution |
| `UPDATED_AT` sur EXECUTIONS + IDX_EXECUTIONS_UPDATED_AT | Détection staleness (Epic 76) |

### Éléments exclus (neutralisés par les migrations)

| Élément | Raison |
|---------|--------|
| `SCHEMA_VERSION` | Créée V000, droppée V015 |
| `REF_PLATFORMS` | Créée V051, droppée V083 |
| Séquences legacy | Droppées V016 — colonnes IDENTITY suffisent |
| `ACTIONS_CATALOG.RBAC_POLICIES` | Colonne droppée V013 |
| `ACTIONS_CATALOG.CHANGE_MODEL_CODE` | Colonne droppée V019 |
| `ACTIONS_CATALOG.CHANGE_TYPE_CONFIG` | Colonne droppée V109 |
| `ACTIONS_CATALOG.GATE_CONFIG` | Colonne droppée V109 |
| `CK_ACTIONS_CATALOG_CATEGORY` | Contrainte droppée V018 |
| `CK_ACTIONS_CATALOG_ENGINE` | Contrainte droppée V050 |
| `CK_ACTIONS_CATALOG_PLATFORM` | Contrainte droppée V052 |
| `CHK_EXECUTION_ENV` | Contrainte droppée V053 — env dicté par inventaire |
| `CHK_SCHEDULED_ENV` | Contrainte droppée V053 |
| `CK_INTEGRATIONS_TYPE` | Contrainte droppée V024 (TYPE libre depuis V024) |
| `EXECUTION_LOG` | Table créée V006, droppée V121 |
| `USER_PERMISSIONS` | Table créée V005, droppée V121 |
| `IDX_EXECUTIONS_PENDING_APPROVAL` | Index créé V030, droppé V121 |

---

## Plan de validation — Procédure via Docker

Pour valider que le schéma produit par `baseline_flyway.sql` est identique à celui produit par la chaîne V000–V121 :

```bash
# 1. Démarrer deux instances Oracle Docker
docker-compose up oracle-a oracle-b

# 2. Sur oracle-a : appliquer la chaîne complète V000–V129
flyway -url=jdbc:oracle:thin:@oracle-a:1521/XEPDB1 migrate

# 3. Sur oracle-b : appliquer le baseline uniquement
sqlplus idp_user/password@oracle-b:1521/XEPDB1 @database/baseline/baseline_flyway.sql
flyway -url=jdbc:oracle:thin:@oracle-b:1521/XEPDB1 \
       -baselineVersion=129 \
       -baselineDescription=baseline_flyway \
       baseline

# 4. Exporter et comparer (script de diff DBMS_METADATA)
./scripts/export_schema.sh oracle-a > /tmp/schema-a.sql
./scripts/export_schema.sh oracle-b > /tmp/schema-b.sql
diff <(normalize.sh /tmp/schema-a.sql) <(normalize.sh /tmp/schema-b.sql)
# Résultat attendu : 0 différences structurelles (état V129)
```

---

## Checklist de validation manuelle (avant promotion)

| Vérification | Commande SQL | Critère de succès |
|--------------|-------------|-------------------|
| Nombre de tables | `SELECT COUNT(*) FROM user_tables` | 40 tables |
| Trigger immutabilité | `SELECT status FROM user_triggers WHERE trigger_name = 'TRG_AUDIT_LOG_IMMUTABLE'` | ENABLED |
| Données REF_ENGINES | `SELECT COUNT(*) FROM REF_ENGINES` | 6 lignes |
| Données REF_CATEGORIES | `SELECT COUNT(*) FROM REF_CATEGORIES` | 6 lignes |
| Colonnes ACTIONS_CATALOG | `SELECT column_name FROM user_tab_columns WHERE table_name = 'ACTIONS_CATALOG' ORDER BY column_id` | Vérifier absence de RBAC_POLICIES, CHANGE_MODEL_CODE ; présence de OUTPUT_SCHEMA_ID |
| Colonne CORRELATION_ID sur EXECUTIONS | `SELECT column_name FROM user_tab_columns WHERE table_name = 'EXECUTIONS' AND column_name = 'CORRELATION_ID'` | 1 ligne |
| Colonne UPDATED_AT sur EXECUTIONS | `SELECT column_name FROM user_tab_columns WHERE table_name = 'EXECUTIONS' AND column_name = 'UPDATED_AT'` | 1 ligne |
| Contraintes exclues | `SELECT constraint_name FROM user_constraints WHERE table_name = 'ACTIONS_CATALOG'` | Absence de CK_ACTIONS_CATALOG_CATEGORY, CK_ACTIONS_CATALOG_ENGINE, CK_ACTIONS_CATALOG_PLATFORM |
| Partitionnement | `SELECT table_name FROM user_part_tables WHERE table_name IN ('EXECUTIONS','EXECUTION_STEPS','AUDIT_LOG')` | 3 tables partitionnées |
| Package purge | `SELECT status FROM user_objects WHERE object_name = 'PKG_IDP_MAINTENANCE'` | VALID |
| WORKFLOW_EVENTS exists | `SELECT COUNT(*) FROM user_tables WHERE table_name = 'WORKFLOW_EVENTS'` | 1 |
| RUNNABLE_STEPS exists | `SELECT COUNT(*) FROM user_tables WHERE table_name = 'RUNNABLE_STEPS'` | 1 |
| WORKFLOW_DEFINITIONS exists | `SELECT COUNT(*) FROM user_tables WHERE table_name = 'WORKFLOW_DEFINITIONS'` | 1 |
| Historique Flyway | `SELECT version, state FROM flyway_schema_history ORDER BY installed_rank` | baseline V129 uniquement |

---

## Commandes de diagnostic Flyway

```bash
# Voir l'état complet des migrations
flyway -url=... info

# Réparer en cas d'échec partiel (corriger checksum ou état)
flyway -url=... repair

# Valider les checksums des migrations V084–V088
flyway -url=... validate
```

---

## Rollback post-déploiement (migrations V084–V087 uniquement)

Des scripts de rollback sont disponibles pour les partitionnements :

```text
database/rollback/
  V084__partition_executions_rollback.sql
  V085__partition_execution_steps_rollback.sql
  V086__partition_audit_log_rollback.sql
  V087__create_purge_procedure_rollback.sql
```

> **⚠️ Attention** : Le rollback des partitionnements est destructif (DROP TABLE). Toujours sauvegarder avant rollback sur un environnement non-vierge.

---

*Référence : `docs/backend/migration/migration-audit-epic41.md`*
