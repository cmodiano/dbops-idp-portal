# Temporal-like orchestration without Temporal

## Full implementation plan (Oracle + Django + Celery)

Date: 2026-03-13  
Status: Proposed implementation plan  
Audience: Backend engineers, DBAs, DevOps/SRE, QA  
Primary goal: achieve Temporal-level reliability properties without introducing Temporal infrastructure

---

## 1. Executive summary

The current platform already has strong building blocks:

- partitioned runtime tables (`EXECUTIONS`, `EXECUTION_STEPS`, `AUDIT_LOG`)
- durable workflow event log (`WORKFLOW_EVENTS`)
- durable runnable queue table (`RUNNABLE_STEPS`)
- retention and partition maintenance package (`PKG_IDP_MAINTENANCE`)

However, orchestration complexity remains high because runtime control is split across:

- in-process threads in `ContainerWorkflowRuntime.run()`
- multiple task paths (`polling`, `gates`, `reconcile`, `scheduled`)
- mixed "best effort" vs "must persist" semantics for control events
- legacy and modern runtime paths coexisting

This plan makes the design clean, robust, and maintainable by:

1. making DB-backed orchestration primitives the single source of truth
2. replacing thread-led runtime progression with queue-led workers
3. formalizing command, event, and side-effect durability
4. normalizing selected CLOB JSON domains that create long-term complexity
5. removing legacy code paths after staged cutover

---

## 2. Why this change is needed

## 2.1 Main pain points

1. **Sequence race risk in workflow events**
   - `WorkflowEventService` computes `MAX(sequence_num)+1`, which is race-prone under concurrent emitters.
   - Result: duplicate sequence collisions and potential dropped events if insert failures are swallowed.

2. **Queue table exists but is not the single runtime driver**
   - `RUNNABLE_STEPS` is implemented but orchestration still relies on in-process runtime thread progression.
   - This increases crash-recovery burden and code complexity.

3. **Runtime split across multiple paradigms**
   - legacy sequential runtime and container runtime both exist
   - branching, gating, retries, and recovery logic are spread across many files

4. **JSON/CLOB governance is inconsistent**
   - some CLOB columns are DB JSON constrained
   - many runtime-critical CLOB JSON columns are only validated in application code

5. **Schema-model mismatches**
   - example: `EXECUTION_STEPS.CONFIG_STEP_ID` is `VARCHAR2(255)` in DB but `TextField` in model
   - this reduces predictability and can fail at persistence time

## 2.2 Desired properties (Temporal-like capabilities)

- durable command handling
- durable event history and replay
- durable work queue with leases and reclaim
- deterministic state transitions
- idempotent side effects
- resumability after crash/restart without in-memory reconstruction

---

## 3. Design principles

1. **Single source of truth for orchestration state: database**
2. **Stateless workers; no in-process orchestration threads**
3. **Append-only control history for reproducibility**
4. **Event-first, projection-second model**
5. **Expand-migrate-contract rollout (no big-bang)**
6. **Strict backward-compatible APIs during transition**
7. **Schema constraints for invariants, not only app logic**

---

## 4. Target architecture (without Temporal)

## 4.1 Logical components

1. **Execution Projection**
   - `EXECUTIONS`, `EXECUTION_STEPS`, `EXECUTION_TARGETS`
   - fast read model for UI/API

2. **Event Store**
   - `WORKFLOW_EVENTS` append-only stream per execution with strict sequence monotonicity

3. **Command Store** (new)
   - `WORKFLOW_COMMANDS` for durable commands (approve, reject, cancel, timeout signal, resume signal)

4. **Work Queue**
   - `RUNNABLE_STEPS` as the sole queue of executable units
   - claim with lease + reclaim expired claims

5. **Outbox**
   - `EXECUTION_OUTBOX` for reliable external effects (notifications, websocket broadcast fanout, integration callbacks if needed)

6. **Workers**
   - orchestration worker (claim step, execute handler, transition state, enqueue next)
   - polling worker
   - gate evaluator worker
   - command processor worker
   - outbox dispatcher worker

## 4.2 Data-flow summary

1. API writes command (durable) and returns quickly.
2. Command processor validates transition and appends event.
3. Orchestrator enqueues runnable steps.
4. Worker claims runnable step (`SKIP LOCKED` + lease), executes, persists outcome event + snapshot update.
5. Next runnable steps are enqueued.
6. Outbox dispatcher emits side effects after commit.
7. UI catches up from `WORKFLOW_EVENTS` sequences.

---

## 5. Full implementation roadmap

## 5.1 Phase A - Reliability hardening (no behavior change)

### Objectives

- remove race windows
- define critical durability boundaries
- keep existing behavior and API contracts

### Changes

1. Add `WORKFLOW_EVENT_COUNTER` table:
   - `(execution_id PK, last_sequence_num)`
   - allocate sequence atomically via row-level lock/update

2. Update `WorkflowEventService`:
   - replace `MAX()+1` logic
   - classify emits:
     - critical control events: fail/retry path if append fails
     - non-critical telemetry: best effort allowed

3. Strengthen `RUNNABLE_STEPS` claim semantics:
   - claim only where `eligible_at <= now`
   - add `claimed_until`, `attempt_no`, `last_error`, `max_attempts`
   - reclaim expired leases

4. Fix model/schema mismatches:
   - align `ExecutionStep.config_step_id` model to `CharField(max_length=255)`

### Why

- deterministic event ordering is mandatory for replay/catch-up correctness
- lease-based queue semantics are required for robust crash recovery
- model/schema alignment avoids latent data integrity defects

---

## 5.2 Phase B - Queue-led orchestration (replace thread-led progression)

### Objectives

- remove dependence on app-process threads
- reduce reconcile complexity

### Changes

1. Replace `ContainerWorkflowRuntime.run()` thread launch with queue dispatch:
   - production path must enqueue root runnable steps
   - worker loop drives progression

2. Create `WORKFLOW_COMMANDS` table:
   - commands are persisted and retriable

3. Introduce orchestration worker:
   - claim runnable step
   - execute step handler
   - persist transition/event
   - enqueue next steps

4. Simplify `reconcile`:
   - reclaim expired claims
   - re-drive pending commands
   - fail stale executions by policy

### Why

- thread-based orchestration is fragile on process restarts
- DB queue + workers gives deterministic recovery and easier operations

---

## 5.3 Phase C - Unify runtimes and remove duplication

### Objectives

- one runtime model
- one transition map
- one persistence strategy

### Changes

1. Keep one orchestration engine for workflows.
2. Decommission production use of legacy `WorkflowRuntime` path.
3. Consolidate transition logic into dedicated module (`state_machine`).
4. Consolidate persistence APIs (`event_store`, `work_queue`, `execution_repo`).

### Why

- duplicate runtime paths multiply bug surface and test burden
- central transition/persistence logic improves maintainability and onboarding

---

## 5.4 Phase D - CLOB normalization (high value first)

### Objectives

- normalize CLOB domains that hurt maintainability/queryability the most
- keep flexible payloads where variability is truly high

### Priority rule

Normalize when data is:

- structurally stable
- frequently queried/filterable
- security/compliance critical
- reused across services

Keep as JSON CLOB when data is:

- highly variable
- mostly write/read by ID
- not used for complex cross-row relational queries

---

## 6. CLOB normalization strategy and matrix

## 6.1 Tier 1 normalize now (highest ROI)

| Current column(s) | New normalized model | Reason |
|---|---|---|
| `ACTIONS_CATALOG.EXECUTION_STEPS` | `WORKFLOW_DEFINITIONS`, `WORKFLOW_STEPS`, `WORKFLOW_STEP_EDGES` | Core orchestration logic should not depend on opaque JSON blobs. Improves validation, diffs, migration safety. |
| `PROFILE_ACTION_PERMISSIONS.ACTION_IDS_JSON`, `TAG_PATTERNS_JSON`, `ENVIRONMENTS_JSON` | `PROFILE_ACTION_ALLOWLIST`, `PROFILE_ACTION_TAG_PATTERNS`, `PROFILE_ACTION_ENVS` | RBAC decisions become relational, auditable, indexable, and simpler to test. |
| `PROFILE_TARGET_PERMISSIONS.*_JSON` fields | `PROFILE_TARGET_ALLOWLIST`, `PROFILE_TARGET_PATTERNS`, `PROFILE_TARGET_ATTRIBUTE_FILTERS`, `PROFILE_TARGET_EXCLUSIONS` | Eliminates repetitive parse logic and makes permission evaluation clearer/faster. |

## 6.2 Tier 2 keep as JSON CLOB but enforce DB JSON constraints + helper indexes

| Column | Action |
|---|---|
| `EXECUTIONS.PARAMETERS` | add `IS JSON` check and optional generated columns for frequently queried keys |
| `EXECUTION_STEPS.OUTPUT` | add `IS JSON` check; keep flexible structure due to heterogeneous outputs |
| `INTEGRATIONS.CONFIG` | add `IS JSON` check |
| `SCHEDULED_EXECUTIONS.PARAMETERS` | add `IS JSON` check |
| `RECURRING_PATTERNS.PATTERN_CONFIG` | add `IS JSON` check |
| `INTEGRATION_ACTIONS.REQUIRED_PARAMS/OPTIONAL_PARAMS/RESPONSE_FORMAT` | add `IS JSON` checks |
| `ACTIONS_CATALOG.PARAMETERS_SCHEMA/IMPACT_RULES/REMEDIATION_RULES/BUSINESS_RULE_POLICIES` | add `IS JSON` checks where applicable; retain flexible authoring |

## 6.3 Tier 3 keep as plain text CLOB

| Column | Reason |
|---|---|
| `ACTIONS_CATALOG.DOCUMENTATION_MD` | free-form markdown text |
| `*_ERROR_MESSAGE` columns | arbitrary text, not structured domain data |
| `AUDIT_LOG.DETAILS` (initially) | large historical compatibility footprint; optionally enforce JSON later after cleanup |

---

## 7. Detailed schema migration plan (Flyway)

Note: version numbers are suggested and can be adjusted to your release process.

### Stream 1: orchestration reliability

1. `V121__create_workflow_event_counter.sql`
2. `V122__harden_runnable_steps_with_leases.sql`
3. `V123__add_workflow_commands.sql`
4. `V124__add_execution_outbox.sql`
5. `V125__add_json_checks_runtime_tier1.sql`

### Stream 2: workflow definition normalization

6. `V126__create_workflow_definition_tables.sql`
7. `V127__backfill_workflow_definitions_from_actions.sql`
8. `V128__add_dual_read_support_workflow_defs.sql`
9. `V129__enforce_workflow_definition_not_nulls_uniques.sql`

### Stream 3: profile permission normalization

10. `V130__create_profile_action_permission_tables.sql`
11. `V131__create_profile_target_permission_tables.sql`
12. `V132__backfill_profile_permissions.sql`
13. `V133__add_permission_indexes_and_constraints.sql`

### Stream 4: cleanup/contract

14. `V134__deprecate_legacy_runtime_columns.sql`
15. `V135__drop_or_archive_legacy_permission_clobs.sql`
16. `V136__optional_drop_unused_legacy_tables.sql`

### Rollback strategy

- every migration must include explicit rollback script where feasible
- use feature flags to avoid immediate hard dependency on newly normalized reads
- keep dual-write until parity is proven

---

## 8. Codebase rework plan

## 8.1 New package structure

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

## 8.2 Refactor targets

1. Split `container_workflow_runtime.py` into:
   - orchestration flow
   - step execution
   - routing/join logic
   - persistence boundary

2. Convert `services/workflow_events.py` to transactional event-store API.

3. Convert `services/runnable_steps.py` into lease-aware queue abstraction.

4. Reduce `tasks/reconcile.py` responsibilities:
   - reclaim
   - stale detection
   - limited repair policies

5. Keep API layer unchanged while internals move to command-driven orchestration.

---

## 9. Testing plan

## 9.1 Must-have automated tests

1. **Concurrency and sequencing**
   - many concurrent event emits for same execution
   - verify strict sequence with no duplicates/gaps

2. **Queue lease behavior**
   - claim/reclaim under worker crash simulation
   - no double execution

3. **Crash recovery**
   - kill worker mid-step
   - verify resumability from DB state only

4. **Dual-read parity**
   - old workflow JSON vs normalized workflow definitions
   - old profile permission CLOB vs normalized permission tables

5. **Migration data parity**
   - row counts
   - checksums
   - sampled semantic equivalence

## 9.2 Non-functional tests

- throughput under concurrent executions
- p95/p99 API latency under event-heavy workflows
- queue depth and processing lag SLOs

---

## 10. Observability and operations

## 10.1 Metrics

- runnable queue depth (unclaimed/claimed/expired lease)
- command backlog and age
- event append failures
- reconciliation actions count
- per-step handler latency and failure rate

## 10.2 Runbooks

1. lease expiry storms
2. command backlog growth
3. outbox stuck events
4. sequence allocation failures

## 10.3 Alerts

- queue lag threshold
- event append error rate > threshold
- stale execution reconciliation spike

---

## 11. Rollout and cutover plan

## 11.1 Expand

- deploy new tables/columns
- enable dual-write for normalized domains
- read old path by default

## 11.2 Validate

- parity checks in staging and canary
- runtime correctness and performance comparison

## 11.3 Switch

- feature-flag switch to normalized read path
- monitor parity and SLOs

## 11.4 Contract

- disable old writes
- archive/drop deprecated columns and legacy runtime code after soak

---

## 12. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Dual-write divergence | High | parity jobs, checksum validation, alerting |
| Migration runtime overhead | Medium | phased rollout, online migration windows, DBA validation |
| Queue lease misconfiguration | High | conservative defaults, soak tests, runbook |
| Feature-flag rollback complexity | Medium | strict toggle strategy and documented rollback drills |
| Hidden dependencies on legacy CLOB columns | Medium | dependency scan and temporary compatibility views |

---

## 13. Delivery plan (suggested)

## Sprint 1-2

- Phase A reliability hardening
- event sequencing fix
- lease-ready queue schema
- critical tests

## Sprint 3-4

- queue-driven orchestration path in production
- workflow commands + outbox
- reconcile simplification

## Sprint 5-6

- workflow definition normalization + dual-read
- parity and canary cutover

## Sprint 7-8

- profile permission normalization + dual-read
- parity and cutover

## Sprint 9

- legacy runtime removal
- deprecated schema cleanup prep

## Sprint 10

- contract phase (drop/archive legacy pieces as approved)

---

## 14. Definition of done

1. No production orchestration depends on in-process threads.
2. `WORKFLOW_EVENTS` sequence is deterministic and collision-free.
3. `RUNNABLE_STEPS` lease/reclaim works under crash tests.
4. Workflow definitions and profile permissions read from normalized schema.
5. Legacy runtime path disabled/removed.
6. Documented runbooks and alerts are active.
7. API behavior remains backward compatible for frontend/consumers.

---

## 15. Notes on enterprise Oracle constraints

- This plan is Oracle-native and does not require PostgreSQL.
- It relies on Oracle strengths already used in this repository:
  - partitioning
  - `FOR UPDATE SKIP LOCKED`
  - global/local indexing strategy
  - package-based maintenance automation

The objective is not changing database platform; the objective is making orchestration architecture clean and durable within existing enterprise constraints.

