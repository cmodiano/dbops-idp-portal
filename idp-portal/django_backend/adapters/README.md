# adapters/ — Adaptateurs de plateforme

Ce package contient les **adaptateurs de plateforme** du portail IDP.

## Principe

Chaque adaptateur :
- Herite de `BaseAdapter` (`base_adapter.py`)
- Implemente le contrat commun : `start_job()`, `get_job_status()`, `cancel_job()`, etc.
- Execute des jobs sur une plateforme distante

## Plateformes supportees

| Adaptateur | Fichier | Plateforme |
|-----------|---------|-----------|
| `AAPAdapter` | `aap_adapter.py` | Ansible Automation Platform |
| `TowerAdapter` | `tower_adapter.py` | Ansible Tower (legacy) |
| `AzureDevOpsAdapter` | `azure_devops_adapter.py` | Azure DevOps Pipelines |
| `GitHubActionsAdapter` | `github_actions_adapter.py` | GitHub Actions |
| `TerraformCloudAdapter` | `terraform_cloud_adapter.py` | Terraform Cloud |

## Factory

```python
from adapters import get_platform_adapter

adapter = get_platform_adapter(integration)
adapter.start_job(params)
```

La factory `get_platform_adapter()` retourne l'adaptateur correspondant
au type d'integration passe en parametre.

## Fichiers utilitaires

- `base_adapter.py` — Classe abstraite definissant le contrat commun
- `utils.py` — Fonctions utilitaires partagees (`build_auth_headers()`, etc.)

## A ne pas confondre

Les **services consommes** (Vault, Splunk, ServiceNow) se trouvent dans le
package `services/`. Ils n'heritent pas de `BaseAdapter`.
