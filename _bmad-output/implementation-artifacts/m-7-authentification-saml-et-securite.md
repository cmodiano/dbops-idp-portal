# Story M.7: Authentification SAML et sécurité

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a responsable technique,
I want l'authentification SAML 2.0 et la gestion des sessions (JWT ou session Django) alignées avec la plateforme hébergeuse,
So que le portail IDP s'intègre à leur infra SSO et politique de sécurité.

## Acceptance Criteria

1. **Given** la plateforme hébergeuse utilise Django + SSO (SAML ou autre)
   **When** on intègre le mécanisme d'auth (django-saml2, python3-saml, ou proxy SSO côté hébergeur)
   **Then** un utilisateur non authentifié est redirigé vers l'IdP et revient avec une session valide
   **And** les attributs utilisateur (nom, groupes AD, etc.) sont disponibles pour la résolution des profils IDP (FR25, FR25a-d)
   **And** les tokens ou cookies de session respectent la politique de sécurité (httpOnly, durée, renouvellement)
   **And** NFR6 (TLS), NFR9 (expiration session), NFR10 (accès non autorisé journalisé) sont satisfaits
   **And** un document d'architecture ou runbook décrit l'interaction SSO entre le portail IDP et l'infra hébergeur

2. **Given** des tests d'auth (login, refresh, 401, 403)
   **When** on les exécute contre le backend Django
   **Then** les scénarios de succès et d'échec sont couverts

## Tasks / Subtasks

### Task 1: Analyser l'implémentation FastAPI SAML existante et définir la stratégie Django (AC: #1)

- [x] Subtask 1.1: Analyser `idp-portal/backend/app/api/v1/auth.py` — endpoints SAML login et callback FastAPI
- [x] Subtask 1.2: Analyser `idp-portal/backend/app/core/saml.py` — configuration python3-saml et helpers
- [x] Subtask 1.3: Analyser `idp-portal/backend/app/core/security.py` — génération/validation JWT (python-jose)
- [x] Subtask 1.4: Documenter le flow SAML complet FastAPI : SP-initiated, extraction attributs, création user, émission JWT
- [x] Subtask 1.5: Rechercher les options Django SAML : django-saml2, python3-saml avec Django views, ou proxy SSO hébergeur
- [x] Subtask 1.6: Décider de la stratégie : python3-saml (réutiliser) vs django-saml2 (intégration Django native) vs proxy SSO
- [x] Subtask 1.7: Documenter la décision dans `docs/drf-api-migration-notes.md` avec justification

### Task 2: Configurer SAML dans Django (AC: #1)

- [x] Subtask 2.1: Ajouter python3-saml dans `django_backend/requirements.txt` ou `pyproject.toml` (si pas déjà présent)
- [x] Subtask 2.2: Créer `idp_auth/saml_config.py` — fonction `get_saml_settings()` qui retourne le dict python3-saml (réutiliser logique FastAPI)
- [x] Subtask 2.3: Ajouter les settings SAML dans `idp_backend/settings.py` : SAML_SP_ENTITY_ID, SAML_SP_ACS_URL, SAML_IDP_ENTITY_ID, SAML_IDP_SSO_URL, SAML_IDP_SLO_URL, SAML_IDP_CERT_PATH, SAML_SP_KEY_PATH, SAML_SP_CERT_PATH
- [x] Subtask 2.4: Créer helper `idp_auth/saml_utils.py` : `prepare_django_request(request)` — convertir HttpRequest Django en dict pour python3-saml
- [x] Subtask 2.5: Créer helper `idp_auth/saml_utils.py` : `create_saml_auth(request, post_data=None)` — instancier OneLogin_Saml2_Auth
- [x] Subtask 2.6: Écrire tests unitaires pour `get_saml_settings()` et `prepare_django_request()`

### Task 3: Implémenter les endpoints SAML login et callback en DRF (AC: #1)

- [x] Subtask 3.1: Créer `idp_auth/views.py` — APIView pour GET /api/v1/auth/saml/login (initie flow SP-initiated, redirige vers IdP)
- [x] Subtask 3.2: Créer `idp_auth/views.py` — APIView pour POST /api/v1/auth/saml/callback (reçoit assertion SAML, valide, extrait attributs)
- [x] Subtask 3.3: Dans le callback, extraire attributs SAML : username, display_name, profile, ad_groups (groups/memberOf/ad_groups)
- [x] Subtask 3.4: Dans le callback, résoudre profils via ProfileService.find_by_ad_groups() (réutiliser logique M.5)
- [x] Subtask 3.5: Dans le callback, appeler AuthService.create_or_update_user() pour créer/mettre à jour l'utilisateur en DB
- [x] Subtask 3.6: Dans le callback, générer JWT tokens (access + refresh) — réutiliser logique FastAPI ou adapter pour Django
- [x] Subtask 3.7: Dans le callback, rediriger vers SPA avec access token en fragment URL (#access_token=...)
- [x] Subtask 3.8: Dans le callback, définir refresh token en httpOnly cookie (même politique que FastAPI)
- [x] Subtask 3.9: Gérer le mode dev bypass (AUTH_DEV_BYPASS) si configuré — skip IdP, émettre JWT dev directement
- [x] Subtask 3.10: Gérer les erreurs SAML : validation échouée → 403 SAML_VALIDATION_FAILED, pas authentifié → 403 SAML_NOT_AUTHENTICATED, aucun profil → 403 NO_PROFILE

### Task 4: Implémenter la génération et validation JWT en Django (AC: #1)

- [x] Subtask 4.1: Créer `idp_auth/jwt_utils.py` — `create_access_token(payload: dict, expires_delta: timedelta) -> str` (réutiliser python-jose ou PyJWT)
- [x] Subtask 4.2: Créer `idp_auth/jwt_utils.py` — `create_refresh_token(payload: dict) -> str` (durée 8h, configurable)
- [x] Subtask 4.3: Créer `idp_auth/jwt_utils.py` — `verify_token(token: str) -> dict | None` (valide signature et expiration)
- [x] Subtask 4.4: Ajouter settings JWT dans `idp_backend/settings.py` : JWT_SECRET_KEY, JWT_ALGORITHM (HS256/RS256), JWT_ACCESS_TOKEN_EXPIRE_MINUTES (30), JWT_REFRESH_TOKEN_EXPIRE_HOURS (8)
- [x] Subtask 4.5: Créer DRF authentication backend `idp_auth/authentication.py` — classe JWTAuthentication qui hérite de BaseAuthentication
- [x] Subtask 4.6: Dans JWTAuthentication.authenticate(), extraire token du header Authorization: Bearer <token>
- [x] Subtask 4.7: Dans JWTAuthentication.authenticate(), vérifier token via verify_token(), charger User depuis DB
- [x] Subtask 4.8: Configurer REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] avec JWTAuthentication
- [x] Subtask 4.9: Écrire tests unitaires pour create_access_token(), create_refresh_token(), verify_token()

### Task 5: Implémenter les endpoints auth current user et refresh (AC: #1)

- [x] Subtask 5.1: Créer `idp_auth/views.py` — APIView pour GET /api/v1/auth/me (retourne profil utilisateur courant + permissions)
- [x] Subtask 5.2: Dans GET /auth/me, utiliser AuthService.resolve_user_profiles() pour résoudre profils multi-profiles (Story 2.12)
- [x] Subtask 5.3: Dans GET /auth/me, calculer cumulative_permissions via RBACService (si disponible)
- [x] Subtask 5.4: Dans GET /auth/me, inclure navigation_tabs calculés (comme FastAPI)
- [x] Subtask 5.5: Dans GET /auth/me, inclure is_business_profile flag (Story 7.1)
- [x] Subtask 5.6: Créer `idp_auth/views.py` — APIView pour POST /api/v1/auth/refresh (refresh token → access token)
- [x] Subtask 5.7: Dans POST /auth/refresh, lire refresh token depuis httpOnly cookie
- [x] Subtask 5.8: Dans POST /auth/refresh, vérifier refresh token, générer nouveau access token
- [x] Subtask 5.9: Créer `idp_auth/views.py` — APIView pour POST /api/v1/auth/logout (clear refresh token cookie)
- [x] Subtask 5.10: Créer serializers `idp_auth/serializers.py` — UserProfileSerializer (lecture seule, format identique FastAPI)
- [x] Subtask 5.11: Créer serializers `idp_auth/serializers.py` — TokenRefreshResponseSerializer (access_token, token_type="bearer")

### Task 6: Configurer les URLs DRF pour auth (AC: #1)

- [x] Subtask 6.1: Créer `idp_auth/urls.py` avec routes : /auth/saml/login, /auth/saml/callback, /auth/me, /auth/refresh, /auth/logout
- [x] Subtask 6.2: Inclure idp_auth.urls dans `idp_backend/urls.py` avec préfixe /api/v1
- [x] Subtask 6.3: Vérifier que les URLs correspondent exactement aux routes FastAPI (parité contractuelle)
- [x] Subtask 6.4: Configurer CORS dans `idp_backend/settings.py` — CORS_ALLOWED_ORIGINS pour frontend uniquement

### Task 7: Implémenter le middleware de sécurité et audit (AC: #1)

- [x] Subtask 7.1: Créer `core/middleware.py` — CorrelationIdMiddleware (génère X-Idp-Request-Id, propage dans logs)
- [x] Subtask 7.2: Créer `core/middleware.py` — SecurityHeadersMiddleware (ajoute headers sécurité : X-Content-Type-Options, X-Frame-Options, etc.)
- [x] Subtask 7.3: Configurer middleware dans `idp_backend/settings.py` — MIDDLEWARE avec CorrelationIdMiddleware, SecurityHeadersMiddleware
- [x] Subtask 7.4: Créer `idp_auth/middleware.py` — AuditAuthMiddleware (loggue tentatives auth réussies/échouées dans AUDIT_LOG)
- [x] Subtask 7.5: Dans AuditAuthMiddleware, logger chaque login SAML avec user_id, ip_address, timestamp (NFR10)
- [x] Subtask 7.6: Dans AuditAuthMiddleware, logger chaque refresh token avec user_id, ip_address
- [x] Subtask 7.7: Utiliser AuditService.create_entry() avec types USER_LOGIN, USER_REFRESH, USER_LOGOUT

### Task 8: Documenter l'architecture SSO et runbook (AC: #1)

- [x] Subtask 8.1: Créer `docs/sso-architecture.md` — documenter le flow SAML complet Django
- [x] Subtask 8.2: Documenter l'interaction entre portail IDP et infra hébergeur (IdP SAML, certificats, métadonnées)
- [x] Subtask 8.3: Documenter la politique de sécurité : durée tokens, httpOnly cookies, TLS requis
- [x] Subtask 8.4: Créer `docs/sso-runbook.md` — procédures de dépannage SAML (erreurs courantes, logs à vérifier)
- [x] Subtask 8.5: Documenter la configuration requise côté hébergeur (métadonnées SP, ACS URL, certificats)

### Task 9: Tester les endpoints auth avec tests unitaires et d'intégration (AC: #2)

- [x] Subtask 9.1: Créer `idp_auth/tests/test_saml_views.py` — tests pour GET /auth/saml/login (redirection IdP)
- [x] Subtask 9.2: Créer `idp_auth/tests/test_saml_views.py` — tests pour POST /auth/saml/callback avec mock assertion SAML
- [x] Subtask 9.3: Tester callback avec assertion valide → création user, émission JWT, redirection SPA
- [x] Subtask 9.4: Tester callback avec assertion invalide → 403 SAML_VALIDATION_FAILED
- [x] Subtask 9.5: Tester callback avec utilisateur sans profil → 403 NO_PROFILE
- [x] Subtask 9.6: Créer `idp_auth/tests/test_auth_views.py` — tests pour GET /auth/me (authentifié → 200, non authentifié → 401)
- [x] Subtask 9.7: Créer `idp_auth/tests/test_auth_views.py` — tests pour POST /auth/refresh (cookie valide → 200, cookie absent → 401)
- [x] Subtask 9.8: Créer `idp_auth/tests/test_auth_views.py` — tests pour POST /auth/logout (clear cookie → 200)
- [x] Subtask 9.9: Créer `idp_auth/tests/test_jwt_utils.py` — tests pour create_access_token(), verify_token(), expiration
- [x] Subtask 9.10: Créer `idp_auth/tests/test_jwt_authentication.py` — tests pour JWTAuthentication backend (token valide → user, token expiré → None, token absent → None)

### Task 10: Valider la parité contractuelle avec FastAPI (AC: #1, #2)

- [x] Subtask 10.1: Comparer les réponses JSON DRF vs FastAPI pour chaque endpoint auth (format identique)
- [x] Subtask 10.2: Vérifier que les URLs sont identiques (avec trailing slash DRF si nécessaire)
- [x] Subtask 10.3: Vérifier que les codes HTTP sont identiques (200, 401, 403)
- [x] Subtask 10.4: Vérifier que le format des tokens JWT est identique (payload, algorithm, expiration)
- [x] Subtask 10.5: Vérifier que les cookies httpOnly sont identiques (nom, path, samesite, secure)
- [x] Subtask 10.6: Mettre à jour `docs/drf-api-migration-notes.md` avec les notes de cette story

## Dev Notes

### Context from Previous Stories

**Story M.1 - Bootstrap Django établi:**
- Projet Django créé avec structure d'apps: `catalog`, `profiles`, `idp_auth`, `integrations`, `core`, `executions`
- Configuration DRF en place (REST_FRAMEWORK dans settings.py)
- Format de réponse API préservé (enveloppe data/error, snake_case)

**Story M.2 - Modèles Django créés:**
- User model dans idp_auth/models.py (username, display_name, profile, saml_subject)
- Profile model dans profiles/models.py avec ad_group_mapping
- Enums: UserProfile (dba_applicatif, dba_infrastructure, dbops)

**Story M.3 - Couche données Django ORM complète:**
- **AuthService** complet: create_or_update_user(), get_by_username(), get_by_id(), find_by_saml_subject(), resolve_user_profiles()
- **ProfileService** complet: find_by_ad_groups() pour résolution multi-profils (Story 2.12)
- Audit via AuditService.create_entry() avec types USER_CREATED/UPDATED, USER_LOGIN, etc.

**Story M.4 & M.5 - Patterns établis:**
- CustomPageNumberPagination (format FastAPI compatible)
- DBOPSProfilePermission pour require_profile("dbops")
- Custom exception handler pour format erreurs FastAPI
- Enveloppe {"data": ...} pour toutes les réponses

**Story M.6 - Endpoints auth partiels:**
- GET /api/v1/auth/me implémenté avec placeholder (retourne profil utilisateur)
- POST /api/v1/auth/refresh et POST /api/v1/auth/logout en placeholders (full auth prévu en M.7)
- Health check déjà implémenté (GET /api/v1/health)

**Story 1.2 (FastAPI) - Référence d'implémentation:**
- Flow SAML complet implémenté dans FastAPI avec python3-saml
- Endpoints: GET /auth/saml/login, POST /auth/saml/callback
- Génération JWT avec python-jose (access 30min + refresh 8h)
- Stockage refresh token en httpOnly cookie, access token en mémoire SPA

### Architecture Compliance

**Contrainte critique de migration:** Parité contractuelle ABSOLUMENT CRITIQUE avec FastAPI. Le frontend React consomme la même API — aucun changement de contrat autorisé.

**Flow d'authentification (depuis Architecture section "Authentication & Security"):**

```
Navigateur → Portail React (SPA)
  → Pas de token? Redirige vers /api/v1/auth/saml/login
  → Backend Django redirige vers IdP SAML
  → IdP authentifie → POST assertion SAML vers /api/v1/auth/saml/callback
  → Backend valide assertion, extrait attributs (nom, profil, groupes)
  → Backend crée/met à jour l'utilisateur en DB
  → Backend émet JWT (access + refresh)
  → Redirige vers SPA avec tokens
  → SPA stocke access token en mémoire, refresh en httpOnly cookie
  → Toutes les requêtes API avec Authorization: Bearer <token>
```

**Décisions architecturales applicables:**

| Decision | Choix | Source |
|----------|-------|--------|
| SSO | SAML 2.0 (SP-initiated) | Architecture#Authentication & Security |
| Librairie SAML | python3-saml (OneLogin) | Architecture#Authentication & Security |
| Session post-SAML | JWT (access 30min + refresh 8h httpOnly) | Architecture#Authentication & Security |
| Token storage SPA | Access token en mémoire, refresh en httpOnly cookie | Architecture#Authentication & Security |
| JWT algorithm | HS256 (défaut) ou RS256 | Architecture#Authentication & Security |
| API security | CORS restreint + Bearer token + validation DRF | Architecture#Authentication & Security |
| TLS | 1.2+ terminé au reverse proxy Nginx | Architecture#Authentication & Security (NFR6) |
| Audit sécurité | Chaque action mutante logguée dans AUDIT_LOG | Architecture#Authentication & Security (NFR10) |

**Endpoints FastAPI à migrer:**

| Endpoint | Méthode | Description | Auth |
|----------|---------|-------------|------|
| /auth/saml/login | GET | Initie flow SP-initiated, redirige vers IdP | - |
| /auth/saml/callback | POST | Reçoit assertion SAML, valide, crée user, émet JWT | - |
| /auth/me | GET | Profil utilisateur courant + permissions | Bearer JWT |
| /auth/refresh | POST | Refresh token → access token | Cookie refresh_token |
| /auth/logout | POST | Clear refresh token cookie | - |

**Note importante:** L'endpoint GET /auth/me est déjà partiellement implémenté en M.6 avec placeholder. Cette story complète l'implémentation avec résolution profils multi-profiles et permissions cumulatives.

### Technical Requirements

**Réutilisation de python3-saml (comme FastAPI):**

La stratégie recommandée est de **réutiliser python3-saml** (même librairie que FastAPI) plutôt que django-saml2, pour:
1. Parité maximale avec l'implémentation FastAPI existante
2. Réutilisation de la configuration SAML (certificats, métadonnées)
3. Moins de risques de régression dans le flow SAML
4. python3-saml fonctionne bien avec Django (views DRF)

**Alternative django-saml2:** Si la plateforme hébergeuse impose django-saml2, adapter la stratégie en conséquence.

**Génération JWT:**

Options:
1. **python-jose** (comme FastAPI) — réutiliser la même librairie
2. **PyJWT** — alternative plus légère, compatible Django

Recommandation: **python-jose** pour parité maximale avec FastAPI.

**Utilisation des Services Django (M.3):**

```python
from idp_auth.services import AuthService
from profiles.services import ProfileService
from core.services import AuditService

class SAMLLoginView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        # Initier flow SAML SP-initiated
        auth = create_saml_auth(request)
        sso_url = auth.login()
        return redirect(sso_url)

class SAMLCallbackView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        # Valider assertion SAML
        auth = create_saml_auth(request, post_data=dict(request.POST))
        auth.process_response()
        
        if auth.get_errors():
            raise InvalidStateError(
                code="SAML_VALIDATION_FAILED",
                message=f"SAML validation failed: {auth.get_errors()}"
            )
        
        # Extraire attributs
        attributes = auth.get_attributes()
        ad_groups = extract_ad_groups(attributes)
        
        # Résoudre profils
        profile_service = ProfileService()
        profiles = profile_service.find_by_ad_groups(ad_groups)
        if not profiles:
            raise ForbiddenError(code="NO_PROFILE", message="Aucun profil associé")
        
        # Créer/mettre à jour user
        auth_service = AuthService()
        user = auth_service.create_or_update_user(
            username=extract_username(attributes),
            display_name=extract_display_name(attributes),
            profile=profiles[0].name,
            saml_subject=auth.get_nameid()
        )
        
        # Générer JWT
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "profile": user.profile,
            "ad_groups": ad_groups,
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        # Rediriger vers SPA avec tokens
        redirect_url = f"{settings.CORS_ORIGIN}/auth/callback#access_token={access_token}"
        response = redirect(redirect_url)
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.APP_ENV != "development",
            samesite="lax",
            max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_HOURS * 3600,
            path="/api/v1/auth",
        )
        return response
```

**DRF Authentication Backend:**

```python
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from idp_auth.jwt_utils import verify_token
from idp_auth.models import User

class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        payload = verify_token(token)
        if not payload:
            raise AuthenticationFailed('Invalid or expired token')
        
        try:
            user = User.objects.get(id=int(payload['sub']))
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found')
        
        return (user, None)
```

**Configuration settings.py:**

```python
# SAML Configuration
SAML_SP_ENTITY_ID = env('SAML_SP_ENTITY_ID')
SAML_SP_ACS_URL = env('SAML_SP_ACS_URL')
SAML_IDP_ENTITY_ID = env('SAML_IDP_ENTITY_ID')
SAML_IDP_SSO_URL = env('SAML_IDP_SSO_URL')
SAML_IDP_SLO_URL = env('SAML_IDP_SLO_URL', default='')
SAML_IDP_CERT_PATH = env('SAML_IDP_CERT_PATH')
SAML_SP_KEY_PATH = env('SAML_SP_KEY_PATH')
SAML_SP_CERT_PATH = env('SAML_SP_CERT_PATH')

# JWT Configuration
JWT_SECRET_KEY = env('JWT_SECRET_KEY')
JWT_ALGORITHM = env('JWT_ALGORITHM', default='HS256')
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = env.int('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', default=30)
JWT_REFRESH_TOKEN_EXPIRE_HOURS = env.int('JWT_REFRESH_TOKEN_EXPIRE_HOURS', default=8)

# Auth Dev Bypass (dev only)
AUTH_DEV_BYPASS = env.bool('AUTH_DEV_BYPASS', default=False)

# CORS
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
CORS_ALLOW_CREDENTIALS = True

# DRF Authentication
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'idp_auth.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    # ... autres configs DRF
}
```

### Library/Framework Requirements

**Dépendances à ajouter:**

- `python3-saml>=1.16` — librairie SAML (réutiliser version FastAPI)
- `python-jose[cryptography]>=3.3.0` — génération/validation JWT (réutiliser version FastAPI)
- `django-cors-headers>=4.3.0` — gestion CORS (déjà installé en M.1)

**Aucune nouvelle dépendance majeure requise** — réutilisation des mêmes librairies que FastAPI pour parité maximale.

### File Structure Requirements

**Structure Django cible:**

```
idp-portal/django_backend/
├── idp_auth/
│   ├── models.py              # User model (déjà créé en M.2)
│   ├── services.py            # AuthService (déjà créé en M.3)
│   ├── saml_config.py         # get_saml_settings() (NOUVEAU)
│   ├── saml_utils.py          # prepare_django_request(), create_saml_auth() (NOUVEAU)
│   ├── jwt_utils.py           # create_access_token(), verify_token() (NOUVEAU)
│   ├── authentication.py      # JWTAuthentication backend (NOUVEAU)
│   ├── serializers.py         # UserProfileSerializer, TokenRefreshResponseSerializer (MODIFIÉ depuis M.6)
│   ├── views.py               # SAMLLoginView, SAMLCallbackView, AuthMeView, RefreshView, LogoutView (MODIFIÉ depuis M.6)
│   ├── urls.py                # Routes auth (MODIFIÉ depuis M.6)
│   ├── middleware.py           # AuditAuthMiddleware (NOUVEAU)
│   └── tests/
│       ├── test_saml_views.py  # Tests SAML login/callback (NOUVEAU)
│       ├── test_auth_views.py   # Tests auth/me, refresh, logout (MODIFIÉ depuis M.6)
│       ├── test_jwt_utils.py   # Tests JWT utils (NOUVEAU)
│       └── test_jwt_authentication.py # Tests authentication backend (NOUVEAU)
├── core/
│   ├── middleware.py          # CorrelationIdMiddleware, SecurityHeadersMiddleware (MODIFIÉ)
│   └── exceptions.py          # Custom exceptions (déjà créé en M.4)
├── idp_backend/
│   ├── urls.py                # Inclure idp_auth.urls (MODIFIÉ)
│   └── settings.py            # Settings SAML, JWT, CORS (MODIFIÉ)
└── docs/
    ├── sso-architecture.md    # Architecture SSO (NOUVEAU)
    ├── sso-runbook.md         # Runbook dépannage SAML (NOUVEAU)
    └── drf-api-migration-notes.md # Notes migration (MODIFIÉ)
```

### Testing Requirements

**Tests à créer (parité avec tests FastAPI existants):**

1. **Tests SAML:**
   - test_saml_login_redirects_to_idp
   - test_saml_callback_valid_assertion_creates_user
   - test_saml_callback_valid_assertion_emits_jwt
   - test_saml_callback_invalid_assertion_returns_403
   - test_saml_callback_no_profile_returns_403
   - test_saml_callback_dev_bypass_skips_idp

2. **Tests auth endpoints:**
   - test_get_current_user_authenticated (→ 200)
   - test_get_current_user_unauthenticated (→ 401)
   - test_get_current_user_includes_navigation_tabs
   - test_get_current_user_includes_is_business_profile
   - test_refresh_token_success (→ 200)
   - test_refresh_token_missing (→ 401)
   - test_refresh_token_expired (→ 401)
   - test_logout_success (→ 200)

3. **Tests JWT utils:**
   - test_create_access_token
   - test_create_refresh_token
   - test_verify_token_valid
   - test_verify_token_expired
   - test_verify_token_invalid_signature

4. **Tests authentication backend:**
   - test_jwt_authentication_valid_token
   - test_jwt_authentication_expired_token
   - test_jwt_authentication_missing_header
   - test_jwt_authentication_invalid_format

**Commandes de test:**
```bash
pytest idp_auth/tests/
pytest --cov=idp_auth --cov-report=html
```

### Previous Story Intelligence

**Apprentissages de Story M.6:**
- Endpoints auth partiels déjà en place (GET /auth/me avec placeholder)
- Pattern d'enveloppe {"data": ...} établi
- DBOPSProfilePermission pour require_profile("dbops")
- Custom exception handler pour format erreurs FastAPI
- Tests avec APIClient DRF et mock pour permissions

**Apprentissages de Story 1.2 (FastAPI):**
- Flow SAML complet fonctionnel avec python3-saml
- Extraction attributs AD groups (groups/memberOf/ad_groups) avec fallback
- Résolution profils multi-profiles via ProfileService.find_by_ad_groups()
- Génération JWT avec python-jose (HS256 ou RS256)
- Stockage refresh token en httpOnly cookie (path=/api/v1/auth, samesite=lax)
- Mode dev bypass (AUTH_DEV_BYPASS) pour développement local

**Patterns établis:**
- Délégation logique métier aux Services (pas d'accès direct modèles)
- Transactions atomiques dans les Services
- Audit via AuditService.create_entry() avec types appropriés
- Tests avec APITestCase et fixtures
- Format de réponse API préservé (enveloppe data/error, snake_case)

**Fichiers FastAPI à analyser:**
- `idp-portal/backend/app/api/v1/auth.py` — Endpoints SAML login/callback, auth/me, refresh, logout
- `idp-portal/backend/app/core/saml.py` — Configuration python3-saml, helpers
- `idp-portal/backend/app/core/security.py` — Génération/validation JWT (python-jose)
- `idp-portal/backend/app/models/auth.py` — Modèles Pydantic (UserProfile, TokenPayload)

### Git Intelligence

**Derniers commits pertinents:**
- `m-6` — API REST auth et integrations - DRF migration (endpoints auth partiels)
- `m-5` — API REST profils et permissions - Code review fixes
- `m-4` — API REST catalogue et admin - Code review fixes
- `m-3` — Migration repositories FastAPI vers Django ORM - Couche données complète

**Pattern de commit à suivre:**
```
feat(m-7): Authentification SAML et sécurité - Migration Django
```

### Project Context Reference

**Contexte Epic M:**
- Migration FastAPI → Django REST pour arrimage plateforme hébergeuse
- Parité fonctionnelle et contractuelle avec API actuelle (OpenAPI / contrats frontend)
- Backend uniquement (API, couche données, auth, config, middleware, tests)
- Frontend React inchangé (cohabitation ou même API contract)

**Contraintes critiques:**
- Aucun changement de contrat API autorisé (frontend consomme la même API)
- Format de réponse préservé (enveloppe data/error, snake_case)
- URLs identiques (avec trailing slash DRF si nécessaire)
- Codes HTTP identiques

### References

- [Source: _bmad-output/planning-artifacts/epic-migration-fastapi-django.md#Story-M.7] - Story M.7 : Authentification SAML et sécurité
- [Source: _bmad-output/planning-artifacts/architecture.md#Authentication & Security] - Décisions architecturales SAML/JWT
- [Source: idp-portal/backend/app/api/v1/auth.py] - Endpoints FastAPI SAML/auth
- [Source: idp-portal/backend/app/core/saml.py] - Configuration python3-saml FastAPI
- [Source: idp-portal/backend/app/core/security.py] - Génération/validation JWT FastAPI
- [Source: _bmad-output/implementation-artifacts/1-2-authentification-saml-2-0-et-session-jwt.md] - Story FastAPI SAML complète
- [Source: _bmad-output/implementation-artifacts/m-6-api-rest-auth-health-integrations.md] - Story M.6 endpoints auth partiels
- [Source: idp-portal/django_backend/idp_auth/models.py] - Modèle Django User (M.2)
- [Source: idp-portal/django_backend/idp_auth/services.py] - AuthService Django (M.3)
- [Source: idp-portal/django_backend/profiles/services.py] - ProfileService Django (M.3)
- [Source: idp-portal/django_backend/core/services.py] - AuditService Django (M.3)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No debugging required.

### Completion Notes List

1. **Task 1 (Analysis):** Analyzed FastAPI auth.py, saml.py, security.py. Decision: Use python3-saml (same as FastAPI) for maximum parity.
2. **Task 2 (SAML Config):** Created saml_config.py with get_saml_settings(), saml_utils.py with prepare_django_request() and create_saml_auth(). Added SAML settings to settings.py. Tests created in test_saml_config.py.
3. **Task 3 (SAML Views):** Implemented SAMLLoginView (GET /auth/saml/login) and SAMLCallbackView (POST /auth/saml/callback) with full SAML flow, attribute extraction, profile resolution, user creation, and JWT emission. Includes dev bypass mode (AUTH_DEV_BYPASS).
4. **Task 4 (JWT):** Created jwt_utils.py with create_access_token(), create_refresh_token(), verify_token(), TokenPayload class. Created JWTAuthentication DRF backend. Configured DRF to use JWTAuthentication by default. Tests in test_jwt_utils.py and test_jwt_authentication.py.
5. **Task 5 (Auth Endpoints):** Updated CurrentUserProfileView, RefreshTokenView, LogoutView with full implementation. Refresh reads httpOnly cookie and validates refresh token type. Logout clears cookie with delete_cookie(). Audit logging added for login/refresh/logout.
6. **Task 6 (URLs):** Updated idp_auth/urls.py with SAML routes. URLs match FastAPI exactly (no trailing slash for auth endpoints).
7. **Task 7 (Middleware):** Created core/middleware.py with CorrelationIdMiddleware and SecurityHeadersMiddleware. Created idp_auth/middleware.py with AuditAuthMiddleware. Added USER_LOGIN, USER_REFRESH, USER_LOGOUT to AuditActionType enum.
8. **Task 8 (Documentation):** Created docs/sso-architecture.md with full SAML flow diagram and configuration reference. Created docs/sso-runbook.md with troubleshooting procedures.
9. **Task 9 (Tests):** Created test_saml_views.py, test_auth_views.py, test_jwt_utils.py, test_jwt_authentication.py with comprehensive test coverage for success and error scenarios.
10. **Task 10 (Parity):** Verified contract parity with FastAPI - same URLs, same response format ({"data": ...}), same JWT payload structure, same cookie policy (httponly, path=/api/v1/auth, samesite=lax).
11. **Code Review Fixes (2026-02-04):** Fixed 8 critical/medium issues identified in adversarial code review:
    - **CRITICAL #1:** Fixed `decode_token_unsafe()` to use `jwt.get_unverified_claims()` instead of exposing secret key
    - **CRITICAL #2:** Fixed audit logging in RefreshTokenView to validate user_id and raise error if invalid (no more fake entity_id=0)
    - **CRITICAL #3:** Fixed CORS_ALLOWED_ORIGINS array access to prevent IndexError when list is empty
    - **MEDIUM #4:** Simplified profile resolution logic in SAMLCallbackView - removed redundant fallback code after NO_PROFILE check
    - **MEDIUM #5:** Added warning logging in `_read_cert_file()` when certificate files not found
    - **MEDIUM #7:** Added documentation comment in test_saml_views.py about mock strategy and integration test recommendation
    - **MEDIUM #8:** Added error logging in CurrentUserProfileView when get_cumulative_permissions fails (no more silent exceptions)
    - **Note:** Issue #6 (dynamic ad_groups attribute) left as-is - architectural decision consistent with Story 2.12 multi-profile support

### Change Log

- 2026-02-04: Full SAML/JWT authentication implementation for Django REST Framework
- 2026-02-04: Code review fixes - Security and error handling improvements

### File List

**New Files:**
- idp-portal/django_backend/idp_auth/saml_config.py
- idp-portal/django_backend/idp_auth/saml_utils.py
- idp-portal/django_backend/idp_auth/jwt_utils.py
- idp-portal/django_backend/idp_auth/authentication.py
- idp-portal/django_backend/idp_auth/middleware.py
- idp-portal/django_backend/core/middleware.py
- idp-portal/django_backend/idp_auth/tests/test_saml_config.py
- idp-portal/django_backend/idp_auth/tests/test_saml_views.py
- idp-portal/django_backend/idp_auth/tests/test_jwt_utils.py
- idp-portal/django_backend/idp_auth/tests/test_jwt_authentication.py
- idp-portal/django_backend/docs/sso-architecture.md
- idp-portal/django_backend/docs/sso-runbook.md

**Modified Files:**
- idp-portal/django_backend/requirements.txt (added python3-saml, python-jose)
- idp-portal/django_backend/idp_backend/settings.py (SAML/JWT settings, middleware, DRF auth classes)
- idp-portal/django_backend/idp_auth/views.py (full SAML views implementation)
- idp-portal/django_backend/idp_auth/urls.py (added SAML routes)
- idp-portal/django_backend/core/models.py (added USER_LOGIN, USER_REFRESH, USER_LOGOUT audit types)
- idp-portal/django_backend/idp_auth/tests/test_auth_views.py (updated for real implementation)
- idp-portal/django_backend/docs/drf-api-migration-notes.md (added auth endpoint documentation)
