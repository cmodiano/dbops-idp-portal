# Matrice de Compatibilité — Extensibilité Gates, Services, Plateformes

> **Story 82.1 — Phase 0 : Stabilisation et réduction de dérive**
> Document de référence pour les Stories 82.2 à 82.9.
> Document complémentaire : [platform-canonical-codes.md](platform-canonical-codes.md)

---

## 1. Table Gate Types

État d'implémentation des types de gate à travers le système.

| Gate Type | Déclaré valide (`VALID_GATE_CONDITION_TYPES`) | Géré par GateHandler | Évalué par GateEvaluator | Affiché en frontend (`GateStepConfig.tsx`) | Statut |
|---|---|---|---|---|---|
| `maintenance_window` | ✅ | ✅ (`gate_type: maintenance_window`) | ✅ (vérifie inventaire) | ✅ (`Fenêtre de maintenance`) | ✅ **Implémenté** |
| `approval_granted` | ✅ | ✅ (via alias `gate_type: approval`) | ✅ (attend `POST /approve/`) | ✅ (label `Approbation manuelle`, value `approval`) | ✅ **Implémenté** |
| `time_window` | ❌ (déplacé dans `FUTURE_GATE_TYPES` — Story 82.1) | ❌ | ❌ (case `_` → satisfied=False) | ❌ | 🔮 **Futur — non implémenté** |
| `target_state` | ❌ (déplacé dans `FUTURE_GATE_TYPES` — Story 82.1) | ❌ | ❌ (case `_` → satisfied=False) | ❌ | 🔮 **Futur — non implémenté** |

### Notes

- **Avant Story 82.1** : `time_window` et `target_state` étaient dans `VALID_GATE_CONDITION_TYPES` mais non gérés → gate silencieusement jamais satisfaite sans erreur explicite.
- **Après Story 82.1** : Ces types sont dans `FUTURE_GATE_TYPES` (constante documentée) et retirés de `VALID_GATE_CONDITION_TYPES` — toute tentative de les utiliser échouera la validation catalog dès la création.
- **Alias frontend** : Le frontend utilise `approval` comme valeur (pas `approval_granted`) — le `GateHandler.condition_type_map` fait la traduction.

---

## 2. Table Plateformes

État d'implémentation des plateformes à travers le système.

| Code canonique | Alias backend | Adapter registré | Health check | Alias frontend (connector_type) | ActionPlatform (BD) | Queue Celery | Kwargs runtime requis |
|---|---|---|---|---|---|---|---|
| `aap` | — | ✅ `aap` | ✅ | `aap` | `AAP` | `aap` | — |
| `tower` | `tower` → `aap` (PLATFORM_ALIAS) | ✅ `tower` | ✅ | `aap` | `Tower` | `aap` | `ssl_verify` (optionnel) |
| `azure_devops` | `azuredevops` (_ADAPTER_TYPE_ALIASES) | ✅ `azure_devops` | ✅ | `azuredevops` | `Azure DevOps` | `azure` | — |
| `github_actions` | — | ✅ `github_actions` | ✅ | `github_actions` | `GitHub Actions` | `github` | `owner`, `repo` (requis) |
| `terraform_cloud` | `terraform` (PLATFORM_ALIAS + _ADAPTER_TYPE_ALIASES) | ✅ `terraform_cloud` | ✅ | `terraform` / `terraform_cloud` | `Terraform` | `terraform` | `organization` (requis) |

### Détail des dérives plateformes

| Dérive | Description | Impact | Résolution prévue |
|---|---|---|---|
| `azuredevops` vs `azure_devops` | `IntegrationType` contient les deux formes | Duplication dans le modèle | Story 82.3 — normalisation aliases |
| Aliases définis en 3 endroits | `PLATFORM_ALIAS`, `_ADAPTER_TYPE_ALIASES`, `IntegrationType` | Maintenance difficile | Story 82.3 — consolidation |
| `INTEGRATION_TYPE_TO_CONNECTOR` utilise `azuredevops` | Frontend envoie `azuredevops` comme connector_type | Cohérent avec ITSM externe | Conserver (nom ServiceNow) |
| `terraform_cloud` et `terraform` mappent tous deux vers `Terraform` dans frontend | `INTEGRATION_TYPE_TO_PLATFORM` renvoie `'Terraform'` pour les deux | Pas de perte d'information | Documenter uniquement |

---

## 3. Table Services / Opérations

État de compatibilité backend ↔ frontend pour les service_call steps.

| Service | Opérations backend (`_ALLOWED_OPERATIONS`) | Opérations frontend (`SERVICE_CALL_OPERATIONS`) | Cohérent ? | Dans `SERVICE_TYPES` | Dans `IntegrationAction` (BD) |
|---|---|---|---|---|---|
| `servicenow` | `create_change`, `update_change`, `close_change`, `get_change_status`, `cancel_change` | `create_change`, `update_change`, `close_change`, `get_change_status`, `cancel_change` | ✅ | ✅ | ✅ |
| `vault` | `get_secret` | `get_secret` | ✅ | ✅ | ✅ |
| `jira` | `create_issue`, `update_issue`, `get_issue` | `create_issue`, `update_issue`, `get_issue` | ✅ | ✅ | ✅ |
| `notification` | `send_email`, `send_teams`, `notify_execution_event` | `send_email`, `send_teams`, `notify_execution_event` | ✅ | ✅ | ✅ |
| `splunk` | ❌ **absent** | ❌ **absent** | ✅ (cohérent mais non exposé) | ✅ | ❓ à vérifier |

### Dérives services

| Dérive | Description | Impact | Résolution prévue |
|---|---|---|---|
| `splunk` absent de `_ALLOWED_OPERATIONS` et `SERVICE_CALL_OPERATIONS` | `splunk` est dans `SERVICE_TYPES` et `ServiceRegistry` mais n'a aucune opération définie | Inutilisable en `service_call` step | Story 82.9 — supprimer de `SERVICE_TYPES` ou implémenter les opérations |
| `INTEGRATION_LABELS` dupliqué | Défini dans `serviceCallConstants.ts` ET `WorkflowStepNode.tsx` avec contenu différent | `notification` absent de `WorkflowStepNode.INTEGRATION_LABELS` | Story 82.6 — consolidation |
| `OPERATION_LABELS` dupliqué | Défini dans `serviceCallConstants.ts` ET `WorkflowStepNode.tsx` avec contenu différent | `send_*` et `notify_*` absents de `WorkflowStepNode.OPERATION_LABELS` | Story 82.6 — consolidation |

---

## 4. Recensement complet des mappings frontend hard-codés

### `serviceCallConstants.ts` (`idp-portal/frontend/src/components/admin/step-config/`)

| Constante | Type | Clés | Usage |
|---|---|---|---|
| `SERVICE_CALL_OPERATIONS` | `Record<string, string[]>` | `servicenow`, `vault`, `jira`, `notification` | Opérations disponibles par service dans le step config |
| `INTEGRATION_LABELS` | `Record<string, string>` | `servicenow`, `vault`, `jira`, `notification` | Labels humains pour les services (fr) |
| `OPERATION_LABELS` | `Record<string, string>` | 14 opérations (tous services) | Labels humains pour les opérations (fr) |

### `integrationHelpers.ts` (`idp-portal/frontend/src/utils/`)

| Constante | Type | Clés | Usage |
|---|---|---|---|
| `INTEGRATION_TYPE_TO_PLATFORM` | `Record<string, ActionPlatform>` | `aap`, `tower`, `github_actions`, `azure_devops`, `terraform`, `terraform_cloud` | integration_type → ActionPlatform (BD) |
| `INTEGRATION_TYPE_TO_CONNECTOR` | `Record<string, ConnectorType>` | `aap`, `tower`, `github_actions`, `azure_devops`, `terraform`, `terraform_cloud` | integration_type → connector_type |
| `PLATFORM_CODE_TO_STEP_TYPE` | `Record<string, string>` | `AAP`, `Tower`, `Terraform`, `Terraform Cloud`, `Azure DevOps` | ActionPlatform → step_type (pour filtrage policies) |

### `GateStepConfig.tsx` (`idp-portal/frontend/src/components/admin/step-config/`)

| Constante | Valeurs | Cohérence avec backend |
|---|---|---|
| `GATE_TYPE_OPTIONS` | `maintenance_window`, `approval` | ✅ Cohérent avec les types implémentés (note : `approval` est un alias, pas `approval_granted`) |
| `ON_TIMEOUT_OPTIONS` | `FAIL`, `SKIP` | ✅ Cohérent avec `VALID_ON_TIMEOUT_VALUES` backend |

### `WorkflowStepNode.tsx` (`idp-portal/frontend/src/components/admin/`)

| Constante | Type | Valeurs/Clés | Note |
|---|---|---|---|
| `STEP_TYPE_COLORS` | `Record<WorkflowStepType, string>` | `platform`, `service_call`, `evaluation`, `gate`, `http_request`, `schedule_execution`, `parallel_group` | 7 step types — `parallel_group` déprécié (rétrocompat) |
| `STEP_TYPE_LABELS` | `Record<WorkflowStepType, string>` | Idem + labels FR | `parallel_group` → `'Parallèle'` (déprécié) |
| `INTEGRATION_LABELS` | `Record<string, string>` | `servicenow`, `vault`, `jira` | ⚠️ **PARTIEL** — absent : `notification`. Dupliqué de `serviceCallConstants.ts` |
| `OPERATION_LABELS` | `Record<string, string>` | 9 opérations (servicenow + vault + jira) | ⚠️ **PARTIEL** — absent : opérations `notification`. Dupliqué de `serviceCallConstants.ts` |

---

## 5. Mappings à supprimer en Phase 4 (Story 82.9)

Cette section liste les constantes et fichiers redondants à éliminer lors du grand nettoyage de Phase 4.

### 5.1 Aliases à centraliser (Story 82.3)

| Fichier | Constante/Element | Ligne(s) approx. | Action |
|---|---|---|---|
| `catalog/serializers/validators.py` | `PLATFORM_ALIAS` | ~15-20 | Remplacer par appel à un module central `adapters/aliases.py` |
| `integrations/tasks.py` | `_ADAPTER_TYPE_ALIASES` | ~30-40 | Remplacer par appel au même module central |
| `integrations/models.py` | Valeurs `azuredevops` dans `IntegrationType` | enum | Déprecier `azuredevops` — migrer vers `azure_devops` |

### 5.2 Duplications frontend à consolider (Story 82.6)

| Fichier | Constante | Doublon dans | Action |
|---|---|---|---|
| `WorkflowStepNode.tsx` | `INTEGRATION_LABELS` | `serviceCallConstants.ts` | Supprimer de `WorkflowStepNode.tsx` — importer depuis `serviceCallConstants.ts` |
| `WorkflowStepNode.tsx` | `OPERATION_LABELS` | `serviceCallConstants.ts` | Supprimer de `WorkflowStepNode.tsx` — importer depuis `serviceCallConstants.ts` |

### 5.3 Services non exposés à nettoyer (Story 82.9)

| Fichier | Element | Action |
|---|---|---|
| `services/__init__.py` | `'splunk'` dans `SERVICE_TYPES` | Supprimer OU implémenter les opérations `_ALLOWED_OPERATIONS['splunk']` |

### 5.4 Types gate futurs (à implémenter avant usage)

| Fichier | Element | Condition pour retirer de `FUTURE_GATE_TYPES` |
|---|---|---|
| `catalog/validators.py` | `FUTURE_GATE_TYPES = {'time_window', 'target_state'}` | Implémenter dans `GateEvaluator` ET ajouter dans `VALID_GATE_CONDITION_TYPES` ET `GateHandler.condition_type_map` ET `GateStepConfig.GATE_TYPE_OPTIONS` |

---

*Dernière mise à jour : 2026-03-14 — Story 82.1*
