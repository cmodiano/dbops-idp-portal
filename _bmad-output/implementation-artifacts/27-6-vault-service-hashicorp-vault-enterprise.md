# Story 27.6 : Service client HashiCorp Vault (Open Source + Enterprise) — résolution credential_ref

Status: done

<!-- Note: HashiCorp Vault KV v2 API avec auth Token/AppRole, retry + circuit breaker + cache pour resilience. Vault Enterprise namespace support optionnel. Implementation VaultService centralisé pour tous les adapters (AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud). Ce n'est pas un adapter de plateforme d'exécution (comme AAP). VaultService résout les credential_ref pour que les adapters (AAP, Azure DevOps, etc.) obtiennent leurs credentials depuis Vault. Référence : security-architecture.md, security-remediation-plan.md (ECART-001 VaultService placeholder). -->

## Story

En tant que **système backend**,
je veux **un service client Vault (VaultService) qui résout les credential_ref (vault:secret/data/...) en secrets au moment de l'exécution**,
afin que **les adapters (AAP, Azure DevOps, etc.) obtiennent leurs credentials depuis Vault sans les stocker dans le portail, y compris avec Vault Enterprise (namespaces, etc.)**.

## Acceptance Criteria

**AC1 — Analyse documentation HashiCorp Vault (API KV v2, auth Token et AppRole, Vault Enterprise namespaces)**

**Given** la documentation officielle HashiCorp Vault (API KV v2, auth Token et AppRole, Vault Enterprise namespaces),
**When** on conçoit le VaultService,
**Then** une analyse/synthèse de la doc est disponible pour : lecture secrets KV v2, auth (token, AppRole), options Enterprise,
**And** les points d'intégration (VAULT_ADDR, namespace, chemins secret) sont identifiés,
**And** les différences Vault Open Source vs Enterprise sont documentées (namespaces, multi-tenancy, API differences).

**AC2 — Résolution credential_ref vers secret Vault**

**Given** une configuration Vault valide (URL, token ou AppRole via env / Vault),
**When** le backend doit résoudre un credential_ref (format `vault:secret/data/path#key` ou équivalent),
**Then** le VaultService retourne la valeur du secret (chaîne ou champ cible),
**And** les paramètres nécessaires (path, key optionnel) sont supportés selon le format credential_ref documenté,
**And** le format `vault:secret/data/path` (KV v2 mount path) est supporté,
**And** le format optionnel avec namespace `vault:namespace/secret/data/path#key` est supporté (Vault Enterprise).

**AC3 — Retry avec backoff exponentiel**

**Given** une indisponibilité ou erreur Vault temporaire,
**When** on appelle get_secret(),
**Then** un **retry** avec backoff exponentiel est appliqué (ex. 3 tentatives),
**And** le backoff exponentiel suit le pattern : 1s, 2s, 4s (ou configurable),
**And** les erreurs transitoires (HTTP 500, 503, timeout) déclenchent un retry,
**And** les erreurs définitives (HTTP 403 Forbidden, 404 Not Found) ne déclenchent PAS de retry.

**AC4 — Circuit breaker pour protection**

**Given** des appels répétés en échec,
**When** le nombre d'échecs consécutifs atteint un seuil (ex. 5 échecs),
**Then** un **circuit breaker** limite les appels répétés en échec (ex. 5 échecs → ouvert 60s),
**And** pendant l'état "ouvert", les appels sont rejetés immédiatement avec VaultUnavailableError,
**And** après le timeout (60s), le circuit breaker passe en état "half-open" et tente 1 appel de test,
**And** si l'appel de test réussit, le circuit breaker passe en état "fermé" et reprend les appels normaux,
**And** une erreur explicite est remontée si Vault reste indisponible (NFR21 : pas de fallback silencieux).

**AC5 — Cache avec TTL pour performance**

**Given** des appels répétés pour le même credential_ref,
**When** le secret est en cache,
**Then** un **cache** avec TTL (ex. 5 min) évite de surcharger Vault,
**And** l'invalidation ou TTL est documentée,
**And** le cache est thread-safe pour environnement multi-threadé (Gunicorn workers),
**And** le cache peut être invalidé manuellement via méthode clear_cache() ou clear_secret(credential_ref).

**AC6 — Authentification Vault (Token et AppRole)**

**And** l'authentification Vault (token, AppRole) et le stockage du token initial (env, Vault agent) sont documentés,
**And** le VaultService supporte auth Token (VAULT_TOKEN env var ou fichier),
**And** le VaultService supporte auth AppRole (VAULT_ROLE_ID + VAULT_SECRET_ID env vars),
**And** le token est automatiquement renouvelé avant expiration (si renewable),
**And** les erreurs d'authentification (403, token expiré) sont remontées clairement.

**AC7 — Support Vault Enterprise (namespaces, multi-tenancy)**

**And** les spécificités Vault Enterprise (namespaces, multi-tenancy) sont supportées ou documentées comme limitation,
**And** le namespace Vault Enterprise est configurable via env var VAULT_NAMESPACE ou dans credential_ref,
**And** le header `X-Vault-Namespace` est envoyé si namespace configuré,
**And** les limitations Open Source (pas de namespace) sont documentées.

**AC8 — Tests unitaires et d'intégration**

**And** des tests unitaires et d'intégration (mock ou Vault dev) valident le comportement,
**And** les tests couvrent : get_secret() succès, retry, circuit breaker, cache, auth Token, auth AppRole,
**And** les tests couvrent les erreurs : 404 Not Found, 403 Forbidden, 500 Internal Error, timeout,
**And** les tests d'intégration utilisent Vault dev mode ou mock pour ne pas dépendre d'un Vault externe,
**And** la couverture de tests atteint minimum 85% sur VaultService.

## Tasks / Subtasks

- [x] Task 1 — Analyse documentation HashiCorp Vault (AC: 1)
  - [x] 1.1 Étudier la documentation officielle HashiCorp Vault KV v2 API (2026)
  - [x] 1.2 Identifier les endpoints pour lecture secrets (GET /v1/{mount}/data/{path})
  - [x] 1.3 Identifier les mécanismes d'authentification Token et AppRole (POST /v1/auth/approle/login)
  - [x] 1.4 Analyser les options Vault Enterprise (namespaces, header X-Vault-Namespace)
  - [x] 1.5 Documenter le format credential_ref supporté : `vault:secret/data/path#key` et `vault:namespace/secret/data/path#key`
  - [x] 1.6 Documenter les différences Vault Open Source vs Enterprise dans `docs/vault-integration-analysis.md`
  - [x] 1.7 Identifier les codes HTTP pour erreurs (403 Forbidden, 404 Not Found, 500 Internal Error)
  - [x] 1.8 Documenter la stratégie de retry et circuit breaker dans `docs/vault-integration-analysis.md`

- [x] Task 2 — Création VaultService avec retry et circuit breaker (AC: 2, 3, 4)
  - [x] 2.1 Créer `core/vault_service.py` avec classe VaultService
  - [x] 2.2 Implémenter méthode `get_secret(credential_ref: str) -> str` pour résoudre credential_ref
  - [x] 2.3 Parser le format credential_ref : `vault:secret/data/path#key` ou `vault:namespace/secret/data/path#key`
  - [x] 2.4 Implémenter appel HTTP GET `/v1/{mount}/data/{path}` vers Vault API
  - [x] 2.5 Extraire la clé spécifiée (`#key`) ou retourner tout le secret si pas de clé
  - [x] 2.6 Implémenter retry avec backoff exponentiel (3 tentatives, 1s → 2s → 4s)
  - [x] 2.7 Différencier erreurs transitoires (500, 503, timeout → retry) vs définitives (403, 404 → pas de retry)
  - [x] 2.8 Implémenter circuit breaker avec états (closed, open, half-open)
  - [x] 2.9 Circuit breaker : 5 échecs consécutifs → open 60s → half-open (1 test call) → closed si succès
  - [x] 2.10 Remonter VaultUnavailableError si circuit breaker open ou erreur définitive
  - [x] 2.11 Logger avec structlog les appels Vault avec correlation_id
  - [x] 2.12 Gérer les erreurs : secret non trouvé (404), access denied (403), Vault indisponible (503, timeout)

- [x] Task 3 — Cache avec TTL (AC: 5)
  - [x] 3.1 Implémenter cache thread-safe avec TTL 5 minutes (cachetools.TTLCache)
  - [x] 3.2 Cacher les secrets résolus par credential_ref (key = credential_ref, value = secret)
  - [x] 3.3 Implémenter méthode `clear_cache()` pour invalider tout le cache
  - [x] 3.4 Implémenter méthode `clear_secret(credential_ref: str)` pour invalider un secret spécifique
  - [x] 3.5 Documenter le comportement du cache (TTL, thread-safe, invalidation) dans docstring
  - [x] 3.6 Logger les hits/miss du cache pour observabilité (debug level)

- [x] Task 4 — Authentification Vault (Token et AppRole) (AC: 6)
  - [x] 4.1 Implémenter auth Token via env var VAULT_TOKEN ou constructeur
  - [x] 4.2 Implémenter auth AppRole via env vars VAULT_ROLE_ID + VAULT_SECRET_ID (POST /v1/auth/approle/login)
  - [x] 4.3 Stocker le token AppRole obtenu en mémoire pour réutilisation
  - [x] 4.4 Implémenter renouvellement automatique du token avant expiration (si renewable)
  - [x] 4.5 Gérer les erreurs d'authentification (403, token expiré) avec messages clairs
  - [x] 4.6 Documenter les patterns d'authentification supportés dans `docs/vault-integration-analysis.md`
  - [x] 4.7 Valider compatibilité auth Vault credentials avec tous les adapters (AAP, Tower, Azure DevOps, GitHub, Terraform)

- [x] Task 5 — Support Vault Enterprise (namespaces) (AC: 7)
  - [x] 5.1 Supporter env var VAULT_NAMESPACE pour configurer namespace global
  - [x] 5.2 Parser namespace depuis credential_ref si format `vault:namespace/secret/data/path#key`
  - [x] 5.3 Ajouter header `X-Vault-Namespace: {namespace}` si namespace configuré
  - [x] 5.4 Documenter limitations Vault Open Source (pas de namespace) dans `docs/vault-integration-analysis.md`
  - [x] 5.5 Tester avec mock Vault Enterprise pour valider header namespace

- [x] Task 6 — Tests unitaires et d'intégration (AC: 8)
  - [x] 6.1 Tests VaultService.get_secret() : succès avec Token auth, succès avec AppRole auth
  - [x] 6.2 Tests retry : erreur transitoire (500) → retry → succès, timeout → retry → succès
  - [x] 6.3 Tests circuit breaker : 5 échecs → open → rejet immédiat, half-open → test call succès → closed
  - [x] 6.4 Tests cache : premier appel → cache miss → Vault call, deuxième appel → cache hit → pas de Vault call
  - [x] 6.5 Tests cache invalidation : clear_cache(), clear_secret(credential_ref)
  - [x] 6.6 Tests erreurs : 404 Not Found, 403 Forbidden, 500 Internal Error, timeout
  - [x] 6.7 Tests auth Token : env var VAULT_TOKEN, constructeur, token manquant
  - [x] 6.8 Tests auth AppRole : VAULT_ROLE_ID + VAULT_SECRET_ID, login succès, login échec
  - [x] 6.9 Tests namespace Vault Enterprise : header X-Vault-Namespace, credential_ref avec namespace
  - [x] 6.10 Tests parsing credential_ref : `vault:secret/data/path#key`, `vault:namespace/secret/data/path#key`, formats invalides
  - [x] 6.11 Vérifier couverture ≥ 85% sur vault_service.py — 91.64% atteint
  - [x] 6.12 Tests d'intégration avec mock (ne dépendent pas d'un Vault externe)

- [x] Task 7 — Intégration avec adapters existants (AC: 2)
  - [x] 7.1 build_auth_headers() étendu pour résoudre credential_ref via VaultService si prefix vault:
  - [x] 7.2 Backward compat : credential_ref direct (non-Vault) utilisé tel quel
  - [x] 7.3 Tests intégration : build_auth_headers avec vault ref, direct token, basic auth
  - [x] 7.4 Tous adapters utilisent build_auth_headers() → VaultService automatiquement
  - [x] 7.5 Tests non-régression adapters : 207/207 tests passent (0 régression)

- [x] Task 8 — Documentation finale (AC: 1, 6, 7)
  - [x] 8.1 Compléter `docs/vault-integration-analysis.md` avec tous les patterns supportés
  - [x] 8.2 Documenter flow complet : Adapter → VaultService → Vault API → Cache/Retry/Circuit Breaker
  - [x] 8.3 Documenter diagramme de séquence VaultService dans `docs/vault-integration-analysis.md`
  - [x] 8.4 Documenter configuration requise (env vars, fichiers, Vault policy)
  - [x] 8.5 Ajouter exemples credential_ref dans documentation
  - [x] 8.6 Documenter troubleshooting : circuit breaker open, auth failed, secret not found

## Dev Notes

### Contexte métier

- **Epic 27** : Adapters d'intégration backend — AAP, Tower, Azure DevOps, GitHub Actions et Terraform Cloud complétés (Stories 27.1-27.5). Ces adapters ont besoin de résoudre les `credential_ref` pour obtenir les credentials (tokens, secrets) depuis HashiCorp Vault au moment de l'exécution.
- **Stories 27.1-27.5** : Ont créé AAPAdapter, TowerAdapter, AzureDevOpsAdapter, GitHubActionsAdapter et TerraformCloudAdapter. 222 tests passent. Tous utilisent pattern `build_auth_headers()` qui doit appeler VaultService pour résoudre credential_ref. [Source: 27-1 à 27-5 story files]
- **Objectif 27.6** : Créer un service centralisé VaultService qui résout les credential_ref vers secrets Vault avec retry, circuit breaker et cache pour résilience et performance.
- **NFR21** : "En cas d'indisponibilité de Vault, l'execution est refusee avec un message explicite (pas de fallback)" — le VaultService doit remonter erreur claire si Vault indisponible. [Source: epics.md]
- **NFR7** : "Aucun secret (credential, token, cle) n'est stocke dans le portail ou le catalogue — recuperation exclusive depuis Vault a l'execution" — le VaultService est le seul point d'accès aux secrets. [Source: epics.md]

### Patterns à respecter

- **Service Pattern** : VaultService est un service singleton réutilisable par tous les adapters. [Source: architecture.md]
- **Retry Pattern** : Backoff exponentiel pour erreurs transitoires (500, 503, timeout). [Source: architecture.md, patterns observés Stories 27.1-27.5]
- **Circuit Breaker Pattern** : Protection contre avalanche d'appels en échec vers Vault (5 échecs → open 60s). [Source: architecture.md, resilience best practices]
- **Cache Pattern** : Cache thread-safe avec TTL pour réduire charge Vault et améliorer performance. [Source: architecture.md "Cache in-memory : cachetools / lru_cache Python"]
- **Error Hierarchy** : VaultError → VaultUnavailableError, VaultAuthError, VaultSecretNotFoundError, VaultAccessDeniedError. [Source: core/exceptions.py]
- **Logging structuré** : structlog JSON avec correlation_id pour tous les appels Vault. [Source: architecture.md]

### Ce qui existe déjà (Stories 27.1-27.5)

- **Backend adapters** :
  - `app/adapters/aap_adapter.py`, `app/adapters/tower_adapter.py`, `app/adapters/azure_devops_adapter.py`, `app/adapters/github_actions_adapter.py`, `app/adapters/terraform_cloud_adapter.py` avec trigger(), get_status(), get_job_logs(), cancel_execution()
  - `app/adapters/base_adapter.py` avec BaseAdapter ABC
  - `app/adapters/utils.py` avec build_auth_headers() helper — **DOIT ÊTRE ÉTENDU pour appeler VaultService.get_secret()**
  - Factory `get_platform_adapter("aap"|"tower"|"azure_devops"|"github_actions"|"terraform_cloud")` dans `app/adapters/__init__.py`
  - [Source: adapters/]

- **Backend services** :
  - `app/services/execution_service.py` orchestration
  - **PAS DE VaultService EXISTANT** — cette story crée VaultService de zéro
  - [Source: 4-3-moteur-execution-et-facade-api.md]

- **Error hierarchy** :
  - `core/exceptions.py` avec IdpError → PlatformError, NotFoundError, ForbiddenError
  - **AJOUTER** : VaultError → VaultUnavailableError, VaultAuthError, VaultSecretNotFoundError, VaultAccessDeniedError
  - [Source: core/exceptions.py]

- **Env vars existantes** :
  - VAULT_ADDR probablement déjà configuré (à vérifier)
  - **AJOUTER** : VAULT_TOKEN, VAULT_ROLE_ID, VAULT_SECRET_ID, VAULT_NAMESPACE (optionnel), VAULT_CACHE_TTL
  - [Source: .env.example si existant]

- **Doc existante** :
  - `docs/security-architecture.md` — pseudo-code VaultService (get_secret, retry, circuit breaker, cache), format credential_ref `vault:secret/data/...`. [Source: security-architecture.md]
  - `docs/security-remediation-plan.md` — ECART-001 VaultService non implémenté, critères acceptation. [Source: security-remediation-plan.md]
  - **CRÉER** : `docs/vault-integration-analysis.md` — documentation complète Vault API, patterns, troubleshooting

- **Tests existants** :
  - `tests/conftest.py` mock_vault_service (patch `core.services.vault_service`) — **À CRÉER** le vrai VaultService
  - Tests SOC1 credential_ref format Vault — **À VALIDER** avec VaultService réel
  - [Source: tests/]

### Références techniques HashiCorp Vault

**Vault KV v2 API** :
- Endpoint lecture secret : `GET /v1/{mount}/data/{path}` (mount par défaut : `secret`)
- Format réponse : `{"data": {"data": {"key": "value"}, "metadata": {...}}}`
- Auth Token : Header `X-Vault-Token: {token}`
- Auth AppRole : `POST /v1/auth/approle/login` avec `role_id` + `secret_id` → retourne `client_token`
- Namespace Enterprise : Header `X-Vault-Namespace: {namespace}`
- [Source: HashiCorp Vault API Documentation 2026]

**Format credential_ref** :
- `vault:secret/data/path#key` — secret KV v2 dans mount `secret`, path `path`, clé `key`
- `vault:namespace/secret/data/path#key` — secret avec namespace Vault Enterprise
- Si pas de `#key`, retourner tout le secret (JSON ou premier champ)

**Retry et Circuit Breaker** :
- Erreurs transitoires (retry) : HTTP 500, 503, timeout, connexion refusée
- Erreurs définitives (pas de retry) : HTTP 403 Forbidden, 404 Not Found, 400 Bad Request
- Circuit breaker : 5 échecs consécutifs → open 60s → half-open (1 test call) → closed si succès
- [Source: Resilience patterns best practices]

**Cache** :
- TTL : 5 minutes (configurable via env var VAULT_CACHE_TTL)
- Thread-safe : cachetools.TTLCache avec lock threading.RLock()
- Invalidation : clear_cache() (tout) ou clear_secret(credential_ref) (un secret)
- [Source: architecture.md "Cache in-memory : cachetools / lru_cache Python"]

### Architecture VaultService (esquisse d'implémentation)

```python
# app/services/vault_service.py

import os
import time
import requests
import structlog
from cachetools import TTLCache
from threading import RLock
from typing import Optional

from core.exceptions import VaultUnavailableError, VaultAuthError, VaultSecretNotFoundError, VaultAccessDeniedError

logger = structlog.get_logger(__name__)

class CircuitBreaker:
    """Circuit breaker pour protection contre appels répétés en échec."""
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        self.lock = RLock()

    def call(self, func, *args, **kwargs):
        with self.lock:
            if self.state == "open":
                # Vérifier si timeout écoulé
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = "half-open"
                    logger.info("circuit_breaker_half_open")
                else:
                    raise VaultUnavailableError("Circuit breaker open - Vault unavailable")

            try:
                result = func(*args, **kwargs)
                if self.state == "half-open":
                    self.state = "closed"
                    self.failures = 0
                    logger.info("circuit_breaker_closed")
                return result
            except Exception as e:
                self.failures += 1
                self.last_failure_time = time.time()
                if self.failures >= self.failure_threshold:
                    self.state = "open"
                    logger.warning("circuit_breaker_open", failures=self.failures)
                raise


class VaultService:
    """Service client HashiCorp Vault avec retry, circuit breaker et cache."""

    def __init__(self):
        self.vault_addr = os.getenv("VAULT_ADDR", "http://localhost:8200")
        self.vault_token = os.getenv("VAULT_TOKEN")
        self.vault_namespace = os.getenv("VAULT_NAMESPACE")
        self.cache = TTLCache(maxsize=1000, ttl=int(os.getenv("VAULT_CACHE_TTL", 300)))
        self.cache_lock = RLock()
        self.circuit_breaker = CircuitBreaker()
        self.session = requests.Session()

        if not self.vault_token:
            self._authenticate_approle()

    def _authenticate_approle(self):
        """Authenticate via AppRole if VAULT_ROLE_ID and VAULT_SECRET_ID provided."""
        role_id = os.getenv("VAULT_ROLE_ID")
        secret_id = os.getenv("VAULT_SECRET_ID")
        if role_id and secret_id:
            # POST /v1/auth/approle/login
            # Store client_token
            pass

    def get_secret(self, credential_ref: str, correlation_id: Optional[str] = None) -> str:
        """Résout credential_ref vers secret Vault avec cache, retry et circuit breaker."""
        with self.cache_lock:
            if credential_ref in self.cache:
                logger.debug("vault_cache_hit", credential_ref=credential_ref, correlation_id=correlation_id)
                return self.cache[credential_ref]

        # Parse credential_ref : vault:secret/data/path#key ou vault:namespace/secret/data/path#key
        namespace, mount, path, key = self._parse_credential_ref(credential_ref)

        # Appel Vault avec retry et circuit breaker
        secret_value = self.circuit_breaker.call(self._fetch_secret, namespace, mount, path, key, correlation_id)

        with self.cache_lock:
            self.cache[credential_ref] = secret_value

        return secret_value

    def _fetch_secret(self, namespace, mount, path, key, correlation_id):
        """Appel HTTP GET vers Vault avec retry backoff exponentiel."""
        for attempt in range(3):
            try:
                headers = {"X-Vault-Token": self.vault_token}
                if namespace:
                    headers["X-Vault-Namespace"] = namespace

                url = f"{self.vault_addr}/v1/{mount}/data/{path}"
                response = self.session.get(url, headers=headers, timeout=10)

                if response.status_code == 200:
                    data = response.json()["data"]["data"]
                    return data.get(key) if key else data
                elif response.status_code == 404:
                    raise VaultSecretNotFoundError(f"Secret not found: {path}")
                elif response.status_code == 403:
                    raise VaultAccessDeniedError(f"Access denied: {path}")
                elif response.status_code in [500, 503]:
                    # Erreur transitoire → retry
                    if attempt < 2:
                        backoff = 2 ** attempt
                        time.sleep(backoff)
                        continue
                    raise VaultUnavailableError(f"Vault unavailable: HTTP {response.status_code}")
            except requests.exceptions.Timeout:
                if attempt < 2:
                    backoff = 2 ** attempt
                    time.sleep(backoff)
                    continue
                raise VaultUnavailableError("Vault timeout")

        raise VaultUnavailableError("Vault max retries exceeded")

    def clear_cache(self):
        """Invalide tout le cache."""
        with self.cache_lock:
            self.cache.clear()

    def clear_secret(self, credential_ref: str):
        """Invalide un secret spécifique du cache."""
        with self.cache_lock:
            self.cache.pop(credential_ref, None)
```

### Mapping erreurs Vault → Exceptions IDP Portal

| Statut HTTP Vault | Exception IDP Portal | Retry ? | Notes |
|-------------------|---------------------|---------|-------|
| 200 OK | Succès | - | Secret retourné |
| 404 Not Found | VaultSecretNotFoundError | Non | Secret ou path inexistant |
| 403 Forbidden | VaultAccessDeniedError | Non | Token invalide ou pas de permissions |
| 400 Bad Request | VaultError | Non | Paramètres invalides |
| 500 Internal Error | VaultUnavailableError | Oui (3x) | Erreur transitoire Vault |
| 503 Service Unavailable | VaultUnavailableError | Oui (3x) | Vault sealed ou maintenance |
| Timeout | VaultUnavailableError | Oui (3x) | Réseau lent ou Vault surchargé |

### Intégration avec adapters existants

Tous les adapters (AAP, Tower, Azure DevOps, GitHub, Terraform) utilisent `build_auth_headers()` dans `app/adapters/utils.py`. Cette fonction doit être étendue pour :

```python
# app/adapters/utils.py

from app.services.vault_service import VaultService

vault_service = VaultService()

def build_auth_headers(credential_ref: str, correlation_id: Optional[str] = None) -> dict:
    """Résout credential_ref via VaultService et construit headers auth."""
    if credential_ref.startswith("vault:"):
        token = vault_service.get_secret(credential_ref, correlation_id)
        return {"Authorization": f"Bearer {token}"}
    else:
        # Fallback : credential_ref est un token direct (dev/test)
        return {"Authorization": f"Bearer {credential_ref}"}
```

### Tests

**Tests unitaires** (mock Vault API) :
- `tests/services/test_vault_service.py` : 20+ tests couvrant tous les AC
- Mock `requests.Session.get()` pour simuler réponses Vault (200, 404, 403, 500, 503, timeout)
- Tests retry : 500 → 500 → 200 (succès après retry)
- Tests circuit breaker : 5x 500 → open → rejet immédiat
- Tests cache : hit, miss, invalidation
- Tests auth : Token, AppRole, erreurs auth

**Tests d'intégration** (Vault dev mode) :
- Démarrer Vault dev mode : `docker run --rm --cap-add=IPC_LOCK -e 'VAULT_DEV_ROOT_TOKEN_ID=root' -p 8200:8200 vault:latest`
- Tests réels contre Vault dev : get_secret(), retry, cache
- Optionnel : ne pas bloquer CI si Vault dev indisponible (skip si pas de VAULT_ADDR)

**Tests non-régression adapters** :
- Vérifier que tous les adapters (AAP, Tower, Azure DevOps, GitHub, Terraform) utilisent VaultService
- Exécuter tests existants : 222/222 tests passent (0 régression)

### Project Structure Notes

- **Nouveau fichier** : `app/services/vault_service.py` (VaultService + CircuitBreaker)
- **Modification** : `app/adapters/utils.py` (build_auth_headers appelle VaultService)
- **Nouvelle exception** : `core/exceptions.py` (VaultError, VaultUnavailableError, VaultAuthError, VaultSecretNotFoundError, VaultAccessDeniedError)
- **Nouveau doc** : `docs/vault-integration-analysis.md` (analyse Vault API, patterns, troubleshooting)
- **Tests** : `tests/services/test_vault_service.py` (20+ tests unitaires)
- **Env vars** : `.env.example` ajouter VAULT_ADDR, VAULT_TOKEN, VAULT_ROLE_ID, VAULT_SECRET_ID, VAULT_NAMESPACE, VAULT_CACHE_TTL

### References

- [Source: HashiCorp Vault API Documentation — KV v2 Secrets Engine](https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2)
- [Source: HashiCorp Vault API Documentation — AppRole Auth Method](https://developer.hashicorp.com/vault/api-docs/auth/approle)
- [Source: HashiCorp Vault Enterprise Namespaces](https://developer.hashicorp.com/vault/docs/enterprise/namespaces)
- [Source: architecture.md#Vault Integration]
- [Source: epics.md — NFR7, NFR21]
- [Source: 27-1-adapter-aap-doc-workflows-jobs-monitoring-websocket.md]
- [Source: 27-2-adapter-ansible-tower-doc-workflows-jobs-monitoring-websocket.md]
- [Source: 27-3-adapter-azure-devops-pipelines-runs-monitoring.md]
- [Source: 27-4-adapter-github-actions-workflow-runs-monitoring.md]
- [Source: 27-5-adapter-terraform-cloud-runs-monitoring.md]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

N/A — Implémentation complète en une session

### Completion Notes List

- **Task 1 — Analyse documentation** : Analyse Vault KV v2 API, auth Token/AppRole, Enterprise namespaces documentée dans `docs/vault-integration-analysis.md`
- **Task 2 — VaultService** : `core/vault_service.py` créé avec CircuitBreaker, retry exponentiel (3x, backoff 1s/2s/4s), parsing credential_ref regex, hiérarchie exceptions Vault
- **Task 3 — Cache TTL** : cachetools.TTLCache thread-safe (RLock), TTL 5min configurable, clear_cache(), clear_secret(), logging hits/miss
- **Task 4 — Auth Token/AppRole** : Token via env/constructeur, AppRole login automatique POST /v1/auth/approle/login, renouvellement token renewable, erreurs auth claires
- **Task 5 — Enterprise namespaces** : X-Vault-Namespace header, namespace depuis credential_ref ou VAULT_NAMESPACE env, compatible Open Source (pas de header si pas de namespace)
- **Task 6 — Tests** : 46 tests unitaires couvrant parsing, get_secret, retry, circuit breaker (closed/open/half-open), cache (hit/miss/clear), auth Token/AppRole, Enterprise namespaces, erreurs (404/403/500/timeout), intégration build_auth_headers. Couverture 91.64% (objectif 85%)
- **Task 7 — Intégration adapters** : build_auth_headers() étendu avec _resolve_credential() — vault: prefix → VaultService, sinon direct token. 207/207 tests adapters passent (0 régression)
- **Task 8 — Documentation** : `docs/vault-integration-analysis.md` complet avec API, auth, credential_ref formats, résilience, diagramme séquence, config, troubleshooting

### Code Review Notes (2026-02-14)

**Review type:** Adversarial (auto-fix mode)

**Issues trouvés:** 10 total
- **CRITICAL:** 2 (circuit breaker DoS thread pool exhaustion, token renewal race condition)
- **HIGH:** 4 (token renewal jamais appelé, singleton env vars, cache namespace collision, tests parallèles)
- **MEDIUM:** 3 (retry_after negative, details leak sécurité, sleep blocking Gunicorn)
- **LOW:** 1 (monitoring circuit breaker manquant)

**Issues auto-fixés:** 7
- **CRIT-1:** Circuit breaker check d'état SANS lock pour éviter contention massive threads
- **CRIT-2:** Token renewal avec lock thread-safe (race condition éliminée)
- **HIGH-1:** `_ensure_token_valid()` appelé automatiquement dans `get_secret()` (token renewal fonctionnel)
- **HIGH-3:** Cache key inclut namespace (`_build_cache_key()`) pour éviter collisions multi-tenancy
- **MED-1:** `retry_after_s` avec `max(0, ...)` pour éviter valeurs négatives
- **MED-2:** Exception details sanitisés (pas de leak path/mount vers client)
- **LOW-1:** Documentation troubleshooting circuit breaker créée (`docs/vault-troubleshooting-circuit-breaker.md`)

**Issues documentés (non-bloquants):** 3
- **HIGH-2:** Singleton non-réactif aux changements env vars (workaround: restart workers) — documenté `docs/vault-known-limitations-story-27-6.md`
- **HIGH-4:** Singleton global vulnérable tests parallèles (workaround: tests isolés) — documenté
- **MED-3:** Retry sleep bloque thread Gunicorn (acceptable Phase 2, migration Celery Phase 3 Story 20-3) — documenté

**Tests après fixes:**
- 46/46 VaultService tests PASS ✅
- 207/207 adapter tests PASS ✅ (0 régression)

**Statut final:** Story **DONE** — Toutes AC1-AC8 MET, 7 fixes critiques appliqués, 3 limitations documentées pour Phase 3.

### Implementation Plan

- VaultService dans `core/vault_service.py` (pas `app/services/`) car c'est un service core réutilisé partout
- Exceptions Vault héritent de ServiceUnavailableError pour compatibilité exception handler DRF existant
- CircuitBreaker utilise time.monotonic() (pas time.time()) pour éviter sauts horloge
- Singleton module-level avec double-checked locking (get_vault_service())
- build_auth_headers() backward compatible : credential_ref non-Vault utilisé tel quel

## Change Log

- 2026-02-14: Story 27.6 implémentée — VaultService avec retry, circuit breaker, cache, auth Token/AppRole, Enterprise namespaces. 46 tests, 91.64% couverture, 207 adapter tests non-régression, documentation complète.
- 2026-02-14: Code review adversarial — **10 issues trouvés** (2 CRITICAL, 4 HIGH, 3 MEDIUM, 1 LOW). **7 auto-fixés**, 3 documentés comme Known Limitations (non-bloquants). 46/46 tests + 207/207 adapters passent. Story **DONE**.

### File List

- `idp-portal/django_backend/core/vault_service.py` (NOUVEAU — VaultService + CircuitBreaker; MODIFIÉ code review — 7 fixes CRIT-1, CRIT-2, HIGH-1, HIGH-3, MED-1, MED-2)
- `idp-portal/django_backend/core/exceptions.py` (MODIFIÉ — ajout VaultError, VaultUnavailableError, VaultAuthError, VaultSecretNotFoundError, VaultAccessDeniedError)
- `idp-portal/django_backend/adapters/utils.py` (MODIFIÉ — _resolve_credential() + build_auth_headers() étendu pour Vault)
- `idp-portal/django_backend/core/tests/test_vault_service.py` (NOUVEAU — 46 tests unitaires)
- `idp-portal/django_backend/docs/vault-integration-analysis.md` (NOUVEAU — documentation complète Vault; MODIFIÉ code review — référence troubleshooting)
- `idp-portal/django_backend/docs/vault-troubleshooting-circuit-breaker.md` (NOUVEAU code review — LOW-1 fix monitoring circuit breaker)
- `idp-portal/django_backend/docs/vault-known-limitations-story-27-6.md` (NOUVEAU code review — HIGH-2, HIGH-4, MED-3 limitations documentées)
- `idp-portal/.env.example` (MODIFIÉ — ajout VAULT_NAMESPACE, VAULT_CACHE_TTL, VAULT_TIMEOUT, VAULT_MAX_RETRIES)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (MODIFIÉ — 27-6 status review → done)
- `_bmad-output/implementation-artifacts/27-6-vault-service-hashicorp-vault-enterprise.md` (MODIFIÉ — story file)
