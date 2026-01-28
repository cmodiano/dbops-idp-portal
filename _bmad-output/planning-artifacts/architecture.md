---
stepsCompleted:
  - step-01-init
  - step-02-context
  - step-03-starter
  - step-04-decisions
  - step-05-patterns
  - step-06-structure
  - step-07-validation
  - step-08-complete
inputDocuments:
  - planning-artifacts/prd.md
  - planning-artifacts/ux-design-specification.md
  - design-thinking-2026-01-26.md
workflowType: 'architecture'
lastStep: 8
status: 'complete'
completedAt: '2026-01-27'
project_name: 'test'
user_name: 'Cyrille'
date: '2026-01-27'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements : 45 FR en 10 domaines**

| Domaine | FR | Implications architecturales |
|---|---|---|
| **Software Catalog** | FR1-FR7 | CRUD entites action, schema JSON parametres, metadonnees dynamiques, generation doc IA |
| **Decouverte & Navigation** | FR8-FR12 | Recherche full-text, filtrage multi-criteres, vues filtrees par RBAC |
| **Execution d'Actions** | FR13-FR18 | Formulaires dynamiques, validation, facade API event-driven, routage multi-plateforme, Vault, ServiceNow |
| **Suivi d'Execution** | FR19-FR23 | Callbacks asynchrones, mise a jour temps reel (WebSocket/SSE), historique persiste |
| **Controle d'Acces** | FR24-FR29 | SSO entreprise, RBAC granulaire (action x profil x environnement), workflows d'approbation |
| **Audit & Conformite** | FR30-FR35 | Logs immutables (append-only), tracabilite SOC1, export rapports, evidence generation |
| **Autoremediation** | FR36-FR38 | Detection d'echec, proposition corrective, execution auto (faible risque) |
| **Analytics** | FR39-FR41 | Scorecards, dashboards, agregations temps reel et historique |
| **Donnees & Inventaire** | FR42-FR43 | Sync API inventaire interne, alimentation dynamique des formulaires |
| **Communication & IA** | FR44-FR45 | Canal DBA, interface conversationnelle NLP |

**Non-Functional Requirements : 25 NFR sur 5 axes**

| Axe | NFR cles | Impact architectural |
|---|---|---|
| **Performance** | Pages < 2s, soumission < 3s, statut < 5s apres callback, recherche < 1s | Cache, index, optimisation requetes, CDN statiques |
| **Securite** | TLS 1.2+, zero credential stocke, logs immutables, sessions timeout, RBAC audit | Vault dynamique, append-only store, middleware securite |
| **Fiabilite** | SLA 99.9%, isolation des plateformes, reprise sur callback, break-the-glass externe | HA multi-instance, circuit breaker par plateforme, idempotence |
| **Integration** | Independence des plateformes, callbacks idempotents, tolerance ServiceNow 30s, sync inventaire non-bloquante | Pattern adapter/plugin, retry avec backoff, async processing |
| **Scalabilite** | Plugin nouvelles plateformes, 100+ actions, 10 000+ executions/an, multi-moteur sans refonte | Architecture modulaire, separation concerns, schema extensible |

### Scale & Complexity

| Indicateur | Niveau | Justification |
|---|---|---|
| **Temps reel** | Eleve | Timeline d'execution via callbacks asynchrones multi-plateformes, mise a jour instantanee UI |
| **Multi-tenancy** | Modere | Pas de multi-tenant classique, mais RBAC a 3 dimensions (action x profil x environnement) |
| **Conformite reglementaire** | Eleve | SOC1, logs immutables, tracabilite complete, change management integre |
| **Complexite d'integration** | Eleve | 4 plateformes d'execution (AAP, GitHub Actions, Azure DevOps, Terraform) + Vault + ServiceNow + Inventaire interne + SSO |
| **Interaction utilisateur** | Modere-Eleve | Wizard dynamique, timeline temps reel, admin preview live, drawer, mais desktop-only |
| **Complexite donnees** | Modere | Catalogue d'actions (schema JSON flexible), historique executions (audit), inventaire (sync externe) |

- **Complexite globale : Elevee (enterprise-grade)**
- **Domaine technique primaire : Full-stack web + Integrations API**
- **Pattern architectural dominant : Event-driven facade + Plugin adapters**

### Technical Constraints & Dependencies

| Contrainte | Source | Impact |
|---|---|---|
| **On-prem ou Azure** (pas SaaS-only) | PRD | Exclut les solutions cloud-only, impose un deploiement maitrise |
| **Reseau bancaire** | PRD / Design Thinking | Connectivite vers les plateformes d'execution peut etre contrainte (proxy, firewall, zones reseau) |
| **SSO entreprise** | PRD | Protocole a confirmer (SAML, OIDC). L'architecture doit supporter les deux |
| **Zero credential stocke** | PRD | Vault obligatoire. Aucun fallback sur secrets locaux — si Vault down, execution refusee (NFR21) |
| **ServiceNow obligatoire** | PRD | Change management comme etape d'execution. Tolerance 30s latence API |
| **Inventaire interne comme source de verite** | PRD | Plus riche que CMDB ServiceNow. Sync periodique ou on-demand |
| **Break-the-glass externe** | PRD | Le portail n'a pas de mode degrade. DBOPS a un acces direct externe aux plateformes |
| **Greenfield** | PRD | Pas de dette technique, mais pas de fondation existante non plus |
| **Equipe DB automation** (pas frontend) | UX Spec | Le choix de stack doit privilegier la productivite frontend (frameworks avec composants prets) |

### Cross-Cutting Concerns Identified

| Preoccupation | Composants impactes | Strategie preliminaire |
|---|---|---|
| **Authentification & RBAC** | Tous | Middleware centralise. SSO → profil → permissions par action/env. Filtrage invisible cote UI |
| **Audit trail** | Execution, Admin, Catalogue | Store append-only. Chaque mutation cree un enregistrement immutable |
| **Gestion d'erreur** | Facade API, UI Timeline, Autoremediation | Pattern unifie : quoi/pourquoi/options. Circuit breaker par plateforme. Erreur != crash |
| **Temps reel** | Timeline, Dashboard, Notifications | WebSocket ou SSE du backend vers le frontend. Backend recoit callbacks des plateformes |
| **Securite des secrets** | Execution uniquement | Vault at runtime. Aucun secret en transit sauf entre Vault et plateforme cible |
| **Idempotence** | Callbacks, ServiceNow, Vault | Chaque callback a un ID unique. Doublon detecte et ignore. NFR18 explicite |
| **Observabilite** | Infrastructure | Logs structures, metriques, health checks. Necessaire pour le SLA 99.9% |

### UX Architectural Implications

| Exigence UX | Contrainte architecturale |
|---|---|
| **Timeline temps reel** (Temporal-style) | WebSocket/SSE bidirectionnel, etat d'execution persiste par etape |
| **Formulaires dynamiques** (schema-driven) | Schema JSON par action dans le catalogue, rendu cote client |
| **Drawer 480px + Wizard 640px** | SPA (Single Page Application) obligatoire — pas de rechargement page |
| **Skeleton loading** (shimmer) | API rapides, ou cache cote client avec invalidation |
| **Filtrage RBAC invisible** | API filtre en amont — le frontend ne recoit que les donnees autorisees |
| **Admin preview temps reel** | Rendu cote client des memes composants catalogue (composants reutilises) |
| **Export CSV/PDF** | Generation cote serveur (volume potentiel 10 000+ executions) |
| **Design system themeable** | Architecture frontend modulaire, tokens CSS/design centralises |
| **WCAG 2.1 AA** | Tests automatises axe-core en CI, composants accessibles natifs |

## Starter Template Evaluation

### Primary Technology Domain

Full-stack web : SPA React + API Python + Oracle DB. Base sur l'analyse du contexte projet et les preferences techniques de l'equipe (JavaScript/TypeScript ou Python, peu d'experience frontend, Oracle DB, deploiement VM ou Azure).

### Versions verifiees (janvier 2026)

| Technologie | Version | Role |
|---|---|---|
| **Vite** | 7.3.1 stable | Build tool frontend |
| **React** | 19 | Framework UI |
| **React Router** | 7.12.0 | Routing SPA |
| **Ant Design** | 6.2.0 | Design system enterprise |
| **TypeScript** | 5.x | Typage frontend |
| **FastAPI** | 0.115+ | Framework API backend |
| **Python** | 3.12+ | Runtime backend |
| **python-oracledb** | 3.4.1 (mode Thin) | Driver Oracle Database |
| **Pydantic** | v2.12+ | Validation donnees |

### Starter Options Considered

**Frontend :**

| Option | Avantages | Limites | Decision |
|---|---|---|---|
| `create vite` react-ts | Leger, rapide, flexible, standard | Minimal — tout a ajouter | **Retenu** |
| Full Stack FastAPI Template | React + FastAPI integre | PostgreSQL-centre, pas Oracle | Ecarte |
| Ant Design Pro (UmiJS) | Ant Design integre, layouts admin | Trop opinionated, impose UmiJS | Ecarte |

**Backend :**

| Option | Avantages | Limites | Decision |
|---|---|---|---|
| Structure manuelle FastAPI | Controle total, adapte Oracle | Plus de setup initial | **Retenu** |
| `fastapi-new` CLI | Officiel, structure de base | Tres minimal, PostgreSQL-centre | Ecarte |
| Full Stack Template | Complet (Docker, CI, tests) | PostgreSQL + SQLModel, pas Oracle | Ecarte |

### Selected Starter

**Frontend : Vite + React + TypeScript + Ant Design**

```bash
npm create vite@latest idp-portal -- --template react-ts
cd idp-portal
npm install antd @ant-design/icons react-router
```

**Backend : FastAPI + python-oracledb (structure manuelle)**

```bash
mkdir idp-api && cd idp-api
python -m venv .venv && source .venv/bin/activate
pip install "fastapi[standard]" oracledb pydantic uvicorn python-jose passlib
```

**Rationale :** Les starters officiels sont centres PostgreSQL/SQLModel. Notre stack Oracle + python-oracledb necessite une structure adaptee. Le template Vite react-ts est le point de depart le plus flexible pour ajouter Ant Design 6 et le theming Desjardins.

### Architectural Decisions Provided by Starter

**Language & Runtime :**
- Frontend : TypeScript strict (via Vite template)
- Backend : Python 3.12+ avec typing Pydantic v2
- Contrat API : OpenAPI auto-genere par FastAPI

**UI Component Library :**
- Ant Design 6.2 — enterprise-grade
- Composants natifs couvrant 80% des besoins UX : Drawer, Steps (wizard), Timeline, Table, Form, Tabs, Badge, Modal, Alert, Navigation
- Theming CSS Variables pour palette Desjardins (`#00874E`)

**Build Tooling :**
- Vite 7 avec HMR rapide
- ESLint + Prettier (fournis par template)
- Vitest + React Testing Library (tests frontend)
- pytest + httpx async (tests backend)

**Communication temps reel :**
- WebSocket natif FastAPI → React pour timeline d'execution
- Callbacks asynchrones des plateformes recus par endpoints REST

**Database :**
- Oracle Database via python-oracledb 3.4.1 mode Thin
- Pas de dependance Oracle Client — connexion directe
- Tables dediees portail : ACTIONS_CATALOG, EXECUTIONS, RBAC_POLICIES, AUDIT_LOG

**Project Structure :**

```
idp-portal/                    # Monorepo
├── frontend/                  # React + Vite + Ant Design
│   ├── src/
│   │   ├── components/        # ActionCard, ImpactIndicator, Timeline...
│   │   ├── pages/             # Catalogue, Executions, Dashboard, Admin
│   │   ├── hooks/             # useWebSocket, useAuth, useActions...
│   │   ├── services/          # Appels API
│   │   ├── theme/             # Tokens Desjardins (Ant Design config)
│   │   ├── types/             # Types TypeScript partages
│   │   └── App.tsx            # Routes principales
│   ├── vite.config.ts
│   └── package.json
├── backend/                   # FastAPI + Oracle
│   ├── app/
│   │   ├── api/               # Routes (catalog, executions, auth, admin, webhooks)
│   │   ├── core/              # Config, security, database connection
│   │   ├── models/            # Pydantic models + DB schemas
│   │   ├── services/          # Logique metier (execution engine, vault, servicenow)
│   │   ├── adapters/          # Adapters par plateforme (AAP, GitHub, Azure DevOps, Terraform)
│   │   ├── websocket/         # WebSocket manager timeline temps reel
│   │   └── main.py            # Point d'entree FastAPI
│   ├── tests/
│   ├── alembic/               # Migrations DB
│   └── pyproject.toml
├── docs/
└── docker-compose.yml         # Dev environment
```

**Note :** L'initialisation du projet avec ces commandes devrait etre la premiere story d'implementation.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation) :**
- SAML 2.0 authentication avec JWT session — prerequis a toute feature
- Repository Pattern avec SQL brut via python-oracledb — chaque feature backend en depend
- Platform adapter pattern (Strategy) — coeur du moteur d'execution
- Structured logging JSON vers Splunk — doit etre en place des le skeleton

**Important Decisions (Shape Architecture) :**
- WebSocket pour timeline temps reel
- Cache in-memory (pas de Redis)
- OpenAPI → Types TypeScript generes
- HA active-active 2 VMs minimum

**Deferred Decisions (Post-MVP) :**
- Task queue (Celery/ARQ) pour executions longues — callbacks suffisent au MVP
- Rate limiting avance — outil interne, charge maitrisee au MVP
- Blue/green deployment — rolling restart suffisant au MVP

### Data Architecture

**Acces donnees : SQL brut + Repository Pattern**

| Decision | Choix | Justification |
|---|---|---|
| **Acces donnees** | SQL brut via python-oracledb | Preference equipe, controle total des requetes Oracle, pas de couche ORM |
| **Pattern** | Repository Pattern | Chaque domaine (catalog, executions, rbac, audit) a son repository avec methodes dediees. SQL encapsule, testable |
| **Connexion DB** | Pool de connexions oracledb.create_pool() | Async, reutilisation des connexions, configurable (min/max) |
| **Schema JSON** | Colonne CLOB avec JSON_VALUE / JSON_TABLE (Oracle 19+) | Parametres d'action stockes en JSON, interrogeables via SQL natif Oracle |
| **Migrations** | Scripts SQL versionnes (V001_create_catalog.sql, V002_...) | Pas d'Alembic sans ORM. Scripts SQL sequentiels, historique en table SCHEMA_VERSION |
| **Audit log** | Table AUDIT_LOG append-only (INSERT uniquement) | SOC1. Trigger ou contrainte pour empecher modifications |
| **Cache** | In-memory Python (cachetools / lru_cache) | Pas de Redis. Cache catalogue TTL 5min, cache RBAC TTL 1min. Invalidation au redemarrage |
| **Cache frontend** | React state + refetch sur focus | Donnees catalogue cachees cote client, refresh sur navigation |

**Schema de donnees principal :**

```sql
-- Software Catalog
ACTIONS_CATALOG (
  id, name, description, category, engine, platform,
  parameters_schema CLOB,  -- JSON schema des parametres
  impact_rules CLOB,       -- JSON regles d'impact par environnement
  rbac_policies CLOB,      -- JSON profils autorises
  status, created_by, created_at, updated_at
)

-- Executions
EXECUTIONS (
  id, action_id, user_id, environment,
  parameters CLOB,         -- JSON parametres saisis
  status,                  -- SUBMITTED/RUNNING/SUCCESS/FAILED
  servicenow_change_id,
  started_at, completed_at
)

EXECUTION_STEPS (
  id, execution_id, step_order, step_name,
  status, started_at, completed_at,
  output CLOB,             -- Logs/resultat de l'etape
  platform_job_id
)

-- Audit (append-only)
AUDIT_LOG (
  id, timestamp, user_id, action_type,
  entity_type, entity_id,
  details CLOB,            -- JSON contexte complet
  ip_address
)

-- RBAC
USERS (id, username, display_name, profile, saml_subject)
USER_PERMISSIONS (user_id, action_id, environment, granted_by, granted_at)
```

### Authentication & Security

| Decision | Choix | Justification |
|---|---|---|
| **SSO** | SAML 2.0 (SP-initiated) | Standard entreprise confirme |
| **Librairie SAML** | python3-saml (OneLogin) | Mature, bien maintenue, SP-initiated flow |
| **Session post-SAML** | JWT (access token 30min + refresh token 8h) | Apres auth SAML, le backend emet un JWT. SPA stocke le token en memoire (pas localStorage). Refresh via httpOnly cookie |
| **RBAC** | Middleware FastAPI + decorateurs par route | Le profil SAML (attributs) determine le role. Middleware charge permissions depuis le cache. Filtrage invisible cote API |
| **Vault** | Appel runtime via API REST Vault | Secrets recuperes uniquement au moment de l'execution. Pas de secret en cache, pas en config |
| **API security** | CORS restreint (origin portail uniquement), validation Pydantic, rate limiting in-memory | Pas d'API publique — interne uniquement |
| **TLS** | 1.2+ termine au reverse proxy Nginx | Backend ecoute en HTTP derriere le proxy. TLS gere en infrastructure |
| **Audit securite** | Chaque action mutante logguee dans AUDIT_LOG | Qui, quoi, quand, depuis quelle IP. Immutable |

**Flow d'authentification :**

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

### API & Communication Patterns

| Decision | Choix | Justification |
|---|---|---|
| **Style API** | REST (JSON) | Simple, standard, OpenAPI auto-genere par FastAPI |
| **Versioning** | URL prefix /api/v1/ | Evolutif. V2 possible sans casser V1 |
| **Documentation** | OpenAPI auto (FastAPI /docs) | Swagger UI integre pour dev, Redoc pour documentation formelle |
| **Erreurs** | Format structure uniforme | `{ "error": { "code": "EXEC_FAILED", "message": "...", "details": {...} } }` |
| **WebSocket** | Endpoint /ws/executions/{id} | Une connexion par execution active. Backend pousse les changements d'etape en temps reel |
| **Callbacks** | POST /api/v1/webhooks/{platform}/{execution_id} | Idempotent (ID unique par callback). Authentifie par HMAC |
| **Platform adapters** | Pattern Strategy | Interface commune : trigger(), get_status(), parse_callback(). Implementations : AAPAdapter, GitHubActionsAdapter, AzureDevOpsAdapter, TerraformAdapter |
| **ServiceNow** | Client REST dedie dans services/ | Creation changement, mise a jour statut. Timeout 30s, retry avec backoff |
| **Inventaire** | Client REST dedie, sync on-demand | Appel API inventaire interne pour alimenter les listes deroulantes du wizard |

**Architecture de communication :**

```
[SPA React] <--REST--> [FastAPI REST API] <--SQL--> [Oracle DB]
     ^  WebSocket            | Webhook sortant
     |                       v
     |              [Plateforme d'execution]
     |                       | Callback entrant
     +--- WS push <-- [FastAPI recoit callback → maj DB → push WS]

                    [Vault] <-- appel runtime
                    [ServiceNow] <-- creation changement
                    [Inventaire] <-- donnees formulaires
```

### Frontend Architecture

| Decision | Choix | Justification |
|---|---|---|
| **State management** | React Context + hooks | Auth context, execution context. Pas de Redux |
| **Routing** | React Router 7 declaratif, 4 routes | /catalog, /executions, /dashboard, /admin |
| **Lazy loading** | React.lazy() par page | Chaque page chargee a la demande. Catalogue en eager (premiere vue) |
| **Theme** | Ant Design ConfigProvider + tokens CSS | Palette Desjardins via token override global. Un seul fichier theme.ts |
| **Formulaires dynamiques** | Ant Design Form + schema JSON | Le schema JSON de l'action genere le formulaire du wizard dynamiquement |
| **Composants custom** | 6 composants (spec UX) | ActionCard, ImpactIndicator, ExecutionTimeline, StructuredErrorCard, ExecutionWizard, AdminPreview |
| **API calls** | fetch natif + wrapper type | Un service par domaine (catalogService, executionService, authService) |
| **Types OpenAPI** | Generation automatique (openapi-typescript) | Schema OpenAPI FastAPI genere les types TS. Contrat API garanti |

### Infrastructure & Deployment

| Decision | Choix | Justification |
|---|---|---|
| **CI/CD** | GitHub Actions | Workflows dans .github/workflows/ |
| **Deploiement** | VM directe (pas de Docker) | Contexte bancaire, Docker non disponible |
| **Frontend deploy** | Build statique (vite build) → Nginx sur VM | Fichiers HTML/JS/CSS servis par Nginx |
| **Backend deploy** | Uvicorn derriere Nginx reverse proxy | Nginx termine TLS, proxy vers Uvicorn (port interne) |
| **Process manager** | systemd (Linux VM) | Service systemd pour Uvicorn, restart automatique |
| **Environnements** | DEV → QA → PROD | Variables d'environnement par fichier .env par environnement |
| **Logging** | structlog (Python JSON) → fichiers → Splunk forwarder | Logs structures JSON. Splunk Universal Forwarder collecte les fichiers |
| **Monitoring APM** | Dynatrace OneAgent sur VM | Instrumentation automatique FastAPI via OneAgent |
| **Health checks** | GET /api/v1/health (DB + Vault + ServiceNow) | Verifie connectivite dependances critiques. Utilise par Dynatrace et load balancer |
| **HA** | 2 VMs minimum (active-active) derriere load balancer | SLA 99.9% exige la redondance |
| **Scaling** | Horizontal (ajouter des VMs) | Stateless backend (JWT + DB). Ajouter une VM = ajouter capacite |

**Pipeline CI/CD GitHub Actions :**

```yaml
# .github/workflows/ci.yml
# Declenche sur push/PR vers main
# 1. Lint + Type check (frontend: eslint + tsc, backend: ruff + mypy)
# 2. Tests unitaires (frontend: vitest, backend: pytest)
# 3. Tests accessibilite (axe-core)
# 4. Build frontend (vite build)
# 5. Build backend (package Python)
# 6. Deploy vers environnement cible (SSH + rsync vers VM)
```

### Decision Impact Analysis

**Sequence d'implementation :**

1. Infrastructure VM + Nginx + systemd (prerequis)
2. Schema Oracle + scripts migration V001
3. Backend FastAPI : skeleton + health check + SAML auth
4. Frontend React : skeleton + Ant Design theme + routing + auth flow
5. Catalogue CRUD (API + UI) — premier ecran fonctionnel
6. Execution engine : adapter AAP + wizard + timeline
7. WebSocket temps reel
8. Integrations : Vault, ServiceNow, Inventaire
9. RBAC complet
10. Dashboard + audit + export

**Dependances croisees :**

| Decision | Impacte |
|---|---|
| SAML → JWT | Le flow SAML doit fonctionner avant toute feature. Blocker #1 |
| SQL brut + Repository | Chaque feature backend commence par le repository SQL |
| Platform adapter pattern | Chaque nouvelle plateforme est un adapter isole. Extensible sans modifier le core |
| Structured logging JSON → Splunk | Le format de log doit etre defini des le skeleton backend |
| WebSocket execution | Necessite que le callback et le modele EXECUTION_STEPS soient en place |
| OpenAPI → Types TS | Le contrat API doit etre stable avant de generer les types frontend |

## Implementation Patterns & Consistency Rules

### Naming Patterns

**Base de donnees Oracle :**

| Element | Convention | Exemple |
|---|---|---|
| Tables | UPPER_SNAKE_CASE | `ACTIONS_CATALOG`, `EXECUTION_STEPS`, `AUDIT_LOG` |
| Colonnes | UPPER_SNAKE_CASE | `ACTION_ID`, `CREATED_AT`, `PARAMETERS_SCHEMA` |
| Cles primaires | ID | `ID` (sequence Oracle ou UUID) |
| Cles etrangeres | {TABLE_SINGULIER}_ID | `ACTION_ID`, `USER_ID`, `EXECUTION_ID` |
| Index | IDX_{TABLE}_{COLONNES} | `IDX_EXECUTIONS_STATUS`, `IDX_AUDIT_LOG_TIMESTAMP` |
| Sequences | SEQ_{TABLE} | `SEQ_ACTIONS_CATALOG`, `SEQ_EXECUTIONS` |
| Contraintes | CK_{TABLE}_{RULE} / UK_{TABLE}_{COL} | `CK_EXECUTIONS_STATUS`, `UK_USERS_USERNAME` |

**API REST :**

| Element | Convention | Exemple |
|---|---|---|
| Endpoints | /api/v1/{ressource_pluriel} | `/api/v1/actions`, `/api/v1/executions` |
| Sous-ressources | /{parent}/{id}/{enfant} | `/api/v1/executions/{id}/steps` |
| Parametres query | snake_case | `?action_id=5&page_size=25` |
| JSON fields | snake_case | `{ "action_name": "...", "created_at": "..." }` |
| Headers custom | X-Idp-{Name} | `X-Idp-Request-Id`, `X-Idp-Execution-Id` |

**Python backend :**

| Element | Convention | Exemple |
|---|---|---|
| Fichiers | snake_case.py | `catalog_repository.py`, `aap_adapter.py` |
| Classes | PascalCase | `CatalogRepository`, `AAPAdapter`, `ExecutionService` |
| Fonctions / methodes | snake_case | `get_action_by_id()`, `trigger_execution()` |
| Variables | snake_case | `action_name`, `execution_status` |
| Constantes | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT`, `CACHE_TTL_SECONDS` |
| Pydantic models | PascalCase | `ActionCreate`, `ExecutionResponse`, `UserProfile` |
| Enum values | UPPER_SNAKE_CASE | `Status.RUNNING`, `Impact.HIGH` |

**TypeScript frontend :**

| Element | Convention | Exemple |
|---|---|---|
| Fichiers composants | PascalCase.tsx | `ActionCard.tsx`, `ExecutionTimeline.tsx` |
| Fichiers utilitaires | snake_case.ts ou camelCase.ts | `api_client.ts`, `useWebSocket.ts` |
| Composants React | PascalCase | `ActionCard`, `ExecutionWizard` |
| Hooks | camelCase (use prefix) | `useActions()`, `useWebSocket()`, `useAuth()` |
| Variables locales | camelCase | `const actionList`, `let isLoading` |
| Interfaces API | PascalCase + snake_case fields | `interface ActionResponse { action_name: string; created_at: string; }` |
| Props composants | camelCase | `<ActionCard actionId={5} onSelect={...} />` |
| Constantes | UPPER_SNAKE_CASE | `const MAX_RETRY = 3` |
| CSS classes | kebab-case | `.action-card`, `.impact-indicator--high` |

**Regle frontiere :** Les donnees venant de l'API sont en snake_case. Les props React et variables locales sont en camelCase. La conversion se fait au point d'usage dans le composant, pas dans un layer global.

### Structure Patterns

**Tests :**

| Couche | Localisation | Convention |
|---|---|---|
| Backend unit | `backend/tests/unit/test_{module}.py` | `test_catalog_repository.py` |
| Backend integration | `backend/tests/integration/test_{feature}.py` | `test_saml_auth_flow.py` |
| Frontend unit | Co-localise : `{Component}.test.tsx` | `ActionCard.test.tsx` a cote de `ActionCard.tsx` |
| Frontend integration | `frontend/src/__tests__/` | `catalog_page.test.tsx` |
| E2E (Phase 2) | `e2e/` a la racine | `golden_path.spec.ts` |

**Organisation composants React (par feature) :**

```
src/components/
├── catalog/
│   ├── ActionCard.tsx
│   ├── ActionCard.test.tsx
│   ├── ActionDrawer.tsx
│   ├── CategoryTabs.tsx
│   └── index.ts              # barrel export
├── execution/
│   ├── ExecutionWizard.tsx
│   ├── ExecutionTimeline.tsx
│   ├── StructuredErrorCard.tsx
│   └── index.ts
├── shared/
│   ├── ImpactIndicator.tsx
│   ├── SkeletonCard.tsx
│   └── index.ts
└── admin/
    ├── AdminPreview.tsx
    └── index.ts
```

**Organisation backend Python :**

```
app/
├── api/v1/
│   ├── catalog.py             # Routes catalogue
│   ├── executions.py          # Routes executions
│   ├── auth.py                # Routes SAML/JWT
│   ├── admin.py               # Routes admin
│   ├── webhooks.py            # Callbacks plateformes
│   └── health.py              # Health check
├── repositories/
│   ├── catalog_repository.py
│   ├── execution_repository.py
│   ├── user_repository.py
│   └── audit_repository.py
├── services/
│   ├── execution_service.py
│   ├── vault_service.py
│   ├── servicenow_service.py
│   └── inventory_service.py
├── adapters/
│   ├── base_adapter.py        # Interface abstraite
│   ├── aap_adapter.py
│   ├── github_actions_adapter.py
│   ├── azure_devops_adapter.py
│   └── terraform_adapter.py
├── models/
│   ├── catalog.py             # Pydantic: ActionCreate, ActionResponse...
│   ├── execution.py           # Pydantic: ExecutionCreate, ExecutionStatus...
│   ├── auth.py                # Pydantic: UserProfile, TokenPayload...
│   └── common.py              # Pydantic: ErrorResponse, PaginatedResponse...
├── core/
│   ├── config.py              # Settings (env vars)
│   ├── database.py            # Oracle pool
│   ├── security.py            # JWT, SAML, RBAC middleware
│   └── logging.py             # structlog JSON config
├── websocket/
│   └── execution_ws.py        # WebSocket manager
└── main.py
```

### Format Patterns

**API Response — Succes :**

```json
{
  "data": {
    "id": 42,
    "action_name": "Creer PDB",
    "status": "PUBLISHED",
    "created_at": "2026-01-27T14:30:00Z"
  }
}
```

**API Response — Succes liste paginee :**

```json
{
  "data": [
    { "id": 1, "action_name": "Creer PDB" },
    { "id": 2, "action_name": "Patcher BD" }
  ],
  "pagination": {
    "page": 1,
    "page_size": 25,
    "total_count": 42,
    "total_pages": 2
  }
}
```

**API Response — Erreur :**

```json
{
  "error": {
    "code": "ACTION_NOT_FOUND",
    "message": "L'action demandee n'existe pas.",
    "details": {
      "action_id": 999
    }
  }
}
```

**Codes HTTP :**

| Code | Usage |
|---|---|
| 200 | Succes lecture / mise a jour |
| 201 | Succes creation |
| 204 | Succes suppression (pas de body) |
| 400 | Validation echouee (donnees invalides) |
| 401 | Non authentifie (token absent/expire) |
| 403 | Non autorise (RBAC refuse) |
| 404 | Ressource non trouvee |
| 409 | Conflit (action deja en cours, doublon) |
| 500 | Erreur interne |
| 502 | Erreur plateforme externe (AAP, ServiceNow down) |
| 503 | Service indisponible (maintenance) |

**Dates :** ISO 8601 UTC partout — `2026-01-27T14:30:00Z`. Conversion en timezone locale cote frontend uniquement.

**Nulls :** Champs absents omis du JSON (pas `"field": null`). Le frontend gere l'absence via optional chaining (`data?.field`).

**Booleens :** `true` / `false` en JSON, `1` / `0` en Oracle (NUMBER(1)).

### Communication Patterns

**WebSocket — Messages timeline :**

```json
{
  "type": "step_update",
  "execution_id": "exec-123",
  "data": {
    "step_order": 2,
    "step_name": "Recuperation secrets Vault",
    "status": "COMPLETED",
    "started_at": "2026-01-27T14:30:05Z",
    "completed_at": "2026-01-27T14:30:08Z"
  }
}
```

Types de messages WS : `step_update`, `execution_complete`, `execution_failed`, `connection_ack`.

**Logging structure (structlog JSON → Splunk) :**

```json
{
  "timestamp": "2026-01-27T14:30:05.123Z",
  "level": "info",
  "event": "execution_step_completed",
  "execution_id": "exec-123",
  "step_order": 2,
  "step_name": "vault_secrets",
  "duration_ms": 3012,
  "user_id": "marc.dupont",
  "correlation_id": "req-abc-456"
}
```

**Niveaux de log :**

| Niveau | Usage |
|---|---|
| debug | Detail technique, payload entrant, query SQL |
| info | Action metier reussie (execution lancee, etape terminee, action creee) |
| warning | Situation inhabituelle non bloquante (retry, timeout approche, cache miss) |
| error | Echec recuperable (plateforme down, callback invalide, Vault timeout) |
| critical | Echec irrecuperable (DB down, corruption donnees, securite) |

**Correlation ID :** Chaque requete HTTP recoit un `X-Idp-Request-Id` (UUID). Propage dans tous les logs, appels externes, et WebSocket.

### Process Patterns

**Error handling backend :**

```python
# Exceptions custom hierarchisees
class IdpError(Exception): ...
class NotFoundError(IdpError): ...
class ForbiddenError(IdpError): ...
class PlatformError(IdpError): ...
class VaultError(IdpError): ...
class ServiceNowError(IdpError): ...

# Handler global dans main.py
@app.exception_handler(IdpError)
async def idp_error_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}}
    )
```

**Error handling frontend :**

```typescript
// Wrapper API centralise
async function apiCall<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...options, headers: authHeaders() });
  if (!response.ok) {
    const error = await response.json();
    throw new ApiError(error.error.code, error.error.message, error.error.details);
  }
  return (await response.json()).data;
}
```

**Loading states — Convention React :**

```typescript
const [data, setData] = useState<Action[] | null>(null);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<ApiError | null>(null);
// UI: loading → Skeleton, error → message, data → contenu
```

**Retry — Backend uniquement :**

| Service externe | Retry | Backoff | Max |
|---|---|---|---|
| Plateforme d'execution (webhook) | Oui | Exponentiel (1s, 2s, 4s) | 3 tentatives |
| ServiceNow | Oui | Lineaire (5s) | 2 tentatives |
| Vault | Non | — | Echec immediat (securite) |
| Inventaire | Oui | Exponentiel (1s, 2s) | 2 tentatives |

Pas de retry cote frontend. En cas d'erreur API, afficher le StructuredErrorCard avec options.

### Enforcement Guidelines

**Tous les agents IA et developpeurs DOIVENT :**

1. Utiliser snake_case pour toutes les donnees (JSON, DB columns via Python, interfaces TS API)
2. Wrapper chaque reponse API dans `{ "data": ... }` ou `{ "error": ... }`
3. Logger en JSON structure avec correlation_id sur chaque entree
4. Utiliser les exceptions custom (IdpError hierarchy) — jamais raise Exception() nu
5. Organiser le code par feature (catalog/, execution/, admin/) — pas par type
6. Co-localiser les tests frontend (Component.test.tsx a cote de Component.tsx)
7. Separer les tests backend en unit/ et integration/
8. Utiliser ISO 8601 UTC pour toutes les dates dans l'API
9. Propager le correlation_id dans tous les appels externes
10. Documenter chaque route API avec les docstrings FastAPI (auto-OpenAPI)

**Anti-patterns interdits :**

| Anti-pattern | Correction |
|---|---|
| `raise Exception("something failed")` | `raise PlatformError(code="AAP_TIMEOUT", message="...")` |
| `console.log("debug")` dans le frontend | Supprimer ou utiliser un logger conditionnel |
| `return {"name": "..."}` sans wrapper | `return {"data": {"name": "..."}}` |
| Dates en format local dans l'API | ISO 8601 UTC : `2026-01-27T14:30:00Z` |
| `catch (e) {}` silencieux | Logger + afficher l'erreur a l'utilisateur |
| Tests dans un dossier separe (frontend) | Co-localises avec le composant |
| camelCase dans le JSON API | snake_case partout |
| Secret en variable d'environnement | Vault runtime uniquement |

## Project Structure & Boundaries

### Complete Project Directory Structure

```
idp-portal/
├── .github/
│   └── workflows/
│       ├── ci.yml                         # Lint + tests + build
│       └── deploy.yml                     # Deploy SSH+rsync vers VM
├── .env.example                           # Template variables d'environnement
├── .gitignore
├── README.md
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── public/
│   │   └── favicon.svg
│   ├── src/
│   │   ├── main.tsx                       # Point d'entree React
│   │   ├── App.tsx                        # Routes + Layout + AuthProvider
│   │   ├── vite-env.d.ts
│   │   ├── theme/
│   │   │   └── desjardins.ts             # Ant Design theme tokens
│   │   ├── types/
│   │   │   ├── api.ts                     # Types generes depuis OpenAPI
│   │   │   └── common.ts                 # Types partages (enums, utilitaires)
│   │   ├── services/
│   │   │   ├── api_client.ts             # Wrapper fetch + auth + errors
│   │   │   ├── catalog_service.ts        # GET /actions, GET /actions/{id}
│   │   │   ├── execution_service.ts      # POST /executions, GET /executions
│   │   │   ├── auth_service.ts           # Login SAML, refresh, logout
│   │   │   ├── admin_service.ts          # CRUD actions (admin)
│   │   │   └── websocket_service.ts      # Connexion WS + reconnect
│   │   ├── hooks/
│   │   │   ├── useAuth.ts                # AuthContext consumer
│   │   │   ├── useActions.ts             # Fetch + cache actions catalogue
│   │   │   ├── useExecution.ts           # Fetch execution + status
│   │   │   └── useWebSocket.ts           # WS connexion + messages timeline
│   │   ├── contexts/
│   │   │   ├── AuthContext.tsx            # User profile, token, permissions
│   │   │   └── ExecutionContext.tsx       # Execution active (timeline)
│   │   ├── pages/
│   │   │   ├── CatalogPage.tsx           # Catalogue + filtres + search
│   │   │   ├── ExecutionsPage.tsx         # Historique executions (table)
│   │   │   ├── DashboardPage.tsx         # Stats + recentes
│   │   │   ├── AdminPage.tsx             # Gestion actions (CRUD + preview)
│   │   │   └── NotFoundPage.tsx          # 404
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── AppLayout.tsx         # Top bar + navigation + contenu
│   │   │   │   ├── TopNav.tsx            # 4 onglets + profil + notifications
│   │   │   │   └── index.ts
│   │   │   ├── catalog/
│   │   │   │   ├── ActionCard.tsx
│   │   │   │   ├── ActionCard.test.tsx
│   │   │   │   ├── ActionDrawer.tsx
│   │   │   │   ├── ActionDrawer.test.tsx
│   │   │   │   ├── CategoryTabs.tsx
│   │   │   │   ├── CatalogFilters.tsx
│   │   │   │   ├── CatalogSearch.tsx
│   │   │   │   └── index.ts
│   │   │   ├── execution/
│   │   │   │   ├── ExecutionWizard.tsx
│   │   │   │   ├── ExecutionWizard.test.tsx
│   │   │   │   ├── WizardStepEnv.tsx
│   │   │   │   ├── WizardStepParams.tsx
│   │   │   │   ├── WizardStepConfirm.tsx
│   │   │   │   ├── ExecutionTimeline.tsx
│   │   │   │   ├── ExecutionTimeline.test.tsx
│   │   │   │   ├── TimelineNode.tsx
│   │   │   │   ├── StructuredErrorCard.tsx
│   │   │   │   ├── StructuredErrorCard.test.tsx
│   │   │   │   └── index.ts
│   │   │   ├── shared/
│   │   │   │   ├── ImpactIndicator.tsx
│   │   │   │   ├── ImpactIndicator.test.tsx
│   │   │   │   ├── SkeletonCard.tsx
│   │   │   │   ├── EmptyState.tsx
│   │   │   │   └── index.ts
│   │   │   ├── admin/
│   │   │   │   ├── ActionForm.tsx
│   │   │   │   ├── AdminPreview.tsx
│   │   │   │   ├── AdminPreview.test.tsx
│   │   │   │   └── index.ts
│   │   │   └── dashboard/
│   │   │       ├── StatCard.tsx
│   │   │       ├── RecentExecutions.tsx
│   │   │       └── index.ts
│   │   └── __tests__/
│   │       └── catalog_page.test.tsx
│   └── .eslintrc.cjs
│
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                        # FastAPI app + handlers + middleware
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py                    # Dependencies injectees (DB pool, current_user)
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── catalog.py             # FR1-FR12
│   │   │       ├── executions.py          # FR13-FR23
│   │   │       ├── auth.py                # FR24-FR29
│   │   │       ├── admin.py               # FR1-FR7 (admin)
│   │   │       ├── webhooks.py            # Callbacks plateformes
│   │   │       ├── audit.py               # FR30-FR35
│   │   │       ├── dashboard.py           # FR39-FR41
│   │   │       └── health.py              # Health check
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── catalog.py                 # ActionCreate, ActionResponse, ActionDetail
│   │   │   ├── execution.py               # ExecutionCreate, ExecutionResponse, StepUpdate
│   │   │   ├── auth.py                    # UserProfile, TokenPayload, SAMLAssertion
│   │   │   ├── audit.py                   # AuditEntry, AuditExportRequest
│   │   │   └── common.py                  # ErrorResponse, PaginatedResponse, HealthStatus
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── catalog_repository.py      # SQL brut: actions CRUD, recherche, filtrage
│   │   │   ├── execution_repository.py    # SQL brut: executions + steps
│   │   │   ├── user_repository.py         # SQL brut: users + permissions RBAC
│   │   │   └── audit_repository.py        # SQL brut: append-only audit log + export
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── execution_service.py       # Orchestration: validate → SN → Vault → trigger
│   │   │   ├── vault_service.py           # Client REST Vault
│   │   │   ├── servicenow_service.py      # Client REST ServiceNow
│   │   │   ├── inventory_service.py       # Client REST inventaire interne
│   │   │   └── rbac_service.py            # Evaluation permissions (cache in-memory)
│   │   ├── adapters/
│   │   │   ├── __init__.py
│   │   │   ├── base_adapter.py            # ABC: trigger(), get_status(), parse_callback()
│   │   │   ├── aap_adapter.py             # Ansible Automation Platform
│   │   │   ├── github_actions_adapter.py  # GitHub Actions
│   │   │   ├── azure_devops_adapter.py    # Azure DevOps
│   │   │   └── terraform_adapter.py       # Terraform
│   │   ├── websocket/
│   │   │   ├── __init__.py
│   │   │   └── execution_ws.py            # WS manager: connexions + push
│   │   └── core/
│   │       ├── __init__.py
│   │       ├── config.py                  # Settings (pydantic-settings, env vars)
│   │       ├── database.py                # Oracle pool: create_pool, get_connection
│   │       ├── security.py                # SAML SP, JWT, RBAC middleware
│   │       ├── logging.py                 # structlog JSON config → Splunk
│   │       ├── exceptions.py              # IdpError hierarchy
│   │       └── middleware.py              # Correlation ID, request logging, CORS
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                    # Fixtures: DB mock, auth mock, test client
│       ├── unit/
│       │   ├── test_catalog_repository.py
│       │   ├── test_execution_service.py
│       │   ├── test_rbac_service.py
│       │   ├── test_aap_adapter.py
│       │   └── test_vault_service.py
│       └── integration/
│           ├── test_saml_auth_flow.py
│           ├── test_execution_flow.py
│           └── test_webhook_callback.py
│
├── database/
│   ├── migrations/
│   │   ├── V001_create_users.sql
│   │   ├── V002_create_actions_catalog.sql
│   │   ├── V003_create_executions.sql
│   │   ├── V004_create_audit_log.sql
│   │   └── V005_create_user_permissions.sql
│   └── seed/
│       └── V001_seed_initial_actions.sql  # 3 actions POC
│
├── nginx/
│   ├── idp-portal.conf                    # Config Nginx: TLS, proxy, static
│   └── idp-portal.service                 # systemd unit file
│
└── scripts/
    ├── deploy.sh                          # Deploy VM (rsync + restart)
    ├── run_migrations.sh                  # Execute scripts SQL sequentiellement
    └── generate_types.sh                  # Genere types TS depuis OpenAPI
```

### Architectural Boundaries

**API Boundaries (contrat frontend <-> backend) :**

| Frontiere | Point de contact | Regle |
|---|---|---|
| Frontend → Backend | `services/*_service.ts` → `/api/v1/*` | Toute communication passe par les services TS. Jamais de fetch dans un composant |
| Backend → Frontend | WebSocket `/ws/executions/{id}` | Push uniquement. Le frontend ne pousse pas via WS |
| Backend → Plateformes | `adapters/*_adapter.py` → Webhook sortant | Chaque plateforme isolee dans son adapter |
| Plateformes → Backend | POST `/api/v1/webhooks/{platform}/{id}` | Callbacks authentifies par HMAC. Idempotents |
| Backend → Vault | `vault_service.py` → API REST Vault | Runtime uniquement. Aucun secret cache |
| Backend → ServiceNow | `servicenow_service.py` → API REST SN | Creation changement + mise a jour statut |
| Backend → Inventaire | `inventory_service.py` → API REST interne | Donnees formulaires on-demand |

**Data Boundaries :**

| Couche | Acces | Regle |
|---|---|---|
| API routes (`api/v1/*.py`) | Appelle les services | Jamais de SQL dans les routes |
| Services (`services/*.py`) | Appelle repositories + adapters | Logique metier. Pas de SQL direct |
| Repositories (`repositories/*.py`) | SQL brut via oracledb | Seul point d'acces a Oracle |
| Adapters (`adapters/*.py`) | HTTP vers plateformes externes | Isole chaque plateforme |

**Component Boundaries (frontend) :**

| Couche | Responsabilite | Regle |
|---|---|---|
| Pages (`pages/*.tsx`) | Layout, orchestration composants | Appelle hooks, passe donnees aux composants |
| Composants (`components/**/*.tsx`) | Rendu UI pur | Props in, events out. Pas de fetch |
| Hooks (`hooks/*.ts`) | Data-fetching + state | Appelle services, gere loading/error/data |
| Services (`services/*.ts`) | Appels API types | Wrapper fetch. Pas de logique metier |
| Contexts (`contexts/*.tsx`) | State global | Auth, execution active. Via hooks uniquement |

### Requirements to Structure Mapping

| Domaine FR | Backend | Frontend | DB |
|---|---|---|---|
| **FR1-FR7 Catalog** | `api/v1/catalog.py` + `api/v1/admin.py` + `repositories/catalog_repository.py` | `pages/CatalogPage` + `pages/AdminPage` + `components/catalog/*` + `components/admin/*` | `V002_create_actions_catalog.sql` |
| **FR8-FR12 Decouverte** | `api/v1/catalog.py` (search, filter) | `CatalogSearch` + `CatalogFilters` + `CategoryTabs` | Index sur ACTIONS_CATALOG |
| **FR13-FR18 Execution** | `api/v1/executions.py` + `services/execution_service.py` + `adapters/*` | `ExecutionWizard` + `WizardStep*` | `V003_create_executions.sql` |
| **FR19-FR23 Suivi** | `websocket/execution_ws.py` + `api/v1/webhooks.py` | `ExecutionTimeline` + `TimelineNode` | EXECUTION_STEPS |
| **FR24-FR29 RBAC** | `core/security.py` + `services/rbac_service.py` + `repositories/user_repository.py` | `AuthContext` + `useAuth` | `V001` + `V005` |
| **FR30-FR35 Audit** | `api/v1/audit.py` + `repositories/audit_repository.py` | `ExecutionsPage` (table + export) | `V004_create_audit_log.sql` |
| **FR36-FR38 Autoremediation** | `services/execution_service.py` | `StructuredErrorCard` | EXECUTIONS |
| **FR39-FR41 Analytics** | `api/v1/dashboard.py` | `DashboardPage` + `components/dashboard/*` | Vues Oracle |
| **FR42-FR43 Inventaire** | `services/inventory_service.py` | `WizardStepParams` (listes dynamiques) | On-demand |
| **FR44-FR45 Comm & IA** | Phase 3 | Phase 3 | Phase 3 |

### Data Flow

```
[Utilisateur] → [React SPA]
                     |
                     ├── GET /api/v1/actions (catalogue)
                     ├── POST /api/v1/executions (lancer)
                     └── WS /ws/executions/{id} (suivre)
                          |
                     [FastAPI]
                          |
                ┌─────────┼──────────┬──────────┐
                |         |          |          |
           [Oracle]  [Vault]   [ServiceNow]  [Inventaire]
                |
                |    POST webhook sortant
                |         |
                |    [Plateforme AAP/GH/Azure/TF]
                |         |
                |    POST callback entrant
                |         |
                └─── maj EXECUTION_STEPS
                          |
                     push WS → [React Timeline]
```

### Development Workflow

**Dev local :**
- Frontend : `cd frontend && npm run dev` → Vite dev server (port 5173)
- Backend : `cd backend && fastapi dev app/main.py` → Uvicorn (port 8000)
- Vite proxy `/api` et `/ws` vers le backend (config vite.config.ts)

**Build :**
- Frontend : `npm run build` → `frontend/dist/` (fichiers statiques)
- Backend : package Python standard

**Deploy VM :**
- `scripts/deploy.sh` : rsync frontend/dist → Nginx static, rsync backend → app dir, restart systemd

## Architecture Validation Results

### Coherence Validation

**Compatibilite des technologies :**

| Combinaison | Statut |
|---|---|
| React 19 + Ant Design 6.2 | OK — Ant Design 6 supporte React 18+/19 |
| Vite 7 + React 19 + TypeScript | OK — template react-ts officiel |
| FastAPI + python-oracledb 3.4.1 | OK — async, Python 3.12+ |
| python3-saml + python-jose (JWT) + FastAPI | OK — SAML auth initiale, JWT session SPA |
| React Router 7 + React 19 | OK — support natif |
| WebSocket FastAPI natif + React hook | OK — pas de librairie tierce |
| structlog JSON + Splunk Forwarder | OK — JSON standard |
| Dynatrace OneAgent + FastAPI sur VM | OK — instrumentation automatique Python ASGI |

Aucune incompatibilite detectee.

**Coherence des patterns :**

| Pattern | Statut |
|---|---|
| snake_case API <-> snake_case TypeScript interfaces | OK — pas de conversion |
| UPPER_SNAKE Oracle <-> snake_case Python | OK — mapping dans repositories |
| Repository Pattern <-> SQL brut | OK — encapsulation testable |
| Adapter Pattern <-> 4 plateformes | OK — interface commune isolee |
| JWT session <-> WebSocket auth | OK — token passe a la connexion WS |
| Error hierarchy <-> API error format | OK — handler global uniforme |

### Requirements Coverage

**Exigences fonctionnelles : 43/45 couvertes, 2 differees Phase 3**

| FR | Domaine | Statut |
|---|---|---|
| FR1-FR7 | Software Catalog | OK |
| FR8-FR12 | Decouverte & Navigation | OK |
| FR13-FR18 | Execution d'Actions | OK |
| FR19-FR23 | Suivi d'Execution | OK |
| FR24-FR29 | Controle d'Acces | OK |
| FR30-FR35 | Audit & Conformite | OK |
| FR36-FR38 | Autoremediation | OK |
| FR39-FR41 | Analytics | OK |
| FR42-FR43 | Inventaire | OK |
| FR44-FR45 | Communication & IA | DIFFERE Phase 3 |

**Exigences non-fonctionnelles : 25/25 couvertes**

| NFR | Domaine | Solution | Statut |
|---|---|---|---|
| NFR1-5 | Performance | Vite build, FastAPI async, Oracle pool, cache in-memory, WS push | OK |
| NFR6-11 | Securite | TLS Nginx, SAML+JWT, Vault runtime, RBAC middleware, audit append-only | OK |
| NFR12-16 | Fiabilite | HA 2 VMs, circuit breaker (adapter), idempotence callbacks, systemd restart | OK |
| NFR17-21 | Integration | Adapter pattern, retry backoff, SN 30s tolerance, Vault fail-fast | OK |
| NFR22-25 | Scalabilite | Stateless backend, horizontal scaling, adapter plugin, schema extensible | OK |

### Implementation Readiness

| Critere | Evaluation | Statut |
|---|---|---|
| Decisions critiques documentees avec versions | 15+ technologies verifiees (jan 2026) | OK |
| Patterns d'implementation complets | Naming, structure, format, communication, process | OK |
| Regles de coherence claires | 10 regles obligatoires + anti-patterns | OK |
| Exemples concrets | JSON, Python, TypeScript, SQL | OK |
| Structure projet complete | ~80 fichiers/dossiers nommes | OK |
| Frontieres architecturales | API, donnees, composants, services | OK |
| Mapping FR → fichiers | 10 domaines FR mappes | OK |
| Data flow documente | Diagramme complet | OK |

### Gap Analysis

**Gaps critiques : aucun.**

**Gaps importants (non bloquants) :**

| Gap | Impact | Recommandation |
|---|---|---|
| Config pool Oracle (min/max) | Performance sous charge | Valeurs par defaut dans config.py (min=2, max=10) |
| Reconnexion WS sur failover HA | Execution active si VM tombe | Client reconnecte automatiquement, state en DB pas en memoire WS |
| Backup DB | Resilience donnees | Infrastructure Oracle DBA — hors perimetre application |

**Gaps nice-to-have :**

| Gap | Recommandation |
|---|---|
| Guide onboarding developpeur | Creer a la premiere story d'infrastructure |
| Workflow generation types OpenAPI → TS | Documenter dans README |
| Storybook composants custom | Envisageable Phase 2 |

### Architecture Completeness Checklist

- [x] Contexte projet analyse (45 FR, 25 NFR, 5 profils, 8 integrations)
- [x] Stack technique selectionnee et versions verifiees (janvier 2026)
- [x] Decisions architecturales documentees (data, auth, API, frontend, infra)
- [x] Patterns d'implementation definis (naming, structure, format, communication, process)
- [x] Structure projet complete (~80 fichiers nommes)
- [x] Frontieres architecturales etablies (API, donnees, composants, services)
- [x] Mapping exigences → structure
- [x] Data flow documente
- [x] Sequence d'implementation definie (10 etapes)
- [x] Dependances croisees identifiees

### Architecture Readiness Assessment

**Statut global : PRET POUR L'IMPLEMENTATION**

**Niveau de confiance : Eleve**

**Forces :**
- Event-driven facade avec zero credential — securite bancaire native
- Adapter pattern pour 4 plateformes — extensible sans toucher le core
- Stack moderne pragmatique — React + FastAPI + Oracle, technologies eprouvees
- Patterns clairs pour agents IA — snake_case, structure par feature, error hierarchy
- Couverture complete 43/45 FR et 25/25 NFR
- Separation nette frontend/backend avec contrat OpenAPI

**Points d'attention implementation :**
- SAML est le premier blocker — valider que l'IdP est disponible en DEV
- Pool Oracle a configurer correctement des le skeleton
- Connectivite reseau vers les API des plateformes a valider tot

### Implementation Handoff

**Tous les agents IA DOIVENT :**
1. Suivre toutes les decisions architecturales exactement comme documentees
2. Utiliser les patterns d'implementation de maniere coherente
3. Respecter la structure projet et les frontieres
4. Consulter ce document pour toute question architecturale

**Premiere priorite d'implementation :**
1. Initialiser le monorepo (frontend Vite + backend FastAPI)
2. Scripts migration Oracle V001-V005
3. Skeleton backend : health check + pool Oracle + structlog
4. Skeleton frontend : Ant Design theme Desjardins + routing + layout
