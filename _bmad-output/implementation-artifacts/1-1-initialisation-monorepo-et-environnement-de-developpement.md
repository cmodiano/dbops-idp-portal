# Story 1.1 : Initialisation du monorepo et environnement de developpement

Status: review

## Story

As a developpeur de l'equipe IDP,
I want le monorepo initialise avec le frontend React+Vite+Ant Design et le backend FastAPI+python-oracledb,
So that je peux commencer a developper les features du portail sur une base solide.

## Acceptance Criteria

1. **Given** un developpeur clone le repo **When** il execute `npm run dev` dans frontend/ et `fastapi dev` dans backend/ **Then** le frontend demarre sur le port 5173 avec le theme Desjardins (#00874E) et le backend repond sur le port 8000
2. **Given** le frontend est demarre **When** le proxy Vite est configure **Then** `/api` et `/ws` sont rediriges vers le backend (port 8000)
3. **Given** le frontend est demarre **When** le fichier `desjardins.ts` est charge **Then** les tokens Ant Design 6 sont configures (primary color #00874E, bordures, spacings)
4. **Given** le frontend est demarre **When** le layout principal est rendu **Then** la top bar fixe (56px), la zone contenu fluide et le fond #FAFBFC sont en place
5. **Given** le projet est clone **When** on inspecte l'arborescence **Then** la structure respecte l'architecture definie (frontend/src/**, backend/app/**)
6. **Given** le backend demarre **When** la connexion Oracle est initialisee **Then** la table USERS (V001) est creee via le script de migration SQL
7. **Given** le backend demarre **When** le pool de connexions est initialise **Then** `oracledb.create_pool()` est configure dans `core/database.py`
8. **Given** le backend demarre **When** une erreur se produit **Then** les exceptions custom (IdpError hierarchy) sont definies dans `core/exceptions.py`

## Tasks / Subtasks

### Task 1 : Initialiser le monorepo (AC: #5)

- [x] 1.1 Creer le dossier racine `idp-portal/` avec `.gitignore`, `.env.example`, `README.md`
- [x] 1.2 Initialiser le frontend via `npm create vite@latest` avec template `react-ts`
- [x] 1.3 Installer les dependances frontend : `antd@^6.2.0`, `@ant-design/icons`, `react-router@^7.12.0`
- [x] 1.4 Initialiser le backend : creer `backend/app/` avec `__init__.py`, `main.py`
- [x] 1.5 Creer `backend/pyproject.toml` avec dependances : `fastapi[standard]`, `oracledb`, `pydantic`, `uvicorn`, `python-jose`, `passlib`, `structlog`
- [x] 1.6 Creer la structure complete des dossiers (voir section File Structure ci-dessous)

### Task 2 : Configurer le theme Desjardins et le layout (AC: #1, #3, #4)

- [x] 2.1 Creer `frontend/src/theme/desjardins.ts` avec les tokens Ant Design 6 (ConfigProvider)
- [x] 2.2 Configurer `App.tsx` avec `<ConfigProvider theme={desjardinsTheme}>` comme wrapper racine
- [x] 2.3 Creer `frontend/src/components/layout/AppLayout.tsx` : top bar fixe 56px + zone contenu fluide + fond #FAFBFC
- [x] 2.4 Creer `frontend/src/components/layout/TopNav.tsx` : placeholder navigation avec onglets (Catalogue, Executions, Dashboard, Admin)
- [x] 2.5 Configurer `main.tsx` comme point d'entree React avec le theme et layout

### Task 3 : Configurer le routing et le proxy Vite (AC: #2)

- [x] 3.1 Configurer `vite.config.ts` avec proxy `/api` → `http://localhost:8000` et `/ws` → `ws://localhost:8000`
- [x] 3.2 Configurer React Router 7 dans `App.tsx` avec 4 routes : `/catalog`, `/executions`, `/dashboard`, `/admin`
- [x] 3.3 Creer les pages placeholder : `CatalogPage.tsx`, `ExecutionsPage.tsx`, `DashboardPage.tsx`, `AdminPage.tsx`, `NotFoundPage.tsx`
- [x] 3.4 Configurer le lazy loading (`React.lazy`) pour chaque page

### Task 4 : Backend FastAPI skeleton (AC: #1, #7, #8)

- [x] 4.1 Creer `backend/app/main.py` : FastAPI app avec titre "IDP Portal API", version "0.1.0"
- [x] 4.2 Creer `backend/app/core/config.py` : Settings via pydantic-settings (env vars : ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD, ORACLE_MIN_POOL, ORACLE_MAX_POOL)
- [x] 4.3 Creer `backend/app/core/database.py` : `oracledb.create_pool()` async, fonctions `get_pool()` et `get_connection()` context manager
- [x] 4.4 Creer `backend/app/core/exceptions.py` : hierarchy IdpError → NotFoundError, ForbiddenError, PlatformError, VaultError, ServiceNowError (avec status_code, code, message, details)
- [x] 4.5 Configurer le handler global d'exceptions dans `main.py` : `@app.exception_handler(IdpError)` → `{ "error": { "code", "message", "details" } }`
- [x] 4.6 Creer `backend/app/core/middleware.py` : middleware Correlation ID (X-Idp-Request-Id UUID) + middleware CORS (origin portail uniquement)
- [x] 4.7 Creer `backend/app/api/v1/health.py` : `GET /api/v1/health` retourne statut connectivite Oracle (200 OK / 503)
- [x] 4.8 Monter le router API v1 dans `main.py`

### Task 5 : Migration SQL V001 (AC: #6)

- [x] 5.1 Creer `database/migrations/V001_create_users.sql` : table USERS (ID NUMBER, USERNAME VARCHAR2, DISPLAY_NAME VARCHAR2, PROFILE VARCHAR2, SAML_SUBJECT VARCHAR2, CREATED_AT TIMESTAMP, UPDATED_AT TIMESTAMP) + sequence SEQ_USERS + index unique UK_USERS_USERNAME
- [x] 5.2 Creer `scripts/run_migrations.sh` : script qui execute les migrations SQL sequentiellement via sqlplus ou python-oracledb

### Task 6 : Structured logging (AC: #8, fondation observabilite)

- [x] 6.1 Creer `backend/app/core/logging.py` : configuration structlog JSON (timestamp, level, event, correlation_id, user_id)
- [x] 6.2 Integrer le logger dans `main.py` et le middleware

### Task 7 : Pydantic models fondation

- [x] 7.1 Creer `backend/app/models/common.py` : ErrorResponse, PaginatedResponse, HealthStatus (Pydantic v2)
- [x] 7.2 Creer `backend/app/models/auth.py` : UserProfile, TokenPayload (stubs pour Story 1.2)

### Task 8 : User repository fondation

- [x] 8.1 Creer `backend/app/repositories/user_repository.py` : stub avec methodes `get_by_username()`, `create_or_update()` (SQL brut via oracledb)

### Task 9 : Verification end-to-end

- [x] 9.1 Verifier que `cd frontend && npm run dev` demarre sans erreur sur port 5173
- [x] 9.2 Verifier que `cd backend && fastapi dev app/main.py` demarre sur port 8000
- [x] 9.3 Verifier que le proxy Vite redirige `/api/v1/health` vers le backend
- [x] 9.4 Verifier que le theme Desjardins est applique (couleur primaire #00874E visible)
- [x] 9.5 Verifier que la structure de fichiers est conforme a l'architecture

## Dev Notes

### Architecture Compliance

Cette story initialise le monorepo. TOUTES les decisions architecturales fondamentales doivent etre en place :

**Stack exacte (versions verifiees janvier 2026) :**
- Frontend : Vite 7.3.1, React 19, React Router 7.12.0, Ant Design 6.2.0, TypeScript 5.x
- Backend : FastAPI 0.115+, Python 3.12+, python-oracledb 3.4.1 (mode Thin), Pydantic v2.12+, structlog

**Commandes d'initialisation (depuis Architecture section "Starter Template") :**

```bash
# Frontend
npm create vite@latest idp-portal -- --template react-ts
cd idp-portal
npm install antd @ant-design/icons react-router

# Backend
mkdir -p backend/app
cd backend
python -m venv .venv && source .venv/bin/activate
pip install "fastapi[standard]" oracledb pydantic uvicorn python-jose passlib structlog
```

**python-oracledb mode Thin :** Pas de dependance Oracle Client. Connexion directe. Le mode Thin est le defaut de python-oracledb 3.4.1.

### Naming Conventions (OBLIGATOIRES)

| Contexte | Convention | Exemple |
|---|---|---|
| Tables Oracle | UPPER_SNAKE_CASE | `USERS`, `ACTIONS_CATALOG` |
| Colonnes Oracle | UPPER_SNAKE_CASE | `USER_ID`, `CREATED_AT` |
| JSON API | snake_case | `{ "user_name": "...", "created_at": "..." }` |
| Fichiers Python | snake_case.py | `catalog_repository.py` |
| Classes Python | PascalCase | `IdpError`, `UserProfile` |
| Fonctions Python | snake_case | `get_by_username()` |
| Fichiers composants React | PascalCase.tsx | `AppLayout.tsx`, `TopNav.tsx` |
| Composants React | PascalCase | `AppLayout`, `TopNav` |
| Hooks React | camelCase (use prefix) | `useAuth()` |
| Props React | camelCase | `<TopNav activeTab="catalog" />` |
| CSS classes | kebab-case | `.app-layout`, `.top-nav` |
| Variables locales TS | camelCase | `const isLoading` |
| Constantes | UPPER_SNAKE_CASE | `const MAX_RETRY = 3` |

### API Response Format (OBLIGATOIRE)

Succes : `{ "data": { ... } }` ou `{ "data": [...], "pagination": { ... } }`
Erreur : `{ "error": { "code": "...", "message": "...", "details": { ... } } }`
Dates : ISO 8601 UTC (`2026-01-27T14:30:00Z`)
Nulls : Champs absents omis (pas `"field": null`)

### Error Handling Pattern

```python
# backend/app/core/exceptions.py
class IdpError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}

class NotFoundError(IdpError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(404, code, message, details)

class ForbiddenError(IdpError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(403, code, message, details)

class PlatformError(IdpError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(502, code, message, details)

class VaultError(IdpError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(502, code, message, details)

class ServiceNowError(IdpError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(502, code, message, details)
```

### Structured Logging Pattern

```python
# backend/app/core/logging.py
import structlog

def configure_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
    )
```

Chaque entree de log DOIT contenir : timestamp, level, event, correlation_id.

### Oracle Pool Pattern

```python
# backend/app/core/database.py
import oracledb
from contextlib import asynccontextmanager
from app.core.config import settings

pool: oracledb.AsyncConnectionPool | None = None

async def create_pool():
    global pool
    pool = oracledb.create_pool_async(
        user=settings.oracle_user,
        password=settings.oracle_password,
        dsn=settings.oracle_dsn,
        min=settings.oracle_min_pool,  # default 2
        max=settings.oracle_max_pool,  # default 10
    )

async def close_pool():
    global pool
    if pool:
        await pool.close()
        pool = None

@asynccontextmanager
async def get_connection():
    async with pool.acquire() as conn:
        yield conn
```

### Theme Desjardins Pattern

```typescript
// frontend/src/theme/desjardins.ts
import type { ThemeConfig } from 'antd';

export const desjardinsTheme: ThemeConfig = {
  token: {
    colorPrimary: '#00874E',
    // Ajouter les tokens selon l'UX spec : bordures, spacings, fond
  },
};
```

### Vite Proxy Pattern

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
});
```

### Migration SQL V001 Pattern

```sql
-- database/migrations/V001_create_users.sql
CREATE SEQUENCE SEQ_USERS START WITH 1 INCREMENT BY 1;

CREATE TABLE USERS (
    ID NUMBER DEFAULT SEQ_USERS.NEXTVAL PRIMARY KEY,
    USERNAME VARCHAR2(255) NOT NULL,
    DISPLAY_NAME VARCHAR2(255),
    PROFILE VARCHAR2(50) NOT NULL,
    SAML_SUBJECT VARCHAR2(512),
    CREATED_AT TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    UPDATED_AT TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX UK_USERS_USERNAME ON USERS(USERNAME);
```

### Project Structure Notes

Structure COMPLETE a creer (conforme a l'Architecture) :

```
idp-portal/
├── .gitignore
├── .env.example
├── README.md
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── public/
│   │   └── favicon.svg
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── vite-env.d.ts
│       ├── theme/
│       │   └── desjardins.ts
│       ├── types/
│       │   ├── api.ts              (stub)
│       │   └── common.ts           (stub)
│       ├── services/
│       │   └── api_client.ts       (stub)
│       ├── hooks/                   (vide, pret)
│       ├── contexts/
│       │   └── AuthContext.tsx      (stub minimal)
│       ├── pages/
│       │   ├── CatalogPage.tsx     (placeholder)
│       │   ├── ExecutionsPage.tsx   (placeholder)
│       │   ├── DashboardPage.tsx    (placeholder)
│       │   ├── AdminPage.tsx        (placeholder)
│       │   └── NotFoundPage.tsx
│       └── components/
│           ├── layout/
│           │   ├── AppLayout.tsx
│           │   ├── TopNav.tsx
│           │   └── index.ts
│           ├── catalog/             (vide, pret)
│           ├── execution/           (vide, pret)
│           ├── shared/              (vide, pret)
│           ├── admin/               (vide, pret)
│           └── dashboard/           (vide, pret)
├── backend/
│   ├── pyproject.toml
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── deps.py             (stub)
│       │   └── v1/
│       │       ├── __init__.py
│       │       └── health.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── common.py
│       │   └── auth.py             (stub)
│       ├── repositories/
│       │   ├── __init__.py
│       │   └── user_repository.py  (stub)
│       ├── services/
│       │   └── __init__.py
│       ├── adapters/
│       │   └── __init__.py
│       ├── websocket/
│       │   └── __init__.py
│       └── core/
│           ├── __init__.py
│           ├── config.py
│           ├── database.py
│           ├── security.py         (stub)
│           ├── logging.py
│           ├── exceptions.py
│           └── middleware.py
├── database/
│   ├── migrations/
│   │   └── V001_create_users.sql
│   └── seed/
│       └── (vide, pret)
├── scripts/
│   └── run_migrations.sh
└── docs/
    └── (vide, pret)
```

**Dossiers crees vides (prets pour les stories suivantes) :**
- `frontend/src/components/catalog/` — Story 3.1
- `frontend/src/components/execution/` — Story 4.1
- `frontend/src/components/shared/` — Story 3.1 (ImpactIndicator)
- `frontend/src/components/admin/` — Story 2.1
- `frontend/src/components/dashboard/` — Story 5.1
- `backend/app/services/` — Story 1.2+ (execution_service, vault_service...)
- `backend/app/adapters/` — Story 4.4 (base_adapter, aap_adapter...)
- `backend/app/websocket/` — Story 4.6

### Anti-Patterns INTERDITS

| Anti-pattern | Correction |
|---|---|
| `raise Exception("something failed")` | `raise PlatformError(code="...", message="...")` |
| `console.log("debug")` dans le frontend | Supprimer ou logger conditionnel |
| `return {"name": "..."}` sans wrapper | `return {"data": {"name": "..."}}` |
| Dates en format local dans l'API | ISO 8601 UTC : `2026-01-27T14:30:00Z` |
| `catch (e) {}` silencieux | Logger + afficher erreur |
| Tests frontend dans un dossier separe | Co-localises avec le composant |
| camelCase dans le JSON API | snake_case partout |
| localStorage pour tokens | Memoire uniquement (Story 1.2) |
| ORM (SQLAlchemy, SQLModel) | SQL brut via python-oracledb |
| Docker pour le deploiement | VM directe (Nginx + systemd) |

### References

- [Source: planning-artifacts/architecture.md#Starter Template Evaluation] — Commandes d'initialisation, versions, structure
- [Source: planning-artifacts/architecture.md#Core Architectural Decisions] — Data architecture, error handling, logging
- [Source: planning-artifacts/architecture.md#Implementation Patterns & Consistency Rules] — Naming, structure, format patterns
- [Source: planning-artifacts/architecture.md#Project Structure & Boundaries] — Arborescence complete
- [Source: planning-artifacts/ux-design-specification.md#Design System] — Theme Desjardins (#00874E), layout principal, tokens
- [Source: planning-artifacts/epics.md#Story 1.1] — Acceptance criteria originaux
- [Source: planning-artifacts/prd.md#MVP Feature Set] — Perimetre MVP

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- `requires-python` ajuste de `>=3.12` a `>=3.11` (Python 3.11.8 disponible sur la machine de dev)
- `jsdom` remplace par `happy-dom` (incompatibilite ESM avec Node.js 20.11.1)
- Node.js 20.11.1 produit des warnings `EBADENGINE` pour Vite 7.3.1 (requiert 20.19+) — fonctionnel malgre les warnings

### Completion Notes List

- Task 1: Monorepo initialise — structure complete (frontend Vite react-ts, backend FastAPI, database, scripts, docs)
- Task 2: Theme Desjardins (#00874E) configure via ConfigProvider, AppLayout (top bar 56px fixe, fond #FAFBFC), TopNav (4 onglets)
- Task 3: Vite proxy `/api` et `/ws` configure, React Router 7 avec 4 routes + 404, lazy loading actif
- Task 4: FastAPI skeleton complet — config pydantic-settings, pool oracledb async, exceptions IdpError hierarchy, middleware correlation ID + CORS, health endpoint, exception handler global
- Task 5: Migration V001 SQL (USERS table, sequence, unique index) + script run_migrations.sh
- Task 6: structlog JSON configure (timestamp ISO, level, event, correlation_id via contextvars)
- Task 7: Pydantic v2 models — ErrorResponse, PaginatedResponse, HealthStatus, UserProfile, TokenPayload
- Task 8: user_repository.py stub — get_by_username() et create_or_update() en SQL brut
- Task 9: Verification end-to-end — 53 tests passes (42 backend + 11 frontend), build frontend OK, backend charge OK

### Change Log

- 2026-01-28: Implementation initiale — Story 1.1 complete, 9 tasks / 30 subtasks

### File List

**Frontend (nouveau):**
- frontend/src/App.tsx
- frontend/src/App.test.tsx
- frontend/src/main.tsx
- frontend/src/test-setup.ts
- frontend/src/theme/desjardins.ts
- frontend/src/theme/desjardins.test.ts
- frontend/src/types/api.ts
- frontend/src/types/common.ts
- frontend/src/services/api_client.ts
- frontend/src/contexts/AuthContext.tsx
- frontend/src/pages/CatalogPage.tsx
- frontend/src/pages/ExecutionsPage.tsx
- frontend/src/pages/DashboardPage.tsx
- frontend/src/pages/AdminPage.tsx
- frontend/src/pages/NotFoundPage.tsx
- frontend/src/components/layout/AppLayout.tsx
- frontend/src/components/layout/AppLayout.test.tsx
- frontend/src/components/layout/TopNav.tsx
- frontend/src/components/layout/index.ts
- frontend/vite.config.ts
- frontend/package.json

**Backend (nouveau):**
- backend/pyproject.toml
- backend/app/__init__.py
- backend/app/main.py
- backend/app/core/__init__.py
- backend/app/core/config.py
- backend/app/core/database.py
- backend/app/core/exceptions.py
- backend/app/core/logging.py
- backend/app/core/middleware.py
- backend/app/core/security.py
- backend/app/api/__init__.py
- backend/app/api/deps.py
- backend/app/api/v1/__init__.py
- backend/app/api/v1/health.py
- backend/app/models/__init__.py
- backend/app/models/common.py
- backend/app/models/auth.py
- backend/app/repositories/__init__.py
- backend/app/repositories/user_repository.py
- backend/app/services/__init__.py
- backend/app/adapters/__init__.py
- backend/app/websocket/__init__.py
- backend/tests/__init__.py
- backend/tests/test_project_structure.py
- backend/tests/test_config.py
- backend/tests/test_exceptions.py
- backend/tests/test_api.py
- backend/tests/test_logging.py
- backend/tests/test_migration.py
- backend/tests/test_models.py
- backend/tests/test_user_repository.py

**Database (nouveau):**
- database/migrations/V001_create_users.sql

**Scripts (nouveau):**
- scripts/run_migrations.sh

**Racine (nouveau):**
- .gitignore
- .env.example
- README.md
