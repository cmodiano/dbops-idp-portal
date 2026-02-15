# Catalogue des Types d'Intégration

> Story 24.1 — Modèle `IntegrationTypeCatalogue` + `IntegrationAction` et API de lecture.

## Architecture

### Schéma ER

```
IntegrationTypeCatalogue (1) ──── (N) IntegrationAction
         PK: code                      PK: id
                                       FK: integration_type_code
```

### Tables Oracle

| Table | Description |
|-------|-------------|
| `INTEGRATION_TYPE_CATALOGUE` | Types d'intégration supportés (AAP, ServiceNow, etc.) |
| `INTEGRATION_ACTIONS` | Actions disponibles par type (start_job, create_change, etc.) |

### Modèle IntegrationTypeCatalogue

| Champ | Type | Description |
|-------|------|-------------|
| `code` | CharField(50), PK | Code unique du type (ex: `aap`, `servicenow`) |
| `name` | CharField(255) | Nom affichage (ex: `Ansible Automation Platform`) |
| `description` | TextField | Description du type d'intégration |
| `version` | CharField(20) | Version du catalogue (ex: `1.0`) |
| `is_active` | BooleanField | Actif/déprécié |
| `created_at` | DateTimeField | Date de création |
| `updated_at` | DateTimeField | Date de mise à jour |

### Modèle IntegrationAction

| Champ | Type | Description |
|-------|------|-------------|
| `id` | BigAutoField, PK | Identifiant auto-incrémenté |
| `integration_type` | FK → IntegrationTypeCatalogue | Type parent |
| `action_code` | CharField(100) | Code technique (ex: `start_job`) |
| `action_label` | CharField(255) | Label UI (ex: `Démarrer un job`) |
| `description` | TextField | Description de l'action |
| `required_params` | TextField (JSON) | Schéma JSON des paramètres obligatoires |
| `optional_params` | TextField (JSON) | Schéma JSON des paramètres optionnels |
| `response_format` | TextField (JSON) | Description du format de réponse |
| `is_active` | BooleanField | Actif/déprécié |
| `created_at` | DateTimeField | Date de création |
| `updated_at` | DateTimeField | Date de mise à jour |

**Contrainte unique :** `(integration_type, action_code)`

## Types d'intégration supportés

### Tableau récapitulatif

| Type | Code | Catégorie | Actions disponibles | Version | Story |
|------|------|-----------|---------------------|---------|-------|
| Ansible Automation Platform | `aap` | **Plateforme** | 4 (start_job, start_workflow, get_job_status, cancel_job) | 1.0 | Story 27.1 |
| Ansible Tower | `tower` | **Plateforme** | 4 (start_job, start_workflow, get_job_status, cancel_job) | 1.0 | Story 27.2 |
| Azure DevOps Pipelines | `azure_devops` | **Plateforme** | 4 (run_pipeline, get_run_status, get_run_logs, cancel_run) | 1.0 | Story 27.3 |
| GitHub Actions | `github_actions` | **Plateforme** | 4 (trigger_workflow, get_workflow_run_status, get_workflow_run_logs, cancel_workflow_run) | 1.0 | Story 27.4 |
| Terraform Cloud | `terraform_cloud` | **Plateforme** | 5 (create_run, get_run_status, get_run_logs, cancel_run, apply_run) | 1.0 | Story 27.5 |
| HashiCorp Vault | `vault` | **Service** | 3 (get_secret, renew_token, lookup_token) | 1.0 | Story 27.6 |
| ServiceNow ITSM | `servicenow` | **Service** | 3 (create_change, update_change, get_change_status) | 1.0 | Existant |
| Splunk HEC | `splunk` | **Service** | 2 (send_event, send_batch) | 1.0 | Story 27.8 |
| Jira | `jira` | **Service** | 4 (create_issue, update_issue, get_issue, add_comment) | 1.0 | Story 27.10 |

> **Plateforme** = adaptateur dans `adapters/`, hérite de `BaseAdapter`, exécute des jobs via `get_platform_adapter()`.
> **Service** = client dans `services/`, n'hérite pas de `BaseAdapter`, consommé via `get_service_client()`.

### AAP (Ansible Automation Platform)

| Action | Label | Paramètres obligatoires |
|--------|-------|------------------------|
| `start_job` | Démarrer un job | `job_template_id` (integer) |
| `start_workflow` | Démarrer un workflow | `workflow_job_template_id` (integer) |
| `get_job_status` | Récupérer le statut d'un job | `job_id` (integer) |
| `cancel_job` | Annuler un job | `job_id` (integer) |

### Ansible Tower (tower)

> Version legacy avant AAP. Adapter: `TowerAdapter` (Story 27.2)

| Action | Label | Paramètres obligatoires | Paramètres optionnels |
|--------|-------|------------------------|----------------------|
| `start_job` | Démarrer un job template Tower | `job_template_id` (integer) | `extra_vars` (object) |
| `start_workflow` | Démarrer un workflow job Tower | `workflow_job_template_id` (integer) | `extra_vars` (object) |
| `get_job_status` | Récupérer statut job Tower | `job_id` (integer) | — |
| `cancel_job` | Annuler job Tower en cours | `job_id` (integer) | — |

**Exemple credential_ref :** `vault:secret/data/tower/prod#token`
**Exemple base_url :** `https://tower.example.com`

### Azure DevOps Pipelines (azure_devops)

> Adapter: `AzureDevOpsAdapter` (Story 27.3). Monitoring temps réel (polling 5s).

| Action | Label | Paramètres obligatoires | Paramètres optionnels |
|--------|-------|------------------------|----------------------|
| `run_pipeline` | Exécuter un pipeline | `pipeline_id` (integer), `branch` (string) | `variables` (object) |
| `get_run_status` | Statut exécution pipeline | `run_id` (integer) | — |
| `get_run_logs` | Logs exécution | `run_id` (integer) | — |
| `cancel_run` | Annuler exécution pipeline | `run_id` (integer) | — |

**Exemple credential_ref :** `vault:secret/data/azure-devops/prod#token`
**Exemple base_url :** `https://dev.azure.com/organization`

### GitHub Actions (github_actions)

> Adapter: `GitHubActionsAdapter` (Story 27.4). Monitoring webhooks + polling.

| Action | Label | Paramètres obligatoires | Paramètres optionnels |
|--------|-------|------------------------|----------------------|
| `trigger_workflow` | Déclencher workflow | `owner` (string), `repo` (string), `workflow_id` (string), `ref` (string) | `inputs` (object) |
| `get_workflow_run_status` | Statut workflow | `run_id` (integer) | — |
| `get_workflow_run_logs` | Logs workflow | `run_id` (integer) | — |
| `cancel_workflow_run` | Annuler workflow | `run_id` (integer) | — |

**Exemple credential_ref :** `vault:secret/data/github/prod#token`
**Exemple base_url :** `https://api.github.com`

### Terraform Cloud (terraform_cloud)

> Adapter: `TerraformCloudAdapter` (Story 27.5). Runs plan/apply, monitoring webhooks + polling.

| Action | Label | Paramètres obligatoires | Paramètres optionnels |
|--------|-------|------------------------|----------------------|
| `create_run` | Créer et démarrer un run | `workspace_id` (string), `message` (string) | `is_destroy` (boolean), `variables` (object) |
| `get_run_status` | Statut run | `run_id` (string) | — |
| `get_run_logs` | Logs run | `run_id` (string) | — |
| `cancel_run` | Annuler run | `run_id` (string) | — |
| `apply_run` | Appliquer plan | `run_id` (string) | — |

**Exemple credential_ref :** `vault:secret/data/terraform/prod#token`
**Exemple base_url :** `https://app.terraform.io`

### HashiCorp Vault (vault)

> **Service** (pas un adapter). Client : `VaultService` (`services/vault_service.py`, Story 27.6). Résolution secrets KV v2, auth Token ou AppRole.

| Action | Label | Paramètres obligatoires | Paramètres optionnels |
|--------|-------|------------------------|----------------------|
| `get_secret` | Résoudre credential_ref | `path` (string) | `key` (string), `namespace` (string) |
| `renew_token` | Renouveler token | — | — |
| `lookup_token` | Vérifier validité token | — | — |

**Exemple credential_ref :** `vault:secret/data/vault/prod#token`
**Exemple base_url :** `https://vault.example.com`

### ServiceNow ITSM

| Action | Label | Paramètres obligatoires |
|--------|-------|------------------------|
| `create_change` | Créer un changement | `short_description`, `category` |
| `update_change` | Mettre à jour un changement | `change_id` |
| `get_change_status` | Récupérer le statut d'un changement | `change_id` |

### Splunk HEC (splunk)

> **Service** (pas un adapter). Client : `SplunkService` (`services/splunk_service.py`, Story 27.8). Envoi logs structurés JSON vers Splunk HEC.

| Action | Label | Paramètres obligatoires | Paramètres optionnels |
|--------|-------|------------------------|----------------------|
| `send_event` | Envoyer un événement | `event` (object) | `sourcetype` (string), `index` (string) |
| `send_batch` | Envoyer un batch | `events` (array) | `sourcetype` (string), `index` (string) |

**Exemple credential_ref :** `vault:secret/data/splunk/prod#token`
**Exemple base_url :** `https://splunk.example.com:8088`

Voir [splunk-integration.md](splunk-integration.md) pour la documentation complète.

### Jira (jira)

> **Service** (pas un adapter). Client : `JiraService` (`services/jira_service.py`, Story 27.10). Gestion d'issues via REST API v3/v2.

| Action | Label | Paramètres obligatoires | Paramètres optionnels |
|--------|-------|------------------------|----------------------|
| `create_issue` | Créer une issue | `project_key` (string), `issue_type` (string), `summary` (string) | `description` (string), `assignee` (string), `labels` (array), `priority` (string) |
| `update_issue` | Mettre à jour une issue | `issue_key` (string) | `status` (string), `assignee` (string), `labels` (array), `summary` (string) |
| `get_issue` | Récupérer une issue | `issue_key` (string) | — |
| `add_comment` | Ajouter un commentaire | `issue_key` (string), `comment` (string) | — |

**Exemple credential_ref :** `vault:secret/data/jira/cloud#api_token`
**Exemple base_url :** `https://instance.atlassian.net` (Cloud) ou `https://jira.company.com` (Server)

Voir [jira-integration.md](jira-integration.md) pour la documentation complète.

## Format JSON Schema des Paramètres

Les champs `required_params` et `optional_params` utilisent un format JSON Schema simplifié :

```json
{
  "type": "object",
  "properties": {
    "job_template_id": {
      "type": "integer",
      "description": "ID du job template AAP"
    }
  },
  "required": ["job_template_id"]
}
```

## Comment les types sont exposés au menu Admin (frontend)

1. **Backend** : Les types affichés dans le formulaire « Nouvelle intégration » viennent **uniquement** du catalogue en base :
   - Modèle `IntegrationTypeCatalogue` (table `INTEGRATION_TYPE_CATALOGUE`) avec `is_active=True`
   - Les enregistrements sont chargés via la fixture `integration_type_catalogue` (`python manage.py loaddata integration_type_catalogue`).

2. **API** : Le frontend appelle `GET /api/v1/integrations/types/`. La vue `IntegrationTypeCatalogueViewSet.list` retourne tous les types actifs avec leurs actions (sérialiseur `IntegrationTypeWithActionsSerializer`).

3. **Frontend** : Le hook `useIntegrationTypes()` (appel à `getIntegrationTypes()` du service intégrations) récupère cette liste. Le composant `IntegrationForm` affiche un `Select` alimenté par ces types ; aucun type n’est codé en dur côté UI (sauf repli si l’API échoue).

**Pour qu’un nouveau type (ex. Azure DevOps, GitHub Actions, Terraform Cloud, Tower, Vault) apparaisse dans le menu Admin :**
- Ajouter le type et ses actions dans la fixture `integrations/fixtures/integration_type_catalogue.json`.
- Ajouter le code du type dans l’enum `IntegrationType` dans `integrations/models.py` (pour que la création d’intégration accepte ce type).
- Charger la fixture : `python manage.py loaddata integration_type_catalogue` (en dev ou au déploiement). Après rechargement, le type apparaît dans la liste déroulante « Type d’intégration » sans changement frontend.

## API Endpoints

### GET /api/v1/integrations/types/

Liste tous les types d'intégration actifs avec leurs actions.

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/integrations/types/
```

**Réponse 200 :**
```json
{
  "data": [
    {
      "code": "aap",
      "name": "Ansible Automation Platform",
      "description": "Exécution de jobs et workflows Ansible via AAP Controller",
      "version": "1.0",
      "is_active": true,
      "created_at": "2026-02-10T10:00:00Z",
      "updated_at": "2026-02-10T10:00:00Z",
      "actions": [
        {
          "id": 1,
          "action_code": "start_job",
          "action_label": "Démarrer un job",
          "description": "Lance un job template AAP avec paramètres extra_vars",
          "required_params": {"type": "object", "properties": {"job_template_id": {"type": "integer"}}},
          "optional_params": {"type": "object", "properties": {"extra_vars": {"type": "object"}}},
          "response_format": {"job_id": "integer", "status": "string"},
          "is_active": true,
          "created_at": "2026-02-10T10:00:00Z",
          "updated_at": "2026-02-10T10:00:00Z"
        }
      ]
    }
  ]
}
```

### GET /api/v1/integrations/types/{code}/

Récupère un type spécifique avec ses actions.

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/integrations/types/aap/
```

**Réponse 404 si le code n'existe pas.**

### GET /api/v1/integrations/types/{code}/actions/

Liste les actions d'un type spécifique.

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/integrations/types/aap/actions/
```

## Guide : Ajouter un nouveau type d'intégration

1. **Créer le type** dans la fixture `integrations/fixtures/integration_type_catalogue.json` ou via l'admin Django :
   ```json
   {
     "model": "integrations.integrationtypecatalogue",
     "pk": "terraform",
     "fields": {
       "name": "Terraform Cloud",
       "description": "Gestion d'infrastructure via Terraform",
       "version": "1.0",
       "is_active": true,
       "created_at": "2026-02-10T10:00:00Z",
       "updated_at": "2026-02-10T10:00:00Z"
     }
   }
   ```

2. **Ajouter les actions** supportées par ce type :
   ```json
   {
     "model": "integrations.integrationaction",
     "fields": {
       "integration_type": "terraform",
       "action_code": "plan",
       "action_label": "Terraform Plan",
       "description": "Génère un plan d'exécution Terraform",
       "required_params": "{...}",
       "optional_params": "{...}",
       "response_format": "{...}",
       "is_active": true,
       "created_at": "2026-02-10T10:00:00Z",
       "updated_at": "2026-02-10T10:00:00Z"
     }
   }
   ```

3. **Charger les fixtures** :
   ```bash
   python manage.py loaddata integration_type_catalogue
   ```

4. **Vérifier** via l'API :
   ```bash
   curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/v1/integrations/types/terraform/
   ```

## Validation du Statut des Intégrations

> Voir [integration-status-validation.md](integration-status-validation.md) pour la documentation complète.

Chaque intégration possède un champ `status` (`valid`, `invalid`, `deprecated`) calculé automatiquement en vérifiant l'existence et l'état (`is_active`) du type dans le catalogue.

**Scénario de dépréciation :**
1. Un type est marqué `is_active=False` dans le catalogue
2. La validation périodique (`validate_integrations`) détecte le changement
3. Les intégrations utilisant ce type passent en `status=deprecated`
4. L'UI Admin affiche un badge orange "Déprécié" et un warning dans le formulaire
5. Les nouvelles utilisations dans les workflows sont bloquées (Story 24.4)

## Gestion des Versions et Dépréciation

### Stratégie de Versionnement

Le champ `version` suit un modèle de versionnement sémantique simplifié (`MAJOR.MINOR`) :

| Type de changement | Incrémentation | Exemple | Impact |
|-------------------|---------------|---------|--------|
| **Ajout d'actions** (non-breaking) | Minor | `1.0` → `1.1` | Les intégrations existantes continuent de fonctionner |
| **Modification de paramètres existants** (breaking) | Major | `1.0` → `2.0` | Nécessite migration des intégrations |
| **Suppression d'actions** (breaking) | Major | `1.0` → `2.0` | Nécessite migration des intégrations |
| **Modification du format de réponse** (breaking) | Major | `1.0` → `2.0` | Nécessite adaptation du code client |

### Dépréciation d'un Type ou d'une Action

**Étape 1: Marquer comme inactif**
```python
# Via Django shell ou Admin
type_obj = IntegrationTypeCatalogue.objects.get(code='old_type')
type_obj.is_active = False
type_obj.save()
```

**Étape 2: Communication**
- Les types/actions avec `is_active=False` ne sont **plus retournés par l'API** (`GET /api/v1/integrations/types`)
- Les intégrations existantes utilisant un type déprécié continuent de fonctionner **mais un warning est loggé** (Story 24.4)

**Étape 3: Migration**
- Identifier les intégrations affectées : `Integration.objects.filter(type='old_type')`
- Mettre à jour manuellement ou via script de migration vers le nouveau type
- Les exécutions utilisant un type déprécié **sont rejetées avec erreur explicite** (Story 24.4)

**Étape 4: Suppression (optionnelle)**
- **JAMAIS supprimer les données** de la table (violation SOC1/NFR8 audit trail)
- Garder `is_active=False` indéfiniment pour traçabilité historique

### Migration Breaking Changes

Exemple : Changement du paramètre `job_template_id` (integer) vers `job_template_name` (string) dans AAP `start_job`

**1. Créer nouvelle version du type :**
```json
{
  "model": "integrations.integrationtypecatalogue",
  "pk": "aap",
  "fields": {
    "version": "2.0",  // Incrément major
    ...
  }
}
```

**2. Modifier l'action avec nouveaux paramètres :**
```json
{
  "model": "integrations.integrationaction",
  "fields": {
    "integration_type": "aap",
    "action_code": "start_job",
    "required_params": "{\"type\": \"object\", \"properties\": {\"job_template_name\": {\"type\": \"string\"}}, \"required\": [\"job_template_name\"]}", // CHANGÉ
    ...
  }
}
```

**3. Script de migration des intégrations existantes :**
```python
# Adapter les configurations JSON des intégrations existantes
for integration in Integration.objects.filter(type='aap'):
    config = integration.get_config()
    if 'job_template_id' in config:
        config['job_template_name'] = resolve_template_name(config['job_template_id'])
        del config['job_template_id']
        integration.set_config(config)
        integration.save()
```

**4. Validation lors des exécutions** (Story 24.4) :
- Valider que `required_params` du catalogue correspondent aux params fournis
- Rejeter les exécutions avec paramètres obsolètes

## Audit Trail

Toute création ou modification de type ou d'action est automatiquement auditée via les signaux Django `post_save` :

- `INTEGRATION_TYPE_CREATED` / `INTEGRATION_TYPE_UPDATED`
- `INTEGRATION_ACTION_CREATED` / `INTEGRATION_ACTION_UPDATED`

Les entrées d'audit sont immutables (SOC1/NFR8).
