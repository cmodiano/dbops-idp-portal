# Story 1.4: Observabilite, Health Check et CI/CD

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBOPS responsable de la plateforme,
I want des logs structures, un health check et un pipeline de deploiement automatise,
so that le portail est monitorable, deployable et pret pour la production.

## Acceptance Criteria

1. **AC1 — Health Check** : Given le backend est en cours d'execution, When on appelle GET /api/v1/health, Then la reponse indique le statut de connectivite Oracle, et retourne HTTP 200 si OK, 503 sinon.

2. **AC2 — Correlation ID** : Given une requete HTTP arrive sur le backend, When elle est traitee, Then un correlation ID (X-Idp-Request-Id, UUID) est genere et propage dans tous les logs.

3. **AC3 — Structured Logging** : Given une requete HTTP arrive sur le backend, When elle est traitee, Then chaque entree de log est en JSON structure (structlog) avec timestamp, level, event, correlation_id, user_id.

4. **AC4 — CI/CD Pipeline** : Given un push sur la branche main, When GitHub Actions se declenche, Then le pipeline execute : lint (eslint+ruff), type check (tsc+mypy), tests (vitest+pytest), build (vite build). And le deploy copie les fichiers via SSH+rsync vers la VM.

5. **AC5 — Nginx** : Given le deploiement est effectue, When la config Nginx est appliquee, Then idp-portal.conf termine TLS et proxy vers Uvicorn.

6. **AC6 — systemd** : Given le deploiement est effectue, When le service systemd est actif, Then idp-portal.service gere le process Uvicorn avec restart automatique.

7. **AC7 — CORS** : Given une requete HTTP arrive sur le backend, When le middleware CORS est actif, Then seule l'origin portail est autorisee.

8. **AC8 — Log Levels** : Given le backend est en cours d'execution, When des evenements sont logues, Then les niveaux de log suivent la convention Architecture (debug, info, warning, error, critical).

## Tasks / Subtasks

- [x] Task 1: Enrichir le logging structure avec contexte requete (AC: 2, 3, 8)
  - [x] 1.1: Ajouter un middleware de request logging dans `backend/app/core/middleware.py` qui logue chaque requete avec : method, path, status_code, duration_ms, user_id (si authentifie), correlation_id. Utiliser structlog.get_logger(). Log level: info pour succes, warning pour 4xx, error pour 5xx
  - [x] 1.2: Binder `user_id` dans structlog contextvars apres authentication (enrichir `get_current_user()` dans `backend/app/core/security.py` pour ajouter `structlog.contextvars.bind_contextvars(user_id=user.id)`)
  - [x] 1.3: Ajouter le setting `log_level` dans `backend/app/core/config.py` (defaut: "INFO", configurable via env var `LOG_LEVEL`). Appliquer le level dans `configure_logging()` de `backend/app/core/logging.py`
  - [x] 1.4: Ajouter les processeurs structlog manquants : `structlog.processors.StackInfoRenderer()`, `structlog.processors.format_exc_info` pour les traces d'erreur
  - [x] 1.5: Ecrire les tests unitaires pour le request logging middleware (succes 200, erreur 4xx/5xx, duration logged, user_id present quand authentifie, absent quand anonyme), la configuration du log level, et les processeurs structlog

- [x] Task 2: Frontend — script test et configuration vitest (AC: 4)
  - [x] 2.1: Ajouter le script `"test": "vitest run"` et `"test:watch": "vitest"` dans `frontend/package.json`
  - [x] 2.2: Verifier que `npx vitest run` execute tous les tests frontend existants avec succes (37 tests attendus)

- [x] Task 3: Backend — configuration mypy pour type checking (AC: 4)
  - [x] 3.1: Ajouter `mypy>=1.10` aux dev dependencies dans `backend/pyproject.toml`
  - [x] 3.2: Configurer `[tool.mypy]` dans `backend/pyproject.toml` : python_version = "3.11", strict = false, warn_return_any = true, warn_unused_configs = true, ignore_missing_imports = true (pour les libs sans stubs)
  - [x] 3.3: Executer `mypy app/` et corriger les erreurs de type critiques (ne pas forcer strict mode — trop de refactoring pour une story observabilite)
  - [x] 3.4: Ecrire un test de validation qui verifie que mypy est installe et configurable (test_project_structure ou equivalent)

- [x] Task 4: CI/CD Pipeline — GitHub Actions (AC: 4)
  - [x] 4.1: Creer `.github/workflows/ci.yml` declenche sur push/PR vers main avec les jobs :
    - **lint-backend** : `ruff check app/ tests/`
    - **lint-frontend** : `cd frontend && npm ci && npm run lint`
    - **typecheck-backend** : `mypy app/`
    - **typecheck-frontend** : `cd frontend && npx tsc -b --noEmit`
    - **test-backend** : `pytest tests/ -v` (avec setup Python 3.11, sans Oracle — tests unitaires uniquement)
    - **test-frontend** : `cd frontend && npm ci && npm test`
    - **build-frontend** : `cd frontend && npm ci && npm run build`
  - [x] 4.2: Creer `.github/workflows/deploy.yml` declenche manuellement (workflow_dispatch) ou sur push vers main (apres CI success) avec les etapes :
    - Build frontend (`vite build`)
    - Package backend
    - Deploy via SSH + rsync vers la VM cible (variables secrets : `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_KEY`, `DEPLOY_PATH`)
    - Restart systemd service (`sudo systemctl restart idp-portal`)
  - [x] 4.3: Ecrire un test de validation des fichiers YAML workflow (syntaxe valide, jobs attendus presents)

- [x] Task 5: Configuration Nginx (AC: 5)
  - [x] 5.1: Creer `nginx/idp-portal.conf` avec :
    - Listener HTTPS 443 avec TLS 1.2+ (ssl_protocols TLSv1.2 TLSv1.3)
    - Certificats SSL (chemins parametrables)
    - Location `/` : servir les fichiers statiques frontend depuis `/var/www/idp-portal/frontend/dist/`
    - Location `/api/` : proxy_pass vers http://127.0.0.1:8000 (Uvicorn)
    - Location `/ws/` : proxy_pass WebSocket vers http://127.0.0.1:8000 avec upgrade headers
    - Headers securite : X-Content-Type-Options, X-Frame-Options, Strict-Transport-Security
    - try_files $uri /index.html pour le SPA routing
    - Redirect HTTP 80 → HTTPS 443
  - [x] 5.2: Ecrire un test de validation de la syntaxe du fichier conf Nginx (structure attendue presente)

- [x] Task 6: Service systemd (AC: 6)
  - [x] 6.1: Creer `nginx/idp-portal.service` avec :
    - Type=simple
    - ExecStart : uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
    - Restart=always, RestartSec=5
    - WorkingDirectory vers le repertoire backend
    - User=idp-portal (user systeme dedie)
    - EnvironmentFile pour charger les variables d'environnement
    - After=network.target oracle.service
  - [x] 6.2: Ecrire un test de validation du fichier service (sections [Unit], [Service], [Install] presentes, directives clefs presentes)

- [x] Task 7: Script de deploiement (AC: 4)
  - [x] 7.1: Creer `scripts/deploy.sh` avec :
    - Verification des arguments (host, user, path)
    - rsync frontend/dist/ vers le serveur (repertoire Nginx static)
    - rsync backend/ vers le serveur (repertoire application)
    - Commande SSH pour restart systemd (`systemctl restart idp-portal`)
    - Gestion d'erreur (set -euo pipefail, messages explicites)
  - [x] 7.2: Ecrire un test de validation du script (fichier executable, shebang present, options de securite set -e)

- [x] Task 8: Validation end-to-end et regression (AC: tous)
  - [x] 8.1: Verifier AC1 — health check retourne 200/503 avec statut Oracle (deja implemente, confirmer via tests existants)
  - [x] 8.2: Verifier AC2 — correlation ID present dans les reponses et les logs (deja implemente, confirmer via tests existants)
  - [x] 8.3: Verifier AC3 — request logging avec timestamp, level, event, correlation_id, user_id (nouveau)
  - [x] 8.4: Verifier AC4 — CI/CD workflows valides et complets
  - [x] 8.5: Verifier AC5 — Nginx conf syntaxiquement correcte
  - [x] 8.6: Verifier AC6 — systemd service syntaxiquement correct
  - [x] 8.7: Verifier AC7 — CORS deja configure dans main.py (confirmer)
  - [x] 8.8: Verifier AC8 — log level configurable et conventions respectees
  - [x] 8.9: Regression check — tous les tests existants passent (118 backend + 37 frontend = 155 attendus minimum)

## Dev Notes

### Architecture Requirements

- **Structured logging** : structlog JSON → fichiers → Splunk Forwarder. Correlation ID (X-Idp-Request-Id) sur chaque requete. [Source: architecture.md — Communication Patterns, Logging structure]
- **Health check** : GET /api/v1/health verifie la connectivite Oracle. Au MVP, seul Oracle est verifie. Vault et ServiceNow seront ajoutes quand ces integrations existeront (Epic 4). [Source: architecture.md — Infrastructure & Deployment]
- **CI/CD** : GitHub Actions. Pipeline : lint (eslint+ruff), type check (tsc+mypy), tests (vitest+pytest), build (vite build). Deploy : SSH + rsync vers VM. [Source: architecture.md — Infrastructure & Deployment]
- **Deployment VM** : Nginx reverse proxy (TLS) + Uvicorn + systemd. 2 VMs minimum (HA active-active) en prod. [Source: architecture.md — Infrastructure & Deployment]
- **Monitoring** : Dynatrace OneAgent sur VM (hors scope story — infrastructure). Health check endpoint utilise par Dynatrace et load balancer. [Source: architecture.md — Infrastructure & Deployment]
- **Log levels** : debug, info, warning, error, critical — conventions documentees dans l'architecture. [Source: architecture.md — Communication Patterns]
- **CORS** : origin portail uniquement — deja configure dans main.py via settings.cors_origin.
- **Error hierarchy** : IdpError → NotFoundError, UnauthorizedError, ForbiddenError, PlatformError, VaultError, ServiceNowError — deja implemente.

### What Already Exists (DO NOT REIMPLEMENT)

Les elements suivants sont deja implementes dans les stories 1.1 et 1.2. Le dev agent DOIT les enrichir, PAS les remplacer.

| Element | Fichier | Statut |
|---|---|---|
| structlog JSON logging | `backend/app/core/logging.py` | Existe — enrichir avec log_level et processeurs |
| Correlation ID middleware | `backend/app/core/middleware.py` | Existe — enrichir avec request logging |
| Health check endpoint | `backend/app/api/v1/health.py` | Existe — AC1 deja satisfaite |
| CORS middleware | `backend/app/main.py` | Existe — AC7 deja satisfaite |
| IdpError hierarchy | `backend/app/core/exceptions.py` | Existe — ne pas toucher |
| Configuration settings | `backend/app/core/config.py` | Existe — ajouter log_level |
| Tests logging | `backend/tests/unit/test_logging.py` | Existe — enrichir |
| Tests API health | `backend/tests/unit/test_api.py` | Existe — confirmer |

### What Needs to Be CREATED

| Element | Fichier | Description |
|---|---|---|
| Request logging middleware | `backend/app/core/middleware.py` (enrichir) | Log chaque requete avec method, path, status, duration, user_id |
| Log level config | `backend/app/core/config.py` (enrichir) | Setting `log_level` env var |
| mypy config | `backend/pyproject.toml` (enrichir) | Section [tool.mypy] |
| CI workflow | `.github/workflows/ci.yml` | Lint + type check + tests + build |
| Deploy workflow | `.github/workflows/deploy.yml` | SSH + rsync + restart |
| Nginx config | `nginx/idp-portal.conf` | TLS + proxy + static files |
| systemd service | `nginx/idp-portal.service` | Uvicorn process manager |
| Deploy script | `scripts/deploy.sh` | Automatisation deploy VM |
| Frontend test script | `frontend/package.json` (enrichir) | Script `test` manquant |

### Technical Stack (verified January 2026)

| Technology | Version | Role |
|---|---|---|
| FastAPI | 0.115+ | API backend |
| Python | 3.11.8 | Runtime (machine constraint, NOT 3.12) |
| structlog | 24.0+ | Structured logging JSON |
| ruff | 0.8+ | Python linting |
| mypy | 1.10+ | Python type checking (A AJOUTER) |
| pytest | 8.0+ | Backend tests |
| pytest-asyncio | 0.24+ | Async tests |
| Vite | 7.x | Frontend build |
| vitest | 4.0+ | Frontend tests |
| ESLint | 9.x | Frontend linting |
| TypeScript | 5.9+ | Frontend type checking |
| React | 19.x | UI framework |
| Ant Design | 6.2+ | Design system |
| Nginx | latest stable | Reverse proxy TLS |
| Uvicorn | 0.30+ | ASGI server |
| GitHub Actions | N/A | CI/CD platform |

### Previous Story Intelligence

#### Story 1.1 Learnings
- Python 3.11.8 sur la machine (pas 3.12 comme prevu en architecture)
- happy-dom au lieu de jsdom (incompatibilite ESM avec Node.js 20.11.1)
- Node.js 20.11.1 produit des warnings EBADENGINE pour Vite 7.3.1 mais fonctionne
- Patterns fondation : IdpError hierarchy, structlog JSON, Oracle pool, Ant Design theme, API response wrapper

#### Story 1.2 Learnings
- AUTH_DEV_BYPASS=true pour dev local sans IdP — retourne un dev user
- get_current_user() retourne UserProfile avec fields: id, username, display_name, profile
- 401 pour erreurs auth, 403 pour RBAC
- apiFetch deja configure pour unwrap .data as T

#### Story 1.3 Learnings (la plus recente)
- cachetools ajoute a pyproject.toml pour TTLCache
- 155 tests passing (118 backend + 37 frontend) apres code review — NE PAS CASSER
- User type dans `types/common.ts` (pas `types/api.ts`)
- Ant Design Content render deja `<main>` — pas de wrapper explicite necessaire
- PROJECT_ROOT path fixe : 4 niveaux de `.parent` depuis tests/unit/

#### Code Review Patterns from 1.3 (DO NOT REGRESS)
- H1: Toujours fermer les cursors Oracle (ou utiliser `async with`)
- H2: Validation des valeurs (profils SAML)
- H3: Eviter TOCTOU — utiliser MERGE Oracle pour upsert
- H4: Tester toutes les fonctions repository

### Naming Conventions (MANDATORY)

| Context | Convention | Example |
|---|---|---|
| Python files | snake_case.py | middleware.py, logging.py |
| Python classes | PascalCase | RequestLoggingMiddleware |
| Python functions | snake_case | configure_logging() |
| Python constants | UPPER_SNAKE_CASE | CORRELATION_HEADER |
| JSON API | snake_case | correlation_id |
| Config env vars | UPPER_SNAKE_CASE | LOG_LEVEL |
| GitHub workflows | kebab-case.yml | ci.yml, deploy.yml |
| Nginx files | kebab-case.conf | idp-portal.conf |
| systemd files | kebab-case.service | idp-portal.service |
| Shell scripts | snake_case.sh | deploy.sh |

### Anti-Patterns FORBIDDEN

| Anti-pattern | Correction |
|---|---|
| `raise Exception("x")` | `raise IdpError(500, "INTERNAL_ERROR", "...")` |
| `print()` dans le backend | `structlog.get_logger().info(...)` |
| `console.log()` dans le frontend | Supprimer ou conditionnel |
| Log sans correlation_id | Toujours via structlog contextvars |
| Secret en clair dans les workflows | Utiliser GitHub Secrets |
| `return {"name": "..."}` | `return {"data": {"name": "..."}}` |
| Spinner de deploy sans gestion d'erreur | `set -euo pipefail` dans les scripts |
| mypy strict mode | `strict = false` — trop invasif pour cette story |

### Log Level Convention (Architecture)

| Niveau | Usage | Exemple |
|---|---|---|
| debug | Detail technique, payload entrant, query SQL | `logger.debug("sql_query", query="SELECT ...")` |
| info | Action metier reussie | `logger.info("request_completed", method="GET", path="/api/v1/health")` |
| warning | Situation inhabituelle non bloquante | `logger.warning("oracle_pool_failed", error="...")` |
| error | Echec recuperable | `logger.error("platform_error", platform="AAP")` |
| critical | Echec irrecuperable | `logger.critical("database_down")` |

### API Response Format (MANDATORY)

```json
// Succes
{ "data": { "status": "healthy", "oracle": "connected" } }

// Erreur
{ "error": { "code": "ORACLE_UNAVAILABLE", "message": "...", "details": {} } }
```

### Existing File Paths (Absolute)

- `idp-portal/backend/app/core/logging.py` — a enrichir
- `idp-portal/backend/app/core/middleware.py` — a enrichir
- `idp-portal/backend/app/core/config.py` — a enrichir
- `idp-portal/backend/app/core/security.py` — a enrichir (user_id binding)
- `idp-portal/backend/app/api/v1/health.py` — deja OK
- `idp-portal/backend/app/main.py` — deja OK
- `idp-portal/backend/pyproject.toml` — a enrichir (mypy)
- `idp-portal/frontend/package.json` — a enrichir (test script)
- `idp-portal/backend/tests/unit/test_logging.py` — a enrichir
- `idp-portal/backend/tests/unit/test_api.py` — confirmer

### Project Structure Notes

- Monorepo : `idp-portal/frontend/` + `idp-portal/backend/` + `idp-portal/database/` + `idp-portal/scripts/`
- Tests backend : `backend/tests/unit/` et `backend/tests/integration/`
- Tests frontend : co-localises (`.test.tsx` a cote de `.tsx`)
- Nginx config et systemd service vont dans `idp-portal/nginx/`
- Scripts deploy dans `idp-portal/scripts/`
- CI/CD dans `idp-portal/.github/workflows/`

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.4]
- [Source: _bmad-output/planning-artifacts/architecture.md — Infrastructure & Deployment, Communication Patterns, CI/CD Pipeline]
- [Source: _bmad-output/planning-artifacts/prd.md — NFR1-NFR5 Performance, NFR6-NFR11 Securite, NFR12-NFR16 Fiabilite]
- [Source: _bmad-output/implementation-artifacts/1-3-profil-rbac-et-navigation-du-portail.md — Previous story learnings, test counts, patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- mypy runs with 18 known warnings due to incomplete third-party stubs (oracledb, cachetools, jose) - documented and expected per story requirements (strict=false)

### Completion Notes List

- **Task 1**: Implemented RequestLoggingMiddleware with method, path, status_code, duration_ms logging. Log levels: info (2xx), warning (4xx), error (5xx). Added user_id binding in get_current_user(). Added log_level setting (LOG_LEVEL env var). Added StackInfoRenderer and format_exc_info processors. 12 new tests in test_logging.py.
- **Task 2**: Added "test" and "test:watch" scripts to frontend/package.json. 37 frontend tests pass.
- **Task 3**: Added mypy>=1.10 to dev dependencies. Configured [tool.mypy] with python_version=3.11, strict=false, warn_return_any=true, ignore_missing_imports=true. Fixed health.py return type. 3 new tests for mypy config.
- **Task 4**: Created ci.yml with 7 jobs (lint-backend, lint-frontend, typecheck-backend, typecheck-frontend, test-backend, test-frontend, build-frontend). Created deploy.yml with workflow_dispatch and push triggers, rsync deployment, health check. 6 new tests for workflows.
- **Task 5**: Created nginx/idp-portal.conf with HTTPS 443 + TLS 1.2+, API proxy, WebSocket proxy, security headers, HTTP→HTTPS redirect, SPA routing. 8 new tests.
- **Task 6**: Created nginx/idp-portal.service with Type=simple, Restart=always, User=idp-portal, EnvironmentFile. 7 new tests.
- **Task 7**: Created scripts/deploy.sh with argument validation, rsync deployment, systemctl restart, error handling (set -euo pipefail). 7 new tests.
- **Task 8**: All ACs verified. 162 backend + 37 frontend = 199 tests passing (baseline was 155).

### File List

**New Files:**
- `.github/workflows/ci.yml` — CI pipeline (lint, typecheck, test, build)
- `.github/workflows/deploy.yml` — Deploy pipeline (SSH + rsync)
- `nginx/idp-portal.conf` — Nginx reverse proxy config
- `nginx/idp-portal.service` — systemd service unit

**Modified Files:**
- `backend/app/core/middleware.py` — Added RequestLoggingMiddleware
- `backend/app/core/logging.py` — Added log_level, stdlib integration, StackInfoRenderer, format_exc_info
- `backend/app/core/config.py` — Added log_level setting
- `backend/app/api/deps.py` — Added user_id binding to structlog contextvars
- `backend/app/api/v1/health.py` — Fixed return type annotation
- `backend/app/main.py` — Added RequestLoggingMiddleware
- `backend/pyproject.toml` — Added mypy, pytest-mock to dev deps; added [tool.mypy] config
- `backend/tests/unit/test_logging.py` — Added 12 tests for request logging, log level, processors
- `backend/tests/unit/test_auth_api.py` — Added 2 tests for user_id binding
- `backend/tests/unit/test_project_structure.py` — Added 28 tests for mypy, workflows, nginx, systemd, deploy script
- `frontend/package.json` — Added test and test:watch scripts
- `scripts/deploy.sh` — New deploy script

### Change Log

- 2026-01-28: Story 1.4 implementation complete. All 8 tasks done. 199 tests passing (162 backend + 37 frontend). Ready for code review.
- 2026-01-28: Code review fixes applied:
  - Fixed deploy.yml workflow syntax (removed invalid `uses:` reference)
  - Added LOG_LEVEL validation with Enum (prevents invalid values)
  - Added correlation_id propagation in health check response
  - Explicitly documented user_id in RequestLoggingMiddleware
  - Improved error handling in deploy.sh (SSH failures, build verification)
  - Added Oracle error logging in health check
  - Improved mypy CI workflow error handling
  - Added documentation comments in nginx config and systemd service