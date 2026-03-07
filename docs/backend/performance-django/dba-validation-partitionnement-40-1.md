# Note de validation DBA — Partitionnement Oracle
## Story 40.1 : Analyse des contraintes FK, index et requêtes

**Date :** 2026-02-24
**Auteur :** Agent Dev (claude-sonnet-4-6)
**Statut :** Prêt pour validation DBA
**Périmètre :** Tables EXECUTIONS, EXECUTION_STEPS, AUDIT_LOG
**Sources :** `executions/models.py`, `core/models.py`, `executions/views/`, `audit/views.py`, `executions/utils/filters.py`

---

## 1. Schéma actuel — Cartographie des tables et FK

### 1.1 Table EXECUTIONS (`executions/models.py:101`)

| Colonne | Type Django | Colonne Oracle | Contrainte | Notes |
|---------|------------|----------------|------------|-------|
| `id` | BigAutoField (PK) | `ID` NUMBER | PK | Séquentiel, identity column |
| `action_id` | ForeignKey(Action, CASCADE) | `ACTION_ID` | FK → ACTIONS | — |
| `user_id` | ForeignKey(User, CASCADE) | `USER_ID` | FK → USERS | — |
| `environment` | CharField(50) | `ENVIRONMENT` | CHECK constraint | DEV/STAGING/PROD |
| `parameters` | TextField (CLOB) | `PARAMETERS` | nullable | JSON sérialisé |
| `status` | CharField(20) | `STATUS` | CHECK constraint | 8 valeurs possibles |
| `servicenow_change_id` | CharField(100) | `SERVICENOW_CHANGE_ID` | nullable | — |
| `approved_by` | ForeignKey(User, SET_NULL) | `APPROVED_BY` | FK nullable → USERS | — |
| `approved_at` | DateTimeField | `APPROVED_AT` | nullable | — |
| `approval_comment` | CharField(1000) | `APPROVAL_COMMENT` | nullable | — |
| `parent_execution_id` | ForeignKey('self', SET_NULL) | `PARENT_EXECUTION_ID` | FK auto-ref nullable → EXECUTIONS | Remédiation V033 |
| `error_message` | TextField (CLOB) | `ERROR_MESSAGE` | nullable | — |
| `started_at` | DateTimeField | `STARTED_AT` | nullable | — |
| `completed_at` | DateTimeField | `COMPLETED_AT` | nullable | — |
| `created_at` | DateTimeField (auto_now_add) | `CREATED_AT` | **clé de partition cible** | Jamais modifié |

**Index existants (`models.py:173–174`) :**
```text
idx_exec_action_created : (ACTION_ID, CREATED_AT)
```

**Auto-référence :** `PARENT_EXECUTION_ID` → `EXECUTIONS.ID` (SET_NULL, nullable) — présente une auto-référence FK sur la même table partitionnée.

### 1.2 Table EXECUTION_STEPS (`executions/models.py:276`)

| Colonne | Type Django | Colonne Oracle | Contrainte | Notes |
|---------|------------|----------------|------------|-------|
| `id` | BigAutoField (PK) | `ID` | PK | — |
| `execution_id` | ForeignKey(Execution, CASCADE) | `EXECUTION_ID` | FK → EXECUTIONS | **Candidat Reference Partitioning** |
| `step_order` | IntegerField | `STEP_ORDER` | — | — |
| `step_name` | CharField(255) | `STEP_NAME` | — | — |
| `step_type` | CharField(50) | `STEP_TYPE` | CHECK constraint | 5 types |
| `status` | CharField(20) | `STATUS` | CHECK constraint | 6 valeurs |
| `started_at` | DateTimeField | `STARTED_AT` | nullable | — |
| `completed_at` | DateTimeField | `COMPLETED_AT` | nullable | — |
| `output` | TextField (CLOB) | `OUTPUT` | nullable | JSON sérialisé |
| `platform_job_id` | CharField(255) | `PLATFORM_JOB_ID` | nullable | — |
| `error_message` | TextField (CLOB) | `ERROR_MESSAGE` | nullable | — |
| `created_at` | DateTimeField (auto_now_add) | `CREATED_AT` | colonne date | Jamais modifié |

**Contrainte unique :** `unique_together = [['execution', 'step_order']]` → index unique Oracle `UK_EXECUTION_STEPS_EXEC_ORDER` sur `(EXECUTION_ID, STEP_ORDER)`.

### 1.3 Table EXECUTION_TARGETS (`executions/models.py:209`)

| Colonne | Type | Contrainte | Notes |
|---------|------|------------|-------|
| `id` | BigAutoField (PK) | PK | — |
| `execution_id` | ForeignKey(Execution, CASCADE) | FK → EXECUTIONS | — |
| `target_type` | CharField(50) | CHECK | SERVER/DB/CLUSTER/... |
| `target_id` | CharField(200) | — | — |
| `target_name` | CharField(255) | — | — |
| `target_metadata` | TextField (CLOB) | nullable | JSON |
| `created_at` | DateTimeField (auto_now_add) | — | — |

**Contrainte unique :** `unique_together = [['execution', 'target_type', 'target_id']]`

### 1.4 Table AUDIT_LOG (`core/models.py:215`)

| Colonne | Type Django | Colonne Oracle | Contrainte | Notes |
|---------|------------|----------------|------------|-------|
| `id` | BigAutoField (PK) | `ID` | PK | — |
| `timestamp` | DateTimeField (auto_now_add) | `TIMESTAMP` | **clé de partition cible** | Jamais modifié |
| `user_id` | CharField(100) | `USER_ID` | — | String, pas de FK |
| `action_type` | CharField(50) | `ACTION_TYPE` | CHECK | ~50 valeurs |
| `entity_type` | CharField(50) | `ENTITY_TYPE` | CHECK | ~12 valeurs |
| `entity_id` | BigIntegerField | `ENTITY_ID` | **pas de FK Oracle** | Relation logique uniquement |
| `details` | TextField (CLOB) | `DETAILS` | nullable | JSON |
| `ip_address` | CharField(45) | `IP_ADDRESS` | nullable | — |
| `correlation_id` | CharField(64) | `CORRELATION_ID` | nullable | — |

**Aucune FK entrante** sur AUDIT_LOG. Immutabilité enforced au niveau ORM (save/delete/update overrides).

### 1.5 Table SCHEDULED_EXECUTIONS (`executions/models.py:376`)

| Colonne | Type | Contrainte | Notes |
|---------|------|------------|-------|
| `id` | BigAutoField (PK) | PK | — |
| `action_id` | ForeignKey(Action, CASCADE) | FK → ACTIONS | — |
| `user_id` | ForeignKey(User, CASCADE) | FK → USERS | — |
| `execution_id` | **BigIntegerField** | **PAS de FK** | Référence brute, pas de contrainte Oracle |
| `created_at` | DateTimeField (auto_now_add) | — | — |

> **Point critique :** `SCHEDULED_EXECUTIONS.EXECUTION_ID` est un `BigIntegerField`, **non** une `ForeignKey`. Il n'y a donc **aucune contrainte FK Oracle** entre SCHEDULED_EXECUTIONS et EXECUTIONS. Ce champ est une référence applicative seulement — impact nul lors du partitionnement.

### 1.6 Table RECURRING_PATTERNS (`executions/models.py:450`)

| Colonne | Type | Contrainte | Notes |
|---------|------|------------|-------|
| `id` | BigAutoField (PK) | PK | — |
| `scheduled_execution_id` | OneToOneField(ScheduledExecution, CASCADE) | FK → SCHEDULED_EXECUTIONS | Aucune relation directe avec EXECUTIONS |

**Aucune FK directe** vers EXECUTIONS.

---

## 2. Synthèse des FK entrantes vers EXECUTIONS

| Table enfant | Colonne FK | On Delete | Type | Impact partitionnement |
|-------------|-----------|-----------|------|----------------------|
| `EXECUTION_STEPS` | `EXECUTION_ID` | CASCADE | ForeignKey | **Candidat Reference Partitioning** |
| `EXECUTION_TARGETS` | `EXECUTION_ID` | CASCADE | ForeignKey | FK classique, pas de partitionnement requis |
| `EXECUTIONS` | `PARENT_EXECUTION_ID` | SET_NULL | ForeignKey (self) | Auto-référence → voir §3.4 |
| `SCHEDULED_EXECUTIONS` | `EXECUTION_ID` | — | BigIntegerField (**pas FK**) | **Aucun impact** |

---

## 3. Analyse des contraintes Oracle FK + partitionnement

### 3.1 ENABLE ROW MOVEMENT

Oracle requiert `ENABLE ROW MOVEMENT` sur une table partitionnée si une ligne peut changer de partition (modification de la clé de partition).

**Analyse :**
- `EXECUTIONS.CREATED_AT` → `auto_now_add=True` → **jamais modifié** par Django ORM
- `AUDIT_LOG.TIMESTAMP` → `auto_now_add=True` → **jamais modifié**

**Recommandation :** `ENABLE ROW MOVEMENT` **non nécessaire** en conditions normales. Cependant, le DBA devrait le confirmer en vérifiant qu'aucun script SQL externe (migration, correction de données) ne modifie `CREATED_AT`/`TIMESTAMP` directement. Si des scripts SQL out-of-band existent, activer ROW MOVEMENT par précaution.

### 3.2 Oracle Reference Partitioning pour EXECUTION_STEPS

**Principe :** `PARTITION BY REFERENCE (fk_execution_id)` — EXECUTION_STEPS hériterait automatiquement la structure de partitions de EXECUTIONS.

| Critère | Évaluation |
|---------|-----------|
| Prérequis FK | FK `EXECUTION_ID → EXECUTIONS.ID` existe et est enabled ✅ |
| Parent partitionné en premier | EXECUTIONS doit être migré avant EXECUTION_STEPS ✅ |
| Avantage principal | Jointures `EXECUTIONS ↔ EXECUTION_STEPS` bénéficient du **partition-wise join** automatiquement ✅ |
| Pruning auto | `WHERE execution_id = X` suffit — Oracle déduit la partition depuis EXECUTIONS ✅ |
| Inconvénient | EXECUTION_STEPS ne peut pas être purgé indépendamment de EXECUTIONS ⚠️ |
| Contrainte | La FK doit rester ENABLED (pas de DISABLE sur cette contrainte) ⚠️ |
| Contrainte | `unique_together(execution, step_order)` → l'index unique doit être compatible (voir §3.5) ⚠️ |

**Recommandation DBA :** Privilégier le **Reference Partitioning** pour EXECUTION_STEPS. Les purges seront alignées sur les partitions d'EXECUTIONS (drop partition parent → drop partition enfant automatiquement).

### 3.3 Alternative : EXECUTION_STEPS partitionné par CREATED_AT

Si le Reference Partitioning est jugé trop contraignant (ex : besoin de rétention indépendante des steps) :

| Critère | Évaluation |
|---------|-----------|
| Clé de partition | `CREATED_AT` (auto_now_add, jamais modifié) ✅ |
| Pruning | `WHERE created_at BETWEEN ...` suffit ✅ |
| Indépendance | Rétention et purge indépendantes de EXECUTIONS ✅ |
| Jointure | Pas de partition-wise join automatique — full join cross-partition possible ⚠️ |
| Simplicité DDL | Plus simple — pas de dépendance sur EXECUTIONS ✅ |
| Cohérence | En théorie, un step de la même execution peut être dans une partition différente si l'execution était en cours au changement de mois (peu probable en pratique) ⚠️ |

**Recommandation DBA :** Utiliser l'alternative CREATED_AT uniquement si la rétention différenciée est une exigence métier. Sinon, préférer le Reference Partitioning.

### 3.4 Auto-référence PARENT_EXECUTION_ID

Oracle supporte une FK d'une table partitionnée vers elle-même. Avec `ON DELETE SET NULL`, le cas d'utilisation est : si une execution parent est supprimée (par purge), les remediations enfants ont `PARENT_EXECUTION_ID = NULL`.

**Analyse :**
- La purge se fait par **drop partition** (pas DELETE ligne à ligne) → Oracle gère le SET_NULL implicitement sur drop partition ? **Non** — le DROP PARTITION sur EXECUTIONS avec FK CASCADE depuis EXECUTION_STEPS supprime les steps mais **ne met pas SET_NULL** sur `PARENT_EXECUTION_ID` d'autres rows EXECUTIONS.
- Risque : après drop d'une vieille partition EXECUTIONS, des executions récentes avec `PARENT_EXECUTION_ID` pointant vers des executions de la partition supprimée auront une **FK orpheline** si la contrainte n'est pas DEFERRED ou DISABLE.

**Recommandation :**
1. Documenter cette dépendance pour la story 40.5 (procédure de purge).
2. Lors du DROP PARTITION, exécuter avant : `UPDATE EXECUTIONS SET PARENT_EXECUTION_ID = NULL WHERE PARENT_EXECUTION_ID IN (SELECT ID FROM EXECUTIONS PARTITION (p_old_partition))` — ou désactiver temporairement la contrainte FK auto-ref pendant le DROP.
3. Alternative : définir la contrainte FK auto-ref comme `DEFERRABLE INITIALLY DEFERRED`.

### 3.5 Index PK sur EXECUTIONS après partitionnement

Oracle impose que la clé de partition soit incluse dans les index UNIQUE (ou PK) pour un **index local prefixed**.

| Type d'index | Compatibilité avec PK (ID) | Performance |
|-------------|--------------------------|-------------|
| **Global (non-prefixed)** | ✅ Compatible avec PK séquentiel sur ID | Coûteux à maintenir (index invalide lors de DDL partitions) — doit être `REBUILD` après DROP PARTITION |
| **Local prefixed** sur (CREATED_AT, ID) | ❌ Incompatible avec PK sur ID seul (doit inclure CREATED_AT dans PK) | Maintenance automatique avec partitions |
| **Local non-prefixed** sur (ID) | ✅ Possible mais déconseillé (performances dégradées) | Index local mais non-prefixed — Oracle ne garantit pas le pruning |

**Conclusion :** L'index PK sur `ID` (BigAutoField séquentiel) devra rester un **index global**. C'est le comportement standard pour les tables partitionnées avec PK surrogate. L'index global est plus coûteux lors des opérations DDL sur les partitions (DROP PARTITION → GLOBAL INDEX REBUILD) mais c'est inévitable avec un PK non lié à la clé de partition.

**Recommandation :** Planifier `ALTER INDEX pk_executions REBUILD` (ou `UPDATE GLOBAL INDEXES`) lors des opérations de DROP PARTITION dans la procédure de purge (story 40.5).

### 3.6 Index `idx_exec_action_created` sur EXECUTIONS

Cet index existe sur `(ACTION_ID, CREATED_AT)` (voir `models.py:174`). Avec le partitionnement par `CREATED_AT` :

| Option | Compatibilité | Recommandation |
|--------|--------------|----------------|
| Index local prefixed sur (CREATED_AT, ACTION_ID) | ✅ CREATED_AT est la clé de partition → prefixed | ⚠️ Ordre différent — filtres sur ACTION_ID seul ne bénéficient plus de cet index |
| Index local non-prefixed sur (ACTION_ID, CREATED_AT) | ✅ Possible | Déconseillé (performances dégradées) |
| Index global sur (ACTION_ID, CREATED_AT) | ✅ Compatible | Reconstruction lors des DROP PARTITION ⚠️ |

**Recommandation :** Recréer comme **index local prefixed** `IDX_EXECUTIONS_CREATED_ACTION` sur `(CREATED_AT, ACTION_ID)`. Les requêtes filtrant par plage de dates ET action bénéficieront du partition pruning. Les requêtes filtrant par `action_id` seul (sans date) devront être documentées comme requêtes à risque (voir §4).

### 3.7 Index unique sur EXECUTION_STEPS

Contrainte `unique_together = [['execution', 'step_order']]` → index unique Oracle `UK_EXECUTION_STEPS_EXEC_ORDER` sur `(EXECUTION_ID, STEP_ORDER)`.

| Stratégie EXECUTION_STEPS | Impact sur l'index unique |
|--------------------------|--------------------------|
| **Reference Partitioning** | L'index peut être **local prefixed** (EXECUTION_ID est la clé de partition héritée) → maintenance automatique ✅ |
| **Partitionnement par CREATED_AT** | L'index sur (EXECUTION_ID, STEP_ORDER) est **non-prefixed** → devient un index global ou local non-prefixed. Recommandation : index global pour garantir l'unicité inter-partitions ⚠️ |

---

## 4. Analyse des requêtes principales

### 4.1 Requêtes sur EXECUTIONS

| QuerySet / Vue | Fichier | Filtre CREATED_AT | Partition Pruning | Risque |
|---------------|---------|------------------|------------------|--------|
| `list_by_user` | `models.py:51` | Aucun (filtre USER_ID uniquement) | ❌ Scan toutes partitions | ⚠️ HAUT — sans plage de dates, scan complet |
| `list_by_status` | `models.py:63` | Aucun (filtre STATUS uniquement) | ❌ Scan toutes partitions | ⚠️ HAUT |
| `get_recent` | `models.py:75` | `order_by('-created_at')[:limit]` | ⚠️ Partiel — Oracle commence par la dernière partition | Acceptable si LIMIT suffisamment petit |
| `ExecutionsListView` + dates | `list_views.py:63` | `created_at__gte/lt` si start_date/end_date fournis | ✅ Pruning si dates fournies | Acceptable |
| `ExecutionsListView` sans dates | `list_views.py:63` | Aucun | ❌ Scan toutes partitions | ⚠️ HAUT — cas fréquent UI |
| `ExecutionStatsView` (jour courant) | `list_views.py:84` | `created_at__gte=today_start` | ✅ 1–2 partitions | OK |
| `ExecutionStatsView` (compteurs statut) | `list_views.py:94–101` | **Conditionnel** : bounded si start_date/end_date fournis via `apply_execution_filters` ; sinon filtre STATUS seul | ❌ Scan toutes partitions **si aucune date fournie** | ⚠️ HAUT — cas d'appel sans date (dashboard sans filtre) |
| `ExecutionTimeSeriesView` | `list_views.py:121` | `created_at__gte/lt` (7j par défaut) | ✅ Pruning sur 7j/30j | OK |
| `ExecutionDetailView` | `execution_views.py:256` | Lookup par PK (ID) | Index global PK | OK |
| `ExecutionStepsView` | `execution_views.py:434` | `filter(execution_id=X)` | ✅ si ref partitioning | OK — double lookup : `Execution.objects.get(id=X)` via index global PK puis steps partition-wise |
| **`ExecutionTagsView`** | `list_views.py:158` | **Aucun** (`values_list("action_id").distinct()`) | ❌ Scan toutes partitions | ⚠️ **HAUT — manquant** : aucun filtre date/scope, scan complet à chaque appel UI |

### 4.2 Requêtes sur AUDIT_LOG

| QuerySet / Vue | Fichier | Filtre TIMESTAMP | Partition Pruning | Risque |
|---------------|---------|-----------------|------------------|--------|
| `list_by_date_range` | `core/models.py:196` | `timestamp__gte/lte` | ✅ Pruning | OK |
| `list_by_entity` | `core/models.py:171` | Aucun (filtre entity_type + entity_id) | ❌ Scan toutes partitions | ⚠️ MOYEN |
| `list_by_user` | `core/models.py:184` | Aucun (filtre user_id) | ❌ Scan toutes partitions | ⚠️ MOYEN |
| `_build_audit_queryset` + from/to | `audit/views.py:148` | `timestamp__gte/lte` si fournis | ✅ Pruning si dates fournies | OK |
| `_build_audit_queryset` sans dates | `audit/views.py:148` | Aucun (entity_type=EXECUTION seul) | ❌ Scan toutes partitions | ⚠️ HAUT — cas sans filtre date |
| `_build_audit_queryset` + filtre status/env/action | `audit/views.py:160–191` | Aucun sur EXECUTIONS | ❌ Sous-requête `Execution.objects.filter(status__in=...)` sans date → scan toutes partitions EXECUTIONS | ⚠️ HAUT — la sous-requête Django `entity_id__in=exec_ids` génère un sous-SELECT sur EXECUTIONS sans filtre date ; post-partitionnement, ce sous-SELECT scanne toutes les partitions EXECUTIONS pour construire les IDs |
| Export CSV | `audit/views.py:347` | Dépend des filtres passés | Variable | Même risque que ci-dessus, amplifié par la limite 10 000 lignes |

### 4.3 Requêtes à risque identifiées — recommandations

| Requête | Risque | Recommandation |
|---------|--------|----------------|
| `list_by_user` (EXECUTIONS) | Scan multi-partitions sur USER_ID | Ajouter index local prefixed `IDX_EXECUTIONS_CREATED_USER` sur `(CREATED_AT, USER_ID)` **ou** imposer une plage de dates par défaut côté API (ex: 90j) |
| `list_by_status` (EXECUTIONS) | Scan multi-partitions sur STATUS | STATUS est peu sélectif (8 valeurs) — index peu efficace. Recommandation : ajouter `created_at__gte` par défaut pour les statuts actifs (SUBMITTED, RUNNING) |
| `ExecutionsListView` sans dates | Scan multi-partitions si scope=all | Imposer une fenêtre de dates par défaut côté API (ex: 30 derniers jours) si non spécifiée |
| `ExecutionStatsView` compteurs | Scan multi-partitions | Pour les compteurs de statut actifs (RUNNING, SUBMITTED), filtrer `created_at >= (NOW - 7 days)` — les executions RUNNING de plus de 7 jours sont anomalies |
| `list_by_entity` (AUDIT_LOG) | Scan multi-partitions sur entity_id | Ajouter index local `IDX_AUDITLOG_CREATED_ENTITY` sur `(TIMESTAMP, ENTITY_TYPE, ENTITY_ID)` |
| `list_by_user` (AUDIT_LOG) | Scan multi-partitions sur user_id | Ajouter index `IDX_AUDITLOG_CREATED_USER` sur `(TIMESTAMP, USER_ID)` |
| Audit sans plage de dates | Scan complet AUDIT_LOG | Imposer un filtre de date par défaut côté API audit (ex: 30 derniers jours) |
| **`ExecutionTagsView`** (EXECUTIONS) | Scan complet toutes partitions sans aucun filtre (`values_list("action_id").distinct()`) | Ajouter un index global sur `ACTION_ID` ou réécrire en passant par `Action.objects.filter(...)` directement (évite EXECUTIONS entièrement) |
| **Sous-requêtes `entity_id__in`** (`_build_audit_queryset` status/env/action) | Sous-SELECT sur EXECUTIONS sans filtre date → scan toutes partitions EXECUTIONS | Ajouter un filtre date sur les sous-requêtes EXECUTIONS (ex: `created_at >= NOW - 90 days`) ou utiliser une borne temporelle implicite sur la vue audit |
| **Index `AUDIT_LOG.TIMESTAMP` absent aujourd'hui** | Gap pré-partitionnement : full scan + sort sur toute la table actuelle | Créer `IDX_AUDITLOG_TIMESTAMP` **avant** la migration de partitionnement comme action immédiate (Quick Win) |

---

## 5. Tableau synthétique — Recommandation de partitionnement

| Table | Clé de partition | Type | Granularité | Partition « active » | Rétention suggérée | Fenêtre maintenance |
|-------|----------------|------|-------------|---------------------|-------------------|-------------------|
| **EXECUTIONS** | `CREATED_AT` | RANGE mensuel | 1 partition/mois | Mois courant | 24 mois | **8–12h** (index global rebuild + FK) |
| **EXECUTION_STEPS** | Reference FK (EXECUTION_ID) | REFERENCE | Héritée de EXECUTIONS | Alignée EXECUTIONS | Alignée EXECUTIONS | Automatique (cascade) |
| **AUDIT_LOG** | `TIMESTAMP` | RANGE mensuel | 1 partition/mois | Mois courant | 12–24 mois (conformité) | **4–6h** (pas de FK entrante) |

---

## 6. Index à adapter / créer

### 6.1 Index EXECUTIONS

| Index | Statut actuel | Après partitionnement | Type cible | Naming convention |
|-------|--------------|----------------------|------------|-------------------|
| PK sur ID | Global | **Garder Global** | Index global | PK_EXECUTIONS |
| `idx_exec_action_created` sur (ACTION_ID, CREATED_AT) | Global | **Recréer** en local prefixed (CREATED_AT, ACTION_ID) | Local prefixed | `IDX_EXECUTIONS_CREATED_ACTION` |
| Nouvel index USER_ID + date | Absent | **À créer** | Local prefixed | `IDX_EXECUTIONS_CREATED_USER` |
| Nouvel index STATUS + date | À évaluer | Optionnel — STATUS peu sélectif | Local prefixed | `IDX_EXECUTIONS_CREATED_STATUS` (si volume justifie) |

### 6.2 Index EXECUTION_STEPS

| Index | Statut actuel | Après partitionnement | Type cible | Naming |
|-------|--------------|----------------------|------------|--------|
| PK sur ID | Global | **Garder Global** | Index global | PK_EXECUTION_STEPS |
| UK `(EXECUTION_ID, STEP_ORDER)` | Global unique | Reference partitioning → **local prefixed** (EXECUTION_ID est clé héritée) | Local unique | `UK_EXEC_STEPS_EXEC_ORDER` |

### 6.3 Index AUDIT_LOG

| Index | Statut actuel | Après partitionnement | Type cible | Naming |
|-------|--------------|----------------------|------------|--------|
| PK sur ID | Global | **Garder Global** | Index global | PK_AUDIT_LOG |
| Index TIMESTAMP | **Absent aujourd'hui** (Meta.ordering = ['-timestamp'] sans index défini dans Django) → **gap pré-partitionnement actuel** : full scan + sort sur toute la table | **À créer immédiatement** (indépendant du partitionnement) puis migrer en local prefixed | Local prefixed | `IDX_AUDITLOG_TIMESTAMP` |
| Index ENTITY_TYPE + ENTITY_ID | Absent | **À créer** | Local prefixed | `IDX_AUDITLOG_CREATED_ENTITY` sur (TIMESTAMP, ENTITY_TYPE, ENTITY_ID) |
| Index USER_ID | Absent | **À créer** | Local prefixed | `IDX_AUDITLOG_CREATED_USER` sur (TIMESTAMP, USER_ID) |
| Index CORRELATION_ID | Absent | **À créer** optionnel | Local ou global | `IDX_AUDITLOG_CORRELATION_ID` (si requêtes fréquentes) |

---

## 7. Contraintes FK — Plan de mitigation

| Contrainte | Table enfant | Risque | Mitigation |
|-----------|-------------|--------|------------|
| FK `EXECUTION_STEPS.EXECUTION_ID` | EXECUTION_STEPS | Aucun si Reference Partitioning (géré automatiquement) | — |
| FK `EXECUTION_TARGETS.EXECUTION_ID` | EXECUTION_TARGETS | Pas de partitionnement EXECUTION_TARGETS → FK classique | Vérifier que DROP PARTITION CASCADE gère les lignes EXECUTION_TARGETS (ou purger avant DROP PARTITION) |
| FK auto-ref `EXECUTIONS.PARENT_EXECUTION_ID` | EXECUTIONS | DROP PARTITION ne cascade pas le SET_NULL → FK orpheline potentielle | Avant DROP PARTITION : `UPDATE EXECUTIONS SET PARENT_EXECUTION_ID = NULL WHERE PARENT_EXECUTION_ID IN (SELECT ID FROM old_partition)` |
| `SCHEDULED_EXECUTIONS.EXECUTION_ID` (BigIntegerField) | SCHEDULED_EXECUTIONS | **Pas de FK Oracle** → aucun problème | Documenter que ce champ peut pointer vers une execution supprimée (comportement déjà possible aujourd'hui) |

---

## 8. Faisabilité et risques

### 8.1 Conclusion de faisabilité

| Table | Faisabilité | Complexité | Risques principaux |
|-------|------------|-----------|-------------------|
| **EXECUTIONS** | ✅ Faisable | Élevée | Index global PK rebuild, FK auto-ref PARENT_EXECUTION_ID, EXECUTION_TARGETS sans partitionnement |
| **EXECUTION_STEPS** | ✅ Faisable (Reference Partitioning recommandé) | Moyenne | Dépend de EXECUTIONS, unique_together à recréer en local prefixed |
| **AUDIT_LOG** | ✅ Faisable | Faible | Aucune FK entrante, table indépendante → migration la plus simple |

**Faisabilité globale : OUI** — le partitionnement range mensuel est techniquement faisable sur les trois tables. Aucun obstacle bloquant identifié dans le code Django.

### 8.2 Risques identifiés

| Risque | Sévérité | Probabilité | Mitigation |
|--------|---------|------------|------------|
| Index global PK rebuild coûteux lors des DROP PARTITION | Moyen | Certaine | Planifier `UPDATE GLOBAL INDEXES` dans la procédure de purge (story 40.5) |
| FK auto-ref PARENT_EXECUTION_ID orpheline après DROP PARTITION | Élevé | Si pas mitigé | Script pre-DROP dans procédure purge |
| EXECUTION_TARGETS non-partitionné : FK vers partition supprimée | Moyen | Si pas mitigé | Purger EXECUTION_TARGETS avant DROP PARTITION EXECUTIONS |
| Requêtes sans filtre date → scan multi-partitions post-migration | Élevé | Certain si pas corrigé | Ajouter plages de dates par défaut côté API (stories 40.x) |
| Downtime lors de la migration initiale | Élevé | Certain | Fenêtre de maintenance requise (voir §9) |
| ENABLE ROW MOVEMENT non nécessaire mais à confirmer | Faible | Peu probable | Vérifier avec DBA qu'aucun script SQL externe modifie CREATED_AT |

---

## 9. Fenêtres de maintenance estimées

| Table | Ordre de migration | Estimation | Justification |
|-------|------------------|-----------|---------------|
| **AUDIT_LOG** | 1er (indépendante) | 4–6h | Volume potentiellement élevé (audit de toutes les actions), aucune FK entrante |
| **EXECUTIONS** | 2e | 8–12h | Table principale, index global rebuild, FK CASCADE multiples, volume important |
| **EXECUTION_STEPS** | 3e (après EXECUTIONS) | 2–4h | Reference Partitioning hérite la structure → migration DDL plus rapide |

> **Hypothèses :** Les estimations supposent une volumétrie de l'ordre de 1–10M lignes par table. À ajuster selon les volumes réels mesurés avant migration. Oracle recommande DBMS_REDEFINITION pour une migration en ligne (Online Table Redefinition) si un downtime zéro est requis.

**Option Online Table Redefinition (DBMS_REDEFINITION) :** Permet de migrer sans downtime applicatif mais complexifie le processus (synchronisation des DML pendant la migration). À évaluer avec le DBA selon les exigences de disponibilité.

---

## 10. Préconditions pour les stories 40.2–40.4

### Ordre impératif des migrations

```text
40.2 : Migration EXECUTIONS (partitionnement CREATED_AT)
    ↓
40.3 : Migration EXECUTION_STEPS (Reference Partitioning sur EXECUTIONS)
    ↓
40.4 : Migration AUDIT_LOG (partitionnement TIMESTAMP)
    Note : AUDIT_LOG peut aussi être fait avant EXECUTIONS (indépendante)
```

### Préconditions techniques avant 40.2

- [ ] Mesurer les volumes réels des tables (row count + taille segments) → ajuster les estimations de fenêtre de maintenance
- [ ] Confirmer avec DBA la nécessité d'ENABLE ROW MOVEMENT (vérifier scripts SQL externes)
- [ ] Valider la stratégie d'index global pour les PK (coût du REBUILD acceptable)
- [ ] Identifier les plages de dates par défaut à imposer dans l'API (corrige les requêtes sans filtre date) — à implémenter dans les stories d'amélioration des requêtes
- [ ] Confirmer la rétention métier : 24 mois EXECUTIONS, 12 mois AUDIT_LOG (à valider avec les équipes conformité/métier)
- [ ] Planifier la fenêtre de maintenance (coordination avec équipes infra/DBOPS)
- [ ] Documenter la procédure pre-DROP PARTITION pour la FK auto-ref PARENT_EXECUTION_ID

### Préconditions pour 40.3 (EXECUTION_STEPS)

- [ ] EXECUTIONS entièrement partitionnée et validée en production
- [ ] FK `EXECUTION_STEPS.EXECUTION_ID → EXECUTIONS.ID` ENABLED (vérifier dans USER_CONSTRAINTS)
- [ ] Choix définitif : Reference Partitioning vs partitionnement par CREATED_AT (recommandation : Reference Partitioning)

### Préconditions pour 40.4 (AUDIT_LOG)

- [ ] Confirmer la rétention conformité (SOC1/NFR8 — table immutable)
- [ ] Valider que DROP PARTITION AUDIT_LOG est compatible avec les exigences d'audit (certains régimes réglementaires interdisent la suppression de logs)
- [ ] Ajouter les index manquants (ENTITY_TYPE+ENTITY_ID, USER_ID) avant ou pendant la migration

---

## 11. Références

| Document | Chemin | Pertinence |
|---------|--------|------------|
| Epic 40 | `_bmad-output/planning-artifacts/epic-40-partitionnement-retention-tables-performance.md` | Contexte et périmètre |
| Modèles Django EXECUTIONS | `executions/models.py:101–500` | Schéma et FK |
| Modèles Django AUDIT_LOG | `core/models.py:215–273` | Schéma AUDIT_LOG |
| Vues liste exécutions | `executions/views/list_views.py` | QuerySets critiques |
| Vues CRUD exécutions | `executions/views/execution_views.py` | Queries detail/steps |
| Vues audit | `audit/views.py` | QuerySets AUDIT_LOG |
| Filtres exécutions | `executions/utils/filters.py` | `apply_execution_filters` |

---

*Document généré le 2026-02-24 dans le cadre de la story 40.1 — Analyse et validation DBA.*
*Ce document constitue la référence technique pour les stories 40.2–40.5 (implémentation des migrations Flyway).*
