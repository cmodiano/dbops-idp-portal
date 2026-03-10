# Infrastructure as Code — Implementation Guide

> ⚠️ **OBSOLÈTE** — Ce document a été remplacé par la Story 64-17 (renommage IaC→CaC).
> Le document de référence actuel est : [Configuration as Code – Guide d'implémentation](configuration-as-code-implementation-guide.md)
> Ce document est conservé à titre historique uniquement.

**Date:** 2026-03-07
**Status:** Implementation specification — ⚠️ OBSOLÈTE, remplacé par CaC
**Companion doc:** [Strategy document](./infrastructure-as-code-strategy.md)

This document is the **developer handbook** for implementing the IaC feature. It explains
exactly what code to write, where to put it, and how every piece connects — from YAML
files on disk to the Oracle database and back.

---

## Table of Contents

1. [Core Concept: Declarative Reconciliation](#1-core-concept-declarative-reconciliation)
2. [YAML Schema Envelope](#2-yaml-schema-envelope)
3. [Entity-by-Entity Implementation Details](#3-entity-by-entity-implementation-details)
4. [Reconciliation Engine (Sync Logic)](#4-reconciliation-engine-sync-logic)
5. [Cross-Reference Resolution](#5-cross-reference-resolution)
6. [API Endpoints (Sync Views)](#6-api-endpoints-sync-views)
7. [Management Commands](#7-management-commands)
8. [Drift Detection](#8-drift-detection)
9. [Database Migration](#9-database-migration)
10. [CI/CD Pipeline](#10-cicd-pipeline)
11. [Frontend Changes](#11-frontend-changes)
12. [Testing Strategy](#12-testing-strategy)
13. [Phased Rollout Plan](#13-phased-rollout-plan)

---

## 1. Core Concept: Declarative Reconciliation

### What the API does automatically

When you POST a YAML configuration, the backend acts as a **reconciliation engine**. You
describe the **desired state** — the backend figures out what to create, update, or skip.

```
  YAML (desired state)          Database (current state)
  ┌──────────────────┐          ┌──────────────────┐
  │ action: deploy   │          │ action: deploy   │
  │   engine: AAP    │   diff   │   engine: Tower  │  ← engine changed
  │                  │ ───────► │                  │  → UPDATE
  │ action: backup   │          │                  │
  │   engine: Oracle │          │ (does not exist) │  → CREATE
  │                  │          │                  │
  │ (not mentioned)  │          │ action: legacy   │  → UNCHANGED (additive)
  └──────────────────┘          │   engine: DB2    │     or DISABLED (full mode)
                                └──────────────────┘
```

**Key rule:** The sync is **additive by default**. Entities present in the DB but absent
from the YAML are left untouched. Only with `--mode full` (or `?mode=full`) are missing
entities soft-deleted/disabled.

### Concrete example: AAP integration with projects & templates

AAP (Ansible Automation Platform) organises resources by API endpoint. When you sync an
integration of type `aap`, each resource type maps to a different AAP API:

| Resource type | AAP API endpoint | IDP model |
|---------------|------------------|-----------|
| Integration itself | N/A (local DB only) | `Integration` |
| Projects | `GET/POST/PATCH /api/v2/projects/` | Not a separate IDP model — embedded in action execution_steps |
| Job templates | `GET/POST/PATCH /api/v2/job_templates/` | Referenced by `connector_config.job_template` in execution steps |
| Inventories | `GET/POST/PATCH /api/v2/inventories/` | Referenced by `connector_config.inventory` in execution steps |

The IaC sync does **not** directly call AAP APIs. It syncs the **IDP Portal configuration**
(actions, integrations, profiles, etc.) into the IDP database. The execution engine then
uses this configuration to call AAP at runtime.

However, a future phase could extend the sync to also reconcile AAP-side resources
(projects, templates) by calling AAP APIs during the sync — making IDP Portal a
**single pane of glass** for all platform configuration.

---

## 2. YAML Schema Envelope

Every YAML file uses a Kubernetes-inspired envelope:

```yaml
apiVersion: idp/v1          # Fixed — schema version for forward compat
kind: Action                 # Entity type (Action, Integration, Profile, etc.)
metadata:
  name: oracle-patching      # UNIQUE lookup key — used for create-or-update
  # ... entity-specific metadata
spec:
  # ... entity-specific configuration
```

### Why this format?

1. **Self-describing** — A YAML file declares its own type. The sync command can read any
   file and know what entity it represents.
2. **Versionable** — When the schema evolves, `apiVersion: idp/v2` signals the parser to
   use updated validation rules.
3. **Tool-friendly** — Standard envelope means we can write a single generic validator and
   dispatcher.

### Validation rules (apply to ALL entity types)

```python
def validate_envelope(parsed: dict) -> None:
    """
    Validate the apiVersion/kind/metadata envelope.
    Called before any entity-specific validation.
    """
    if not isinstance(parsed, dict):
        raise InvalidStateError(code="INVALID_YAML_SCHEMA",
                                message="Le fichier YAML doit être un objet.")

    api_version = parsed.get("apiVersion")
    if api_version != "idp/v1":
        raise InvalidStateError(code="INVALID_API_VERSION",
                                message=f"apiVersion '{api_version}' non supporté. Attendu: 'idp/v1'.")

    kind = parsed.get("kind")
    VALID_KINDS = {"Action", "Integration", "IntegrationTypeCatalogue",
                   "BusinessRulePolicy", "Profile", "ReferenceData",
                   "Tags", "FeatureFlags"}
    if kind not in VALID_KINDS:
        raise InvalidStateError(code="INVALID_KIND",
                                message=f"kind '{kind}' inconnu. Valeurs acceptées: {VALID_KINDS}.")

    metadata = parsed.get("metadata")
    if not isinstance(metadata, dict):
        raise InvalidStateError(code="INVALID_METADATA",
                                message="Le champ 'metadata' est requis et doit être un objet.")

    # Tags and FeatureFlags use a list format in spec, no individual name needed
    if kind not in ("Tags", "FeatureFlags", "ReferenceData"):
        name = metadata.get("name", "").strip() if metadata.get("name") else ""
        if not name:
            raise InvalidStateError(code="MISSING_NAME",
                                    message="metadata.name est requis.")
```

---

## 3. Entity-by-Entity Implementation Details

### 3.1 Reference Data (Engines & Categories)

**Simplest entity — start here.**

#### Database models

```
RefEngine:   id, code (unique), label, display_order, is_active, icon_url
RefCategory: id, code (unique), label, display_order, is_active
```

#### YAML schema

```yaml
# reference/engines.yaml
apiVersion: idp/v1
kind: ReferenceData
metadata:
  type: engines                    # "engines" or "categories"
spec:
  - code: Oracle                   # UNIQUE lookup key
    label: Oracle Database
    display_order: 1
    is_active: true
    icon_url: /icons/oracle.svg    # engines only
  - code: SQL Server
    label: Microsoft SQL Server
    display_order: 2
    is_active: true
```

#### Export function

```python
# reference/services_export_import.py

def export_reference_yaml(ref_type: str) -> bytes:
    """
    Export engines or categories as YAML.

    Args:
        ref_type: "engines" or "categories"

    Returns:
        UTF-8 bytes of YAML content
    """
    if ref_type == "engines":
        items = RefEngine.objects.all().order_by("display_order")
        spec = []
        for e in items:
            entry = {
                "code": e.code,
                "label": e.label,
                "display_order": e.display_order,
                "is_active": bool(e.is_active),
            }
            if e.icon_url:
                entry["icon_url"] = e.icon_url
            spec.append(entry)
    elif ref_type == "categories":
        items = RefCategory.objects.all().order_by("display_order")
        spec = [
            {
                "code": c.code,
                "label": c.label,
                "display_order": c.display_order,
                "is_active": bool(c.is_active),
            }
            for c in items
        ]
    else:
        raise InvalidStateError(code="INVALID_REF_TYPE",
                                message=f"Type '{ref_type}' inconnu. Utilisez 'engines' ou 'categories'.")

    root = {
        "apiVersion": "idp/v1",
        "kind": "ReferenceData",
        "metadata": {"type": ref_type},
        "spec": spec,
    }
    buf = io.StringIO()
    yaml.dump(root, buf, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return buf.getvalue().encode("utf-8")
```

#### Import function

```python
@transaction.atomic
def import_reference_yaml(content: bytes, ref_type: str, user=None) -> tuple[int, int, int]:
    """
    Import engines or categories from YAML.

    Returns:
        (created, updated, unchanged) counts
    """
    parsed = _parse_and_validate(content, expected_kind="ReferenceData")
    spec = parsed.get("spec", [])

    # Validate metadata.type matches ref_type argument
    yaml_type = parsed.get("metadata", {}).get("type")
    if yaml_type != ref_type:
        raise InvalidStateError(
            code="TYPE_MISMATCH",
            message=f"metadata.type='{yaml_type}' ne correspond pas au type attendu '{ref_type}'."
        )

    Model = RefEngine if ref_type == "engines" else RefCategory
    created = updated = unchanged = 0

    for item in spec:
        code = item["code"]
        defaults = {
            "label": item.get("label", code),
            "display_order": item.get("display_order", 0),
            "is_active": 1 if item.get("is_active", True) else 0,
        }
        if ref_type == "engines" and "icon_url" in item:
            defaults["icon_url"] = item["icon_url"]

        obj, was_created = Model.objects.get_or_create(code=code, defaults=defaults)

        if was_created:
            created += 1
        else:
            changed = False
            for field, value in defaults.items():
                if getattr(obj, field) != value:
                    setattr(obj, field, value)
                    changed = True
            if changed:
                obj.save()
                updated += 1
            else:
                unchanged += 1

    # Audit log
    AuditService.create_entry(
        user_id=user.id if user else None,
        action_type="CONFIG_SYNC",
        entity_type=f"REF_{ref_type.upper()}",
        entity_id=None,
        details={"source": "yaml_import", "created": created, "updated": updated, "unchanged": unchanged},
    )

    return (created, updated, unchanged)
```

**Pattern:** This `get_or_create` + field-by-field comparison pattern is the core of
every import function. The only differences between entity types are:
- The model class
- The lookup key field (code, name, flag_key, etc.)
- The fields to compare
- Cross-reference resolution (for entities with FK relationships)

---

### 3.2 Tags

#### Database model

```
Tag: id, name (unique), created_at
```

#### YAML schema

```yaml
# tags.yaml
apiVersion: idp/v1
kind: Tags
spec:
  - oracle
  - sqlserver
  - patching
  - backup
```

#### Import logic

```python
@transaction.atomic
def import_tags_yaml(content: bytes, user=None) -> tuple[int, int, int]:
    parsed = _parse_and_validate(content, expected_kind="Tags")
    spec = parsed.get("spec", [])

    created = unchanged = 0
    for tag_name in spec:
        normalized = tag_name.strip().lower()
        _, was_created = Tag.objects.get_or_create(name=normalized)
        if was_created:
            created += 1
        else:
            unchanged += 1

    return (created, 0, unchanged)  # Tags are never "updated" — name is the only field
```

---

### 3.3 Feature Flags

#### Database model

```
FeatureFlag: id, flag_key (unique), enabled, rollout_percent, description, updated_at, updated_by
```

#### YAML schema

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

#### Import logic

```python
@transaction.atomic
def import_feature_flags_yaml(content: bytes, user=None) -> tuple[int, int, int]:
    parsed = _parse_and_validate(content, expected_kind="FeatureFlags")
    spec = parsed.get("spec", [])

    created = updated = unchanged = 0
    for item in spec:
        flag_key = item["flag_key"]
        defaults = {
            "enabled": item.get("enabled", False),
            "rollout_percent": item.get("rollout_percent", 0),
            "description": item.get("description", ""),
        }
        if user:
            defaults["updated_by"] = user.username if hasattr(user, "username") else str(user)

        obj, was_created = FeatureFlag.objects.get_or_create(
            flag_key=flag_key, defaults=defaults
        )
        if was_created:
            created += 1
        else:
            changed = _apply_field_changes(obj, defaults)
            if changed:
                obj.save()
                updated += 1
            else:
                unchanged += 1

    return (created, updated, unchanged)
```

---

### 3.4 Integration Type Catalogue

#### Database models

```
IntegrationTypeCatalogue: code (PK), name, description, version, is_active,
                          integration_role, created_at, updated_at
IntegrationAction:        id, integration_type (FK), action_code, action_label,
                          description, required_params (JSON), optional_params (JSON),
                          response_format (JSON), is_active, created_at, updated_at
                          unique_together: (integration_type, action_code)
```

#### YAML schema

```yaml
# integration-types/aap.yaml
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
  actions:
    - action_code: launch_job              # UNIQUE within this type
      action_label: "Launch Job Template"
      description: "Launch a job template by ID or name"
      is_active: true
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
      is_active: true
      required_params:
        type: object
        properties:
          job_id: { type: integer }
```

#### Import logic — nested child entities

This is the first entity with **child records** (IntegrationAction). The pattern:

```python
@transaction.atomic
def import_integration_types_yaml(content: bytes, user=None) -> tuple[int, int, int]:
    parsed = _parse_and_validate(content, expected_kind="IntegrationTypeCatalogue")
    metadata = parsed["metadata"]
    spec = parsed["spec"]

    code = metadata["code"]
    defaults = {
        "name": metadata.get("name", code),
        "description": spec.get("description", ""),
        "version": spec.get("version", ""),
        "is_active": spec.get("is_active", True),
        "integration_role": spec.get("integration_role", "platform"),
    }

    obj, was_created = IntegrationTypeCatalogue.objects.get_or_create(
        code=code, defaults=defaults
    )
    if not was_created:
        _apply_field_changes(obj, defaults)
        obj.save()

    # --- Reconcile child IntegrationAction records ---
    yaml_actions = spec.get("actions", [])
    existing_actions = {
        a.action_code: a
        for a in IntegrationAction.objects.filter(integration_type=obj)
    }

    actions_created = actions_updated = actions_unchanged = 0

    for action_item in yaml_actions:
        action_code = action_item["action_code"]
        action_defaults = {
            "action_label": action_item.get("action_label", action_code),
            "description": action_item.get("description", ""),
            "is_active": action_item.get("is_active", True),
        }
        # JSON fields stored as text — serialize to string
        for json_field in ("required_params", "optional_params", "response_format"):
            if action_item.get(json_field):
                action_defaults[json_field] = json.dumps(action_item[json_field])

        if action_code in existing_actions:
            existing = existing_actions.pop(action_code)
            changed = _apply_field_changes(existing, action_defaults)
            if changed:
                existing.save()
                actions_updated += 1
            else:
                actions_unchanged += 1
        else:
            IntegrationAction.objects.create(
                integration_type=obj,
                action_code=action_code,
                **action_defaults,
            )
            actions_created += 1

    # In full mode: deactivate actions in DB but not in YAML
    # (not done in additive mode)

    created = 1 if was_created else 0
    updated = 0 if was_created else 1
    unchanged = 0 if was_created or updated else 1

    return (created, updated, unchanged)
```

**Key pattern for child entities:** Load existing children into a dict keyed by their
natural key (`action_code`), then pop from the dict as you process YAML items. Whatever
remains in the dict after the loop are "orphaned" children (present in DB but not in YAML).

---

### 3.5 Integrations

#### Database model

```
Integration: id, type, name (unique), base_url, credential_ref, icon,
             auth_flow, token_url, config (JSON CLOB), secret_service (FK self),
             status, health_status, health_checked_at, health_error_message,
             created_at, updated_at
```

#### YAML schema

```yaml
# integrations/aap-production.yaml
apiVersion: idp/v1
kind: Integration
metadata:
  name: aap-production                     # UNIQUE — lookup key
  type: aap                                # validated against IntegrationTypeCatalogue.code
spec:
  base_url: https://aap.internal.company.com
  auth_flow: basic_then_token
  token_url: https://aap.internal.company.com/api/v2/tokens/
  credential_ref: secret/integrations/aap-prod    # Vault path — NEVER inline secrets
  icon: /icons/aap.svg
  secret_service_ref: vault-production     # FK resolved by name → Integration.name
  config:
    verify_ssl: true
    timeout: 30
```

#### Cross-reference resolution

The `secret_service_ref` field is a self-referential FK. Resolution:

```python
def _resolve_integration_refs(spec: dict) -> dict:
    """Resolve name-based references to IDs for Integration."""
    resolved = {}

    # secret_service_ref → secret_service_id
    ref_name = spec.get("secret_service_ref")
    if ref_name:
        try:
            ref_integration = Integration.objects.get(name=ref_name)
            resolved["secret_service_id"] = ref_integration.id
        except Integration.DoesNotExist:
            raise InvalidStateError(
                code="REF_NOT_FOUND",
                message=f"Integration référencée '{ref_name}' (secret_service_ref) introuvable.",
                details={"ref_name": ref_name, "ref_type": "Integration"}
            )

    return resolved
```

#### Export — credential masking

```python
def _mask_credential_ref(credential_ref: str | None) -> str | None:
    """
    Mask the last path segment of a Vault path.
    Example: 'secret/integrations/aap-prod' → 'secret/integrations/***'
    """
    if not credential_ref:
        return None
    parts = credential_ref.rsplit("/", 1)
    if len(parts) == 2:
        return f"{parts[0]}/***"
    return "***"
```

#### Import — ordering matters

Integrations can reference other integrations via `secret_service_ref`. This creates a
dependency ordering problem. The solution is **two-pass import**:

```python
@transaction.atomic
def import_integrations_yaml(items: list[dict], user=None) -> tuple[int, int, int]:
    """
    Import multiple integration YAML docs.

    Pass 1: Create/update all integrations WITHOUT resolving secret_service_ref.
    Pass 2: Resolve secret_service_ref now that all integrations exist.
    """
    created = updated = unchanged = 0

    # Pass 1: upsert all integrations
    for item in items:
        metadata = item["metadata"]
        spec = item["spec"]
        name = metadata["name"]

        defaults = {
            "type": metadata["type"],
            "base_url": spec.get("base_url", ""),
            "auth_flow": spec.get("auth_flow", "token"),
            "token_url": spec.get("token_url", ""),
            "credential_ref": spec.get("credential_ref", ""),
            "icon": spec.get("icon", ""),
        }
        if spec.get("config"):
            defaults["config"] = json.dumps(spec["config"])

        obj, was_created = Integration.objects.get_or_create(
            name=name, defaults=defaults
        )
        if was_created:
            created += 1
        else:
            changed = _apply_field_changes(obj, defaults)
            if changed:
                obj.save()
                updated += 1
            else:
                unchanged += 1

    # Pass 2: resolve secret_service_ref
    for item in items:
        ref_name = item["spec"].get("secret_service_ref")
        if ref_name:
            integration = Integration.objects.get(name=item["metadata"]["name"])
            ref_integration = Integration.objects.get(name=ref_name)
            if integration.secret_service_id != ref_integration.id:
                integration.secret_service_id = ref_integration.id
                integration.save(update_fields=["secret_service_id"])

    return (created, updated, unchanged)
```

---

### 3.6 Business Rule Policies

#### Database model

```
BusinessRulePolicy: id, name (unique), description, policy_json (CLOB),
                    is_active, created_at, updated_at, created_by (FK User)
```

#### YAML schema

```yaml
# policies/change-approval-policy.yaml
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

#### Import logic

```python
@transaction.atomic
def import_policies_yaml(content: bytes, user=None) -> tuple[int, int, int]:
    parsed = _parse_and_validate(content, expected_kind="BusinessRulePolicy")
    metadata = parsed["metadata"]
    spec = parsed["spec"]

    name = metadata["name"]
    defaults = {
        "description": metadata.get("description", ""),
        "is_active": spec.get("is_active", True),
        "policy_json": json.dumps(spec.get("policy_json", {})),
    }
    if user:
        defaults["created_by"] = user

    obj, was_created = BusinessRulePolicy.objects.get_or_create(
        name=name, defaults=defaults
    )
    if not was_created:
        # Don't overwrite created_by on update
        update_defaults = {k: v for k, v in defaults.items() if k != "created_by"}
        changed = _apply_field_changes(obj, update_defaults)
        if changed:
            obj.save()
            return (0, 1, 0)
        return (0, 0, 1)

    return (1, 0, 0)
```

---

### 3.7 Actions & Workflows (Most Complex)

#### Database model

```
Action: id, name (unique), description, category, engine, platform,
        parameters_schema (JSON), impact_rules (JSON), execution_steps (JSON),
        notification_config (JSON), remediation_rules (JSON),
        business_rule_policies (JSON — legacy), business_rule_policy (FK),
        default_impact_level, status, item_type, requires_target,
        created_by (FK User), integration (FK Integration),
        created_at, updated_at, deleted_by, deleted_at, deletion_reason

ActionTag: action (FK), tag (FK) — junction table
ActionMutex: action (FK), incompatible_with (FK Action), same_target, description
```

#### YAML schema (full)

```yaml
# actions/oracle-patching-quarterly.yaml
apiVersion: idp/v1
kind: Action
metadata:
  name: oracle-patching-quarterly         # UNIQUE — lookup key
  description: "Quarterly Oracle database patching"
  category: Patching                       # must exist in reference/categories.yaml
  engine: Oracle                           # must exist in reference/engines.yaml
  platform: AAP                            # must exist in integration-types/
  item_type: workflow                      # action | workflow
  tags:
    - oracle
    - patching
spec:
  status: published                        # draft | published | disabled
  requires_target: true
  default_impact_level: high               # low | medium | high | critical
  parameters_schema:                       # JSON Schema draft-07
    type: object
    properties:
      patch_version:
        type: string
      downtime_window:
        type: integer
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
  notification_config:
    email: true
    teams: true
  remediation_rules: null
  integration_ref: aap-production          # resolved by name → Integration.name
  business_rule_policy_ref: change-approval-policy  # resolved by name
  mutex:
    - incompatible_with: oracle-upgrade    # resolved by name → Action.name
      same_target: true
      description: "Cannot patch during upgrade"
```

#### Cross-reference resolution (multiple FKs)

```python
def _resolve_action_refs(metadata: dict, spec: dict) -> dict:
    """
    Resolve all name-based references for an Action.
    Returns a dict of resolved ID fields.
    Raises InvalidStateError if a required ref is missing.
    """
    resolved = {}
    warnings = []

    # integration_ref → integration_id
    ref = spec.get("integration_ref")
    if ref:
        try:
            resolved["integration_id"] = Integration.objects.get(name=ref).id
        except Integration.DoesNotExist:
            raise InvalidStateError(
                code="REF_NOT_FOUND",
                message=f"Integration '{ref}' (integration_ref) introuvable.",
                details={"ref_name": ref}
            )

    # business_rule_policy_ref → business_rule_policy_id
    ref = spec.get("business_rule_policy_ref")
    if ref:
        try:
            resolved["business_rule_policy_id"] = BusinessRulePolicy.objects.get(name=ref).id
        except BusinessRulePolicy.DoesNotExist:
            raise InvalidStateError(
                code="REF_NOT_FOUND",
                message=f"BusinessRulePolicy '{ref}' (business_rule_policy_ref) introuvable.",
                details={"ref_name": ref}
            )

    # category — warn if doesn't exist (soft validation)
    category = metadata.get("category")
    if category and not RefCategory.objects.filter(code=category).exists():
        warnings.append(f"Catégorie '{category}' non trouvée dans REF_CATEGORIES.")

    # engine — warn if doesn't exist
    engine = metadata.get("engine")
    if engine and not RefEngine.objects.filter(code=engine).exists():
        warnings.append(f"Moteur '{engine}' non trouvé dans REF_ENGINES.")

    # platform — warn if doesn't exist
    platform = metadata.get("platform")
    if platform and not IntegrationTypeCatalogue.objects.filter(code=platform).exists():
        warnings.append(f"Type d'intégration '{platform}' non trouvé dans INTEGRATION_TYPE_CATALOGUE.")

    return resolved, warnings
```

#### Import with tags and mutex

```python
@transaction.atomic
def import_actions_yaml(content: bytes, user=None) -> tuple[int, int, int]:
    parsed = _parse_and_validate(content, expected_kind="Action")
    metadata = parsed["metadata"]
    spec = parsed["spec"]

    name = metadata["name"]
    resolved_refs, warnings = _resolve_action_refs(metadata, spec)

    # Build action fields
    defaults = {
        "description": metadata.get("description", ""),
        "category": metadata.get("category", ""),
        "engine": metadata.get("engine", ""),
        "platform": metadata.get("platform", ""),
        "item_type": metadata.get("item_type", "action"),
        "status": spec.get("status", "draft"),
        "requires_target": spec.get("requires_target", True),
        "default_impact_level": spec.get("default_impact_level", "medium"),
        **resolved_refs,  # integration_id, business_rule_policy_id
    }

    # JSON CLOB fields
    for json_field in ("parameters_schema", "execution_steps", "impact_rules",
                       "notification_config", "remediation_rules"):
        value = spec.get(json_field)
        if value is not None:
            defaults[json_field] = json.dumps(value) if not isinstance(value, str) else value
        else:
            defaults[json_field] = None

    if user:
        defaults["created_by"] = user

    # Upsert
    obj, was_created = Action.objects.get_or_create(name=name, defaults=defaults)
    if not was_created:
        update_fields = {k: v for k, v in defaults.items() if k != "created_by"}
        _apply_field_changes(obj, update_fields)
        obj.save()

    # --- Sync tags ---
    tag_names = metadata.get("tags", [])
    if tag_names:
        ActionTag.objects.filter(action=obj).delete()
        for tag_name in tag_names:
            tag, _ = Tag.objects.get_or_create(name=tag_name.strip().lower())
            ActionTag.objects.create(action=obj, tag=tag)

    # --- Sync mutex rules ---
    mutex_items = spec.get("mutex", [])
    ActionMutex.objects.filter(action=obj).delete()  # full replace
    for mutex_item in mutex_items:
        incompatible_name = mutex_item["incompatible_with"]
        try:
            incompatible_action = Action.objects.get(name=incompatible_name)
        except Action.DoesNotExist:
            raise InvalidStateError(
                code="REF_NOT_FOUND",
                message=f"Action '{incompatible_name}' (mutex.incompatible_with) introuvable.",
                details={"ref_name": incompatible_name}
            )
        ActionMutex.objects.create(
            action=obj,
            incompatible_with=incompatible_action,
            same_target=mutex_item.get("same_target", False),
            description=mutex_item.get("description", ""),
        )

    created = 1 if was_created else 0
    updated = 0 if was_created else 1
    return (created, updated, 0)
```

#### Export — FK ID to name resolution

```python
def _export_action_to_yaml(action: Action) -> dict:
    """Serialize a single Action to YAML-compatible dict."""
    metadata = {
        "name": action.name,
        "description": action.description or "",
        "category": action.category or "",
        "engine": action.engine or "",
        "platform": action.platform or "",
        "item_type": action.item_type or "action",
        "tags": [
            at.tag.name for at in ActionTag.objects.filter(action=action).select_related("tag")
        ],
    }

    spec = {
        "status": action.status,
        "requires_target": action.requires_target,
        "default_impact_level": action.default_impact_level or "medium",
    }

    # JSON CLOB fields → Python dicts for YAML serialization
    for field in ("parameters_schema", "execution_steps", "impact_rules",
                  "notification_config", "remediation_rules"):
        raw = getattr(action, field)
        if raw:
            spec[field] = json.loads(raw) if isinstance(raw, str) else raw
        else:
            spec[field] = None

    # Resolve FK IDs back to names
    if action.integration_id:
        try:
            spec["integration_ref"] = Integration.objects.get(id=action.integration_id).name
        except Integration.DoesNotExist:
            spec["integration_ref"] = f"<deleted:{action.integration_id}>"

    if action.business_rule_policy_id:
        try:
            spec["business_rule_policy_ref"] = BusinessRulePolicy.objects.get(
                id=action.business_rule_policy_id
            ).name
        except BusinessRulePolicy.DoesNotExist:
            spec["business_rule_policy_ref"] = f"<deleted:{action.business_rule_policy_id}>"

    # Mutex rules
    mutexes = ActionMutex.objects.filter(action=action).select_related("incompatible_with")
    if mutexes.exists():
        spec["mutex"] = [
            {
                "incompatible_with": m.incompatible_with.name,
                "same_target": m.same_target,
                "description": m.description or "",
            }
            for m in mutexes
        ]

    return {"apiVersion": "idp/v1", "kind": "Action", "metadata": metadata, "spec": spec}
```

---

### 3.8 Profiles (Upgrade Existing Implementation)

The existing `profiles/services_export_import.py` works but uses a flat format without
the `apiVersion/kind/metadata/spec` envelope. The upgrade:

1. **Keep backward compatibility** — accept both old flat format and new envelope format
2. **Add `action_names` support** — resolve action names to IDs (portable across envs)
3. **Add `is_approver`** — missing from current export
4. **Add `exclusion_patterns` and `filter_by_attribute`** — missing from current export

#### Updated YAML schema

```yaml
# profiles/dbops-team.yaml
apiVersion: idp/v1
kind: Profile
metadata:
  name: dbops-team
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
    # OR for list type:
    # type: list
    # action_names:                        # NEW — portable names instead of IDs
    #   - oracle-patching-quarterly
    #   - oracle-provisioning
  targets:
    type: pattern
    patterns:
      - "PROD-*"
    exclusion_patterns:                    # NEW
      - "PROD-CRITICAL-*"
    filter_by_attribute:                   # NEW
      engine_type: ["oracle"]
      zone: ["prod"]
  environments:
    - production
    - staging
```

#### action_names resolution

```python
def _resolve_action_names_to_ids(action_names: list[str]) -> list[int]:
    """
    Resolve a list of action names to IDs.
    Raises InvalidStateError if any name is not found.
    """
    ids = []
    missing = []
    for name in action_names:
        try:
            action = Action.objects.get(name=name)
            ids.append(action.id)
        except Action.DoesNotExist:
            missing.append(name)

    if missing:
        raise InvalidStateError(
            code="REF_NOT_FOUND",
            message=f"Actions introuvables : {', '.join(missing)}",
            details={"missing_actions": missing}
        )

    return ids
```

---

## 4. Reconciliation Engine (Sync Logic)

### Generic helper functions

These are shared by all entity import functions:

```python
# core/services_iac_utils.py

import hashlib
import io
import json
import yaml
from typing import Any
from django.utils import timezone
from core.exceptions import InvalidStateError


def parse_yaml(content: bytes) -> dict:
    """Parse YAML content, raising InvalidStateError on syntax errors."""
    try:
        parsed = yaml.safe_load(content.decode("utf-8"))
    except yaml.YAMLError as e:
        raise InvalidStateError(
            code="INVALID_YAML_SYNTAX",
            message="Syntaxe YAML invalide.",
            details={"error": str(e)},
        ) from e

    if parsed is None:
        raise InvalidStateError(
            code="EMPTY_YAML",
            message="Le fichier YAML est vide.",
        )

    return parsed


def validate_envelope(parsed: dict, expected_kind: str | None = None) -> None:
    """Validate the apiVersion/kind/metadata envelope."""
    # ... (full implementation shown in section 2 above)


def compute_yaml_hash(content: bytes) -> str:
    """Compute SHA-256 hash of YAML content for drift detection."""
    return hashlib.sha256(content).hexdigest()


def serialize_to_yaml(data: dict) -> bytes:
    """Serialize a dict to YAML bytes."""
    buf = io.StringIO()
    yaml.dump(data, buf, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return buf.getvalue().encode("utf-8")


def _apply_field_changes(obj: Any, defaults: dict) -> bool:
    """
    Apply field changes to a Django model instance.
    Returns True if any field was changed.
    """
    changed = False
    for field, value in defaults.items():
        current = getattr(obj, field, None)
        # Normalize JSON comparison
        if isinstance(current, str) and isinstance(value, str):
            try:
                if json.loads(current) == json.loads(value):
                    continue
            except (json.JSONDecodeError, TypeError):
                pass
        if current != value:
            setattr(obj, field, value)
            changed = True
    return changed


def update_sync_tracking(obj: Any, yaml_content: bytes) -> None:
    """
    Update last_synced_at and last_synced_hash on a model instance.
    Called after successful import/sync.
    """
    obj.last_synced_at = timezone.now()
    obj.last_synced_hash = compute_yaml_hash(yaml_content)
    obj.save(update_fields=["last_synced_at", "last_synced_hash"])
```

### Sync modes

| Mode | Behavior | Use case |
|------|----------|----------|
| `additive` (default) | Create new, update existing, leave unmentioned alone | Normal CI/CD sync |
| `full` | Create new, update existing, **soft-delete/disable** unmentioned | Clean slate / environment rebuild |

```python
def apply_full_mode_cleanup(model_class, yaml_names: set[str], lookup_field: str = "name"):
    """
    Soft-delete/disable entities in DB that are NOT in the YAML.
    Only called when mode=full.
    """
    db_names = set(model_class.objects.values_list(lookup_field, flat=True))
    orphans = db_names - yaml_names

    if not orphans:
        return 0

    # For Action: soft-delete (set status=disabled, deleted_at)
    if hasattr(model_class, "status"):
        return model_class.objects.filter(
            **{f"{lookup_field}__in": orphans}
        ).update(status="disabled")

    # For others: set is_active=0
    if hasattr(model_class, "is_active"):
        return model_class.objects.filter(
            **{f"{lookup_field}__in": orphans}
        ).update(is_active=0)

    return 0
```

---

## 5. Cross-Reference Resolution

### Dependency graph

```
                    ┌──────────────┐
                    │  RefEngine   │
                    │ RefCategory  │  ← no deps
                    │  Tags        │
                    │ FeatureFlags │
                    └──────┬───────┘
                           │
                    ┌──────▼───────────────┐
                    │ IntegrationTypeCat.   │  ← no deps (just reference)
                    └──────┬───────────────┘
                           │
                    ┌──────▼───────────────┐
                    │ Integrations         │  ← depends on: IntegrationTypeCat (type validation)
                    │                      │     + self (secret_service_ref)
                    └──────┬───────────────┘
                           │
                    ┌──────▼───────────────┐
                    │ BusinessRulePolicies  │  ← no deps
                    └──────┬───────────────┘
                           │
                    ┌──────▼───────────────┐
                    │ Actions               │  ← depends on: Integrations, Policies,
                    │                       │     RefEngine, RefCategory, Tags
                    └──────┬────────────────┘
                           │
                    ┌──────▼───────────────┐
                    │ Profiles              │  ← depends on: Actions (for list-type perms)
                    └──────────────────────┘
```

### Resolution error handling

All references use **names** (not IDs) for portability. When a reference can't be resolved:

| Severity | Behavior | Example |
|----------|----------|---------|
| **Hard error** | Reject the entire entity import | `integration_ref: "nonexistent"` |
| **Warning** | Import succeeds, log warning | `category: "UnknownCategory"` |
| **Auto-create** | Create the missing entity | `tags: ["new-tag"]` |

---

## 6. API Endpoints (Sync Views)

### URL registration pattern

Each entity type gets two endpoints: export (GET) and sync (POST).

```python
# Example: catalog/urls.py additions

from catalog.views import ActionExportView, ActionSyncView

urlpatterns += [
    path("admin/actions/export/yaml/", ActionExportView.as_view(), name="action-export-yaml"),
    path("admin/actions/sync/", ActionSyncView.as_view(), name="action-sync"),
]
```

### View implementation pattern

```python
# catalog/views.py additions

class ActionExportView(APIView):
    """GET /admin/actions/export/yaml/ — Export all actions as YAML."""
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        yaml_bytes = export_actions_yaml()
        response = HttpResponse(yaml_bytes, content_type="application/x-yaml")
        response["Content-Disposition"] = 'attachment; filename="actions.yaml"'
        return response


class ActionSyncView(APIView):
    """
    POST /admin/actions/sync/ — Import/sync actions from YAML.

    Accepts:
      - multipart/form-data with 'file' field (single file or multiple files)
      - application/x-yaml raw body (single YAML document)

    Query params:
      - mode=additive (default) or mode=full
    """
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes = [MultiPartParser, FileUploadParser]

    def post(self, request):
        mode = request.query_params.get("mode", "additive")

        # Accept file upload or raw YAML body
        if "file" in request.FILES:
            content = request.FILES["file"].read()
        else:
            content = request.body

        if not content:
            return Response(
                {"error": {"code": "EMPTY_BODY", "message": "Aucun contenu YAML fourni."}},
                status=400,
            )

        try:
            created, updated, unchanged = import_actions_yaml(content, user=request.user)
        except InvalidStateError as e:
            return Response(
                {"error": {"code": e.code, "message": e.message, "details": e.details}},
                status=400,
            )

        status_code = 201 if created > 0 and updated == 0 else 200
        return Response(
            {
                "data": {
                    "created": created,
                    "updated": updated,
                    "unchanged": unchanged,
                    "mode": mode,
                }
            },
            status=status_code,
        )
```

### Complete endpoint list

| Method | Endpoint | View class | Service function |
|--------|----------|-----------|-----------------|
| GET | `/admin/actions/export/yaml/` | `ActionExportView` | `export_actions_yaml()` |
| POST | `/admin/actions/sync/` | `ActionSyncView` | `import_actions_yaml()` |
| GET | `/admin/integrations/export/yaml/` | `IntegrationExportView` | `export_integrations_yaml()` |
| POST | `/admin/integrations/sync/` | `IntegrationSyncView` | `import_integrations_yaml()` |
| GET | `/admin/integration-types/export/yaml/` | `IntTypeExportView` | `export_integration_types_yaml()` |
| POST | `/admin/integration-types/sync/` | `IntTypeSyncView` | `import_integration_types_yaml()` |
| GET | `/admin/policies/export/yaml/` | `PolicyExportView` | `export_policies_yaml()` |
| POST | `/admin/policies/sync/` | `PolicySyncView` | `import_policies_yaml()` |
| GET | `/admin/reference/engines/export/yaml/` | `RefEngineExportView` | `export_reference_yaml("engines")` |
| POST | `/admin/reference/engines/sync/` | `RefEngineSyncView` | `import_reference_yaml(..., "engines")` |
| GET | `/admin/reference/categories/export/yaml/` | `RefCategoryExportView` | `export_reference_yaml("categories")` |
| POST | `/admin/reference/categories/sync/` | `RefCategorySyncView` | `import_reference_yaml(..., "categories")` |
| GET | `/admin/tags/export/yaml/` | `TagExportView` | `export_tags_yaml()` |
| POST | `/admin/tags/sync/` | `TagSyncView` | `import_tags_yaml()` |
| GET | `/admin/feature-flags/export/yaml/` | `FFExportView` | `export_feature_flags_yaml()` |
| POST | `/admin/feature-flags/sync/` | `FFSyncView` | `import_feature_flags_yaml()` |
| GET | `/admin/profiles/export/` | existing | existing |
| POST | `/admin/profiles/import/` | existing (upgrade) | existing (upgrade) |

---

## 7. Management Commands

### 7.1 `sync_config` — Full repository sync

```python
# core/management/commands/sync_config.py

class Command(BaseCommand):
    help = "Apply a full IDP config directory to the database."

    def add_arguments(self, parser):
        parser.add_argument("--config-dir", required=True, help="Path to idp-config/ directory")
        parser.add_argument("--dry-run", action="store_true", help="Validate only, no DB writes")
        parser.add_argument("--mode", choices=["additive", "full"], default="additive")
        parser.add_argument("--validate-only", action="store_true",
                            help="Schema + ref validation, no DB writes")

    def handle(self, **options):
        config_dir = Path(options["config_dir"])
        dry_run = options["dry_run"] or options["validate_only"]
        mode = options["mode"]

        # Processing order (dependency graph)
        SYNC_ORDER = [
            ("reference/engines.yaml",    "engines",    import_reference_yaml,    "engines"),
            ("reference/categories.yaml", "categories", import_reference_yaml,    "categories"),
            ("tags.yaml",                 "tags",       import_tags_yaml,          None),
            ("feature-flags.yaml",        "flags",      import_feature_flags_yaml, None),
            ("integration-types/",        "int-types",  import_integration_types_yaml, None),
            ("integrations/",             "integrations", import_integrations_yaml, None),
            ("policies/",                 "policies",   import_policies_yaml,      None),
            ("actions/",                  "actions",    import_actions_yaml,       None),
            ("profiles/",                 "profiles",   import_profiles_yaml,      None),
        ]

        total_results = {}

        for path_pattern, label, import_fn, extra_arg in SYNC_ORDER:
            full_path = config_dir / path_pattern

            if full_path.is_dir():
                # Read all .yaml/.yml files in directory
                files = sorted(full_path.glob("*.yaml")) + sorted(full_path.glob("*.yml"))
                for f in files:
                    content = f.read_bytes()
                    if dry_run:
                        # Validate only — parse + validate_envelope
                        parsed = parse_yaml(content)
                        validate_envelope(parsed)
                        self.stdout.write(f"  ✓ {f.name} — valid")
                    else:
                        args = [content]
                        if extra_arg:
                            args.append(extra_arg)
                        created, updated, unchanged = import_fn(*args)
                        self.stdout.write(
                            f"  {f.name}: created={created} updated={updated} unchanged={unchanged}"
                        )

            elif full_path.is_file():
                content = full_path.read_bytes()
                if dry_run:
                    parsed = parse_yaml(content)
                    validate_envelope(parsed)
                    self.stdout.write(f"  ✓ {path_pattern} — valid")
                else:
                    args = [content]
                    if extra_arg:
                        args.append(extra_arg)
                    created, updated, unchanged = import_fn(*args)
                    total_results[label] = (created, updated, unchanged)
                    self.stdout.write(
                        f"  {label}: created={created} updated={updated} unchanged={unchanged}"
                    )
            else:
                self.stdout.write(f"  ⚠ {path_pattern} — not found, skipping")

        # Summary
        self.stdout.write("\n--- Sync complete ---")
        for label, (c, u, uc) in total_results.items():
            self.stdout.write(f"  {label}: created={c} updated={u} unchanged={uc}")
```

**Usage examples:**

```bash
# Validate only (CI/CD pull request check)
python manage.py sync_config --config-dir ./idp-config/ --validate-only

# Dry run (see what would change without writing to DB)
python manage.py sync_config --config-dir ./idp-config/ --dry-run

# Apply changes (additive — default)
python manage.py sync_config --config-dir ./idp-config/

# Full sync (disable entities not in YAML)
python manage.py sync_config --config-dir ./idp-config/ --mode full
```

### 7.2 `detect_drift` — Drift detection

```python
# core/management/commands/detect_drift.py

class Command(BaseCommand):
    help = "Compare DB state against config repo and report drift."

    def add_arguments(self, parser):
        parser.add_argument("--config-dir", required=True)
        parser.add_argument("--format", choices=["text", "json"], default="text")

    def handle(self, **options):
        config_dir = Path(options["config_dir"])
        report = {"in_sync": [], "diverged": [], "missing_in_db": [], "missing_in_yaml": []}

        # For each entity type:
        # 1. Export DB state to in-memory YAML
        # 2. Load config directory YAML
        # 3. Compare by unique key

        # Example for actions:
        db_actions = {a.name: a for a in Action.objects.all()}
        yaml_actions = {}
        actions_dir = config_dir / "actions"
        if actions_dir.is_dir():
            for f in actions_dir.glob("*.yaml"):
                parsed = parse_yaml(f.read_bytes())
                name = parsed["metadata"]["name"]
                yaml_actions[name] = parsed

        all_names = set(db_actions.keys()) | set(yaml_actions.keys())
        for name in sorted(all_names):
            in_db = name in db_actions
            in_yaml = name in yaml_actions

            if in_db and in_yaml:
                # Compare fields — use last_synced_hash for quick check
                db_obj = db_actions[name]
                if db_obj.last_synced_hash:
                    yaml_hash = compute_yaml_hash(yaml_actions[name])
                    if db_obj.last_synced_hash == yaml_hash:
                        report["in_sync"].append(name)
                        continue
                # Field-by-field comparison
                report["diverged"].append({
                    "name": name,
                    "reason": "DB modified after last sync"
                               if db_obj.updated_at > db_obj.last_synced_at
                               else "YAML content changed",
                })
            elif in_db and not in_yaml:
                report["missing_in_yaml"].append(name)
            elif in_yaml and not in_db:
                report["missing_in_db"].append(name)

        # Output
        if options["format"] == "json":
            self.stdout.write(json.dumps(report, indent=2))
        else:
            self.stdout.write(f"In sync:          {len(report['in_sync'])}")
            self.stdout.write(f"Diverged:         {len(report['diverged'])}")
            self.stdout.write(f"Missing in DB:    {len(report['missing_in_db'])}")
            self.stdout.write(f"Missing in YAML:  {len(report['missing_in_yaml'])}")
            for item in report["diverged"]:
                self.stdout.write(f"  ⚠ {item['name']}: {item['reason']}")
```

---

## 8. Drift Detection

### How it works

```
 Config Repo (YAML)              Database
 ┌─────────────────┐            ┌─────────────────────────────────────┐
 │ action: deploy   │            │ action: deploy                      │
 │   engine: AAP    │    diff    │   engine: AAP                       │
 │   hash: abc123   │ ────────►  │   last_synced_hash: abc123          │
 │                  │            │   last_synced_at: 2026-03-07 10:00  │
 │                  │            │   updated_at:     2026-03-07 10:00  │ ← IN SYNC
 │                  │            │                                     │
 │                  │            │ action: backup                      │
 │                  │            │   last_synced_hash: def456          │
 │                  │            │   last_synced_at: 2026-03-07 10:00  │
 │                  │            │   updated_at:     2026-03-07 14:30  │ ← DIVERGED
 │                  │            │   (UI edit at 14:30)                │
 └─────────────────┘            └─────────────────────────────────────┘
```

**Detection logic:**

1. `last_synced_hash` matches YAML file hash → **in sync**
2. `updated_at > last_synced_at` → **diverged** (UI edit after sync)
3. Entity in DB with `last_synced_at = NULL` → **never synced** (created via UI)
4. Entity in YAML but not in DB → **missing in DB**

---

## 9. Database Migration

### New columns for sync tracking

```sql
-- V111__add_iac_sync_tracking_columns.sql
-- Applied via Flyway (Oracle-compatible DDL)

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
```

### Django model changes

```python
# Add to each model that supports IaC sync:

class Action(models.Model):
    # ... existing fields ...
    last_synced_at = models.DateTimeField(null=True, blank=True, db_column="LAST_SYNCED_AT")
    last_synced_hash = models.CharField(max_length=64, null=True, blank=True, db_column="LAST_SYNCED_HASH")
```

### Django migration

```python
# catalog/migrations/0014_add_iac_sync_tracking.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("catalog", "0013_remove_action_change_type_config_gate_config")]

    operations = [
        migrations.AddField(
            model_name="action",
            name="last_synced_at",
            field=models.DateTimeField(null=True, blank=True, db_column="LAST_SYNCED_AT"),
        ),
        migrations.AddField(
            model_name="action",
            name="last_synced_hash",
            field=models.CharField(max_length=64, null=True, blank=True, db_column="LAST_SYNCED_HASH"),
        ),
    ]

# Similar migrations for each app: integrations, profiles, reference, core
```

---

## 10. CI/CD Pipeline

### GitHub Actions workflow

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
    name: Validate YAML schemas
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install validation dependencies
        run: pip install pyyaml jsonschema
      - name: Validate YAML schemas
        run: |
          python manage.py sync_config \
            --config-dir ./idp-config/ \
            --validate-only

  dry-run-staging:
    name: Dry-run against staging
    if: github.event_name == 'pull_request'
    needs: validate
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - name: Dry-run sync
        env:
          IDP_API_URL: ${{ secrets.STAGING_API_URL }}
          IDP_API_TOKEN: ${{ secrets.STAGING_API_TOKEN }}
        run: |
          python scripts/apply_idp_config.py \
            --env staging \
            --dir idp-config/ \
            --dry-run

  apply-staging:
    name: Apply to staging
    if: github.event_name == 'push'
    needs: validate
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - name: Apply configuration
        env:
          IDP_API_URL: ${{ secrets.STAGING_API_URL }}
          IDP_API_TOKEN: ${{ secrets.STAGING_API_TOKEN }}
        run: |
          python scripts/apply_idp_config.py \
            --env staging \
            --dir idp-config/

  apply-production:
    name: Apply to production
    if: github.event_name == 'push'
    needs: apply-staging
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval in GitHub
    steps:
      - uses: actions/checkout@v4
      - name: Apply configuration
        env:
          IDP_API_URL: ${{ secrets.PROD_API_URL }}
          IDP_API_TOKEN: ${{ secrets.PROD_API_TOKEN }}
        run: |
          python scripts/apply_idp_config.py \
            --env production \
            --dir idp-config/
```

### Apply script

```python
# scripts/apply_idp_config.py
"""
CLI script to apply IDP config to a remote environment via API.
Called by CI/CD pipeline.

Usage:
  python scripts/apply_idp_config.py --env staging --dir idp-config/
  python scripts/apply_idp_config.py --env production --dir idp-config/ --dry-run
"""
import argparse
import os
import sys
from pathlib import Path
import requests

SYNC_ORDER = [
    ("reference/engines.yaml",    "/api/v1/admin/reference/engines/sync/"),
    ("reference/categories.yaml", "/api/v1/admin/reference/categories/sync/"),
    ("tags.yaml",                 "/api/v1/admin/tags/sync/"),
    ("feature-flags.yaml",        "/api/v1/admin/feature-flags/sync/"),
    ("integration-types/",        "/api/v1/admin/integration-types/sync/"),
    ("integrations/",             "/api/v1/admin/integrations/sync/"),
    ("policies/",                 "/api/v1/admin/policies/sync/"),
    ("actions/",                  "/api/v1/admin/actions/sync/"),
    ("profiles/",                 "/api/v1/admin/profiles/import/"),
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True)
    parser.add_argument("--dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_url = os.environ["IDP_API_URL"]
    api_token = os.environ["IDP_API_TOKEN"]
    config_dir = Path(args.dir)
    headers = {"Authorization": f"Bearer {api_token}"}

    errors = []

    for path_pattern, endpoint in SYNC_ORDER:
        full_path = config_dir / path_pattern

        if full_path.is_dir():
            files = sorted(full_path.glob("*.yaml")) + sorted(full_path.glob("*.yml"))
            for f in files:
                resp = requests.post(
                    f"{api_url}{endpoint}",
                    files={"file": (f.name, f.read_bytes(), "application/x-yaml")},
                    headers=headers,
                )
                if resp.status_code >= 400:
                    errors.append(f"{f.name}: {resp.status_code} {resp.text}")
                    print(f"  ✗ {f.name}: {resp.status_code}")
                else:
                    data = resp.json().get("data", {})
                    print(f"  ✓ {f.name}: created={data.get('created', 0)} "
                          f"updated={data.get('updated', 0)} "
                          f"unchanged={data.get('unchanged', 0)}")

        elif full_path.is_file():
            resp = requests.post(
                f"{api_url}{endpoint}",
                files={"file": (full_path.name, full_path.read_bytes(), "application/x-yaml")},
                headers=headers,
            )
            if resp.status_code >= 400:
                errors.append(f"{path_pattern}: {resp.status_code} {resp.text}")
            else:
                data = resp.json().get("data", {})
                print(f"  ✓ {path_pattern}: created={data.get('created', 0)} "
                      f"updated={data.get('updated', 0)}")

    if errors:
        print(f"\n{len(errors)} error(s):")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)

    print("\nSync complete.")

if __name__ == "__main__":
    main()
```

---

## 11. Frontend Changes

### New admin tab: "Config Sync"

Add a new tab to the admin panel showing sync status and controls.

```typescript
// components/admin/ConfigSyncPanel.tsx

interface SyncStatus {
  entity_type: string;
  total: number;
  in_sync: number;
  diverged: number;
  missing_in_yaml: number;
  last_synced_at: string | null;
}
```

### Drift badge on entity tables

Each admin table (actions, integrations, profiles) shows a drift indicator:

```typescript
// components/admin/DriftBadge.tsx

interface DriftBadgeProps {
  lastSyncedAt: string | null;
  updatedAt: string;
}

function DriftBadge({ lastSyncedAt, updatedAt }: DriftBadgeProps) {
  if (!lastSyncedAt) {
    return <Tag color="blue">UI only</Tag>;  // Never synced from YAML
  }
  if (new Date(updatedAt) > new Date(lastSyncedAt)) {
    return (
      <Tooltip title="Modifié localement — pas synchronisé avec le dépôt de config">
        <Tag color="orange" icon={<WarningOutlined />}>Divergé</Tag>
      </Tooltip>
    );
  }
  return <Tag color="green">Synchronisé</Tag>;
}
```

### Export single entity button

On each entity detail view, add a button to export that single entity as YAML for
copy-paste into the config repo.

```typescript
// hooks/useEntityExport.ts

function useEntityExport(entityType: string, entityId: number) {
  const exportToYaml = async () => {
    const blob = await apiFetchBlob(
      `/admin/${entityType}/${entityId}/export/yaml/`
    );
    downloadBlob(blob, `${entityType}-${entityId}.yaml`);
  };
  return { exportToYaml };
}
```

---

## 12. Testing Strategy

### Unit tests per entity type

Each export/import service gets a test file:

```python
# catalog/tests/test_services_export_import.py

class TestActionExport(TestCase):
    def setUp(self):
        self.integration = Integration.objects.create(name="aap-prod", type="aap", ...)
        self.action = Action.objects.create(
            name="test-action", integration=self.integration, status="published", ...
        )

    def test_export_produces_valid_yaml(self):
        yaml_bytes = export_actions_yaml()
        parsed = yaml.safe_load(yaml_bytes)
        self.assertEqual(parsed["apiVersion"], "idp/v1")
        self.assertEqual(parsed["kind"], "Action")

    def test_export_resolves_fk_to_names(self):
        yaml_bytes = export_actions_yaml()
        parsed = yaml.safe_load(yaml_bytes)
        self.assertEqual(parsed["spec"]["integration_ref"], "aap-prod")


class TestActionImport(TestCase):
    def setUp(self):
        # Create dependencies
        Integration.objects.create(name="aap-prod", type="aap", ...)
        BusinessRulePolicy.objects.create(name="my-policy", ...)

    def test_import_creates_new_action(self):
        content = b"""
apiVersion: idp/v1
kind: Action
metadata:
  name: new-action
  item_type: action
spec:
  status: draft
  integration_ref: aap-prod
"""
        created, updated, unchanged = import_actions_yaml(content)
        self.assertEqual(created, 1)
        self.assertTrue(Action.objects.filter(name="new-action").exists())

    def test_import_updates_existing_action(self):
        Action.objects.create(name="existing", status="draft", ...)
        content = b"""
apiVersion: idp/v1
kind: Action
metadata:
  name: existing
spec:
  status: published
"""
        created, updated, unchanged = import_actions_yaml(content)
        self.assertEqual(updated, 1)
        self.assertEqual(Action.objects.get(name="existing").status, "published")

    def test_import_rejects_invalid_ref(self):
        content = b"""
apiVersion: idp/v1
kind: Action
metadata:
  name: bad-ref
spec:
  integration_ref: nonexistent
"""
        with self.assertRaises(InvalidStateError) as ctx:
            import_actions_yaml(content)
        self.assertEqual(ctx.exception.code, "REF_NOT_FOUND")

    def test_roundtrip_export_import(self):
        """Export → import should be idempotent (no changes on second import)."""
        yaml_bytes = export_actions_yaml()
        c, u, uc = import_actions_yaml(yaml_bytes)
        self.assertEqual(c, 0)
        self.assertEqual(u, 0)  # No changes
```

### Integration tests

```python
class TestSyncConfigCommand(TestCase):
    def test_full_sync_from_directory(self):
        """Create a temp config dir with all entity types and sync."""
        config_dir = self._create_test_config()
        call_command("sync_config", config_dir=str(config_dir))
        self.assertTrue(RefEngine.objects.filter(code="Oracle").exists())
        self.assertTrue(Action.objects.filter(name="test-action").exists())

    def test_dry_run_makes_no_changes(self):
        config_dir = self._create_test_config()
        call_command("sync_config", config_dir=str(config_dir), dry_run=True)
        self.assertEqual(Action.objects.count(), 0)

    def test_validate_only_catches_bad_refs(self):
        config_dir = self._create_config_with_bad_refs()
        with self.assertRaises(CommandError):
            call_command("sync_config", config_dir=str(config_dir), validate_only=True)
```

---

## 13. Phased Rollout Plan

### Phase 1: Export/import services (Foundation)

**Start with simplest, end with most complex:**

| Step | Entity | File to create | Complexity |
|------|--------|---------------|------------|
| 1.1 | Reference data | `reference/services_export_import.py` | Low |
| 1.2 | Tags | `catalog/services_export_import_tags.py` | Low |
| 1.3 | Feature flags | `core/services_export_import.py` | Low |
| 1.4 | Integration types | `integrations/services_export_import_types.py` | Medium (nested children) |
| 1.5 | Integrations | `integrations/services_export_import.py` | Medium (self-ref FK) |
| 1.6 | Business rule policies | `catalog/services_export_import_policies.py` | Low |
| 1.7 | Actions | `catalog/services_export_import.py` | High (multiple FKs, tags, mutex) |
| 1.8 | Profiles (upgrade) | `profiles/services_export_import.py` (modify) | Medium (add action_names) |
| 1.9 | Shared utils | `core/services_iac_utils.py` | Medium |

**Deliverable:** All entity types can round-trip (export → import → export produces identical YAML).

### Phase 2: Sync API endpoints

| Step | What | Files |
|------|------|-------|
| 2.1 | Create export/sync view pairs | 8 new view classes across 4 apps |
| 2.2 | Register URLs | Modify urls.py in each app |
| 2.3 | Add OpenAPI schema decorators | `@extend_schema` on each view |
| 2.4 | Add API tests | 8 new test files |

**Deliverable:** All sync endpoints callable via `curl` or API client.

### Phase 3: Management commands

| Step | What |
|------|------|
| 3.1 | `sync_config` command with `--dry-run` and `--validate-only` |
| 3.2 | `detect_drift` command with text and JSON output |
| 3.3 | Command tests |

**Deliverable:** Full repo can be synced from CLI.

### Phase 4: Database migration + drift tracking

| Step | What |
|------|------|
| 4.1 | Flyway SQL migration for sync tracking columns |
| 4.2 | Django model field additions + Django migrations |
| 4.3 | Update import services to set `last_synced_at` / `last_synced_hash` |

**Deliverable:** DB tracks when each entity was last synced.

### Phase 5: CI/CD pipeline

| Step | What |
|------|------|
| 5.1 | `scripts/apply_idp_config.py` CLI |
| 5.2 | GitHub Actions workflow (validate → staging → production) |
| 5.3 | Seed config repo with initial YAML exported from current DB |

**Deliverable:** Merge to main auto-syncs configuration.

### Phase 6: Frontend drift indicators

| Step | What |
|------|------|
| 6.1 | `DriftBadge` component |
| 6.2 | Add badge to all admin entity tables |
| 6.3 | Single-entity export button on detail views |
| 6.4 | Config Sync dashboard widget |

**Deliverable:** Admins can see which entities are in sync, diverged, or UI-only.

---

## Appendix A: File Map (New Files)

```
django_backend/
├── core/
│   ├── services_iac_utils.py              # Shared YAML/hash/envelope utilities
│   ├── services_export_import.py          # FeatureFlag export/import
│   └── management/commands/
│       ├── sync_config.py                 # Full repo sync command
│       └── detect_drift.py               # Drift detection command
├── catalog/
│   ├── services_export_import.py          # Action export/import
│   ├── services_export_import_tags.py     # Tag export/import
│   └── services_export_import_policies.py # BusinessRulePolicy export/import
├── integrations/
│   ├── services_export_import.py          # Integration export/import
│   └── services_export_import_types.py    # IntegrationTypeCatalogue export/import
├── reference/
│   └── services_export_import.py          # RefEngine/RefCategory export/import
└── profiles/
    └── services_export_import.py          # MODIFY existing (add envelope + action_names)

frontend/src/
├── components/admin/
│   ├── ConfigSyncPanel.tsx                # New admin tab
│   └── DriftBadge.tsx                     # Sync status badge
├── hooks/
│   └── useEntityExport.ts                 # Single-entity YAML export
└── services/
    └── config_sync_service.ts             # API calls for sync endpoints

scripts/
└── apply_idp_config.py                    # CI/CD apply script

.github/workflows/
└── sync-idp-config.yml                    # CI/CD pipeline
```

## Appendix B: Audit Action Types (New)

Add these to `AuditActionType` in `core/models.py`:

```python
CONFIG_SYNC_REFERENCE = "CONFIG_SYNC_REFERENCE"
CONFIG_SYNC_TAGS = "CONFIG_SYNC_TAGS"
CONFIG_SYNC_FEATURE_FLAGS = "CONFIG_SYNC_FEATURE_FLAGS"
CONFIG_SYNC_INTEGRATION_TYPES = "CONFIG_SYNC_INTEGRATION_TYPES"
CONFIG_SYNC_INTEGRATIONS = "CONFIG_SYNC_INTEGRATIONS"
CONFIG_SYNC_POLICIES = "CONFIG_SYNC_POLICIES"
CONFIG_SYNC_ACTIONS = "CONFIG_SYNC_ACTIONS"
CONFIG_SYNC_PROFILES = "CONFIG_SYNC_PROFILES"
DRIFT_DETECTED = "DRIFT_DETECTED"
```

## Appendix C: Error Codes

| Code | HTTP | When |
|------|------|------|
| `INVALID_YAML_SYNTAX` | 400 | YAML parsing fails |
| `EMPTY_YAML` | 400 | Empty file |
| `INVALID_API_VERSION` | 400 | `apiVersion` not `idp/v1` |
| `INVALID_KIND` | 400 | Unknown `kind` value |
| `INVALID_METADATA` | 400 | Missing or malformed `metadata` |
| `MISSING_NAME` | 400 | `metadata.name` empty |
| `INVALID_YAML_SCHEMA` | 400 | Entity-specific validation failure |
| `TYPE_MISMATCH` | 400 | metadata.type doesn't match expected |
| `REF_NOT_FOUND` | 400 | Referenced entity doesn't exist |
| `DUPLICATE_NAME` | 400 | Same name appears twice in YAML |

## Appendix D: Security Checklist

- [ ] `credential_ref` values are **never** stored in YAML — only Vault paths
- [ ] Export masks credential paths (last segment replaced with `***`)
- [ ] All sync/import endpoints require admin role (`IsAdminUser` permission)
- [ ] Schema validation runs **before** any DB writes
- [ ] Each entity type import is wrapped in `transaction.atomic()`
- [ ] All sync operations log to `AUDIT_LOG` with `source='config_sync'`
- [ ] CI/CD API token has scoped `config_sync` permission, not full admin
- [ ] YAML files are parsed with `yaml.safe_load()` (prevents code execution)
- [ ] `--mode full` requires explicit opt-in (never deletes by default)
