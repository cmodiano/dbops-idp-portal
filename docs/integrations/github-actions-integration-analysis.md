# Analyse intégration GitHub Actions REST API v3

**Story 27.4** — Adapter GitHub Actions : workflow runs, logs, monitoring temps réel (webhooks/polling)

## Vue d'ensemble API

- **Version API** : v3 (header `X-GitHub-Api-Version: 2022-11-28`)
- **Base URL** : `https://api.github.com` (GitHub.com) ou `https://github.entreprise.com/api/v3` (Enterprise)

## Endpoints principaux

| Opération | Méthode | Endpoint | Notes |
|-----------|---------|----------|-------|
| Lancer workflow | POST | `/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches` | Retourne 204 No Content (pas de run_id) |
| Récupérer run_id | GET | `/repos/{owner}/{repo}/actions/runs?event=workflow_dispatch&created=>{timestamp}&per_page=1` | Polling intelligent post-trigger |
| Statut run | GET | `/repos/{owner}/{repo}/actions/runs/{run_id}` | status + conclusion |
| Logs run | GET | `/repos/{owner}/{repo}/actions/runs/{run_id}/logs` | Redirect ZIP expirante 1 min |
| Annuler run | POST | `/repos/{owner}/{repo}/actions/runs/{run_id}/cancel` | 202 Accepted |

## Paramètres workflow_dispatch

- `ref` (string, required) : Branch ou tag (ex: `"main"`, `"v1.0.0"`)
- `inputs` (object, optional) : Paramètres workflow YAML (max 25 propriétés)

## Format statut (2 champs)

- **`status`** : `queued`, `in_progress`, `completed`
- **`conclusion`** (seulement quand status=completed) : `success`, `failure`, `cancelled`, `timed_out`, `action_required`, `skipped`, `null`

## Mapping statuts GitHub Actions → IDP Portal

| Statut GitHub Actions | Mapping IDP Portal |
|-----------------------|--------------------|
| `queued` | `SUBMITTED` |
| `in_progress` | `RUNNING` |
| `completed:success` | `COMPLETED` |
| `completed:failure` | `FAILED` |
| `completed:cancelled` | `CANCELLED` |
| `completed:timed_out` | `FAILED` |
| `completed:action_required` | `SUBMITTED` |
| `completed:skipped` | `CANCELLED` |

## Authentification

- **Fine-grained PAT (recommandé 2026)** : `Authorization: Bearer <TOKEN>` + headers `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`
- **Classic PAT** : `Authorization: Bearer <TOKEN>`, scope `repo`
- **GitHub App** : Installation/user access tokens, permissions "Actions" read+write

Compatible avec `build_auth_headers()` existant (Bearer token).

## Webhooks GitHub Actions

- **Événement** : `workflow_run` (activity types : `requested`, `in_progress`, `completed`)
- **Sécurité** : Header `X-Hub-Signature-256` = `sha256=HMAC(secret, body)` SHA-256
- **Configuration** : Repository Settings → Webhooks → Payload URL + secret + events

### Payload webhook

```json
{
  "action": "completed",
  "workflow_run": {
    "id": 1234567,
    "status": "completed",
    "conclusion": "success",
    "html_url": "...",
    "logs_url": "..."
  },
  "repository": {"full_name": "owner/repo"},
  "sender": {"login": "user"}
}
```

## Approche monitoring : Hybride (Webhooks primaire + Polling catch-up)

- **Webhooks primaire** : Latence minimale, pas de consommation rate limit
- **Polling fallback** : 30-60s intervalle pour catch-up si webhook manqué
- **Rate limits** : PAT 5,000 req/h, Enterprise Cloud 15,000 req/h

## Gestion run_id après trigger

**Problème** : `POST /dispatches` retourne 204 No Content.
**Solution** : Attendre 2-5s puis GET /runs avec filtres `event=workflow_dispatch&created=>{timestamp}&per_page=1`.

## Récupération logs (Archive ZIP)

- Disponibles seulement si `status == completed`
- Archive ZIP via redirect S3 signée (expire 1 min)
- Extraire en mémoire avec `zipfile`, concaténer logs jobs

## Différences avec AAP/Tower/Azure DevOps

| Aspect | GitHub Actions | Azure DevOps | AAP/Tower |
|--------|---------------|--------------|-----------|
| Structure status | 2 champs (status + conclusion) | 2 champs (state + result) | 1 champ |
| Logs | Archive ZIP redirect 1 min | Multiples endpoints log ID | Endpoint direct |
| Temps réel | Webhooks workflow_run ou polling | Polling | Polling |
| Auth | Bearer PAT/App | Basic PAT | Basic/Bearer |
| Trigger retour | 204 No Content (pas run_id) | 200 OK run object | 201 job_id |
| Paramètres owner/repo | Requis partout | Organisation/projet URL | Pas nécessaire |

## Diagramme de séquence

```
Frontend → API Backend → ExecutionService → GitHubActionsAdapter → GitHub Actions API
                                                                    ↓
                                                              204 No Content
                                                                    ↓
                                                              Polling run_id
                                                                    ↓
                                                              run_id trouvé
                                                                    ↓
GitHub Webhook ← workflow_run event ← GitHub Actions
       ↓
Webhook Endpoint → HMAC Validation → Update Execution → WebSocket Broadcast → Frontend
       ↓
(fallback) Polling catch-up task → get_status() → Update → WebSocket → Frontend
```

## Configuration intégration (INTEGRATIONS table)

```json
{
  "type": "github_actions",
  "base_url": "https://api.github.com",
  "owner": "my-org",
  "repo": "my-repo",
  "workflow_id": "deploy.yaml",
  "default_ref": "main",
  "credential_ref": "vault://secrets/github/pat",
  "use_webhooks": true,
  "webhook_secret": "vault://secrets/github/webhook_secret",
  "polling_interval": 60,
  "verify_ssl": true
}
```

## Guide configuration authentification

### 1. Créer un Fine-grained PAT (recommandé 2026)

1. GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Créer token avec:
   - **Repository access**: Specific repositories → Sélectionner repo cible
   - **Permissions**:
     - Actions: Read and write
     - Contents: Read
     - Metadata: Read (auto-selected)
   - **Expiration**: 90 jours max recommandé
3. **Stocker dans Vault**:
   ```bash
   vault kv put secrets/github/pat token="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```

### 2. Configurer webhook GitHub

1. Repository → Settings → Webhooks → Add webhook
2. **Payload URL**: `https://<idp-portal-domain>/api/v1/webhooks/github/workflow_run`
3. **Content type**: `application/json`
4. **Secret**: Générer secret fort 32+ caractères
5. **Which events**: Workflow runs
6. **Active**: ✓
7. **Stocker secret dans Vault**:
   ```bash
   vault kv put secrets/github/webhook_secret value="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```
8. **Configurer setting Django**:
   ```python
   # settings.py ou .env
   GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
   ```

### 3. Factory usage avec owner/repo

```python
from adapters import get_platform_adapter
from adapters.utils import build_auth_headers

adapter = get_platform_adapter(
    platform_type="github_actions",
    base_url="https://api.github.com",
    auth_headers=build_auth_headers(credential),  # Bearer token
    owner="my-org",  # REQUIRED
    repo="my-repo",  # REQUIRED
    verify_ssl=True,  # SSL validation enabled (default)
)
```

### 4. Sécurité SSL

Par défaut `verify_ssl=True` (validation SSL activée). Pour environnements dev avec certificats custom:
```python
adapter = GitHubActionsAdapter(
    ...,
    verify_ssl=False,  # Désactiver SEULEMENT en dev avec CA custom
)
```

⚠️ **JAMAIS désactiver SSL en production** (risque MITM attack)
