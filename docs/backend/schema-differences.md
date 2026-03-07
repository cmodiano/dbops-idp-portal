# Comparaison Schéma Base de Données : FastAPI vs Django

> **📦 Document d'archivage — Migration terminée**  
> Ce document est conservé pour référence historique. La migration FastAPI→Django est complète (février 2026).  
> Voir [MIGRATION_ARCHIVE.md](./migration/MIGRATION_ARCHIVE.md) pour accéder au code FastAPI archivé.

**Date d'analyse:** 2026-02-05
**Version:** 1.0
**Statut:** ✅ Migration terminée — Schéma identique confirmé

---

## Résumé Exécutif

L'analyse comparative du schéma base de données Oracle entre le backend FastAPI (SQL brut + python-oracledb) et le backend Django (ORM) confirme une **parité complète**.

| Critère | Résultat |
|---------|----------|
| Tables utilisées | ✅ Identiques |
| Colonnes et types | ✅ Identiques |
| Contraintes | ✅ Identiques |
| Index | ✅ Identiques |
| Nouvelles tables Django | ✅ Aucune |
| Migration de données | ✅ Non nécessaire |

---

## Tables Analysées

### Tables Principales (FastAPI et Django)

| Table | Version Migration | Utilisée FastAPI | Utilisée Django | Parité |
|-------|------------------|------------------|-----------------|--------|
| `ACTIONS_CATALOG` | V002, V017, V019, V022, V027, V031, V036, V037 | ✅ | ✅ | ✅ |
| `TAGS` | V007 | ✅ | ✅ | ✅ |
| `ACTION_TAGS` | V007 | ✅ | ✅ | ✅ |
| `USERS` | V001 | ✅ | ✅ | ✅ |
| `PROFILES` | V010 | ✅ | ✅ | ✅ |
| `PROFILE_ACTION_PERMISSIONS` | V011 | ✅ | ✅ | ✅ |
| `PROFILE_TARGET_PERMISSIONS` | V012 | ✅ | ✅ | ✅ |
| `USER_FAVORITES` | V021 | ✅ | ✅ | ✅ |
| `INTEGRATIONS` | V020, V024, V026 | ✅ | ✅ | ✅ |
| `EXECUTIONS` | V023, V030, V033 | ✅ | ✅ | ✅ |
| `EXECUTION_STEPS` | V025 | ✅ | ✅ | ✅ |
| `AUDIT_LOG` | V004, V028-V035, V039-V041 | ✅ | ✅ | ✅ |
| `SCHEDULED_EXECUTIONS` | V038, V041 | ✅ | ✅ | ✅ |
| `RECURRING_PATTERNS` | V038 | ✅ | ✅ | ✅ |

### Tables Supprimées (Migrations Historiques)

| Table | Migration Suppression | Raison |
|-------|----------------------|--------|
| `SCHEMA_VERSION` | V015 | Remplacée par Flyway |
| Séquences `*_SEQ` | V016 | Identity columns Oracle 12c+ |
| `RBAC_POLICIES` (colonnes) | V013 | RBAC déplacé vers PROFILES |
| `CATEGORY` (colonne) | V018 | Simplification tags-only |

---

## Analyse Détaillée par Table

### ACTIONS_CATALOG

**Modèle Django:** `catalog/models.py::Action`

| Colonne | Type Oracle | Type Django | db_column | Parité |
|---------|------------|-------------|-----------|--------|
| ID | NUMBER (identity) | BigAutoField | ID | ✅ |
| NAME | VARCHAR2(255) UNIQUE | CharField(255) unique | NAME | ✅ |
| DESCRIPTION | VARCHAR2(4000) | CharField(4000) null | DESCRIPTION | ✅ |
| CATEGORY | VARCHAR2(50) CHECK | CharField choices | CATEGORY | ✅ |
| ENGINE | VARCHAR2(50) CHECK | CharField choices | ENGINE | ✅ |
| PLATFORM | VARCHAR2(50) CHECK | CharField choices | PLATFORM | ✅ |
| PARAMETERS_SCHEMA | CLOB | TextField | PARAMETERS_SCHEMA | ✅ |
| IMPACT_RULES | CLOB | TextField | IMPACT_RULES | ✅ |
| EXECUTION_STEPS | CLOB | TextField | EXECUTION_STEPS | ✅ |
| CHANGE_TYPE_CONFIG | CLOB | TextField | CHANGE_TYPE_CONFIG | ✅ |
| DOCUMENTATION_MD | CLOB | TextField | DOCUMENTATION_MD | ✅ |
| REMEDIATION_RULES | CLOB | TextField | REMEDIATION_RULES | ✅ |
| DEFAULT_IMPACT_LEVEL | VARCHAR2(20) CHECK | CharField choices | DEFAULT_IMPACT_LEVEL | ✅ |
| STATUS | VARCHAR2(20) CHECK | CharField choices | STATUS | ✅ |
| ITEM_TYPE | VARCHAR2(20) CHECK | CharField choices | ITEM_TYPE | ✅ |
| CREATED_BY | NUMBER | ForeignKey(User) | CREATED_BY | ✅ |
| INTEGRATION_ID | NUMBER | ForeignKey(Integration) | INTEGRATION_ID | ✅ |
| CREATED_AT | TIMESTAMP | DateTimeField auto_now_add | CREATED_AT | ✅ |
| UPDATED_AT | TIMESTAMP | DateTimeField null | UPDATED_AT | ✅ |

### PROFILES

**Modèle Django:** `profiles/models.py::Profile`

| Colonne | Type Oracle | Type Django | db_column | Parité |
|---------|------------|-------------|-----------|--------|
| ID | NUMBER (identity) | BigAutoField | ID | ✅ |
| NAME | VARCHAR2(255) UNIQUE | CharField(255) unique | NAME | ✅ |
| DESCRIPTION | VARCHAR2(4000) | CharField(4000) null | DESCRIPTION | ✅ |
| AD_GROUP | VARCHAR2(512) | CharField(512) | AD_GROUP | ✅ |
| IS_ADMIN | NUMBER(1) CHECK (0,1) | IntegerField default=0 | IS_ADMIN | ✅ |
| IS_AUDITOR | NUMBER(1) CHECK (0,1) | IntegerField default=0 | IS_AUDITOR | ✅ |
| CREATED_AT | TIMESTAMP | DateTimeField auto_now_add | CREATED_AT | ✅ |
| UPDATED_AT | TIMESTAMP | DateTimeField auto_now | UPDATED_AT | ✅ |

### EXECUTIONS

**Modèle Django:** `executions/models.py::Execution`

| Colonne | Type Oracle | Type Django | db_column | Parité |
|---------|------------|-------------|-----------|--------|
| ID | NUMBER (identity) | BigAutoField | ID | ✅ |
| ACTION_ID | NUMBER FK | ForeignKey(Action) | ACTION_ID | ✅ |
| USER_ID | NUMBER FK | ForeignKey(User) | USER_ID | ✅ |
| ENVIRONMENT | VARCHAR2(50) CHECK | CharField choices | ENVIRONMENT | ✅ |
| PARAMETERS | CLOB | TextField | PARAMETERS | ✅ |
| STATUS | VARCHAR2(20) CHECK | CharField choices | STATUS | ✅ |
| SERVICENOW_CHANGE_ID | VARCHAR2(100) | CharField(100) null | SERVICENOW_CHANGE_ID | ✅ |
| APPROVED_BY | NUMBER FK | ForeignKey(User) null | APPROVED_BY | ✅ |
| APPROVED_AT | TIMESTAMP | DateTimeField null | APPROVED_AT | ✅ |
| APPROVAL_COMMENT | VARCHAR2(1000) | CharField(1000) null | APPROVAL_COMMENT | ✅ |
| PARENT_EXECUTION_ID | NUMBER FK | ForeignKey(self) null | PARENT_EXECUTION_ID | ✅ |
| STARTED_AT | TIMESTAMP | DateTimeField null | STARTED_AT | ✅ |
| COMPLETED_AT | TIMESTAMP | DateTimeField null | COMPLETED_AT | ✅ |
| CREATED_AT | TIMESTAMP | DateTimeField auto_now_add | CREATED_AT | ✅ |

### AUDIT_LOG

**Modèle Django:** `core/models.py::AuditLog`

| Colonne | Type Oracle | Type Django | db_column | Parité |
|---------|------------|-------------|-----------|--------|
| ID | NUMBER (identity) | BigAutoField | ID | ✅ |
| TIMESTAMP | TIMESTAMP DEFAULT SYSTIMESTAMP | DateTimeField auto_now_add | TIMESTAMP | ✅ |
| USER_ID | VARCHAR2(100) | CharField(100) | USER_ID | ✅ |
| ACTION_TYPE | VARCHAR2(50) CHECK | CharField choices | ACTION_TYPE | ✅ |
| ENTITY_TYPE | VARCHAR2(50) CHECK | CharField choices | ENTITY_TYPE | ✅ |
| ENTITY_ID | NUMBER | BigIntegerField | ENTITY_ID | ✅ |
| DETAILS | CLOB | TextField | DETAILS | ✅ |
| IP_ADDRESS | VARCHAR2(45) | CharField(45) null | IP_ADDRESS | ✅ |
| CORRELATION_ID | VARCHAR2(64) | CharField(64) null | CORRELATION_ID | ✅ |

---

## Vérification des Index

### Index Existants (Créés par Flyway)

| Table | Index | Colonnes | Présent Django |
|-------|-------|----------|----------------|
| AUDIT_LOG | IDX_AUDIT_LOG_ENTITY | ENTITY_TYPE, TIMESTAMP | ✅ |
| EXECUTIONS | IDX_EXEC_ACTION | ACTION_ID | ✅ |
| EXECUTIONS | IDX_EXEC_USER | USER_ID | ✅ |
| EXECUTIONS | IDX_EXEC_STATUS | STATUS | ✅ |
| SCHEDULED_EXECUTIONS | IDX_SCHED_EXEC_NEXT | STATUS, SCHEDULED_AT | ✅ |

**Note:** Django ORM utilise les index existants via `db_index=False` (pas de recréation d'index).

---

## Pool de Connexions : Compatibilité

### Configuration FastAPI

```python
# backend/app/core/database.py
pool = oracledb.create_pool(
    user=settings.oracle_user,
    password=settings.oracle_password,
    dsn=settings.oracle_dsn,
    min=2,
    max=10,
    increment=1,
    threaded=True
)
```

### Configuration Django

```python
# django_backend/idp_backend/settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.oracle',
        'NAME': os.environ.get('ORACLE_SERVICE_NAME'),
        'USER': os.environ.get('ORACLE_USER'),
        'PASSWORD': os.environ.get('ORACLE_PASSWORD'),
        'HOST': os.environ.get('ORACLE_HOST'),
        'PORT': os.environ.get('ORACLE_PORT', '1521'),
        'OPTIONS': {
            'threaded': True,
            'events': True,
        },
        'CONN_MAX_AGE': 600,  # 10 min persistent connections
    }
}
```

### Compatibilité Pool

| Paramètre | FastAPI | Django | Compatible |
|-----------|---------|--------|------------|
| Driver | oracledb 3.4.1 Thin | oracledb 3.4.1 Thin | ✅ |
| Max connections | 10 | CONN_MAX_AGE managed | ✅ |
| Mode | Threaded | Threaded | ✅ |
| Coexistence | N/A | Possible (pools séparés) | ✅ |

**Conclusion:** Les deux backends peuvent coexister sans conflits de pool. Pendant la période de transition, les deux pools fonctionnent indépendamment.

---

## Migrations Django : État

```bash
$ python manage.py showmigrations

catalog
 [X] 0001_initial

core
 [X] 0001_initial

executions
 [X] 0001_initial

idp_auth
 [X] 0001_initial

integrations
 [X] 0001_initial

profiles
 [X] 0001_initial
```

**Status:** Toutes les migrations Django sont appliquées.

**Important:** Les migrations Django sont en mode `managed = True` mais utilisent `db_table` pour mapper aux tables existantes créées par Flyway. Django ORM n'a **pas créé de nouvelles tables** - il utilise les tables existantes.

---

## Conclusion

### Résultat de l'Analyse

| Critère | Résultat | Impact |
|---------|----------|--------|
| Schéma identique | ✅ Oui | Aucune migration de données |
| Nouvelles tables Django | ✅ Aucune | Pas de conflicts |
| Types de colonnes | ✅ Compatibles | ORM fonctionne correctement |
| Contraintes CHECK | ✅ Respectées | Validation Django aligns |
| Index | ✅ Réutilisés | Pas de recréation |
| Pool connexions | ✅ Compatible | Coexistence possible |

### Recommandation

**Aucune migration de données n'est nécessaire.**

Les deux backends utilisent exactement le même schéma Oracle. La bascule peut être effectuée en toute sécurité sans préparation de données.

### Validation Post-Bascule

Après la bascule, vérifier :

1. **Connexions actives** : `SELECT COUNT(*) FROM V$SESSION WHERE USERNAME='IDP_USER'`
2. **Pas de locks** : `SELECT * FROM V$LOCKED_OBJECT`
3. **Performance requêtes** : Monitoring temps réponse via Dynatrace

---

**Document approuvé par:** Équipe IDP Backend
**Date:** 2026-02-05
