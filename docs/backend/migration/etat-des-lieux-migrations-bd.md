# État des lieux — Migrations de bases de données IDP Portal

**Date :** 2026-03-10  
**Périmètre :** Django migrations, Flyway migrations, baseline schéma Oracle

---

## 1. Vue d'ensemble

| Composant | Emplacement | Version actuelle | Rôle |
|-----------|-------------|------------------|------|
| **Flyway** | `idp-portal/database/migrations/` | V000–V117 (118 scripts) | Schéma Oracle en production |
| **Baseline** | `idp-portal/database/baseline/baseline_schema_v088.sql` | État V116 | Nouveaux environnements vierges |
| **Django** | `idp-portal/django_backend/*/migrations/` | 69 migrations (8 apps) | Tests SQLite + mapping ORM Oracle |

---

## 2. Flyway — Inventaire

### 2.1 Périmètre

- **118 scripts** : `V000__create_schema_version.sql` → `V117__add_missing_audit_types_align_django.sql`
- **Commande** : `flyway migrate` (via `scripts/run_migrations.sh` ou `flyway.conf`)
- **Historique** : table `flyway_schema_history`

### 2.2 Dernières migrations (V089–V117)

| Version | Description |
|---------|-------------|
| V089 | create_auth_user (Django admin) |
| V090 | create_django_session |
| V091 | create_api_keys |
| V092 | create_auth_group_and_user_groups |
| V093 | create_content_type_permission_user_permissions |
| V094 | add_service_login_audit_type |
| V095 | add_email_to_users |
| V096 | (entity types audit) |
| V097 | drop_check_execution_env_v2 |
| V098 | add_integration_health_check_columns |
| V099 | add_approval_fields_and_new_step_types |
| V100 | add_integration_health_check_tested_audit_type |
| V101 | align_executions_approved_at_timestamp |
| V102 | convert_execution_steps_approved_at_to_timestamp |
| V103 | add_scheduled_execution_celery_triggered_audit_type |
| V104 | add_workflow_step_schedule_audit_type |
| V105 | add_is_approver_to_profiles |
| V106 | add_source_execution_id_to_scheduled_executions |
| V107 | add_schedule_execution_step_type |
| V108 | migrate_change_type_config_to_execution_steps |
| V109 | drop_change_type_config_gate_config_from_actions |
| V110 | add_auth_dev_bypass_and_workflow_schedule_audit_types |
| V111 | create_output_schemas_table |
| V112 | add_iac_sync_tracking_columns |
| V113 | optimize_indexes_add_workflow_events_and_runnable_steps |
| V114 | add_iac_config_sync_audit_types |
| V115 | add_output_schema_id_to_actions_catalog |
| V116 | add_config_step_id_to_execution_steps |
| V117 | add_missing_audit_types_align_django |

---

## 3. Baseline — Alignement

### 3.1 Nommage

| Élément | Valeur | Note |
|--------|--------|------|
| Fichier | `baseline_schema_v088.sql` | Nom historique (Epic 41-2) |
| État réel | V000–V116 | Couvert intégralement |
| Commande Flyway | `flyway baseline -baselineVersion=116 -baselineDescription=baseline_schema_v088` | |

**Incohérence** : Le nom du fichier (`v088`) ne reflète pas l’état actuel (V116). Le README du baseline précise que le script couvre V000–V116.

### 3.2 Contenu baseline

- **28 tables** (dont EXECUTIONS, EXECUTION_STEPS, AUDIT_LOG partitionnées)
- **WORKFLOW_EVENTS**, **RUNNABLE_STEPS** (V113)
- **OUTPUT_SCHEMAS** (V111), **OUTPUT_SCHEMA_ID** sur ACTIONS_CATALOG (V115)
- **CONFIG_STEP_ID** sur EXECUTION_STEPS (V116)
- **LAST_SYNCED_AT**, **LAST_SYNCED_HASH** sur 8 tables (V112)
- Trigger **TRG_AUDIT_LOG_IMMUTABLE**, package **PKG_IDP_MAINTENANCE**

### 3.3 Procédure nouveaux environnements

1. `sqlplus ... @database/baseline/baseline_schema_v088.sql`
2. `flyway baseline -baselineVersion=116 -baselineDescription=baseline_schema_v088`
3. `flyway migrate` (pour V117+ futures)

---

## 4. Django migrations — Rôle et alignement

### 4.1 Stratégie (MIGRATION_STRATEGY.md)

- **Production** : Flyway gère le schéma Oracle
- **Django** : `managed = True` avec `db_table` mappé aux tables Oracle
- **Tests** : SQLite avec migrations Django réelles
- **Oracle** : `manage.py migrate --fake-initial` (tables déjà créées par Flyway)

### 4.2 Apps et migrations Django

| App | Migrations | Équivalent Flyway |
|-----|------------|-------------------|
| catalog | 0001–0015 | V002, V014, V056, V070, V074–076, V080–082, V108–109, V112, V115 |
| core | 0001–0010 | V004, V028+, V062, V100, V110, V112, V114 |
| executions | 0001–0011 | V023–025, V030, V033, V057, V063, V066–067, V084–086, V099, V106, V107, V108, V113, V116 |
| idp_auth | 0001–0003 | V001, V091, V095 |
| integrations | 0001–0009 | V020, V024, V026, V061, V064, V077, V088, V098, V112 |
| output_schemas | 0001 | V111 |
| profiles | 0001–0005 | V010, V060, V071, V105, V112 |
| reference | 0001–0006 | V049, V059, V078, V083, V112 |

### 4.3 Migrations Django sans équivalent Flyway direct

| Migration | Type | Commentaire |
|-----------|------|--------------|
| `core/0009_add_scheduled_execution_recurring_enabled_audit_type` | DDL (choices) | **Résolu** : V117 aligne `CK_AUDIT_LOG_ACTION_TYPE` Oracle avec Django |
| `reference/0004_refengine_icon_url_fix_paths` | DML (RunPython) | Correction de chemins d’icônes — pas de script Flyway |

---

## 5. Écarts et risques

### 5.1 SCHEDULED_EXECUTION_RECURRING_ENABLED — Résolu (V117)

- **Django** : `core/migrations/0009` ajoute ce type d’audit (Story 66-16)
- **Résolution** : `V117__add_missing_audit_types_align_django.sql` a ajouté `SCHEDULED_EXECUTION_RECURRING_ENABLED` à `CK_AUDIT_LOG_ACTION_TYPE` Oracle (2026-03-10)

### 5.2 Types d’audit Django — Résolus (V117)

Les types suivants (présents dans Django `core/0009`) ont été ajoutés à `CK_AUDIT_LOG_ACTION_TYPE` par **V117** :

- `EXECUTION_STEP_POLICY_APPROVAL_REQUIRED`
- `EXECUTION_STEP_POLICY_AUTO_APPROVED`
- `EXECUTION_STEP_POLICY_EVALUATION_FAILED`
- `POLICY_CREATED`, `POLICY_UPDATED`, `POLICY_DELETED`
- `EXECUTION_POLLING_EXHAUSTED`

Aucun écart ouvert restant pour ces types.

### 5.3 reference/0004 — Migration DML

- **Rôle** : correction des chemins `icon_url` pour REF_ENGINES (Story 31.3)
- **Type** : `RunPython` (données uniquement)
- **Flyway** : pas d’équivalent — corrections appliquées via fixtures ou manuellement
- **Risque** : faible (données de référence, pas de schéma)

---

## 6. Documentation obsolète

| Document | Contenu obsolète (historique) | Statut |
|----------|------------------------------|--------|
| `docs/backend/database-schema.md` | "45 migrations V000–V044" | OK — 118 migrations V000–V117 (2026-03-10) |
| `django_backend/MIGRATION_STRATEGY.md` | "V041 dernière migration Flyway" | OK — V117 (2026-03-10) |
| `docs/backend/schema-differences.md` | CHANGE_TYPE_CONFIG dans ACTIONS_CATALOG | OK — colonne supprimée V109, doc à jour (2026-03-10) |
| `docs/backend/migration/migration-audit-epic41.md` | Périmètre V000–V088 | À mettre à jour — étendre à V117 |

---

## 7. Checklist d’alignement

| Vérification | Statut |
|--------------|--------|
| Baseline couvre V000–V116 | OK |
| Nom fichier baseline vs version | Incohérence (v088 vs V116) — documentée |
| Django migrations ↔ Flyway (schéma) | OK — V117 créée (2026-03-10) |
| Types audit Django vs CK_AUDIT_LOG_ACTION_TYPE | OK — V117 aligne tous les types |
| Documentation versions | OK — mise à jour 2026-03-10 |

---

## 8. Modifications effectuées (2026-03-10)

1. **V117 créée** : `V117__add_missing_audit_types_align_django.sql` — ajoute SCHEDULED_EXECUTION_RECURRING_ENABLED, EXECUTION_STEP_POLICY_*, POLICY_*, EXECUTION_POLLING_EXHAUSTED à `CK_AUDIT_LOG_ACTION_TYPE`.
2. **Documentation mise à jour** : `database-schema.md`, `MIGRATION_STRATEGY.md`, `schema-differences.md`, `database/baseline/README.md`.

---

## 9. Références

- `idp-portal/database/baseline/README.md`
- `idp-portal/django_backend/MIGRATION_STRATEGY.md`
- `docs/backend/migration/migration-audit-epic41.md`
- `docs/backend/onboarding/django-migration-guide.md` — "Les migrations DB restent gérées par Flyway"
