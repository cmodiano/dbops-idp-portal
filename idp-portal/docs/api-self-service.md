# API Self-Service — Exécution d'actions sans frontend

Ce document décrit comment utiliser l'API du portail IDP pour déclencher des exécutions d'actions en self-service, sans passer par l'interface graphique.

## Vue d'ensemble

L'API permet à des scripts, pipelines CI/CD ou outils internes de déclencher des actions du catalogue. Les exécutions créées via l'API sont visibles dans le portail (historique, timeline) et tracées dans l'audit SOC1.

## Authentification

### Obtention d'un token JWT

L'authentification utilise des tokens JWT (JSON Web Tokens). Deux méthodes sont disponibles :

#### 1. Via SAML (flow interactif)

Pour les cas d'usage occasionnels, vous pouvez obtenir un token via le flow SAML standard :

1. Ouvrez `https://portail.example.com/api/v1/auth/saml/login` dans un navigateur
2. Authentifiez-vous auprès de l'IdP
3. Récupérez le `access_token` depuis l'URL de callback : `#access_token=...`

> **Note** : Ce token a une durée de vie de 30 minutes par défaut. Utilisez le refresh token (cookie httpOnly) pour le renouveler.

#### 2. Mode développement (AUTH_DEV_BYPASS)

En environnement de développement avec `AUTH_DEV_BYPASS=true`, un token est généré automatiquement :

```bash
# Le serveur redirige vers le frontend avec un token dev
curl -s -I http://localhost:8000/api/v1/auth/saml/login
# Extraire le token depuis le header Location
```

#### 3. Token long-lived (à venir)

Pour l'automatisation en production, un mécanisme de tokens long-lived ou API keys sera implémenté (voir backlog / roadmap).

### Utilisation du token

Incluez le token dans le header `Authorization` de chaque requête :

```
Authorization: Bearer <votre_token_jwt>
```

## Endpoint POST /api/v1/executions

### Description

Crée une nouvelle exécution pour une action du catalogue.

### Requête

```http
POST /api/v1/executions HTTP/1.1
Host: portail.example.com
Authorization: Bearer <token>
Content-Type: application/json
X-Idp-Request-Id: <correlation_id_optionnel>

{
  "action_id": 42,
  "target_names": ["srv-dev-oracle-01", "srv-dev-oracle-02"],
  "parameters": {
    "database_name": "TESTDB",
    "operation": "backup"
  }
}
```

### Paramètres

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `action_id` | int | Oui | ID de l'action à exécuter (doit être publiée) |
| `target_names` | list[str] | Oui* | Liste des noms de targets sur lesquels exécuter l'action |
| `parameters` | object | Non | Paramètres spécifiques à l'action |

> **Note** : `target_names` est requis pour les actions avec `requires_target=True`. Pour les autres, vous pouvez utiliser `environment` à la place.

### Réponse succès (201 Created)

```json
{
  "data": {
    "execution_id": 123,
    "status": "SUBMITTED",
    "created_at": "2026-02-05T14:30:00Z"
  }
}
```

### Réponses d'erreur

#### 400 Bad Request — Payload invalide

```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "target_names est requis pour cette action",
    "details": {
      "action_id": 42,
      "requires_target": true
    }
  }
}
```

#### 401 Unauthorized — Token absent ou invalide

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Token invalide ou expire",
    "details": {}
  }
}
```

#### 403 Forbidden — Target non autorisé

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Cible non autorisée: srv-prod-01",
    "details": {
      "target_name": "srv-prod-01"
    }
  }
}
```

#### 404 Not Found — Action inexistante

```json
{
  "error": {
    "code": "ACTION_NOT_FOUND",
    "message": "Action non trouvée",
    "details": {
      "action_id": 999
    }
  }
}
```

## Exemples

### Curl — Exécution simple

```bash
#!/bin/bash

# Configuration
API_URL="https://portail.example.com/api/v1"
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
CORRELATION_ID=$(uuidgen)

# Déclencher une exécution
curl -X POST "${API_URL}/executions" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Idp-Request-Id: ${CORRELATION_ID}" \
  -d '{
    "action_id": 42,
    "target_names": ["srv-dev-oracle-01"],
    "parameters": {
      "database_name": "TESTDB"
    }
  }'

# Réponse attendue :
# {"data": {"execution_id": 123, "status": "SUBMITTED", "created_at": "..."}}
```

### Curl — Suivre le statut

```bash
# Récupérer le statut de l'exécution
EXECUTION_ID=123

curl -X GET "${API_URL}/executions/${EXECUTION_ID}" \
  -H "Authorization: Bearer ${TOKEN}"

# Récupérer les étapes de l'exécution
curl -X GET "${API_URL}/executions/${EXECUTION_ID}/steps" \
  -H "Authorization: Bearer ${TOKEN}"
```

### Python avec requests

```python
#!/usr/bin/env python3
"""
Exemple d'utilisation de l'API IDP Portal pour déclencher une exécution.
"""

import uuid
import requests

# Configuration
API_URL = "https://portail.example.com/api/v1"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

def create_execution(action_id: int, target_names: list[str], parameters: dict = None):
    """Déclenche une exécution via l'API."""
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "X-Idp-Request-Id": str(uuid.uuid4()),
    }

    payload = {
        "action_id": action_id,
        "target_names": target_names,
    }
    if parameters:
        payload["parameters"] = parameters

    response = requests.post(
        f"{API_URL}/executions",
        headers=headers,
        json=payload,
    )

    if response.status_code == 201:
        data = response.json()["data"]
        print(f"✅ Exécution créée: ID={data['execution_id']}, Status={data['status']}")
        return data["execution_id"]
    else:
        error = response.json().get("error", {})
        print(f"❌ Erreur {response.status_code}: {error.get('message')}")
        raise Exception(error.get("message"))


def get_execution_status(execution_id: int):
    """Récupère le statut d'une exécution."""
    headers = {"Authorization": f"Bearer {TOKEN}"}

    response = requests.get(
        f"{API_URL}/executions/{execution_id}",
        headers=headers,
    )

    if response.status_code == 200:
        return response.json()["data"]
    else:
        raise Exception(f"Erreur {response.status_code}")


def wait_for_completion(execution_id: int, timeout_seconds: int = 300):
    """Attend la fin de l'exécution (polling)."""
    import time

    terminal_statuses = {"COMPLETED", "FAILED", "CANCELLED", "REJECTED"}
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        status = get_execution_status(execution_id)
        print(f"  Status: {status['status']}")

        if status["status"] in terminal_statuses:
            return status

        time.sleep(5)  # Polling interval

    raise TimeoutError(f"Timeout après {timeout_seconds}s")


if __name__ == "__main__":
    # Exemple d'utilisation
    execution_id = create_execution(
        action_id=42,
        target_names=["srv-dev-oracle-01"],
        parameters={"database_name": "TESTDB"},
    )

    print("⏳ En attente de la fin de l'exécution...")
    final_status = wait_for_completion(execution_id)
    print(f"✅ Terminé: {final_status['status']}")
```

## Traçabilité et audit

### Correlation ID

Utilisez le header `X-Idp-Request-Id` pour tracer les requêtes dans les logs :

```bash
curl -H "X-Idp-Request-Id: $(uuidgen)" ...
```

Ce correlation ID sera :
- Retourné dans le header de réponse
- Inclus dans les logs du backend
- Enregistré dans l'audit SOC1

### Audit SOC1

Chaque exécution créée via l'API est tracée dans l'audit avec :
- **source** : `"api"` (vs `"ui"` pour les exécutions via le portail)
- **ip_address** : Adresse IP du client
- **correlation_id** : ID de corrélation de la requête
- **user_id** : Identité issue du token JWT
- **action_id**, **targets**, **environment**, **parameters** : Détails de l'exécution

## Erreurs courantes et résolution

| Erreur | Cause | Solution |
|--------|-------|----------|
| 401 "Token invalide ou expire" | Token JWT expiré | Rafraîchir le token via `/auth/refresh` ou se reconnecter |
| 403 "Cible non autorisée" | Target non permis par le profil | Vérifier les permissions du profil ou utiliser un autre target |
| 400 "target_names requis" | Action nécessite des targets | Ajouter `target_names` avec au moins un target valide |
| 400 "environnements différents" | Targets de plusieurs environnements | Utiliser des targets du même environnement |
| 404 "Action non trouvée" | Action inexistante ou non publiée | Vérifier l'action_id et son statut dans le catalogue |

## Limites et bonnes pratiques

1. **Rate limiting** : Pas de rate limiting pour le MVP, mais prévoir un délai entre les appels en batch
2. **Timeout** : Les requêtes timeout après 120 secondes — pour les exécutions longues, utilisez le polling
3. **Idempotence** : Chaque appel crée une nouvelle exécution — utilisez le correlation ID pour éviter les doublons
4. **Taille payload** : Limiter les paramètres à quelques KB

## Voir aussi

Liens relatifs à la base URL du portail (ex. `https://portail.example.com`) :

- Documentation API complète (OpenAPI/Swagger) : `/api/docs`
- Guide d'administration des actions : `/docs/admin-actions.md`
- Architecture RBAC et permissions : `/docs/rbac.md`
