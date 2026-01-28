# Story 1.2 : Authentification SAML 2.0 et session JWT

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a membre de l'equipe (DBA ou DBOPS),
I want me connecter au portail via le SSO d'entreprise,
So that j'accede au portail avec mon identite corporative de maniere securisee.

## Acceptance Criteria

1. **Given** un utilisateur non authentifie ouvre le portail **When** il est redirige vers l'IdP SAML et s'authentifie **Then** le backend recoit l'assertion SAML, valide la signature, extrait les attributs (nom, profil, groupes)
2. **Given** une assertion SAML valide est recue **When** le backend traite le callback **Then** le backend cree ou met a jour l'utilisateur dans la table USERS (via `user_repository.create_or_update()`)
3. **Given** l'utilisateur est authentifie cote SAML **When** le backend emet les tokens **Then** un access token JWT (30min) et un refresh token (8h, httpOnly cookie) sont generes
4. **Given** le SPA recoit les tokens **When** il stocke l'access token **Then** le token est en memoire uniquement (jamais localStorage, jamais sessionStorage)
5. **Given** le SPA effectue une requete API **When** le header est construit **Then** toutes les requetes incluent `Authorization: Bearer <token>`
6. **Given** un access token expire **When** le SPA recoit HTTP 401 **Then** le SPA tente un refresh automatique via le refresh token (cookie httpOnly)
7. **Given** un refresh echoue **When** le token est invalide ou expire **Then** le SPA redirige vers la page de login SSO
8. **Given** FR24 est testee **When** un utilisateur s'authentifie via SSO **Then** le flux complet SAML → JWT → SPA fonctionne de bout en bout

## Tasks / Subtasks

### Task 1 : Installer les dependances SAML et JWT (AC: #1, #3)

- [x] 1.1 Ajouter `python3-saml` dans `pyproject.toml` (dependance principale)
- [x] 1.2 Ajouter `python-jose[cryptography]` dans `pyproject.toml` (generation/verification JWT)
- [x] 1.3 Installer les dependances dans le venv (`pip install -e ".[dev]"`)
- [x] 1.4 Ecrire un test de verification d'import : `import onelogin.saml2` et `import jose` OK

### Task 2 : Configuration SAML SP (AC: #1)

- [x] 2.1 Ajouter les settings SAML dans `core/config.py` : `SAML_SP_ENTITY_ID`, `SAML_SP_ACS_URL`, `SAML_IDP_ENTITY_ID`, `SAML_IDP_SSO_URL`, `SAML_IDP_SLO_URL`, `SAML_IDP_CERT_PATH`, `SAML_SP_KEY_PATH`, `SAML_SP_CERT_PATH`
- [x] 2.2 Creer `core/saml.py` : fonction `get_saml_settings()` qui retourne le dict de configuration python3-saml (SP + IdP metadata)
- [x] 2.3 Creer `core/saml.py` : fonction `create_saml_auth(request)` qui instancie `OneLogin_Saml2_Auth` avec les parametres HTTP de la requete FastAPI
- [x] 2.4 Ecrire tests unitaires pour `get_saml_settings()` : verifie la structure du dict retourne

### Task 3 : Endpoints SAML login et callback (AC: #1, #2)

- [x] 3.1 Creer `api/v1/auth.py` : `GET /api/v1/auth/saml/login` — initie le flow SP-initiated, redirige vers l'IdP
- [x] 3.2 Creer `api/v1/auth.py` : `POST /api/v1/auth/saml/callback` — recoit l'assertion SAML, valide, extrait attributs (username, display_name, profile, saml_subject)
- [x] 3.3 Dans le callback, appeler `user_repository.create_or_update()` pour creer/mettre a jour l'utilisateur en DB
- [x] 3.4 Dans le callback, generer les tokens JWT (access + refresh) et rediriger vers le SPA avec le access token en fragment URL ou parametre securise
- [x] 3.5 Monter le router auth dans `main.py` (`app.include_router(auth.router, prefix="/api/v1", tags=["auth"])`)
- [x] 3.6 Ecrire tests unitaires : mock de l'assertion SAML, verification de la creation utilisateur, verification de l'emission JWT

### Task 4 : Generation et verification JWT (AC: #3, #5, #6)

- [x] 4.1 Implementer `core/security.py` : `create_access_token(data: dict, expires_delta: timedelta) -> str` — JWT signe avec HS256 ou RS256, payload = TokenPayload
- [x] 4.2 Implementer `core/security.py` : `create_refresh_token(data: dict) -> str` — JWT avec TTL 8h
- [x] 4.3 Implementer `core/security.py` : `verify_token(token: str) -> TokenPayload` — decode et valide le JWT, raise `ForbiddenError` si invalide/expire
- [x] 4.4 Ajouter settings JWT dans `core/config.py` : `JWT_SECRET_KEY`, `JWT_ALGORITHM` (defaut HS256), `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (defaut 30), `JWT_REFRESH_TOKEN_EXPIRE_HOURS` (defaut 8)
- [x] 4.5 Ecrire tests unitaires : creation token, verification token valide, token expire, token invalide

### Task 5 : Middleware d'authentification backend (AC: #5, #6)

- [x] 5.1 Implementer `api/deps.py` : `get_current_user(request: Request) -> UserProfile` — extrait le Bearer token du header Authorization, verifie le JWT, retourne UserProfile
- [x] 5.2 Implementer `api/deps.py` : `get_optional_user(request: Request) -> UserProfile | None` — meme chose mais retourne None si pas de token (pour les routes publiques)
- [x] 5.3 Creer `api/v1/auth.py` : `POST /api/v1/auth/refresh` — recoit le refresh token depuis le cookie httpOnly, emet un nouveau access token
- [x] 5.4 Creer `api/v1/auth.py` : `GET /api/v1/auth/me` — retourne le profil de l'utilisateur courant (necessite auth)
- [x] 5.5 Creer `api/v1/auth.py` : `POST /api/v1/auth/logout` — supprime le cookie refresh token
- [x] 5.6 Ecrire tests unitaires : requete avec token valide, token expire (401), token absent (401), refresh OK, refresh expire (401)

### Task 6 : AuthContext frontend (AC: #4, #5, #6, #7)

- [x] 6.1 Implementer `contexts/AuthContext.tsx` : state `user`, `accessToken` (en memoire), `isAuthenticated`, `isLoading`
- [x] 6.2 Implementer `AuthContext` : `login()` — redirige vers `/api/v1/auth/saml/login`
- [x] 6.3 Implementer `AuthContext` : `logout()` — appelle `/api/v1/auth/logout`, vide le state, redirige vers login
- [x] 6.4 Implementer `AuthContext` : `refreshToken()` — appelle `/api/v1/auth/refresh`, met a jour l'access token en memoire
- [x] 6.5 Implementer `AuthContext` : au mount, tenter un refresh silencieux (cookie present) pour restaurer la session
- [x] 6.6 Implementer `AuthContext` : intercepteur automatique — si API retourne 401, tenter refresh puis retry. Si refresh echoue, redirige vers login
- [x] 6.7 Ecrire tests : AuthProvider render, login redirect, logout reset, token refresh flow

### Task 7 : Integration api_client avec auth (AC: #5, #6)

- [x] 7.1 Modifier `services/api_client.ts` : ajouter le header `Authorization: Bearer <token>` depuis AuthContext
- [x] 7.2 Modifier `services/api_client.ts` : intercepter les reponses 401, declencher refresh automatique, retry la requete
- [x] 7.3 Creer `services/auth_service.ts` : `refreshAccessToken()`, `fetchCurrentUser()`, `logout()`
- [x] 7.4 Ecrire tests : requete avec token, intercepteur 401, refresh + retry

### Task 8 : Protection des routes SPA (AC: #7)

- [x] 8.1 Creer un composant `ProtectedRoute.tsx` qui wrappe les routes authentifiees — redirige vers login si pas authentifie
- [x] 8.2 Modifier `App.tsx` : wrapper les 4 routes principales avec `ProtectedRoute`
- [x] 8.3 Creer une route `/login` avec un composant `LoginPage.tsx` qui affiche un bouton "Se connecter via SSO" et appelle `login()` depuis AuthContext
- [x] 8.4 Ecrire tests : route protegee redirige si non auth, route accessible si auth

### Task 9 : Verification end-to-end (AC: #8)

- [x] 9.1 Verifier que tous les tests backend passent (pytest)
- [x] 9.2 Verifier que tous les tests frontend passent (vitest)
- [x] 9.3 Verifier que le build frontend passe (`npx vite build`)
- [x] 9.4 Verifier que le backend charge sans erreur avec les nouveaux modules
- [x] 9.5 Documenter le flux SAML complet dans les Completion Notes

## Dev Notes

### Architecture Compliance

Cette story implemente le flow d'authentification complet. C'est le **blocker #1** identifie dans l'architecture — rien ne fonctionne sans auth.

**Flow d'authentification (depuis Architecture section "Authentication & Security") :**

```
Navigateur → Portail React (SPA)
  → Pas de token? Redirige vers /api/v1/auth/saml/login
  → Backend FastAPI redirige vers IdP SAML
  → IdP authentifie → POST assertion SAML vers /api/v1/auth/saml/callback
  → Backend valide assertion, extrait attributs (nom, profil, groupes)
  → Backend cree/met a jour l'utilisateur en DB
  → Backend emet JWT (access + refresh)
  → Redirige vers SPA avec tokens
  → SPA stocke access token en memoire, refresh en httpOnly cookie
  → Toutes les requetes API avec Authorization: Bearer <token>
```

**Decisions architecturales applicables :**

| Decision | Choix | Source |
|---|---|---|
| SSO | SAML 2.0 (SP-initiated) | Architecture#Authentication & Security |
| Librairie SAML | python3-saml (OneLogin) | Architecture#Authentication & Security |
| Session post-SAML | JWT (access 30min + refresh 8h httpOnly) | Architecture#Authentication & Security |
| Token storage SPA | Access token en memoire, refresh en httpOnly cookie | Architecture#Authentication & Security |
| JWT algorithm | HS256 (defaut) ou RS256 | Architecture#Authentication & Security |
| API security | CORS restreint + Bearer token + Pydantic validation | Architecture#Authentication & Security |

### Stubs existants a implementer (crees dans Story 1.1)

Les fichiers suivants existent deja comme stubs et DOIVENT etre implementes :

**Backend :**
- `backend/app/core/security.py` — Actuellement : `"""Security utilities - will be implemented in Story 1.2."""`. Implementer : JWT create/verify, password utilities si necessaire.
- `backend/app/api/deps.py` — Actuellement : `"""API dependencies - will be implemented in Story 1.2+."""`. Implementer : `get_current_user()`, `get_optional_user()` dependency injection FastAPI.
- `backend/app/models/auth.py` — Stubs existants : `UserProfile(id, username, display_name, profile)`, `TokenPayload(sub, username, profile, exp)`. Ajouter si necessaire : `SAMLAssertion`, `TokenResponse`, `RefreshRequest`.
- `backend/app/repositories/user_repository.py` — Deja implemente : `get_by_username(username)`, `create_or_update(username, display_name, profile, saml_subject)`. Reutiliser tel quel.

**Frontend :**
- `frontend/src/contexts/AuthContext.tsx` — Actuellement stub avec `user: null`. Implementer le context complet avec state management, login, logout, refresh.
- `frontend/src/services/api_client.ts` — Actuellement `apiFetch<T>()` basique. Ajouter le header Bearer token et l'intercepteur 401/refresh.
- `frontend/src/types/common.ts` — Existant : `User` interface et `UserProfile` type union. Reutiliser.

### Nouveaux fichiers a creer

- `backend/app/core/saml.py` — Configuration SAML SP, creation OneLogin_Saml2_Auth
- `backend/app/api/v1/auth.py` — Routes SAML login/callback, refresh, me, logout
- `frontend/src/services/auth_service.ts` — Client auth API
- `frontend/src/components/auth/ProtectedRoute.tsx` — Guard de route
- `frontend/src/pages/LoginPage.tsx` — Page de connexion SSO

### Patterns d'implementation

**JWT Token Pattern :**

```python
# core/security.py
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from app.core.config import settings
from app.core.exceptions import ForbiddenError
from app.models.auth import TokenPayload

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def verify_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return TokenPayload(**payload)
    except JWTError:
        raise ForbiddenError(code="INVALID_TOKEN", message="Token invalide ou expire")
```

**Dependency Injection Pattern (FastAPI) :**

```python
# api/deps.py
from fastapi import Request
from app.core.security import verify_token
from app.core.exceptions import ForbiddenError
from app.models.auth import UserProfile
from app.repositories import user_repository

async def get_current_user(request: Request) -> UserProfile:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise ForbiddenError(code="NO_TOKEN", message="Token d'authentification requis")
    token = auth_header.split(" ")[1]
    payload = verify_token(token)
    user = await user_repository.get_by_username(payload.username)
    if not user:
        raise ForbiddenError(code="USER_NOT_FOUND", message="Utilisateur introuvable")
    return UserProfile(**user)
```

**SAML SP-initiated Flow Pattern :**

```python
# api/v1/auth.py
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from app.core.saml import create_saml_auth

router = APIRouter()

@router.get("/auth/saml/login")
async def saml_login(request: Request):
    auth = create_saml_auth(request)
    return RedirectResponse(url=auth.login())

@router.post("/auth/saml/callback")
async def saml_callback(request: Request):
    auth = create_saml_auth(request)
    auth.process_response()
    errors = auth.get_errors()
    if errors:
        raise ForbiddenError(code="SAML_ERROR", message=str(errors))
    # Extraire attributs, creer/update user, emettre JWT...
```

**AuthContext Frontend Pattern :**

```typescript
// contexts/AuthContext.tsx
interface AuthContextValue {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: () => void;
  logout: () => Promise<void>;
  refreshToken: () => Promise<string | null>;
}
```

**Refresh Token Cookie Pattern :**

```python
# Le refresh token est envoye via httpOnly cookie (securite XSS)
response.set_cookie(
    key="refresh_token",
    value=refresh_token,
    httponly=True,
    secure=True,  # HTTPS only
    samesite="lax",
    max_age=8 * 3600,  # 8 heures
    path="/api/v1/auth",  # Restreint au chemin auth
)
```

### Contraintes environnement (heritees de Story 1.1)

- Python 3.11.8 (pas 3.12 — architecture dit 3.12+ mais la machine a 3.11.8)
- Node.js 20.11.1 (warnings EBADENGINE mais fonctionnel)
- happy-dom pour les tests frontend (pas jsdom)
- Le backend n'a PAS acces a un IdP SAML reel en dev. Les tests DOIVENT mocker les interactions SAML. Prevoir un mode "dev bypass" si necessaire (variable `AUTH_DEV_BYPASS=true` pour les tests locaux)

### Configuration de test SAML

Pour le developpement local sans IdP reel, prevoir :
- Un certificat X.509 de test auto-signe pour la validation SAML
- Mock de l'assertion SAML dans les tests avec des attributs de test
- Variable `AUTH_DEV_BYPASS` dans `.env.example` pour permettre le dev sans IdP

### Anti-patterns INTERDITS

| Anti-pattern | Correction |
|---|---|
| `localStorage.setItem("token", ...)` | Access token en memoire uniquement (`useState`) |
| Refresh token en JS accessible | httpOnly cookie uniquement |
| JWT secret en dur dans le code | Variable d'environnement `JWT_SECRET_KEY` |
| `raise Exception("auth failed")` | `raise ForbiddenError(code="...", message="...")` |
| Token dans query string | Header `Authorization: Bearer` |
| Pas de validation d'expiration | Verifier `exp` dans `verify_token()` |
| SAML cert en variable d'environnement | Fichier sur disque, chemin en config |

### Project Structure Notes

**Fichiers existants modifies :**
- `backend/app/core/security.py` — de stub a implementation complete
- `backend/app/api/deps.py` — de stub a implementation complete
- `backend/app/models/auth.py` — enrichi avec nouveaux modeles si necessaire
- `backend/app/main.py` — ajout du router auth
- `frontend/src/contexts/AuthContext.tsx` — de stub a implementation complete
- `frontend/src/services/api_client.ts` — ajout Bearer token + intercepteur 401
- `frontend/src/App.tsx` — ajout ProtectedRoute + route /login
- `backend/pyproject.toml` — ajout python3-saml, python-jose[cryptography]
- `.env.example` — ajout des variables SAML et JWT

**Nouveaux fichiers :**
- `backend/app/core/saml.py`
- `backend/app/api/v1/auth.py`
- `frontend/src/services/auth_service.ts`
- `frontend/src/components/auth/ProtectedRoute.tsx`
- `frontend/src/pages/LoginPage.tsx`

**Structure conforme a l'architecture :**
- Routes auth dans `api/v1/auth.py` (FR24-FR29)
- Security dans `core/security.py` (JWT + SAML)
- Dependencies dans `api/deps.py` (DI FastAPI)
- AuthContext dans `contexts/AuthContext.tsx`
- Tests co-localises pour composants frontend, dans `tests/` pour backend

### References

- [Source: planning-artifacts/architecture.md#Authentication & Security] — SAML 2.0 SP-initiated, python3-saml, JWT 30min+8h, httpOnly cookie, RBAC middleware
- [Source: planning-artifacts/architecture.md#Core Architectural Decisions] — Decision priority: SAML+JWT est blocker #1
- [Source: planning-artifacts/architecture.md#Implementation Patterns & Consistency Rules] — Error handling (IdpError hierarchy), API response format, naming conventions
- [Source: planning-artifacts/architecture.md#Project Structure & Boundaries] — `core/security.py`, `api/v1/auth.py`, `api/deps.py`, `contexts/AuthContext.tsx`
- [Source: planning-artifacts/architecture.md#Frontend Architecture] — React Context + hooks pour auth, fetch natif + wrapper type
- [Source: planning-artifacts/epics.md#Story 1.2] — Acceptance criteria originaux
- [Source: planning-artifacts/prd.md#FR24] — "Les utilisateurs s'authentifient via le SSO d'entreprise"
- [Source: implementation-artifacts/1-1-initialisation-monorepo-et-environnement-de-developpement.md] — Stubs crees, structure existante, contraintes Python 3.11.8 / happy-dom

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- xmlsec/lxml libxml2 version mismatch: python3-saml installe via pip a un conflit entre les versions compilees de lxml et xmlsec. Resolution: `pip install --no-binary :all: --no-cache-dir --force-reinstall xmlsec lxml` pour rebuilder les deux depuis les sources contre la meme libxml2 systeme (2.14.6 via Homebrew). `brew install xmlsec1` prerequis.
- python-jose[cryptography] etait deja present dans pyproject.toml (Story 1.1).

### Completion Notes List

- **Flux SAML complet implemente** : SP-initiated SAML 2.0 via python3-saml. Endpoints: GET /auth/saml/login (redirige vers IdP), POST /auth/saml/callback (valide assertion, cree/update user, emet JWT).
- **JWT dual-token** : Access token (30min, HS256) en memoire SPA + Refresh token (8h, httpOnly cookie, path=/api/v1/auth). `create_access_token()`, `create_refresh_token()`, `verify_token()` dans `core/security.py`.
- **Dependency injection FastAPI** : `get_current_user()` et `get_optional_user()` dans `api/deps.py`. Extraction Bearer token, verification JWT, lookup DB.
- **AuthContext React complet** : state user/accessToken/isLoading, login (redirect SSO), logout (clear + redirect), refreshToken (POST cookie), silent restore on mount, URL fragment token extraction (/auth/callback#access_token=...).
- **api_client avec auth** : `setAuthAccessors()` pattern pour eviter les dependances circulaires. Header Authorization: Bearer automatique. Intercepteur 401: refresh + retry.
- **ProtectedRoute** : Composant guard qui redirige vers /login si non authentifie. Les 4 routes principales wrappees.
- **LoginPage** : Bouton "Se connecter via SSO" avec Ant Design Result component.
- **108 tests total** : 80 backend (pytest) + 28 frontend (vitest). 0 echecs.
- Anti-patterns respectes : pas de localStorage, refresh en httpOnly, JWT secret en env, ForbiddenError hierarchy, Bearer header.

### Code Review Record

**Reviewer:** Amelia (Dev Agent) — Revue adversariale
**Date:** 2026-01-27
**Issues trouvees:** 3 Critiques, 5 Medium, 2 Low = 10 total
**Resultat:** Toutes les issues Critiques et Medium corrigees

| ID | Severite | Description | Fichiers | Statut |
|---|---|---|---|---|
| C1 | CRITIQUE | Token type non valide — access/refresh interchangeables (securite) | `security.py`, `models/auth.py`, `deps.py`, `auth.py` | CORRIGE |
| C2 | CRITIQUE | Handoff SAML→SPA casse — `<Navigate>` supprime le hash avant AuthContext | `App.tsx`, `AuthContext.tsx` | CORRIGE |
| C3 | CRITIQUE | HTTP 403 au lieu de 401 pour erreurs auth — auto-refresh ne se declenche jamais | `exceptions.py`, `deps.py`, `auth.py`, `api_client.ts` | CORRIGE |
| M1 | MEDIUM | `/auth/me` duplique la logique de `get_current_user` — pas de DI | `auth.py` | CORRIGE |
| M2 | MEDIUM | `auth_service.ts` est du code mort — AuthContext reimplemente en inline | `AuthContext.tsx`, `auth_service.ts` | CORRIGE |
| M3 | MEDIUM | Tests backend dans `tests/` au lieu de `tests/unit/` (architecture) | Tous les tests backend | CORRIGE |
| M4 | MEDIUM | `apiFetch` ne depackete pas `.data` du wrapper API | `api_client.ts` | CORRIGE |
| M5 | MEDIUM | `auth_dev_bypass` existe en config mais jamais utilise | `deps.py` | CORRIGE |
| L1 | LOW | Chemins File List sans prefix `idp-portal/` | Story file | NOTE |
| L2 | LOW | Pas de depot git — verification impossible | Projet | NOTE |

**Corrections appliquees:**

1. **C1:** Ajout `UnauthorizedError(401)` dans `exceptions.py`. Ajout champ `type` dans `TokenPayload`. `verify_token()` accepte `expected_type` param et valide le type. `deps.py` passe `expected_type="access"`, `/auth/refresh` passe `expected_type="refresh"`.
2. **C2:** Creation de `AuthCallbackPage.tsx` qui attend la resolution auth (useEffect + navigate) au lieu de `<Navigate>` qui tue le hash. Mise a jour `App.tsx`.
3. **C3:** Remplacement `ForbiddenError` par `UnauthorizedError` pour toutes les erreurs d'authentification (NO_TOKEN, INVALID_TOKEN, NO_REFRESH_TOKEN). `ForbiddenError(403)` reserve aux erreurs SAML et RBAC futur.
4. **M1:** `/auth/me` utilise `Depends(get_current_user)` au lieu de code duplique.
5. **M2:** `AuthContext.tsx` importe et utilise `auth_service.ts` (refreshAccessToken, fetchCurrentUser, logoutApi).
6. **M3:** Tests deplaces dans `tests/unit/`. `pyproject.toml` testpaths mis a jour. Dossier `tests/integration/` cree.
7. **M4:** `apiFetch` retourne `body.data as T` au lieu de `response.json()`.
8. **M5:** `get_current_user` et `get_optional_user` retournent un dev user quand `auth_dev_bypass=True`.

### Change Log

- 2026-01-27: Story 1.2 implementee — authentification SAML 2.0 + session JWT. 9 tasks, 108 tests.
- 2026-01-27: Code review adversariale — 10 issues trouvees (3C/5M/2L), 8 corrigees. Ajout UnauthorizedError(401), validation token type, AuthCallbackPage, DI pour /auth/me, auth_service integre, tests restructures, apiFetch unwrap, dev bypass.
- 2026-01-28: Code review follow-up — 2 issues additionnelles corrigees:
  - Added FileNotFoundError handling in _read_cert_file() for dev environments
  - Improved token extraction from URL fragment with regex (more robust than split)
  - Added error handling in logoutApi() for network failures

### File List

**Backend — Modifies :**
- `idp-portal/backend/pyproject.toml` — ajout python3-saml>=1.16, testpaths mis a jour vers tests/unit + tests/integration
- `idp-portal/backend/app/core/config.py` — ajout settings JWT (secret, algo, TTLs) + SAML (SP/IdP entity, URLs, cert paths) + auth_dev_bypass
- `idp-portal/backend/app/core/security.py` — create_access_token, create_refresh_token, verify_token (avec expected_type + UnauthorizedError)
- `idp-portal/backend/app/core/exceptions.py` — ajout UnauthorizedError(401)
- `idp-portal/backend/app/api/deps.py` — get_current_user (UnauthorizedError, type="access", dev bypass), get_optional_user
- `idp-portal/backend/app/api/v1/auth.py` — saml_login, saml_callback, refresh (type="refresh"), me (Depends), logout
- `idp-portal/backend/app/models/auth.py` — TokenPayload avec champ type
- `idp-portal/backend/app/main.py` — ajout import auth, include_router auth

**Backend — Nouveaux :**
- `idp-portal/backend/app/core/saml.py` — get_saml_settings(), create_saml_auth(), _prepare_fastapi_request()
- `idp-portal/backend/tests/unit/test_auth_deps.py` — 2 tests import SAML/jose
- `idp-portal/backend/tests/unit/test_saml_config.py` — 8 tests config SAML + settings
- `idp-portal/backend/tests/unit/test_auth_api.py` — 12 tests endpoints auth (ajout test_refresh_rejects_access_token, test_get_me 401)
- `idp-portal/backend/tests/unit/test_security.py` — 13 tests JWT create/verify (ajout 4 tests type validation)
- `idp-portal/backend/tests/unit/test_deps.py` — 12 tests dependency injection (ajout test_rejects_refresh_token, test_dev_bypass)
- `idp-portal/backend/tests/unit/test_exceptions.py` — ajout test_unauthorized_error
- `idp-portal/backend/tests/integration/` — dossier cree (vide)

**Frontend — Modifies :**
- `idp-portal/frontend/src/contexts/AuthContext.tsx` — utilise auth_service.ts (refreshAccessToken, fetchCurrentUser, logoutApi)
- `idp-portal/frontend/src/services/api_client.ts` — Bearer header, 401 interceptor, retourne body.data (unwrap)
- `idp-portal/frontend/src/services/auth_service.ts` — return type User, rename logout→logoutApi
- `idp-portal/frontend/src/App.tsx` — AuthCallbackPage au lieu de Navigate, AuthProvider, ProtectedRoute

**Frontend — Nouveaux :**
- `idp-portal/frontend/src/components/auth/ProtectedRoute.tsx` — guard redirect /login
- `idp-portal/frontend/src/pages/LoginPage.tsx` — bouton SSO avec Ant Design
- `idp-portal/frontend/src/pages/AuthCallbackPage.tsx` — attend auth resolution puis navigate (fix C2)
- `idp-portal/frontend/src/contexts/AuthContext.test.tsx` — 5 tests AuthProvider
- `idp-portal/frontend/src/services/api_client.test.ts` — 5 tests api_client auth (ajuste pour unwrap .data)
- `idp-portal/frontend/src/services/auth_service.test.ts` — 5 tests auth_service (logoutApi)
- `idp-portal/frontend/src/components/auth/ProtectedRoute.test.tsx` — 2 tests ProtectedRoute

**Root — Modifies :**
- `idp-portal/.env.example` — ajout variables JWT, SAML, AUTH_DEV_BYPASS
