# Integration Jira

> Story 27.10 — JiraService comme service consomme (pas un adapter de plateforme).

## Architecture

Jira est un **service consomme** par le portail IDP pour la gestion d'issues. Il n'herite pas de `BaseAdapter` et n'execute pas de jobs.

```
ExecutionService
  └── JiraService (services/jira_service.py)
        ├── create_issue()   — POST /rest/api/3/issue
        ├── update_issue()   — PUT  /rest/api/3/issue/{key}
        ├── get_issue()      — GET  /rest/api/3/issue/{key}
        └── add_comment()    — POST /rest/api/3/issue/{key}/comment
```

**Factory :** `get_service_client("jira", base_url=..., auth_headers=...)`

## API Jira supportee

### Endpoints

| Action | Methode | URL | Status code |
|--------|---------|-----|-------------|
| `create_issue` | POST | `/rest/api/3/issue` | 201 Created |
| `update_issue` | PUT | `/rest/api/3/issue/{issueIdOrKey}` | 204 No Content |
| `get_issue` | GET | `/rest/api/3/issue/{issueIdOrKey}` | 200 OK |
| `add_comment` | POST | `/rest/api/3/issue/{issueIdOrKey}/comment` | 201 Created |

> **Cloud** utilise API v3, **Server/Data Center** utilise API v2. Le JiraService utilise v3 par defaut. Pour Server, ajuster la base_url si necessaire.

## Authentification

### Jira Cloud (recommande)

Basic Auth avec email + API token :

```python
import base64

email = "user@example.com"
api_token = "votre-api-token"  # depuis vault
credentials = base64.b64encode(f"{email}:{api_token}".encode()).decode()

auth_headers = {
    "Authorization": f"Basic {credentials}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
```

### Jira Server / Data Center

**Option 1 — Basic Auth :**
```python
credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
auth_headers = {"Authorization": f"Basic {credentials}"}
```

**Option 2 — Personal Access Token (PAT) :**
```python
auth_headers = {"Authorization": f"Bearer {pat_token}"}
```

### Resolution via Vault

```python
from services.vault_service import get_vault_service

vault = get_vault_service()
api_token = vault.get_secret(
    "vault:secret/data/jira/cloud#api_token",
    correlation_id=correlation_id,
)
```

**Format credential_ref :**
- Cloud : `vault:secret/data/jira/cloud#api_token`
- Server : `vault:secret/data/jira/server#pat`

## Exemples d'utilisation

### Creer une issue

```python
from services import get_service_client

jira = get_service_client(
    "jira",
    base_url="https://jira.example.com",
    auth_headers={"Authorization": "Basic dGVzdDp0ZXN0"},
)

result = await jira.create_issue(
    project_key="PROJ",
    issue_type="Task",
    summary="Deployer patch Oracle PSU",
    description="Appliquer le patch PSU sur les instances production",
    assignee="john.doe",
    labels=["production", "oracle"],
    correlation_id="exec-abc-123",
)
# {"issue_key": "PROJ-456", "issue_id": "10001", "url": "https://..."}
```

### Mettre a jour une issue

```python
result = await jira.update_issue(
    "PROJ-456",
    status="Done",
    labels=["production", "oracle", "completed"],
    correlation_id="exec-abc-123",
)
# {"issue_key": "PROJ-456", "status": "updated"}
```

### Recuperer une issue

```python
issue = await jira.get_issue("PROJ-456", correlation_id="exec-abc-123")
# Full Jira issue data dict
```

### Ajouter un commentaire

```python
result = await jira.add_comment(
    "PROJ-456",
    "Patch applique avec succes sur toutes les instances.",
    correlation_id="exec-abc-123",
)
# {"comment_id": "10042", "issue_key": "PROJ-456", "url": "https://..."}
```

## Error Handling

| Code HTTP | Code erreur | Description |
|-----------|-------------|-------------|
| 401 | `JIRA_AUTH_FAILED` | Credential invalide (token expire, email incorrect) |
| 403 | `JIRA_PERMISSION_DENIED` | Permissions insuffisantes (projet, issue) |
| 404 | `JIRA_RESOURCE_NOT_FOUND` | Projet ou issue inexistant |
| 429 | `JIRA_RATE_LIMITED` | Rate limit atteint |
| 500 | `JIRA_SERVER_ERROR` | Erreur serveur Jira (retry automatique) |
| 503 | `JIRA_SERVER_ERROR` | Service indisponible (retry automatique) |
| timeout | `JIRA_TIMEOUT` | Timeout apres 3 tentatives |

### Retry Logic

- **Erreurs retryables** : 500, 503, timeout (`httpx.TimeoutException`)
- **Max retries** : 3 tentatives
- **Backoff exponentiel** : 2s, 4s, 8s
- **Erreurs non-retryables** : 401, 403, 404, 429 (echec immediat)

Toutes les exceptions sont de type `ServiceUnavailableError` (defini dans `core/exceptions.py`).

## Troubleshooting

### 401 Unauthorized

- **Cloud** : Verifier que l'API token est valide (https://id.atlassian.com/manage-profile/security/api-tokens)
- **Server** : Verifier username/password ou que le PAT n'est pas expire
- **Vault** : Verifier le `credential_ref` et que le secret existe dans Vault

### 403 Forbidden

- Verifier que l'utilisateur a les permissions sur le projet Jira
- Verifier les scopes de l'API token (Cloud)
- Verifier les roles du projet (Browse Projects, Create Issues, etc.)

### 404 Not Found

- Verifier que le `project_key` existe dans Jira
- Verifier que l'`issue_key` est correct (format: PROJ-123)
- Verifier que la base_url pointe vers la bonne instance

### Timeout

- Le timeout par defaut est 30 secondes
- Augmenter via `timeout=60.0` si necessaire
- Verifier la connectivite reseau vers l'instance Jira

### Rate Limiting (429)

- Jira Cloud a des limites de rate par defaut
- Le JiraService ne retente pas automatiquement sur 429
- Implementer un backoff cote appelant si necessaire
