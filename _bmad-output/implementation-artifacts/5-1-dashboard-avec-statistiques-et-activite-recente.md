# Story 5.1: Dashboard avec statistiques et activite recente

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBA,
I want consulter un tableau de bord synthetique avec les chiffres cles et l'activite recente,
So that j'ai une vue d'ensemble immediate de ce qui se passe sur la plateforme.

## Acceptance Criteria

1. **StatCards (AC1)** — Given un DBA accede a l'onglet Dashboard, When la page se charge, Then des StatCards affichent : executions du jour, taux de succes (%), executions en cours, executions en erreur.

2. **Activite recente (AC2)** — Given le dashboard est charge, When le DBA regarde la section activite recente, Then une table affiche les 10 dernieres executions (tous utilisateurs visibles pour DBA) : action, utilisateur, environnement, statut, date.

3. **Detail execution (AC3)** — Given le DBA clique sur une execution dans la table, When le detail s'ouvre, Then la timeline complete s'affiche (reutilisation ExecutionTimeline en mode historique).

4. **APIs** — L'API GET /api/v1/dashboard/stats retourne les statistiques agregees ; l'API GET /api/v1/dashboard/recent retourne les executions recentes.

5. **Layout** — Le layout dashboard est en 2 colonnes sur desktop standard, 3 colonnes sur large.

6. **Loading** — Le chargement affiche des skeleton cards et skeleton rows.

## Tasks / Subtasks

- [x] Task 1: Backend — Endpoints dashboard (AC: #4)
  - [x] 1.1 Creer `app/api/v1/dashboard.py` avec router FastAPI
  - [x] 1.2 Ajouter methodes `get_dashboard_stats()` et `list_recent_executions()` dans `execution_repository.py`
  - [x] 1.3 GET /api/v1/dashboard/stats : executions_jour, taux_succes_pct, executions_en_cours, executions_en_erreur
  - [x] 1.4 GET /api/v1/dashboard/recent : 10 dernieres executions, tous utilisateurs (DBA/DBOPS), avec action_name et user display
  - [x] 1.5 Enregistrer router dashboard dans `main.py`
- [x] Task 2: Frontend — Service et types (AC: #4)
  - [x] 2.1 Creer `dashboard_service.ts` : fetchStats(), fetchRecent()
  - [x] 2.2 Ajouter types DashboardStats, DashboardRecentExecution dans `api.ts` si besoin
- [x] Task 3: Frontend — Composants dashboard (AC: #1, #5, #6)
  - [x] 3.1 Creer `StatCard.tsx` : label, value, icone optionnelle ; variants pour succes/erreur/en-cours
  - [x] 3.2 Creer `RecentExecutions.tsx` : table 10 lignes, colonnes action, utilisateur, environnement, statut, date
  - [x] 3.3 Skeleton loading : SkeletonCard pour StatCards, Skeleton rows pour table
  - [x] 3.4 Layout : Row/Col Ant Design, 2 cols desktop (breakpoint md), 3 cols large (xl)
- [x] Task 4: Frontend — Page Dashboard et drawer (AC: #2, #3)
  - [x] 4.1 Remplir `DashboardPage.tsx` : StatCards + RecentExecutions, appels dashboard_service
  - [x] 4.2 Drawer au clic sur ligne : reutiliser ExecutionTimeline en mode historique (comme ExecutionsPage)
  - [x] 4.3 Appeler getExecution + getExecutionSteps pour alimenter le drawer
- [x] Task 5: Tests (AC: tous)
  - [x] 5.1 Backend : `test_dashboard_api.py` — stats et recent (200, structure)
  - [x] 5.2 Frontend : `StatCard.test.tsx`, `RecentExecutions.test.tsx` ou `DashboardPage.test.tsx`

## Dev Notes

### Contexte technique
- **Epic 5** couvre FR41 : tableau de bord activite recente. Story 5.2 (WebSocket temps reel + badge) est separee.
- **Reutiliser** : ExecutionTimeline, execution_service (getExecution, getExecutionSteps), patterns ExecutionsPage (drawer + table).
- **Dashboard actuel** : `DashboardPage.tsx` est un stub (titre seul). Dossier `components/dashboard/` existe avec .gitkeep.

### Backend
- **Execution repository** : `list_by_user()` existe ; ajouter `get_dashboard_stats()` et `list_recent_executions(limit=10)` sans filtre user pour DBA.
- **RBAC** : Endpoints dashboard accessibles aux profils DBA et DBOPS. Utiliser `get_current_user` ; pas de controle action/env ici.
- **Stats a calculer** :
  - `executions_jour` : COUNT WHERE TRUNC(CREATED_AT) = TRUNC(SYSDATE)
  - `taux_succes_pct` : (COMPLETED / (COMPLETED + FAILED)) * 100 sur periode (ex. 24h ou 7j)
  - `executions_en_cours` : COUNT WHERE STATUS IN ('SUBMITTED','RUNNING','PENDING_APPROVAL')
  - `executions_en_erreur` : COUNT WHERE STATUS = 'FAILED' sur periode recente (ex. 24h)
- **Oracle** : TRUNC(date) pour jour, SYSDATE pour now. Grouper requetes ou une seule avec sous-requetes selon perf.

### Frontend
- **UX Spec** [Source: ux-design-specification.md] : StatCards, layout 2 cols desktop / 3 large, skeleton cards et rows.
- **Architecture** [Source: architecture.md] : `components/dashboard/StatCard.tsx`, `RecentExecutions.tsx` ; `api/v1/dashboard.py`.
- **Ant Design** : Row, Col (span), Card, Table, Drawer, Skeleton. Pas de librairie charts pour cette story.
- **ExecutionsPage** : colonnes action, environment, status, date, duration ; drawer avec ExecutionTimeline. Adapter colonnes (ajouter user) et limiter a 10.

### Project Structure Notes
- Backend : `app/api/v1/dashboard.py` (nouveau) ; `app/repositories/execution_repository.py` (ajout methodes).
- Frontend : `pages/DashboardPage.tsx` (remplir) ; `components/dashboard/StatCard.tsx`, `RecentExecutions.tsx` ; `services/dashboard_service.ts`.

## Dev Agent Record

### Agent Model Used
claude-opus-4-5-20251101

### Debug Log References
- Backend tests: 12/12 passed (test_dashboard_api.py, incl. RBAC 403 tests)
- Frontend tests: 30/30 passed (StatCard.test.tsx, RecentExecutions.test.tsx, DashboardPage.test.tsx)

### Completion Notes List
- **Task 1:** Backend endpoints implemented - GET /api/v1/dashboard/stats and GET /api/v1/dashboard/recent
- **Task 2:** Frontend service (dashboard_service.ts) and types (DashboardStats, DashboardRecentExecution) created
- **Task 3:** StatCard and RecentExecutions components with skeleton loading and responsive layout
- **Task 4:** DashboardPage with StatCards, recent table, and drawer with ExecutionTimeline (historical mode)
- **Task 5:** Full test coverage for backend API and frontend components
- **Code review 2026-01-30:** Fixes applied — AC5 layout (2 cols md / 3 cols xl), RBAC DBA/DBOPS only (403 for other profiles), Pydantic response models for OpenAPI, Alert/Drawer Ant Design 6 deprecations (title, rootStyle), created_at type string | null, skeleton 10 rows, tests for 403 non-DBA profile

### File List
- idp-portal/backend/app/api/v1/dashboard.py (new)
- idp-portal/backend/app/repositories/execution_repository.py (modified: +get_dashboard_stats, +list_recent_executions)
- idp-portal/backend/app/main.py (modified: +dashboard router)
- idp-portal/backend/tests/unit/test_dashboard_api.py (new)
- idp-portal/frontend/src/types/api.ts (modified: +DashboardStats, +DashboardRecentExecution)
- idp-portal/frontend/src/services/dashboard_service.ts (new)
- idp-portal/frontend/src/components/dashboard/StatCard.tsx (new)
- idp-portal/frontend/src/components/dashboard/StatCard.test.tsx (new)
- idp-portal/frontend/src/components/dashboard/RecentExecutions.tsx (new)
- idp-portal/frontend/src/components/dashboard/RecentExecutions.test.tsx (new)
- idp-portal/frontend/src/components/dashboard/index.ts (new)
- idp-portal/frontend/src/pages/DashboardPage.tsx (replaced)
- idp-portal/frontend/src/pages/DashboardPage.test.tsx (new)
