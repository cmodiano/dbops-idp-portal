# Audit des migrations Flyway — Epic 41 : Consolidation des migrations BD

**Date :** 2026-02-24
**Auteur :** Agent de développement (claude-sonnet-4-6)
**Périmètre :** 89 scripts Flyway V000–V088 dans `idp-portal/database/migrations/`
**Objectif :** Inventaire complet, analyse des dépendances, stratégie de consolidation et plan de validation

---

## Table des matières

1. [Tableau d'audit complet V000–V088](#1-tableau-daudit-complet-v000v088)
2. [Groupements logiques](#2-groupements-logiques)
3. [Analyse des dépendances inter-scripts](#3-analyse-des-dépendances-inter-scripts)
4. [Classification par idempotence](#4-classification-par-idempotence)
5. [Scripts de cleanup/drop — importance pour la consolidation](#5-scripts-de-cleanupdrop--importance-pour-la-consolidation)
6. [Stratégies de consolidation](#6-stratégies-de-consolidation)
7. [Stratégie recommandée](#7-stratégie-recommandée)
8. [Risques documentés](#8-risques-documentés)
9. [Plan de validation](#9-plan-de-validation)
10. [Procédure de déploiement — Baseline vs Incrémental](#10-procédure-de-déploiement--baseline-vs-incrémental)

---

## 1. Tableau d'audit complet V000–V088

> **Légende :**
> - **Type DDL** : CREATE TABLE (CT), ALTER TABLE (AT), DROP TABLE (DT), CREATE INDEX (CI), DROP CONSTRAINT (DC), CREATE OR REPLACE (COR), INSERT (INS), UPDATE (UPD), COMMENT (CMT), DROP SEQUENCE (DS), DROP COLUMN (DC), CREATE PACKAGE (CP)
> - **Idempotent** : Oui = peut être ré-exécuté sans erreur ; Non = échoue si objet existe déjà ; Partiel = mécanisme de guard partiel

| Version | Fichier | Type DDL principal | Domaine | Objets créés/modifiés | Dépendances clés | Idempotent |
|---------|---------|-------------------|---------|----------------------|------------------|-----------|
| V000 | `create_schema_version` | CREATE TABLE | schema-init | `SCHEMA_VERSION` | — | Non |
| V001 | `create_users` | CT + CI | users | `USERS`, `UK_USERS_USERNAME` | — | Non |
| V002 | `create_actions_catalog` | CT + CI | catalog | `ACTIONS_CATALOG`, 4 indexes | V001 (FK CREATED_BY) | Non |
| V003 | `add_execution_steps` | AT (PL/SQL guard) | catalog | +`EXECUTION_STEPS` CLOB, +`CHANGE_TYPE_CONFIG` CLOB on ACTIONS_CATALOG | V002 | **Oui** |
| V004 | `create_audit_log` | CT + CI | audit | `AUDIT_LOG`, 3 indexes | — (PERFORMED_BY = VARCHAR2) | Non |
| V005 | `create_user_permissions` | CT | users/rbac | `USER_PERMISSIONS` | V001, V002 (FK) | Non |
| V006 | `create_execution_log` | CT + CI | execution-legacy | `EXECUTION_LOG`, 3 indexes | V002 (FK ACTION_ID) | Non |
| V007 | `create_tags_and_action_tags` | CT + CI | catalog/tags | `TAGS`, `ACTION_TAGS`, 2 indexes | V002 (FK ACTION_ID) | Non |
| V008 | `connector_type_in_execution_steps` | COMMENT | catalog/doc | COMMENT ON ACTIONS_CATALOG.EXECUTION_STEPS | V003 | **Oui** |
| V009 | `remove_cab_change_type` | UPD (data) | catalog/data | CHANGE_TYPE_CONFIG data: `"cab"` → `"pre_approved"` | V003 | **Oui** |
| V010 | `create_profiles` | CT + CI | rbac/profiles | `PROFILES`, `IDX_PROFILES_AD_GROUP` | — | Non |
| V011 | `create_profile_action_permissions` | CT | rbac/profiles | `PROFILE_ACTION_PERMISSIONS` | V010 (FK PROFILE_ID) | Non |
| V012 | `create_profile_target_permissions` | CT | rbac/profiles | `PROFILE_TARGET_PERMISSIONS` | V010 (FK PROFILE_ID) | Non |
| V013 | `drop_rbac_policies_from_actions` | AT DROP COLUMN | catalog/cleanup | DROP ACTIONS_CATALOG.RBAC_POLICIES | V002 | Non |
| V014 | `add_default_impact_level` | AT ADD | catalog | +`DEFAULT_IMPACT_LEVEL` on ACTIONS_CATALOG | V002 | Non |
| V015 | `drop_schema_version` | DROP TABLE | schema-cleanup | DROP `SCHEMA_VERSION` | V000 | Non |
| V016 | `drop_sequences` | DS (guarded) | schema-cleanup | DROP 6 séquences legacy (SEQ_USERS, etc.) | V001–V007 (séquences pré-Flyway) | **Oui** |
| V017 | `add_change_model_code` | AT ADD | catalog | +`CHANGE_MODEL_CODE` on ACTIONS_CATALOG | V002 | Non |
| V018 | `drop_category_column` | AT DROP CI+DC | catalog/cleanup | DROP `CK_ACTIONS_CATALOG_CATEGORY`, `IDX_ACTIONS_CATALOG_CATEGORY` | V002 | Non |
| V019 | `change_type_config_per_env` | UPD + AT DROP | catalog/data | Data migration CHANGE_TYPE_CONFIG; DROP CHANGE_MODEL_CODE | V003, V017 | Non |
| V020 | `create_integrations` | CT | integrations | `INTEGRATIONS` | — | Non |
| V021 | `create_user_favorites` | CT | favorites | `USER_FAVORITES` | V001 (FK), V002 (FK) | Non |
| V022 | `add_documentation_md` | AT ADD | catalog | +`DOCUMENTATION_MD` CLOB on ACTIONS_CATALOG | V002 | Non |
| V023 | `create_executions` | CT + CI | executions | `EXECUTIONS`, 4 indexes | V001 (FK), V002 (FK) | Non |
| V024 | `integrations_type_libre_auth_flow` | AT DROP DC + AT ADD | integrations | DROP type CHECK; +`AUTH_FLOW` on INTEGRATIONS | V020 | Non |
| V025 | `create_execution_steps` | CT + CI | executions | `EXECUTION_STEPS`, 2 indexes | V023 (FK CASCADE) | Non |
| V026 | `integrations_token_url_config` | AT ADD | integrations | +`TOKEN_URL`, +`CONFIG` CLOB on INTEGRATIONS | V020 | Non |
| V027 | `add_item_type_workflows` | AT ADD | catalog | +`ITEM_TYPE` on ACTIONS_CATALOG | V002 | Non |
| V028 | `audit_log_execution_traces` | AT ADD + CI + DC | audit | +`CORRELATION_ID`; IDX_AUDIT_LOG_CORRELATION; REDÉFINIT ACTION_TYPE + ENTITY_TYPE CHECK | V004 | Non |
| V029 | `add_audit_log_entity_type_timestamp_index` | CI | audit/perf | `IDX_AUDIT_LOG_ENTITY_TYPE_TIMESTAMP` (composite) | V004, V028 | Non |
| V030 | `add_approval_workflow` | AT ADD | executions | +`APPROVED_BY`, `APPROVED_AT`, `APPROVAL_COMMENT` on EXECUTIONS | V023, V001 (FK) | Non |
| V031 | `add_remediation_rules` | AT ADD | catalog | +`REMEDIATION_RULES` CLOB on ACTIONS_CATALOG | V002 | Non |
| V032 | `add_approval_audit_action_types` | DC + AT ADD | audit | REDEF. `CK_AUDIT_LOG_ACTION_TYPE` (+PENDING_APPROVAL etc.) | V028 | Non |
| V033 | `add_parent_execution_id` | AT ADD | executions | +`PARENT_EXECUTION_ID` (FK self-join) on EXECUTIONS | V023 | Non |
| V034 | `add_remediation_audit_action_type` | DC + AT ADD | audit | REDEF. `CK_AUDIT_LOG_ACTION_TYPE` (+REMEDIATION_TRIGGERED) | V032 | Non |
| V035 | `add_auto_remediation_audit_types` | DC + AT ADD | audit | REDEF. `CK_AUDIT_LOG_ACTION_TYPE` (+AUTO_REMEDIATION_*) | V034 | Non |
| V036 | `add_integration_id_to_actions` | AT ADD | catalog/integrations | +`INTEGRATION_ID` (FK) on ACTIONS_CATALOG | V002, V020 (FK) | Non |
| V037 | `make_engine_platform_nullable_for_workflows` | AT MODIFY | catalog | ACTIONS_CATALOG.ENGINE, PLATFORM → nullable | V002 | Non |
| V038 | `add_scheduled_executions` | CT (PL/SQL guard) + CI | scheduling | `SCHEDULED_EXECUTIONS`, `RECURRING_PATTERNS`, indexes | V001 (FK), V002 (FK) | **Oui** |
| V039 | `add_scheduled_execution_audit_types` | DC + AT ADD | audit | REDEF. `CK_AUDIT_LOG_ACTION_TYPE` (+SCHEDULED_EXECUTION_*) | V035 | Non |
| V040 | `add_scheduled_execution_cancelled_audit_type` | DC + AT ADD | audit | REDEF. `CK_AUDIT_LOG_ACTION_TYPE` (+SCHEDULED_EXEC_CANCELLED) | V039 | Non |
| V041 | `add_correlation_id_execution_id_to_scheduled_executions` | AT ADD | scheduling | +`CORRELATION_ID`, +`EXECUTION_ID` (FK) on SCHEDULED_EXECUTIONS | V038, V023 (FK) | Non |
| V042 | `add_id_to_action_tags` | AT ADD | catalog/tags | +`ID` NUMBER IDENTITY on ACTION_TAGS | V007 | Non |
| V043 | `add_id_to_user_favorites` | AT ADD | favorites | +`ID` NUMBER IDENTITY on USER_FAVORITES | V021 | Non |
| V044 | `extend_audit_log_action_types_for_auth_and_admin` | DC + AT ADD | audit | REDEF. `CK_AUDIT_LOG_ACTION_TYPE` (+LOGIN/LOGOUT/etc.) | V040 | Non |
| V045 | `add_integration_profile_entity_types_to_audit_log` | DC + AT ADD | audit | REDEF. `CK_AUDIT_LOG_ENTITY_TYPE` (+integration, profile) | V028 | Non |
| V046 | `add_requires_target_to_actions_catalog` | AT ADD | catalog | +`REQUIRES_TARGET` NUMBER(1) on ACTIONS_CATALOG | V002 | Non |
| V047 | `add_execution_target_forbidden_audit_type` | DC + AT ADD | audit | REDEF. `CK_AUDIT_LOG_ACTION_TYPE` (+EXECUTION_TARGET_FORBIDDEN) | V044 | Non |
| V048 | `convert_timestamp_with_tz_to_timestamp` | AT (add/copy/drop/rename) | executions/compat | TIMESTAMP WITH TZ → TIMESTAMP UTC sur EXECUTIONS, EXECUTION_STEPS, SCHEDULED_EXECUTIONS, RECURRING_PATTERNS | V023, V025, V038, V030 | Non |
| V049 | `create_ref_engines` | CT + INS | reference-data | `REF_ENGINES` + 6 lignes (Oracle, SQL Server, DB2, PostgreSQL, MySQL, Workflow) | — | Non |
| V050 | `drop_check_engine_constraint` | DC | catalog/cleanup | DROP `CK_ACTIONS_CATALOG_ENGINE` | V002 | Non |
| V051 | `create_ref_platforms` | CT + INS | reference-data | `REF_PLATFORMS` + 4 lignes (AAP, GitHub Actions, Azure DevOps, Terraform) | — | Non |
| V052 | `drop_check_platform_constraint` | DC | catalog/cleanup | DROP `CK_ACTIONS_CATALOG_PLATFORM` | V002 | Non |
| V053 | `drop_check_environment_constraints` | DC | cleanup | DROP CHK_EXECUTION_ENV, CHK_SCHEDULED_ENV | V023, V038 | Non |
| V054 | `audit_log_immutable_trigger` | CREATE OR REPLACE TRIGGER | audit/security | `TRG_AUDIT_LOG_IMMUTABLE` (BEFORE UPDATE OR DELETE) | V004 | **Oui** |
| V055 | `workflow_steps_branches_retry` | COMMENT | catalog/doc | COMMENT ON ACTIONS_CATALOG.EXECUTION_STEPS (branches/retry JSON schema) | V003 | **Oui** |
| V056 | `add_soft_delete_columns_to_actions_catalog` | AT ADD | catalog | +`DELETED_AT`, `DELETED_BY`, `DELETION_REASON` on ACTIONS_CATALOG | V002 | Non |
| V057 | `add_integration_error_status` | AT ADD + DC | executions | +`ERROR_MESSAGE` on EXECUTIONS; +`INTEGRATION_ERROR` dans CHK_EXECUTION_STATUS | V023 | Non |
| V058 | `add_action_deactivated_reactivated_audit_types` | DC + AT ADD | audit | REDEF. `CK_AUDIT_LOG_ACTION_TYPE` (+ACTION_DEACTIVATED, ACTION_REACTIVATED) | V047 | Non |
| V059 | `create_ref_categories` | CT + INS | reference-data | `REF_CATEGORIES` + 6 lignes (provisioning, patching, etc.) | — | Non |
| V060 | `add_filter_by_attribute_to_profile_target_permissions` | AT ADD | rbac/profiles | +`FILTER_BY_ATTRIBUTE_JSON` CLOB on PROFILE_TARGET_PERMISSIONS | V012 | Non |
| V061 | `create_integration_type_catalogue_and_actions` | CT + CI | integrations/catalogue | `INTEGRATION_TYPE_CATALOGUE`, `INTEGRATION_ACTIONS`, indexes | — | Non |
| V062 | `create_core_feature_flags` | CT | feature-flags | `CORE_FEATURE_FLAGS` | — | Non |
| V063 | `add_execution_action_created_index` | CI | executions/perf | `IDX_EXEC_ACTION_CREATED` (ACTION_ID, CREATED_AT) | V023 | Non |
| V064 | `add_integration_status` | AT ADD | integrations | +`STATUS` on INTEGRATIONS | V020 | Non |
| V065 | `update_audit_log_constraints` | DC + AT ADD | audit | REDEF. `CK_AUDIT_LOG_ACTION_TYPE` (correction/ajout types) | V058 | Non |
| V066 | `create_execution_targets` | CT + CI | executions | `EXECUTION_TARGETS`, 2 indexes | V023 (FK CASCADE) | Non |
| V067 | `add_waiting_status_to_execution_steps` | AT MODIFY | executions | REDEF. CHK_STEP_STATUS (+WAITING) | V025 | Non |
| V068 | `add_missing_audit_action_types_integration_validation` | DC + AT ADD | audit | REDEF. `CK_AUDIT_LOG_ACTION_TYPE` (+INTEGRATION_VALIDATED etc.) | V065 | Non |
| V069 | `add_gate_evaluation_audit_action_types` | DC + AT ADD | audit | REDEF. `CK_AUDIT_LOG_ACTION_TYPE` (+GATE_EVALUATION_*) | V068 | Non |
| V070 | `create_action_mutex` | CT + CI | catalog/rules | `ACTION_MUTEX`, 2 indexes | V002 (FK ×2) | Non |
| V071 | `add_exclusion_patterns_to_profile_target_permissions` | AT ADD | rbac/profiles | +`EXCLUSION_PATTERNS_JSON` CLOB on PROFILE_TARGET_PERMISSIONS | V012 | Non |
| V072 | `add_integration_role` | AT ADD | integrations | +`INTEGRATION_ROLE` on INTEGRATION_TYPE_CATALOGUE | V061 | Non |
| V073 | `add_tower_terraform_cloud_platforms` | INS | reference-data | INSERT 2 lignes dans REF_PLATFORMS (Tower, Terraform Cloud) | V051 | Non |
| V074 | `add_business_rule_policies_to_actions_catalog` | AT ADD | catalog/rules | +`BUSINESS_RULE_POLICIES` CLOB on ACTIONS_CATALOG | V002 | Non |
| V075 | `sync_integration_role_platform_service` | UPD (data) | integrations | UPDATE INTEGRATION_TYPE_CATALOGUE.INTEGRATION_ROLE pour tous les types | V061, V072 | **Oui** |
| V076 | `create_business_rule_policies_table_and_fk` | CT + AT + CI | catalog/rules | `BUSINESS_RULE_POLICIES`; +FK BUSINESS_RULE_POLICY_ID + CHK_XOR on ACTIONS_CATALOG | V001 (FK), V002 (AT) | Non |
| V077 | `add_secret_service_id_to_integrations` | AT ADD | integrations | +`SECRET_SERVICE_ID` on INTEGRATIONS | V020 | Non |
| V078 | `add_icon_url_to_ref_engines` | AT ADD | reference-data | +`ICON_URL` on REF_ENGINES | V049 | Non |
| V079 | `add_action_disabled_integration_deleted_audit_type` | DC + AT ADD | audit | REDEF. `CK_AUDIT_LOG_ACTION_TYPE` (+ACTION_DISABLED_INTEGRATION_DELETED) | V069 | Non |
| V080 | `allow_disabled_without_soft_delete` | AT MODIFY | catalog | REDEF. CHK_ACTIONS_CATALOG_STATUS (allow disabled sans DELETED_AT) | V056 | Non |
| V081 | `add_gate_config_to_actions_catalog` | AT ADD | catalog | +`GATE_CONFIG` JSON on ACTIONS_CATALOG | V002 | Non |
| V082 | `add_notification_config_to_actions_catalog` | AT ADD | catalog | +`NOTIFICATION_CONFIG` JSON on ACTIONS_CATALOG | V002 | Non |
| V083 | `drop_ref_platforms` | DROP TABLE | reference-data/cleanup | DROP `REF_PLATFORMS` | V051, V073 | Non |
| V084 | `partition_executions` | CT + multi-phase DDL | partitioning | `EXECUTIONS` → PARTITION BY RANGE INTERVAL (monthly) ; 11 phases | V023, V025, V066, V030, V033 | Partiel |
| V085 | `partition_execution_steps` | CT + multi-phase DDL | partitioning | `EXECUTION_STEPS` → PARTITION BY REFERENCE (FK V084) ; 10 phases | V084 (prérequis EXECUTIONS partitionné) | Non |
| V086 | `partition_audit_log` | CT + multi-phase DDL + COR TRIGGER | partitioning | `AUDIT_LOG` → PARTITION BY RANGE INTERVAL (monthly) ; recrée TRG_AUDIT_LOG_IMMUTABLE | V004, V054, V069 | Partiel |
| V087 | `create_purge_procedure` | CT + CREATE OR REPLACE PACKAGE | maintenance | `IDP_MAINTENANCE_LOG`; `PKG_IDP_MAINTENANCE` (purge_old_partitions, purge_executions, purge_audit_log) | V084, V085, V086 | **Oui** |
| V088 | `integrations_auth_flow_oauth2_api_key` | DC + AT ADD | integrations | REDEF. `CK_INTEGRATIONS_AUTH_FLOW` (+oauth2_client_credentials, api_key) | V024 | Non |

---

## 2. Groupements logiques

| Domaine | Scripts | Nb | Description |
|---------|---------|-----|-------------|
| **schema-init** | V000 | 1 | Table SCHEMA_VERSION custom (remplacée par flyway_schema_history) |
| **users** | V001, V005 | 2 | Table USERS + USER_PERMISSIONS |
| **catalog** | V002–V003, V008, V013–V014, V017–V018, V022, V027, V031, V036–V037, V046, V056, V074, V080–V082 | 18 | ACTIONS_CATALOG et toutes ses évolutions |
| **audit** | V004, V028–V029, V032, V034–V035, V039–V040, V044–V045, V047, V054, V058, V065, V068–V069, V079 | 17 | AUDIT_LOG + extensions constantes de types + trigger immutabilité |
| **execution-legacy** | V006 | 1 | EXECUTION_LOG (table simplifiée antérieure à EXECUTIONS) |
| **catalog/tags** | V007, V042 | 2 | TAGS + ACTION_TAGS |
| **rbac/profiles** | V010–V012, V060, V071 | 5 | PROFILES + permissions actions/targets |
| **cleanup-drop** | V009, V013, V015–V016, V018–V019, V050, V052–V053, V083 | 10 | Suppressions/nettoyages de schéma et données |
| **integrations** | V020, V024, V026, V036, V064, V072, V075, V077, V088 | 9 | Table INTEGRATIONS + évolutions auth/status |
| **favorites** | V021, V043 | 2 | USER_FAVORITES |
| **executions** | V023, V025, V030, V033, V037, V041, V048, V057, V063, V066–V067 | 11 | EXECUTIONS + EXECUTION_STEPS + EXECUTION_TARGETS |
| **scheduling** | V038–V041 | 4 | SCHEDULED_EXECUTIONS + RECURRING_PATTERNS |
| **approval/remediation** | V030–V032, V034–V035 | 5 | Workflow d'approbation + règles de remédiation |
| **reference-data** | V049, V051, V059, V061, V073, V078 | 6 | REF_ENGINES, REF_PLATFORMS (droppée V083), REF_CATEGORIES, INTEGRATION_TYPE_CATALOGUE |
| **catalog/rules** | V070, V074, V076 | 3 | ACTION_MUTEX + BUSINESS_RULE_POLICIES |
| **feature-flags** | V062 | 1 | CORE_FEATURE_FLAGS |
| **partitioning** | V084–V087 | 4 | Partitionnement EXECUTIONS + EXECUTION_STEPS + AUDIT_LOG + procédure purge |
| **integrations/catalogue** | V061, V072, V075 | 3 | INTEGRATION_TYPE_CATALOGUE + INTEGRATION_ACTIONS |

---

## 3. Analyse des dépendances inter-scripts

### 3.1 Graphe de dépendances par FK et ALTER TABLE

```text
USERS (V001)
  ├── ACTIONS_CATALOG.CREATED_BY → USERS.ID (V002)
  ├── USER_PERMISSIONS → USERS (V005)
  ├── USER_FAVORITES.USER_ID → USERS.ID (V021)
  ├── EXECUTIONS.USER_ID → USERS.ID (V023)
  ├── EXECUTIONS.APPROVED_BY → USERS.ID (V030)
  ├── SCHEDULED_EXECUTIONS.USER_ID → USERS.ID (V038)
  └── BUSINESS_RULE_POLICIES.CREATED_BY_ID → USERS.ID (V076)

ACTIONS_CATALOG (V002)
  ├── USER_PERMISSIONS → ACTIONS_CATALOG (V005)
  ├── EXECUTION_LOG.ACTION_ID → ACTIONS_CATALOG.ID (V006)
  ├── ACTION_TAGS.ACTION_ID → ACTIONS_CATALOG.ID (V007)
  ├── USER_FAVORITES.ACTION_ID → ACTIONS_CATALOG.ID (V021)
  ├── EXECUTIONS.ACTION_ID → ACTIONS_CATALOG.ID (V023)
  ├── ACTIONS_CATALOG.INTEGRATION_ID → INTEGRATIONS.ID (V036)
  ├── SCHEDULED_EXECUTIONS.ACTION_ID → ACTIONS_CATALOG.ID (V038)
  ├── PROFILE_ACTION_PERMISSIONS (V011) — via PROFILES
  ├── ACTION_MUTEX.ACTION_ID → ACTIONS_CATALOG.ID ×2 (V070)
  └── ACTIONS_CATALOG.BUSINESS_RULE_POLICY_ID → BUSINESS_RULE_POLICIES.ID (V076)

EXECUTIONS (V023)
  ├── EXECUTION_STEPS.EXECUTION_ID → EXECUTIONS.ID CASCADE (V025)
  ├── EXECUTIONS.PARENT_EXECUTION_ID → EXECUTIONS.ID (V033)
  ├── SCHEDULED_EXECUTIONS.EXECUTION_ID → EXECUTIONS.ID (V041)
  ├── EXECUTION_TARGETS.EXECUTION_ID → EXECUTIONS.ID CASCADE (V066)
  └── V084 (partition) → prérequis pour V085 (partition ref EXECUTION_STEPS)

PROFILES (V010)
  ├── PROFILE_ACTION_PERMISSIONS.PROFILE_ID → PROFILES.ID CASCADE (V011)
  └── PROFILE_TARGET_PERMISSIONS.PROFILE_ID → PROFILES.ID CASCADE (V012)

INTEGRATIONS (V020)
  ├── ACTIONS_CATALOG.INTEGRATION_ID → INTEGRATIONS.ID (V036)
  └── CK_INTEGRATIONS_AUTH_FLOW évolue V024 → V088

TAGS (V007)
  └── ACTION_TAGS.TAG_ID → TAGS.ID (V007)

INTEGRATION_TYPE_CATALOGUE (V061)
  ├── INTEGRATION_ACTIONS.INTEGRATION_TYPE_CODE → INTEGRATION_TYPE_CATALOGUE.CODE CASCADE (V061)
  └── INTEGRATION_TYPE_CATALOGUE.INTEGRATION_ROLE (V072)

BUSINESS_RULE_POLICIES (V076)
  └── ACTIONS_CATALOG.BUSINESS_RULE_POLICY_ID → BUSINESS_RULE_POLICIES.ID (V076)

AUDIT_LOG (V004)
  ├── CK_AUDIT_LOG_ACTION_TYPE évolue : V028→V032→V034→V035→V039→V040→V044→V047→V058→V065→V068→V069→V079→V086
  ├── CK_AUDIT_LOG_ENTITY_TYPE évolue : V028→V045
  └── TRG_AUDIT_LOG_IMMUTABLE : V054 (créé) → V086 (recréé après partition)
```

### 3.2 Chaîne de dépendances de la contrainte CK_AUDIT_LOG_ACTION_TYPE

La contrainte est redéfinie **14 fois** (V028, V032, V034, V035, V039, V040, V044, V047, V058, V065, V068, V069, V079, V086). Chaque script drop la contrainte précédente et recrée une version étendue. L'état final (V086) contient ~65 types d'action.

**Implication pour la baseline :** La baseline doit inclure uniquement l'état final de la contrainte (contenu de V086), pas les 13 versions intermédiaires.

### 3.3 Scripts neutralisés (create + drop dans la même plage)

| Script de création | Script de suppression | État net | Conséquence pour baseline |
|-------------------|-----------------------|----------|--------------------------|
| V000 (SCHEMA_VERSION) | V015 (DROP SCHEMA_VERSION) | N'existe pas | **Exclure les deux** |
| V001–V007 (séquences pré-Flyway) | V016 (DROP séquences) | Séquences absentes | **Exclure les séquences** ; tables avec IDENTITY suffisent |
| V017 (ADD CHANGE_MODEL_CODE) | V019 (DROP CHANGE_MODEL_CODE) | Colonne absente | **Exclure** ADD et DROP |
| V018 (DROP category CHECK+IDX) | — | CHECK/IDX absents | La baseline ne doit pas inclure `CK_ACTIONS_CATALOG_CATEGORY` ni `IDX_ACTIONS_CATALOG_CATEGORY` |
| V051 (REF_PLATFORMS) + V073 (INSERTs) | V083 (DROP REF_PLATFORMS) | N'existe pas | **Exclure les trois** |
| V002 (RBAC_POLICIES column) | V013 (DROP COLUMN) | Colonne absente | La baseline exclut RBAC_POLICIES de ACTIONS_CATALOG |

---

## 4. Classification par idempotence

### 4.1 Scripts idempotents (peuvent être ré-exécutés)

| Script | Mécanisme d'idempotence |
|--------|------------------------|
| V003 | PL/SQL `DECLARE/IF COUNT()=0 THEN EXECUTE IMMEDIATE` |
| V008 | `COMMENT ON COLUMN` (toujours écrasé) |
| V009 | `UPDATE REGEXP_REPLACE` (idempotent si aucune valeur `"cab"`) |
| V016 | `EXCEPTION WHEN OTHERS IF SQLCODE = -2289 THEN NULL` (DROP SEQUENCE si existe) |
| V038 | PL/SQL guard `IF COUNT(*) FROM user_tables = 0` |
| V054 | `CREATE OR REPLACE TRIGGER` |
| V055 | `COMMENT ON COLUMN` |
| V075 | `UPDATE SET` (idempotent sur données existantes) |
| V087 | `CREATE OR REPLACE PACKAGE / PACKAGE BODY` |

### 4.2 Scripts partiellement idempotents

| Script | Mécanisme | Limite |
|--------|-----------|--------|
| V084 | Phase 0 vérifie si `EXECUTIONS_NEW` existe déjà (état de migration partiellement exécutée — raise error si trouvée) | Pas sûr si interruption en cours de migration ; ne détecte pas si EXECUTIONS est déjà partitionnée |
| V086 | Phase 0 vérifie si `AUDIT_LOG_NEW` existe déjà (même mécanisme) | Idem |

### 4.3 Scripts non-idempotents (majorité)

Tous les `CREATE TABLE`, `ALTER TABLE ADD`, `DROP TABLE`, `CREATE INDEX`, `INSERT` sans guard PL/SQL, et les `DROP CONSTRAINT / ADD CONSTRAINT`. Oracle < 23c ne supporte pas `CREATE TABLE IF NOT EXISTS` nativement.

> **Conclusion :** La consolidation devra être conçue pour être exécutée **uniquement sur une base vierge**. Les scripts consolidés ne sont pas réexécutables sur une base existante.

---

## 5. Scripts de cleanup/drop — importance pour la consolidation

Ces scripts sont cruciaux : ils définissent ce qui **ne doit pas** apparaître dans un script de baseline.

| Script | Action | Impact sur la baseline |
|--------|--------|----------------------|
| V009 | UPDATE data CAB→pre_approved | **Non applicable** en baseline (pas de données existantes à migrer) |
| V013 | DROP COLUMN RBAC_POLICIES | La baseline **n'inclut pas** RBAC_POLICIES dans ACTIONS_CATALOG |
| V015 | DROP TABLE SCHEMA_VERSION | La baseline **n'inclut pas** la création de SCHEMA_VERSION |
| V016 | DROP SEQUENCE ×6 | La baseline **n'inclut pas** de séquences (IDENTITY columns suffisent) |
| V018 | DROP CK_ACTIONS_CATALOG_CATEGORY | La baseline **n'inclut pas** la contrainte CHECK CATEGORY |
| V019 | DROP COLUMN CHANGE_MODEL_CODE + data migration | La baseline **n'inclut pas** CHANGE_MODEL_CODE |
| V050 | DROP CK_ACTIONS_CATALOG_ENGINE | La baseline **n'inclut pas** la contrainte CHECK ENGINE |
| V052 | DROP CK_ACTIONS_CATALOG_PLATFORM | La baseline **n'inclut pas** la contrainte CHECK PLATFORM |
| V053 | DROP CHK_EXECUTION_ENV, CHK_SCHEDULED_ENV | La baseline **n'inclut pas** ces CHECK contraintes |
| V073 | INSERT REF_PLATFORMS | La baseline **n'inclut pas** ces inserts (REF_PLATFORMS supprimée en V083) |
| V083 | DROP TABLE REF_PLATFORMS | La baseline **n'inclut pas** la création de REF_PLATFORMS |

---

## 6. Stratégies de consolidation

### Option A — Baseline V000–V083 + incrémental V084–V088 *(Recommandée)*

**Description :** Créer un seul script `database/baseline/baseline_schema_v083.sql` représentant l'état final du schéma après V000–V083. Ce script est stocké dans un dossier dédié `baseline/` (hors de `migrations/`) car il n'est pas une migration Flyway — il est appliqué via SQL*Plus sur les nouveaux environnements vierges. Les scripts V084–V088 restent comme migrations incrémentales dans `migrations/`.

**Contenu de la baseline :**
- CREATE TABLE pour les 22 tables présentes dans l'état final
- INSERT de données de référence (REF_ENGINES, REF_CATEGORIES + inserts, INTEGRATION_TYPE_CATALOGUE inserts si présents)
- `CREATE OR REPLACE TRIGGER TRG_AUDIT_LOG_IMMUTABLE`
- Tous les index de l'état final
- Contraintes FK dans l'état final
- **Exclure :** SCHEMA_VERSION, séquences, REF_PLATFORMS, colonnes droppées (RBAC_POLICIES, CHANGE_MODEL_CODE), contraintes droppées (CHECK CATEGORY/ENGINE/PLATFORM/ENVIRONMENT)

**Avantages :**
- ✅ Réduction de 84 migrations à 1 script pour nouveaux environnements
- ✅ Point de coupure logique clair : avant le partitionnement (opération complexe et irréversible)
- ✅ Rollbacks disponibles pour V084–V087 (uniquement les partitionnements)
- ✅ `flyway baseline` est la commande native Flyway exactement conçue pour ce cas
- ✅ V084–V088 restent explicites et traçables
- ✅ Un seul nouveau script à maintenir

**Inconvénients :**
- ❌ Script baseline volumineux (~500–800 lignes)
- ❌ 5 scripts incrémantaux restent obligatoires après la baseline
- ❌ Doit être construit manuellement (en tenant compte des neutralisations)

---

### Option B — Squash par phases (3 scripts consolidés)

**Description :** 3 scripts distincts couvrant des phases chronologiques :
- `V001_phase1__init_v000_v019.sql` : tables core + cleanup précoce (V000–V019)
- `V002_phase2__features_v020_v047.sql` : intégrations, exécutions, audit étendu, scheduling (V020–V047)
- `V003_phase3__ref_cleanup_advanced_v048_v083.sql` : ref-data, triggers, soft-delete, business rules (V048–V083)
- V084–V088 restent incrémentaux

**Avantages :**
- ✅ Plus granulaire qu'une baseline unique (diagnostic d'échec plus précis)
- ✅ Meilleure lisibilité par domaine

**Inconvénients :**
- ❌ 3 scripts consolidés + 5 incrémantaux = 8 migrations totales (gestion plus complexe)
- ❌ Dépendances FK entre phases doivent être respectées strictement
- ❌ 3 nouveaux checksums dans `flyway_schema_history`
- ❌ Effort de construction 3× supérieur à l'Option A

---

### Option C — DDL export complet via DBMS_METADATA

**Description :** Utiliser `DBMS_METADATA.GET_DDL` sur l'instance Oracle de dev Docker pour extraire le DDL courant complet et créer un seul script bootstrap.

**Méthode :**
```sql
SELECT DBMS_METADATA.GET_DDL('TABLE', table_name)
FROM user_tables
ORDER BY table_name;

SELECT DBMS_METADATA.GET_DDL('INDEX', index_name)
FROM user_indexes
WHERE generated = 'N';
```

**Avantages :**
- ✅ Représente exactement l'état courant de la base (aucune déduction manuelle)
- ✅ Inclut les paramètres de storage/tablespace automatiquement

**Inconvénients :**
- ❌ Requiert accès à l'instance Oracle Docker fonctionnelle avec toutes les migrations appliquées
- ❌ DDL Oracle inclut des clauses de storage/physiques non portables (PCTFREE, INITRANS, etc.)
- ❌ Ne gère pas les données de référence (INSERTs séparés requis)
- ❌ Moins lisible et maintenable qu'un script écrit manuellement
- ❌ Risque d'inclure des objets système ou temporaires non désirés
- ❌ Trigger `TRG_AUDIT_LOG_IMMUTABLE` peut ne pas être exporté selon les privilèges

---

## 7. Stratégie recommandée

### Recommandation : **Option A — Baseline V000–V083**

**Justification :**

1. **Point de coupure logique optimal** : V084–V086 sont des partitionnements Oracle (opérations irréversibles à fort impact). Les garder comme scripts incrémantaux explicites avec rollbacks disponibles est plus sûr.

2. **Commande Flyway native** : `flyway baseline` est exactement conçu pour ce cas d'usage — marquer une base existante comme "déjà migrée" sans modifier `flyway_schema_history` des environnements existants.

3. **Maintenabilité maximale** : Un seul script à maintenir. Les futurs développeurs partent d'un état clairement documenté.

4. **Risque minimal** : Les scripts V084–V088 restant incrémantaux, les rollbacks existants (V084–V087) restent utilisables.

5. **Cohérence avec le projet** : Les stories restantes (41-2 etc.) implémenteront ce script consolidé. L'audit (cette story) prépare le terrain.

### Plan d'implémentation de la baseline (Story 41-2)

```text
idp-portal/database/
  baseline/
    baseline_schema_v083.sql                    ← NOUVEAU (à créer en 41-2) — appliqué via SQL*Plus, pas via Flyway
  migrations/
    V084__partition_executions.sql              ← INCHANGÉ
    V085__partition_execution_steps.sql         ← INCHANGÉ
    V086__partition_audit_log.sql               ← INCHANGÉ
    V087__create_purge_procedure.sql            ← INCHANGÉ
    V088__integrations_auth_flow_oauth2_api_key.sql ← INCHANGÉ
```

> **Pourquoi hors de `migrations/` ?** Les versions Flyway doivent être numériques (ex: `1`, `1.2`, `83`). Tout composant non-numérique dans le nom (ex: `_consolidated`) cause une erreur de parsing Flyway. Ce script n'est pas une migration Flyway mais un script SQL d'initialisation pour nouveaux environnements.
> **Important :** Les scripts V000–V083 originaux **restent dans `migrations/`** pour les environnements existants (dev, staging, prod). Le script consolidé est utilisé **uniquement pour nouveaux environnements**.

### Tables dans l'état final post-V083

| Table | Créée en | Notes |
|-------|----------|-------|
| USERS | V001 | Stable, nombreuses FK entrantes |
| ACTIONS_CATALOG | V002 + ~20 ALTERs | Table centrale, état final complexe |
| AUDIT_LOG | V004 + ~14 évolutions CHECK | CHECK CK_AUDIT_LOG_ACTION_TYPE = état V079 dans la baseline ; V086 (incrémental, post-baseline) redéfinira cette contrainte et recrée `TRG_AUDIT_LOG_IMMUTABLE` — inclure la définition finale de V086 dans la baseline serait prématuré |
| USER_PERMISSIONS | V005 | Stable |
| EXECUTION_LOG | V006 | Table legacy simple (jamais droppée) |
| TAGS | V007 | Stable |
| ACTION_TAGS | V007 + V042 | +ID IDENTITY (V042) |
| PROFILES | V010 | Stable |
| PROFILE_ACTION_PERMISSIONS | V011 | Stable |
| PROFILE_TARGET_PERMISSIONS | V012 + V060 + V071 | +FILTER_BY_ATTRIBUTE_JSON (V060), +EXCLUSION_PATTERNS_JSON (V071) |
| INTEGRATIONS | V020 + V024 + V026 + V036 + V057 + V064 + V072 + V077 | Auth flow, token_url, status, role, secret |
| USER_FAVORITES | V021 + V043 | +ID IDENTITY (V043) |
| EXECUTIONS | V023 + V030 + V033 + V037 + V048 + V057 | Timestamps UTC, approval, parent, nullable engine |
| EXECUTION_STEPS | V025 + V048 + V067 | Timestamps UTC, +WAITING status |
| SCHEDULED_EXECUTIONS | V038 + V041 + V048 | +CORRELATION_ID, +EXECUTION_ID FK, timestamps UTC |
| RECURRING_PATTERNS | V038 + V048 | Timestamps UTC |
| REF_ENGINES | V049 + V078 | +ICON_URL; inserts: Oracle, SQL Server, DB2, PostgreSQL, MySQL, Workflow |
| REF_CATEGORIES | V059 | Inserts: provisioning, patching, administration, monitoring, backup, autres |
| INTEGRATION_TYPE_CATALOGUE | V061 + V072 | +INTEGRATION_ROLE |
| INTEGRATION_ACTIONS | V061 | FK CASCADE vers INTEGRATION_TYPE_CATALOGUE |
| CORE_FEATURE_FLAGS | V062 | |
| EXECUTION_TARGETS | V066 | FK CASCADE vers EXECUTIONS |
| ACTION_MUTEX | V070 | Auto-référence ACTIONS_CATALOG |
| BUSINESS_RULE_POLICIES | V076 | FK CREATED_BY_ID → USERS |
| TRG_AUDIT_LOG_IMMUTABLE | V054 | Trigger SOC1/NFR8 sur AUDIT_LOG |

**Tables absentes de la baseline (neutralisées) :**
- `SCHEMA_VERSION` (V000 créé → V015 droppé)
- `REF_PLATFORMS` (V051 créé → V083 droppé)

---

## 8. Risques documentés

### R1 — Checksums Flyway incompatibles avec environnements existants

**Description :** Flyway vérifie le checksum de chaque migration dans `flyway_schema_history`. Le script consolidé `V001_consolidated__baseline_schema_v083.sql` aura un checksum différent des 84 scripts originaux.

**Impact :** Si appliqué sur un environnement existant (dev, staging, prod), Flyway rejettera le script avec erreur `Checksum mismatch`.

**Mitigation :**
- Le script consolidé est **exclusivement pour nouveaux environnements**
- Les environnements existants continuent d'utiliser V000–V088 intacts
- La commande `flyway baseline -baselineVersion=83 -baselineDescription=baseline_schema_v083` permet de déclarer un nouvel env comme "déjà au niveau V083 inclus" (les versions Flyway doivent être numériques)

### R2 — Rollback impossible après déploiement de la baseline

**Description :** Une fois la baseline appliquée sur un nouvel environnement, il n'est pas possible de "revenir" à la chaîne V000–V083 individuelle.

**Impact :** Si un bug est découvert dans la baseline consolidée après déploiement, le rollback implique de recréer l'environnement.

**Mitigation :**
- Validation rigoureuse avant promotion (voir section 9)
- Garder la baseline en lecture seule dans le repo (pas de modification post-déploiement)
- V084–V087 ont des scripts de rollback disponibles dans `database/rollback/`

### R3 — Migrations de données exclues (V009, V019)

**Description :** V009 migre les données `"cab"` → `"pre_approved"` dans ACTIONS_CATALOG.CHANGE_TYPE_CONFIG. V019 migre CHANGE_TYPE_CONFIG vers un format JSON par-environnement. Ces scripts n'ont pas de sens sur une base vierge (pas de données existantes).

**Impact :** Ces migrations ne sont pas incluses dans la baseline — ce qui est correct pour un nouvel environnement (base vierge).

**Mitigation :** Pas de mitigation nécessaire. La baseline part d'un schéma sans données, les migrations de données ne s'appliquent pas.

### R4 — Données de référence insérées par plusieurs scripts

**Description :** V049 insère des lignes dans REF_ENGINES, V059 dans REF_CATEGORIES, V073 insère dans REF_PLATFORMS (mais cette table est droppée en V083). La baseline doit inclure uniquement les inserts pertinents.

**Impact :** Si la baseline omet les inserts de référence, les fonctionnalités dépendantes (sélection d'engine, catégories) ne fonctionneront pas.

**Mitigation :** Inclure dans la baseline : inserts REF_ENGINES (V049 + V078 ICON_URL), inserts REF_CATEGORIES (V059). Exclure : inserts REF_PLATFORMS (V051, V073 — table droppée en V083).

### R5 — Trigger TRG_AUDIT_LOG_IMMUTABLE sur AUDIT_LOG non-partitionné

**Description :** V054 crée le trigger sur AUDIT_LOG. Après V086 (partition), le trigger est recréé sur la nouvelle table partitionnée. La baseline (état post-V083) inclut le trigger sur AUDIT_LOG non-partitionné — ce qui est correct car V086 sera appliqué après.

**Impact :** Aucun si la séquence baseline + V084–V088 est respectée.

**Mitigation :** Inclure le trigger dans la baseline, s'assurer que V086 le recrée (ce qu'il fait).

### R6 — Nommage des scripts consolidés doit éviter les conflits de version

**Description :** Flyway utilise des versions numériques pour ordonner les migrations. Le script consolidé doit avoir une version qui ne conflicte pas avec V000–V088.

**Impact :** Si le script est placé dans `migrations/` avec un nom commençant par `V`, Flyway tentera de le parser et d'appliquer comme une migration ordinaire. Les versions Flyway doivent être **purement numériques** — tout composant alphabétique (ex: `_consolidated`) dans la version cause une erreur de parsing.

**Mitigation :** Stocker le script dans `database/baseline/baseline_schema_v083.sql` (hors de `migrations/`). Ce script est appliqué **manuellement** via SQL*Plus sur un nouvel environnement vierge. Ensuite, `flyway baseline -baselineVersion=83` enregistre le schéma comme déjà à la version V083. Flyway applique alors V084–V088 automatiquement via `flyway migrate`.

---

## 9. Plan de validation

### 9.1 Méthode : Schema diff Oracle

Pour valider que le schéma produit par la baseline + V084–V088 est identique au schéma produit par V000–V088 :

```sql
-- Sur chaque Oracle (env-A = V000-V088, env-B = baseline + V084-V088)
-- Exporter toutes les tables
SELECT t.table_name,
       DBMS_METADATA.GET_DDL('TABLE', t.table_name) AS ddl
FROM user_tables t
ORDER BY table_name;

-- Exporter tous les index
SELECT i.index_name,
       DBMS_METADATA.GET_DDL('INDEX', i.index_name) AS ddl
FROM user_indexes i
WHERE i.generated = 'N'
ORDER BY index_name;

-- Exporter tous les triggers
SELECT t.trigger_name,
       DBMS_METADATA.GET_DDL('TRIGGER', t.trigger_name) AS ddl
FROM user_triggers t
ORDER BY trigger_name;

-- Exporter tous les packages
SELECT p.object_name,
       DBMS_METADATA.GET_DDL('PACKAGE', p.object_name) AS ddl
FROM user_objects p
WHERE p.object_type = 'PACKAGE'
ORDER BY object_name;
```

### 9.2 Procédure de validation via Docker

```bash
# 1. Démarrer deux instances Oracle Docker
docker-compose up oracle-a oracle-b

# 2. Sur oracle-a : appliquer la chaîne complète V000-V088
flyway -url=jdbc:oracle:thin:@oracle-a:1521/XEPDB1 migrate

# 3. Sur oracle-b : appliquer le script baseline puis migrer V084-V088
sqlplus idp_user/password@oracle-b:1521/XEPDB1 @database/baseline/baseline_schema_v083.sql
flyway -url=jdbc:oracle:thin:@oracle-b:1521/XEPDB1 baseline -baselineVersion=83 -baselineDescription=baseline_schema_v083
flyway -url=jdbc:oracle:thin:@oracle-b:1521/XEPDB1 migrate

# 4. Exporter et comparer
./scripts/export_schema.sh oracle-a > /tmp/schema-a.sql
./scripts/export_schema.sh oracle-b > /tmp/schema-b.sql
# Normaliser (suppression whitespace/storage clauses Oracle)
diff <(normalize.sh /tmp/schema-a.sql) <(normalize.sh /tmp/schema-b.sql)
# Résultat attendu : 0 différences structurelles
```

### 9.3 Checklist de validation manuelle (avant promotion)

| Vérification | Commande/Méthode | Critère de succès |
|-------------|-----------------|-------------------|
| Nombre de tables identiques | `SELECT COUNT(*) FROM user_tables` sur les 2 env | Même count |
| Tables présentes | `SELECT table_name FROM user_tables ORDER BY table_name` diff | Listes identiques |
| Colonnes de chaque table | `SELECT col_name, data_type FROM user_tab_columns WHERE table_name=... ORDER BY col_name` | Identiques |
| Contraintes FK | `SELECT constraint_name, r_constraint_name FROM user_constraints WHERE constraint_type='R'` | Identiques |
| Index | `SELECT index_name, table_name FROM user_indexes WHERE generated='N'` | Identiques |
| Données de référence | `SELECT COUNT(*) FROM REF_ENGINES`, `REF_CATEGORIES` | Même count et contenu |
| Trigger immutabilité | `SELECT status FROM user_triggers WHERE trigger_name='TRG_AUDIT_LOG_IMMUTABLE'` | ENABLED |
| Package purge | `SELECT status FROM user_objects WHERE object_name='PKG_IDP_MAINTENANCE'` | VALID |
| Partitionnement | `SELECT partition_count FROM user_part_tables WHERE table_name IN ('EXECUTIONS','EXECUTION_STEPS','AUDIT_LOG')` | 3 tables partitionnées |

---

## 10. Procédure de déploiement — Baseline vs Incrémental

### 10.1 Environnements existants (dev, staging, prod)

> **Aucun changement.** Les environments existants continuent d'utiliser la chaîne V000–V088 sans modification.

```bash
# Comportement normal — aucune action requise
flyway migrate  # Applique uniquement les nouvelles migrations (V089+ futures)
```

### 10.2 Nouveaux environnements

**Étape 1 : Appliquer le script baseline via SQL*Plus**
```bash
# Appliquer le script DDL directement sur la base vierge
sqlplus idp_user/password@NEW_ENV:1521/XEPDB1 @database/baseline/baseline_schema_v083.sql

# Puis déclarer à Flyway que la base est déjà au niveau V083
flyway -url=jdbc:oracle:thin:@NEW_ENV:1521/XEPDB1 \
       -baselineVersion=83 \
       -baselineDescription=baseline_schema_v083 \
       baseline
```

> **Note :** Le script baseline **ne doit pas** être placé dans `migrations/` — les versions Flyway doivent être numériques. Il est appliqué via SQL*Plus en dehors du mécanisme Flyway.

**Étape 2 : Appliquer les migrations incrémantales**
```bash
flyway -url=jdbc:oracle:thin:@NEW_ENV:1521/XEPDB1 migrate
# Applique automatiquement V084, V085, V086, V087, V088
```

**Étape 3 : Valider**
```bash
flyway -url=jdbc:oracle:thin:@NEW_ENV:1521/XEPDB1 info
# Doit afficher : baseline + V084-V088 : Success
```

### 10.3 Rollback post-déploiement (si nécessaire)

Les rollbacks sont disponibles uniquement pour les scripts de partitionnement :

```text
idp-portal/database/rollback/
  V084__partition_executions_rollback.sql
  V085__partition_execution_steps_rollback.sql
  V086__partition_audit_log_rollback.sql
  V087__create_purge_procedure_rollback.sql
```

> **Attention :** Le rollback des partitionnements est destructif (DROP TABLE PARTITION). Toujours sauvegarder les données avant rollback sur un environnement non-vierge.

---

*Document généré dans le cadre de la Story 41-1 — Audit des migrations existantes et stratégie de consolidation*
*Prochaine étape : Story 41-2 — Implémentation du script de baseline V001_consolidated__baseline_schema_v083.sql*
