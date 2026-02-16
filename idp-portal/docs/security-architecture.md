# Architecture de Securite — Portail IDP

**Date :** 2026-02-06
**Version :** 1.0
**Projet :** IDP Portal (portail d'operations DBA)
**Auteur :** Equipe Securite — Story 15.4

---

## Resume Executif

Ce document decrit l'architecture de securite complete du portail IDP, incluant l'authentification SAML 2.0, l'autorisation RBAC granulaire, le chiffrement en transit, la gestion des secrets, les middleware de securite, et les procedures de reponse aux incidents.

**Architecture en 6 couches :**
1. **Reseau (Nginx)** : TLS 1.2+, HSTS, redirect HTTP→HTTPS
2. **Application (Django)** : Middleware stack securite (6 middleware)
3. **Authentification** : SAML 2.0 + JWT (access 30min, refresh 8h)
4. **RBAC 3 dimensions** : Action x Profil x Environnement
5. **Secrets** : credential_ref Vault, detect-secrets, pre-commit hooks
6. **Audit** : Logs immutables (trigger Oracle + Django model override)

**Tests de securite : 211** (154 fonctionnels + 23 SOC1 + 34 rate limiting) — 100% passing ✅

---

## Table des Matieres

1. [Architecture Generale](#1-architecture-generale)
2. [Couche 1 : Reseau (Nginx)](#2-couche-1--reseau-nginx)
3. [Couche 2 : Application (Django Middleware)](#3-couche-2--application-django-middleware)
4. [Couche 3 : Authentification SAML 2.0 + JWT](#4-couche-3--authentification-saml-20--jwt)
5. [Couche 4 : RBAC 3 Dimensions](#5-couche-4--rbac-3-dimensions)
6. [Couche 5 : Gestion des Secrets](#6-couche-5--gestion-des-secrets)
7. [Couche 6 : Audit Trail Immutable](#7-couche-6--audit-trail-immutable)
8. [Controles de Securite Implementes](#8-controles-de-securite-implementes)
9. [Guide Bonnes Pratiques Developpeurs](#9-guide-bonnes-pratiques-developpeurs)
10. [Procedures de Reponse aux Incidents](#10-procedures-de-reponse-aux-incidents)
11. [References Standards](#11-references-standards)
12. [Rate Limiting (Story 17.11)](#12-rate-limiting-story-1711)

---

## 1. Architecture Generale

### Diagramme des Couches de Securite

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLIENT (Navigateur)                          │
└─────────────────────────────────────────────────────────────────┘
                              ▼ HTTPS
┌─────────────────────────────────────────────────────────────────┐
│  COUCHE 1 : RESEAU (Nginx)                                      │
│  - TLS 1.2+ (ECDHE-ECDSA, ECDHE-RSA, CHACHA20-POLY1305)       │
│  - HSTS (max-age=31536000; includeSubDomains; preload)        │
│  - Redirect HTTP → HTTPS (port 80 → 443)                       │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  COUCHE 2 : APPLICATION (Django Middleware Stack)               │
│  1. SecurityMiddleware (Django built-in)                        │
│  2. CorrelationIdMiddleware (UUID par requete)                  │
│  3. RequestResponseLoggingMiddleware (Logging JSON structlog)   │
│  4. SecurityHeadersMiddleware (X-Frame, X-Content-Type, Cache)  │
│  5. AuthenticationMiddleware (Django)                           │
│  6. AuditAuthMiddleware (Journalisation 401 auth endpoints)     │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  COUCHE 3 : AUTHENTIFICATION                                    │
│  - SAML 2.0 SP-initiated (python3-saml)                        │
│  - JWT HS256 (access 30min, refresh 8h httpOnly secure)        │
│  - Dev bypass mode (desactive en production)                    │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  COUCHE 4 : RBAC 3 DIMENSIONS                                   │
│  - Profils : dbops, dba, dba_applicatif, dba_infrastructure,   │
│              client_business                                     │
│  - Permissions actions : ALL, LIST (action_ids), PATTERN (tags) │
│  - Restrictions environnements : dev, staging, prod             │
│  - Accumulation multi-profils (most permissive wins)            │
│  - Workflow approbation production                              │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  COUCHE 5 : SECRETS                                             │
│  - credential_ref = reference Vault (vault:secret/data/...)     │
│  - SECRET_KEY, JWT_SECRET_KEY via env vars                      │
│  - detect-secrets baseline + pre-commit hook                    │
│  - VaultService : placeholder (ecart documente)                 │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  COUCHE 6 : AUDIT                                               │
│  - Table AUDIT_LOG immutable (trigger Oracle V054 +            │
│    Django model override + ImmutableQuerySet)                   │
│  - correlation_id propage de bout en bout                       │
│  - Lifecycle : SUBMITTED → RUNNING → COMPLETED/FAILED          │
│  - API filtree par environnement, periode, type action          │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  SYSTEMES EXTERNES                                              │
│  - Ansible Automation Platform (AAP)                            │
│  - ServiceNow (changements preapprouves)                        │
│  - HashiCorp Vault (secrets)                                    │
│  - Oracle Database (donnees persistantes)                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Couche 1 : Reseau (Nginx)

### Configuration TLS

**Fichier :** `deployment/nginx-django.conf:17-30`

```nginx
# TLS Configuration
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305';
ssl_prefer_server_ciphers on;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;

# HSTS (HTTP Strict Transport Security)
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}
```

### Justification Choix TLS

| Protocole | Statut | Justification |
|---|---|---|
| TLSv1.0 | ❌ Desactive | Vulnerabilites connues (POODLE, BEAST) |
| TLSv1.1 | ❌ Desactive | Obsolete, vulnerabilites connues |
| TLSv1.2 | ✅ Active | Standard industrie, conforme PCI-DSS |
| TLSv1.3 | ✅ Active | Dernier standard, performance optimale |

### Cipher Suites

**Criteres de selection :**
- Forward secrecy (ECDHE)
- Authentification forte (ECDSA, RSA)
- Chiffrement moderne (AES-GCM, CHACHA20-POLY1305)
- Pas de cipher suites obsoletes (3DES, RC4, DES)

**Tests de validation :**
- `test_nginx_tls_configuration_exists` (Story 15.3)

---

## 3. Couche 2 : Application (Django Middleware)

### Middleware Stack

**Fichier :** `django_backend/idp_backend/settings.py:60-73`

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',        # 1. Django built-in security
    'core.middleware.CorrelationIdMiddleware',              # 2. UUID par requete
    'core.middleware.RequestResponseLoggingMiddleware',     # 3. Logging JSON structlog
    'core.middleware.SecurityHeadersMiddleware',            # 4. Headers securite
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware', # 5. Auth Django
    'core.middleware.AuditAuthMiddleware',                  # 6. Audit 401 auth endpoints
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

### 1. SecurityMiddleware (Django)

**Responsabilites :**
- Active SECURE_SSL_REDIRECT (production)
- Configure HSTS (SECURE_HSTS_SECONDS)
- Protege cookies (SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE)

### 2. CorrelationIdMiddleware

**Fichier :** `django_backend/core/middleware.py`

**Fonctionnement :**
```python
def process_request(self, request):
    correlation_id = request.headers.get('X-Idp-Request-Id') or str(uuid.uuid4())
    request.correlation_id = correlation_id
    _correlation_id.set(correlation_id)  # thread-local
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
```

**Tests de validation :**
- `test_correlation_id_propagated_from_request_to_audit` (Story 15.3)
- 17 tests headers securite (Story 15.2)

### 3. RequestResponseLoggingMiddleware

**Fonctionnement :**
- Logging JSON structure (structlog)
- Inclut : method, path, status_code, duration, correlation_id, user_id
- Masque donnees sensibles (passwords, tokens dans body)

### 4. SecurityHeadersMiddleware

**Headers ajoutes :**
```python
response['X-Frame-Options'] = 'DENY'
response['X-Content-Type-Options'] = 'nosniff'
response['Cache-Control'] = 'no-store'  # endpoints sensibles
```

**Tests de validation :**
- `test_x_frame_options_header` (Story 15.2)
- `test_x_content_type_options_header` (Story 15.2)
- `test_cache_control_on_sensitive_endpoints` (Story 15.2)

### 5. AuthenticationMiddleware (Django)

**Responsabilites :**
- Charge user depuis JWT (custom authentication backend)
- Associe request.user a l'utilisateur authentifie

### 6. AuditAuthMiddleware

**Fonctionnement :**
- Intercepte reponses 401 Unauthorized sur `/api/v1/auth`
- Cree entree AUDIT_LOG avec type `AUTH_FAILED`
- Enregistre : user_id (si disponible), ip_address, correlation_id, details (endpoint, reason)

**Tests de validation :**
- `test_audit_failed_authentication` (Story 15.2)

### Settings Securite Production

**Fichier :** `django_backend/idp_backend/settings.py` (conditions `if not DEBUG`)

```python
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 an
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

**Tests de validation :**
- `test_production_security_settings_enabled` (Story 15.3)
- `test_ssl_redirect_when_not_debug` (Story 15.3)

---

## 4. Couche 3 : Authentification SAML 2.0 + JWT

### Flow Complet SAML 2.0 SP-Initiated

```
1. USER → IDP Portal (/login)
   ↓
2. IDP Portal → SAML IdP (AuthnRequest)
   ↓
3. User authentifie sur SAML IdP
   ↓
4. SAML IdP → IDP Portal (SAMLResponse + Assertion)
   ↓
5. IDP Portal valide SAML Assertion (signature, expiration)
   ↓
6. IDP Portal cree JWT access token (HS256, 30min)
   ↓
7. IDP Portal cree JWT refresh token (HS256, 8h, httpOnly cookie)
   ↓
8. JWT access token → Client (response body)
   Refresh token → Client (Set-Cookie httpOnly secure samesite=lax)
```

### Configuration SAML 2.0

**Fichier :** `django_backend/idp_auth/saml_config.py`

**Parametres critiques :**
```python
saml_settings = {
    'sp': {
        'entityId': SAML_SP_ENTITY_ID,
        'assertionConsumerService': {
            'url': f'{SAML_SP_BASE_URL}/api/v1/auth/saml/acs',
            'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST'
        },
        'x509cert': SAML_SP_CERT,  # Certificat SP pour signature
        'privateKey': SAML_SP_KEY,  # Cle privee SP
    },
    'idp': {
        'entityId': SAML_IDP_ENTITY_ID,
        'singleSignOnService': {
            'url': SAML_IDP_SSO_URL,
            'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect'
        },
        'x509cert': SAML_IDP_CERT,  # Certificat IdP pour validation signature
    },
    'security': {
        'authnRequestsSigned': True,
        'wantAssertionsSigned': True,
        'wantMessagesSigned': True,
        'wantNameIdEncrypted': False,
    }
}
```

### JWT Access Token

**Fichier :** `django_backend/idp_auth/jwt_utils.py`

**Structure :**
```python
{
    "user_id": 123,
    "username": "john.doe",
    "display_name": "John Doe",
    "email": "john.doe@example.com",
    "profile_ids": [1, 2],
    "exp": 1738876800,  # Expiration 30 minutes
    "iat": 1738875000,  # Issued at
    "type": "access"    # Type token
}
```

**Algorithme :** HS256 (HMAC SHA-256)
**Secret :** `JWT_SECRET_KEY` (variable d'environnement)
**Expiration :** 30 minutes (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`)

### JWT Refresh Token

**Structure :**
```python
{
    "user_id": 123,
    "exp": 1738903200,  # Expiration 8 heures
    "iat": 1738875000,
    "type": "refresh"
}
```

**Cookie httpOnly secure :**
```python
response.set_cookie(
    key='refresh_token',
    value=refresh_token,
    httponly=True,
    secure=True,  # HTTPS uniquement
    samesite='lax',
    max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_HOURS * 3600
)
```

### Dev Bypass Mode

**Fichier :** `django_backend/idp_backend/settings.py`

```python
AUTH_DEV_BYPASS = env.bool('AUTH_DEV_BYPASS', default=False)
```

**Fonctionnement :**
- Si `AUTH_DEV_BYPASS=true` et `DEBUG=True` : endpoint `/api/v1/auth/dev-bypass` actif
- Genere JWT sans SAML (username hardcode ou parametre)
- **CRITIQUE :** TOUJOURS desactive en production (`if DEBUG`)

**Guard production (Story 30.5 — SEC-7) :**
- Si `AUTH_DEV_BYPASS=True` et `DEBUG=False` → log CRITICAL emis dans `SAMLLoginView.get()` et `JWTAuthentication.authenticate()`
- Message : `"SECURITY ALERT: AUTH_DEV_BYPASS is enabled in production mode (DEBUG=False). This creates a critical security vulnerability."`
- Permet la detection par les outils de monitoring (Splunk, Dynatrace)

**Limitation connue (SEC-11) :** Le token d'acces est passe dans le fragment URL (`#access_token=...`) en mode dev bypass. Le fragment n'est pas envoye au serveur mais reste visible dans l'historique navigateur. Acceptable pour dev uniquement. Production utilise le flow SAML standard.

**Tests de validation :**
- 52 tests authentification JWT (Story 15.2)
- 5 tests guard production (Story 30.5 — SEC-7)
- `test_jwt_valid_token` : Token valide accepte
- `test_jwt_expired_token` : Token expire rejete
- `test_jwt_invalid_signature` : Signature incorrecte rejetee
- `test_jwt_token_type_mismatch` : Refresh token comme access rejete
- `test_jwt_corrupted_token` : Token corrompu rejete

### File Upload Security (Story 30.5)

**Fichier :** `django_backend/integrations/upload_views.py`

**3 couches de validation :**

1. **Extension allowlist (SEC-5)** : Seules les extensions `.png`, `.jpg`, `.jpeg`, `.svg`, `.gif` sont acceptees. Toute autre extension est rejetee avec erreur 400.

2. **Magic bytes validation (SEC-10)** : Le contenu reel du fichier est verifie via `puremagic` (pure Python). Un fichier avec extension `.png` mais contenu executable est rejete. SVG exempte (format texte XML).

3. **SVG sanitization (SEC-6)** : Les fichiers SVG sont parses avec `defusedxml` et sanitises :
   - Balises `<script>` supprimees
   - Attributs event handlers (`onclick`, `onerror`, `onload`, etc.) supprimes
   - Balises `<style>` contenant du JavaScript supprimees
   - Attributs `href`/`xlink:href` avec protocole `javascript:` supprimes

**Tests :** 27 tests upload security (Story 30.5 — AC9)

---

## 5. Couche 4 : RBAC 3 Dimensions

### Modele RBAC

**Dimensions :**
1. **Action** : Quelle action est autorisee
2. **Profil** : Quel profil utilisateur
3. **Environnement** : Sur quel environnement (dev, staging, prod)

### Profils Disponibles

| Profil | Description | Environnements Autorises | Workflow Approbation Prod |
|---|---|---|---|
| **dbops** | Super-admin DBA (tous pouvoirs) | dev, staging, prod | ❌ Non (acces direct prod) |
| **dba** | DBA standard (actions moderees) | dev, staging, prod | ✅ Oui (approbation requise prod) |
| **dba_applicatif** | DBA applicatif (bases app) | dev, staging | ❌ Non (pas acces prod) |
| **dba_infrastructure** | DBA infra (bases infra) | dev, staging, prod | ✅ Oui |
| **client_business** | Client business (actions preapprouvees) | staging, prod | ✅ Oui |

### Permissions Actions

**Types de permissions :**

#### 1. ALL (toutes les actions)

```python
ProfileActionPermission.objects.create(
    profile=dbops_profile,
    permission_type='ALL',
    action_ids=None,
    action_tag_pattern=None
)
```

**Effet :** Autorise execution de TOUTES les actions du catalogue

#### 2. LIST (liste explicite d'actions)

```python
ProfileActionPermission.objects.create(
    profile=dba_profile,
    permission_type='LIST',
    action_ids=[1, 5, 10],  # IDs des actions autorisees
    action_tag_pattern=None
)
```

**Effet :** Autorise uniquement les actions dont l'ID est dans la liste

#### 3. PATTERN (pattern de tags)

```python
ProfileActionPermission.objects.create(
    profile=client_business_profile,
    permission_type='PATTERN',
    action_ids=None,
    action_tag_pattern='patching,backup'  # Tags separes par virgule
)
```

**Effet :** Autorise toutes les actions ayant AU MOINS UN des tags specifies

### Restrictions Environnements

**Table :** `PROFILE_TARGET_PERMISSIONS`

```python
ProfileTargetPermission.objects.create(
    profile=dba_applicatif_profile,
    environment='dev',   # ou 'staging', 'prod'
    target_pattern='%'   # Tous les targets de cet environnement
)
```

**Filtrage :**
- Inventory API `/api/v1/inventory/targets` filtre par environnements autorises
- Execution API `/api/v1/executions` valide environnement des targets

### Accumulation Multi-Profils

**Principe :** Most permissive wins (le plus permissif gagne)

**Exemple :**
```python
user.profiles = [dba_applicatif, dba_infrastructure]

# dba_applicatif : LIST [1, 2, 3], environments = ['dev', 'staging']
# dba_infrastructure : LIST [4, 5], environments = ['dev', 'staging', 'prod']

# Resultat accumule :
# - Actions autorisees : [1, 2, 3, 4, 5]
# - Environnements autorises : ['dev', 'staging', 'prod']
```

**Implementation :**
- Service `RBACService.get_authorized_actions(user)`
- Service `RBACService.get_authorized_environments(user)`
- Service `RBACService.check_action_permission(user, action, target_names)`

### Workflow Approbation Production

**Condition :** Execution sur environnement `prod` par profil non-dbops

**Flow :**
```
1. User soumet execution sur target prod
   ↓
2. Systeme cree ApprovalRequest (statut PENDING)
   ↓
3. Execution reste PENDING_APPROVAL
   ↓
4. DBA dbops approuve/rejette via API /api/v1/executions/{id}/approve
   ↓
5. Si approuve : execution demarre
   Si rejette : execution annulee
```

**Tests de validation :**
- 34 tests autorisation RBAC (Story 15.2)
- 27 tests controle granulaire (Story 15.2)
- `test_production_requires_approval_for_dba` (Story 15.2)
- `test_dbops_bypass_approval` (Story 15.2)

---

## 6. Couche 5 : Gestion des Secrets

### Principe : credential_ref = Reference Vault

**Modele Integration :**

```python
class Integration(models.Model):
    name = models.CharField(max_length=100)
    integration_type = models.CharField(max_length=50)  # AAP, VAULT, SERVICENOW, etc.
    credential_ref = models.CharField(max_length=255)   # vault:secret/data/aap/prod
    # PAS de champ 'password' ou 'api_key'
```

**Format credential_ref :**
```
vault:secret/data/<path>/<to>/<secret>
```

### Variables d'Environnement

**Fichier :** `django_backend/idp_backend/settings.py`

```python
SECRET_KEY = env('SECRET_KEY')  # Cle Django pour signing cookies/sessions
JWT_SECRET_KEY = env('JWT_SECRET_KEY')  # Cle JWT pour signature tokens
```

**Fichier production :** `.env` (NON commite dans git, via `.gitignore`)

**Template :** `.env.production.template`

```bash
SECRET_KEY=CHANGE_ME_PRODUCTION_SECRET_KEY_50_CHARS_MIN
JWT_SECRET_KEY=CHANGE_ME_JWT_SECRET_KEY_32_CHARS_MIN
SAML_SP_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
VAULT_ADDR=https://vault.example.com:8200
VAULT_TOKEN=hvs.XXXXXXXXXXXXX
```

### Startup Secret Validation (Story 17.5)

**Fail-Fast Pattern :** L'application refuse de demarrer si des secrets critiques sont manquants ou contiennent des valeurs par defaut en environnement non-dev.

**Secrets proteges :**
- `SECRET_KEY` : Protection sessions/CSRF Django
- `JWT_SECRET_KEY` : Cle de signature tokens
- `ORACLE_PASSWORD` : Credentials base de donnees
- `SAML_*_CERT_PATH` : Chemins certificats SAML (si `AUTH_DEV_BYPASS=false`)

**Regles de validation :**
1. Production/Staging : Valeurs manquantes ou par defaut → `ImproperlyConfigured`
2. Development : Valeurs par defaut autorisees mais loguees en warning
3. Detection placeholders : Patterns `CHANGE_*`, `<VARIABLE>`, `TODO:` rejetes

**Implementation :**
- Module : `core/startup_checks.py`
- Point d'entree : `core/apps.CoreConfig.ready()`
- Tests : `tests/security/test_soc1_compliance.py::TestSecretValidation`
- Tests unitaires : `core/tests/test_startup_checks.py`

### detect-secrets

**Fichier :** `.secrets.baseline`

**Commande scan :**
```bash
detect-secrets scan --all-files --baseline .secrets.baseline
```

**Faux positifs :**
- Tests : `django_backend/tests/`
- Templates : `.env.production.template`
- Docs : `docs/`

**Pre-commit hook :**

**Fichier :** `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        exclude: |
          (?x)^(
            django_backend/tests/.*|
            .*\.template|
            docs/.*
          )$
```

**Tests de validation :**
- `test_no_secrets_in_integration_config` (Story 15.3)
- `test_no_secrets_in_settings_file` (Story 15.3)
- `test_detect_secrets_baseline_exists` (Story 15.3)
- detect-secrets scan : 0 secrets reels (Story 15.1)

### VaultService (Ecart Documente)

**Statut actuel :** Placeholder (mock dans tests)

**Plan implementation (Sprint suivant) :**

```python
class VaultService:
    def __init__(self, vault_addr: str, vault_token: str):
        self.client = hvac.Client(url=vault_addr, token=vault_token)
        self.cache = {}  # Cache secrets avec TTL
        self.circuit_breaker = CircuitBreaker(threshold=5, timeout=60)

    def get_secret(self, credential_ref: str) -> str:
        # Parse credential_ref : vault:secret/data/path/to/secret
        path = credential_ref.replace('vault:', '')

        # Check cache
        if path in self.cache and not self.is_expired(path):
            return self.cache[path]

        # Circuit breaker check
        if self.circuit_breaker.is_open():
            raise VaultUnavailableError("Circuit breaker open")

        # Retry logic (3x avec exponential backoff)
        for attempt in range(3):
            try:
                response = self.client.secrets.kv.v2.read_secret_version(path=path)
                secret = response['data']['data']['value']
                self.cache[path] = secret
                return secret
            except VaultError as e:
                if attempt == 2:
                    self.circuit_breaker.record_failure()
                    raise
                time.sleep(2 ** attempt)  # 1s, 2s, 4s
```

**Criteres acceptation :**
- Retry 3x avec backoff exponentiel
- Circuit breaker (5 echecs → ouvert 60s)
- Cache secrets (TTL 5 min)
- Tests integration Vault dev

---

## 7. Couche 6 : Audit Trail Immutable

### Defense en Profondeur : Trigger Oracle + Django Model Override

#### Couche 1 : Trigger Oracle

**Fichier :** `database/migrations/V054__audit_log_immutable_trigger.sql`

```sql
CREATE OR REPLACE TRIGGER TRG_AUDIT_LOG_IMMUTABLE
BEFORE UPDATE OR DELETE ON AUDIT_LOG
FOR EACH ROW
BEGIN
    RAISE_APPLICATION_ERROR(-20001, 'AUDIT_LOG is immutable - UPDATE/DELETE operations are not allowed');
END;
/
```

**Effet :** Rejette TOUTE tentative UPDATE ou DELETE sur table AUDIT_LOG au niveau base de donnees

#### Couche 2 : Django Model Override

**Fichier :** `django_backend/core/models.py`

```python
class AuditLog(models.Model):
    # ... fields ...

    def save(self, *args, **kwargs):
        if self.pk:
            raise IntegrityError("AuditLog instances cannot be updated once created")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise IntegrityError("AuditLog instances cannot be deleted")

    class Meta:
        db_table = 'AUDIT_LOG'
```

#### Couche 3 : ImmutableQuerySet

**Fichier :** `django_backend/core/models.py`

```python
class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise IntegrityError("AuditLog instances cannot be updated")

    def delete(self):
        raise IntegrityError("AuditLog instances cannot be deleted")

class AuditLogManager(models.Manager):
    def get_queryset(self):
        return ImmutableQuerySet(self.model, using=self._db)
```

### Champs Audit Log

```python
class AuditLog(models.Model):
    id = models.AutoField(primary_key=True)
    user_id = models.IntegerField(null=True)
    action_type = models.CharField(max_length=50)
    entity_type = models.CharField(max_length=50, null=True)
    entity_id = models.IntegerField(null=True)
    details = models.JSONField(null=True)
    ip_address = models.CharField(max_length=45, null=True)
    correlation_id = models.CharField(max_length=36, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Types d'Actions Auditees

**Fichier :** `django_backend/core/models.py` (AuditActionType enum)

| Type | Description |
|---|---|
| `AUTH_LOGIN` | Authentification reussie |
| `AUTH_LOGOUT` | Deconnexion |
| `AUTH_FAILED` | Tentative authentification echouee |
| `EXECUTION_SUBMITTED` | Execution soumise |
| `EXECUTION_RUNNING` | Execution demarree |
| `EXECUTION_COMPLETED` | Execution reussie |
| `EXECUTION_FAILED` | Execution echouee |
| `EXECUTION_CANCELLED` | Execution annulee |
| `APPROVAL_REQUESTED` | Approbation demandee |
| `APPROVAL_APPROVED` | Approbation accordee |
| `APPROVAL_REJECTED` | Approbation rejetee |
| `ACTION_CREATED` | Action creee (admin) |
| `ACTION_UPDATED` | Action modifiee (admin) |
| `ACTION_DELETED` | Action supprimee (admin) |
| `PROFILE_CREATED` | Profil cree (admin) |
| `PROFILE_UPDATED` | Profil modifie (admin) |
| `PROFILE_DELETED` | Profil supprime (admin) |
| `INTEGRATION_CREATED` | Integration creee (admin) |
| `INTEGRATION_UPDATED` | Integration modifiee (admin) |
| `INTEGRATION_DELETED` | Integration supprimee (admin) |

### API Consultation Audit

**Endpoint :** `GET /api/v1/audit`

**Filtres :**
- `environment` : Filtrer par environnement (dev, staging, prod)
- `action_type` : Filtrer par type d'action
- `start_date`, `end_date` : Periode
- `user_id` : Filtrer par utilisateur
- `entity_type`, `entity_id` : Filtrer par entite

**Permissions :**
- RBAC dbops : Acces tous les logs
- RBAC dba : Acces logs de ses environnements autorises
- RBAC client_business : Acces logs de ses propres executions

**Tests de validation :**
- 11 tests audit trail immutable (Story 15.3)
- `test_audit_log_update_raises_error`
- `test_audit_log_delete_raises_error`
- `test_audit_log_save_existing_raises_error`
- `test_audit_log_bulk_delete_raises_error`
- `test_audit_filter_by_environment`
- `test_correlation_id_propagated_from_request_to_audit`

---

## 8. Controles de Securite Implementes

### Matrice des Controles

| Controle | Exigence | Implementation | Tests | Statut |
|---|---|---|---|---|
| **FR30** | Audit trail immutable | Trigger Oracle + Django override + ImmutableQuerySet | 11 tests | ✅ CONFORME |
| **FR33** | Consultation audit filtree | API /api/v1/audit avec filtres env/type/periode | 3 tests | ✅ CONFORME |
| **NFR6** | Chiffrement en transit | TLS 1.2+ Nginx + Django settings production | 3 tests | ✅ CONFORME |
| **NFR7** | Zero credentials stockes | credential_ref Vault + detect-secrets | 4 tests | ✅ CONFORME |
| **NFR8** | Logs immutables | Defense en profondeur (trigger + model + queryset) | 6 tests | ✅ CONFORME |
| **NFR9** | Sessions 30min | JWT access token expiration 30min | 52 tests auth | ✅ CONFORME |
| **NFR10** | Journalisation acces non autorise | AuditAuthMiddleware + RBAC tests | 61 tests RBAC | ✅ CONFORME |
| **NFR11** | Pas de donnees sensibles | Scan modeles + masquage erreurs 500 | 4 tests | ✅ CONFORME |
| **FR29** | Secrets via Vault | credential_ref = reference Vault (VaultService placeholder) | 2 tests | ⚠️ PARTIEL |

**Total tests securite : 211** (154 fonctionnels + 23 SOC1 + 34 rate limiting)

### Middleware Stack Complete

| # | Middleware | Responsabilite | Ordre Critique |
|---|---|---|---|
| 1 | SecurityMiddleware | Django built-in (SSL redirect, HSTS, cookies secure) | ✅ Premier |
| 2 | CorrelationIdMiddleware | UUID par requete, thread-local, structlog contextvars | ✅ Avant logging |
| 3 | RequestResponseLoggingMiddleware | Logging JSON structure (method, path, status, duration, correlation_id) | ✅ Avant auth |
| 4 | RateLimitHeadersMiddleware | Detection 429, logging rate_limit_exceeded, header Retry-After (Story 17.11) | ✅ Apres logging |
| 5 | SecurityHeadersMiddleware | X-Frame-Options, X-Content-Type-Options, Cache-Control | ✅ Avant auth |
| 6 | AuthenticationMiddleware | Django authentication (charge user depuis JWT) | ✅ Apres security |
| 7 | AuditAuthMiddleware | Journalisation 401 sur /api/v1/auth | ✅ Apres auth |

---

## 9. Guide Bonnes Pratiques Developpeurs

### 1. Utilisation ORM Django

**✅ BON :**

```python
# Utiliser ORM avec parametres prepares
from django.db.models import Q

targets = InventoryTarget.objects.filter(
    Q(environment='prod') & Q(name__in=target_names)
)
```

**❌ MAUVAIS :**

```python
# JAMAIS de SQL brut non securise
query = f"SELECT * FROM targets WHERE name = '{user_input}'"  # SQL Injection!
cursor.execute(query)
```

**⚠️ ACCEPTABLE (avec precautions) :**

```python
# SQL brut UNIQUEMENT si variable controlee application
from django.db import connection

# target_table = "IDP_INVENTORY_TARGETS" (controle par app, pas user input)
with connection.cursor() as cursor:
    query = f"SELECT * FROM {target_table} WHERE name = %s"  # %s = bind variable
    cursor.execute(query, [target_name])  # nosec B608
```

### 2. Gestion des Secrets

**✅ BON :**

```python
# Variables d'environnement
import environ
env = environ.Env()

SECRET_KEY = env('SECRET_KEY')
JWT_SECRET_KEY = env('JWT_SECRET_KEY')

# credential_ref Vault
integration.credential_ref = 'vault:secret/data/aap/prod'
```

**❌ MAUVAIS :**

```python
# JAMAIS de secrets hardcodes
SECRET_KEY = 'django-insecure-hardcoded-key'  # Detect-secrets trigger!
api_key = 'my-secret-api-key-12345'  # Detect-secrets trigger!
```

### 3. Utilisation Factories dans Tests

**✅ BON :**

```python
from tests.factories import UserFactory, ProfileFactory, ActionFactory

def test_user_with_profile():
    profile = ProfileFactory(name='dba')
    user = UserFactory(profiles=[profile])
    assert user.profiles.count() == 1
```

**❌ MAUVAIS :**

```python
# EVITER creation manuelle avec secrets hardcodes
def test_user():
    user = User.objects.create(
        username='test',
        password='hardcoded-password-123'  # Detect-secrets trigger!
    )
```

### 4. Patterns try/except

**✅ BON :**

```python
import structlog
logger = structlog.get_logger(__name__)

try:
    result = risky_operation()
except SpecificError as e:
    logger.warning("Operation failed gracefully", error=str(e), exc_info=True)
    # Fallback ou re-raise si necessaire
```

**⚠️ ACCEPTABLE (avec justification) :**

```python
try:
    optional_feature()
except FeatureUnavailableError:
    pass  # Feature optionnelle, echec acceptable
    # TODO: Ajouter logging si necessaire pour debug
```

**❌ MAUVAIS :**

```python
try:
    critical_operation()
except Exception:
    pass  # Erreur silencieuse sur operation critique!
```

### 5. Audit Trail

**✅ BON :**

```python
from core.models import AuditLog, AuditActionType

AuditLog.objects.create(
    user_id=request.user.id,
    action_type=AuditActionType.EXECUTION_SUBMITTED,
    entity_type='execution',
    entity_id=execution.id,
    details={'action_name': action.name, 'environment': environment},
    ip_address=request.META.get('REMOTE_ADDR'),
    correlation_id=request.correlation_id
)
```

**❌ MAUVAIS :**

```python
# JAMAIS tenter de modifier/supprimer audit log
audit_log.details = new_details
audit_log.save()  # IntegrityError!

audit_log.delete()  # IntegrityError!
```

### 6. Headers Securite

**✅ BON :**

```python
# SecurityHeadersMiddleware ajoute automatiquement
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff
# Cache-Control: no-store (si endpoint sensible)

@api_view(['GET'])
def sensitive_endpoint(request):
    # Headers deja ajoutes par middleware
    return Response(data)
```

**❌ MAUVAIS :**

```python
# EVITER desactiver headers securite
response = Response(data)
del response['X-Frame-Options']  # Expose a clickjacking!
```

### 7. Validation Entrees Utilisateur

**✅ BON :**

```python
from rest_framework import serializers

class ExecutionSerializer(serializers.Serializer):
    action_id = serializers.IntegerField(min_value=1)
    target_names = serializers.ListField(
        child=serializers.CharField(max_length=255),
        max_length=100
    )
    parameters = serializers.JSONField()

    def validate_parameters(self, value):
        # Validation business logic
        if not isinstance(value, dict):
            raise serializers.ValidationError("Parameters must be a dict")
        return value
```

**❌ MAUVAIS :**

```python
# EVITER utiliser directement request.data sans validation
action_id = request.data['action_id']  # Peut crasher si absent
parameters = request.data.get('parameters', {})  # Pas de validation type
```

---

## 10. Procedures de Reponse aux Incidents

### 1. Detection

**Sources de detection :**
- **Logs structlog** : Erreurs, warnings, acces non autorises
- **Audit trail** : Activites suspectes (multiples 401, tentatives acces prod non autorisees)
- **Monitoring externe** : Alertes Prometheus/Grafana (si configure)

**Commandes investigation :**

```bash
# Logs Django
tail -f django_backend/logs/app.log | grep "ERROR"

# Audit trail (SQL)
SELECT * FROM AUDIT_LOG
WHERE action_type = 'AUTH_FAILED'
  AND created_at > SYSDATE - 1
ORDER BY created_at DESC;

# Audit trail (API)
curl -H "Authorization: Bearer $TOKEN" \
  "https://portal.example.com/api/v1/audit?action_type=AUTH_FAILED&start_date=2026-02-06"
```

### 2. Isolation

**Actions immediates :**

1. **Desactiver utilisateur compromis :**
```python
from core.models import User
user = User.objects.get(username='compromised_user')
user.is_active = False
user.save()
```

2. **Invalider sessions JWT :**
```bash
# Rotation JWT_SECRET_KEY
# 1. Generer nouveau secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Mettre a jour .env
JWT_SECRET_KEY=nouveau_secret_genere

# 3. Redemarrer application
sudo systemctl restart gunicorn
```

3. **Bloquer IP source (Nginx) :**
```nginx
# /etc/nginx/conf.d/blocked_ips.conf
deny 192.168.1.100;
deny 203.0.113.0/24;

# Recharger Nginx
sudo nginx -s reload
```

### 3. Investigation

**Checklist investigation :**

- [ ] Identifier correlation_id de l'incident (logs ou audit trail)
- [ ] Tracer toutes les requetes avec ce correlation_id
- [ ] Identifier user_id et ip_address de l'attaquant
- [ ] Lister toutes les actions executees par cet utilisateur (audit trail)
- [ ] Verifier si acces non autorise a donnees sensibles
- [ ] Identifier vecteur d'attaque (JWT vole, SAML compromis, etc.)

**Requetes SQL investigation :**

```sql
-- Toutes les actions d'un utilisateur suspect
SELECT * FROM AUDIT_LOG
WHERE user_id = 123
ORDER BY created_at DESC;

-- Toutes les actions depuis une IP suspecte
SELECT * FROM AUDIT_LOG
WHERE ip_address = '192.168.1.100'
ORDER BY created_at DESC;

-- Executions non autorisees sur prod
SELECT al.*, e.status, e.action_id
FROM AUDIT_LOG al
JOIN EXECUTIONS e ON al.entity_id = e.id
WHERE al.action_type LIKE 'EXECUTION_%'
  AND e.environment = 'prod'
  AND al.user_id NOT IN (SELECT user_id FROM USER_PROFILES WHERE profile_id = 1)  -- Pas dbops
ORDER BY al.created_at DESC;
```

### 4. Correction

**Actions correctives :**

1. **Patch vulnerabilite exploitee**
2. **Renforcer controles acces** (RBAC plus restrictif si necessaire)
3. **Rotation secrets compromis** (JWT_SECRET_KEY, SAML certificates)
4. **Mise a jour dependances vulnerables** (pip-audit, npm audit)

### 5. Post-Mortem

**Template rapport post-mortem :**

```markdown
# Post-Mortem Incident Securite

**Date incident :** YYYY-MM-DD HH:MM
**Severite :** CRITICAL / HIGH / MEDIUM / LOW
**Duree :** X heures
**Impact :** Description impact (acces non autorise, donnees exposees, etc.)

## Chronologie

- HH:MM : Detection incident (source)
- HH:MM : Isolation (actions prises)
- HH:MM : Investigation (findings)
- HH:MM : Correction (patch)
- HH:MM : Verification (tests)
- HH:MM : Incident cloture

## Cause Racine

Description cause racine (vulnerabilite, configuration, erreur humaine)

## Actions Correctives

- [ ] Action 1 : Description (responsable, date cible)
- [ ] Action 2 : Description (responsable, date cible)

## Lessons Learned

- Lecon 1 : Ce qui a bien fonctionne
- Lecon 2 : Ce qui doit etre ameliore

## Suivi

- Date revue post-mortem : YYYY-MM-DD
- Actions preventives futures : Liste
```

---

## 11. References Standards

### SOC1 (Service Organization Control 1)

**Controles implementes :**
- Audit trail immutable (FR30, NFR8)
- Traçabilite complete executions (FR33)
- Chiffrement en transit (NFR6)
- Gestion secrets (NFR7, FR29)
- Protection donnees sensibles (NFR11)
- Sessions 30min (NFR9)
- Journalisation acces non autorise (NFR10)

**Rapport complet :** [`soc1-compliance-report.md`](soc1-compliance-report.md)

### OWASP Top 10 (2021)

| Vulnerabilite | Mitigation IDP Portal |
|---|---|
| **A01:2021 – Broken Access Control** | RBAC 3 dimensions + 61 tests autorisation |
| **A02:2021 – Cryptographic Failures** | TLS 1.2+ + HSTS + JWT HS256 + credential_ref Vault |
| **A03:2021 – Injection** | ORM Django + bind variables + validation DRF serializers |
| **A04:2021 – Insecure Design** | Defense en profondeur (trigger + model + queryset immutable) |
| **A05:2021 – Security Misconfiguration** | Settings production conditionnels (`if not DEBUG`) + security headers middleware |
| **A06:2021 – Vulnerable Components** | pip-audit + npm audit + CI/CD scan dependances |
| **A07:2021 – Identification/Auth Failures** | SAML 2.0 + JWT 30min + 52 tests auth + rate limiting DRF (Story 17.11) |
| **A08:2021 – Software/Data Integrity** | Audit trail immutable + correlation_id bout-en-bout |
| **A09:2021 – Security Logging Failures** | Logging structlog + audit trail + AuditAuthMiddleware |
| **A10:2021 – SSRF** | Pas de fetch URL utilisateur + validation URL integrations |

### Exigences Fonctionnelles et Non Fonctionnelles

**Exigences Fonctionnelles (FR) :**
- FR24-FR35 : Gestion utilisateurs, profils, RBAC, audit trail
- FR29 : Secrets via Vault (credential_ref)
- FR30 : Audit trail immutable
- FR33 : Consultation audit filtree

**Exigences Non Fonctionnelles (NFR) :**
- NFR6 : Chiffrement en transit (TLS 1.2+)
- NFR7 : Zero credentials stockes
- NFR8 : Logs immutables
- NFR9 : Sessions 30min
- NFR10 : Journalisation acces non autorise
- NFR11 : Pas de donnees sensibles

**Matrice de tracabilite :** Voir [`soc1-compliance-report.md`](soc1-compliance-report.md)

---

## 12. Rate Limiting (Story 17.11)

### Vue d'ensemble

Le rate limiting protege les endpoints publics et authentifies contre les abus, les attaques par force brute, et les requetes excessives. L'implementation utilise exclusivement le **throttling DRF built-in** (tous les endpoints sont des `APIView` DRF).

### Seuils par Endpoint

| Endpoint | Limite | Cle | Classe Throttle | Justification |
|---|---|---|---|---|
| `/auth/saml/login` | 10/min | IP | `AuthEndpointThrottle` | Prevention brute-force SSO |
| `/auth/saml/callback` | 10/min | IP | `AuthEndpointThrottle` | Prevention replay attacks |
| `/auth/refresh` | 20/min | IP | `TokenRefreshThrottle` | Abuse modere token refresh |
| `/executions/` POST | 30/min | User | `ExecutionThrottle` | Usage legitime DBA |
| Endpoints API generaux | 100/min | User | `GeneralAPIThrottle` | Usage normal authentifie |
| Endpoints publics anon | 50/min | IP | `PublicEndpointThrottle` | Prevention scraping |
| `/auth/logout` | 50/min | IP | `PublicEndpointThrottle` | Endpoint public |

### Architecture Technique

**Fichier :** `django_backend/core/throttling.py`

```python
# 5 classes de throttle DRF, toutes avec mixin _RateLimitEnabledMixin
class AuthEndpointThrottle(_RateLimitEnabledMixin, AnonRateThrottle):
    scope = 'auth'
    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': get_client_ip(request)}

class ExecutionThrottle(_RateLimitEnabledMixin, UserRateThrottle):
    scope = 'execution'

class GeneralAPIThrottle(_RateLimitEnabledMixin, UserRateThrottle):
    scope = 'general_api'  # Applique par defaut a tous les endpoints DRF
```

**Keying strategy :**
- **IP-based** (`AnonRateThrottle`) : Endpoints publics/auth — utilise `get_client_ip()` qui gere `X-Forwarded-For`
- **User-based** (`UserRateThrottle`) : Endpoints authentifies — cle par user ID

### Cache Backend

**MVP (single-instance) :**
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'idp-ratelimit-cache',
    }
}
```

**Production HA (multi-instances) — Migration Redis :**
```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
    }
}
```

**Limitation connue :** Avec LocMemCache, les compteurs sont perdus au restart et non partages entre instances.

### Middleware RateLimitHeadersMiddleware

**Fichier :** `django_backend/core/middleware.py`
**Position :** Apres `RequestResponseLoggingMiddleware`, avant `SecurityHeadersMiddleware`

**Responsabilites :**
1. Detection des reponses 429 Too Many Requests
2. Logging structure WARNING avec `correlation_id`, `ip_address`, `user_id`, `endpoint`, `method`, `user_agent`
3. Normalisation du header `Retry-After` (conversion float → int)
4. Exemption des endpoints healthcheck (`/api/v1/health`, `/health`, `/metrics`)

### Format Reponse 429

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 45
Content-Type: application/json

{
    "error": {
        "code": "THROTTLED",
        "message": "Request was throttled. Expected available in 45 seconds.",
        "details": {}
    }
}
```

### Configuration via Variables d'Environnement

**Fichier :** `.env.production.template`

```bash
RATELIMIT_ENABLED=true              # false = desactive tout rate limiting (urgence)
THROTTLE_AUTH_RATE=10/minute         # Endpoints auth (par IP)
THROTTLE_TOKEN_REFRESH_RATE=20/minute # Token refresh (par IP)
THROTTLE_EXECUTION_RATE=30/minute    # Executions POST (par user)
THROTTLE_API_RATE=100/minute         # API generales (par user)
THROTTLE_PUBLIC_RATE=50/minute       # Endpoints publics (par IP)
```

**Format :** `<count>/<period>` ou period = `second|s`, `minute|m|min`, `hour|h`, `day|d`

**Validation startup :** `core/startup_checks.py::validate_rate_limit_config()` valide le format au demarrage. Format invalide → `ImproperlyConfigured` (fail-fast).

### Procedure d'Ajustement Dynamique des Seuils

#### En Cas d'Attaque DDoS ou Abus Detecte

**Etape 1 : Evaluation**
- Query Splunk pour identifier endpoints/IPs abuses : `index=idp_portal event="rate_limit_exceeded" | stats count by endpoint, ip_address`
- Determiner si c'est un abus legitime (augmenter seuil) ou une attaque (reduire seuil)

**Etape 2 : Ajustement des seuils**
- Modifier `/etc/idp/django.env` ou variables d'environnement :
  ```bash
  # Exemple : Reduire auth rate de 10/min a 5/min
  THROTTLE_AUTH_RATE=5/minute
  ```
- **IMPORTANT :** Restart requis pour prendre effet (variables chargees au demarrage)

**Etape 3 : Redemarrage**
```bash
sudo systemctl restart gunicorn
# OU si Docker
docker restart idp-backend
```

**Etape 4 : Verification**
- Checker logs startup : `grep "rate_limit_config" /var/log/idp/django.log`
- Tester endpoint manuellement : faire 6 requetes rapides, verifier 429 a la 6eme

**Etape 5 : Monitoring post-ajustement**
- Surveiller taux 429 sur 15min
- Si taux 429 reste > 5% : investiguer cause racine (bot, script defectueux)

#### Rollback d'Urgence

Si le rate limiting cause des problemes operationnels (faux positifs massifs) :

```bash
# Desactiver TOUT le rate limiting
echo "RATELIMIT_ENABLED=false" >> /etc/idp/django.env
sudo systemctl restart gunicorn
```

**ATTENTION :** Ceci desactive TOUTE protection rate limit. A utiliser uniquement en urgence et restaurer `RATELIMIT_ENABLED=true` des que possible.

#### Formats Valides

- `<count>/second` ou `/s` : Ex `100/second`
- `<count>/minute` ou `/m` ou `/min` : Ex `10/minute`
- `<count>/hour` ou `/h` : Ex `1000/hour`
- `<count>/day` ou `/d` : Ex `10000/day`

**Validation automatique :** Format invalide = startup bloque avec `ImproperlyConfigured`.

### Monitoring

**Logs structures :** Chaque violation 429 emet un log WARNING :
```json
{
    "event": "rate_limit_exceeded",
    "correlation_id": "abc-123",
    "ip_address": "192.168.1.100",
    "user_id": "42",
    "endpoint": "/api/v1/executions/",
    "method": "POST",
    "user_agent": "Mozilla/5.0..."
}
```

**Query Splunk recommandee :**
```
index=idp_portal event="rate_limit_exceeded" | stats count by ip_address, endpoint | sort -count
```

**Alertes suggerees :**
- Taux 429 > 5% du trafic total → investigation DDoS potentiel
- > 50 violations/min depuis une meme IP → blocage Nginx recommande

### Tests

- **29 tests unitaires** : `core/tests/test_rate_limiting.py` (throttle classes, middleware, config validation, settings, RATELIMIT_ENABLED bypass)
- **8 tests securite** : `tests/security/test_rate_limiting_security.py` (brute-force SAML/token/execution, IP spoofing, persistance cache)

---

## Conclusion

Le portail IDP implementer une architecture de securite robuste en 6 couches de defense en profondeur, couvrant le chiffrement en transit, l'authentification SAML 2.0 + JWT, l'autorisation RBAC granulaire, la gestion des secrets via Vault, et l'audit trail immutable. **177 tests de securite automatises** valident en continu ces controles via CI/CD, garantissant la conformite SOC1 et la protection contre les vulnerabilites OWASP Top 10.

**Documents lies :**
- **Rapport audit securite :** [`security-audit-report.md`](security-audit-report.md)
- **Plan de remediation :** [`security-remediation-plan.md`](security-remediation-plan.md)
- **Rapport conformite SOC1 :** [`soc1-compliance-report.md`](soc1-compliance-report.md)
- **Validation release :** [`security-release-validation.md`](security-release-validation.md)

---

*Document cree pour Story 15.4 — Date: 2026-02-06*
