# services/ — Services consommes

Ce package contient les **clients de services externes** consommes par le
portail IDP pour des fonctions transversales.

## Principe

Chaque service :
- Encapsule l'acces a un service externe (secrets, logs, ITSM)
- N'herite **pas** de `BaseAdapter` (ce ne sont pas des plateformes d'execution)
- Possede sa propre interface adaptee a son domaine

## Services disponibles

| Service | Fichier | Role |
|---------|---------|------|
| `VaultService` | `vault_service.py` | Resolution des secrets via HashiCorp Vault (KV v2) |
| `SplunkService` | `splunk_service.py` | Envoi de logs structures vers Splunk HEC |
| `ServiceNowService` | `servicenow_service.py` | Gestion des changements ITSM ServiceNow |
| `JiraService` | `jira_service.py` | Gestion d'issues Jira (creation, mise a jour, commentaires) |
| `NotificationService` | `notification_service.py` | Envoi de notifications multi-destinations (email, Teams, page) |

## Factory

```python
from services import get_service_client

vault = get_service_client("vault", vault_addr="...", vault_token="...")
splunk = get_service_client("splunk", base_url="...", auth_headers={...})
jira = get_service_client("jira", base_url="...", auth_headers={...})
```

La factory `get_service_client()` retourne le client de service correspondant
au type demande.

**Note:** La factory `get_service_client()` est fournie pour symetrie avec
`get_platform_adapter()` et pour faciliter les tests. Dans le code de production,
les services sont generalement instancies directement ou via des singletons :
- `VaultService` : via `get_vault_service()` (singleton, ligne 502 vault_service.py)
- `SplunkService` : instancie directement dans `SplunkLoggingHandler`

## Exemples d'utilisation

### Utilisation directe (pattern actuel)
```python
from services.vault_service import get_vault_service

vault = get_vault_service()
secret = vault.get_secret("vault:secret/data/myapp/db#password")
```

### Utilisation via factory (tests, injection de dependances)
```python
from services import get_service_client

vault = get_service_client("vault", vault_addr="http://vault:8200", vault_token="test")
secret = vault.get_secret("vault:secret/data/myapp/db#password")
```

### Jira (Story 27.10)
```python
from services import get_service_client

jira = get_service_client(
    "jira",
    base_url="https://jira.example.com",
    auth_headers={"Authorization": "Basic <base64(email:api_token)>"},
)

# Creer une issue
result = await jira.create_issue(
    project_key="PROJ",
    issue_type="Task",
    summary="Deployer patch Oracle",
    description="Appliquer le patch PSU sur les instances production",
    correlation_id="abc-123",
)
# result = {"issue_key": "PROJ-456", "issue_id": "10001", "url": "..."}

# Ajouter un commentaire
await jira.add_comment("PROJ-456", "Patch applique avec succes", correlation_id="abc-123")
```

**Authentification Jira :**
- **Cloud** : Basic Auth `email:api_token` (encode base64)
- **Server/Data Center** : Basic Auth `username:password` ou Bearer PAT

### NotificationService (Story 31.8)
```python
from services.notification_service import NotificationService

notif = NotificationService()

# Envoi direct
notif.send_email("user@example.com", "Sujet", "Corps du message")
notif.send_teams("https://webhook.example.com/...", "Message Teams")

# Point d'entree principal — traite tous les canaux configures sur l'action
notif.notify_execution_event(
    execution=execution_obj,
    action=action_obj,
    event="on_failure",  # ou "on_success"
    page_me=True,
    page_me_user_id="user123",
    page_me_user_name="User Name",
    correlation_id="abc-123",
)
```

**Destinations :**
- **email** : `django.core.mail.send_mail()` via SMTP
- **teams** : POST webhook MessageCard
- **page_individual** : POST API interne (prod + critique uniquement)
- **page_dba** : POST API interne DBA on-call (prod + critique uniquement)

## A ne pas confondre

Les **adaptateurs de plateforme** (AAP, Tower, Azure DevOps, GitHub Actions,
Terraform Cloud) se trouvent dans le package `adapters/`. Ils heritent de
`BaseAdapter` et executent des jobs sur des plateformes distantes.
