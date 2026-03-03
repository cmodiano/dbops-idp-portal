# Baseline Schema V098 — IDP Portal

## Contexte (Epic 41 — Consolidation des migrations BD)

Ce dossier contient le script de **baseline** du schéma Oracle de l'IDP Portal. Il consolide les 99 migrations Flyway V000–V098 en un seul script d'initialisation pour les **nouveaux environnements**.

| Fichier | Description |
|---------|-------------|
| `baseline_schema_v088.sql` | Script DDL+DML : 25 tables, indexes, contraintes, trigger, package PKG_IDP_MAINTENANCE, données de référence |
| `README.md` | Ce fichier — procédure de déploiement et validation |

> **⚠️ IMPORTANT** : Ce script s'applique **UNIQUEMENT** sur une base Oracle vierge.
> Les environnements existants (dev, staging, prod) sont **inchangés** — ils continuent d'utiliser la chaîne V000–V098 via Flyway normalement.

---

## Procédure de déploiement — Nouveaux environnements

### Étape 1 : Appliquer le script baseline via SQL\*Plus

```bash
# Connexion à la base vierge et exécution du script
sqlplus idp_user/password@NEW_ENV:1521/XEPDB1 @database/baseline/baseline_schema_v088.sql
```

> Le script crée les 25 tables (dont EXECUTIONS, EXECUTION_STEPS, AUDIT_LOG partitionnées), indexes, contraintes, le trigger d'immutabilité, le package PKG_IDP_MAINTENANCE et insère les données de référence (REF_ENGINES, REF_CATEGORIES).

### Étape 2 : Déclarer la base au niveau V088 (commande Flyway `baseline`)

```bash
flyway \
  -url=jdbc:oracle:thin:@NEW_ENV:1521/XEPDB1 \
  -user=idp_user \
  -password=password \
  -baselineVersion=100 \
  -baselineDescription=baseline_schema_v088 \
  baseline
```

> Cette commande enregistre une ligne dans `flyway_schema_history` indiquant que la base est déjà au niveau V098 (success=true). Flyway ne re-jouera pas V000–V098. **Aucune migration incrémentale n'est nécessaire pour V000–V098.** Les migrations futures (V099 et au-delà) devront toutefois être appliquées via `flyway migrate` lorsqu'elles seront disponibles — ne pas les ignorer.

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
| Versioned  | 98      | baseline schema v088          | BASELN | ...                 | Baseline |
+------------+---------+-------------------------------+--------+---------------------+----------+
```

---

## Environnements existants — Aucune action requise

```bash
# Comportement normal — aucune modification
flyway migrate  # Applique uniquement les nouvelles migrations (V098+ futures)
```

Les environnements existants ont déjà V000–V098 dans `flyway_schema_history`. Ce script ne les affecte pas.

---

## Contenu de baseline_schema_v088.sql

### Tables créées (25)

| Phase | Tables |
|-------|--------|
| Phase 1 — Sans FK entrantes | USERS, TAGS, PROFILES, INTEGRATIONS, REF_ENGINES, REF_CATEGORIES, INTEGRATION_TYPE_CATALOGUE, CORE_FEATURE_FLAGS, BUSINESS_RULE_POLICIES, ACTIONS_CATALOG |
| Phase 2 — Dépendantes d'ACTIONS_CATALOG/USERS | EXECUTION_LOG, USER_PERMISSIONS, ACTION_TAGS, USER_FAVORITES, ACTION_MUTEX, PROFILE_ACTION_PERMISSIONS, PROFILE_TARGET_PERMISSIONS, INTEGRATION_ACTIONS, AUDIT_LOG (partitionnée) |
| Phase 3 — Exécutions | EXECUTIONS (partitionnée), EXECUTION_STEPS (reference partitioned), EXECUTION_TARGETS, SCHEDULED_EXECUTIONS, RECURRING_PATTERNS |
| Phase 4 — Trigger | TRG_AUDIT_LOG_IMMUTABLE |
| Phase 4b — Maintenance | IDP_MAINTENANCE_LOG, PKG_IDP_MAINTENANCE |

### Données de référence insérées

| Table | Lignes | Source |
|-------|--------|--------|
| REF_ENGINES | 6 | V049 + V078 : Oracle, SQL Server, DB2, PostgreSQL, MySQL, Workflow |
| REF_CATEGORIES | 6 | V059 : provisioning, patching, administration, monitoring, backup, autres |
| INTEGRATION_TYPE_CATALOGUE | 0 | Gérées par l'application (fixtures Django) |
| INTEGRATION_ACTIONS | 0 | Gérées par l'application (fixtures Django) |

### Éléments exclus (neutralisés par les migrations V000–V088)

| Élément | Raison |
|---------|--------|
| `SCHEMA_VERSION` | Créée V000, droppée V015 |
| `REF_PLATFORMS` | Créée V051, droppée V083 |
| Séquences legacy | Droppées V016 — colonnes IDENTITY suffisent |
| `ACTIONS_CATALOG.RBAC_POLICIES` | Colonne droppée V013 |
| `ACTIONS_CATALOG.CHANGE_MODEL_CODE` | Colonne droppée V019 |
| `CK_ACTIONS_CATALOG_CATEGORY` | Contrainte droppée V018 |
| `CK_ACTIONS_CATALOG_ENGINE` | Contrainte droppée V050 |
| `CK_ACTIONS_CATALOG_PLATFORM` | Contrainte droppée V052 |
| `CHK_EXECUTION_ENV` | Contrainte droppée V053 — env dicté par inventaire |
| `CHK_SCHEDULED_ENV` | Contrainte droppée V053 |
| `CK_INTEGRATIONS_TYPE` | Contrainte droppée V024 (TYPE libre depuis V024) |

---

## Plan de validation — Procédure via Docker

Pour valider que le schéma produit par `baseline_schema_v088.sql` est identique à celui produit par V000–V098 :

```bash
# 1. Démarrer deux instances Oracle Docker
docker-compose up oracle-a oracle-b

# 2. Sur oracle-a : appliquer la chaîne complète V000–V098
flyway -url=jdbc:oracle:thin:@oracle-a:1521/XEPDB1 migrate

# 3. Sur oracle-b : appliquer le baseline uniquement
sqlplus idp_user/password@oracle-b:1521/XEPDB1 @database/baseline/baseline_schema_v088.sql
flyway -url=jdbc:oracle:thin:@oracle-b:1521/XEPDB1 \
       -baselineVersion=100 \
       -baselineDescription=baseline_schema_v088 \
       baseline

# 4. Exporter et comparer (script de diff DBMS_METADATA)
./scripts/export_schema.sh oracle-a > /tmp/schema-a.sql
./scripts/export_schema.sh oracle-b > /tmp/schema-b.sql
diff <(normalize.sh /tmp/schema-a.sql) <(normalize.sh /tmp/schema-b.sql)
# Résultat attendu : 0 différences structurelles
```

---

## Checklist de validation manuelle (avant promotion)

| Vérification | Commande SQL | Critère de succès |
|--------------|-------------|-------------------|
| Nombre de tables | `SELECT COUNT(*) FROM user_tables` | 25 tables |
| Trigger immutabilité | `SELECT status FROM user_triggers WHERE trigger_name = 'TRG_AUDIT_LOG_IMMUTABLE'` | ENABLED |
| Données REF_ENGINES | `SELECT COUNT(*) FROM REF_ENGINES` | 6 lignes |
| Données REF_CATEGORIES | `SELECT COUNT(*) FROM REF_CATEGORIES` | 6 lignes |
| Colonnes ACTIONS_CATALOG | `SELECT column_name FROM user_tab_columns WHERE table_name = 'ACTIONS_CATALOG' ORDER BY column_id` | Vérifier absence de RBAC_POLICIES et CHANGE_MODEL_CODE |
| Contraintes exclues | `SELECT constraint_name FROM user_constraints WHERE table_name = 'ACTIONS_CATALOG'` | Absence de CK_ACTIONS_CATALOG_CATEGORY, CK_ACTIONS_CATALOG_ENGINE (post-V050), CK_ACTIONS_CATALOG_PLATFORM (post-V052) |
| Partitionnement (post-V084–V086) | `SELECT table_name FROM user_part_tables WHERE table_name IN ('EXECUTIONS','EXECUTION_STEPS','AUDIT_LOG')` | 3 tables partitionnées |
| Package purge (post-V087) | `SELECT status FROM user_objects WHERE object_name = 'PKG_IDP_MAINTENANCE'` | VALID |
| Historique Flyway | `SELECT version, state FROM flyway_schema_history ORDER BY installed_rank` | baseline V98 uniquement |

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

*Généré dans le cadre de la Story 41-2 — Consolidation des scripts de migration Flyway*
*Référence : `idp-portal/docs/migration-audit-epic41.md` (Story 41-1)*
