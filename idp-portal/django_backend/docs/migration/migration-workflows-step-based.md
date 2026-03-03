# Guide de migration — Workflows vers le format step-based

**Version :** 1.0.0 — Story 57.12 (ADR-007, Phase 4.2)
**Date :** 2026-03-02
**Statut :** Actif

---

## Section 1 : Contexte ADR-007 — Pourquoi migrer

L'ADR-007 (_Workflow Step-Based Change Management_) introduit un format de définition de workflows
plus riche et plus flexible que le format historique basé sur `change_type_config` et `gate_config`.

### Problèmes du format historique

| Problème | Impact |
|----------|--------|
| `change_type_config` couplé à ServiceNow | Impossible d'utiliser d'autres intégrations (Jira, PagerDuty) |
| `gate_config` monolithique | Pas de gates conditionnels ni de timeout configurable |
| Logique d'approbation sur `Execution` | Pas de traçabilité par étape (`Execution.approved_by/at`) |
| Pas de branchement conditionnel | Impossible de gérer `on_success_step_id` / `on_error_step_id` |

### Solution ADR-007

Le champ `Action.execution_steps` (tableau JSON) permet de définir des workflows multi-étapes avec :
- **Types de step :** `platform`, `service_call`, `http_request`, `evaluation`, `gate`, `vault`, `servicenow`, `prerequisite`, `verification`
- **Branchement conditionnel :** `on_success_step_id`, `on_error_step_id`
- **Conditions d'environnement :** `condition.environment_in`
- **Gates configurables :** `maintenance_window`, `approval` avec timeout
- **Output mapping :** interpolation Jinja2 entre steps (`{{ steps['create-change']['change_number'] }}`)

---

## Section 2 : Champs dépréciés et leur équivalent step-based

### Sur le modèle `Action`

| Champ déprécié | Déprécié depuis | Équivalent step-based | Notes |
|---|---|---|---|
| `change_type_config` | ADR-007 / Story 57.12 | `execution_steps` avec step `service_call` ServiceNow | Wrapper auto Story 57.11 |
| `gate_config` | ADR-007 / Story 57.12 | `execution_steps` avec step `gate` | Plus de `gate_config` dans le runtime |

### Sur le modèle `Execution`

| Champ déprécié | Déprécié depuis | Équivalent step-based | Notes |
|---|---|---|---|
| `approved_by` | ADR-007 / Story 57.1 | `ExecutionStep.approved_by` | Donnée historique conservée en DB |
| `approved_at` | ADR-007 / Story 57.1 | `ExecutionStep.approved_at` | Donnée historique conservée en DB |
| `approval_comment` | ADR-007 / Story 57.1 | `ExecutionStep.approval_comment` | Donnée historique conservée en DB |

> **Note :** Les colonnes Oracle restent présentes dans la base de données. La dépréciation est
> uniquement au niveau code Python. Ne plus écrire dans ces champs pour de nouveaux développements.

---

## Section 3 : Migration d'une "action simple avec change_type_config"

### Avant (format historique)

Une action avec changement ServiceNow standard était définie avec `change_type_config` :

```json
{
  "item_type": "action",
  "change_type_config": {
    "model": "standard",
    "category": "database",
    "assignment_group": "DBA-Team"
  }
}
```

La logique ServiceNow était gérée implicitement par le moteur d'exécution.

### Après (format step-based)

La même action est maintenant définie explicitement avec `execution_steps` :

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

### Mécanisme transitoire (Story 57.11)

> **Rétrocompatibilité :** Si une action possède encore `change_type_config` sans `execution_steps`,
> le wrapper `_build_change_wrapper_steps()` dans `ContainerWorkflowRuntime` génère automatiquement
> les steps ServiceNow équivalents. Ce mécanisme est temporaire et sera retiré post-Story 57.17.

---

## Section 4 : Exemple complet — Oracle Patching

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

## Section 5 : Exemple Terraform avec évaluation conditionnelle

Cet exemple illustre un workflow Terraform avec :
- Plan Terraform
- Évaluation automatique du plan (Business Rule Policy)
- Gate d'approbation DBA si l'évaluation échoue
- Création changement ServiceNow (prod seulement)
- Apply Terraform
- Fermeture changement

> Source : ADR-007 — `docs/decisions/adr-007-workflow-step-based-change-management.md`

```json
{
  "item_type": "workflow",
  "execution_steps": [
    {
      "step_id": "tf-plan",
      "order": 1,
      "name": "Terraform Plan",
      "step_type": "platform",
      "referenced_action_id": 300,
      "output_mapping": {
        "plan": "$.artifacts.plan_json",
        "resource_count": "$.artifacts.resource_count"
      }
    },
    {
      "step_id": "check-plan",
      "order": 2,
      "name": "Analyze Plan",
      "step_type": "evaluation",
      "input_mapping": {
        "artifact": "{{ steps['tf-plan']['plan'] }}"
      },
      "policy_id": 5,
      "on_success_step_id": "create-change",
      "on_error_step_id": "request-approval"
    },
    {
      "step_id": "request-approval",
      "order": 3,
      "name": "DBA Approval Required",
      "step_type": "gate",
      "gate_type": "approval",
      "timeout_hours": 48,
      "on_timeout": "FAIL",
      "context_from": ["tf-plan", "check-plan"],
      "on_success_step_id": "create-change",
      "on_error_step_id": null
    },
    {
      "step_id": "create-change",
      "order": 4,
      "name": "Create ServiceNow Change",
      "step_type": "service_call",
      "integration_type": "servicenow",
      "operation": "create_change",
      "condition": {
        "environment_in": ["production"]
      },
      "input_mapping": {
        "short_description": "Terraform apply — {{ steps['tf-plan']['resource_count'] }} resources"
      },
      "output_mapping": {
        "change_number": "$.number"
      }
    },
    {
      "step_id": "tf-apply",
      "order": 5,
      "name": "Terraform Apply",
      "step_type": "platform",
      "referenced_action_id": 301,
      "input_mapping": {
        "extra_vars": {
          "change_id": "{{ steps['create-change']['change_number'] }}"
        }
      }
    },
    {
      "step_id": "close-change",
      "order": 6,
      "name": "Close Change",
      "step_type": "service_call",
      "integration_type": "servicenow",
      "operation": "close_change",
      "condition": {
        "environment_in": ["production"]
      },
      "input_mapping": {
        "change_id": "{{ steps['create-change']['change_number'] }}"
      }
    }
  ]
}
```

---

## Section 6 : Calendrier prévisionnel de suppression

| Phase | Story | Action | Horizon |
|-------|-------|--------|---------|
| Phase 4.1 | 57.11 | Wrapper backward-compat pour `change_type_config` | Terminé |
| Phase 4.2 | **57.12** | **Annotations de dépréciation (cette story)** | **Terminé** |
| Phase 5 | 57.13–57.16 | Fonctionnalités step-based complémentaires | À planifier |
| Phase finale | 57.17+ | Suppression effective des champs dépréciés | Post-57.17 |

### Prérequis avant suppression (post-57.17)

Avant de pouvoir supprimer les champs dépréciés, les conditions suivantes doivent être remplies :

1. **Toutes les actions** dans la base de données doivent avoir `execution_steps` défini
   (aucune action ne doit avoir uniquement `change_type_config`)
2. **Aucun client API** ne doit écrire dans `Execution.approved_by/at/approval_comment`
3. **Migration de données** : traitement des `Execution` historiques avec `approved_by` non null
4. **Retrait du wrapper 57.11** : `_build_change_wrapper_steps()` peut être supprimé

### Vérification de l'état de migration

Pour vérifier combien d'actions utilisent encore l'ancien format :

```python
from catalog.models import Action

# Actions avec change_type_config mais sans execution_steps
legacy_actions = Action.objects.filter(
    change_type_config__isnull=False,
    execution_steps__isnull=True
)
print(f"Actions legacy à migrer : {legacy_actions.count()}")
```

---

## Références

- [ADR-007](../decisions/adr-007-workflow-step-based-change-management.md) — Architecture Decision Record complet
- [Story 57.11](../../_bmad-output/implementation-artifacts/57-11-wrapper-automatique-backward-compatibility.md) — Wrapper backward-compat
- [Story 57.1](../../_bmad-output/implementation-artifacts/57-1-migration-champs-approbation-execution-step.md) — Migration champs approbation vers ExecutionStep (voir dossier implementation-artifacts si nom différent)
- `executions/models.py` — Modèle `Execution` et propriété `is_pending_approval`
- `executions/container_workflow_runtime.py` — `_build_change_wrapper_steps()`
