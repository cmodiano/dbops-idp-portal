# Backend Best Practices

Ce document rassemble les bonnes pratiques et patterns identifiés lors du développement du backend.

## Table des matières

1. [Gestion des contraintes CHECK Oracle dans les migrations](#gestion-des-contraintes-check-oracle-dans-les-migrations)
2. [Bind Variables Oracle - Mots réservés](#bind-variables-oracle---mots-réservés)
3. [RBAC Inventaire — Comportement Fail-Open de `filter_by_attribute`](#rbac-inventaire--comportement-fail-open-de-filter_by_attribute)

---

## Gestion des contraintes CHECK Oracle dans les migrations

### Contexte

Les contraintes CHECK Oracle (comme `CK_AUDIT_LOG_ACTION_TYPE` sur la table `AUDIT_LOG`) définissent les valeurs autorisées pour une colonne. Quand plusieurs migrations modifient la même contrainte, il y a un risque de perdre des valeurs si une migration fait DROP/ADD sans inclure toutes les valeurs précédentes.

### Problème rencontré (Story 9.8)

**Symptôme:** Erreur `ORA-02290: check constraint (CK_AUDIT_LOG_ACTION_TYPE) violated` lors d'insertions dans AUDIT_LOG.

**Cause potentielle:** Une migration ultérieure a DROP/ADD la contrainte CHECK sans inclure tous les types d'action précédents.

**Exemple de chaîne de migrations problématique:**
```
V028: Ajoute EXECUTION_SUBMITTED, EXECUTION_STARTED, ...
V032: Ajoute EXECUTION_PENDING_APPROVAL, EXECUTION_APPROVED, EXECUTION_REJECTED
V034: Ajoute REMEDIATION_EXECUTION_CREATED
      ⚠️ RISQUE: Si V034 ne copie pas les types de V032, ils sont perdus!
```

### Pattern recommandé

**Règle:** Toute migration qui modifie une contrainte CHECK DOIT copier l'état complet de la contrainte précédente, puis ajouter les nouveaux types.

```sql
-- V034: Add remediation audit action type (Story 9.2)
-- Extends V032 to include REMEDIATION_EXECUTION_CREATED
-- ⚠️ IMPORTANT: Preserve ALL previous types from V032

ALTER TABLE AUDIT_LOG DROP CONSTRAINT CK_AUDIT_LOG_ACTION_TYPE;

ALTER TABLE AUDIT_LOG ADD CONSTRAINT CK_AUDIT_LOG_ACTION_TYPE CHECK (
    ACTION_TYPE IN (
        -- Action lifecycle (V004)
        'ACTION_CREATED', 'ACTION_UPDATED', 'ACTION_PUBLISHED', 'ACTION_DISABLED', 'ACTION_ENABLED',
        -- Execution lifecycle (V028)
        'EXECUTION_SUBMITTED', 'EXECUTION_STARTED', 'EXECUTION_COMPLETED', 'EXECUTION_FAILED',
        -- ServiceNow change (V028)
        'SERVICENOW_CHANGE_CREATED',
        -- Approval workflow (V032 - Story 7.4) ← DOIT ÊTRE COPIÉ
        'EXECUTION_PENDING_APPROVAL', 'EXECUTION_APPROVED', 'EXECUTION_REJECTED',
        -- Remediation (V034 - Story 9.2) ← NOUVEAU
        'REMEDIATION_EXECUTION_CREATED'
    )
);
```

### Checklist avant commit d'une migration touchant une contrainte CHECK

- [ ] Lire la migration précédente qui a modifié cette contrainte
- [ ] Copier TOUTES les valeurs existantes dans la nouvelle contrainte
- [ ] Ajouter les nouvelles valeurs à la fin
- [ ] Commenter la source de chaque groupe de valeurs (ex: `-- Approval workflow (V032)`)
- [ ] Tester l'insertion de toutes les valeurs (existantes + nouvelles)

### Commandes diagnostic

```sql
-- Vérifier contrainte CHECK actuelle
SELECT SEARCH_CONDITION
FROM USER_CONSTRAINTS
WHERE CONSTRAINT_NAME = 'CK_AUDIT_LOG_ACTION_TYPE';

-- Vérifier migrations Flyway appliquées
SELECT installed_rank, version, description, installed_on, success
FROM FLYWAY_SCHEMA_HISTORY
ORDER BY installed_rank DESC
FETCH FIRST 10 ROWS ONLY;

-- Test rapide: vérifier si contrainte permet les approval types
BEGIN
  INSERT INTO AUDIT_LOG (USER_ID, ACTION_TYPE, ENTITY_TYPE, ENTITY_ID, ACTION_TIMESTAMP, CLIENT_IP, ACTION_DETAILS)
  VALUES ('_test_', 'EXECUTION_APPROVED', 'execution', 0, SYSTIMESTAMP, '127.0.0.1', '{}');
  DBMS_OUTPUT.PUT_LINE('✓ EXECUTION_APPROVED autorisé');
  ROLLBACK;
EXCEPTION
  WHEN OTHERS THEN
    ROLLBACK;
    IF SQLCODE = -2290 THEN
      DBMS_OUTPUT.PUT_LINE('✗ EXECUTION_APPROVED NON autorisé - contrainte obsolète');
    END IF;
    RAISE;
END;
/
```

### Script de validation automatisé

Voir: `scripts/validate-audit-log-constraint.sql`

Ce script vérifie que tous les action types attendus sont présents dans la contrainte CHECK.

---

## Bind Variables Oracle - Mots réservés {#bind-variables-oracle---mots-réservés}

### Contexte

Oracle a des mots réservés qui ne peuvent pas être utilisés comme noms de bind variables dans les requêtes SQL. Utiliser un mot réservé cause l'erreur `ORA-01745: invalid host/bind variable name`.

### Problème rencontré (Story 9.7)

**Symptôme:** Erreur `ORA-01745: invalid host/bind variable name` lors de l'approbation/rejet d'exécutions.

**Cause:** Le code utilisait `:comment` comme bind variable, mais `COMMENT` est un mot réservé Oracle.

**Correction:** Renommer en `:approval_comment`.

```python
# ❌ Mauvais - COMMENT est un mot réservé Oracle
params = {"comment": "Approved for production"}
query = "UPDATE EXECUTIONS SET APPROVAL_COMMENT = :comment WHERE ID = :id"

# ✅ Bon - approval_comment n'est pas réservé
params = {"approval_comment": "Approved for production"}
query = "UPDATE EXECUTIONS SET APPROVAL_COMMENT = :approval_comment WHERE ID = :id"
```

### Mots réservés Oracle courants à éviter

- `COMMENT`
- `DATE`
- `SIZE`
- `TYPE`
- `VALUE`
- `FILE`
- `TABLE`
- `INDEX`
- `VIEW`

### Pattern recommandé

1. Préfixer les bind variables avec le contexte (ex: `approval_comment`, `execution_date`)
2. Ajouter des tests de régression qui vérifient les noms des bind variables
3. Scanner le codebase régulièrement pour détecter les mots réservés

### Tests de régression

Voir: `backend/tests/unit/test_approval_workflow.py::TestOracleBindVariableRegression`

Ces tests vérifient que les requêtes SQL n'utilisent pas de mots réservés Oracle comme bind variables.

---

---

## RBAC Inventaire — Comportement Fail-Open de `filter_by_attribute`

### Contexte

Le filtre `filter_by_attribute` dans `InventoryRBACFilter._apply_attribute_filter()` (module `inventory/rbac_filter.py`) est utilisé pour restreindre l'accès aux serveurs selon un attribut de leur fiche inventaire (ex: `engine_type`, `os_type`).

### ⚠️ Comportement Fail-Open (Story 66.21 — INV-MED-03)

**Règle :** Si la clé d'attribut configurée dans un profil (`filter_by_attribute`) est **absente de tous les serveurs** du résultat, le filtre est **silencieusement ignoré** — tous les serveurs passent à travers.

**Conséquence sécuritaire :** Un typo dans la clé (ex: `"engine_tpe"` au lieu de `"engine_type"`) accorde un accès **plus large que prévu** plutôt que de bloquer l'accès.

```python
# Exemple : profil configuré avec filter_by_attribute = {"engine_tpe": ["oracle"]}
# engine_tpe n'existe dans aucun serveur → filtre ignoré → TOUS les serveurs retournés
# Comportement intentionnel pour éviter de casser les déploiements lors d'une migration de schéma d'inventaire
```

### Monitoring obligatoire

Surveiller le log warning `rbac_filter_attribute_not_found` — ce warning indique une **misconfiguration probable** d'un profil :

```python
logger.warning(
    "rbac_filter_attribute_not_found",
    attribute=attr_key,
    allowed_values=allowed_values,
    correlation_id=correlation_id,
)
```

### Pattern recommandé

1. Valider les clés `filter_by_attribute` lors de la création/modification d'un profil
2. Surveiller le log `rbac_filter_attribute_not_found` via alerting en production
3. Tester les profils RBAC après tout changement de schéma d'inventaire
4. Documenter les clés disponibles dans la configuration d'intégration

### Références

- `inventory/rbac_filter.py::InventoryRBACFilter._apply_attribute_filter()` — implémentation
- `inventory/tests/test_rbac_filter_by_attribute.py::test_fail_open_behavior_typo_in_attribute_key_grants_full_access` — test de régression explicite
- Story 66.21 — INV-MED-03

---

## Références

- [Oracle Reserved Words](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/Oracle-SQL-Reserved-Words.html)
- Story 9.7: Fix Oracle bind variable comment (voir `_bmad-output/implementation-artifacts/` dans le dépôt)
- Story 9.8: Fix audit log approval action types (voir `_bmad-output/implementation-artifacts/` dans le dépôt)
- Story 66.21: RBAC fail-open behavior `filter_by_attribute` (voir `_bmad-output/implementation-artifacts/` dans le dépôt)
