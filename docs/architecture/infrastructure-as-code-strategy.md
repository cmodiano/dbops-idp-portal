# Infrastructure as Code Strategy — IDP Portal

**Date:** 2026-03-07
**Status:** Proposal
**Authors:** Architecture Team

---

## Problem Statement

The IDP Portal manages Actions, Workflows, Integrations, Profiles, Business Rule Policies, and Reference Data. Today these are configured exclusively through the UI/REST API, with state stored in Oracle. This creates challenges:

- **No version history** — Who changed what, when, and why? (Audit log exists but doesn't capture "desired state")
- **No peer review** — Changes go live instantly without approval from another team member
- **No rollback** — Reverting a broken action configuration requires manual re-editing
- **No environment promotion** — No way to promote configurations from dev → staging → prod
- **No disaster recovery** — If the database is lost, all configuration must be rebuilt manually

We need a strategy that versions configuration as code while preserving the UI-first experience that makes the platform accessible.

---

## Current State

### Already "as code"
| Asset | Mechanism | Maturity |
|-------|-----------|----------|
| Database schema | Flyway SQL migrations (`database/migrations/V*`) | High |
| Infrastructure | Docker Compose + Dockerfiles | High |
| Secrets references | Vault `credential_ref` paths | High |
| Profiles | YAML export/import (`profiles/services_export_import.py`) | Medium |

### Not yet "as code"
| Asset | Current storage | Priority |
|-------|----------------|----------|
| Actions (catalog) | Oracle `ACTIONS_CATALOG` | **High** |
| Integrations | Oracle `INTEGRATIONS` | **High** |
| Integration Type Catalogue | Oracle `INTEGRATION_TYPE_CATALOGUE` | Medium |
| Business Rule Policies | Oracle `BUSINESS_RULE_POLICIES` | Medium |
| Reference Data (engines, categories, platforms) | Oracle `REF_*` tables | Medium |
| Tags | Oracle `TAGS` | Low |
| Action Mutexes | Oracle `ACTION_MUTEX` | Low |

### What should NEVER be versioned as code
- **Executions** — Runtime state, not configuration
- **Audit logs** — Append-only operational data
- **User favorites** — User preferences
- **Scheduled executions** — Runtime scheduling state

---

## Recommended Architecture: DB-First with Export/Import + Managed-By Flag

### Why not pure GitOps?

Pure GitOps (Git as single source of truth, UI creates PRs) requires:
- Git API integration in the frontend
- A reconciliation controller
- Branch/merge conflict handling for concurrent UI users
- Significantly more complexity

For a team managing database operations, the **pragmatic approach** is:

1. **Keep the database as source of truth** — UI works exactly as today
2. **Add declarative export/import** — Any config can be serialized to YAML and reimported
3. **Add a `managed_by` flag** — Entities can be locked to "code-only" management
4. **CI/CD pipeline applies desired state** — A pipeline reads YAML from Git and calls import endpoints

```
 ┌─────────────────────────────────────────────────────────────────┐
 │                        Git Repository                          │
 │  idp-config/                                                   │
 │  ├── actions/                                                  │
 │  │   ├── oracle-patching.yaml                                  │
 │  │   └── db2-provisioning.yaml                                 │
 │  ├── integrations/                                             │
 │  │   ├── aap-production.yaml                                   │
 │  │   └── servicenow.yaml                                      │
 │  ├── profiles.yaml                    (already exists!)        │
 │  ├── policies/                                                 │
 │  │   └── change-approval-policy.yaml                           │
 │  └── reference/                                                │
 │      ├── engines.yaml                                          │
 │      ├── categories.yaml                                       │
 │      └── platforms.yaml                                        │
 └──────────────┬──────────────────────────────┬──────────────────┘
                │ CI/CD pipeline               │ Developer pushes
                │ calls import API             │ YAML changes
                ▼                              │
 ┌──────────────────────────┐                  │
 │       Django API         │◄─────────────────┘
 │  POST /admin/*/import/   │
 │  GET  /admin/*/export/   │
 └──────────┬───────────────┘
            │ create-or-update
            ▼
 ┌──────────────────────────┐     ┌──────────────────────┐
 │     Oracle Database      │◄────│    UI (React)        │
 │   (source of truth)      │     │  Direct API writes   │
 └──────────────────────────┘     └──────────────────────┘
```

### The `managed_by` Flag

Each versionable entity gets a new field:

```python
managed_by = models.CharField(
    max_length=10,
    choices=[('ui', 'UI'), ('code', 'Code')],
    default='ui',
    db_column='MANAGED_BY',
)
```

**Behavior:**
- `managed_by='ui'` → Fully editable in the UI (default, backward-compatible)
- `managed_by='code'` → **Read-only in the UI**, only modifiable via import endpoint
- The UI shows a lock icon and "Managed by code" badge on code-managed entities
- The import endpoint sets `managed_by='code'` automatically
- An admin can "release" an entity back to UI management via a dedicated endpoint

This prevents the **drift problem**: if an entity is managed by code, no one can accidentally modify it through the UI.

---

## YAML Schema Design

### Action Definition

```yaml
# idp-config/actions/oracle-patching.yaml
apiVersion: idp/v1
kind: Action
metadata:
  name: oracle-patching-quarterly
  description: "Quarterly Oracle database patching workflow"
  category: Patching
  engine: Oracle
  platform: AAP
  item_type: workflow
  tags:
    - oracle
    - patching
    - quarterly
spec:
  status: published
  requires_target: true
  default_impact_level: high
  parameters_schema:
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
  integration_ref: aap-production  # Reference by name
  business_rule_policy_ref: change-approval-policy  # Reference by name
  mutex:
    - incompatible_with: oracle-upgrade
      same_target: true
      description: "Cannot patch during upgrade"
```

### Integration Definition

```yaml
# idp-config/integrations/aap-production.yaml
apiVersion: idp/v1
kind: Integration
metadata:
  name: aap-production
  type: aap
  role: platform
spec:
  base_url: https://aap.internal.company.com
  auth_flow: basic_then_token
  token_url: https://aap.internal.company.com/api/v2/tokens/
  credential_ref: vault:secret/integrations/aap-prod  # Vault path, never inline secrets
  icon: /icons/aap.svg
  config:
    verify_ssl: true
    timeout: 30
```

### Business Rule Policy Definition

```yaml
# idp-config/policies/change-approval-policy.yaml
apiVersion: idp/v1
kind: BusinessRulePolicy
metadata:
  name: change-approval-policy
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

### Reference Data

```yaml
# idp-config/reference/engines.yaml
apiVersion: idp/v1
kind: ReferenceData
metadata:
  type: engines
spec:
  - code: Oracle
    name: Oracle Database
    icon_url: /icons/oracle.svg
  - code: SQL Server
    name: Microsoft SQL Server
    icon_url: /icons/sqlserver.svg
  - code: DB2
    name: IBM DB2
    icon_url: /icons/db2.svg
```

---

## Implementation Phases

### Phase 1: Generalize Export/Import (extend existing pattern)

**Goal:** Every configurable entity can be exported to YAML and reimported.

**Backend changes:**

| App | New file | Endpoints |
|-----|----------|-----------|
| `catalog` | `catalog/services_export_import.py` | `GET /admin/actions/export/`, `POST /admin/actions/import/` |
| `integrations` | `integrations/services_export_import.py` | `GET /admin/integrations/export/`, `POST /admin/integrations/import/` |
| `catalog` | (extend above) | `GET /admin/business-rule-policies/export/`, `POST .../import/` |
| `reference` | `reference/services_export_import.py` | `GET /admin/reference/export/`, `POST /admin/reference/import/` |

**Pattern to follow** (from `profiles/services_export_import.py`):
- `export_*_yaml()` → Serialize all entities to YAML bytes
- `import_*_yaml(content, user)` → Parse, validate schema, create-or-update, return `(created, updated)` counts
- `_validate_yaml_schema(parsed)` → Structural validation before applying changes
- References between entities use `name` (not IDs) for portability across environments

**Frontend changes:**
- Add "Export YAML" / "Import YAML" buttons to each admin panel
- Reuse the existing `ProfileImportModal.tsx` pattern

### Phase 2: Add `managed_by` field

**Database migration:**
```sql
-- V090__add_managed_by_columns.sql
ALTER TABLE ACTIONS_CATALOG ADD MANAGED_BY VARCHAR2(10) DEFAULT 'ui' NOT NULL;
ALTER TABLE INTEGRATIONS ADD MANAGED_BY VARCHAR2(10) DEFAULT 'ui' NOT NULL;
ALTER TABLE BUSINESS_RULE_POLICIES ADD MANAGED_BY VARCHAR2(10) DEFAULT 'ui' NOT NULL;

ALTER TABLE ACTIONS_CATALOG ADD CONSTRAINT CK_ACTIONS_MANAGED_BY CHECK (MANAGED_BY IN ('ui', 'code'));
ALTER TABLE INTEGRATIONS ADD CONSTRAINT CK_INTEGRATIONS_MANAGED_BY CHECK (MANAGED_BY IN ('ui', 'code'));
ALTER TABLE BUSINESS_RULE_POLICIES ADD CONSTRAINT CK_BRP_MANAGED_BY CHECK (MANAGED_BY IN ('ui', 'code'));
```

**Backend changes:**
- Add `managed_by` field to Django models
- Import endpoint sets `managed_by='code'` on imported entities
- Update/delete views reject modifications on `managed_by='code'` entities with HTTP 403
- Add `POST /admin/actions/{id}/release/` to set `managed_by='ui'`

**Frontend changes:**
- Show lock icon + "Managed by code" badge on code-managed entities
- Disable edit/delete buttons for code-managed entities
- Show tooltip: "This entity is managed via YAML. To modify, update the YAML file and reimport."

### Phase 3: CI/CD Reconciliation Pipeline

**GitHub Actions workflow** (or Azure DevOps equivalent):

```yaml
# .github/workflows/sync-idp-config.yml
name: Sync IDP Configuration
on:
  push:
    branches: [main]
    paths: ['idp-config/**']

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate YAML schemas
        run: python scripts/validate_idp_config.py idp-config/
      - name: Apply to staging
        env:
          IDP_API_URL: ${{ secrets.STAGING_API_URL }}
          IDP_API_TOKEN: ${{ secrets.STAGING_API_TOKEN }}
        run: python scripts/apply_idp_config.py --env staging idp-config/
      - name: Drift detection
        run: python scripts/detect_drift.py --env staging idp-config/
```

**Drift detection** (scheduled Celery task):
- Export current DB state → compare with Git repo content
- Report drift as Slack/Teams notification or dashboard warning
- Optional: auto-remediate by re-applying Git state

### Phase 4: UI Writes as PRs (optional, full GitOps)

Only if the team wants full GitOps:
- UI "Save" button generates a YAML diff
- Calls GitHub/Azure DevOps API to create a PR
- PR review + merge triggers Phase 3 pipeline
- Requires frontend integration with Git API

---

## Security Considerations

1. **Never store secrets in YAML** — Use `credential_ref: vault:path/to/secret` references only
2. **Import endpoint requires admin role** — Same RBAC as existing admin endpoints
3. **Audit trail** — All imports logged in `AUDIT_LOG` with source='yaml_import'
4. **Schema validation** — Reject malformed YAML before applying any changes
5. **Atomic imports** — Wrap import in a database transaction; rollback on any error
6. **Sensitive fields excluded from export** — `credential_ref` values are masked in export

---

## Migration Path

1. **No breaking changes** — All existing UI workflows continue to work
2. **Default `managed_by='ui'`** — Existing entities are unaffected
3. **Opt-in per entity** — Teams choose which entities to manage as code
4. **Gradual adoption** — Start with reference data (low risk), then integrations, then actions

---

## Decision Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Source of truth | Database (not Git) | Preserves instant UI editing; Git is secondary sync |
| File format | YAML | Human-readable, already used for profiles, familiar to DevOps teams |
| Entity references | By name (not ID) | Portable across environments (dev/staging/prod have different IDs) |
| Conflict resolution | Last-write-wins with audit | Simpler than merge; audit trail provides recovery |
| Import granularity | Per-entity-type | Import all actions, or all integrations; not mixed bundles |
| `managed_by` default | `ui` | Backward-compatible; opt-in for code management |
