# Backend Best Practices

Ce document décrit les bonnes pratiques de développement backend pour le projet IDP Portal.

## Oracle Database avec python-oracledb

**Version Oracle cible:** Oracle Database 19c (compatible 21c)

### Mots réservés Oracle dans les variables de liaison (Bind Variables)

#### Problème

Lors de l'utilisation de python-oracledb avec des requêtes paramétrées, certains mots réservés Oracle ne peuvent pas être utilisés comme noms de variables de liaison. Cela provoque l'erreur **ORA-01745: invalid host/bind variable name**.

**Exemple de bug historique (Story 7.4 → 9.7):**

Le mot `COMMENT` est un mot réservé Oracle. Son utilisation comme bind variable cause l'erreur ORA-01745:

```python
# ❌ INCORRECT - provoque ORA-01745
query = """
    UPDATE EXECUTIONS
    SET APPROVAL_COMMENT = :comment
    WHERE ID = :execution_id
"""
params = {"comment": user_comment, "execution_id": 42}
```

**Solution (appliquée dans commit 6163b8e):**

```python
# ✅ CORRECT - préfixe descriptif évite le mot réservé
query = """
    UPDATE EXECUTIONS
    SET APPROVAL_COMMENT = :approval_comment
    WHERE ID = :execution_id
"""
params = {"approval_comment": user_comment, "execution_id": 42}
```

#### Liste des mots réservés Oracle courants à éviter

Les mots suivants ne doivent **jamais** être utilisés seuls comme noms de bind variables:

**Objets de base de données (DDL):**
- `COMMENT`, `TABLE`, `INDEX`, `COLUMN`, `VIEW`, `SEQUENCE`, `CONSTRAINT`

**Sécurité et contrôle d'accès:**
- `USER`, `GROUP`, `ROLE`, `PROFILE`, `SESSION`, `GRANT`, `REVOKE`

**Opérations de données (DML):**
- `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `MERGE`

**Opérations de définition (DDL):**
- `CREATE`, `DROP`, `ALTER`, `TRUNCATE`

**Types temporels:**
- `DATE`, `TIME`, `TIMESTAMP`, `YEAR`, `MONTH`, `DAY`, `HOUR`, `MINUTE`, `SECOND`

**Clauses SQL:**
- `ORDER`, `BY`, `WHERE`, `FROM`, `JOIN`, `ON`, `AND`, `OR`, `NOT`

**Contraintes:**
- `NULL`, `DEFAULT`, `CHECK`, `PRIMARY`, `FOREIGN`, `KEY`, `UNIQUE`

**Fonctions d'agrégation:**
- `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`, `LEVEL`, `ROWNUM`

> **Note:** Cette liste n'est pas exhaustive. En cas de doute, consultez la [documentation Oracle 19c](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/Oracle-SQL-Reserved-Words.html).
>
> **Important:** La liste des mots réservés peut varier entre les versions Oracle (19c, 21c, 23c). Cette documentation est basée sur Oracle 19c. Réviser lors de migrations de version majeure.

#### Pattern recommandé pour les bind variables

**Règle d'or:** Toujours préfixer avec le contexte ou le nom de la colonne.

| ❌ À éviter | ✅ Recommandé | Contexte |
|-------------|---------------|----------|
| `:comment` | `:approval_comment` | Commentaire d'approbation |
| `:user` | `:user_id`, `:user_name` | Identifiant/nom utilisateur |
| `:name` | `:action_name`, `:profile_name` | Nom avec contexte |
| `:type` | `:integration_type`, `:action_type` | Type avec contexte |
| `:status` | `:execution_status`, `:new_status` | Statut avec contexte |
| `:date` | `:created_date`, `:from_date` | Date avec contexte |
| `:id` | `:execution_id`, `:action_id` | ID avec contexte table |

#### Exemples complets

**Approbation d'exécution:**
```python
async def approve(execution_id: int, approver_id: int, comment: Optional[str] = None):
    query = """
        UPDATE EXECUTIONS
        SET STATUS = :new_status,
            APPROVED_BY = :approver_id,
            APPROVED_AT = SYSTIMESTAMP,
            APPROVAL_COMMENT = :approval_comment
        WHERE ID = :execution_id AND STATUS = :current_status
    """
    params = {
        "execution_id": execution_id,
        "new_status": ExecutionStatus.SUBMITTED.value,
        "current_status": ExecutionStatus.PENDING_APPROVAL.value,
        "approver_id": approver_id,
        "approval_comment": comment,  # ✅ Préfixé avec 'approval_'
    }
```

**Filtrage par tags:**
```python
# ✅ CORRECT - placeholders dynamiques avec préfixe
tag_placeholders = ", ".join([f":filter_tag{i}" for i in range(len(tags))])
query = f"SELECT * FROM ACTIONS WHERE TAG IN ({tag_placeholders})"
params = {f"filter_tag{i}": tag for i, tag in enumerate(tags)}
```

#### Tests de régression

Pour prévenir la réintroduction de ce bug, des tests de régression explicites vérifient les noms de bind variables:

```python
# test_approval_workflow.py - TestOracleBindVariableRegression
def test_approve_uses_approval_comment_bind_variable():
    """Regression test: approve() must use :approval_comment, not :comment."""
    # ... mock setup ...

    # Verify SQL uses correct bind variable name
    assert ":approval_comment" in query
    assert ":comment" not in query.replace(":approval_comment", "")

    # Verify params dict uses correct key
    assert "approval_comment" in params
    assert "comment" not in params
```

#### Référence

- **Bug introduit:** Story 7-4, commit a450130 (2026-02-01)
- **Bug corrigé:** Story 9-1, commit 6163b8e (2026-02-02)
- **Tests ajoutés:** Story 9-7 (2026-02-02)
- **Fichiers concernés:** `backend/app/repositories/execution_repository.py`

---

## Prochaines sections (à compléter)

- Gestion des transactions
- Logging et observabilité
- Gestion des erreurs
- Tests unitaires et mocks
