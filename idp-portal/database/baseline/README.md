# Baseline Schema V083 — IDP Portal

## Contexte (Epic 41 — Consolidation des migrations BD)

Ce dossier contient le script de **baseline** du schéma Oracle de l'IDP Portal. Il consolide les 84 migrations Flyway V000–V083 en un seul script d'initialisation pour les **nouveaux environnements**.

| Fichier | Description |
|---------|-------------|
| `baseline_schema_v083.sql` | Script DDL+DML : 24 tables, indexes, contraintes, trigger, données de référence |
| `README.md` | Ce fichier — procédure de déploiement et validation |

> **⚠️ IMPORTANT** : Ce script s'applique **UNIQUEMENT** sur une base Oracle vierge.
> Les environnements existants (dev, staging, prod) sont **inchangés** — ils continuent d'utiliser la chaîne V000–V088 via Flyway normalement.

---

## Procédure de déploiement — Nouveaux environnements

### Étape 1 : Appliquer le script baseline via SQL\*Plus

```bash
# Connexion à la base vierge et exécution du script
sqlplus idp_user/password@NEW_ENV:1521/XEPDB1 @database/baseline/baseline_schema_v083.sql
```

> Le script crée les 24 tables, indexes, contraintes, le trigger d'immutabilité et insère les données de référence (REF_ENGINES, REF_CATEGORIES).

### Étape 2 : Déclarer la base au niveau V083 (commande Flyway `baseline`)

```bash
flyway \
  -url=jdbc:oracle:thin:@NEW_ENV:1521/XEPDB1 \
  -user=idp_user \
  -password=password \
  -baselineVersion=83 \
  -baselineDescription=baseline_schema_v083 \
  baseline
```

> Cette commande enregistre une ligne dans `flyway_schema_history` indiquant que la base est déjà au niveau V083 (success=true). Flyway ne re-jouera pas V000–V083.

### Étape 3 : Appliquer les migrations incrémantales V084–V088

```bash
flyway \
  -url=jdbc:oracle:thin:@NEW_ENV:1521/XEPDB1 \
  -user=idp_user \
  -password=password \
  migrate
```

> Flyway applique automatiquement les migrations V084, V085, V086, V087, V088 dans l'ordre.

### Étape 4 : Vérifier le résultat

```bash
flyway \
  -url=jdbc:oracle:thin:@NEW_ENV:1521/XEPDB1 \
  -user=idp_user \
  -password=password \
  info
```

Le résultat attendu :

```
+------------+---------+-------------------------------+--------+---------------------+----------+
| Category   | Version | Description                   | Type   | Installed On        | State    |
+------------+---------+-------------------------------+--------+---------------------+----------+
| Versioned  | 83      | baseline schema v083          | BASELN | ...                 | Baseline |
| Versioned  | 84      | partition executions          | SQL    | ...                 | Success  |
| Versioned  | 85      | partition execution steps     | SQL    | ...                 | Success  |
| Versioned  | 86      | partition audit log           | SQL    | ...                 | Success  |
| Versioned  | 87      | create purge procedure        | SQL    | ...                 | Success  |
| Versioned  | 88      | integrations auth flow oauth2 | SQL    | ...                 | Success  |
+------------+---------+-------------------------------+--------+---------------------+----------+
```

---

## Environnements existants — Aucune action requise

```bash
# Comportement normal — aucune modification
flyway migrate  # Applique uniquement les nouvelles migrations (V089+ futures)
```

Les environnements existants ont déjà V000–V088 dans `flyway_schema_history`. Ce script ne les affecte pas.

---

## Contenu de baseline_schema_v083.sql

### Tables créées (24)

| Phase | Tables |
|-------|--------|
| Phase 1 — Sans FK entrantes | USERS, TAGS, PROFILES, INTEGRATIONS, REF_ENGINES, REF_CATEGORIES, INTEGRATION_TYPE_CATALOGUE, CORE_FEATURE_FLAGS, BUSINESS_RULE_POLICIES, ACTIONS_CATALOG |
| Phase 2 — Dépendantes d'ACTIONS_CATALOG/USERS | EXECUTION_LOG, USER_PERMISSIONS, ACTION_TAGS, USER_FAVORITES, ACTION_MUTEX, PROFILE_ACTION_PERMISSIONS, PROFILE_TARGET_PERMISSIONS, INTEGRATION_ACTIONS, AUDIT_LOG |
| Phase 3 — Exécutions | EXECUTIONS, EXECUTION_STEPS, EXECUTION_TARGETS, SCHEDULED_EXECUTIONS, RECURRING_PATTERNS |
| Phase 4 — Trigger | TRG_AUDIT_LOG_IMMUTABLE |

### Données de référence insérées

| Table | Lignes | Source |
|-------|--------|--------|
| REF_ENGINES | 6 | V049 + V078 : Oracle, SQL Server, DB2, PostgreSQL, MySQL, Workflow |
| REF_CATEGORIES | 6 | V059 : provisioning, patching, administration, monitoring, backup, autres |
| INTEGRATION_TYPE_CATALOGUE | 0 | Gérées par l'application (fixtures Django) |
| INTEGRATION_ACTIONS | 0 | Gérées par l'application (fixtures Django) |

### Éléments exclus (neutralisés par les migrations V000–V083)

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
| `CHK_EXECUTION_ENV` | Contrainte droppée V053 |
| `CHK_SCHEDULED_ENV` | Contrainte droppée V053 |
| `CK_INTEGRATIONS_TYPE` | Contrainte droppée V024 (TYPE libre depuis V024) |

---

## Plan de validation — Procédure via Docker

Pour valider que le schéma produit par `baseline_schema_v083.sql` + V084–V088 est identique à celui produit par V000–V088 :

```bash
# 1. Démarrer deux instances Oracle Docker
docker-compose up oracle-a oracle-b

# 2. Sur oracle-a : appliquer la chaîne complète V000–V088
flyway -url=jdbc:oracle:thin:@oracle-a:1521/XEPDB1 migrate

# 3. Sur oracle-b : appliquer baseline puis migrer V084–V088
sqlplus idp_user/password@oracle-b:1521/XEPDB1 @database/baseline/baseline_schema_v083.sql
flyway -url=jdbc:oracle:thin:@oracle-b:1521/XEPDB1 \
       -baselineVersion=83 \
       -baselineDescription=baseline_schema_v083 \
       baseline
flyway -url=jdbc:oracle:thin:@oracle-b:1521/XEPDB1 migrate

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
| Nombre de tables | `SELECT COUNT(*) FROM user_tables` | 24 tables (baseline) ; après V084–V088, vérifier via `user_part_tables` (EXECUTIONS, EXECUTION_STEPS, AUDIT_LOG partitionnées — le compte `user_tables` peut varier selon la configuration Oracle) |
| Trigger immutabilité | `SELECT status FROM user_triggers WHERE trigger_name = 'TRG_AUDIT_LOG_IMMUTABLE'` | ENABLED |
| Données REF_ENGINES | `SELECT COUNT(*) FROM REF_ENGINES` | 6 lignes |
| Données REF_CATEGORIES | `SELECT COUNT(*) FROM REF_CATEGORIES` | 6 lignes |
| Colonnes ACTIONS_CATALOG | `SELECT column_name FROM user_tab_columns WHERE table_name = 'ACTIONS_CATALOG' ORDER BY column_id` | Vérifier absence de RBAC_POLICIES et CHANGE_MODEL_CODE |
| Contraintes exclues | `SELECT constraint_name FROM user_constraints WHERE table_name = 'ACTIONS_CATALOG'` | Absence de CK_ACTIONS_CATALOG_CATEGORY, CK_ACTIONS_CATALOG_ENGINE (post-V050), CK_ACTIONS_CATALOG_PLATFORM (post-V052) |
| Partitionnement (post-V084–V086) | `SELECT table_name FROM user_part_tables WHERE table_name IN ('EXECUTIONS','EXECUTION_STEPS','AUDIT_LOG')` | 3 tables partitionnées |
| Package purge (post-V087) | `SELECT status FROM user_objects WHERE object_name = 'PKG_IDP_MAINTENANCE'` | VALID |
| Historique Flyway | `SELECT version, state FROM flyway_schema_history ORDER BY installed_rank` | baseline V83 + V84–V88 Success |

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

```
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
