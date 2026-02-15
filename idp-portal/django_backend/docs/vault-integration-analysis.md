# Analyse d'intégration HashiCorp Vault — Story 27.6

## 1. Vue d'ensemble

Le **VaultService** (`services/vault_service.py`) est le client centralisé pour HashiCorp Vault.
Tous les adapters de plateforme (AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud)
l'utilisent via `build_auth_headers()` pour résoudre les `credential_ref` en secrets
au moment de l'exécution.

### Principes

- **NFR7** : Aucun secret stocké dans le portail — récupération exclusive depuis Vault
- **NFR21** : En cas d'indisponibilité Vault, exécution refusée avec message explicite (pas de fallback)

## 2. API Vault KV v2

### Lecture d'un secret

```
GET /v1/{mount}/data/{path}
```

**Headers requis :**
- `X-Vault-Token: {token}` — authentification
- `X-Vault-Namespace: {namespace}` — Vault Enterprise uniquement (optionnel)

**Réponse (200 OK) :**
```json
{
  "data": {
    "data": {
      "username": "admin",
      "password": "s3cret"
    },
    "metadata": {
      "version": 3,
      "created_time": "2026-01-15T10:00:00Z"
    }
  }
}
```

### Codes HTTP

| Code | Signification | Retry ? | Exception IDP |
|------|--------------|---------|---------------|
| 200 | Succès | — | — |
| 400 | Bad Request | Non | VaultUnavailableError |
| 403 | Forbidden | Non | VaultAccessDeniedError |
| 404 | Not Found | Non | VaultSecretNotFoundError |
| 500 | Internal Error | Oui (3x) | VaultUnavailableError |
| 502 | Bad Gateway | Oui (3x) | VaultUnavailableError |
| 503 | Service Unavailable | Oui (3x) | VaultUnavailableError |
| Timeout | Connexion | Oui (3x) | VaultUnavailableError |

## 3. Authentification

### Token (simple)

```bash
export VAULT_TOKEN=s.xxxxxxxxxxxxxxxx
```

Le token est passé via le header `X-Vault-Token`.

### AppRole (production)

```bash
export VAULT_ROLE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
export VAULT_SECRET_ID=yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy
```

Login AppRole :
```
POST /v1/auth/approle/login
{"role_id": "...", "secret_id": "..."}
```

Réponse :
```json
{
  "auth": {
    "client_token": "s.xxxxxxxx",
    "renewable": true,
    "lease_duration": 3600
  }
}
```

Le VaultService gère automatiquement :
- Login initial au démarrage
- Renouvellement du token avant expiration (si `renewable=true`)
- Stockage du token en mémoire (jamais persisté)

## 4. Format credential_ref

### Vault Open Source

```
vault:secret/data/path/to/secret#key
```

- `secret` = mount point KV v2
- `path/to/secret` = chemin du secret
- `#key` = clé spécifique (optionnel — sans `#key`, retourne tout le dict)

### Vault Enterprise (namespace)

```
vault:namespace/secret/data/path/to/secret#key
```

- `namespace` = namespace Vault Enterprise
- Ajoute le header `X-Vault-Namespace: {namespace}`

### Exemples

| credential_ref | mount | path | key | namespace |
|---------------|-------|------|-----|-----------|
| `vault:secret/data/aap/prod#token` | secret | aap/prod | token | — |
| `vault:secret/data/github/actions` | secret | github/actions | — (dict) | — |
| `vault:team-ops/secret/data/db#password` | secret | db | password | team-ops |

## 5. Résilience

### Retry avec backoff exponentiel

- **Tentatives** : 3 (configurable via `VAULT_MAX_RETRIES`)
- **Backoff** : 1s, 2s, 4s (`2^attempt`)
- **Erreurs transitoires** (retry) : HTTP 500, 502, 503, timeout, connexion refusée
- **Erreurs définitives** (pas de retry) : HTTP 400, 403, 404

### Circuit Breaker

```
[CLOSED] --5 échecs--> [OPEN] --60s--> [HALF-OPEN] --succès--> [CLOSED]
                                          |
                                          --échec--> [OPEN]
```

- **Seuil** : 5 échecs consécutifs
- **Timeout** : 60s
- En état **OPEN** : les appels sont rejetés immédiatement (`VaultUnavailableError`)
- En état **HALF-OPEN** : 1 appel de test autorisé
- Les erreurs définitives (404, 403) ne comptent PAS vers le circuit breaker

### Cache TTL

- **TTL** : 5 minutes (configurable via `VAULT_CACHE_TTL`)
- **Thread-safe** : `cachetools.TTLCache` + `threading.RLock`
- **Invalidation** :
  - `clear_cache()` — tout le cache
  - `clear_secret(credential_ref)` — un secret spécifique

## 6. Vault Open Source vs Enterprise

| Fonctionnalité | Open Source | Enterprise |
|---------------|-------------|------------|
| KV v2 Secrets | Oui | Oui |
| Auth Token | Oui | Oui |
| Auth AppRole | Oui | Oui |
| Namespaces | Non | Oui |
| Multi-tenancy | Non | Oui |
| Header X-Vault-Namespace | Ignoré | Requis si namespace |

Le VaultService supporte les deux versions. Si `VAULT_NAMESPACE` est vide et
qu'aucun namespace n'est dans le credential_ref, le header `X-Vault-Namespace`
n'est pas envoyé (compatible Vault Open Source).

## 7. Diagramme de séquence

```
Adapter                    build_auth_headers        VaultService            Vault API
   |                              |                       |                      |
   |-- build_auth_headers() ----->|                       |                      |
   |                              |-- get_secret() ------>|                      |
   |                              |                       |-- [check cache] ---->|
   |                              |                       |   (hit? return)      |
   |                              |                       |                      |
   |                              |                       |-- [circuit breaker]->|
   |                              |                       |   (open? reject)     |
   |                              |                       |                      |
   |                              |                       |-- GET /v1/.../data ->|
   |                              |                       |   + retry (3x)       |
   |                              |                       |<-- 200 {secret} -----|
   |                              |                       |                      |
   |                              |                       |-- [store cache] ---->|
   |                              |<-- secret value ------|                      |
   |<-- {"Authorization": "..."} -|                       |                      |
```

## 8. Configuration

### Variables d'environnement

| Variable | Requis | Défaut | Description |
|----------|--------|--------|-------------|
| `VAULT_ADDR` | Non | `http://localhost:8200` | URL serveur Vault |
| `VAULT_TOKEN` | Oui* | — | Token auth (prioritaire sur AppRole) |
| `VAULT_ROLE_ID` | Oui* | — | AppRole role_id |
| `VAULT_SECRET_ID` | Oui* | — | AppRole secret_id |
| `VAULT_NAMESPACE` | Non | — | Namespace Vault Enterprise global |
| `VAULT_CACHE_TTL` | Non | `300` | TTL cache en secondes |
| `VAULT_TIMEOUT` | Non | `10` | Timeout HTTP en secondes |
| `VAULT_MAX_RETRIES` | Non | `3` | Nombre max de tentatives |

*Il faut soit `VAULT_TOKEN`, soit `VAULT_ROLE_ID` + `VAULT_SECRET_ID`.

### Vault Policy minimale

```hcl
path "secret/data/*" {
  capabilities = ["read"]
}
```

## 9. Troubleshooting

### Circuit breaker open

**Symptôme** : `VaultUnavailableError: Circuit breaker open — Vault unavailable`

**Cause** : 5+ échecs consécutifs vers Vault.

**Solution** :
1. Vérifier que Vault est accessible : `curl $VAULT_ADDR/v1/sys/health`
2. Vérifier que le token est valide : `curl -H "X-Vault-Token: $VAULT_TOKEN" $VAULT_ADDR/v1/auth/token/lookup-self`
3. Le circuit breaker se ferme automatiquement après 60s si Vault redevient disponible
4. **NOUVEAU** : Consulter `docs/vault-troubleshooting-circuit-breaker.md` pour monitoring détaillé (LOW-1 fix)

### Auth failed (403)

**Symptôme** : `VaultAccessDeniedError: Access denied to secret`

**Cause** : Token invalide ou policy insuffisante.

**Solution** :
1. Vérifier le token : `vault token lookup`
2. Vérifier la policy : `vault token capabilities secret/data/path`
3. Pour AppRole : vérifier `VAULT_ROLE_ID` et `VAULT_SECRET_ID`

### Secret not found (404)

**Symptôme** : `VaultSecretNotFoundError: Secret not found`

**Cause** : Chemin incorrect ou secret supprimé.

**Solution** :
1. Vérifier le chemin : `vault kv get secret/path`
2. Vérifier le mount : `vault secrets list`
3. Pour Vault Enterprise : vérifier le namespace

### Token expiré

**Symptôme** : 403 après un certain temps.

**Cause** : Token AppRole expiré et renouvellement échoué.

**Solution** :
1. Vérifier `renewable` et `lease_duration` du token
2. Le VaultService renouvelle automatiquement si `renewable=true`
3. Forcer un nouveau login : redémarrer le service

## 10. Rôle de Vault dans l'architecture (Story 27.11)

HashiCorp Vault est le **service de secrets principal** du portail IDP. Tous les credentials
des intégrations (AAP, Tower, ServiceNow, Azure DevOps, GitHub Actions, Terraform Cloud, Jira, Splunk)
sont **résolus via Vault au moment de l'exécution**. Aucun secret n'est stocké en base de données.

### Flux de résolution des secrets

```
Integration → credential_ref → resolve_credential() → VaultService.get_secret() → Secret résolu
```

### Multi-instance Vault (Story 27.11)

Le champ `secret_service_id` sur le modèle `Integration` permet de spécifier quelle instance
Vault utiliser pour résoudre les secrets d'une intégration donnée :

- **`secret_service_id = NULL`** : Vault par défaut (singleton, configuré via variables d'environnement)
- **`secret_service_id = <id>`** : Instance Vault spécifique (référence vers une intégration de type `vault`)

Le cache est isolé par instance via un `instance_id` dans la clé de cache.

### Bootstrap Vault (secret 0)

Le problème du « secret 0 » (œuf/poule) est documenté dans
[vault-bootstrap-guide.md](vault-bootstrap-guide.md). En résumé :
- Le secret 0 (VAULT_TOKEN ou VAULT_ROLE_ID + VAULT_SECRET_ID) est fourni par les variables d'environnement
- Il n'est jamais stocké en base de données
- Les intégrations de type `vault` dans l'Admin n'ont pas de champ `credential_ref`
