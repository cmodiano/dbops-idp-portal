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

#### 3. Via API key (programmatique)


Pour l'automatisation en production (scripts, CI/CD), utilisez une API key pour obtenir un token JWT sans interaction navigateur :

**Prérequis :** Une API key doit avoir été créée et communiquée par l'équipe DBOPS.

**Étape 1 — Obtenir un token :**

```bash
curl -s -X POST https://portail.example.com/api/v1/auth/token \
  -H "X-API-Key: <votre_api_key>"
```

**Réponse :**
```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 1800
  }
}
```

**Étape 2 — Utiliser le token :**

Incluez le token dans le header `Authorization` pour les appels suivants :
```
Authorization: Bearer <access_token>
```

> **Note :** Le token a une durée de vie de 30 minutes. Après expiration, répétez l'étape 1 pour obtenir un nouveau token. Le rate limiting est de 10 requêtes/minute par IP sur cet endpoint.

**Erreurs possibles :**

| Code | Signification |
|------|--------------|
| `MISSING_API_KEY` | Le header `X-API-Key` est absent ou vide |
| `INVALID_API_KEY` | La clé est invalide, révoquée ou expirée |
| 429 Too Many Requests | Rate limit atteint (10 req/min par IP) |

#### 4. Via LDAP (comptes de service — authentification programmatique)

Pour les pipelines CI/CD et scripts d'automatisation utilisant un compte Active Directory dédié, sans nécessiter de clé API.

**Cas d'usage :** Le compte de service `svc-ci-cd` doit déclencher des actions automatisées sans interaction humaine et sans clé API gérée manuellement.

**Prérequis :**
1. Un compte Active Directory valide (username + password connus)
2. Le compte appartient à au moins un groupe AD mappé à un profil dans le portail IDP (ex. `CN=GRP-IDP-DBOPS,OU=Groups,DC=example,DC=com`)
3. Le profil associé dispose des permissions nécessaires sur les actions et targets à utiliser
4. Le serveur LDAP est configuré et accessible depuis le portail IDP (cf. [`docs/backend/ldap-configuration.md`](backend/ldap-configuration.md))

**Flow :** Le portail IDP effectue un bind LDAP avec vos credentials, récupère vos groupes AD, résout votre profil, et émet un JWT — exactement comme un login SAML, mais de façon programmatique.

**Étape 1 — Obtenir un token JWT :**

```bash
curl -s -X POST https://portail.example.com/api/v1/auth/service-login \
  -H "Content-Type: application/json" \
  -d '{"username": "svc-ci-cd", "password": "..."}'
```

**Réponse :**
```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 1800
  }
}
```

> **Note :** Le mot de passe n'est jamais enregistré ni retourné. Chaque tentative (succès ou échec) est tracée dans l'audit avec le type `SERVICE_LOGIN`. Le rate limiting est de 5 requêtes/minute par IP (vs 10/min pour `/auth/token` via API key).

**Étape 2 — Utiliser le token :**

Incluez le token dans le header `Authorization` pour les appels suivants :
```
Authorization: Bearer <access_token>
```

**Erreurs possibles :**

| Code | Signification |
|------|--------------|
| 401 `INVALID_CREDENTIALS` | Username ou password incorrect, ou compte AD inexistant |
| 503 `LDAP_UNAVAILABLE` | Le serveur LDAP est inaccessible ou non configuré |
| 403 `NO_PROFILE` | Le compte n'appartient à aucun groupe AD mappé à un profil IDP |
| 429 Too Many Requests | Rate limit atteint (5 req/min par IP) |

**Bash — Obtention de token LDAP + exécution complète :**

```bash
#!/bin/bash
set -euo pipefail

# Configuration
API_URL="https://portail.example.com/api/v1"
LDAP_USER="svc-ci-cd"
LDAP_PASSWORD="${IDP_LDAP_PASSWORD:?La variable IDP_LDAP_PASSWORD doit être définie}"
CORRELATION_ID=$(uuidgen)

# Étape 1 : Obtenir un token JWT via LDAP
echo "🔑 Authentification LDAP..."
TOKEN_RESPONSE=$(curl -s -f -X POST "${API_URL}/auth/service-login" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"${LDAP_USER}\", \"password\": \"${LDAP_PASSWORD}\"}")

ACCESS_TOKEN=$(echo "${TOKEN_RESPONSE}" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")
echo "✅ Token obtenu (valide 30 min)"

# Étape 2 : Déclencher une exécution
echo "🚀 Déclenchement de l'exécution..."
EXEC_RESPONSE=$(curl -s -f -X POST "${API_URL}/executions" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Idp-Request-Id: ${CORRELATION_ID}" \
  -d '{
    "action_id": 42,
    "target_names": ["srv-dev-oracle-01"],
    "parameters": {"database_name": "TESTDB"}
  }')

EXECUTION_ID=$(echo "${EXEC_RESPONSE}" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['execution_id'])")
echo "✅ Exécution créée : ID=${EXECUTION_ID}"

# Étape 3 : Attendre la fin (polling)
echo "⏳ Attente de la fin..."
TERMINAL_STATUSES=("COMPLETED" "FAILED" "CANCELLED" "REJECTED")
for i in $(seq 1 60); do
  STATUS_RESPONSE=$(curl -s -H "Authorization: Bearer ${ACCESS_TOKEN}" "${API_URL}/executions/${EXECUTION_ID}")
  STATUS=$(echo "${STATUS_RESPONSE}" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['status'])")
  echo "  [${i}/60] Status: ${STATUS}"

  for ts in "${TERMINAL_STATUSES[@]}"; do
    if [ "${STATUS}" = "${ts}" ]; then
      echo "✅ Terminé : ${STATUS}"
      exit $([ "${STATUS}" = "COMPLETED" ] && echo 0 || echo 1)
    fi
  done

  sleep 5
done

echo "❌ Timeout : l'exécution n'est pas terminée après 5 minutes"
exit 1
```

**Python avec requests :**

```python
#!/usr/bin/env python3
"""
Exemple d'utilisation de l'API IDP Portal avec authentification LDAP
pour un compte de service.
"""

import os
import uuid
import requests

# Configuration
API_URL = "https://portail.example.com/api/v1"
LDAP_USER = "svc-ci-cd"
LDAP_PASSWORD = os.environ["IDP_LDAP_PASSWORD"]


def get_token_via_ldap(username: str, password: str) -> str:
    """Obtient un JWT via authentification LDAP."""
    response = requests.post(
        f"{API_URL}/auth/service-login",
        json={"username": username, "password": password},
    )

    if response.status_code == 200:
        data = response.json()["data"]
        print(f"✅ Token obtenu (expire dans {data['expires_in']}s)")
        return data["access_token"]
    else:
        error = response.json().get("error", {})
        raise Exception(f"Authentification LDAP échouée [{response.status_code}]: {error.get('code')} — {error.get('message')}")


def create_execution(access_token: str, action_id: int, target_names: list[str], parameters: dict = None) -> int:
    """Déclenche une exécution via l'API."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Idp-Request-Id": str(uuid.uuid4()),
    }

    payload = {"action_id": action_id, "target_names": target_names}
    if parameters:
        payload["parameters"] = parameters

    response = requests.post(f"{API_URL}/executions", headers=headers, json=payload)

    if response.status_code == 201:
        data = response.json()["data"]
        print(f"✅ Exécution créée: ID={data['execution_id']}, Status={data['status']}")
        return data["execution_id"]
    else:
        error = response.json().get("error", {})
        raise Exception(f"Erreur {response.status_code}: {error.get('message')}")


if __name__ == "__main__":
    token = get_token_via_ldap(LDAP_USER, LDAP_PASSWORD)

    execution_id = create_execution(
        access_token=token,
        action_id=42,
        target_names=["srv-dev-oracle-01"],
        parameters={"database_name": "TESTDB"},
    )
    print(f"✅ Exécution {execution_id} soumise avec succès")
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

### Bash — Obtention de token via API key + exécution

```bash
#!/bin/bash
set -euo pipefail

# Configuration
API_URL="https://portail.example.com/api/v1"
API_KEY="${IDP_API_KEY:?La variable IDP_API_KEY doit être définie}"
CORRELATION_ID=$(uuidgen)

# Étape 1 : Obtenir un token JWT via l'API key
echo "🔑 Obtention du token..."
TOKEN_RESPONSE=$(curl -s -f -X POST "${API_URL}/auth/token" \
  -H "X-API-Key: ${API_KEY}")

ACCESS_TOKEN=$(echo "${TOKEN_RESPONSE}" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")
echo "✅ Token obtenu (valide 30 min)"

# Étape 2 : Déclencher une exécution
echo "🚀 Déclenchement de l'exécution..."
EXEC_RESPONSE=$(curl -s -f -X POST "${API_URL}/executions" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Idp-Request-Id: ${CORRELATION_ID}" \
  -d '{
    "action_id": 42,
    "target_names": ["srv-dev-oracle-01"],
    "parameters": {"database_name": "TESTDB"}
  }')

EXECUTION_ID=$(echo "${EXEC_RESPONSE}" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['execution_id'])")
echo "✅ Exécution créée : ID=${EXECUTION_ID}"

# Étape 3 : Attendre la fin (polling)
echo "⏳ Attente de la fin..."
TERMINAL_STATUSES=("COMPLETED" "FAILED" "CANCELLED" "REJECTED")
for i in $(seq 1 60); do
  STATUS_RESPONSE=$(curl -s -H "Authorization: Bearer ${ACCESS_TOKEN}" "${API_URL}/executions/${EXECUTION_ID}")
  STATUS=$(echo "${STATUS_RESPONSE}" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['status'])")
  echo "  [${i}/60] Status: ${STATUS}"

  for ts in "${TERMINAL_STATUSES[@]}"; do
    if [ "${STATUS}" = "${ts}" ]; then
      echo "✅ Terminé : ${STATUS}"
      exit $([ "${STATUS}" = "COMPLETED" ] && echo 0 || echo 1)
    fi
  done

  sleep 5
done

echo "❌ Timeout : l'exécution n'est pas terminée après 5 minutes"
exit 1
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

| Erreur | Endpoint | Cause | Solution |
|--------|----------|-------|----------|
| 401 `MISSING_API_KEY` | `/auth/token` | Le header `X-API-Key` est absent | Ajouter le header `X-API-Key` à la requête `/auth/token` |
| 401 `INVALID_API_KEY` | `/auth/token` | Clé invalide, révoquée ou expirée | Contacter l'équipe DBOPS pour obtenir une nouvelle clé |
| 429 Too Many Requests | `/auth/token` | Rate limit atteint (10/min par IP) | Attendre 1 minute avant de réessayer |
| 401 `INVALID_CREDENTIALS` | `/auth/service-login` | Username/password incorrect ou compte AD inexistant | Vérifier les credentials du compte de service |
| 503 `LDAP_UNAVAILABLE` | `/auth/service-login` | Serveur LDAP inaccessible ou non configuré | Contacter l'équipe DBOPS — vérifier la configuration LDAP |
| 403 `NO_PROFILE` | `/auth/service-login` | Le compte n'appartient à aucun groupe AD mappé à un profil | Contacter l'équipe DBOPS pour associer le compte à un profil |
| 429 Too Many Requests | `/auth/service-login` | Rate limit atteint (5/min par IP) | Attendre 1 minute avant de réessayer |
| 401 "Token invalide ou expire" | `/executions` | Token JWT expiré | Rafraîchir le token via `/auth/refresh` ou répéter l'étape 1 |
| 403 "Cible non autorisée" | `/executions` | Target non permis par le profil | Vérifier les permissions du profil ou utiliser un autre target |
| 400 "target_names requis" | `/executions` | Action nécessite des targets | Ajouter `target_names` avec au moins un target valide |
| 400 "environnements différents" | `/executions` | Targets de plusieurs environnements | Utiliser des targets du même environnement |
| 404 "Action non trouvée" | `/executions` | Action inexistante ou non publiée | Vérifier l'action_id et son statut dans le catalogue |

## Limites et bonnes pratiques

1. **Rate limiting** : L'endpoint `/auth/token` est limité à 10 requêtes/minute par IP (protection brute-force) ; `/auth/service-login` est limité à 5 requêtes/minute par IP. Pour les appels à `/executions`, prévoir un délai entre les appels en batch
2. **Timeout** : Les requêtes timeout après 120 secondes — pour les exécutions longues, utilisez le polling
3. **Idempotence** : Chaque appel crée une nouvelle exécution — utilisez le correlation ID pour éviter les doublons
4. **Taille payload** : Limiter les paramètres à quelques KB

## Voir aussi

Liens relatifs à la base URL du portail (ex. `https://portail.example.com`) :

- Documentation API complète (OpenAPI/Swagger) : `/api/docs`
- Référence complète des endpoints : [`docs/backend/api-reference.md`](backend/api-reference.md)
- Configuration LDAP pour comptes de service : [`docs/backend/ldap-configuration.md`](backend/ldap-configuration.md)
- Guide d'administration des actions : `/docs/admin-actions.md`
- Architecture RBAC et permissions : `/docs/rbac.md`
