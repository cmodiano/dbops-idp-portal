# Architecture — IDP Portal Backend

## Structure des packages d'intégration

Le backend distingue deux types de composants d'intégration externe :

### `adapters/` — Adaptateurs de plateforme

Contient les adaptateurs pour les **plateformes d'exécution** sur lesquelles le portail lance des jobs.

- Chaque adaptateur hérite de `BaseAdapter` (`adapters/base_adapter.py`)
- Contrat commun : `start_job()`, `get_job_status()`, `cancel_job()`, etc.
- Factory : `get_platform_adapter(integration)` dans `adapters/__init__.py`

**Plateformes supportées :**

| Adaptateur | Fichier | Plateforme |
|-----------|---------|-----------|
| `AAPAdapter` | `adapters/aap_adapter.py` | Ansible Automation Platform |
| `TowerAdapter` | `adapters/tower_adapter.py` | Ansible Tower (legacy) |
| `AzureDevOpsAdapter` | `adapters/azure_devops_adapter.py` | Azure DevOps Pipelines |
| `GitHubActionsAdapter` | `adapters/github_actions_adapter.py` | GitHub Actions |
| `TerraformCloudAdapter` | `adapters/terraform_cloud_adapter.py` | Terraform Cloud |

### `services/` — Services consommés

Contient les clients pour les **services transversaux** consommés par le portail (secrets, logs, ITSM).

- N'héritent **pas** de `BaseAdapter`
- Chaque service a sa propre interface selon son domaine
- Factory : `get_service_client(service_type)` dans `services/__init__.py`

**Services supportés :**

| Service | Fichier | Rôle |
|---------|---------|------|
| `VaultService` | `services/vault_service.py` | Résolution des secrets (credential_ref) |
| `SplunkService` | `services/splunk_service.py` | Envoi de logs structurés vers Splunk HEC |
| `ServiceNowService` | `services/servicenow_service.py` | Gestion des changements ITSM |

### Pourquoi cette séparation ?

- Les **adapters** partagent un contrat commun (`BaseAdapter`) car ils remplissent tous la meme fonction : exécuter des jobs sur une plateforme distante.
- Les **services** ont des responsabilités distinctes (secrets, logs, ITSM) et ne partagent pas de contrat commun.
- La factory `get_platform_adapter()` est utilisée par le moteur d'exécution pour obtenir le bon adapter selon le type d'intégration.
- La factory `get_service_client()` est utilisée par les composants internes qui ont besoin d'un service transversal.

Voir aussi : [glossary.md](glossary.md) pour la terminologie.

## Règles et Politiques sur les Actions

Le modèle `Action` (catalog/models.py) contient plusieurs types de règles/configurations JSON évaluées à différents moments du workflow d'exécution :

| Champ | Évalué à | Objectif |
|-------|----------|----------|
| `impact_rules` | Soumission | Déterminer impact_level par environnement |
| `change_type_config` | Soumission | Changement ServiceNow requis par environnement |
| `gate_conditions` | Pré-étape (runtime) | Conditions bloquantes (maintenance_window, manual_approval) |
| **`business_rule_policies`** | **Post-étape** | **Évaluer sortie d'étape → revue DBA ou auto-approbation** |
| `remediation_rules` | Post-exécution | Suggérer/déclencher actions correctives si échec |

### business_rule_policies (Stories 28.1–28.3)

Champ `OracleJSONField` nullable sur le modèle `Action`. Définit des politiques métier évaluées après la sortie d'une étape d'exécution (ex. plan Terraform, job AAP) pour décider si une revue DBA est nécessaire ou si l'approbation automatique est possible.

- **Validation** : `catalog/validators.py` → `validate_business_rule_policies()`
- **API** : `PUT /api/v1/admin/actions/{id}/business-rule-policies/`
- **UI Admin** : Section "Règles métier" dans ActionForm (éditeur JSON avec validation live)
- **Documentation complète** : [business-rule-policies.md](../../docs/business-rule-policies.md)

#### Architecture RuleEngine (Story 28.3)

Le `PolicyEvaluator` délègue au `RuleEngine`, qui utilise des `OutputInterpreter` spécialisés par plateforme :

```
PolicyEvaluator → RuleEngine → OutputInterpreterRegistry → OutputInterpreter → NormalizedArtifact
```

| Composant | Fichier | Rôle |
|-----------|---------|------|
| `RuleEngine` | `executions/rule_engine.py` | Moteur d'évaluation des règles métier |
| `OutputInterpreterRegistry` | `executions/interpreters/registry.py` | Registre singleton des interpréteurs |
| `TerraformPlanInterpreter` | `executions/interpreters/terraform_plan_interpreter.py` | Interpréteur plans Terraform |
| `AAPOutputInterpreter` | `executions/interpreters/aap_output_interpreter.py` | Interpréteur sorties AAP |

Pour ajouter une nouvelle plateforme : implémenter `OutputInterpreter.interpret()` et enregistrer dans le registre.
