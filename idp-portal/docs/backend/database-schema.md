# Schéma de Base de Données et Relations Tables

## Vue d'ensemble

Le portail IDP utilise **Oracle Database** avec **13 tables principales** organisées en **6 domaines fonctionnels**. Le schéma est géré par **Flyway** (45 migrations: V000 à V044) avec cohabitation Django ORM.

### Caractéristiques techniques

| Aspect | Détail |
|--------|--------|
| **SGBD** | Oracle Database 19c+ |
| **Gestion migrations** | Flyway 9.x (prod) + Django Migrations (dev) |
| **Convention nommage** | UPPER_SNAKE_CASE (tables, colonnes) |
| **Clés primaires** | `IDENTITY` columns (pas de séquences) |
| **JSON** | Stocké en CLOB, sérialisé via helpers Django |
| **Booléens** | `NUMBER(1) CHECK (0, 1)` |

---

## Diagramme ER Complet

```
                                       ┌──────────────────────┐
                                       │       USERS          │
                                       ├──────────────────────┤
                                       │ ID (PK, IDENTITY)    │
                                       │ USERNAME (UK)        │
                                       │ DISPLAY_NAME         │
                                       │ PROFILE              │
                                       │ SAML_SUBJECT         │
                                       │ CREATED_AT           │
                                       │ UPDATED_AT           │
                                       └──────────┬───────────┘
                                                  │
            ┌─────────────────────────────────────┼─────────────────────────────────────┐
            │                                     │                                     │
            │                                     │                                     │
            ▼                                     ▼                                     ▼
  ┌─────────────────┐              ┌──────────────────────┐              ┌──────────────────────┐
  │  USER_FAVORITES │              │     EXECUTIONS       │              │ SCHEDULED_EXECUTIONS │
  ├─────────────────┤              ├──────────────────────┤              ├──────────────────────┤
  │ ID (PK)         │              │ ID (PK, IDENTITY)    │              │ ID (PK, IDENTITY)    │
  │ USER_ID (FK) ───┼──────────────│ USER_ID (FK) ────────┼──────────────│ USER_ID (FK)         │
  │ ACTION_ID (FK)  │              │ ACTION_ID (FK)       │              │ ACTION_ID (FK)       │
  │ CREATED_AT      │              │ ENVIRONMENT          │              │ ENVIRONMENT          │
  └────────┬────────┘              │ PARAMETERS (CLOB)    │              │ PARAMETERS (CLOB)    │
           │                       │ STATUS               │              │ SCHEDULED_AT         │
           │                       │ SERVICENOW_CHANGE_ID │              │ STATUS               │
           │                       │ APPROVED_BY (FK) ────┼──┐           │ CORRELATION_ID       │
           │                       │ APPROVED_AT          │  │           │ EXECUTION_ID         │
           │                       │ APPROVAL_COMMENT     │  │           └──────────┬───────────┘
           │                       │ PARENT_EXEC_ID (FK)◄─┼──┼──┐                   │
           │                       │ STARTED_AT           │  │  │                   │
           │                       │ COMPLETED_AT         │  │  │        ┌──────────▼───────────┐
           │                       │ CREATED_AT           │  │  │        │  RECURRING_PATTERNS  │
           │                       └──────────┬───────────┘  │  │        ├──────────────────────┤
           │                                  │              │  │        │ ID (PK, IDENTITY)    │
           │                                  │ 1:N          │  │        │ SCHED_EXEC_ID (FK,UK)│
           │                                  ▼              │  │        │ PATTERN_TYPE         │
           │                       ┌──────────────────────┐  │  │        │ PATTERN_CONFIG (CLOB)│
           │                       │   EXECUTION_STEPS    │  │  │        │ NEXT_EXECUTION_DATE  │
           │                       ├──────────────────────┤  │  │        │ IS_ACTIVE            │
           │                       │ ID (PK, IDENTITY)    │  │  │        │ CREATED_AT           │
           │                       │ EXECUTION_ID (FK)    │  │  │        │ UPDATED_AT           │
           │                       │ STEP_ORDER           │  │  │        └──────────────────────┘
           │                       │ STEP_NAME            │  │  │
           │                       │ STEP_TYPE            │  │  │   Self-reference
           │                       │ STATUS               │  │  │   (remédiation)
           │                       │ STARTED_AT           │  │  │
           │                       │ COMPLETED_AT         │  │  │
           │                       │ OUTPUT (CLOB)        │  │  │
           │                       │ PLATFORM_JOB_ID      │  │  │
           │                       │ ERROR_MESSAGE (CLOB) │  │  │
           │                       │ CREATED_AT           │  │  │
           │                       └──────────────────────┘  │  │
           │                                                 │  │
           │         ┌───────────────────────────────────────┘  │
           │         │                                          │
           │         │  FK vers USERS                           │
           │         │  (approved_by)                           │
           ▼         ▼                                          │
┌─────────────────────────────────┐              ┌──────────────────────┐
│       ACTIONS_CATALOG           │◄─────────────│    INTEGRATIONS      │
├─────────────────────────────────┤     FK       ├──────────────────────┤
│ ID (PK, IDENTITY)               │              │ ID (PK, IDENTITY)    │
│ NAME (UK)                       │              │ TYPE                 │
│ DESCRIPTION                     │              │ NAME (UK)            │
│ CATEGORY                        │              │ BASE_URL             │
│ ENGINE (nullable)               │              │ CREDENTIAL_REF       │
│ PLATFORM (nullable)             │              │ ICON                 │
│ PARAMETERS_SCHEMA (CLOB)        │              │ AUTH_FLOW            │
│ IMPACT_RULES (CLOB)             │              │ TOKEN_URL            │
│ EXECUTION_STEPS (CLOB)          │              │ CONFIG (CLOB)        │
│ CHANGE_TYPE_CONFIG (CLOB)       │              │ CREATED_AT           │
│ DOCUMENTATION_MD (CLOB)         │              │ UPDATED_AT           │
│ REMEDIATION_RULES (CLOB)        │              └──────────────────────┘
│ DEFAULT_IMPACT_LEVEL            │
│ STATUS                          │
│ ITEM_TYPE                       │
│ CREATED_BY (FK → USERS)         │
│ INTEGRATION_ID (FK → INTEGRATIONS)
│ CREATED_AT                      │
│ UPDATED_AT                      │
└─────────────┬───────────────────┘
              │
              │ 1:N (via ACTION_TAGS)
              ▼
    ┌─────────────────┐          ┌──────────────────────┐
    │   ACTION_TAGS   │──────────│        TAGS          │
    ├─────────────────┤   N:1    ├──────────────────────┤
    │ ID (PK)         │          │ ID (PK, IDENTITY)    │
    │ ACTION_ID (FK)  │          │ NAME (UK)            │
    │ TAG_ID (FK)     │          │ CREATED_AT           │
    └─────────────────┘          └──────────────────────┘
    (UK: ACTION_ID, TAG_ID)


┌──────────────────────┐          ┌──────────────────────────────────┐
│      PROFILES        │          │   PROFILE_ACTION_PERMISSIONS     │
├──────────────────────┤   1:1    ├──────────────────────────────────┤
│ ID (PK, IDENTITY)    │◄─────────│ PROFILE_ID (PK, FK)              │
│ NAME (UK)            │          │ PERMISSION_TYPE                  │
│ DESCRIPTION          │          │ ACTION_IDS_JSON (CLOB)           │
│ AD_GROUP             │          │ TAG_PATTERNS_JSON (CLOB)         │
│ IS_ADMIN             │          │ ENVIRONMENTS_JSON (CLOB)         │
│ IS_AUDITOR           │          │ CREATED_AT                       │
│ CREATED_AT           │          │ UPDATED_AT                       │
│ UPDATED_AT           │          └──────────────────────────────────┘
└──────────┬───────────┘
           │
           │   1:1    ┌──────────────────────────────────┐
           └──────────│   PROFILE_TARGET_PERMISSIONS     │
                      ├──────────────────────────────────┤
                      │ PROFILE_ID (PK, FK)              │
                      │ PERMISSION_TYPE                  │
                      │ TARGET_NAMES_JSON (CLOB)         │
                      │ TARGET_PATTERNS_JSON (CLOB)      │
                      │ CREATED_AT                       │
                      │ UPDATED_AT                       │
                      └──────────────────────────────────┘


┌──────────────────────────────────┐
│          AUDIT_LOG               │     ⚠️ APPEND-ONLY
├──────────────────────────────────┤     (pas de UPDATE/DELETE)
│ ID (PK, IDENTITY)                │
│ TIMESTAMP                        │
│ USER_ID (VARCHAR, pas FK)        │
│ ACTION_TYPE                      │
│ ENTITY_TYPE                      │
│ ENTITY_ID                        │
│ DETAILS (CLOB)                   │
│ IP_ADDRESS                       │
│ CORRELATION_ID                   │
└──────────────────────────────────┘
```

---

## Description détaillée des tables

### 1. Domaine Utilisateurs (idp_auth)

#### USERS (V001)

Table des utilisateurs authentifiés via SAML.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| ID | NUMBER | PK, IDENTITY | Identifiant unique auto-généré |
| USERNAME | VARCHAR2(255) | UNIQUE, NOT NULL | Nom d'utilisateur (email) |
| DISPLAY_NAME | VARCHAR2(255) | NULL | Nom affiché |
| PROFILE | VARCHAR2(50) | NOT NULL | Profil legacy (deprecated, utiliser PROFILES) |
| SAML_SUBJECT | VARCHAR2(512) | NULL | Identifiant SAML |
| CREATED_AT | TIMESTAMP | DEFAULT SYSTIMESTAMP | Date de création |
| UPDATED_AT | TIMESTAMP | NULL | Date de mise à jour |

**Index:** `IDX_USERS_USERNAME` (unique)

**Requêtes courantes:**
```sql
-- Trouver un utilisateur par username
SELECT * FROM USERS WHERE USERNAME = 'john.doe@example.com';

-- Lister les utilisateurs créés ce mois
SELECT * FROM USERS WHERE CREATED_AT >= TRUNC(SYSDATE, 'MM');
```

**Modèle Django:** `idp_auth/models.py:50` - `class User`

---

### 2. Domaine Profils et RBAC (profiles)

#### PROFILES (V010)

Table des profils liés aux groupes AD.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| ID | NUMBER | PK, IDENTITY | Identifiant unique |
| NAME | VARCHAR2(255) | UNIQUE, NOT NULL | Nom du profil |
| DESCRIPTION | VARCHAR2(4000) | NULL | Description |
| AD_GROUP | VARCHAR2(512) | NOT NULL | Groupe Active Directory |
| IS_ADMIN | NUMBER(1) | DEFAULT 0, CHECK (0,1) | Profil administrateur |
| IS_AUDITOR | NUMBER(1) | DEFAULT 0, CHECK (0,1) | Profil auditeur |
| CREATED_AT | TIMESTAMP | DEFAULT SYSTIMESTAMP | Date de création |
| UPDATED_AT | TIMESTAMP | NULL | Date de mise à jour |

**Relations:**
- `PROFILE_ACTION_PERMISSIONS` (1:1)
- `PROFILE_TARGET_PERMISSIONS` (1:1)

**Requêtes courantes:**
```sql
-- Profils admin
SELECT * FROM PROFILES WHERE IS_ADMIN = 1;

-- Profils d'un utilisateur (via ses AD groups)
SELECT p.* FROM PROFILES p
WHERE p.AD_GROUP IN ('CN=DBAs,OU=Groups,DC=corp', 'CN=DevOps,OU=Groups,DC=corp');
```

**Modèle Django:** `profiles/models.py:94` - `class Profile`

---

#### PROFILE_ACTION_PERMISSIONS (V011)

Permissions d'actions par profil (relation 1:1 avec PROFILES).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| PROFILE_ID | NUMBER | PK, FK → PROFILES.ID ON DELETE CASCADE | Profil associé |
| PERMISSION_TYPE | VARCHAR2(20) | CHECK ('LIST', 'PATTERN', 'ALL') | Type de permission |
| ACTION_IDS_JSON | CLOB | NULL | JSON array d'IDs d'actions (si LIST) |
| TAG_PATTERNS_JSON | CLOB | NULL | JSON array de patterns (si PATTERN) |
| ENVIRONMENTS_JSON | CLOB | NULL | JSON array d'environnements autorisés |
| CREATED_AT | TIMESTAMP | DEFAULT SYSTIMESTAMP | Date de création |
| UPDATED_AT | TIMESTAMP | NULL | Date de mise à jour |

**Contrainte métier:**
- `permission_type = 'LIST'` → utilise `action_ids_json`
- `permission_type = 'PATTERN'` → utilise `tag_patterns_json`
- `permission_type = 'ALL'` → accès complet

**Requêtes courantes:**
```sql
-- Permissions d'actions d'un profil
SELECT * FROM PROFILE_ACTION_PERMISSIONS WHERE PROFILE_ID = 1;

-- Profils avec permission de type LIST
SELECT p.NAME, pap.PERMISSION_TYPE FROM PROFILES p
JOIN PROFILE_ACTION_PERMISSIONS pap ON p.ID = pap.PROFILE_ID
WHERE pap.PERMISSION_TYPE = 'LIST';
```

**Modèle Django:** `profiles/models.py:119` - `class ProfileActionPermission`

---

#### PROFILE_TARGET_PERMISSIONS (V012)

Permissions de targets par profil (relation 1:1 avec PROFILES).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| PROFILE_ID | NUMBER | PK, FK → PROFILES.ID ON DELETE CASCADE | Profil associé |
| PERMISSION_TYPE | VARCHAR2(20) | CHECK ('LIST', 'PATTERN', 'ALL') | Type de permission |
| TARGET_NAMES_JSON | CLOB | NULL | JSON array de noms de targets (si LIST) |
| TARGET_PATTERNS_JSON | CLOB | NULL | JSON array de patterns (si PATTERN) |
| CREATED_AT | TIMESTAMP | DEFAULT SYSTIMESTAMP | Date de création |
| UPDATED_AT | TIMESTAMP | NULL | Date de mise à jour |

**Requêtes courantes:**
```sql
-- Permissions de targets d'un profil
SELECT * FROM PROFILE_TARGET_PERMISSIONS WHERE PROFILE_ID = 1;

-- Profils avec accès ALL (pas de restriction target)
SELECT p.NAME FROM PROFILES p
JOIN PROFILE_TARGET_PERMISSIONS ptp ON p.ID = ptp.PROFILE_ID
WHERE ptp.PERMISSION_TYPE = 'ALL';
```

**Modèle Django:** `profiles/models.py:205` - `class ProfileTargetPermission`

---

### 3. Domaine Catalogue (catalog)

#### ACTIONS_CATALOG (V002, V014, V017, V019, V022, V027, V031, V036, V037)

Table principale du catalogue d'actions.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| ID | NUMBER | PK, IDENTITY | Identifiant unique |
| NAME | VARCHAR2(255) | UNIQUE, NOT NULL | Nom de l'action |
| DESCRIPTION | VARCHAR2(4000) | NULL | Description |
| CATEGORY | VARCHAR2(50) | CHECK (...) | Catégorie |
| ENGINE | VARCHAR2(50) | NULL, CHECK (...) | Moteur DB (nullable depuis V037) |
| PLATFORM | VARCHAR2(50) | NULL, CHECK (...) | Plateforme (nullable depuis V037) |
| PARAMETERS_SCHEMA | CLOB | NULL | JSON Schema des paramètres |
| IMPACT_RULES | CLOB | NULL | Règles d'impact JSON |
| EXECUTION_STEPS | CLOB | NULL | Étapes d'exécution JSON |
| CHANGE_TYPE_CONFIG | CLOB | NULL | Config changement par env (V019) |
| DOCUMENTATION_MD | CLOB | NULL | Documentation Markdown (V022) |
| REMEDIATION_RULES | CLOB | NULL | Règles de remédiation (V031) |
| DEFAULT_IMPACT_LEVEL | VARCHAR2(20) | NULL, CHECK (...) | Niveau d'impact par défaut (V014) |
| STATUS | VARCHAR2(20) | DEFAULT 'draft', CHECK (...) | Statut |
| ITEM_TYPE | VARCHAR2(20) | DEFAULT 'action', CHECK (...) | Type (V027) |
| CREATED_BY | NUMBER | FK → USERS.ID ON DELETE SET NULL | Créateur |
| INTEGRATION_ID | NUMBER | FK → INTEGRATIONS.ID ON DELETE SET NULL | Intégration (V036) |
| CREATED_AT | TIMESTAMP | DEFAULT SYSTIMESTAMP | Date de création |
| UPDATED_AT | TIMESTAMP | NULL | Date de mise à jour |

**Valeurs CHECK:**
- `CATEGORY`: 'Provisioning', 'Patching', 'Administration', 'Monitoring'
- `ENGINE`: 'Oracle', 'SQL Server', 'DB2'
- `PLATFORM`: 'AAP', 'GitHub Actions', 'Azure DevOps', 'Terraform'
- `STATUS`: 'draft', 'published', 'disabled'
- `ITEM_TYPE`: 'action', 'workflow'
- `DEFAULT_IMPACT_LEVEL`: 'low', 'medium', 'high', 'critical'

**Index:** `IDX_ACTIONS_STATUS`, `IDX_ACTIONS_CATEGORY`

**Requêtes courantes:**
```sql
-- Actions publiées
SELECT * FROM ACTIONS_CATALOG WHERE STATUS = 'published';

-- Actions d'une catégorie
SELECT * FROM ACTIONS_CATALOG
WHERE CATEGORY = 'Patching' AND STATUS = 'published';

-- Actions avec leurs tags
SELECT a.ID, a.NAME, LISTAGG(t.NAME, ', ') WITHIN GROUP (ORDER BY t.NAME) AS tags
FROM ACTIONS_CATALOG a
LEFT JOIN ACTION_TAGS at ON a.ID = at.ACTION_ID
LEFT JOIN TAGS t ON at.TAG_ID = t.ID
WHERE a.STATUS = 'published'
GROUP BY a.ID, a.NAME;
```

**Modèle Django:** `catalog/models.py:127` - `class Action`

---

#### TAGS (V007)

Table des tags pour catégoriser les actions.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| ID | NUMBER | PK, IDENTITY | Identifiant unique |
| NAME | VARCHAR2(255) | UNIQUE, NOT NULL | Nom du tag |
| CREATED_AT | TIMESTAMP | DEFAULT SYSTIMESTAMP | Date de création |

**Requêtes courantes:**
```sql
-- Tags les plus utilisés
SELECT t.NAME, COUNT(at.ACTION_ID) AS usage_count
FROM TAGS t
LEFT JOIN ACTION_TAGS at ON t.ID = at.TAG_ID
GROUP BY t.NAME
ORDER BY usage_count DESC;
```

**Modèle Django:** `catalog/models.py:295` - `class Tag`

---

#### ACTION_TAGS (V007, V042)

Table pivot pour la relation N:N entre ACTIONS_CATALOG et TAGS.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| ID | NUMBER | PK, IDENTITY (V042) | Identifiant unique (ajouté pour Django ORM) |
| ACTION_ID | NUMBER | NOT NULL, FK → ACTIONS_CATALOG.ID ON DELETE CASCADE | Action |
| TAG_ID | NUMBER | NOT NULL, FK → TAGS.ID ON DELETE CASCADE | Tag |

**Contrainte:** `UK_ACTION_TAGS (ACTION_ID, TAG_ID)` - unicité de la paire

**Note:** La colonne ID a été ajoutée en V042 pour compatibilité avec Django ORM qui requiert une PK explicite.

**Requêtes courantes:**
```sql
-- Tags d'une action
SELECT t.NAME FROM TAGS t
JOIN ACTION_TAGS at ON t.ID = at.TAG_ID
WHERE at.ACTION_ID = 42;

-- Associer un tag à une action (éviter doublon)
INSERT INTO ACTION_TAGS (ACTION_ID, TAG_ID)
SELECT 42, 5 FROM DUAL WHERE NOT EXISTS (
  SELECT 1 FROM ACTION_TAGS WHERE ACTION_ID = 42 AND TAG_ID = 5
);
```

**Modèle Django:** `catalog/models.py:312` - `class ActionTag`

---

#### USER_FAVORITES (V021, V043)

Table pivot pour les favoris utilisateur.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| ID | NUMBER | PK, IDENTITY (V043) | Identifiant unique (ajouté pour Django ORM) |
| USER_ID | NUMBER | NOT NULL, FK → USERS.ID ON DELETE CASCADE | Utilisateur |
| ACTION_ID | NUMBER | NOT NULL, FK → ACTIONS_CATALOG.ID ON DELETE CASCADE | Action favorite |
| CREATED_AT | TIMESTAMP | DEFAULT SYSTIMESTAMP | Date d'ajout |

**Contrainte:** `UK_USER_FAVORITES (USER_ID, ACTION_ID)` - unicité de la paire

**Requêtes courantes:**
```sql
-- Favoris d'un utilisateur
SELECT a.ID, a.NAME FROM ACTIONS_CATALOG a
JOIN USER_FAVORITES uf ON a.ID = uf.ACTION_ID
WHERE uf.USER_ID = 1;

-- Ajouter un favori
INSERT INTO USER_FAVORITES (USER_ID, ACTION_ID) VALUES (1, 42);
```

**Modèle Django:** `catalog/models.py:336` - `class UserFavorite`

---

### 4. Domaine Exécutions (executions)

#### EXECUTIONS (V023, V030, V033)

Table des exécutions d'actions.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| ID | NUMBER | PK, IDENTITY | Identifiant unique |
| ACTION_ID | NUMBER | NOT NULL, FK → ACTIONS_CATALOG.ID ON DELETE CASCADE | Action exécutée |
| USER_ID | NUMBER | NOT NULL, FK → USERS.ID ON DELETE CASCADE | Utilisateur demandeur |
| ENVIRONMENT | VARCHAR2(50) | NOT NULL, CHECK (...) | Environnement cible |
| PARAMETERS | CLOB | NULL | Paramètres d'exécution (JSON) |
| STATUS | VARCHAR2(20) | DEFAULT 'SUBMITTED', CHECK (...) | Statut |
| SERVICENOW_CHANGE_ID | VARCHAR2(100) | NULL | ID du changement ServiceNow |
| APPROVED_BY | NUMBER | NULL, FK → USERS.ID ON DELETE SET NULL | Approbateur (V030) |
| APPROVED_AT | TIMESTAMP | NULL | Date d'approbation (V030) |
| APPROVAL_COMMENT | VARCHAR2(1000) | NULL | Commentaire approbation (V030) |
| PARENT_EXECUTION_ID | NUMBER | NULL, FK → EXECUTIONS.ID ON DELETE SET NULL | Exécution parent pour remédiation (V033) |
| STARTED_AT | TIMESTAMP | NULL | Date de début |
| COMPLETED_AT | TIMESTAMP | NULL | Date de fin |
| CREATED_AT | TIMESTAMP | DEFAULT SYSTIMESTAMP | Date de création |

**Valeurs CHECK:**
- `ENVIRONMENT`: 'dev', 'staging', 'prod'
- `STATUS`: 'SUBMITTED', 'PENDING_APPROVAL', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'REJECTED'

**Index:** `IDX_EXECUTIONS_STATUS`, `IDX_EXECUTIONS_USER`, `IDX_EXECUTIONS_ACTION`

**Workflow de statuts:**
```
SUBMITTED ───► PENDING_APPROVAL (si approbation requise)
    │                 │
    │                 ├──► REJECTED (refusé)
    │                 │
    ▼                 ▼
RUNNING ◄────────────┘
    │
    ├──► COMPLETED
    ├──► FAILED
    └──► CANCELLED
```

**Requêtes courantes:**
```sql
-- Exécutions d'un utilisateur (récentes)
SELECT * FROM EXECUTIONS WHERE USER_ID = 1 ORDER BY CREATED_AT DESC FETCH FIRST 20 ROWS ONLY;

-- Exécutions en attente d'approbation
SELECT * FROM EXECUTIONS WHERE STATUS = 'PENDING_APPROVAL';

-- Exécutions d'une action
SELECT * FROM EXECUTIONS WHERE ACTION_ID = 42 ORDER BY CREATED_AT DESC;
```

**Modèle Django:** `executions/models.py:85` - `class Execution`

---

#### EXECUTION_STEPS (V025)

Table des étapes d'une exécution.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| ID | NUMBER | PK, IDENTITY | Identifiant unique |
| EXECUTION_ID | NUMBER | NOT NULL, FK → EXECUTIONS.ID ON DELETE CASCADE | Exécution parente |
| STEP_ORDER | NUMBER | NOT NULL | Ordre de l'étape |
| STEP_NAME | VARCHAR2(255) | NOT NULL | Nom de l'étape |
| STEP_TYPE | VARCHAR2(50) | NOT NULL, CHECK (...) | Type d'étape |
| STATUS | VARCHAR2(20) | DEFAULT 'PENDING', CHECK (...) | Statut |
| STARTED_AT | TIMESTAMP | NULL | Date de début |
| COMPLETED_AT | TIMESTAMP | NULL | Date de fin |
| OUTPUT | CLOB | NULL | Sortie (JSON) |
| PLATFORM_JOB_ID | VARCHAR2(255) | NULL | ID du job sur la plateforme |
| ERROR_MESSAGE | CLOB | NULL | Message d'erreur |
| CREATED_AT | TIMESTAMP | DEFAULT SYSTIMESTAMP | Date de création |

**Valeurs CHECK:**
- `STEP_TYPE`: 'vault', 'servicenow', 'platform', 'prerequisite', 'verification'
- `STATUS`: 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED'

**Contrainte:** `UK_EXECUTION_STEPS (EXECUTION_ID, STEP_ORDER)` - unicité

**Requêtes courantes:**
```sql
-- Étapes d'une exécution (ordre)
SELECT * FROM EXECUTION_STEPS WHERE EXECUTION_ID = 123 ORDER BY STEP_ORDER;

-- Étapes en échec
SELECT es.*, e.ACTION_ID FROM EXECUTION_STEPS es
JOIN EXECUTIONS e ON e.ID = es.EXECUTION_ID
WHERE es.STATUS = 'FAILED';
```

**Modèle Django:** `executions/models.py:196` - `class ExecutionStep`

---

#### SCHEDULED_EXECUTIONS (V038, V041)

Table des exécutions planifiées.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| ID | NUMBER | PK, IDENTITY | Identifiant unique |
| ACTION_ID | NUMBER | NOT NULL, FK → ACTIONS_CATALOG.ID ON DELETE CASCADE | Action à exécuter |
| USER_ID | NUMBER | NOT NULL, FK → USERS.ID ON DELETE CASCADE | Utilisateur planificateur |
| ENVIRONMENT | VARCHAR2(50) | NOT NULL, CHECK (...) | Environnement cible |
| PARAMETERS | CLOB | NULL | Paramètres (JSON) |
| SCHEDULED_AT | TIMESTAMP | NULL | Date planifiée (one-time) |
| STATUS | VARCHAR2(20) | DEFAULT 'pending', CHECK (...) | Statut |
| CORRELATION_ID | VARCHAR2(64) | NULL | ID de corrélation (V041) |
| EXECUTION_ID | NUMBER | NULL | ID de l'exécution effective (V041) |
| CREATED_AT | TIMESTAMP | DEFAULT SYSTIMESTAMP | Date de création |
| UPDATED_AT | TIMESTAMP | NULL | Date de mise à jour |

**Valeurs CHECK:**
- `ENVIRONMENT`: 'dev', 'staging', 'prod'
- `STATUS`: 'pending', 'executed', 'cancelled'

**Index:** `IDX_SCHEDULED_EXECUTIONS_STATUS`

**Requêtes courantes:**
```sql
-- Schedules en attente (scheduler externe)
SELECT * FROM SCHEDULED_EXECUTIONS
WHERE STATUS = 'pending' AND (SCHEDULED_AT <= SYSTIMESTAMP OR SCHEDULED_AT IS NULL)
ORDER BY SCHEDULED_AT NULLS LAST;

-- Exécutions planifiées d'un utilisateur
SELECT * FROM SCHEDULED_EXECUTIONS WHERE USER_ID = 1 ORDER BY CREATED_AT DESC;
```

**Modèle Django:** `executions/models.py:296` - `class ScheduledExecution`

---

#### RECURRING_PATTERNS (V038)

Table des patterns de récurrence (relation 1:1 avec SCHEDULED_EXECUTIONS).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| ID | NUMBER | PK, IDENTITY | Identifiant unique |
| SCHEDULED_EXECUTION_ID | NUMBER | NOT NULL, FK → SCHEDULED_EXECUTIONS.ID ON DELETE CASCADE, UNIQUE | Exécution planifiée |
| PATTERN_TYPE | VARCHAR2(50) | NOT NULL, CHECK (...) | Type de récurrence |
| PATTERN_CONFIG | CLOB | NULL | Configuration (JSON) |
| NEXT_EXECUTION_DATE | TIMESTAMP | NOT NULL | Prochaine date d'exécution |
| IS_ACTIVE | NUMBER(1) | DEFAULT 1, CHECK (0, 1) | Pattern actif |
| CREATED_AT | TIMESTAMP | DEFAULT SYSTIMESTAMP | Date de création |
| UPDATED_AT | TIMESTAMP | NULL | Date de mise à jour |

**Valeurs CHECK:**
- `PATTERN_TYPE`: 'one_time', 'daily', 'weekly', 'cron'

**Index:** `IDX_RECURRING_PATTERNS_NEXT_DATE`, `IDX_RECURRING_PATTERNS_ACTIVE`

**Format PATTERN_CONFIG:**
```json
// daily
{"hour": 3, "minute": 30, "timezone": "Europe/Paris"}

// weekly
{"day_of_week": 1, "hour": 3, "minute": 30, "timezone": "Europe/Paris"}

// cron
{"expression": "0 3 * * 1-5", "timezone": "Europe/Paris"}
```

**Requêtes courantes:**
```sql
-- Patterns récurrents à exécuter (scheduler)
SELECT rp.*, se.ACTION_ID, se.ENVIRONMENT FROM RECURRING_PATTERNS rp
JOIN SCHEDULED_EXECUTIONS se ON se.ID = rp.SCHEDULED_EXECUTION_ID
WHERE rp.IS_ACTIVE = 1 AND rp.NEXT_EXECUTION_DATE <= SYSTIMESTAMP;

-- Désactiver un pattern récurrent
UPDATE RECURRING_PATTERNS SET IS_ACTIVE = 0, UPDATED_AT = SYSTIMESTAMP WHERE ID = 1;
```

**Modèle Django:** `executions/models.py:370` - `class RecurringPattern`

---

### 5. Domaine Intégrations (integrations)

#### INTEGRATIONS (V020, V024, V026)

Table des intégrations avec les plateformes externes.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| ID | NUMBER | PK, IDENTITY | Identifiant unique |
| TYPE | VARCHAR2(50) | NOT NULL | Type d'intégration (libre depuis V024) |
| NAME | VARCHAR2(255) | UNIQUE, NOT NULL | Nom de l'intégration |
| BASE_URL | VARCHAR2(2000) | NOT NULL | URL de base |
| CREDENTIAL_REF | VARCHAR2(500) | NULL | Référence Vault |
| ICON | VARCHAR2(500) | NULL | URL ou data URI de l'icône |
| AUTH_FLOW | VARCHAR2(50) | NULL, CHECK (...) | Flow d'authentification (V024) |
| TOKEN_URL | VARCHAR2(2000) | NULL | URL pour obtenir le token (V026) |
| CONFIG | CLOB | NULL | Configuration (JSON Schema validé, V026) |
| CREATED_AT | TIMESTAMP | DEFAULT SYSTIMESTAMP | Date de création |
| UPDATED_AT | TIMESTAMP | NULL | Date de mise à jour |

**Valeurs CHECK:**
- `AUTH_FLOW`: 'token', 'basic', 'basic_then_token', 'pat'

**Types suggérés:** aap, servicenow, terraform, azuredevops, jira, github_actions, inventory, inventory_db

**Requêtes courantes:**
```sql
-- Intégration par nom
SELECT * FROM INTEGRATIONS WHERE NAME = 'AAP Production';

-- Intégrations par type
SELECT * FROM INTEGRATIONS WHERE TYPE = 'aap' ORDER BY NAME;

-- Actions utilisant une intégration
SELECT a.NAME FROM ACTIONS_CATALOG a WHERE a.INTEGRATION_ID = 1;
```

**Modèle Django:** `integrations/models.py:60` - `class Integration`

---

### 6. Domaine Audit (core)

#### AUDIT_LOG (V004, V028-V035, V039-V041, V044)

Table d'audit **APPEND-ONLY** pour la conformité SOC1.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| ID | NUMBER | PK, IDENTITY | Identifiant unique |
| TIMESTAMP | TIMESTAMP | DEFAULT SYSTIMESTAMP, NOT NULL | Date de l'événement |
| USER_ID | VARCHAR2(100) | NOT NULL | Identifiant utilisateur (pas FK) |
| ACTION_TYPE | VARCHAR2(50) | NOT NULL, CHECK (...) | Type d'action |
| ENTITY_TYPE | VARCHAR2(50) | NOT NULL, CHECK (...) | Type d'entité |
| ENTITY_ID | NUMBER | NOT NULL | ID de l'entité |
| DETAILS | CLOB | NULL | Détails (JSON) |
| IP_ADDRESS | VARCHAR2(45) | NULL | Adresse IP |
| CORRELATION_ID | VARCHAR2(64) | NULL | ID de corrélation |

**Index:** `IDX_AUDIT_LOG_TIMESTAMP`, `IDX_AUDIT_LOG_ENTITY (ENTITY_TYPE, TIMESTAMP)`

**⚠️ Contrainte métier APPEND-ONLY:** Cette table ne permet que les INSERT. Aucune modification (UPDATE) ou suppression (DELETE) n'est autorisée pour garantir l'intégrité de l'historique d'audit.

**Valeurs ENTITY_TYPE:**
- `action`, `user`, `permission`, `execution`, `integration`, `scheduled_execution`, `profile`

**Types ACTION_TYPE par domaine:**

| Domaine | Types |
|---------|-------|
| Actions catalogue | ACTION_CREATED, ACTION_UPDATED, ACTION_PUBLISHED, ACTION_DISABLED, ACTION_ENABLED, ACTION_DELETED |
| Profils | PROFILE_CREATED, PROFILE_UPDATED, PROFILE_DELETED |
| Intégrations | INTEGRATION_CREATED, INTEGRATION_UPDATED, INTEGRATION_DELETED |
| Exécutions | EXECUTION_SUBMITTED, EXECUTION_RUNNING, EXECUTION_COMPLETED, EXECUTION_FAILED, EXECUTION_CANCELLED, EXECUTION_PENDING_APPROVAL, EXECUTION_REJECTED |
| Planification | SCHEDULED_EXECUTION_CREATED, SCHEDULED_EXECUTION_RECURRING_CREATED, SCHEDULED_EXECUTION_EXECUTED, SCHEDULED_EXECUTION_CANCELLED, SCHEDULED_EXECUTION_RECURRING_DISABLED |
| Utilisateurs | USER_CREATED, USER_UPDATED, USER_LOGIN, USER_LOGOUT, USER_REFRESH |
| Favoris | FAVORITE_ADDED, FAVORITE_REMOVED |

**Requêtes courantes:**
```sql
-- Historique d'une entité
SELECT * FROM AUDIT_LOG
WHERE ENTITY_TYPE = 'action' AND ENTITY_ID = 42
ORDER BY TIMESTAMP DESC;

-- Activité d'un utilisateur
SELECT * FROM AUDIT_LOG
WHERE USER_ID = 'john.doe@example.com'
ORDER BY TIMESTAMP DESC;

-- Événements par correlation_id (traçabilité requête)
SELECT * FROM AUDIT_LOG
WHERE CORRELATION_ID = 'abc123-def456'
ORDER BY TIMESTAMP;

-- Export audit pour SOC1 (derniers 30 jours)
SELECT * FROM AUDIT_LOG
WHERE TIMESTAMP >= SYSTIMESTAMP - INTERVAL '30' DAY
ORDER BY TIMESTAMP;
```

**Modèle Django:** `core/models.py:147` - `class AuditLog`

---

## Contraintes métier critiques

### RBAC - Cumul des permissions multi-profils

**Règle RM6:** Un utilisateur peut appartenir à plusieurs profils via plusieurs AD groups. Les permissions sont cumulées (UNION):
- Si Profil A donne accès aux actions [1, 2] et Profil B aux actions [3, 4], l'utilisateur voit [1, 2, 3, 4]
- Calculé par `ProfileService.get_cumulative_permissions()` dans `profiles/services.py`

**Types de permission (PERMISSION_TYPE):**

| Type | Usage | Champs JSON utilisés |
|------|-------|----------------------|
| `LIST` | Liste explicite | `action_ids_json`, `target_names_json` |
| `PATTERN` | Patterns glob | `tag_patterns_json`, `target_patterns_json` |
| `ALL` | Accès complet | Aucun (tous les éléments autorisés) |

### AUDIT_LOG - Append-only et immutabilité

**Contrainte SOC1:** La table AUDIT_LOG est en INSERT ONLY. Chaque entrée est immuable avec:
- `correlation_id`: Identifiant de requête pour traçabilité end-to-end
- `entity_type` + `entity_id`: Entité concernée
- `details`: JSON avec contexte complet

**Implémentation:**
- Pas de méthode `update()` ou `delete()` dans `AuditLogManager`
- Triggers Oracle peuvent être ajoutés pour rejeter les UPDATE/DELETE

### ACTIONS_CATALOG - Statuts et transitions

| Statut | Description | Transitions possibles |
|--------|-------------|----------------------|
| `draft` | Brouillon | → `published` |
| `published` | Publié (visible catalogue) | → `disabled` |
| `disabled` | Désactivé (archive) | → `published` |

### EXECUTIONS - Workflow d'approbation

**Flux production (environment = 'prod'):**
1. `SUBMITTED` → `PENDING_APPROVAL` (si action requiert approbation)
2. Approbateur valide → `RUNNING` (avec `approved_by`, `approved_at`)
3. Approbateur refuse → `REJECTED`

**Flux développement (environment != 'prod'):**
1. `SUBMITTED` → `RUNNING` (pas d'approbation)

### SCHEDULED_EXECUTIONS - Scheduler externe

Le système utilise un **scheduler externe** (Control-M ou Django scheduler) pour déclencher les exécutions planifiées. L'API expose:
- `GET /api/v1/scheduled-executions/pending` - Récupère les schedules à exécuter
- `PATCH /api/v1/scheduled-executions/{id}/executed` - Marque comme exécuté, recalcule `next_execution_date`

---

## Historique des migrations Flyway

### Vue d'ensemble

| Version | Domaine | Description |
|---------|---------|-------------|
| V000 | Core | Création SCHEMA_VERSION (supprimée en V015) |
| V001 | Users | Création USERS avec IDENTITY column |
| V002 | Catalog | Création ACTIONS_CATALOG |
| V003-V008 | Executions | Steps d'exécution, connecteurs |
| V007 | Catalog | Création TAGS et ACTION_TAGS |
| V010-V013 | RBAC | PROFILES, permissions action/target, suppression rbac_policies |
| V014 | Catalog | DEFAULT_IMPACT_LEVEL |
| V015-V016 | Cleanup | Suppression SCHEMA_VERSION et séquences |
| V017-V019 | Catalog | Change model code, change_type_config par env |
| V020-V026 | Integrations | INTEGRATIONS, auth_flow, token_url, config |
| V021 | Catalog | USER_FAVORITES |
| V022 | Catalog | DOCUMENTATION_MD (markdown) |
| V023-V025 | Executions | EXECUTIONS, EXECUTION_STEPS refactorisés |
| V027 | Catalog | ITEM_TYPE (action/workflow) |
| V028-V035 | Audit | Types d'actions étendus (execution, approval, remediation) |
| V030 | Executions | Workflow d'approbation (APPROVED_BY, etc.) |
| V031 | Catalog | REMEDIATION_RULES |
| V033 | Executions | PARENT_EXECUTION_ID pour remédiation |
| V036-V037 | Catalog | INTEGRATION_ID, engine/platform nullable pour workflows |
| V038-V041 | Scheduling | SCHEDULED_EXECUTIONS, RECURRING_PATTERNS |
| V042-V043 | Catalog | ID ajouté à ACTION_TAGS et USER_FAVORITES (Django ORM) |
| V044 | Audit | Types auth et admin étendus |

### Migrations par domaine

#### Utilisateurs (V001)
```
V001__create_users.sql
  → Création table USERS avec colonnes IDENTITY
```

#### Catalogue (V002, V007, V014, V017-V019, V021-V022, V027, V031, V036-V037, V042-V043)
```
V002__create_actions_catalog.sql
  → Création ACTIONS_CATALOG

V007__create_tags_and_action_tags.sql
  → Création TAGS et ACTION_TAGS (N:N)

V014__add_default_impact_level.sql
  → Ajout DEFAULT_IMPACT_LEVEL à ACTIONS_CATALOG

V017__add_change_model_code.sql
  → Ajout champ pour code modèle de changement

V018__drop_category_column.sql
  → CATEGORY rendue nullable, contrainte/index supprimés (colonne conservée) ; migration des données vers TAGS

V019__change_type_config_per_env.sql
  → CHANGE_TYPE_CONFIG (JSON par environnement)

V021__create_user_favorites.sql
  → Création table USER_FAVORITES

V022__add_documentation_md.sql
  → Ajout DOCUMENTATION_MD (markdown)

V027__add_item_type_workflows.sql
  → Ajout ITEM_TYPE (action/workflow)

V031__add_remediation_rules.sql
  → Ajout REMEDIATION_RULES

V036__add_integration_id_to_actions.sql
  → Ajout FK INTEGRATION_ID

V037__make_engine_platform_nullable_for_workflows.sql
  → ENGINE et PLATFORM nullable (pour workflows)

V042__add_id_to_action_tags.sql
  → Ajout PK ID à ACTION_TAGS (Django ORM)

V043__add_id_to_user_favorites.sql
  → Ajout PK ID à USER_FAVORITES (Django ORM)
```

#### Profils et RBAC (V005, V010-V013)
```
V005__create_user_permissions.sql
  → Création permissions utilisateur (legacy)

V010__create_profiles.sql
  → Création PROFILES

V011__create_profile_action_permissions.sql
  → Création PROFILE_ACTION_PERMISSIONS (1:1)

V012__create_profile_target_permissions.sql
  → Création PROFILE_TARGET_PERMISSIONS (1:1)

V013__drop_rbac_policies_from_actions.sql
  → Suppression ancien RBAC, migration vers profils
```

#### Exécutions (V003, V006, V008, V023, V025, V030, V033, V038-V041)
```
V003__add_execution_steps.sql
  → Ajout étapes d'exécution (legacy)

V006__create_execution_log.sql
  → Création log d'exécution (legacy)

V008__connector_type_in_execution_steps.sql
  → Ajout type connecteur

V023__create_executions.sql
  → Nouvelle table EXECUTIONS (refactoring)

V025__create_execution_steps.sql
  → Nouvelle table EXECUTION_STEPS (refactoring)

V030__add_approval_workflow.sql
  → Workflow approbation (APPROVED_BY, APPROVED_AT, etc.)

V033__add_parent_execution_id.sql
  → PARENT_EXECUTION_ID pour remédiation

V038__add_scheduled_executions.sql
  → SCHEDULED_EXECUTIONS et RECURRING_PATTERNS

V041__add_correlation_id_execution_id_to_scheduled_executions.sql
  → CORRELATION_ID et EXECUTION_ID pour traçabilité
```

#### Intégrations (V020, V024, V026)
```
V020__create_integrations.sql
  → Création INTEGRATIONS

V024__integrations_type_libre_auth_flow.sql
  → TYPE libre, AUTH_FLOW

V026__integrations_token_url_config.sql
  → TOKEN_URL, CONFIG (JSON Schema)
```

#### Audit (V004, V028-V035, V039-V040, V044)
```
V004__create_audit_log.sql
  → Création AUDIT_LOG

V028__audit_log_execution_traces.sql
  → Types execution (EXECUTION_*)

V029__add_audit_log_entity_type_timestamp_index.sql
  → Index composite

V032__add_approval_audit_action_types.sql
  → Types approbation

V034__add_remediation_audit_action_type.sql
  → Types remédiation

V035__add_auto_remediation_audit_types.sql
  → Types auto-remédiation

V039__add_scheduled_execution_audit_types.sql
  → Types scheduled execution

V040__add_scheduled_execution_cancelled_audit_type.sql
  → SCHEDULED_EXECUTION_CANCELLED

V044__extend_audit_log_action_types_for_auth_and_admin.sql
  → Types auth (LOGIN, LOGOUT, REFRESH) et admin
```

---

## Guide de migration de schéma

### Ajouter une nouvelle table

1. **Créer la migration Flyway:**
```sql
-- idp-portal/database/migrations/V045__create_new_table.sql
CREATE TABLE NEW_TABLE (
    ID NUMBER GENERATED BY DEFAULT ON NULL AS IDENTITY PRIMARY KEY,
    NAME VARCHAR2(255) NOT NULL,
    CREATED_AT TIMESTAMP DEFAULT SYSTIMESTAMP
);

CREATE UNIQUE INDEX UK_NEW_TABLE_NAME ON NEW_TABLE(NAME);

COMMENT ON TABLE NEW_TABLE IS 'Description de la table';
COMMENT ON COLUMN NEW_TABLE.NAME IS 'Nom unique';
```

2. **Créer le modèle Django:**
```python
# django_backend/app_name/models.py
class NewTable(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    name = models.CharField(max_length=255, unique=True, db_column='NAME')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')

    class Meta:
        db_table = 'NEW_TABLE'
        managed = False  # Flyway gère le schéma
```

3. **Générer la migration Django (optionnel):**
```bash
cd idp-portal/django_backend
python manage.py makemigrations app_name --empty --name create_new_table
```

### Modifier une colonne existante

1. **Migration Flyway:**
```sql
-- V046__alter_column.sql
ALTER TABLE ACTIONS_CATALOG MODIFY DESCRIPTION VARCHAR2(8000);
```

2. **Mettre à jour le modèle Django:**
```python
description = models.CharField(max_length=8000, ...)  # Était 4000
```

### Ajouter un index ou une contrainte

```sql
-- V047__add_index.sql
CREATE INDEX IDX_EXECUTIONS_ENV_STATUS ON EXECUTIONS(ENVIRONMENT, STATUS);

-- Contrainte CHECK
ALTER TABLE ACTIONS_CATALOG ADD CONSTRAINT CHK_STATUS
    CHECK (STATUS IN ('draft', 'published', 'disabled', 'archived'));
```

### Cohabitation Flyway/Django

**Règle:** Flyway gère le schéma en production, Django en développement.

1. **Production:** Flyway applique les migrations V*.sql
2. **Développement:** `managed = False` dans les modèles Django
3. **Tests:** Utiliser le même schéma via fixtures ou migrations Django

**Structure recommandée:**
```
idp-portal/
├── database/
│   └── migrations/
│       ├── V000__create_schema_version.sql
│       ├── V001__create_users.sql
│       └── ...
└── django_backend/
    └── {app}/
        └── migrations/
            └── 0001_initial.py  # managed = False
```

---

## Génération automatique de diagrammes

### Option 1: django-extensions (recommandé)

```bash
# Installation
pip install django-extensions graphviz pydotplus

# settings.py
INSTALLED_APPS += ['django_extensions']

# Générer le diagramme
python manage.py graph_models -a -g -o models.png

# Options utiles:
# -a : Toutes les apps
# -g : Grouper par app
# -o : Fichier de sortie
# --exclude-models Model1,Model2 : Exclure des modèles
```

### Option 2: dbdiagram.io (en ligne)

Exporter depuis Django ou utiliser le diagramme ASCII de ce document.

### Option 3: Oracle SQL Developer Data Modeler

Importer le schéma Oracle pour visualisation graphique.

---

## Références

### Fichiers sources

| Fichier | Contenu |
|---------|---------|
| `idp-portal/django_backend/catalog/models.py` | Action, Tag, ActionTag, UserFavorite |
| `idp-portal/django_backend/executions/models.py` | Execution, ExecutionStep, ScheduledExecution, RecurringPattern |
| `idp-portal/django_backend/profiles/models.py` | Profile, ProfileActionPermission, ProfileTargetPermission |
| `idp-portal/django_backend/core/models.py` | AuditLog, AuditActionType, AuditEntityType |
| `idp-portal/django_backend/integrations/models.py` | Integration |
| `idp-portal/django_backend/idp_auth/models.py` | User |
| `idp-portal/database/migrations/` | 45 migrations Flyway (V000-V044) |

### Documentation connexe

- [Modèles Django et Relations](./models.md) - Documentation des modèles Django
- [Architecture](../../_bmad-output/planning-artifacts/architecture.md#Data-Architecture) - Décisions architecturales (chemin relatif à la racine du dépôt)
