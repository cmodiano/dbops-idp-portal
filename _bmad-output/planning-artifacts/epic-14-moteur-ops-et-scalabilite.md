# Epic 14 : Moteur Ops “targets-first” + robustesse d’exécution + scalabilité (Oracle)

## Objectif

Élever `idp-portal` d’un modèle “portail d’actions + exécutions” vers un **moteur d’opérations** de niveau production, en intégrant efficacement les capacités observées dans `dbops`, tout en conservant le principe **scheduler externe**.

Cet epic vise principalement :

- **Targets first-class**: exécution et scheduling multi-cibles, environnement dérivé de la cible, validation existence/techno/env via source inventaire (API ou schéma BD).
- **Robustesse moteur**: validations avant soumission, dépendances/mutex (concurrence), retries/backoff, transitions d’état fiables, audit complet.
- **Scalabilité Oracle**: partitionnement/rétention des tables à croissance non bornée, index adaptés aux écrans, et mécanismes d’agrégation/monitoring si nécessaire.

## Contexte

- `idp-portal` supporte déjà :
  - **Workflows catalogue** (`ITEM_TYPE='workflow'`) qui composent d’autres actions via `ACTIONS_CATALOG.EXECUTION_STEPS` (steps `action_reference`).
  - **Exécutions** (`EXECUTIONS`) et **étapes runtime** (`EXECUTION_STEPS`).
  - **Scheduling externe** (`SCHEDULED_EXECUTIONS` + `RECURRING_PATTERNS`) avec calcul du prochain run côté scheduler externe.
  - **Audit** (`AUDIT_LOG`) et **RBAC profils** (`PROFILES` + permissions).
- `dbops` apporte des patterns “moteur ops” que l’on souhaite intégrer :
  - cibles normalisées (`target_type_registry`, `*_target`), validations (existence, fenêtre maintenance, allowed env, techno),
  - dépendances/mutex, retries/backoff, traçabilité, et scalabilité (partitionnement, MViews, purge).

## Pré-requis / dépendances

- **Epic 13** (Sélection des targets + permissions par environnement dérivées du target) est un prérequis fonctionnel.
  - Si Epic 13 n’implémente pas la persistance relationnelle des targets (tables dédiées), cet epic la complète.

## Scope

### In scope

- Modèle de données “targets-first” pour :
  - `EXECUTIONS` (multi-targets),
  - `SCHEDULED_EXECUTIONS` (multi-targets),
  - résolution/validation des targets via registre.
- Politique d’exécution : retries/backoff, scheduling_mode, dépendances/mutex.
- Validation “maintenance window” **par consommation de l’inventaire** (lecture), sans persistance des fenêtres côté portail.
- Audit enrichi (événements d’exécution + décisions moteur).
- Scalabilité Oracle : partitionnement + rétention + indexation.

### Out of scope (explicit)

- Internaliser le scheduler (pas de Celery/Quartz/etc.). On conserve le scheduler externe.
- Remplacer le modèle “workflows catalogue” existant ; on se limite à améliorer l’exécution runtime et la traçabilité.

## Personas / cas d’usage

- **DBA**: exécuter une action sur une ou plusieurs cibles, avec validations/guardrails (fenêtre, dépendances, mutex).
- **DBOPS**: configurer les règles (dépendances, mutex, retries), diagnostiquer les échecs, assurer la rétention.
- **Sécurité / Audit**: extraire une trace complète, corrélée, immuable.
- **Scheduler externe**: déclencher les exécutions à partir des objets planifiés, et mettre à jour l’état.

## Principes de conception (clean implémentation)

- **Source of truth relationnelle** pour tout ce qui est filtrage/validation/permissions (targets, env, techno).
- **CLOB JSON** conservé pour payloads et outputs, mais on projette en colonnes/tables les champs “queryables”.
- **Idempotence** et **transitions d’état** défensives (éviter les doubles soumissions / doublons scheduler).
- **Scalabilité par design**: partitionnement des tables volumineuses et purge “drop partitions” quand possible.

---

## Stories

### Story 14.1 : Modèle “targets-first” — registre des types de cibles + résolution + validation

As a system,
I want un registre de types de cibles et une stratégie uniforme de résolution/validation (API inventaire ou schéma BD),
So that je peux valider l’existence d’un target, en déduire l’environnement/la techno, et auditer la cible de manière fiable.

**Acceptance Criteria**

- **Given** une configuration inventaire (integration type `inventory` ou `inventory_db`) est active,
  **When** un target est fourni à l’exécution (type + valeur),
  **Then** le backend le résout (ID/nom) et récupère au minimum `environment` et, si applicable, `db_technology`.
- **Given** un type de cible “externe” (validate_exists=false),
  **When** il est utilisé,
  **Then** la validation d’existence n’est pas bloquante mais la cible est quand même stockée et auditée.
- **And** la résolution est traçable : toute erreur de résolution est auditée et renvoyée de manière explicite.

**Notes d’implémentation (data)**

- Introduire une table `TARGET_TYPE_REGISTRY` (inspirée de `dbops.target_type_registry`), incluant :
  - `target_type` (PK), `validate_exists`, `source` (inventory_api / inventory_db), `lookup_config` (colonnes/synonymes), `enabled`, métadonnées.

---

### Story 14.2 : Exécutions multi-cibles — persistance relationnelle des targets d’exécution

As a DBA,
I want exécuter une action sur une ou plusieurs cibles, avec targets stockés de façon relationnelle,
So that l’autorisation, la validation, l’audit et le reporting ne dépendent pas d’un parsing de CLOB.

**Acceptance Criteria**

- **Given** une requête d’exécution contient `targets[]`,
  **When** l’exécution est créée,
  **Then** les targets sont persistés dans une table dédiée (une ligne par target), avec unicité (execution_id, target_type, target_ref).
- **Given** un target résolu,
  **When** l’exécution est créée,
  **Then** l’environnement de l’exécution est dérivé du target (règles Epic 13) et stocké de manière cohérente.
- **And** l’API permet de lister les exécutions filtrées par target (type + ref) sans scan de CLOB.

**Notes d’implémentation (data)**

- Table `EXECUTION_TARGETS` : `execution_id`, `target_type`, `target_ref` (id ou valeur), `resolved_id`, `resolved_name`, `environment`, `db_technology`, `target_metadata` (optionnel), `created_at`.

---

### Story 14.3 : Scheduling multi-cibles — persistance relationnelle des targets planifiés + traçabilité

As a system,
I want planifier une exécution sur plusieurs targets avec traçabilité,
So that le scheduler externe et l’audit puissent opérer sans ambiguïté.

**Acceptance Criteria**

- **Given** un scheduled execution est créé avec `targets[]`,
  **When** il est enregistré,
  **Then** les targets sont persistés relationnellement (table dédiée) et validés selon la politique (existe / externe).
- **Given** le scheduler externe déclenche une exécution,
  **When** il marque le scheduled execution comme “executed”,
  **Then** un lien est stocké vers l’exécution effective (`execution_id`) et un `correlation_id` est présent.
- **And** un historique minimal des runs planifiés est disponible (audit ou table history) avec succès/échec/cancel.

**Notes**

- Conserver le modèle `SCHEDULED_EXECUTIONS`/`RECURRING_PATTERNS`.
- Ajouter `SCHEDULED_EXECUTION_TARGETS` (+ éventuellement `SCHEDULED_EXECUTION_HISTORY` si audit seul ne suffit pas).

---

### Story 14.4 : Politique d’exécution — retries/backoff et états robustes

As a system,
I want gérer retries/backoff de manière explicite au niveau exécution,
So that les erreurs transitoires ne nécessitent pas une relance manuelle et que les SLA soient améliorés.

**Acceptance Criteria**

- **Given** une exécution échoue avec une erreur classifiée “transitoire”,
  **When** la politique de retry de l’action l’autorise,
  **Then** l’exécution passe dans un état retryable et un `next_retry_at` est calculé (FIXED/LINEAR/EXPONENTIAL).
- **Given** `next_retry_at` est atteint,
  **When** le scheduler externe (ou un worker) récupère les exécutions retryables,
  **Then** il peut relancer de manière idempotente sans créer de doublon.
- **And** chaque retry est audité (attempt n, cause, next_retry_at).

**Notes d’implémentation (data)**

- Étendre `EXECUTIONS` : `attempt_number`, `next_retry_at`, `last_error`, `retry_policy_snapshot` (optionnel).
- Introduire une “classification” d’erreur (application layer) + mapping sur policy.

---

### Story 14.5 : Dépendances & mutex — guardrails de concurrence et séquencement

As a DBOPS,
I want définir des dépendances et des règles de non-concurrence entre actions (global ou même target),
So that les opérations critiques ne se télescopent pas et que la séquence soit respectée.

**Acceptance Criteria**

- **Given** une action A dépend de B (MUST_COMPLETE_BEFORE),
  **When** une exécution de A est soumise pour un target donné,
  **Then** le système bloque ou met en attente tant qu’une exécution compatible de B n’est pas en succès (selon règle).
- **Given** une règle mutex (MUST_NOT_RUN_WITH),
  **When** une exécution est soumise,
  **Then** le système refuse ou met en file d’attente si une exécution incompatible est RUNNING (scope global ou same_target).
- **And** les décisions (blocked/waiting/refused) sont auditables avec raison explicite.

**Notes**

- Tables inspirées `operation_dependency` :
  - `ACTION_DEPENDENCIES` (action_id, depends_on_action_id, dependency_type, same_target)
  - `ACTION_MUTEX_RULES` (action_id, mutex_with_action_id, same_target)

---

### Story 14.6 : Fenêtres de maintenance — validation optionnelle, compatible scheduler externe

As a DBOPS,
I want vérifier qu’une exécution “maintenance required” respecte la plage de maintenance **gérée par l’inventaire**,
So that les opérations prod respectent les contraintes d’exploitation sans dupliquer la source de vérité dans le portail.

**Acceptance Criteria**

- **Given** l’inventaire expose les fenêtres de maintenance par target (ou par regroupement) via API ou accès BD (`inventory_db`),
  **When** une exécution est soumise sur un target en PROD nécessitant une fenêtre,
  **Then** le portail interroge l’inventaire pour récupérer la/les fenêtre(s) applicables et valide que `scheduled_at` est dans une fenêtre autorisée (sinon refuse avec raison).
- **Given** une exécution est déclenchée (immédiate ou planifiée) et la fenêtre a pu changer depuis la soumission,
  **When** l’exécution démarre réellement,
  **Then** le portail revalide la conformité à la fenêtre via l’inventaire (défense en profondeur).
- **And** le portail **ne stocke pas** les fenêtres de maintenance : il peut seulement auditer la décision avec un snapshot minimal (ex: window_id, start/end, source, timestamp).

**Notes**

- Pas de table `MAINTENANCE_WINDOWS` dans le portail (source of truth = inventaire).
- Ne pas internaliser le scheduler ; seulement valider.

---

### Story 14.7 : Audit “moteur” + corrélation — traçabilité bout-en-bout

As a Security/Auditor,
I want une trace complète et corrélée (correlation_id) des décisions moteur (RBAC, validation, mutex, retries),
So that je peux prouver qui a fait quoi, sur quelles cibles, et pourquoi le système a autorisé/refusé.

**Acceptance Criteria**

- **Given** une exécution est soumise,
  **When** les validations/autorisation sont évaluées,
  **Then** l’audit capture : action, targets, environnement dérivé, décision (granted/denied), raison.
- **Given** un changement d’état (pending→running→completed/failed/retried/cancelled),
  **When** il a lieu,
  **Then** un événement d’audit est écrit avec `correlation_id`.
- **And** l’audit est **append-only** (aucun update/delete) ; une défense en profondeur (trigger) est documentée si activée.

---

### Story 14.8 : Scalabilité Oracle — partitionnement, rétention, indexation, et agrégats

As a Tech Lead / DBOPS,
I want que les tables à croissance non bornée soient scalables (partition + purge) et que les écrans restent performants,
So that le portail supporte la montée en charge (exécutions, steps, audit) sans dégradation.

**Acceptance Criteria**

- **Given** une volumétrie croissante,
  **When** on interroge les pages “mes exécutions”, “toutes les exécutions”, “audit”,
  **Then** les requêtes principales utilisent des index sélectifs et restent sous les objectifs NFR.
- **Given** une politique de rétention (ex: 24 mois exécutions, 3 mois logs/steps détaillés),
  **When** la purge est exécutée,
  **Then** elle s’appuie sur “drop partitions” quand possible, et le système reste disponible.

**Notes d’implémentation**

- Partitionnement recommandé :
  - `EXECUTIONS` par `CREATED_AT` (mensuel),
  - `EXECUTION_STEPS` partitionné par référence à `EXECUTIONS` (si Oracle le permet selon FK),
  - `AUDIT_LOG` par `TIMESTAMP` (mensuel).
- Ajouter une procédure de purge + doc opérationnelle.
- Ajouter au besoin des agrégats (MViews ou tables rollup) pour dashboards (à activer seulement si nécessaire).

---

## Definition of Done (Epic)

- Schéma et migrations livrés (Flyway) + tests de migration.
- API backend : création exécution avec targets[] + validations + retries + mutex/dépendances (au moins MVP).
- Scheduler externe : endpoints/views nécessaires pour “due items” + idempotence.
- Audit complet + corrélation (correlation_id).
- Stratégie scalabilité documentée + scripts/procédures de purge.
- Observabilité : métriques clés (taux d’échec, retries, blocked by mutex, latence).

## Risques & mitigations

- **Complexité moteur** (mutex/dépendances): livrer par itérations (read-only “detect + warn” puis “enforce”).
- **Partitionnement**: nécessite validation DBA (choix de clés, contraintes FK, impacts requêtes).
- **Sources inventaire multiples**: standardiser un contrat “target” et centraliser la résolution.

## Plan de livraison (phases recommandées)

1. **Phase 1**: `TARGET_TYPE_REGISTRY` + `EXECUTION_TARGETS` + `SCHEDULED_EXECUTION_TARGETS` + APIs de résolution/validation.
2. **Phase 2**: retries/backoff + audit moteur + idempotence scheduler.
3. **Phase 3**: dépendances/mutex + validation maintenance windows via inventaire (enforce), puis scalabilité (partition/purge) selon volumétrie.

