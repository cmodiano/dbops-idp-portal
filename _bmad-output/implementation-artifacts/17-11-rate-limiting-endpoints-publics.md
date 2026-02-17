# Story 17.11: Rate limiting sur les endpoints publics

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a équipe sécurité,
I want un système de rate limiting sur les endpoints exposés (API publiques et endpoints d'authentification),
So that nous puissions limiter les abus, prévenir les attaques par force brute, et protéger l'infrastructure contre les requêtes excessives.

## Acceptance Criteria

**Given** un client appelle un endpoint exposé (ex. login SAML, API v1, endpoints publics)
**When** le nombre de requêtes dépasse un seuil défini (par IP ou par utilisateur authentifié)
**Then** le serveur répond avec un statut HTTP 429 Too Many Requests
**And** la réponse inclut les headers `Retry-After` et `X-RateLimit-*` pour informer le client

**Given** un endpoint critique nécessite une protection contre le brute-force (ex. `/auth/saml/login`, `/api/v1/auth/token`)
**When** le rate limiting est configuré
**Then** les seuils sont restrictifs : maximum 10 requêtes par minute par IP pour les endpoints d'authentification
**And** les seuils sont modérés pour les endpoints API généraux : 100 requêtes par minute par utilisateur authentifié

**Given** le rate limiting est actif
**When** un utilisateur atteint la limite
**Then** les tentatives suivantes retournent 429 pendant la fenêtre de temps définie
**And** un log structuré WARNING est émis avec `correlation_id`, `ip_address`, `user_id`, `endpoint`, `limit_type`

**Given** la configuration du rate limiting
**When** l'application démarre
**Then** les seuils (limite, fenêtre de temps) sont paramétrables via variables d'environnement ou settings Django
**And** les valeurs par défaut sont sécurisées (restrictives)

**Given** le système de rate limiting utilise le cache Django
**When** une requête est reçue
**Then** le compteur de requêtes est stocké dans le cache configuré (in-memory cache pour MVP, Redis si disponible en production)
**And** les clés de cache expirent automatiquement après la fenêtre de temps

**Given** les endpoints critiques identifiés
**When** le rate limiting est déployé
**Then** au minimum les endpoints suivants sont protégés :
- `/auth/saml/login` (10 req/min par IP)
- `/auth/saml/acs` (10 req/min par IP)
- `/api/v1/auth/token/refresh` (20 req/min par utilisateur)
- `/api/v1/executions/` POST (30 req/min par utilisateur)
- Tous les endpoints publics non-authentifiés (50 req/min par IP)

**Given** un endpoint nécessite des seuils spécifiques
**When** le rate limiting est configuré
**Then** l'approche DRF ScopedRateThrottle permet de définir des scopes personnalisés par endpoint ou groupe d'endpoints
**And** la configuration est documentée dans `docs/security-architecture.md`

**Given** le rate limiting est actif en production
**When** un incident de performance ou attaque DDoS est détecté
**Then** les seuils peuvent être ajustés dynamiquement via variables d'environnement sans redéploiement (restart requis)

## Tasks / Subtasks

- [x] Task 1: Choisir l'approche de rate limiting et installer les dépendances (AC: 4, 5)
  - [x] 1.1: Évaluer DRF built-in throttling vs django-ratelimit vs custom middleware
  - [x] 1.2: Décision : Utiliser **DRF throttling classes uniquement** — tous les endpoints sont des APIView DRF, django-ratelimit non nécessaire
  - [x] 1.3: Pas de dépendance externe requise — DRF throttling built-in suffit
  - [x] 1.4: N/A — pas de dépendance à ajouter
  - [x] 1.5: N/A — pas de dépendance à installer

- [x] Task 2: Configurer le cache Django pour le rate limiting (AC: 5)
  - [x] 2.1: Cache LocMemCache configuré dans `idp_backend/settings.py`
  - [x] 2.2: MVP : LocMemCache single-instance
  - [x] 2.3: Migration Redis documentée dans `docs/security-architecture.md`
  - [x] 2.4: Variable `RATELIMIT_USE_CACHE=default` ajoutée dans `.env.production.template`

- [x] Task 3: Implémenter DRF throttling pour les endpoints API (AC: 1, 2, 6)
  - [x] 3.1: Créé `django_backend/core/throttling.py` avec 5 classes custom throttle + mixin _RateLimitEnabledMixin
  - [x] 3.2: `AuthEndpointThrottle(AnonRateThrottle)` : 10 req/min par IP
  - [x] 3.3: `ExecutionThrottle(UserRateThrottle)` : 30 req/min par user
  - [x] 3.4: `GeneralAPIThrottle(UserRateThrottle)` : 100 req/min par user (default)
  - [x] 3.5: Rates configurés dans `REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']`
  - [x] 3.6: Rates configurables via env vars : THROTTLE_AUTH_RATE, THROTTLE_TOKEN_REFRESH_RATE, THROTTLE_EXECUTION_RATE, THROTTLE_API_RATE, THROTTLE_PUBLIC_RATE
  - [x] 3.7: Throttle classes appliqués à SAMLLoginView, SAMLCallbackView, RefreshTokenView, LogoutView, ExecutionsView

- [x] Task 4: ~~django-ratelimit~~ → DRF throttling pour endpoints SAML (AC: 1, 2, 6)
  - [x] 4.1: N/A — SAMLLoginView et SAMLCallbackView sont des DRF APIViews, pas des views Django
  - [x] 4.2: SAMLLoginView protégé via `throttle_classes = [AuthEndpointThrottle]`
  - [x] 4.3: SAMLCallbackView protégé via `throttle_classes = [AuthEndpointThrottle]`
  - [x] 4.4: Exception handler custom retourne JSON 429 avec code THROTTLED + header Retry-After
  - [x] 4.5: Rate configurable via `THROTTLE_AUTH_RATE` env var

- [x] Task 5: Ajouter les headers de rate limiting dans les réponses (AC: 1)
  - [x] 5.1: Créé `RateLimitHeadersMiddleware` dans `core/middleware.py`
  - [x] 5.2: Headers `Retry-After` et `X-RateLimit-*` exposés via CORS_EXPOSE_HEADERS
  - [x] 5.3: Retry-After normalisé (float→int) et propagé via exception handler
  - [x] 5.4: DRF gère automatiquement Retry-After, middleware détecte 429 pour logging
  - [x] 5.5: Middleware ajouté après RequestResponseLoggingMiddleware, avant SecurityHeadersMiddleware

- [x] Task 6: Logging structuré des rate limit violations (AC: 3)
  - [x] 6.1: RateLimitHeadersMiddleware détecte réponses 429
  - [x] 6.2: WARNING structuré : `rate_limit_exceeded` avec correlation_id, ip_address, user_id, endpoint, method
  - [x] 6.3: Utilise `get_client_ip()` existant (gère X-Forwarded-For)
  - [x] 6.4: user_agent inclus dans le log structuré

- [x] Task 7: Configuration des seuils de rate limiting (AC: 2, 4, 6, 8)
  - [x] 7.1: Section Rate Limiting ajoutée dans `.env.production.template`
  - [x] 7.2: Variables définies : THROTTLE_AUTH_RATE, THROTTLE_TOKEN_REFRESH_RATE, THROTTLE_EXECUTION_RATE, THROTTLE_API_RATE, THROTTLE_PUBLIC_RATE, RATELIMIT_ENABLED
  - [x] 7.3: Valeurs par défaut sécurisées dans settings.py (10/minute auth, 100/minute API, etc.)
  - [x] 7.4: Format documenté dans security-architecture.md et .env.production.template
  - [x] 7.5: Validation startup via `validate_rate_limit_config()` dans core/startup_checks.py (ImproperlyConfigured si invalide)

- [x] Task 8: Documenter le système de rate limiting (AC: 7)
  - [x] 8.1: Section "12. Rate Limiting (Story 17.11)" ajoutée dans `docs/security-architecture.md`
  - [x] 8.2: Seuils par endpoint documentés avec justification (tableau)
  - [x] 8.3: Approche technique documentée (DRF throttling uniquement, cache LocMemCache)
  - [x] 8.4: Format réponse 429 documenté (JSON THROTTLED + Retry-After)
  - [x] 8.5: Procédure d'ajustement documentée (env vars + restart + rollback RATELIMIT_ENABLED=false)
  - [x] 8.6: Migration Redis documentée avec exemple configuration

- [x] Task 9: Tests unitaires et intégration (AC: 1, 2, 3, 5) — 29 tests
  - [x] 9.1: Test scope auth et cache key par IP (TestAuthEndpointThrottle, 4 tests)
  - [x] 9.2: Test scope execution et héritage UserRateThrottle (TestExecutionThrottle, 2 tests)
  - [x] 9.3: Test Retry-After préservé dans middleware (test_429_preserves_retry_after_header)
  - [x] 9.4: Test WARNING logging avec correlation_id, ip, user_id, endpoint, method, user_agent (3 tests)
  - [x] 9.5: Test health endpoint exempt (test_health_endpoint_exempt)
  - [x] 9.6: Test IPs différentes ont des clés différentes (test_different_ips_get_different_keys)
  - [x] 9.7: Test cache key par IP pour endpoints anonymes (TokenRefresh, Public)
  - [x] 9.8: Test configuration settings DRF (TestDRFThrottlingSettings, 3 tests)
  - [x] 9.9: Test parsing invalide échoue au startup (TestRateLimitConfigValidation, 6 tests)
  - [x] 9.10: Tests dans `core/tests/test_rate_limiting.py` — 29 tests ✅
  - [x] 9.11: Test RATELIMIT_ENABLED bypass flag (TestRateLimitEnabledFlag, 2 tests)

- [x] Task 10: Tests de sécurité fonctionnels (AC: 1, 2, 6) — 7 tests
  - [x] 10.1: Brute-force SAML login bloqué (TestSAMLLoginBruteForce, 2 tests) + 429 Retry-After vérifié
  - [x] 10.2: SAML callback brute-force bloqué (TestSAMLCallbackBruteForce, 1 test)
  - [x] 10.3: Token refresh abuse bloqué (TestTokenRefreshAbuse, 1 test)
  - [x] 10.4: IP spoofing via X-Forwarded-For ne bypass pas (TestIPSpoofingProtection, 2 tests)
  - [x] 10.5: Rate limit persiste entre clients (TestRateLimitPersistence, 1 test)
  - [x] 10.6: Tests dans `tests/security/test_rate_limiting_security.py` — 7 tests ✅

- [x] Task 11: Validation et rollout progressif (AC: 8)
  - [x] 11.1: Validé en environnement dev — 36 tests rate limiting + 18 middleware + 10 startup = 64 tests ✅
  - [x] 11.2: Tests sécurité simulent charge (brute-force 4+ requêtes rapides, vérifient 429)
  - [x] 11.3: Tests vérifient que requêtes légitimes passent avant seuil (assert != 429)
  - [x] 11.4: Rollback via `RATELIMIT_ENABLED=false` — mixin `_RateLimitEnabledMixin` bypass tout throttling
  - [x] 11.5: Monitoring documenté dans security-architecture.md (query Splunk, alertes suggérées)

## Dev Notes

### Contexte Technique

**Architecture Projet:**
- **Backend**: Django 5.2 + DRF 3.16, Python 3.12+, Gunicorn 25.0
- **Cache**: LocMemCache (in-memory) pour MVP, migration vers Redis recommandée pour production multi-instances
- **Middleware Stack**: 6 middleware existants dans `idp_backend/settings.py`
- **Logging**: structlog 25.5 avec JSON structuré vers stdout

**Epic 17 Context:**
- Story 17.1-17.10 : Décommissionnement FastAPI, refactoring frontend, secrets, lockfiles, mypy, Dockerfiles ✅
- **Story 17.11 : Rate Limiting** ← CURRENT
- Story 17.12-17.15 : Feature flags, UX improvements (backlog)

### Contraintes Architecturales

**Sécurité (Epic 15, docs/security-architecture.md):**
1. **Endpoints critiques identifiés** : Login SAML, ACS SAML, token refresh, execution POST
2. **Logging immutable** : Toutes violations de rate limit doivent être loguées dans `AUDIT_LOG` (optionnel, ou juste structlog)
3. **Correlation ID** : Middleware `CorrelationIdMiddleware` déjà en place, utiliser `request.correlation_id`
4. **IP extraction** : Fonction `get_client_ip(request)` dans `core/middleware.py` gère X-Forwarded-For

**Performance (Architecture NFR):**
- **Cache in-memory** : Acceptable pour MVP single-instance, mais **limitation connue** : perte des compteurs au restart
- **Redis requis** : Pour production HA multi-instances (2+ VMs), sinon rate limits inconsistants entre instances
- **Overhead** : DRF throttling utilise cache lookup par requête, impact négligeable (<1ms)

**Déploiement:**
- **Configuration dynamique** : Seuils via env vars, ajustables sans redéploiement (restart requis)
- **Fail-safe** : Si cache indisponible, **ne pas bloquer les requêtes** (degrade gracefully, logger ERROR)

### Patterns et Composants Existants à Réutiliser

**Middleware Pattern (Story M.7, M.8):**
```python
# Fichier : django_backend/core/middleware.py (150 lignes existantes)
class CorrelationIdMiddleware:
    def __call__(self, request):
        correlation_id = request.META.get('HTTP_X_IDP_REQUEST_ID') or str(uuid.uuid4())
        request.correlation_id = correlation_id
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        # ...

def get_client_ip(request) -> str:
    """Extract client IP, handling X-Forwarded-For for proxies."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')
```
**Utilisation :** Réutiliser `get_client_ip()` pour keying des rate limits par IP.

**DRF Configuration (settings.py):**
```python
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    # ... autres configs existantes
}
```
**Ajout :** Ajouter `DEFAULT_THROTTLE_CLASSES` et `DEFAULT_THROTTLE_RATES` dans cette section.

**Environment Variables Pattern (Story 17.5):**
```python
# Fichier : django_backend/idp_backend/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Exemple de variable sécurisée avec fail-fast
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY and ENVIRONMENT == 'production':
    raise ValueError("SECRET_KEY must be set in production")
```
**Utilisation :** Appliquer même pattern pour `THROTTLE_*_RATE` variables.

**Structured Logging Pattern (Story 17.7):**
```python
# Fichier : django_backend/core/middleware.py:119-127
logger.info(
    "request_received",
    correlation_id=correlation_id,
    method=request.method,
    path=request.path,
    ip_address=get_client_ip(request),
    user_agent=request.META.get('HTTP_USER_AGENT', ''),
    user_id=user_id,
)
```
**Utilisation :** Logger les violations de rate limit avec même format structuré.

### Librairies et Frameworks

**Django REST Framework Throttling (Built-in):**
- **Version** : DRF 3.16.1 (déjà installé)
- **Classes** : `AnonRateThrottle`, `UserRateThrottle`, `ScopedRateThrottle`
- **Docs** : https://www.django-rest-framework.org/api-guide/throttling/
- **Configuration** :
  ```python
  REST_FRAMEWORK = {
      'DEFAULT_THROTTLE_CLASSES': [
          'rest_framework.throttling.AnonRateThrottle',
          'rest_framework.throttling.UserRateThrottle',
      ],
      'DEFAULT_THROTTLE_RATES': {
          'anon': '50/minute',
          'user': '100/minute',
      }
  }
  ```
- **Avantages** : Intégré DRF, supporte cache Django, headers automatiques
- **Limitations** : Seulement pour DRF ViewSets/APIViews (pas pour views Django standards comme SAML)

**django-ratelimit 4.1.0:**
- **Installation** : `pip install django-ratelimit==4.1.0`
- **Usage** : Decorator `@ratelimit(key='ip', rate='10/m', method='POST')`
- **Docs** : https://django-ratelimit.readthedocs.io/
- **Avantages** : Fonctionne avec views Django standards, flexible (key: ip, user, header)
- **Configuration** :
  ```python
  # settings.py
  RATELIMIT_USE_CACHE = 'default'  # Utilise le cache Django configuré
  RATELIMIT_ENABLE = True
  ```
- **Custom 429 handler** :
  ```python
  # urls.py
  handler429 = 'core.views.ratelimit_error_handler'
  ```

**Cache Backend (settings.py):**
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'idp-ratelimit-cache',
    }
}
```
**Note** : Pour production multi-instances, remplacer par Redis :
```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

### Intelligence des Stories Précédentes

**Story 17.5 (Secrets Management):**
- Pattern de fail-fast pour variables critiques en production
- Validation au startup dans `core/startup_checks.py`
- **Learnings** : Appliquer même validation pour format des rate configurations

**Story 17.7 (Structured Logging Frontend):**
- Service de logging avec niveaux (debug/info/warn/error)
- Format structuré JSON pour parsing
- **Learnings** : Utiliser même approche pour logger rate limit violations côté backend

**Story 17.10 (Dockerfiles):**
- Variables d'environnement injectées via `.env` ou `/etc/idp/django.env`
- Healthcheck sur `/api/v1/health`
- **Learnings** : Rate limiting ne doit PAS bloquer endpoint healthcheck (whitelist)

**Story M.8 (Middleware Logging):**
- `RequestResponseLoggingMiddleware` déjà en place
- Logs `request_received` et `request_completed` avec duration_ms
- **Learnings** : Ajouter `rate_limit_exceeded` log event, aligner sur format existant

**Story 15.2 (Security Functional Tests):**
- 154 tests sécurité fonctionnels (auth, RBAC, endpoints)
- Pattern de test : simuler attaques, vérifier blocage
- **Learnings** : Créer tests similaires pour brute-force login et rate limit bypass attempts

### Architecture Patterns à Suivre

**1. Middleware Chain Pattern:**
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',        # 1. Django security
    'core.middleware.CorrelationIdMiddleware',              # 2. UUID per request
    'core.middleware.RequestResponseLoggingMiddleware',     # 3. Logging
    'core.middleware.RateLimitHeadersMiddleware',           # 4. NEW - Rate limit headers
    'core.middleware.SecurityHeadersMiddleware',            # 5. Security headers
    # ... autres middleware
]
```
**Ordre important :** Rate limit headers après CorrelationId (pour logging), avant SecurityHeaders.

**2. DRF Throttle Class Pattern:**
```python
# core/throttling.py
from rest_framework.throttling import UserRateThrottle
from django.conf import settings

class ExecutionThrottle(UserRateThrottle):
    """Rate limit for execution POST endpoints."""
    scope = 'execution'

    def get_rate(self):
        """Allow runtime configuration via env vars."""
        return settings.THROTTLE_EXECUTION_RATE or '30/min'
```

**3. Graceful Degradation Pattern:**
```python
# Si cache indisponible, ne pas bloquer
try:
    # Check rate limit in cache
    pass
except CacheException:
    logger.error("rate_limit_cache_unavailable", exc_info=True)
    # Allow request to proceed (fail open, not fail closed)
    return None  # No throttling
```

**4. Configuration Validation Pattern (Story 17.5):**
```python
# core/startup_checks.py
def validate_rate_limit_config():
    """Validate rate limit configuration at startup."""
    import re
    rate_pattern = re.compile(r'^\d+/(s|m|h|d)$')

    rates = {
        'THROTTLE_AUTH_RATE': settings.THROTTLE_AUTH_RATE,
        'THROTTLE_EXECUTION_RATE': settings.THROTTLE_EXECUTION_RATE,
    }

    for key, value in rates.items():
        if not rate_pattern.match(value):
            raise ValueError(f"{key} has invalid format: {value}. Expected: <count>/<period>")
```

### Files et Chemins Importants

**Fichiers à Modifier:**
- `django_backend/idp_backend/settings.py` : Configuration DRF throttling, cache, env vars
- `django_backend/core/middleware.py` : Nouveau middleware `RateLimitHeadersMiddleware`
- `django_backend/auth/views.py` : Appliquer `@ratelimit` decorator aux views SAML
- `django_backend/.env.production.template` : Variables d'environnement rate limiting
- `django_backend/pyproject.toml` : Ajouter `django-ratelimit==4.1.0`

**Fichiers à Créer:**
- `django_backend/core/throttling.py` : Classes custom throttle pour DRF
- `django_backend/core/tests/test_rate_limiting.py` : Tests unitaires
- `django_backend/security_tests/test_rate_limiting_security.py` : Tests sécurité

**Fichiers à Documenter:**
- `docs/security-architecture.md` : Section Rate Limiting (ajout)
- `docs/backend/api-reference.md` : Documenter headers `X-RateLimit-*` et réponses 429

**Structure Cache Keys:**
```
# DRF throttling keys
throttle_user_<user_id>_<scope>  # Ex: throttle_user_42_execution
throttle_anon_<ip>_<scope>       # Ex: throttle_anon_192.168.1.1_auth

# django-ratelimit keys
rl:<group>:<key_value>           # Ex: rl:saml_login:192.168.1.1
```

### Standards de Tests

**Pattern de Test Rate Limiting (DRF):**
```python
# core/tests/test_rate_limiting.py
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model

class ExecutionThrottleTestCase(APITestCase):
    def test_execution_rate_limited_after_30_requests(self):
        """Test that execution POST is rate limited at 30 req/min per user."""
        user = get_user_model().objects.create_user(username='dba1')
        self.client.force_authenticate(user=user)

        # Make 30 requests (should succeed)
        for i in range(30):
            response = self.client.post('/api/v1/executions/', {...})
            self.assertEqual(response.status_code, 201)

        # 31st request should be rate limited
        response = self.client.post('/api/v1/executions/', {...})
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response.headers)
```

**Pattern de Test Sécurité Brute-Force:**
```python
# security_tests/test_rate_limiting_security.py
class BruteForceProtectionTestCase(APITestCase):
    def test_saml_login_brute_force_blocked(self):
        """Test that SAML login brute-force is blocked after 10 attempts."""
        # Simulate 10 login attempts from same IP
        for i in range(10):
            response = self.client.get('/auth/saml/login', REMOTE_ADDR='192.168.1.100')
            self.assertIn(response.status_code, [200, 302])

        # 11th attempt should be rate limited
        response = self.client.get('/auth/saml/login', REMOTE_ADDR='192.168.1.100')
        self.assertEqual(response.status_code, 429)
```

### Références Techniques

**Web Research - Django Rate Limiting Best Practices 2026:**

**DRF Built-in Throttling:**
- [Throttling - Django REST framework](https://www.django-rest-framework.org/api-guide/throttling/)
- [Throttling and Rate-Limiting API Requests in Django REST Framework | Medium](https://medium.com/django-unleashed/throttling-and-rate-limiting-api-requests-in-django-rest-framework-428a599a49fe)
- Support multiple throttles (burst + sustained rates)
- Retourne 429 Too Many Requests par défaut

**Django Ratelimit:**
- [Django Ratelimit 4.1.0 documentation](https://django-ratelimit.readthedocs.io/)
- Decorator pour views Django standards
- Stockage dans cache Django configuré

**Patterns et Guides:**
- [A Guide To API Rate Limiting In Django - CoderPad](https://coderpad.io/blog/development/a-guide-to-api-rate-limiting-in-django/)
- [Throttling Traffic to Your Django App | Medium](https://medium.com/@mathur.danduprolu/throttle-traffic-to-your-django-app-implementing-a-rate-limiting-algorithm-afc58643ed4a)
- Custom middleware possible avec cache framework

### Project Structure Notes

**Alignment avec Architecture Unifiée:**
```
idp-portal/
├── django_backend/
│   ├── core/
│   │   ├── middleware.py           # Existing + RateLimitHeadersMiddleware
│   │   ├── throttling.py           # NEW - DRF throttle classes
│   │   ├── startup_checks.py       # Add rate config validation
│   │   └── tests/
│   │       └── test_rate_limiting.py  # NEW
│   ├── auth/
│   │   └── views.py                # Add @ratelimit decorators
│   ├── security_tests/
│   │   └── test_rate_limiting_security.py  # NEW
│   ├── idp_backend/
│   │   └── settings.py             # Configure throttling + cache
│   ├── pyproject.toml              # Add django-ratelimit
│   └── requirements.lock           # Regenerate after dep add
└── docs/
    └── security-architecture.md    # Document rate limiting
```

**Dépendances à Ajouter:**
- `django-ratelimit = "^4.1.0"` dans `[project.dependencies]` de `pyproject.toml`

**Pas de Conflits Détectés:**
- Middleware stack a de la place (6 middleware actuels, ajouter 1)
- Cache `default` déjà configuré (LocMemCache)
- DRF déjà installé, juste ajouter throttling config

### Recommandations de l'Agent

**Approche Hybride DRF + django-ratelimit:**
- **DRF throttling** pour tous les endpoints DRF (API v1, executions, catalog, etc.)
- **django-ratelimit** pour views Django non-DRF (SAML login, SAML ACS)
- **Avantage** : Meilleure couverture, utilise le même cache backend

**Seuils Recommandés (MVP):**
| Endpoint | Limite | Clé | Justification |
|---|---|---|---|
| `/auth/saml/login` | 10/min | IP | Prévention brute-force |
| `/auth/saml/acs` | 10/min | IP | Prévention replay attacks |
| `/api/v1/auth/token/refresh` | 20/min | User | Abuse modéré |
| `/api/v1/executions/` POST | 30/min | User | Usage légitime DBA |
| Endpoints API généraux | 100/min | User | Usage normal |
| Endpoints publics anon | 50/min | IP | Prévention scraping |

**Headers de Réponse Standard:**
```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1675432800  # Unix timestamp
Retry-After: 45  # Secondes
Content-Type: application/json

{
  "detail": "Request was throttled. Expected available in 45 seconds.",
  "code": "throttled"
}
```

**Migration Redis (Post-MVP):**
```python
# Pour production HA, ajouter django-redis
# pip install django-redis
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            }
        },
        'KEY_PREFIX': 'idp',
        'TIMEOUT': 300,
    }
}
```

**Whitelist Healthcheck:**
```python
# core/middleware.py - RateLimitHeadersMiddleware
RATE_LIMIT_WHITELIST_PATHS = [
    '/api/v1/health',
    '/health',
    '/metrics',  # Si Prometheus monitoring
]
```

**Monitoring et Alertes:**
- Requêtes 429 dans logs structurés → Query Splunk
- Alerte si taux 429 > 5% du trafic total (possible attaque DDoS)
- Dashboard : Taux 429 par endpoint, par IP, par utilisateur

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- Context continuation required due to context limit — see transcript 272d9829-5e44-462e-adfc-2ac7c3fa474c

### Completion Notes List

- **Décision architecturale :** django-ratelimit NON nécessaire — tous les endpoints (y compris SAML) sont des DRF APIView, donc DRF throttling built-in suffit
- **DRF THROTTLE_RATES class attribute bug :** `SimpleRateThrottle.THROTTLE_RATES` est un attribut de classe défini au chargement du module. `override_settings` ne le met pas à jour. Résolu dans les tests sécurité via `patch.object(SimpleRateThrottle, 'THROTTLE_RATES', LOW_RATES)`
- **RATELIMIT_ENABLED bypass :** Mixin `_RateLimitEnabledMixin` ajouté à toutes les classes throttle pour supporter le flag d'urgence
- **Exception handler 429 :** `core/exceptions.py` mis à jour pour propager Retry-After et utiliser code erreur THROTTLED
- **Tests : 37 total** (29 unitaires + 8 sécurité) — tous passent en isolation et combinés
- Configuration cache LocMemCache MVP, migration Redis documentée
- Documentation complète dans security-architecture.md (section 12)
- **Code Review Fixes (2026-02-07) :**
  - Ajout documentation scopes uniques dans throttling.py pour éviter collisions
  - Ajout docstring complète pour `_RateLimitEnabledMixin.allow_request()`
  - `get_client_ip()` log WARNING si X-Forwarded-For contient >2 IPs (détection spoofing)
  - Validation `RATELIMIT_ENABLED` format booléen dans startup_checks.py
  - Test exécution brute-force ajouté (TestExecutionBruteForce)
  - Documentation procédure d'ajustement dynamique enrichie (DDoS, rollback, formats valides)

### Change Log

| Date | Changement | Fichiers |
|---|---|---|
| 2026-02-07 | Implémentation complète rate limiting | core/throttling.py, settings.py, middleware.py, views.py |
| 2026-02-07 | Tests unitaires et sécurité | core/tests/test_rate_limiting.py, tests/security/test_rate_limiting_security.py |
| 2026-02-07 | Documentation | docs/security-architecture.md, .env.production.template |
| 2026-02-07 | Exception handler 429 | core/exceptions.py |
| 2026-02-07 | Startup validation | core/startup_checks.py, core/apps.py |

### File List

**Files Created:**
- `django_backend/core/throttling.py` — 5 DRF throttle classes + _RateLimitEnabledMixin
- `django_backend/core/tests/test_rate_limiting.py` — 29 unit tests
- `django_backend/tests/security/test_rate_limiting_security.py` — 7 security tests

**Files Modified:**
- `django_backend/idp_backend/settings.py` — CACHES, REST_FRAMEWORK throttling, MIDDLEWARE, CORS_EXPOSE_HEADERS, RATELIMIT_ENABLED
- `django_backend/core/middleware.py` — RateLimitHeadersMiddleware
- `django_backend/idp_auth/views.py` — throttle_classes on SAMLLoginView, SAMLCallbackView, RefreshTokenView, LogoutView
- `django_backend/executions/views.py` — throttle_classes on ExecutionsView
- `django_backend/core/exceptions.py` — THROTTLED error code, Retry-After propagation
- `django_backend/core/startup_checks.py` — validate_rate_limit_config()
- `django_backend/core/apps.py` — call validate_rate_limit_config on startup
- `django_backend/.env.production.template` — rate limiting section
- `docs/security-architecture.md` — section 12 Rate Limiting, middleware stack, OWASP, test counts

**Files Excluded (Not Story-Related):**
- `.claude/settings.local.json` — IDE configuration
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — Sprint tracking (auto-updated)
- `_bmad-output/planning-artifacts/epics.md` — Epic index (auto-updated)
- `node_modules/.vite/vitest/...` — Test runner cache
- `idp-portal/django_backend/static/icons/*.{jpg,png,svg}` — Unrelated static assets
