# Guide opérationnel — Procédure de purge et politique de rétention

**Story 40.5 — Epic 40 : Partitionnement et rétention tables performance**
**Livrable : PKG_IDP_MAINTENANCE (V087)**
**Date :** 2026-02-24

---

## Table des matières

1. [Politique de rétention](#1-politique-de-rétention)
2. [Fréquence recommandée et fenêtre de maintenance](#2-fréquence-recommandée-et-fenêtre-de-maintenance)
3. [Procédure d'exécution (guide DBA)](#3-procédure-dexécution-guide-dba)
4. [Paramètres configurables](#4-paramètres-configurables)
5. [Rollback — IMPOSSIBLE après DROP PARTITION PURGE](#5-rollback--impossible-après-drop-partition-purge)
6. [Avertissements AUDIT_LOG — SOC1/NFR8](#6-avertissements-audit_log--soc1nfr8)
7. [Planification automatique — DBMS_SCHEDULER (optionnel)](#7-planification-automatique--dbms_scheduler-optionnel)
8. [Monitoring et vérification](#8-monitoring-et-vérification)

---

## 1. Politique de rétention

| Table | Clé de partition | Rétention par défaut | Justification |
|---|---|---|---|
| `EXECUTIONS` | `CREATED_AT` (mensuel INTERVAL) | **24 mois** | Conformité opérationnelle — historique des exécutions pour audit et re-jeu |
| `EXECUTION_STEPS` | cascade via Reference Partitioning | **identique à EXECUTIONS** | Partitionnement par référence sur `EXECUTION_ID → EXECUTIONS.ID` (V085) — aucune action manuelle |
| `AUDIT_LOG` | `TIMESTAMP` (mensuel INTERVAL) | **12 mois (configurable 12–24 mois)** | SOC1/NFR8 — **validation conformité obligatoire avant activation** |

### Justification métier / conformité

- **EXECUTIONS (24 mois)** : La durée de 24 mois permet de couvrir les besoins d'audit rétrospectif (accords SOC1, revues d'accès annuelles ×2). Au-delà, les exécutions n'ont plus de valeur opérationnelle pour le portail IDP.
- **EXECUTION_STEPS (cascade)** : Les étapes d'exécution ont la même valeur d'audit que l'exécution parente. La cascade automatique via Reference Partitioning (V085) garantit la cohérence sans action supplémentaire.
- **AUDIT_LOG (12–24 mois)** : Durée à valider avec l'équipe conformité/sécurité selon les obligations réglementaires applicables (ex. SOC 2, PCI-DSS, RGPD). La valeur par défaut de 12 mois est un plancher prudent — elle peut être portée à 24 mois si la réglementation l'exige.

---

## 2. Fréquence recommandée et fenêtre de maintenance

### Fréquence

**Mensuelle** — à exécuter le **1er de chaque mois**, hors heures de pointe (ex. 02:00–06:00 UTC).

Rationale : EXECUTIONS et AUDIT_LOG sont partitionnées mensuellement (INTERVAL mensuel Oracle). Une purge mensuelle garantit qu'une partition complète est supprimée à chaque cycle, sans accumulation de retard.

### Fenêtre de maintenance

| Opération | Impact service | Durée estimée |
|---|---|---|
| `DROP PARTITION … UPDATE GLOBAL INDEXES` | **Aucun** (DDL non-bloquant) | Quasi-instantané (< 1 min par partition) |
| `UPDATE … SET PARENT_EXECUTION_ID = NULL` (pré-requis) | DML standard, verrous ligne | Dépend du volume EXECUTIONS avec `PARENT_EXECUTION_ID` non-NULL dans la partition (quelques secondes à quelques minutes) |
| `DELETE FROM EXECUTION_TARGETS WHERE …` (pré-requis) | DML standard | Dépend du volume `EXECUTION_TARGETS` |

**Conclusion** : le `DROP PARTITION` lui-même est quasi-instantané et n'impacte pas les DML en cours sur les autres partitions. Seuls les pré-requis DML (UPDATE/DELETE) peuvent prendre plus longtemps selon le volume.

**Recommandation** : exécuter d'abord en mode `dry_run=1` pour estimer le volume avant l'exécution réelle.

---

## 3. Procédure d'exécution (guide DBA)

### Étape 1 — Vérification préalable (backup)

```sql
-- Vérifier l'état des partitions avant purge
SELECT TABLE_NAME, PARTITION_NAME, HIGH_VALUE, NUM_ROWS
FROM USER_TAB_PARTITIONS
WHERE TABLE_NAME IN ('EXECUTIONS', 'AUDIT_LOG')
ORDER BY TABLE_NAME, PARTITION_POSITION;
```

> ⚠️ **Un backup complet de la base doit avoir été effectué avant toute purge réelle (`p_dry_run=0`).
> Les données supprimées par DROP PARTITION sont IRRÉCUPÉRABLES sans restauration du backup.**

### Étape 2 — Simulation (DRY RUN obligatoire)

```sql
-- Simuler la purge complète (aucun DROP réel)
-- Examiner IDP_MAINTENANCE_LOG après pour valider les partitions ciblées
BEGIN
    PKG_IDP_MAINTENANCE.purge_old_partitions(
        p_retention_executions => 24,
        p_retention_audit_log  => 12,
        p_dry_run              => 1   -- ← SIMULATION
    );
END;
/

-- Vérifier les résultats de la simulation
SELECT EXECUTED_AT, TABLE_NAME, PARTITION_NAME, ACTION, STATUS, NOTES
FROM IDP_MAINTENANCE_LOG
WHERE DRY_RUN = 1
ORDER BY EXECUTED_AT DESC;
```

### Étape 3 — Validation des résultats DRY RUN

Vérifier que :
- Les partitions listées avec `ACTION='DROP'` sont bien hors de la fenêtre de rétention.
- Les partitions dans la fenêtre sont bien conservées (absentes du log ou STATUS='KEEP').
- Le nombre de lignes estimé (`NOTES`) est cohérent avec les attentes.

### Étape 4 — Exécution réelle

```sql
-- Exécution réelle — EXECUTIONS uniquement (AUDIT_LOG reste en dry_run)
BEGIN
    PKG_IDP_MAINTENANCE.purge_executions(
        p_retention_months => 24,
        p_dry_run          => 0   -- ← EXÉCUTION RÉELLE
    );
END;
/

-- Exécution AUDIT_LOG uniquement (après validation conformité SOC1/NFR8)
-- ⚠️ NE PAS EXÉCUTER SANS VALIDATION CONFORMITÉ
BEGIN
    PKG_IDP_MAINTENANCE.purge_audit_log(
        p_retention_months => 12,
        p_dry_run          => 0   -- ← EXÉCUTION RÉELLE
    );
END;
/

-- Ou exécution combinée (les deux tables en une seule commande)
BEGIN
    PKG_IDP_MAINTENANCE.purge_old_partitions(
        p_retention_executions => 24,
        p_retention_audit_log  => 12,
        p_dry_run              => 0
    );
END;
/
```

### Étape 5 — Vérification post-purge

```sql
-- Vérifier les partitions restantes
SELECT TABLE_NAME, PARTITION_NAME, HIGH_VALUE, NUM_ROWS
FROM USER_TAB_PARTITIONS
WHERE TABLE_NAME IN ('EXECUTIONS', 'AUDIT_LOG')
ORDER BY TABLE_NAME, PARTITION_POSITION;

-- Vérifier l'intégrité des index globaux (doivent être VALID après UPDATE GLOBAL INDEXES)
SELECT INDEX_NAME, TABLE_NAME, STATUS, PARTITIONED
FROM USER_INDEXES
WHERE TABLE_NAME IN ('EXECUTIONS', 'AUDIT_LOG')
  AND STATUS != 'VALID'
ORDER BY TABLE_NAME, INDEX_NAME;
-- ↑ Résultat attendu : 0 lignes (tous les index doivent être VALID)

-- Consulter le log de maintenance
SELECT EXECUTED_AT, TABLE_NAME, PARTITION_NAME, ACTION, STATUS, DRY_RUN, NOTES
FROM IDP_MAINTENANCE_LOG
WHERE DRY_RUN = 0
  AND EXECUTED_AT > SYSDATE - 1
ORDER BY EXECUTED_AT DESC;
```

---

## 4. Paramètres configurables

La procédure `PKG_IDP_MAINTENANCE.purge_old_partitions` accepte les paramètres suivants :

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `p_retention_executions` | `NUMBER` | `24` | Rétention EXECUTIONS en mois |
| `p_retention_audit_log` | `NUMBER` | `12` | Rétention AUDIT_LOG en mois |
| `p_dry_run` | `NUMBER` | `1` | `1` = simulation (aucun DROP), `0` = exécution réelle |

Les procédures ciblées (`purge_executions`, `purge_audit_log`) acceptent `p_retention_months` et `p_dry_run`.

### Constantes du package (référence)

```sql
-- Voir dans USER_SOURCE :
SELECT TEXT FROM USER_SOURCE
WHERE NAME = 'PKG_IDP_MAINTENANCE' AND TYPE = 'PACKAGE'
ORDER BY LINE;
```

Les constantes `gc_retention_executions = 24` et `gc_retention_audit_log = 12` sont des valeurs de référence documentaires — les valeurs effectives sont passées en paramètres.

---

## 5. Rollback — IMPOSSIBLE après DROP PARTITION PURGE

> 🚨 **AVERTISSEMENT CRITIQUE**
>
> **Un DROP PARTITION PURGE est IRRÉVERSIBLE.**
> Oracle supprime physiquement les données sans passer par la Recycle Bin.
> Il n'existe aucun mécanisme de rollback transactionnel pour un DROP PARTITION.
>
> **Seule solution de récupération : restauration depuis un backup complet.**

### Procédure de rollback (uniquement via backup)

1. **Identifier** le backup valide antérieur à l'exécution de la purge.
2. **Restaurer** la base complète ou les datafiles concernés (procédure RMAN, selon l'infrastructure DBOPS).
3. **Valider** la cohérence des données après restauration (`COUNT(*)`, contraintes FK).
4. **Documenter** l'incident et la restauration dans le journal de maintenance.

### Prévention

- Toujours exécuter en mode `p_dry_run=1` avant `p_dry_run=0`.
- Toujours effectuer un backup avant toute purge réelle.
- Valider les partitions ciblées dans `IDP_MAINTENANCE_LOG` après le DRY RUN.

---

## 6. Avertissements AUDIT_LOG — SOC1/NFR8

### Contexte réglementaire

La table `AUDIT_LOG` est protégée par le trigger `TRG_AUDIT_LOG_IMMUTABLE` (V054) qui interdit les opérations `UPDATE` et `DELETE` (conformité SOC1/NFR8). Cependant, **DROP PARTITION est une opération DDL qui contourne ce trigger**.

### 🚨 Précautions obligatoires avant activation en production

1. **Valider avec l'équipe conformité/sécurité** que la suppression de logs d'audit au-delà de la durée de rétention est autorisée par :
   - Les accords SOC 2 Type II en vigueur.
   - Les politiques internes de conservation des données.
   - Les obligations réglementaires applicables (RGPD, secteur bancaire, etc.).

2. **Documenter la décision de conformité** : la validation de l'équipe conformité doit être consignée par écrit (ticket ITSM, email officiel) avant toute purge AUDIT_LOG réelle.

3. **La procédure a `p_dry_run=1` par défaut** : la purge AUDIT_LOG ne peut être activée qu'en passant explicitement `p_dry_run=0`. Ce choix est délibéré pour éviter toute activation accidentelle.

### Activation — procédure recommandée

```sql
-- UNIQUEMENT après validation conformité signée
-- Remplacer <ticket_itsm> par le numéro du ticket de validation
-- Exemple : p_dry_run => 0 (activation après approbation ITSM-12345)
BEGIN
    PKG_IDP_MAINTENANCE.purge_audit_log(
        p_retention_months => 12,  -- ou 24 selon décision conformité
        p_dry_run          => 0
    );
END;
/
```

---

## 7. Planification automatique — DBMS_SCHEDULER (optionnel)

Le déclenchement automatique via `DBMS_SCHEDULER` est une option pour automatiser la purge mensuelle. **Ce script est fourni à titre indicatif et n'est pas activé par V087.**

```sql
-- Créer un job DBMS_SCHEDULER pour exécuter la purge le 1er de chaque mois à 03:00 UTC
-- ADAPTER : p_dry_run => 0 uniquement après validation (voir §3 et §6)
BEGIN
    DBMS_SCHEDULER.CREATE_JOB(
        job_name        => 'JOB_IDP_MAINTENANCE_PURGE',
        job_type        => 'PLSQL_BLOCK',
        job_action      => '
            BEGIN
                PKG_IDP_MAINTENANCE.purge_old_partitions(
                    p_retention_executions => 24,
                    p_retention_audit_log  => 12,
                    p_dry_run              => 1  -- ← Passer à 0 après validation
                );
            END;',
        start_date      => TRUNC(ADD_MONTHS(SYSDATE, 1), 'MM') + 3/24,  -- 1er mois suivant à 03:00
        repeat_interval => 'FREQ=MONTHLY; BYMONTHDAY=1; BYHOUR=3; BYMINUTE=0; BYSECOND=0',
        enabled         => FALSE,  -- ← Activer manuellement après validation
        auto_drop       => FALSE,
        comments        => 'Purge mensuelle partitions IDP (EXECUTIONS + AUDIT_LOG). Story 40.5.'
    );
END;
/

-- Pour activer le job après validation :
-- EXEC DBMS_SCHEDULER.ENABLE('JOB_IDP_MAINTENANCE_PURGE');

-- Pour vérifier l'état du job :
-- SELECT JOB_NAME, STATE, LAST_START_DATE, NEXT_RUN_DATE FROM USER_SCHEDULER_JOBS
-- WHERE JOB_NAME = 'JOB_IDP_MAINTENANCE_PURGE';
```

> **Note :** Si l'infrastructure utilise Control-M ou un scheduler externe, préférer le déclenchement via API Control-M avec appel à `PKG_IDP_MAINTENANCE.purge_old_partitions`. Contacter l'équipe DBOPS pour la configuration.

---

## 8. Monitoring et vérification

### Tableau de bord IDP_MAINTENANCE_LOG

```sql
-- Résumé des dernières purges (30 derniers jours)
SELECT
    TRUNC(EXECUTED_AT, 'DD')    AS PURGE_DATE,
    TABLE_NAME,
    ACTION,
    STATUS,
    DRY_RUN,
    COUNT(*)                    AS NB_PARTITIONS,
    MAX(NOTES)                  AS SAMPLE_NOTES
FROM IDP_MAINTENANCE_LOG
WHERE EXECUTED_AT > SYSDATE - 30
GROUP BY TRUNC(EXECUTED_AT, 'DD'), TABLE_NAME, ACTION, STATUS, DRY_RUN
ORDER BY PURGE_DATE DESC, TABLE_NAME, ACTION;

-- Vérifier les erreurs récentes
SELECT EXECUTED_AT, TABLE_NAME, PARTITION_NAME, NOTES
FROM IDP_MAINTENANCE_LOG
WHERE STATUS = 'ERROR'
ORDER BY EXECUTED_AT DESC;
```

### Vérification de l'état des index après purge

```sql
-- Tous les index EXECUTIONS et AUDIT_LOG doivent être VALID
SELECT INDEX_NAME, TABLE_NAME, STATUS, PARTITIONED, INDEX_TYPE
FROM USER_INDEXES
WHERE TABLE_NAME IN ('EXECUTIONS', 'AUDIT_LOG', 'EXECUTION_STEPS')
ORDER BY TABLE_NAME, INDEX_NAME;
```

### Références

- **Migration V087** : `idp-portal/database/migrations/V087__create_purge_procedure.sql`
- **Rollback V087** : `idp-portal/database/rollback/V087__create_purge_procedure_rollback.sql`
- **Note DBA 40.1** : `idp-portal/django_backend/docs/performance/dba-validation-partitionnement-40-1.md`
- **Story 40.5** : `_bmad-output/implementation-artifacts/40-5-procedure-purge-politique-retention.md`
- **Trigger immutabilité** : `idp-portal/database/migrations/V054__audit_log_immutable_trigger.sql`
