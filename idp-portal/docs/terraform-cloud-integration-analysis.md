# Analyse Intégration Terraform Cloud REST API v2

## Vue d'ensemble

Terraform Cloud fournit une API REST v2 (JSON API spec) pour gérer les workspaces, runs (plan/apply), logs et notifications en temps réel.

- **Version API** : v2 (JSON API spec)
- **Base URL** : `https://app.terraform.io/api/v2` (Cloud) ou `https://terraform.entreprise.com/api/v2` (Enterprise)

## Endpoints principaux

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/organizations/{org}/workspaces` | GET | Liste workspaces |
| `/workspaces/{workspace_id}` | GET | Détails workspace |
| `/runs` | POST | Créer run (201 Created + run object) |
| `/runs/{run_id}` | GET | Statut run |
| `/runs/{run_id}/plan` | GET | Détails plan (inclut log-read-url) |
| `/runs/{run_id}/apply` | GET | Détails apply (inclut log-read-url) |
| `/runs/{run_id}/actions/cancel` | POST | Annuler run |
| `/runs/{run_id}/actions/force-cancel` | POST | Force annuler run |
| `/runs/{run_id}/actions/discard` | POST | Abandonner run |

## Paramètres POST /runs

```json
{
  "data": {
    "type": "runs",
    "attributes": {
      "auto-apply": false,
      "message": "Triggered via IDP Portal",
      "target-addrs": ["module.vpc"],
      "is-destroy": false
    },
    "relationships": {
      "workspace": {
        "data": {
          "type": "workspaces",
          "id": "ws-xxxxx"
        }
      }
    }
  }
}
```

## Authentification

- **Header** : `Authorization: Bearer <TOKEN>`
- **Content-Type** : `application/vnd.api+json`
- **Types tokens** : User tokens (full access), Team tokens (scoped), Organization tokens (scoped)
- **Stockage** : Vault credentials (credential_ref → Vault path)

## Cycle de vie des statuts

```
pending → plan_queued → planning → planned
  → [cost_estimating → cost_estimated]
  → [policy_checking → policy_checked]
  → [confirmed]
  → apply_queued → applying → applied

Terminaisons alternatives :
  → errored (erreur plan ou apply)
  → canceled / force_canceled (annulation)
  → discarded (abandonné)
  → planned_and_finished (plan seul, pas d'apply)
```

## Mapping statuts Terraform Cloud → IDP Portal

| Statut Terraform Cloud | Mapping IDP Portal | Notes |
|------------------------|-------------------|-------|
| `pending` | SUBMITTED | En attente |
| `plan_queued` | SUBMITTED | En attente de plan |
| `planning` | RUNNING | Plan en cours |
| `planned` | SUBMITTED | Plan terminé, attente apply |
| `cost_estimating` | RUNNING | Estimation coûts |
| `cost_estimated` | SUBMITTED | Estimation terminée |
| `policy_checking` | RUNNING | Vérification policies |
| `policy_override` | SUBMITTED | Policy override requis |
| `policy_soft_failed` | SUBMITTED | Policy soft fail |
| `policy_checked` | SUBMITTED | Policies validées |
| `confirmed` | SUBMITTED | Confirmé manuellement |
| `apply_queued` | SUBMITTED | En attente d'apply |
| `applying` | RUNNING | Apply en cours |
| `applied` | COMPLETED | Apply réussi |
| `planned_and_finished` | COMPLETED | Plan seul terminé |
| `errored` | FAILED | Erreur plan ou apply |
| `canceled` | CANCELLED | Annulé |
| `force_canceled` | CANCELLED | Force annulé |
| `discarded` | CANCELLED | Abandonné |

## Récupération des logs

Les logs sont disponibles via un mécanisme à deux étapes :
1. **GET /runs/{run_id}/plan** → récupérer `log-read-url` dans la réponse
2. **GET {log-read-url}** → télécharger le texte brut des logs

Même approche pour apply : GET /runs/{run_id}/apply → `log-read-url`.

Si le run est en cours, les logs partiels sont disponibles (`complete: False`).

## Webhooks (Notifications)

- **Configuration** : Workspace Settings → Notifications → Webhook
- **Events** : `run:created`, `run:planning`, `run:applying`, `run:completed`, `run:errored`
- **Sécurité** : Header `X-TFE-Notification-Signature` = HMAC SHA-512(token, body)
- **Payload** : Inclut `run_id`, `run_status`, `workspace_id`, `organization_name`

### Payload exemple

```json
{
  "notification_configuration_id": "nc-xxxxx",
  "run_url": "https://app.terraform.io/app/my-org/my-workspace/runs/run-xxxxx",
  "run_id": "run-xxxxx",
  "run_message": "Triggered via IDP Portal",
  "workspace_id": "ws-xxxxx",
  "workspace_name": "my-workspace",
  "organization_name": "my-org",
  "notifications": [
    {
      "message": "Run applying",
      "trigger": "run:applying",
      "run_status": "applying",
      "run_updated_at": "2026-02-14T10:01:00Z"
    }
  ]
}
```

## Différences avec AAP/Tower/Azure DevOps/GitHub Actions

| Aspect | Terraform Cloud | GitHub Actions | Azure DevOps | AAP/Tower |
|--------|----------------|---------------|--------------|-----------|
| **Structure status** | 1 champ complexe (18+ états) | 2 champs (status + conclusion) | 2 champs (state + result) | 1 champ |
| **Logs** | Via log-read-url (plan + apply séparés) | Archive ZIP redirect 1 min | Multiples endpoints log ID | Endpoint direct |
| **Temps réel** | Webhooks notification + polling | Webhooks workflow_run + polling | Polling | Polling |
| **Auth** | Bearer token (User/Team/Org) | Bearer PAT/App | Basic PAT | Basic/Bearer |
| **Trigger retour** | 201 Created run object (run_id immédiat) | 204 No Content (pas run_id) | 200 OK run object | 201 job_id |
| **Params org/workspace** | Requis partout | owner/repo requis | Organisation/projet URL | Pas nécessaire |

## Rate Limits

- **Free tier** : 30 req/min
- **Paid tiers** : 100+ req/min
- **Recommandation** : Webhooks primaire pour éviter polling excessif

## Approche monitoring temps réel

**Stratégie hybride** : Webhooks primaire + Polling catch-up (60s)

- Webhooks : latence minimale, pas de consommation rate limit
- Polling fallback : 60s intervalle, GET /runs/{run_id}
- Réutilisation patterns ExecutionConsumer Django Channels (Stories 27.1-27.4)

## Flow complet

```
API backend → TerraformCloudAdapter.trigger() → POST /runs (Terraform Cloud)
    ↓
201 Created → run_id récupéré
    ↓
Webhooks notification (primaire) ou Polling 60s (fallback)
    ↓
TerraformCloudAdapter.get_status() → mapping statut
    ↓
_broadcast_execution_update() → WebSocket ExecutionConsumer
    ↓
Frontend ws/executions/{id} → mise à jour temps réel
```
