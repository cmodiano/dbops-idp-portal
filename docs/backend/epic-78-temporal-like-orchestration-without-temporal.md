# Epic 78 : Orchestration Temporal-like sans Temporal — Fiabilité niveau entreprise

**Date :** 2026-03-13  
**Statut :** Draft  
**Référence :** [docs/architecture/temporal-advantages-without-temporal-implementation-plan.md](../architecture/temporal-advantages-without-temporal-implementation-plan.md)  
**Périmètre :** `executions/`, `profiles/`, `catalog/`, schéma Oracle Flyway

---

## 1. Contexte et problème

### 1.1 Bâtiments existants

La plateforme dispose déjà de fondations solides :

- Tables runtime partitionnées (`EXECUTIONS`, `EXECUTION_STEPS`, `AUDIT_LOG`)
- Journal d'événements workflow durable (`WORKFLOW_EVENTS`)
- Table de file d'attente exécutable (`RUNNABLE_STEPS`)
- Package de maintenance et rétention (`PKG_IDP_MAINTENANCE`)

### 1.2 Points de douleur actuels

| Problème | Impact | Détail |
|----------|--------|--------|
| **Risque de course sur séquence** | Critique | `WorkflowEventService` utilise `MAX(sequence_num)+1` — collision possible sous émetteurs concurrents, événements perdus si insert échoue |
| **File non pilote unique** | Élevé | `RUNNABLE_STEPS` existe mais l'orchestration repose encore sur les threads in-process de `ContainerWorkflowRuntime.run()` |
| **Runtime fragmenté** | Élevé | Runtime legacy séquentiel et container runtime coexistent ; branchement, gates, retries, recovery dispersés |
| **Gouvernance JSON/CLOB incohérente** | Moyen | Certaines colonnes CLOB ont contrainte DB JSON, d'autres validées uniquement en app |
| **Décalage schéma-modèle** | Moyen | Ex. `EXECUTION_STEPS.CONFIG_STEP_ID` : `VARCHAR2(255)` en DB vs `TextField` en modèle Django |

### 1.3 Propriétés cibles (niveau Temporal)

- Commandes durables
- Historique d'événements durable et rejouable
- File de travail durable avec leases et reclaim
- Transitions d'état déterministes
- Effets de bord idempotents
- Reprise après crash/restart sans reconstruction en mémoire

---

## 2. Principes de conception

1. **Source de vérité unique : base de données**
2. **Workers stateless ; pas de threads d'orchestration in-process**
3. **Historique de contrôle append-only pour reproductibilité**
4. **Modèle event-first, projection-second**
5. **Déploiement expand-migrate-contract (pas de big-bang)**
6. **APIs strictement rétrocompatibles pendant la transition**
7. **Contraintes schéma pour les invariants, pas seulement la logique applicative**

---

## 3. Architecture cible

### 3.1 Composants logiques

| Composant | Rôle |
|-----------|------|
| **Execution Projection** | `EXECUTIONS`, `EXECUTION_STEPS`, `EXECUTION_TARGETS` — modèle de lecture rapide UI/API |
| **Event Store** | `WORKFLOW_EVENTS` — flux append-only par exécution, séquence monotone stricte |
| **Command Store** (nouveau) | `WORKFLOW_COMMANDS` — commandes durables (approve, reject, cancel, timeout, resume) |
| **Work Queue** | `RUNNABLE_STEPS` — file unique d'unités exécutables, claim avec lease + reclaim |
| **Outbox** | `EXECUTION_OUTBOX` — effets externes fiables (notifications, websocket, callbacks) |
| **Workers** | orchestration, polling, gate evaluator, command processor, outbox dispatcher |

### 3.2 Flux de données

1. API écrit une commande (durable) et retourne rapidement
2. Command processor valide la transition et ajoute l'événement
3. Orchestrateur enqueue les runnable steps
4. Worker claim un step (`SKIP LOCKED` + lease), exécute, persiste outcome + snapshot
5. Prochains steps enqueued
6. Outbox dispatcher émet les effets de bord après commit
7. UI se synchronise depuis les séquences `WORKFLOW_EVENTS`

---

## 4. Phases et Stories

### Phase A — Fiabilisation (sans changement de comportement)

---

#### Story 78.1 — Table WORKFLOW_EVENT_COUNTER et allocation séquence atomique

**Priorité :** Critique  
**Effort estimé :** M

**Description :**  
Remplacer la logique `MAX(sequence_num)+1` de `WorkflowEventService` par une allocation atomique via table dédiée. Éliminer le risque de collision de séquence sous émetteurs concurrents.

**Acceptance criteria :**
- AC1 : Table `WORKFLOW_EVENT_COUNTER` créée : `(execution_id PK, last_sequence_num)` avec allocation via row-level lock/update
- AC2 : `WorkflowEventService` utilise la nouvelle allocation atomique — plus de `MAX()+1`
- AC3 : Classification des emits : événements de contrôle critiques → fail/retry si append échoue ; télémétrie non-critique → best-effort autorisé
- AC4 : Tests de concurrence : N émetteurs concurrents pour une même exécution → séquence stricte sans doublons ni trous

**Fichiers impactés :** `executions/services/workflow_events.py`, migration Flyway `V122__create_workflow_event_counter.sql`

---

#### Story 78.2 — Renforcement RUNNABLE_STEPS avec leases

**Priorité :** Haute  
**Effort estimé :** M

**Description :**  
Ajouter sémantique de claim avec lease sur `RUNNABLE_STEPS` : `claimed_until`, `attempt_no`, `last_error`, `max_attempts`. Claim uniquement où `eligible_at <= now`. Reclaim des leases expirés.

**Acceptance criteria :**
- AC1 : Colonnes `claimed_until`, `attempt_no`, `last_error`, `max_attempts` ajoutées à `RUNNABLE_STEPS`
- AC2 : Claim uniquement si `eligible_at <= now` et (pas de claim actif OU `claimed_until < now`)
- AC3 : Reclaim des leases expirés intégré au réconciliateur ou task dédiée
- AC4 : Tests : simulation crash worker → reclaim → pas de double exécution

**Fichiers impactés :** `executions/services/runnable_steps.py`, `executions/tasks/reconcile.py`, migration `V123__harden_runnable_steps_with_leases.sql`

---

#### Story 78.3 — Alignement modèle/schéma ExecutionStep.config_step_id

**Priorité :** Moyenne  
**Effort estimé :** S

**Description :**  
`EXECUTION_STEPS.CONFIG_STEP_ID` est `VARCHAR2(255)` en DB mais `TextField` en modèle Django. Aligner le modèle sur `CharField(max_length=255)` pour éviter défauts de persistance.

**Acceptance criteria :**
- AC1 : Modèle `ExecutionStep.config_step_id` défini comme `CharField(max_length=255)`
- AC2 : Migration Django si nécessaire ; pas de régression sur données existantes
- AC3 : Tests de persistance avec valeurs à la limite (255 caractères)

**Fichiers impactés :** `executions/models.py`, migrations Django

---

### Phase B — Orchestration pilotée par la file (remplacer progression thread-led)

---

#### Story 78.4 — Table WORKFLOW_COMMANDS et persistance des commandes

**Priorité :** Haute  
**Effort estimé :** M

**Description :**  
Créer la table `WORKFLOW_COMMANDS` pour stocker les commandes durables (approve, reject, cancel, timeout signal, resume signal). Les commandes sont persistées et retriables.

**Acceptance criteria :**
- AC1 : Table `WORKFLOW_COMMANDS` créée avec colonnes : execution_id, command_type, payload, status, created_at, processed_at
- AC2 : API d'écriture de commande : l'API écrit la commande et retourne rapidement (pas d'attente de traitement)
- AC3 : Command processor worker (ou intégré reconcile) traite les commandes en attente

**Fichiers impactés :** Migration `V124__add_workflow_commands.sql`, nouveau module `executions/commands.py` ou équivalent

---

#### Story 78.5 — Dispatch par file au lieu de thread dans ContainerWorkflowRuntime

**Priorité :** Haute  
**Effort estimé :** L

**Description :**  
Remplacer le lancement de thread dans `ContainerWorkflowRuntime.run()` par un dispatch vers la file. Le chemin de production doit enqueue les root runnable steps ; une boucle worker pilote la progression.

**Acceptance criteria :**
- AC1 : `ContainerWorkflowRuntime.run()` n'instancie plus de thread pour la progression — enqueue uniquement
- AC2 : Orchestration worker : claim runnable step → exécute handler → persiste transition/event → enqueue next steps
- AC3 : Comportement fonctionnel identique pour les cas existants (tests de régression)
- AC4 : Reprise après crash : état reconstruit depuis la DB uniquement

**Fichiers impactés :** `executions/container_workflow_runtime.py`, `executions/tasks/` (nouveau worker ou extension reconcile)

---

#### Story 78.6 — Simplification du réconciliateur

**Priorité :** Moyenne  
**Effort estimé :** M

**Description :**  
Réduire les responsabilités du réconciliateur : reclaim des claims expirés, re-drive des commandes en attente, fail des exécutions stale selon politique. Déplacer la logique de reprise vers le worker d'orchestration.

**Acceptance criteria :**
- AC1 : Reconcile se limite à : reclaim, détection stale, politiques de repair limitées
- AC2 : Re-drive des commandes pending intégré
- AC3 : Pas de duplication de logique avec le worker d'orchestration
- AC4 : Documentation des responsabilités dans le module reconcile

**Fichiers impactés :** `executions/tasks/reconcile.py`

---

### Phase C — Unification des runtimes et suppression de la duplication

---

#### Story 78.7 — Table EXECUTION_OUTBOX pour effets externes fiables

**Priorité :** Moyenne  
**Effort estimé :** M

**Description :**  
Créer la table `EXECUTION_OUTBOX` pour les effets externes (notifications, websocket broadcast, callbacks intégrations). Le dispatcher outbox émet après commit.

**Acceptance criteria :**
- AC1 : Table `EXECUTION_OUTBOX` créée (execution_id, event_type, payload, status, created_at, dispatched_at)
- AC2 : Les side-effects (approve/reject notifications, etc.) écrivent dans l'outbox au lieu d'émettre directement
- AC3 : Outbox dispatcher worker traite les événements non dispatchés
- AC4 : Idempotence : pas de double envoi en cas de retry

**Fichiers impactés :** Migration `V125__add_execution_outbox.sql`, `executions/` (outbox module)

---

#### Story 78.8 — Désactivation du runtime legacy en production

**Priorité :** Haute  
**Effort estimé :** M

**Description :**  
Désactiver l'utilisation en production du chemin legacy `WorkflowRuntime`. Conserver un seul moteur d'orchestration pour les workflows.

**Acceptance criteria :**
- AC1 : Feature flag ou configuration : chemin legacy désactivé en production
- AC2 : Tous les chemins d'exécution passent par le container runtime + file
- AC3 : Code legacy conservé mais non invoqué (ou supprimé si safe)
- AC4 : Tests de non-régression sur tous les types de workflows

**Fichiers impactés :** `executions/workflow_runtime.py`, points d'entrée (trigger, scheduled, etc.)

---

#### Story 78.9 — Consolidation state_machine et persistence APIs

**Priorité :** Moyenne  
**Effort estimé :** L

**Description :**  
Consolider la logique de transition dans un module dédié `state_machine.py`. Consolider les APIs de persistance : `event_store`, `work_queue`, `execution_repo`.

**Acceptance criteria :**
- AC1 : Module `executions/domain/state_machine.py` — carte de transitions centralisée
- AC2 : Module `executions/infra/event_store.py` — API transactionnelle event-store
- AC3 : Module `executions/infra/work_queue.py` — abstraction queue avec lease
- AC4 : Réduction de la duplication dans `container_workflow_runtime.py`, `reconcile.py`, `gates.py`

**Fichiers impactés :** `executions/` (nouvelle structure domain/, infra/, app/)

---

### Phase D — Normalisation CLOB (priorité haute)

---

#### Story 78.10 — Tables WORKFLOW_DEFINITIONS normalisées

**Priorité :** Haute  
**Effort estimé :** XL

**Description :**  
Extraire `ACTIONS_CATALOG.EXECUTION_STEPS` (JSON) vers tables normalisées : `WORKFLOW_DEFINITIONS`, `WORKFLOW_STEPS`, `WORKFLOW_STEP_EDGES`. Dual-write puis cutover.

**Acceptance criteria :**
- AC1 : Tables créées : `WORKFLOW_DEFINITIONS`, `WORKFLOW_STEPS`, `WORKFLOW_STEP_EDGES`
- AC2 : Migration backfill depuis `ACTIONS_CATALOG.EXECUTION_STEPS`
- AC3 : Dual-read : feature flag pour basculer lecture ancien JSON vs tables normalisées
- AC4 : Parity checks : même résultat pour les deux chemins
- AC5 : Contraintes NOT NULL et UNIQUE après validation

**Fichiers impactés :** Migrations V126–V129, `catalog/models.py`, `executions/` (lecture workflow)

---

#### Story 78.11 — Tables PROFILE_ACTION permission normalisées

**Priorité :** Moyenne  
**Effort estimé :** L

**Description :**  
Extraire `PROFILE_ACTION_PERMISSIONS.ACTION_IDS_JSON`, `TAG_PATTERNS_JSON`, `ENVIRONMENTS_JSON` vers `PROFILE_ACTION_ALLOWLIST`, `PROFILE_ACTION_TAG_PATTERNS`, `PROFILE_ACTION_ENVS`.

**Acceptance criteria :**
- AC1 : Tables créées avec backfill
- AC2 : Dual-read avec feature flag
- AC3 : Parity checks
- AC4 : Décisions RBAC deviennent relationnelles, auditable, indexables

**Fichiers impactés :** Migrations V130–V133, `profiles/`, `catalog/rbac_service.py`

---

#### Story 78.12 — Tables PROFILE_TARGET permission normalisées

**Priorité :** Moyenne  
**Effort estimé :** L

**Description :**  
Extraire `PROFILE_TARGET_PERMISSIONS.*_JSON` vers `PROFILE_TARGET_ALLOWLIST`, `PROFILE_TARGET_PATTERNS`, `PROFILE_TARGET_ATTRIBUTE_FILTERS`, `PROFILE_TARGET_EXCLUSIONS`.

**Acceptance criteria :**
- AC1 : Tables créées avec backfill
- AC2 : Dual-read avec feature flag
- AC3 : Parity checks
- AC4 : Évaluation des permissions plus claire et plus rapide

**Fichiers impactés :** Migrations V131–V133, `profiles/`

---

#### Story 78.13 — Contraintes IS JSON sur colonnes Tier 2

**Priorité :** Basse  
**Effort estimé :** M

**Description :**  
Ajouter contraintes `IS JSON` et index helper sur colonnes Tier 2 : `EXECUTIONS.PARAMETERS`, `EXECUTION_STEPS.OUTPUT`, `INTEGRATIONS.CONFIG`, `SCHEDULED_EXECUTIONS.PARAMETERS`, `RECURRING_PATTERNS.PATTERN_CONFIG`, etc.

**Acceptance criteria :**
- AC1 : Migration `V126__add_json_checks_runtime_tier2.sql` (ou intégrée au stream)
- AC2 : Colonnes listées dans le plan avec `IS JSON` check
- AC3 : Pas de régression sur données existantes (validation préalable)

**Fichiers impactés :** Migration Flyway

---

### Phase E — Nettoyage et contrat final

---

#### Story 78.14 — Dépréciation colonnes runtime legacy

**Priorité :** Moyenne  
**Effort estimé :** M

**Description :**  
Marquer comme dépréciées les colonnes runtime legacy. Préparer la suppression.

**Acceptance criteria :**
- AC1 : Migration `V134__deprecate_legacy_runtime_columns.sql`
- AC2 : Documentation des colonnes dépréciées et date de suppression prévue
- AC3 : Aucun codepath ne lit/écrit ces colonnes en production

**Fichiers impactés :** Migration, documentation

---

#### Story 78.15 — Suppression CLOB permissions legacy

**Priorité :** Moyenne  
**Effort estimé :** M

**Description :**  
Après cutover validé, supprimer ou archiver les colonnes CLOB legacy des permissions (`ACTION_IDS_JSON`, `TAG_PATTERNS_JSON`, etc.).

**Acceptance criteria :**
- AC1 : Migration `V135__drop_or_archive_legacy_permission_clobs.sql`
- AC2 : Rollback script documenté
- AC3 : Soak period respecté avant exécution

**Fichiers impactés :** Migration Flyway

---

#### Story 78.16 — Observabilité : métriques, runbooks, alertes

**Priorité :** Moyenne  
**Effort estimé :** M

**Description :**  
Mettre en place les métriques, runbooks et alertes définis dans le plan d'architecture.

**Acceptance criteria :**
- AC1 : Métriques : runnable queue depth, command backlog, event append failures, reconciliation count, per-step latency
- AC2 : Runbooks : lease expiry storms, command backlog growth, outbox stuck, sequence allocation failures
- AC3 : Alertes : queue lag, event append error rate, stale reconciliation spike
- AC4 : Documentation opérationnelle à jour

**Fichiers impactés :** `executions/` (instrumentation), `docs/operations/`

---

## 5. Plan de migrations Flyway (aligné projet)

**Note :** Les versions V120–V121 sont déjà utilisées. Les migrations de cet epic démarrent à V122.

| Version | Description |
|---------|-------------|
| V122 | create_workflow_event_counter |
| V123 | harden_runnable_steps_with_leases |
| V124 | add_workflow_commands |
| V125 | add_execution_outbox |
| V126 | add_json_checks_runtime_tier1 |
| V127 | create_workflow_definition_tables |
| V128 | backfill_workflow_definitions_from_actions |
| V129 | add_dual_read_support_workflow_defs |
| V130 | enforce_workflow_definition_not_nulls_uniques |
| V131 | create_profile_action_permission_tables |
| V132 | create_profile_target_permission_tables |
| V133 | backfill_profile_permissions |
| V134 | add_permission_indexes_and_constraints |
| V135 | deprecate_legacy_runtime_columns |
| V136 | drop_or_archive_legacy_permission_clobs |
| V137 | optional_drop_unused_legacy_tables |

---

## 6. Structure cible du package executions/

```
executions/
  domain/
    state_machine.py
    workflow_graph.py
    commands.py
  infra/
    event_store.py
    work_queue.py
    repositories.py
    outbox.py
  app/
    orchestrator.py
    command_processor.py
    handlers/
      platform.py
      service_call.py
      http_request.py
      evaluation.py
      gate.py
      schedule_execution.py
```

---

## 7. Plan de tests

### 7.1 Tests automatisés obligatoires

1. **Concurrence et séquencement** : N émetteurs concurrents → séquence stricte sans doublons/trous
2. **Comportement lease queue** : claim/reclaim sous simulation crash worker → pas de double exécution
3. **Crash recovery** : kill worker mid-step → reprise depuis état DB uniquement
4. **Dual-read parity** : ancien JSON vs tables normalisées → même résultat
5. **Migration data parity** : row counts, checksums, échantillon sémantique

### 7.2 Tests non-fonctionnels

- Débit sous exécutions concurrentes
- Latence p95/p99 API sous workflows event-heavy
- SLOs queue depth et processing lag

---

## 8. Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Divergence dual-write | Élevé | Jobs de parity, validation checksum, alerting |
| Surcharge migration runtime | Moyen | Déploiement phasé, fenêtres migration online, validation DBA |
| Mauvaise config lease queue | Élevé | Defaults conservateurs, soak tests, runbook |
| Complexité rollback feature-flag | Moyen | Stratégie toggle stricte, drills de rollback documentés |
| Dépendances cachées colonnes CLOB legacy | Moyen | Scan de dépendances, vues de compatibilité temporaires |

---

## 9. Dépendances et ordre de réalisation

| Phase | Stories | Dépendances |
|-------|---------|-------------|
| A | 78.1, 78.2, 78.3 | Aucune — peut démarrer immédiatement |
| B | 78.4, 78.5, 78.6 | 78.1, 78.2 recommandés |
| C | 78.7, 78.8, 78.9 | 78.5 (dispatch file) |
| D | 78.10, 78.11, 78.12, 78.13 | 78.8 (runtime unifié) |
| E | 78.14, 78.15, 78.16 | Cutover phases D validé |

---

## 10. Definition of Done (epic)

1. Aucune orchestration en production ne dépend de threads in-process
2. Séquence `WORKFLOW_EVENTS` déterministe et sans collision
3. Lease/reclaim `RUNNABLE_STEPS` validé sous tests de crash
4. Workflow definitions et profile permissions lus depuis schéma normalisé
5. Chemin runtime legacy désactivé/supprimé
6. Runbooks et alertes documentés et actifs
7. Comportement API rétrocompatible pour frontend/consommateurs

---

## 11. Références

- [Plan complet Temporal-like](docs/architecture/temporal-advantages-without-temporal-implementation-plan.md)
- [Epic 76 — Reconcile Crash Recovery](epic-76-reconcile-crash-recovery.md)
- [Epic 77 — Workflow Engine Durability](../_bmad-output/planning-artifacts/epic-77-workflow-engine-durability.md) (si existant)
- [État des lieux migrations](migration/etat-des-lieux-migrations-bd.md)
- [Analyse schéma orphelin](migration/schema-codepath-orphan-analysis.md)
