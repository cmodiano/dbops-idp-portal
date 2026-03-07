# Analyse d'Intégration — Azure DevOps Pipelines

## 1. Vue d'ensemble

Azure DevOps Pipelines REST API v7.1+. Objectif : lancer pipelines (runs), récupérer logs, suivre statut en temps réel.

## 2. Endpoints REST API v7.1+

Base URL: `https://dev.azure.com/{organization}/{project}/_apis/pipelines/`

### 2.1 Lancer un run (POST)
- POST `/pipelines/{pipelineId}/runs?api-version=7.1`
- Body:
```json
{
  "templateParameters": {
    "environment": "production",
    "version": "1.2.3"
  },
  "variables": {
    "debug": {"value": "true"},
    "region": {"value": "us-east-1"}
  },
  "resources": {
    "repositories": {
      "self": {"refName": "refs/heads/main"}
    }
  }
}
```
- Response:
```json
{
  "id": 12345,
  "state": "inProgress",
  "result": null,
  "createdDate": "2026-02-14T10:00:00Z",
  "finishedDate": null,
  "url": "https://dev.azure.com/org/project/_apis/pipelines/78/runs/12345",
  "pipeline": {"id": 78, "name": "main-ci"}
}
```

### 2.2 Récupérer statut run (GET)
- GET `/pipelines/{pipelineId}/runs/{runId}?api-version=7.1`
- Response:
```json
{
  "id": 12345,
  "state": "completed",
  "result": "succeeded",
  "createdDate": "2026-02-14T10:00:00Z",
  "finishedDate": "2026-02-14T10:05:30Z",
  "url": "https://dev.azure.com/org/project/_apis/pipelines/78/runs/12345"
}
```

### 2.3 Récupérer liste logs (GET)
- GET `/pipelines/{pipelineId}/runs/{runId}/logs?api-version=7.1`
- Response:
```json
{
  "count": 3,
  "logs": [
    {"id": 1, "lineCount": 150, "createdOn": "2026-02-14T10:00:05Z"},
    {"id": 2, "lineCount": 342, "createdOn": "2026-02-14T10:02:10Z"},
    {"id": 3, "lineCount": 89, "createdOn": "2026-02-14T10:05:20Z"}
  ]
}
```

### 2.4 Récupérer log spécifique (GET)
- GET `/pipelines/{pipelineId}/runs/{runId}/logs/{logId}?api-version=7.1`
- Response (plain text):
```
2026-02-14T10:00:05.123Z Starting: Checkout sources
2026-02-14T10:00:05.456Z Cloning repository from refs/heads/main...
2026-02-14T10:00:06.789Z Successfully checked out commit abc123def
...
```

### 2.5 Annuler run
- Azure DevOps Pipelines API v7.1 does NOT provide direct DELETE/cancel endpoint
- Alternative: PATCH run with state=canceling (via Build API PATCH /builds/{buildId})
- Note: Pipeline run == Build in Azure DevOps. The Builds API provides PATCH for cancellation.

## 3. Authentification

### 3.1 Personal Access Token (PAT)
- Format: `Authorization: Basic <base64(:<PAT>)>` (username empty, password = PAT)
- Scopes minimaux: Build (read, execute), Pipeline (read)
- Recommandé pour scripts et automation

### 3.2 Microsoft Entra ID OAuth (production)
- OAuth 2.0 deprecated avril 2025, migration Entra ID
- Bearer token via Entra ID app registration
- Recommandé pour applications production

### 3.3 Intégration portail
- Réutilisation `build_auth_headers()` de Stories 27.1-27.2
- auth_flow="basic" pour PAT Azure DevOps (identique basic auth base64)
- auth_flow="pat" pour Bearer token via Entra ID

## 4. Mapping Statuts

| Statut Azure DevOps | Description | Mapping IDP Portal |
|-----|-----|-----|
| state=inProgress | Run en cours | RUNNING |
| state=completed, result=succeeded | Succès | COMPLETED |
| state=completed, result=failed | Échec | FAILED |
| state=completed, result=canceled | Annulé | CANCELLED |
| state=canceling | En cours d'annulation | RUNNING |

Note: Azure DevOps sépare `state` et `result`. L'adapter mappe les deux.

## 5. Webhooks vs Polling

### 5.1 Webhooks Service Hooks
- Azure DevOps Service Hooks pour envoyer événements vers endpoint externe
- Événements: Run completed, Run state changed
- Sécurité: HMAC SHA-1 checksum body webhook
- Nécessite configuration Service Hook côté organization Azure DevOps (LOW-1 FIX: "organization" anglais technique)

### 5.2 Stratégie portail: Polling 5s
- Identique AAP/Tower (Stories 27.1-27.2)
- Plus simple, fonctionne partout, pas de configuration Service Hooks nécessaire
- Celery task auto-rescheduling toutes les 5 secondes

## 6. Différences avec AAP/Tower

| Aspect | AAP/Tower | Azure DevOps |
|--------|-----------|--------------|
| Auth | Bearer token | Basic PAT (base64) |
| Base URL | `/api/v2/` | `/pipelines/` API v7.1 |
| Statuts | pending/waiting/running/successful/failed/error/canceled | state + result (inProgress/completed + succeeded/failed/canceled) |
| Logs | JSON/txt/ANSI, pagination start/end_line | Texte brut, par logId individuel |
| Temps réel | WebSocket natif | Webhooks Service Hooks ou polling |
| Lancement | POST /job_templates/{id}/launch/ (extra_vars) | POST /pipelines/{id}/runs (templateParameters, variables, resources) |
| Annulation | POST /jobs/{id}/cancel/ | PATCH /builds/{buildId} (status=cancelling) |

## 7. Points d'intégration

### 7.1 Flow monitoring temps réel
```
[Pipeline Run Azure DevOps en cours]
     | (Polling 5s Celery task)
     v
[AzureDevOpsAdapter.get_status() + get_job_logs()]
     | (via ExecutionService)
     v
[Update EXECUTION_STEPS.STATUS + OUTPUT/LOGS]
     | (via ExecutionConsumer.send())
     v
[Frontend WebSocket /ws/executions/{id}]
```

### 7.2 Composants réutilisés (Stories 27.1-27.2)
- ExecutionConsumer WebSocket broadcast
- _broadcast_execution_update() helper
- _update_execution_from_poll() helper
- ExecutionLogsView GET /executions/{id}/logs/
- build_auth_headers() (compatible PAT basic auth)

## 8. Diagramme de séquence

```
Client         Backend          AzureDevOpsAdapter       Azure DevOps
  |               |                    |                      |
  |--POST exec--->|                    |                      |
  |               |---trigger()------->|                      |
  |               |                    |---POST /runs-------->|
  |               |                    |<--{id, state}--------|
  |               |<--platform_job_id--|                      |
  |               |                    |                      |
  |               |  [Celery poll 5s]  |                      |
  |               |---get_status()---->|                      |
  |               |                    |---GET /runs/{id}---->|
  |               |                    |<--{state, result}----|
  |               |---get_job_logs()-->|                      |
  |               |                    |---GET /runs/{id}/logs|
  |               |                    |<--[logId list]-------|
  |               |                    |---GET /logs/{logId}->|
  |               |                    |<--plain text---------|
  |               |<--{status, logs}---|                      |
  |<--WS update---|                    |                      |
```

## Références

- Azure DevOps Pipelines REST API v7.1
- Runs - Run Pipeline
- Runs - Get
- Logs - List / Logs - Get
- Use Personal Access Tokens
- Webhooks with Azure DevOps (Service Hooks)
