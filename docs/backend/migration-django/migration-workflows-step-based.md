# Guide de migration — Workflows vers le format step-based

**Version :** 2.0.0 — Story 57.18 (ADR-007, Phase finale)
**Date :** 2026-03-03
**Statut :** Migration terminée

---

## Section 1 : Contexte ADR-007

L'ADR-007 (_Workflow Step-Based Change Management_) a introduit un format de définition de workflows
plus riche et plus flexible que le format historique basé sur `change_type_config` et `gate_config`.

### Migration terminée (Story 57.18)

Les champs `change_type_config` et `gate_config` ont été **supprimés** du modèle `Action` (Story 57.18).
Les workflows sont désormais définis uniquement via `execution_steps`.

| Phase | Story | Action | Statut |
|-------|-------|--------|--------|
| Phase 4.1 | 57.11 | Wrapper backward-compat pour `change_type_config` | Terminé |
| Phase 4.2 | 57.12 | Annotations de dépréciation | Terminé |
| Phase 5 | 57.13–57.17 | Fonctionnalités step-based complémentaires | Terminé |
| **Phase finale** | **57.18** | **Suppression effective des champs et du wrapper** | **Terminé** |

---

## Section 2 : Format step-based

Le champ `Action.execution_steps` (tableau JSON) permet de définir des workflows multi-étapes avec :
- **Types de step :** `platform`, `service_call`, `http_request`, `evaluation`, `gate`, `vault`, `servicenow`, `prerequisite`, `verification`, `schedule_execution`
- **Branchement conditionnel :** `on_success_step_id`, `on_error_step_id`
- **Conditions d'environnement :** `condition.environment_in`
- **Gates configurables :** `maintenance_window`, `approval` avec timeout
- **Output mapping :** interpolation Jinja2 entre steps (`{{ steps['create-change']['change_number'] }}`)

### Exemple : Action avec changement ServiceNow

```json
{
  "item_type": "workflow",
  "execution_steps": [
    {
      "step_id": "create-change",
      "order": 1,
      "name": "Créer le changement ServiceNow",
      "step_type": "service_call",
      "integration_type": "servicenow",
      "operation": "create_change",
      "input_mapping": {
        "short_description": "IDP Portal — <nom_de_l_action>",
        "change_type": "standard",
        "category": "database",
        "assignment_group": "DBA-Team"
      },
      "output_mapping": {
        "change_number": "$.number",
        "sys_id": "$.sys_id"
      },
      "on_success_step_id": "execute-action"
    },
    {
      "step_id": "execute-action",
      "order": 2,
      "name": "Exécuter l'action plateforme",
      "step_type": "platform",
      "referenced_action_id": "<ID_ACTION>",
      "on_success_step_id": "close-change"
    },
    {
      "step_id": "close-change",
      "order": 3,
      "name": "Fermer le changement ServiceNow",
      "step_type": "service_call",
      "integration_type": "servicenow",
      "operation": "close_change",
      "input_mapping": {
        "change_id": "{{ steps['create-change']['change_number'] }}"
      }
    }
  ]
}
```

---

## Section 3 : Exemple complet — Oracle Patching

Cet exemple illustre un workflow de patching Oracle complet avec :
- Discovery via HTTP
- Changement ServiceNow conditionnel (prod/pre-prod seulement)
- Validation santé pre-patch
- Attente fenêtre de maintenance (prod seulement)
- Application du patch
- Fermeture du changement

> Source : ADR-007 — `docs/decisions/adr-007-workflow-step-based-change-management.md`

```json
{
  "item_type": "workflow",
  "execution_steps": [
    {
      "step_id": "discovery",
      "order": 1,
      "name": "Query inventory",
      "step_type": "http_request",
      "config": {
        "url": "https://inventory.corp/api/v1/patch-scope",
        "method": "GET",
        "headers": { "Accept": "application/json" },
        "params": { "engine": "oracle", "patch_eligible": true }
      },
      "output_mapping": {
        "databases": "$.data.databases",
        "patch_number": "$.data.latest_patch.number",
        "cmdb_ci": "$.data.cmdb_ci"
      }
    },
    {
      "step_id": "create-change",
      "order": 2,
      "name": "Create ServiceNow Change",
      "step_type": "service_call",
      "integration_type": "servicenow",
      "operation": "create_change",
      "condition": {
        "environment_in": ["production", "pre-production"]
      },
      "input_mapping": {
        "short_description": "Patching {{ steps.discovery.patch_number }} — {{ steps.discovery.databases | length }} databases",
        "cmdb_ci": "{{ steps.discovery.cmdb_ci }}",
        "u_patch_number": "{{ steps.discovery.patch_number }}",
        "u_impacted_databases": "{{ steps.discovery.databases | join(', ') }}"
      },
      "output_mapping": {
        "change_number": "$.number",
        "sys_id": "$.sys_id"
      }
    },
    {
      "step_id": "pre-check",
      "order": 3,
      "name": "Pre-patch validation",
      "step_type": "platform",
      "referenced_action_id": 100,
      "input_mapping": {
        "extra_vars": {
          "databases": "{{ steps.discovery.databases }}"
        }
      },
      "output_mapping": {
        "health_report": "$.artifacts.health_report"
      }
    },
    {
      "step_id": "evaluate-health",
      "order": 4,
      "name": "Check pre-patch health",
      "step_type": "evaluation",
      "input_mapping": {
        "artifact": "{{ steps['pre-check']['health_report'] }}"
      },
      "policy_id": 7,
      "on_success_step_id": "wait-window",
      "on_error_step_id": "abort-change"
    },
    {
      "step_id": "wait-window",
      "order": 5,
      "name": "Wait for maintenance window",
      "step_type": "gate",
      "gate_type": "maintenance_window",
      "condition": {
        "environment_in": ["production"]
      },
      "timeout_hours": 72,
      "on_timeout": "FAIL",
      "on_success_step_id": "apply-patch",
      "on_error_step_id": "abort-change"
    },
    {
      "step_id": "apply-patch",
      "order": 6,
      "name": "Apply patch",
      "step_type": "platform",
      "referenced_action_id": 200,
      "input_mapping": {
        "extra_vars": {
          "change_id": "{{ steps['create-change']['change_number'] }}",
          "databases": "{{ steps.discovery.databases }}",
          "patch_number": "{{ steps.discovery.patch_number }}"
        }
      }
    },
    {
      "step_id": "close-change",
      "order": 7,
      "name": "Close change",
      "step_type": "service_call",
      "integration_type": "servicenow",
      "operation": "close_change",
      "condition": {
        "environment_in": ["production", "pre-production"]
      },
      "input_mapping": {
        "change_id": "{{ steps['create-change']['change_number'] }}"
      },
      "on_success_step_id": null
    },
    {
      "step_id": "abort-change",
      "name": "Abort — cancel change",
      "step_type": "service_call",
      "integration_type": "servicenow",
      "operation": "cancel_change",
      "condition": {
        "environment_in": ["production", "pre-production"]
      },
      "input_mapping": {
        "change_id": "{{ steps['create-change']['change_number'] }}"
      }
    }
  ]
}
```

---

## Références

- [ADR-007](../decisions/adr-007-workflow-step-based-change-management.md) — Architecture Decision Record complet
- `catalog/models.py` — Modèle `Action` avec `execution_steps`
- `executions/container_workflow_runtime.py` — Runtime d'exécution step-based
