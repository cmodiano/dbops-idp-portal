# Infrastructure as Code Strategy — IDP Portal

> ⚠️ **OBSOLÈTE** — Ce document a été remplacé par la Story 64-17 (renommage IaC→CaC).
> Le document de référence actuel est : [Configuration as Code – Stratégie](configuration-as-code-strategy.md)
> Ce document est conservé à titre historique uniquement.

**Date:** 2026-03-07
**Status:** Proposal (v2 — Git as Source of Truth) — ⚠️ OBSOLÈTE, remplacé par CaC
**Authors:** Architecture Team

---

## Paradigm: Git is the Source of Truth

The configuration Git repository is the authoritative source for all IDP Portal configuration.
The database is a **runtime cache** of what Git declares. Any environment can be rebuilt
from scratch by applying the repo content to an empty database (after Flyway schema migrations).

The UI remains available for **incident / immediate actions only**. Any change made through the
UI is considered **ephemeral** — it lives only in the database until the next Git sync overwrites
it. If a team wants to persist a UI change, they must manually add it to the config repo and
merge it.

```
 ┌─────────────────────────────────────────────────────────────────────┐
 │                    Git Repository (SOURCE OF TRUTH)                 │
 │  idp-config/                                                       │
 │  ├── actions/           one YAML per action/workflow                │
 │  ├── integrations/      one YAML per integration                   │
 │  ├── profiles/          one YAML per profile (or single file)      │
 │  ├── policies/          one YAML per business rule policy           │
 │  ├── integration-types/ one YAML per integration type catalogue     │
 │  ├── reference/         engines.yaml, categories.yaml               │
 │  ├── feature-flags.yaml                                             │
 │  └── tags.yaml                                                      │
 └────────────────────┬────────────────────────────────────────────────┘
                      │
            merge to main triggers CI/CD
                      │
                      ▼
 ┌─────────────────────────────────────────────────────────────────────┐
 │                    CI/CD Pipeline                                    │
 │  1. Validate YAML schemas (offline, no DB needed)                   │
 │  2. Resolve cross-references (action→integration by name)           │
 │  3. Call POST /admin/<entity>/sync/ for each entity type            │
 │     (ordered: reference → integrations → policies → actions →       │
 │      profiles → feature-flags)                                      │
 │  4. Drift report: compare DB state vs repo                          │
 └────────────────────┬────────────────────────────────────────────────┘
                      │
                      ▼
 ┌──────────────────────────────┐       ┌─────────────────────────────┐
 │     Oracle Database          │       │     UI (React)              │
 │  (runtime cache of config)   │◄──────│  Emergency edits only       │
 │                              │       │  Shows ⚠ "out of sync"     │
 └──────────────────────────────┘       │  badge on diverged entities │
                                        └─────────────────────────────┘
```

---

## What is Managed as Code (and What is Not)

### Managed as code — the full config repo can recreate these
| Entity | YAML location | Lookup key |
|--------|---------------|------------|
| Actions & Workflows | `actions/<name>.yaml` | `name` (unique) |
| Integrations | `integrations/<name>.yaml` | `name` (unique) |
| Integration Type Catalogue | `integration-types/<code>.yaml` | `code` (PK) |
| Business Rule Policies | `policies/<name>.yaml` | `name` (unique) |
| Profiles + Permissions | `profiles/<name>.yaml` | `name` (unique) |
| Reference Engines | `reference/engines.yaml` | `code` (unique) |
| Reference Categories | `reference/categories.yaml` | `code` (unique) |
| Tags | `tags.yaml` | `name` (unique) |
| Feature Flags | `feature-flags.yaml` | `flag_key` (unique) |
| Action Mutexes | Inline in `actions/<name>.yaml` → `spec.mutex` | composite |

### NOT managed as code — runtime / operational state
| Entity | Reason |
|--------|--------|
| Executions, Execution Steps, Execution Targets | Runtime state |
| Scheduled Executions, Recurring Patterns | Runtime scheduling |
| Audit Log | Append-only operational data |
| User Favorites | User preferences |
| Users, API Keys, Sessions | Identity / auth state |
| Integration health_status/health_checked_at | Runtime health probes |

---

## Current State Assessment

| What exists today | Status |
|-------------------|--------|
| **Profiles YAML export/import** (`profiles/services_export_import.py`) | Done — pattern to replicate |
| Profile Import Modal in UI (`ProfileImportModal.tsx`) | Done |
| Profile export endpoint (`GET /admin/profiles/export/yaml/`) | Done |
| Profile import endpoint (`POST /admin/profiles/import/yaml/`) | Done |
| Integration seed command (`seed_integration_types.py`) | Partial — imperative, not declarative |
| Integration migration command (`migrate_integrations.py`) | Partial — status updates only |
| Dev seed script (`scripts/seed_dev_data.py`) | Partial — imperative Python, not YAML |
| Actions export/import | **Missing** |
| Integrations export/import | **Missing** |
| Policies export/import | **Missing** |
| Reference data export/import | **Missing** |
| Feature flags export/import | **Missing** |
| Integration type catalogue export/import | **Missing** |
| Tags export/import | **Missing** |
| Sync endpoint (full declarative reconciliation) | **Missing** |
| Drift detection | **Missing** |
| CI/CD pipeline for config sync | **Missing** |

---

## YAML Schema Definitions

All YAML files use a consistent envelope:

```yaml
apiVersion: idp/v1
kind: <EntityType>
metadata:
  name: <unique-identifier>
  # entity-specific metadata
spec:
  # entity-specific configuration
```

### Action / Workflow

```yaml
apiVersion: idp/v1
kind: Action
metadata:
  name: oracle-patching-quarterly         # UNIQUE — lookup key
  description: "Quarterly Oracle database patching"
  category: Patching                       # must exist in reference/categories.yaml
  engine: Oracle                           # must exist in reference/engines.yaml
  platform: AAP                            # must exist in integration-types/
  item_type: workflow                      # action | workflow
  tags:                                    # auto-created if missing from tags.yaml
    - oracle
    - patching
spec:
  status: published                        # draft | published | disabled
  requires_target: true
  default_impact_level: high               # low | medium | high | critical
  documentation_md: |
    ## Oracle Quarterly Patching
    This workflow applies quarterly Oracle CPU patches.
  parameters_schema:                       # JSON Schema draft-07
    type: object
    properties:
      patch_version:
        type: string
        description: "Oracle patch version to apply"
      downtime_window:
        type: integer
        description: "Expected downtime in minutes"
    required:
      - patch_version
  execution_steps:
    - order: 1
      name: "Retrieve credentials"
      type: vault
      connector_config:
        secret_path: "secret/oracle/patching"
    - order: 2
      name: "Create change request"
      type: servicenow
      connector_config:
        template: "standard_change"
    - order: 3
      name: "Apply patches"
      type: platform
      connector_config:
        job_template: "oracle-patch-apply"
      gate_config:
        gate_type: approval
        required_roles: ["DBOPS", "DBA"]
    - order: 4
      name: "Verify patching"
      type: verification
      connector_config:
        job_template: "oracle-patch-verify"
  impact_rules:
    production:
      impact_level: critical
      requires_change: true
    staging:
      impact_level: high
      requires_change: false
  notification_config:
    email: true
    teams: true
  remediation_rules: null                  # or inline remediation config
  integration_ref: aap-production          # resolved by name → Integration.name
  business_rule_policy_ref: change-approval-policy  # resolved by name → BusinessRulePolicy.name
  mutex:
    - incompatible_with: oracle-upgrade    # resolved by name → Action.name
      same_target: true
      description: "Cannot patch during upgrade"
```

### Integration

```yaml
apiVersion: idp/v1
kind: Integration
metadata:
  name: aap-production                     # UNIQUE — lookup key
  type: aap                                # must exist in integration-types/
spec:
  base_url: https://aap.internal.company.com
  auth_flow: basic_then_token
  token_url: https://aap.internal.company.com/api/v2/tokens/
  credential_ref: secret/integrations/aap-prod   # Vault path — NEVER inline secrets
  icon: /icons/aap.svg
  secret_service_ref: vault-production     # optional — resolved by name → Integration.name
  config:                                  # auth flow steps, JSON blob
    verify_ssl: true
    timeout: 30
```

### Integration Type Catalogue

```yaml
apiVersion: idp/v1
kind: IntegrationTypeCatalogue
metadata:
  code: aap                                # PK — lookup key
  name: Ansible Automation Platform
spec:
  description: "Red Hat AAP for automation"
  version: "2.4"
  is_active: true
  integration_role: platform               # platform | service
  actions:                                 # IntegrationAction entries
    - action_code: launch_job
      action_label: "Launch Job Template"
      description: "Launch a job template by ID or name"
      required_params:
        type: object
        properties:
          job_template_id: { type: integer }
      optional_params:
        type: object
        properties:
          extra_vars: { type: object }
      response_format:
        type: object
        properties:
          job_id: { type: integer }
          status: { type: string }
    - action_code: check_job_status
      action_label: "Check Job Status"
      description: "Poll job status by ID"
      required_params:
        type: object
        properties:
          job_id: { type: integer }
```

### Business Rule Policy

```yaml
apiVersion: idp/v1
kind: BusinessRulePolicy
metadata:
  name: change-approval-policy             # UNIQUE — lookup key
  description: "Standard change approval requirements"
spec:
  is_active: true
  policy_json:
    on_step_output:
      - when:
          step_type: servicenow
          field: state
          operator: equals
          value: "approved"
        then:
          action: continue
      - when:
          step_type: servicenow
          field: state
          operator: equals
          value: "rejected"
        then:
          action: abort
          message: "Change request rejected"
```

### Profile

```yaml
apiVersion: idp/v1
kind: Profile
metadata:
  name: dbops-team                         # UNIQUE — lookup key
  description: "Database operations team"
  ad_group: CN=GRP-IDP-DBOPS,OU=Groups,DC=corp
spec:
  is_admin: false
  is_auditor: false
  is_approver: true
  actions:
    type: pattern                          # all | list | pattern
    patterns:
      - oracle
      - patching
  targets:
    type: pattern
    patterns:
      - "PROD-*"
    exclusion_patterns:
      - "PROD-CRITICAL-*"
    filter_by_attribute:
      engine_type: ["oracle"]
      zone: ["prod"]
  environments:
    - production
    - staging
```

### Reference Data

```yaml
# reference/engines.yaml
apiVersion: idp/v1
kind: ReferenceData
metadata:
  type: engines
spec:
  - code: Oracle
    label: Oracle Database
    display_order: 1
    is_active: true
    icon_url: /icons/oracle.svg
  - code: SQL Server
    label: Microsoft SQL Server
    display_order: 2
    is_active: true
  - code: DB2
    label: IBM DB2
    display_order: 3
    is_active: true
```

```yaml
# reference/categories.yaml
apiVersion: idp/v1
kind: ReferenceData
metadata:
  type: categories
spec:
  - code: Provisioning
    label: Provisioning
    display_order: 1
    is_active: true
  - code: Patching
    label: Patching
    display_order: 2
    is_active: true
  - code: Administration
    label: Administration
    display_order: 3
    is_active: true
  - code: Monitoring
    label: Monitoring
    display_order: 4
    is_active: true
```

### Tags

```yaml
# tags.yaml
apiVersion: idp/v1
kind: Tags
spec:
  - oracle
  - sqlserver
  - db2
  - patching
  - provisioning
  - monitoring
  - backup
  - administration
```

### Feature Flags

```yaml
# feature-flags.yaml
apiVersion: idp/v1
kind: FeatureFlags
spec:
  - flag_key: new_workflow_builder
    enabled: true
    rollout_percent: 100
    description: "Enable new visual workflow builder"
  - flag_key: inventory_multi_table
    enabled: false
    rollout_percent: 0
    description: "Enable multi-table inventory support"
```

---

## Implementation Plan

### Ordering constraint

Entities have dependencies. The sync must apply them in order:

```
1. reference/engines.yaml       (no deps)
2. reference/categories.yaml    (no deps)
3. tags.yaml                    (no deps)
4. feature-flags.yaml           (no deps)
5. integration-types/*.yaml     (no deps)
6. integrations/*.yaml          (depends on: integration-types, other integrations for secret_service_ref)
7. policies/*.yaml              (no deps)
8. actions/*.yaml               (depends on: integrations, policies, reference data, tags)
9. profiles/*.yaml              (depends on: actions for LIST-type permissions)
```

### Phase 1: Export services for all entity types

**Goal:** Every entity type can be serialized to YAML and deserialized back.

Replicate the `profiles/services_export_import.py` pattern for each entity.

| New file | Entity types | Export function | Import function |
|----------|-------------|-----------------|-----------------|
| `catalog/services_export_import.py` | Actions, ActionMutex, Tags | `export_actions_yaml()` | `import_actions_yaml(content, user)` |
| `integrations/services_export_import.py` | Integrations | `export_integrations_yaml()` | `import_integrations_yaml(content, user)` |
| `integrations/services_export_import_types.py` | IntegrationTypeCatalogue + IntegrationAction | `export_integration_types_yaml()` | `import_integration_types_yaml(content, user)` |
| `catalog/services_export_import_policies.py` | BusinessRulePolicy | `export_policies_yaml()` | `import_policies_yaml(content, user)` |
| `reference/services_export_import.py` | RefEngine, RefCategory | `export_reference_yaml(type)` | `import_reference_yaml(content, type, user)` |
| `core/services_export_import.py` | FeatureFlag | `export_feature_flags_yaml()` | `import_feature_flags_yaml(content, user)` |
| `catalog/services_export_import_tags.py` | Tag | `export_tags_yaml()` | `import_tags_yaml(content, user)` |

**Each import function must:**
1. Parse YAML with `yaml.safe_load`
2. Validate the schema envelope (`apiVersion`, `kind`, required fields)
3. Resolve cross-references by name (e.g., `integration_ref: "aap-production"` → lookup `Integration.objects.get(name="aap-production")`)
4. Create-or-update using the unique key (name/code)
5. Wrap in `transaction.atomic()` — all-or-nothing
6. Log to `AUDIT_LOG` with `source='yaml_import'` in details
7. Return `(created, updated, unchanged)` counts

**Each export function must:**
1. Query all entities (or filter by a list of names)
2. Serialize to YAML using the schema above
3. Resolve FK IDs back to names (e.g., `integration_id=42` → `integration_ref: "aap-production"`)
4. Mask `credential_ref` values in export (show path but redact last segment)
5. Return UTF-8 bytes

### Phase 2: Sync API endpoints

**New API endpoints** (admin-only):

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin/actions/export/yaml/` | Export all actions as YAML |
| `POST` | `/admin/actions/sync/` | Import actions YAML (create-or-update) |
| `GET` | `/admin/integrations/export/yaml/` | Export all integrations as YAML |
| `POST` | `/admin/integrations/sync/` | Import integrations YAML |
| `GET` | `/admin/integration-types/export/yaml/` | Export integration type catalogue |
| `POST` | `/admin/integration-types/sync/` | Import integration types |
| `GET` | `/admin/policies/export/yaml/` | Export business rule policies |
| `POST` | `/admin/policies/sync/` | Import policies |
| `GET` | `/admin/reference/engines/export/yaml/` | Export engines |
| `POST` | `/admin/reference/engines/sync/` | Import engines |
| `GET` | `/admin/reference/categories/export/yaml/` | Export categories |
| `POST` | `/admin/reference/categories/sync/` | Import categories |
| `GET` | `/admin/tags/export/yaml/` | Export tags |
| `POST` | `/admin/tags/sync/` | Import tags |
| `GET` | `/admin/feature-flags/export/yaml/` | Export feature flags |
| `POST` | `/admin/feature-flags/sync/` | Import feature flags |

**Sync semantics (declarative):**
- Entities in YAML that don't exist in DB → **created**
- Entities in YAML that exist in DB → **updated** (full replace of fields)
- Entities in DB that are NOT in YAML → **not deleted** (additive sync by default)
- Optional `?mode=full` query param → entities in DB but NOT in YAML get **soft-deleted/disabled**

The `/sync/` endpoints accept `multipart/form-data` (file upload) or `application/x-yaml` (raw body).

### Phase 3: Management command for full repo sync

**New management command:** `python manage.py sync_config --config-dir /path/to/idp-config/`

```python
# core/management/commands/sync_config.py
"""
Apply a full IDP config directory to the database.
Processes entity types in dependency order.

Usage:
  python manage.py sync_config --config-dir ./idp-config/
  python manage.py sync_config --config-dir ./idp-config/ --dry-run
  python manage.py sync_config --config-dir ./idp-config/ --mode full
"""
```

This command:
1. Reads all YAML files from the config directory
2. Validates schemas offline (no DB queries)
3. Resolves cross-references and checks for dangling refs
4. Applies changes in dependency order (see ordering above)
5. Reports: `created`, `updated`, `unchanged`, `errors` per entity type
6. `--dry-run` mode: validate + report without writing to DB
7. `--mode full`: disable/delete entities not in config repo
8. `--validate-only`: schema + reference validation, no DB writes

### Phase 4: Drift detection

**New management command:** `python manage.py detect_drift --config-dir /path/to/idp-config/`

This command:
1. Exports current DB state as YAML (in-memory)
2. Loads config directory YAML
3. Compares entity-by-entity using the unique key
4. Reports:
   - **Missing in DB** — entity in YAML but not in DB (needs sync)
   - **Missing in YAML** — entity in DB but not in YAML (UI-created, unversioned)
   - **Diverged** — entity exists in both but fields differ (UI edit overrode code)
   - **In sync** — entity matches

**Optional Celery periodic task:** Run drift detection every N hours, push results to:
- Dashboard widget (new React component)
- Teams/Slack notification
- Audit log entry

### Phase 5: CI/CD pipeline

```yaml
# .github/workflows/sync-idp-config.yml
name: Sync IDP Configuration
on:
  push:
    branches: [main]
    paths: ['idp-config/**']
  pull_request:
    branches: [main]
    paths: ['idp-config/**']

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - name: Install dependencies
        run: pip install pyyaml jsonschema
      - name: Validate YAML schemas
        run: python scripts/validate_idp_config.py idp-config/
      - name: Check cross-references
        run: python scripts/check_references.py idp-config/

  apply-staging:
    if: github.event_name == 'push'
    needs: validate
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - name: Apply configuration to staging
        env:
          IDP_API_URL: ${{ secrets.STAGING_API_URL }}
          IDP_API_TOKEN: ${{ secrets.STAGING_API_TOKEN }}
        run: python scripts/apply_idp_config.py --env staging --dir idp-config/

  apply-production:
    if: github.event_name == 'push'
    needs: apply-staging
    runs-on: ubuntu-latest
    environment: production  # requires manual approval in GitHub
    steps:
      - uses: actions/checkout@v4
      - name: Apply configuration to production
        env:
          IDP_API_URL: ${{ secrets.PROD_API_URL }}
          IDP_API_TOKEN: ${{ secrets.PROD_API_TOKEN }}
        run: python scripts/apply_idp_config.py --env production --dir idp-config/
```

**`scripts/apply_idp_config.py`** — Python CLI that:
1. Reads YAML files from `idp-config/`
2. For each entity type (in dependency order), calls the corresponding `/admin/*/sync/` endpoint
3. Reports results per entity type
4. Exits non-zero on any error

### Phase 6: UI drift indicators

**Frontend changes:**

1. **Drift badge on admin panels** — If an entity was modified via UI after the last Git sync, show a warning icon with tooltip: "Modified locally — not in sync with config repo. Add to YAML to persist."

2. **"Export to YAML" button** — On each entity detail page, allow exporting a single entity as YAML (for copy-paste into the config repo).

3. **Sync status dashboard widget** — Show last sync time, counts of diverged entities, link to audit log.

**Backend support:**
- Add `last_synced_at` and `last_synced_hash` columns to track when an entity was last applied from YAML
- Compare `updated_at > last_synced_at` to detect UI-modified entities

---

## Database Migration

```sql
-- V111__add_iac_sync_tracking_columns.sql

-- Track when entities were last synced from config repo
ALTER TABLE ACTIONS_CATALOG ADD LAST_SYNCED_AT TIMESTAMP NULL;
ALTER TABLE ACTIONS_CATALOG ADD LAST_SYNCED_HASH VARCHAR2(64) NULL;

ALTER TABLE INTEGRATIONS ADD LAST_SYNCED_AT TIMESTAMP NULL;
ALTER TABLE INTEGRATIONS ADD LAST_SYNCED_HASH VARCHAR2(64) NULL;

ALTER TABLE BUSINESS_RULE_POLICIES ADD LAST_SYNCED_AT TIMESTAMP NULL;
ALTER TABLE BUSINESS_RULE_POLICIES ADD LAST_SYNCED_HASH VARCHAR2(64) NULL;

ALTER TABLE PROFILES ADD LAST_SYNCED_AT TIMESTAMP NULL;
ALTER TABLE PROFILES ADD LAST_SYNCED_HASH VARCHAR2(64) NULL;

ALTER TABLE INTEGRATION_TYPE_CATALOGUE ADD LAST_SYNCED_AT TIMESTAMP NULL;
ALTER TABLE INTEGRATION_TYPE_CATALOGUE ADD LAST_SYNCED_HASH VARCHAR2(64) NULL;

ALTER TABLE REF_ENGINES ADD LAST_SYNCED_AT TIMESTAMP NULL;
ALTER TABLE REF_ENGINES ADD LAST_SYNCED_HASH VARCHAR2(64) NULL;

ALTER TABLE REF_CATEGORIES ADD LAST_SYNCED_AT TIMESTAMP NULL;
ALTER TABLE REF_CATEGORIES ADD LAST_SYNCED_HASH VARCHAR2(64) NULL;

ALTER TABLE CORE_FEATURE_FLAGS ADD LAST_SYNCED_AT TIMESTAMP NULL;
ALTER TABLE CORE_FEATURE_FLAGS ADD LAST_SYNCED_HASH VARCHAR2(64) NULL;

-- Add new audit action types for sync operations
-- (extend CHECK constraint on AUDIT_LOG.ACTION_TYPE)
```

The `LAST_SYNCED_HASH` is a SHA-256 of the YAML content for that entity, used by drift detection
to quickly determine if the DB state matches the repo without full field comparison.

---

## Cross-Reference Resolution

All references between entities use **names**, not IDs. The import/sync process resolves them:

| Field in YAML | Resolved to | Error if missing? |
|---------------|-------------|-------------------|
| `integration_ref: "aap-production"` | `Action.integration_id` via `Integration.objects.get(name=...)` | Yes — reject import |
| `business_rule_policy_ref: "change-approval"` | `Action.business_rule_policy_id` via `BusinessRulePolicy.objects.get(name=...)` | Yes — reject import |
| `secret_service_ref: "vault-prod"` | `Integration.secret_service_id` via `Integration.objects.get(name=...)` | Yes — reject import |
| `mutex[].incompatible_with: "oracle-upgrade"` | `ActionMutex.incompatible_with_id` via `Action.objects.get(name=...)` | Yes — reject import |
| `metadata.category: "Patching"` | Validated against `RefCategory.objects.filter(code=...)` | Warning (allow if category doesn't exist yet) |
| `metadata.engine: "Oracle"` | Validated against `RefEngine.objects.filter(code=...)` | Warning |
| `metadata.platform: "AAP"` | Validated against `IntegrationTypeCatalogue.objects.filter(code=...)` | Warning |
| `metadata.tags: ["oracle"]` | Auto-created via `Tag.objects.get_or_create(name=...)` | Never fails |
| `profiles.actions.list: [42]` | **Problem: IDs not portable!** Must use action names instead | N/A |

**Profile action permissions fix:** The existing profile YAML uses `action_ids` (integer list).
For Git-as-source-of-truth, we need to also support `action_names` (string list) that resolve
to IDs at import time. The existing `action_ids` format continues to work for backward
compatibility, but the export should prefer `action_names`.

---

## Security Considerations

1. **Never store secrets in YAML** — Only Vault paths (`credential_ref`). The export masks even paths.
2. **Import/sync endpoints require admin role** — Same RBAC as existing admin endpoints.
3. **Audit trail** — Every sync operation logs to `AUDIT_LOG` with `details.source = 'config_sync'`.
4. **Schema validation** — Reject malformed YAML before any DB writes.
5. **Atomic per entity type** — Each entity type import is wrapped in `transaction.atomic()`.
6. **CI/CD token scoping** — API token for sync should have a dedicated `config_sync` permission, not full admin.
7. **No delete by default** — Sync is additive. Full mode (with deletes) requires explicit `--mode full`.

---

## Disaster Recovery Scenario

If the database is destroyed:

1. Run Flyway migrations → empty schema
2. Run `python manage.py sync_config --config-dir ./idp-config/` → full config restored
3. Runtime state (executions, audit logs, scheduled tasks) is lost — this is acceptable as it's operational data

This makes the config repo the **complete backup** of all IDP Portal configuration.

---

## UI Emergency Edit Flow

When an operator makes an emergency change via the UI:

1. UI shows a confirmation dialog: "This entity is managed by the config repo. Your change will be overwritten on next sync. Proceed?"
2. Change is applied immediately to the DB (for incident response speed).
3. The entity's `updated_at` becomes later than `last_synced_at` → drift detected.
4. Dashboard shows the entity as "diverged from config repo".
5. After the incident, the operator must:
   - Export the entity as YAML (button in UI)
   - Add it to the config repo (manual Git commit)
   - Merge to main → next sync makes DB and repo consistent again

---

## File Structure in Config Repo

```
idp-config/
├── README.md                          # Explains the structure and sync process
├── reference/
│   ├── engines.yaml                   # RefEngine entries
│   └── categories.yaml                # RefCategory entries
├── tags.yaml                          # All tags
├── feature-flags.yaml                 # All feature flags
├── integration-types/
│   ├── aap.yaml                       # IntegrationTypeCatalogue + IntegrationActions
│   ├── servicenow.yaml
│   ├── terraform_cloud.yaml
│   ├── github_actions.yaml
│   ├── azure_devops.yaml
│   └── vault.yaml
├── integrations/
│   ├── aap-production.yaml
│   ├── servicenow-itsm.yaml
│   ├── vault-production.yaml
│   └── github-actions-ci.yaml
├── policies/
│   ├── change-approval-policy.yaml
│   └── emergency-bypass-policy.yaml
├── actions/
│   ├── oracle-patching-quarterly.yaml
│   ├── oracle-provisioning.yaml
│   ├── db2-health-check.yaml
│   └── sqlserver-backup-full.yaml
└── profiles/
    ├── dbops-team.yaml
    ├── dba-senior.yaml
    ├── auditors.yaml
    └── platform-admin.yaml
```

---

## Implementation Priority & Effort Estimates

| Phase | Description | Dependencies | Files to create/modify |
|-------|-------------|--------------|----------------------|
| **1** | Export/import services for all entities | None | 7 new service files, ~200 lines each |
| **2** | Sync API endpoints | Phase 1 | 8 new view classes, URL registrations |
| **3** | `sync_config` management command | Phase 1 | 1 new command, ~300 lines |
| **4** | Drift detection command | Phase 1 | 1 new command, ~200 lines |
| **5** | CI/CD pipeline + apply script | Phases 2-3 | 3 scripts + 1 workflow YAML |
| **6** | UI drift indicators + DB migration | Phase 4 | 1 migration, model changes, 2-3 React components |

**Recommended starting order:** Phase 1 (export/import) is the foundation — everything else depends on it. Within Phase 1, start with **reference data** (simplest schema, lowest risk) → **integrations** → **policies** → **actions** (most complex, has cross-references) → update **profiles** (already exists, needs action_names support).

---

## Decision Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Source of truth | **Git repo** | Full disaster recovery, peer review, environment promotion |
| DB role | Runtime cache | Faster reads than Git; sync applies Git state to DB |
| UI writes | Allowed but ephemeral | Incident response needs instant changes; next sync overwrites |
| Sync semantics | Additive by default | Prevents accidental deletion; `--mode full` for cleanup |
| File format | YAML | Human-readable, already used for profiles, familiar to ops teams |
| Entity references | By name (not ID) | Portable across environments |
| One file per entity vs. bundle | One file per entity for actions/integrations/profiles; single file for reference data/tags/flags | Easier Git diffs, merge conflict avoidance |
| Profile action permissions | Support `action_names` (string list) alongside `action_ids` | Names are portable; IDs are environment-specific |
| Delete behavior on sync | Soft-delete/disable, never hard-delete | Preserves audit trail and FK integrity |
| Sync hash | SHA-256 of YAML content per entity | Fast drift detection without field-by-field comparison |
