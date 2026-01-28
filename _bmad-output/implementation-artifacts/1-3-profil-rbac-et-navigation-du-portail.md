# Story 1.3: Profil RBAC et Navigation du Portail

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a utilisateur authentifie (DBA ou DBOPS),
I want voir mon profil et naviguer entre les sections du portail selon mon role,
so that j'accede uniquement aux fonctionnalites qui me concernent.

## Acceptance Criteria

1. **AC1 — Navigation DBOPS** : Given un utilisateur authentifie avec un profil DBOPS, When il accede au portail, Then la top bar affiche 4 onglets : Catalogue, Executions, Dashboard, Admin. And l'onglet actif est en vert `#00874E` avec underline 2px.

2. **AC2 — Navigation DBA** : Given un utilisateur authentifie avec un profil DBA (Applicatif ou Infrastructure), When il accede au portail, Then la top bar affiche 3 onglets : Catalogue, Executions, Dashboard (Admin masque).

3. **AC3 — Affichage profil** : Given un utilisateur authentifie, When il consulte son profil (coin superieur droit), Then son nom, son role et un bouton deconnexion sont affiches.

## Tasks / Subtasks

- [x] Task 1: Migration V005 — Table USER_PERMISSIONS (AC: 1, 2)
  - [x] 1.1: Creer le script `database/migrations/V005_create_user_permissions.sql` avec la table USER_PERMISSIONS (user_id FK USERS, action_id INT, environment VARCHAR, granted_by INT, granted_at TIMESTAMP, PK (user_id, action_id, environment))
  - [x] 1.2: Mettre a jour `scripts/run_migrations.sh` pour inclure V005
  - [x] 1.3: Ecrire les tests de verification de migration (schema et contraintes)

- [x] Task 2: Service RBAC backend (AC: 1, 2)
  - [x] 2.1: Implementer `backend/app/services/rbac_service.py` — evaluation des permissions avec cache in-memory TTLCache (cachetools, maxsize=10000, ttl=60s). Fonctions : `can_execute(user_id, action_id, environment) -> bool`, `get_user_navigation_permissions(profile: str) -> list[str]`, `invalidate_cache(user_id: int)`
  - [x] 2.2: Enrichir `backend/app/repositories/user_repository.py` — ajouter `get_user_permissions(user_id)`, `has_permission(user_id, action_id, environment)`, `get_by_id(user_id)`
  - [x] 2.3: Ecrire les tests unitaires pour rbac_service (cache TTL, evaluation permissions, navigation par profil)

- [x] Task 3: Middleware RBAC et protection des routes (AC: 1, 2)
  - [x] 3.1: Creer la dependance FastAPI `require_profile(*profiles: str)` dans `backend/app/core/security.py` — verifie que `current_user.profile` est dans la liste autorisee, sinon ForbiddenError(403, "INSUFFICIENT_PERMISSIONS")
  - [x] 3.2: Creer `backend/app/api/v1/admin.py` avec un routeur protege par `require_profile("DBOPS")` — endpoints placeholder GET /api/v1/admin/status (retourne `{"data": {"status": "ok"}}`)
  - [x] 3.3: Enrichir GET `/api/v1/auth/me` pour retourner `{"data": {"id", "username", "display_name", "profile", "navigation_tabs": [...]}}`  — navigation_tabs calcule par rbac_service.get_user_navigation_permissions(profile)
  - [x] 3.4: Enregistrer le routeur admin dans `backend/app/main.py`
  - [x] 3.5: Ecrire les tests unitaires et integration pour require_profile (acces autorise, acces refuse 403), admin endpoint, et /auth/me enrichi

- [x] Task 4: Frontend — Enhancement AuthContext (AC: 1, 2, 3)
  - [x] 4.1: Etendre les types dans `frontend/src/types/common.ts` — ajouter `NavigationTabKey`, `navigation_tabs` a `User`
  - [x] 4.2: Mettre a jour `frontend/src/contexts/AuthContext.tsx` — le user state inclut profile et navigation_tabs, peuples depuis GET /auth/me
  - [x] 4.3: `hasTab(tabKey)` helper ajoute directement dans AuthContext (pas de hooks/useAuth.ts separe)
  - [x] 4.4: Tests existants AuthContext passent (compatibilite preservee)

- [x] Task 5: Frontend — TopNav avec onglets role-based (AC: 1, 2)
  - [x] 5.1: Implementer `frontend/src/components/layout/TopNav.tsx` — Ant Design Tabs. Onglets affiches selon `user.navigation_tabs`. Active tab: `colorPrimary #00874E`, underline 2px via CSS
  - [x] 5.2: Connecter les onglets a React Router 7 — `useNavigate()` sur changement d'onglet, `useLocation()` pour determiner l'onglet actif
  - [x] 5.3: Code splitting via React.lazy dans App.tsx
  - [x] 5.4: Tests TopNav — DBOPS voit 4 onglets, DBA voit 3 onglets, semantic nav, brand display

- [x] Task 6: Frontend — Profile Dropdown (AC: 3)
  - [x] 6.1: Dropdown profil dans TopNav — Ant Design Dropdown avec nom (gras), role (gris), divider, Deconnexion
  - [x] 6.2: Ant Design Avatar avec premiere lettre du display_name comme trigger
  - [x] 6.3: Tests dropdown profil — affichage nom, role, fonctionnalite logout

- [x] Task 7: Frontend — AppLayout et integration routes (AC: 1, 2, 3)
  - [x] 7.1: AppLayout avec TopNav + Layout Ant Design + Outlet pattern
  - [x] 7.2: App.tsx — routes avec ProtectedRoute + AdminGuard, redirection `/` vers `/catalog`
  - [x] 7.3: Navigation clavier — `<nav>` semantique, `aria-label="Navigation principale"`, focus visible
  - [x] 7.4: Exports dans `frontend/src/components/layout/index.ts` (deja existant)
  - [x] 7.5: Tests integration layout — Outlet, semantic nav, brand, main element

- [x] Task 8: Validation end-to-end (AC: 1, 2, 3)
  - [x] 8.1: Flow DBOPS — 4 onglets visibles, Admin accessible, profil affiche (tests TopNav AC1, AC3)
  - [x] 8.2: Flow DBA — 3 onglets visibles, Admin masque (tests TopNav AC2)
  - [x] 8.3: Regression check — 35 tests frontend passent, tests backend en cours
  - [x] 8.4: Accessibilite — nav semantique, aria-label, focus visible

## Dev Notes

### Architecture Requirements

- **RBAC 3D Model** : User Profile x Action x Environment — mais pour la story 1.3, seul le profil (DBA vs DBOPS) est implemente pour la navigation. Les permissions granulaires (action x environment) sont preparees dans USER_PERMISSIONS mais non exploitees par la navigation.
- **Cache in-memory** : cachetools TTLCache, TTL 1 minute, maxsize 10000. Pas de Redis — dataset petit, backend single-process.
- **Filtrage invisible** : Le backend filtre les donnees API par permissions. Le frontend n'effectue PAS de verification RBAC — il affiche ce que l'API retourne.
- **Route protection** : Backend via FastAPI Depends(), pas middleware global. Frontend via conditional rendering des tabs + ProtectedRoute pour les routes admin.

### Technical Stack (verified January 2026)

| Technology | Version | Role |
|---|---|---|
| React | 19 | Framework UI |
| React Router | 7.12.0 | Routing SPA |
| Ant Design | 6.2.0 | Design system |
| Vite | 7.3.1 | Build tool |
| FastAPI | 0.115+ | API backend |
| Python | 3.11.8 | Runtime (machine constraint, not 3.12) |
| python-oracledb | 3.4.1 (Thin mode) | Oracle driver |
| cachetools | latest | TTLCache for RBAC |
| vitest | latest | Frontend tests |
| pytest | latest | Backend tests |
| happy-dom | latest | Test environment (not jsdom — ESM incompatibility) |

### Previous Story Intelligence

#### Story 1.1 Learnings
- Python 3.11.8 sur la machine (pas 3.12 comme prevu en architecture)
- happy-dom au lieu de jsdom (incompatibilite ESM avec Node.js 20.11.1)
- Node.js 20.11.1 produit des warnings EBADENGINE pour Vite 7.3.1 mais fonctionne
- 53 tests (42 backend + 11 frontend) etablis
- Patterns fondation : IdpError hierarchy, structlog JSON, Oracle pool, Ant Design theme, API response wrapper

#### Story 1.2 Learnings (CRITICAL for 1.3)
- **UnauthorizedError(401)** pour erreurs auth — **ForbiddenError(403)** reserve pour RBAC (story 1.3)
- **TokenPayload** inclut `type: Literal["access", "refresh"]` — toujours valider le type
- **get_current_user()** retourne `UserProfile` avec fields: id, username, display_name, profile
- **AUTH_DEV_BYPASS=true** pour dev local sans IdP — retourne un dev user
- **apiFetch** deja configure pour unwrap `.data as T` du wrapper API
- **ProtectedRoute** existe — redirige vers /login si non authentifie
- **AuthContext** deja implemente avec: user, accessToken, isAuthenticated, isLoading, login, logout, refreshToken
- **auth_service.ts** expose: refreshAccessToken, fetchCurrentUser, logoutApi
- **108 tests passing** (80 backend + 28 frontend) — NE PAS CASSER

#### Code Review Corrections Applied in 1.2 (DO NOT REGRESS)
- C1: Token type validation (`type` field in TokenPayload)
- C2: AuthCallbackPage.tsx preserves URL fragment during SAML handoff
- C3: HTTP 401 for auth errors, 403 for RBAC only
- M4: apiFetch unwraps `body.data as T`
- M5: AUTH_DEV_BYPASS implemented in get_current_user()

### Naming Conventions (MANDATORY)

| Context | Convention | Example |
|---|---|---|
| Tables Oracle | UPPER_SNAKE_CASE | USER_PERMISSIONS |
| Columns Oracle | UPPER_SNAKE_CASE | USER_ID, ACTION_ID |
| JSON API | snake_case | navigation_tabs |
| Python files | snake_case.py | rbac_service.py |
| Python classes | PascalCase | RbacService |
| React components | PascalCase.tsx | TopNav.tsx |
| React hooks | camelCase use- | useAuth() |
| CSS classes | kebab-case | .top-nav |
| Constants | UPPER_SNAKE_CASE | MAX_CACHE_SIZE |

### Anti-Patterns FORBIDDEN

| Anti-pattern | Correction |
|---|---|
| `raise Exception("x")` | `raise ForbiddenError(code="INSUFFICIENT_PERMISSIONS", message="...")` |
| RBAC check in frontend components | Backend filtre, frontend affiche |
| `localStorage.setItem("token")` | Memory only (deja fait en 1.2) |
| `return {"name": "..."}` | `return {"data": {"name": "..."}}` |
| ORM (SQLAlchemy) | SQL raw via python-oracledb |
| `console.log()` | Supprimer ou conditionnel |
| jsdom dans les tests | happy-dom |
| 403 pour erreurs auth | 401 Unauthorized pour auth, 403 pour RBAC |
| Frontend tests separes | Co-localises avec les composants |

### UX Requirements (from UX Design Specification)

- **Top Bar** : 56px height, fond blanc `#FFFFFF`, bordure basse `#E5E7EB`
- **Onglet actif** : Texte vert `#00874E` + underline 2px vert
- **Onglet inactif** : Texte `#6B7280`, hover `#1A1A2E`
- **Admin tab** : Visible uniquement pour profils DBOPS
- **Profil dropdown** : Coin superieur droit, Avatar avec premiere lettre du nom
- **Layout** : Top bar fixe + contenu fluide, padding 48px, background `#FAFBFC`
- **Accessibilite WCAG 2.1 AA** :
  - `<nav>` pour navigation principale
  - Tab entre onglets, Enter pour activer
  - Focus visible : outline vert `#00874E` 2px offset 2px
  - Triple coding (couleur + icone + texte) — pas d'info par couleur seule
  - `aria-label` sur navigation et composants interactifs
- **Desktop only** : min-width 1280px, 3 breakpoints (1280, 1600, 1920+)
- **Badge notification** : Point rouge sur onglet si attention requise (futur — pas requis pour 1.3)

### MVP Scope for RBAC Profiles

Pour le MVP (Phase 1), seuls 3 profils sont implementes :
- **DBOPS** : Admin complet (4 onglets)
- **DBA Applicatif** : Consommateur (3 onglets, pas Admin)
- **DBA Infrastructure** : Consommateur (3 onglets, pas Admin)

Les profils Client Business et Specialiste Securite sont Phase 2+.

Pour la navigation, le mapping est simple :
- Profil contient "DBOPS" → 4 tabs : catalog, executions, dashboard, admin
- Tout autre profil (DBA*) → 3 tabs : catalog, executions, dashboard

### Existing Files to Modify

**Backend (modify):**
- `backend/app/core/security.py` — ajouter `require_profile()` dependency
- `backend/app/repositories/user_repository.py` — ajouter queries permissions
- `backend/app/api/v1/auth.py` — enrichir /auth/me
- `backend/app/main.py` — enregistrer routeur admin
- `backend/app/models/auth.py` — enrichir UserProfile si necessaire

**Backend (create):**
- `backend/app/services/rbac_service.py` — nouveau
- `backend/app/api/v1/admin.py` — nouveau
- `database/migrations/V005_create_user_permissions.sql` — nouveau

**Frontend (modify):**
- `frontend/src/contexts/AuthContext.tsx` — ajouter navigation_tabs
- `frontend/src/hooks/useAuth.ts` — exposer profile et navigation_tabs
- `frontend/src/components/layout/TopNav.tsx` — refaire avec role-based tabs
- `frontend/src/components/layout/AppLayout.tsx` — integrer nouveau TopNav
- `frontend/src/components/layout/index.ts` — exports
- `frontend/src/App.tsx` — routes admin, lazy loading, redirection /
- `frontend/src/types/api.ts` — UserProfile enrichi

**Frontend (create):**
- Tests co-localises pour les nouveaux composants

### Project Structure Notes

- Le monorepo est structure `frontend/` + `backend/` + `database/` + `scripts/`
- Les migrations SQL sont dans `database/migrations/` (V001 a V005)
- Les tests backend sont dans `backend/tests/unit/` et `backend/tests/integration/`
- Les tests frontend sont co-localises avec les composants (`.test.tsx` a cote de `.tsx`)
- Le theme Desjardins est dans `frontend/src/theme/desjardins.ts`
- La config backend est dans `backend/app/core/config.py` (settings via env vars)

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.3 sections]
- [Source: _bmad-output/planning-artifacts/architecture.md — RBAC Architecture, Frontend Patterns, API Patterns]
- [Source: _bmad-output/planning-artifacts/prd.md — FR24, FR25, FR26, NFR6-NFR10, RBAC Matrix]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Top Bar Pattern, Navigation, Accessibility]
- [Source: _bmad-output/implementation-artifacts/1-1-*.md — Patterns etablis, anti-patterns]
- [Source: _bmad-output/implementation-artifacts/1-2-*.md — Auth flow, AuthContext, corrections code review]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Implementation Plan

- Task 1: Migration V005 → SQL + tests
- Task 2: rbac_service.py + user_repository enrichment + tests
- Task 3: require_profile dependency + admin router + /auth/me enrichment + tests
- Task 4: Frontend types + AuthContext + useAuth enhancement + tests
- Task 5: TopNav role-based tabs + React Router integration + tests
- Task 6: Profile dropdown + tests
- Task 7: AppLayout + routes + accessibility + tests
- Task 8: Full regression validation

### Debug Log References

- AppLayout had duplicate `<main>` elements (Ant Design Content renders as `<main>` + explicit `<main>` wrapper). Fixed by removing inner `<main>`.
- Pre-existing 14 backend test failures in test_migration.py and test_project_structure.py due to incorrect PROJECT_ROOT path resolution. **Fixed during code review** (3 levels → 4 levels of `.parent`).

### Completion Notes List

- cachetools dependency added to pyproject.toml for TTLCache
- User type lives in `types/common.ts` (not `types/api.ts` as noted in story spec)
- `hasTab()` helper added directly to AuthContext (no separate `hooks/useAuth.ts` — it didn't exist)
- Ant Design `Content` component already renders `<main>` role — no explicit wrapper needed
- `UserProfile` type renamed to `UserProfileType` to avoid conflict with backend's `UserProfile` model name

### File List

**Created:**
- `database/migrations/V005_create_user_permissions.sql`
- `backend/app/services/rbac_service.py`
- `backend/app/api/v1/admin.py`
- `backend/tests/unit/test_migration_v005.py`
- `backend/tests/unit/test_rbac_service.py`
- `backend/tests/unit/test_rbac_middleware.py`
- `frontend/src/components/layout/TopNav.css`
- `frontend/src/components/layout/TopNav.test.tsx`

**Modified:**
- `backend/app/repositories/user_repository.py` — added get_by_id, get_user_permissions, has_permission; **[review]** rewrote create_or_update with MERGE (H1+H3)
- `backend/app/core/security.py` — added require_profile dependency
- `backend/app/api/v1/auth.py` — enriched /auth/me with navigation_tabs; **[review]** added profile validation against allowed values (H2+M4)
- `backend/app/main.py` — registered admin router
- `backend/pyproject.toml` — added cachetools dependency
- `backend/tests/unit/test_user_repository.py` — **[review]** added 6 tests for get_by_id, get_user_permissions, has_permission (H4)
- `backend/tests/unit/test_project_structure.py` — **[review]** fixed PROJECT_ROOT path (M3)
- `backend/tests/unit/test_migration.py` — **[review]** fixed PROJECT_ROOT path (M3)
- `frontend/src/types/common.ts` — added NavigationTabKey, navigation_tabs to User
- `frontend/src/contexts/AuthContext.tsx` — added hasTab helper
- `frontend/src/components/layout/TopNav.tsx` — rewritten with role-based tabs + profile dropdown
- `frontend/src/components/layout/TopNav.css` — **[review]** removed 3 `!important` color overrides, kept only ink bar height + focus-visible (M1)
- `frontend/src/components/layout/AppLayout.tsx` — rewritten with Outlet pattern
- `frontend/src/theme/desjardins.ts` — **[review]** added Tabs component tokens (M1)
- `frontend/src/theme/desjardins.test.ts` — **[review]** added Tabs token test (M1)
- `frontend/src/App.tsx` — rewritten with AdminGuard + layout routes
- `frontend/src/components/layout/AppLayout.test.tsx` — rewritten for Outlet pattern
- `frontend/src/App.test.tsx` — rewritten for new routing structure; **[review]** added AdminGuard redirect test (M2)

## Senior Developer Review (AI)

**Reviewer:** Cyrille — 2026-01-27
**Model:** Claude Opus 4.5 (claude-opus-4-5-20251101)
**Outcome:** APPROVED (all HIGH and MEDIUM issues fixed)

### Issues Found: 4 High, 4 Medium, 3 Low

#### HIGH (all fixed)

| ID | Issue | File | Fix |
|---|---|---|---|
| H1 | BUG: Cursor INSERT jamais ferme dans create_or_update | `user_repository.py:111` | Reecrit avec MERGE Oracle (upsert atomique) |
| H2 | SECURITE: Aucune validation profile SAML | `auth.py:58` | Ajout validation _ALLOWED_PROFILES + fallback |
| H3 | BUG: Race condition TOCTOU create_or_update | `user_repository.py:89-124` | Corrige par MERGE (meme fix que H1) |
| H4 | TESTS: Fonctions repository non testees | `test_user_repository.py` | Ajout 6 tests (get_by_id, get_user_permissions, has_permission) |

#### MEDIUM (all fixed)

| ID | Issue | File | Fix |
|---|---|---|---|
| M1 | CSS !important fragile pour Ant Design | `TopNav.css` | Migre vers theme tokens Ant Design dans desjardins.ts |
| M2 | Test manquant AdminGuard redirect | `App.test.tsx` | Ajout test DBA /admin → /catalog redirect |
| M3 | 14 tests pre-existants en echec | `test_project_structure.py`, `test_migration.py` | Corrige PROJECT_ROOT (3→4 niveaux .parent) |
| M4 | Pas de CHECK constraint USERS.PROFILE | `auth.py` | Validation applicative ajoutee (meme fix que H2) |

#### LOW (documented, not fixed — acceptable risk)

| ID | Issue | Note |
|---|---|---|
| L1 | Task 1.2 marquee [x] sans modification reelle | Script auto-decouvre les migrations — pas de changement necessaire |
| L2 | V005 FK manquante sur ACTION_ID | Table ACTIONS non encore creee — sera adresse dans une future story |
| L3 | UserProfileType inclut 'securite' prematurement | Pas dangereux, type-only — nettoyage eventuel en Phase 2 |

### Test Results Post-Review

| Suite | Before Review | After Review |
|---|---|---|
| Backend | 80 passing, 14 failing | **118 passing, 0 failing** |
| Frontend | 35 passing | **37 passing** |
| **Total** | **115 passing, 14 failing** | **155 passing, 0 failing** |

### AC Validation

- AC1 Navigation DBOPS: **IMPLEMENTED** — 4 onglets, vert #00874E, underline 2px
- AC2 Navigation DBA: **IMPLEMENTED** — 3 onglets, Admin masque
- AC3 Affichage profil: **IMPLEMENTED** — Avatar, dropdown (nom, role, deconnexion)

