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
