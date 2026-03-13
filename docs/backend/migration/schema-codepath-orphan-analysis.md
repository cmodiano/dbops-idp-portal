# Analyse : Colonnes et tables obsolètes — Schéma Flyway vs codepath Django

**Date :** 2026-03-13  
**Objectif :** Comparer le schéma Flyway (baseline V000–V119) au codepath Django pour identifier tables et colonnes créées dans le passé mais non utilisées aujourd'hui.

---

## 1. Résumé exécutif

| Catégorie | Nombre | Action recommandée |
|-----------|--------|--------------------|
| **Tables entièrement obsolètes** | 2 | Migration Flyway pour DROP |
| **Index obsolètes** | 1 | Migration Flyway pour DROP |
| **Colonnes dépréciées (conservées)** | 3 | Documentées, suppression future |
| **Tables utilisées** | 34+ | Aucune action |

---

## 2. Tables obsolètes — Aucun codepath Django

### 2.1 EXECUTION_LOG (V006)

| Attribut | Valeur |
|----------|--------|
| **Migration** | V006 `create_execution_log` |
| **Colonnes** | ID, ACTION_ID, USER_ID, ENVIRONMENT, STARTED_AT, COMPLETED_AT, STATUS |
| **Rôle historique** | Suivi des exécutions pour le tableau de bord (Story 2.4) |
| **Remplacement** | Table `EXECUTIONS` (V023) — source de vérité actuelle |

**Preuve :**
- Le dashboard (`dashboard/views/stats.py`, `executions/services.py`) utilise exclusivement `Execution.objects` (table EXECUTIONS)
- Aucun modèle Django ne mappe `EXECUTION_LOG`
- Aucune requête SQL brute ne référence `EXECUTION_LOG`
- Documentation `migration-audit-epic41.md` : *"Table legacy simple (jamais droppée)"*

**Recommandation :** Créer une migration Flyway `V121__drop_execution_log.sql` pour supprimer la table. Vérifier qu'aucune donnée critique n'y réside (probablement vide ou données très anciennes).

---

### 2.2 USER_PERMISSIONS (V005)

| Attribut | Valeur |
|----------|--------|
| **Migration** | V005 `create_user_permissions` |
| **Colonnes** | USER_ID, ACTION_ID, ENVIRONMENT, GRANTED_BY, GRANTED_AT |
| **Rôle historique** | RBAC par action/environnement (Story 1.3) |
| **Remplacement** | `PROFILES` + `PROFILE_ACTION_PERMISSIONS` + `PROFILE_TARGET_PERMISSIONS` (V010–V012, Story 2-9 à 2-14) |

**Preuve :**
- Story 2-14 : *"refactoring supprimer ancien RBAC par action"* — migration vers profils dynamiques
- Aucun modèle Django ne mappe `USER_PERMISSIONS`
- Le RBAC actuel passe par `CatalogRBACService`, `ProfileActionPermission`, `ProfileTargetPermission`
- Aucune référence à `USER_PERMISSIONS` dans le code Python

**Recommandation :** Créer une migration Flyway `V122__drop_user_permissions.sql` pour supprimer la table. Vérifier qu'aucune donnée n'est encore utilisée (migration 2-14 a dû migrer les données).

---

## 3. Index obsolète

### 3.1 IDX_EXECUTIONS_PENDING_APPROVAL

| Attribut | Valeur |
|----------|--------|
| **Table** | EXECUTIONS |
| **Définition** | `CASE WHEN STATUS = 'PENDING_APPROVAL' THEN ID END` |
| **Contexte** | ADR-007 (Story 57.12) : le statut `PENDING_APPROVAL` est **déprécié** |

**Preuve :**
- `ExecutionStatus.PENDING_APPROVAL` : *"DEPRECATED (ADR-007) — kept for Oracle DB CHECK constraint compatibility"*
- Les approbations sont désormais gérées via `ExecutionStep` (gates WAITING)
- Le modèle `Execution` : *"Legacy PENDING_APPROVAL status is no longer used"*

**Recommandation :** Créer une migration pour `DROP INDEX IDX_EXECUTIONS_PENDING_APPROVAL` (ou inclure dans une migration de cleanup). L'index consomme de l'espace et n'est plus utile si aucun nouvel enregistrement n'utilise ce statut.

---

## 4. Colonnes dépréciées — Conservées pour rétrocompatibilité

Ces colonnes existent encore dans le schéma et le modèle Django, mais ne sont plus la source de vérité. Elles sont documentées comme dépréciées.

| Table | Colonne | Statut | Source de vérité actuelle |
|-------|---------|--------|---------------------------|
| EXECUTIONS | APPROVED_BY | Déprécié ADR-007 | ExecutionStep.approved_by |
| EXECUTIONS | APPROVED_AT | Déprécié ADR-007 | ExecutionStep.approved_at |
| EXECUTIONS | APPROVAL_COMMENT | Déprécié ADR-007 | ExecutionStep.approval_comment |

**Recommandation :** Ne pas supprimer immédiatement — les données historiques peuvent encore être lues. Planifier une migration future (ex. Epic dédiée) pour :
1. Migrer les données restantes vers ExecutionStep si nécessaire
2. Supprimer les colonnes et mettre à jour la contrainte CHECK `CHK_EXECUTION_STATUS` pour retirer `PENDING_APPROVAL`

---

## 5. Tables utilisées — Parité confirmée

Les tables suivantes ont un modèle Django correspondant et sont utilisées dans le codepath :

| Table Flyway | Modèle Django | App |
|--------------|---------------|-----|
| USERS | User | idp_auth |
| AUTH_USER | (Django auth) | django.contrib.auth |
| AUTH_GROUP | (Django auth) | django.contrib.auth |
| AUTH_USER_GROUPS | (Django auth) | django.contrib.auth |
| DJANGO_CONTENT_TYPE | (Django) | django.contrib.contenttypes |
| AUTH_PERMISSION | (Django auth) | django.contrib.auth |
| AUTH_USER_USER_PERMISSIONS | (Django auth) | django.contrib.auth |
| API_KEYS | APIKey | idp_auth |
| DJANGO_SESSION | (Django sessions) | django.contrib.sessions |
| TAGS | Tag | catalog |
| PROFILES | Profile | profiles |
| INTEGRATIONS | Integration | integrations |
| REF_ENGINES | RefEngine | reference |
| REF_CATEGORIES | RefCategory | reference |
| INTEGRATION_TYPE_CATALOGUE | IntegrationTypeCatalogue | integrations |
| CORE_FEATURE_FLAGS | FeatureFlag | core |
| BUSINESS_RULE_POLICIES | BusinessRulePolicy | catalog |
| OUTPUT_SCHEMAS | OutputSchema | output_schemas |
| ACTIONS_CATALOG | Action | catalog |
| ACTION_TAGS | ActionTag | catalog |
| USER_FAVORITES | UserFavorite | catalog |
| ACTION_MUTEX | ActionMutex | catalog |
| PROFILE_ACTION_PERMISSIONS | ProfileActionPermission | profiles |
| PROFILE_TARGET_PERMISSIONS | ProfileTargetPermission | profiles |
| INTEGRATION_ACTIONS | IntegrationAction | integrations |
| AUDIT_LOG | AuditLog | core |
| EXECUTIONS | Execution | executions |
| EXECUTION_STEPS | ExecutionStep | executions |
| EXECUTION_TARGETS | ExecutionTarget | executions |
| SCHEDULED_EXECUTIONS | ScheduledExecution | executions |
| RECURRING_PATTERNS | RecurringPattern | executions |
| WORKFLOW_EVENTS | WorkflowEvent | executions |
| RUNNABLE_STEPS | RunnableStep | executions |
| IDP_MAINTENANCE_LOG | (pas de modèle — table technique) | — |

---

## 6. Colonnes supprimées historiquement (déjà droppées)

Ces colonnes/tables ont déjà été supprimées par des migrations Flyway antérieures — pas d'action requise :

| Élément | Migration de suppression |
|---------|---------------------------|
| SCHEMA_VERSION | V015 |
| RBAC_POLICIES (colonne ACTIONS_CATALOG) | V013 |
| CHANGE_MODEL_CODE (colonne ACTIONS_CATALOG) | V019 |
| CHANGE_TYPE_CONFIG (colonne ACTIONS_CATALOG) | V109 |
| GATE_CONFIG (colonne ACTIONS_CATALOG) | V109 |
| REF_PLATFORMS (table) | V083 |
| CK_ACTIONS_CATALOG_CATEGORY | V018 |
| CK_ACTIONS_CATALOG_ENGINE | V050 |
| CK_ACTIONS_CATALOG_PLATFORM | V052 |

---

## 7. Plan d'action recommandé

### Phase 1 — Validation préalable (avant toute suppression)

1. **EXECUTION_LOG**  
   - Exécuter `SELECT COUNT(*) FROM EXECUTION_LOG` sur chaque environnement  
   - Si données présentes : décider archivage ou perte acceptable  
   - Vérifier qu'aucun script externe (Splunk, monitoring) ne lit cette table  

2. **USER_PERMISSIONS**  
   - Exécuter `SELECT COUNT(*) FROM USER_PERMISSIONS`  
   - Confirmer que Story 2-14 a migré toutes les données vers PROFILES  

### Phase 2 — Migrations Flyway

1. ~~Créer `V121__drop_execution_log.sql`~~ → **Créé** : `V121__drop_legacy_tables_and_index.sql` (regroupe les 3 suppressions)
2. ~~Créer `V122__drop_user_permissions.sql`~~ → Inclus dans V121
3. ~~Créer `V123__drop_idx_executions_pending_approval.sql`~~ → Inclus dans V121  

### Phase 3 — Mise à jour baseline

- Si baseline `baseline_flyway.sql` est régénéré manuellement : retirer EXECUTION_LOG et USER_PERMISSIONS du script  
- Mettre à jour `database/baseline/README.md` et `docs/backend/migration/etat-des-lieux-migrations-bd.md`  

---

## 8. Références

- `idp-portal/database/baseline/baseline_flyway.sql`
- `idp-portal/django_backend/*/models.py` (catalog, executions, profiles, core, integrations, reference, idp_auth, output_schemas)
- `docs/backend/migration/migration-audit-epic41.md`
- `docs/backend/migration/etat-des-lieux-migrations-bd.md`
- Story 2-14 : refactoring supprimer ancien RBAC par action
- ADR-007 : Migration approbations vers ExecutionStep
