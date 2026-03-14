# Codes Canoniques des Plateformes — IDP Portal

> **Story 82.1 — Phase 0 : Stabilisation et réduction de dérive**
> Document de référence pour les Stories 82.2 à 82.9.

## 1. Table des codes canoniques et aliases

Cette table liste, pour chaque plateforme supportée, l'ensemble des identifiants et codes utilisés à travers le système.

| Code canonique | Alias(es) backend | Adapter registré | Queue Celery | ActionPlatform (BD) | Connector frontend | Décision |
|---|---|---|---|---|---|---|
| `aap` | — | ✓ `aap` | `aap` | `AAP` | `aap` | Code principal Ansible Automation Platform |
| `tower` | alias de `aap` | ✓ `tower` (queue `aap`) | `aap` | `Tower` | `aap` | Legacy Ansible Tower — alias vers `aap`, queue partagée |
| `azure_devops` | `azuredevops` (`_ADAPTER_TYPE_ALIASES`) | ✓ `azure_devops` | `azure` | `Azure DevOps` | `azuredevops` | ⚠️ Voir §2 — dérive azuredevops vs azure_devops |
| `github_actions` | — | ✓ `github_actions` | `github` | `GitHub Actions` | `github_actions` | Pas d'alias — cohérent dans tout le système |
| `terraform_cloud` | `terraform` (`PLATFORM_ALIAS` + `_ADAPTER_TYPE_ALIASES`) | ✓ `terraform_cloud` | `terraform` | `Terraform` | `terraform` / `terraform_cloud` | `terraform` est le nom court historique |

### Sources des aliases

Les aliases de normalisation sont définis en **3 endroits distincts** :

1. **`catalog/serializers/validators.py`** — `PLATFORM_ALIAS`
   ```python
   PLATFORM_ALIAS = {'terraform': 'terraform_cloud', 'tower': 'aap'}
   ```
   Utilisé lors de la validation et sérialisation des actions catalog.

2. **`integrations/tasks.py`** — `_ADAPTER_TYPE_ALIASES`
   ```python
   _ADAPTER_TYPE_ALIASES = {'azuredevops': 'azure_devops', 'terraform': 'terraform_cloud'}
   ```
   Utilisé lors de la résolution de l'adapter type pour les tâches Celery.

3. **`integrations/models.py`** — `IntegrationType` enum
   Contient les deux formes : `tower` + `aap`, `terraform` + `terraform_cloud`, `azuredevops` + `azure_devops`.

> **Note Architecture** : Ces 3 sources de vérité séparées seront consolidées dans la Story 82.3 (normalisation des aliases).

---

## 2. Décision de normalisation : `azuredevops` vs `azure_devops`

### Analyse de la dérive

| Emplacement | Valeur utilisée |
|---|---|
| `IntegrationType` enum (`integrations/models.py`) | `azuredevops` ET `azure_devops` (les deux existent) |
| Registre adapter (`adapters/__init__.py`) | `azure_devops` (code canonique) |
| `_ADAPTER_TYPE_ALIASES` (`integrations/tasks.py`) | `azuredevops` → `azure_devops` |
| Frontend `INTEGRATION_TYPE_TO_CONNECTOR` | `azure_devops` → `'azuredevops'` (connector_type) |
| Frontend `INTEGRATION_TYPE_TO_PLATFORM` | `azure_devops` → `'Azure DevOps'` |

### Décision

**Code canonique = `azure_devops`** (snake_case, cohérent avec les autres plateformes : `github_actions`, `terraform_cloud`).

**Alias = `azuredevops`** (camelCase historique, encore présent dans `IntegrationType` et `_ADAPTER_TYPE_ALIASES`).

**Normalisation à appliquer (Story 82.3)** :
- Déprecier `azuredevops` dans `IntegrationType` en faveur de `azure_devops`
- Conserver `_ADAPTER_TYPE_ALIASES` pour rétrocompatibilité des intégrations existantes
- Le `connector_type` frontend reste `azuredevops` (nom ServiceNow/ITSM externe — ne pas modifier)

---

## 3. Kwargs runtime requis par plateforme

Les kwargs runtime spécifiques par plateforme sont injectés via les factory functions de `adapters/__init__.py`. Ces informations serviront à construire `build_platform_runtime_config()` en Story 82.2.

| Plateforme | Kwargs requis | Kwargs optionnels | Validation | Factory |
|---|---|---|---|---|
| `aap` | `base_url`, `auth_headers` | — | implicite | `_factory_aap` |
| `tower` | `base_url`, `auth_headers` | `ssl_verify` (bool, défaut False) | implicite | `_factory_tower` |
| `azure_devops` | `base_url`, `auth_headers` | — | implicite | `_factory_azure_devops` |
| `github_actions` | `base_url`, `auth_headers`, **`owner`**, **`repo`** | — | `ValueError` si absent | `_factory_github_actions` |
| `terraform_cloud` | `base_url`, `auth_headers`, **`organization`** | — | `ValueError` si absent | `_factory_terraform_cloud` |

### Détail par plateforme

#### `aap` (Ansible Automation Platform)
- **`base_url`** : URL de l'instance AAP (ex: `https://aap.example.com`)
- **`auth_headers`** : dict contenant le Bearer token
- Pas de kwargs runtime supplémentaires requis au niveau factory

#### `tower` (Ansible Tower — legacy)
- Même structure que `aap`, queue Celery partagée (`aap`)
- **`ssl_verify`** (optionnel) : booléen pour valider le certificat TLS (défaut : `False` pour compatibilité legacy)

#### `azure_devops`
- **`base_url`** : URL de l'organisation Azure DevOps (ex: `https://dev.azure.com/org`)
- **`auth_headers`** : PAT token dans l'en-tête Authorization

#### `github_actions`
- **`owner`** (requis) : organisation ou utilisateur GitHub
- **`repo`** (requis) : nom du dépôt
- Ces deux kwargs doivent être présents dans la configuration runtime — une `ValueError` est levée si absents

#### `terraform_cloud`
- **`organization`** (requis) : nom de l'organisation Terraform Cloud
- Requis pour construire les URLs d'API Terraform (`/api/v2/organizations/{organization}/...`)

### Note sur la centralisation

Il n'existe actuellement **pas de fonction centralisée** `build_platform_runtime_config()` — chaque factory est indépendante.

La centralisation sera implémentée en **Story 82.2** via `adapters/runtime_config.py`, en s'appuyant sur cette documentation comme spécification.

---

## 4. Cohérence des aliases — État actuel

| Alias | Source | Code canonique résolu | Cohérent ? |
|---|---|---|---|
| `terraform` | `PLATFORM_ALIAS` | `terraform_cloud` | ✓ |
| `tower` | `PLATFORM_ALIAS` | `aap` | ✓ |
| `azuredevops` | `_ADAPTER_TYPE_ALIASES` | `azure_devops` | ✓ (mais les deux formes dans IntegrationType — dérive) |
| `terraform` | `_ADAPTER_TYPE_ALIASES` | `terraform_cloud` | ✓ (doublon avec PLATFORM_ALIAS — consolidation Story 82.3) |

**Conclusion** : Les aliases eux-mêmes sont cohérents (ils pointent vers les bons codes canoniques). La dérive est dans la **multiplicité** des endroits où ils sont définis, et dans la présence des deux formes `azuredevops`/`azure_devops` dans `IntegrationType`.

---

*Dernière mise à jour : 2026-03-14 — Story 82.1*
