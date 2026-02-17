# Story 5.2 : Statuts temps réel et notifications sur le dashboard

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBA,
I want voir les exécutions en cours se mettre à jour en temps réel sur le dashboard,
so that je suis alerté immédiatement si une exécution requiert mon attention.

## Acceptance Criteria

1. **Mise à jour temps réel (AC1)** — Given le DBA est sur le dashboard, When une exécution en cours change de statut, Then la table d'activité récente se met à jour via WebSocket sans refresh.

2. **Badge onglet Dashboard (AC2)** — Given une exécution est en erreur, When le DBA n'est pas sur le dashboard, Then un badge point rouge apparaît sur l'onglet Dashboard dans la top bar.

3. **Consultation et mise en évidence (AC3)** — Given le DBA revient sur le dashboard, When il voit le badge, Then le badge disparaît après consultation et les exécutions en erreur sont mises en évidence (ligne rouge subtile).

4. **WebSocket /ws/dashboard (AC4)** — Le WebSocket /ws/dashboard émet les mises à jour d'exécutions pertinentes pour l'utilisateur (ex. les 10 dernières ou celles en cours).

5. **Accessibilité (AC5)** — aria-live="polite" annonce les changements de statut pour les lecteurs d'écran.

6. **FR41** — FR41 (tableau de bord activité récente et statuts d'exécution) est satisfaite.

## Tasks / Subtasks

- [x] Task 1: Backend — WebSocket dashboard (AC: #1, #4)
  - [x] 1.1 Créer un manager ou étendre l'existant pour canal /ws/dashboard : connexions par user_id (pas par execution_id).
  - [x] 1.2 Endpoint GET /ws/dashboard : accept connexion authentifiée (token query), enregistrer client pour user.
  - [x] 1.3 Lors d'un callback ou mise à jour d'exécution (step_update, execution_complete, execution_failed), si l'exécution fait partie des "récentes" (même critère que GET /api/v1/dashboard/recent), broadcaster aux clients connectés sur /ws/dashboard.
  - [x] 1.4 Format message : type execution_update avec execution_id, status, step_summary optionnel ; cohérent avec /ws/executions/{id}.
- [x] Task 2: Frontend — Hook et service WebSocket dashboard (AC: #1)
  - [x] 2.1 Créer useDashboardWebSocket() ou étendre useWebSocket : connexion à /ws/dashboard (sans execution_id), réception execution_update.
  - [x] 2.2 Sur message execution_update : mettre à jour la liste "récentes" (remplacer ou insérer ligne, tri par date).
  - [x] 2.3 DashboardPage : utiliser le hook quand la page est montée ; passer les mises à jour à RecentExecutions (state ou refetch léger).
- [x] Task 3: Frontend — Badge et mise en évidence (AC: #2, #3)
  - [x] 3.1 TopNav / AppLayout : afficher Badge (Ant Design) sur le lien/onglet Dashboard si au moins une exécution en erreur non "vue" (état local ou API count).
  - [x] 3.2 Persistance "erreurs vues" : au passage sur Dashboard, marquer les erreurs comme vues (localStorage ou endpoint PUT /api/v1/dashboard/seen-errors ou cookie).
  - [x] 3.3 RecentExecutions : ligne avec status FAILED avec style mise en évidence (ligne rouge subtile / Row className ou status render).
- [x] Task 4: Accessibilité (AC: #5)
  - [x] 4.1 Région aria-live="polite" autour de la table ou message annonçant "Exécution X mise à jour : statut Y".
- [x] Task 5: Tests (AC: tous)
  - [x] 5.1 Backend : tests unitaires /ws/dashboard (connexion, auth, broadcast simulé).
  - [x] 5.2 Frontend : tests useDashboardWebSocket et comportement badge / mise en évidence (mock WS).

## Dev Notes

### Contexte technique
- **Epic 5** : Dashboard & Activité (FR41). Story 5.1 a livré StatCards, table récente, drawer avec ExecutionTimeline. Story 5.2 ajoute temps réel sur cette table + badge erreurs + accessibilité.
- **Réutiliser** : ExecutionWebSocketManager (execution_ws.py) pour le pattern broadcast ; soit nouveau manager "DashboardWS" soit étendre pour canal dashboard. Réutiliser useWebSocket pattern (auth token, reconnect) pour /ws/dashboard.
- **Ne pas dupliquer** : /ws/executions/{id} reste pour la timeline détaillée d'une exécution. /ws/dashboard est un canal global "récentes" pour la page Dashboard.

### Backend
- **Où broadcaster** : Dans execution_service ou webhook handler, après mise à jour EXECUTION_STEPS / status execution : appeler un "dashboard_ws_manager.broadcast_execution_update(execution_id, status, ...)" qui envoie à tous les clients connectés sur /ws/dashboard (filtrer par pertinence si besoin : ex. 10 dernières exécutions).
- **Pertinence** : Même périmètre que list_recent_executions(limit=10) — pas de filtre user pour DBA (tous utilisateurs). Donc toute exécution qui apparaît ou pourrait apparaître dans "recent" doit déclencher un push aux clients dashboard.
- **Auth** : Même schéma que /ws/executions/{id} — token en query, verify_token, get_current_user. RBAC : seuls DBA/DBOPS (ou profils autorisés dashboard) peuvent se connecter à /ws/dashboard.

### Frontend
- **TopNav** : Le lien vers /dashboard doit afficher <Badge count={unseenErrorCount} /> quand unseenErrorCount > 0. Source : état dérivé (ex. exécutions FAILED dont "last_seen_at" < updated_at) ou endpoint GET /api/v1/dashboard/unseen-errors-count (optionnel).
- **Badge disparaît** : À l'entrée sur DashboardPage (useEffect on mount), appeler "mark errors as seen" (localStorage key par user ou API) et rafraîchir count.
- **Ant Design** : Badge, aria-live. Table : render status avec Tag color="error" pour FAILED ; Row avec className ou style pour ligne rouge subtile.

### Project Structure Notes
- Backend : `app/websocket/` — soit nouveau `dashboard_ws.py` soit étendre `execution_ws.py` avec canal dashboard. `app/api/websocket_routes.py` — ajouter route WebSocket `/dashboard`.
- Frontend : `hooks/useDashboardWebSocket.ts` (ou `useWebSocketDashboard.ts`), `pages/DashboardPage.tsx` (intégrer hook), `components/layout/TopNav.tsx` ou équivalent (Badge). État "unseen errors" : contexte optionnel ou state + localStorage.

### Architecture Compliance
- [Source: architecture.md] WebSocket : endpoint /ws/executions/{id} existant ; ajouter /ws/dashboard avec même pattern (auth, accept, disconnect). Messages : type execution_update, payload snake_case, execution_id, status.
- [Source: architecture.md] Frontend : hooks use* pour data ; services pour API. Pas de fetch dans composants.
- [Source: architecture.md] NFR3 : mise à jour statut temps réel sous 5 s après callback — le broadcast dashboard doit être déclenché dès réception callback.

### Référence story précédente (5.1)
- Fichiers créés : `dashboard.py`, `StatCard.tsx`, `RecentExecutions.tsx`, `DashboardPage.tsx`, `dashboard_service.ts`, `useWebSocket.ts` (pour /ws/executions/{id}).
- Tests : test_dashboard_api.py, StatCard.test.tsx, RecentExecutions.test.tsx, DashboardPage.test.tsx.
- Réutiliser dashboard_service.fetchRecent() pour données initiales ; le hook temps réel met à jour la liste sans refetch complet si souhaité (ou refetch après message pour simplicité).

### Références
- [Source: _bmad-output/planning-artifacts/epics.md] Epic 5, Story 5.2 — AC détaillées
- [Source: _bmad-output/planning-artifacts/architecture.md] WebSocket, API patterns, Frontend hooks
- [Source: idp-portal/backend/app/websocket/execution_ws.py] Pattern manager et broadcast
- [Source: idp-portal/frontend/src/hooks/useWebSocket.ts] Pattern connexion WS avec token et reconnect

## Dev Agent Record

### Agent Model Used
Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References
- Backend tests: 50/50 pass (dashboard_websocket, dashboard_api, execution_websocket, execution_service)
- Frontend tests: 29/29 new tests pass (useDashboardWebSocket, DashboardPage, RecentExecutions)
- Full regression: 787/800 backend pass (13 pre-existing inventory failures), 439/441 frontend pass (2 pre-existing IntegrationsTable failures)

### Completion Notes List
- Task 1: Backend WebSocket /ws/dashboard with DashboardWebSocketManager, auth/RBAC, broadcast integration in execution_service
- Task 2: Frontend useDashboardWebSocket hook with reconnect, state update, integrated in DashboardPage
- Task 3: Badge on Dashboard tab (TopNav) via DashboardContext, localStorage persistence, FAILED row highlighting
- Task 4: aria-live="polite" region + toast notifications for status changes (accessibility)
- Task 5: 51 new tests (22 backend + 29 frontend) covering all ACs

### File List
**Backend (new)**
- idp-portal/backend/app/websocket/dashboard_ws.py
- idp-portal/backend/tests/unit/test_dashboard_websocket.py

**Backend (modified)**
- idp-portal/backend/app/api/websocket_routes.py
- idp-portal/backend/app/api/v1/executions.py
- idp-portal/backend/app/services/execution_service.py

**Frontend (new)**
- idp-portal/frontend/src/hooks/useDashboardWebSocket.ts
- idp-portal/frontend/src/hooks/useDashboardWebSocket.test.tsx
- idp-portal/frontend/src/contexts/DashboardContext.tsx

**Frontend (modified)**
- idp-portal/frontend/src/App.tsx
- idp-portal/frontend/src/pages/DashboardPage.tsx
- idp-portal/frontend/src/pages/DashboardPage.test.tsx
- idp-portal/frontend/src/components/dashboard/RecentExecutions.tsx
- idp-portal/frontend/src/components/layout/TopNav.tsx
- idp-portal/frontend/src/components/layout/TopNav.test.tsx
- idp-portal/frontend/src/components/layout/AppLayout.test.tsx

## Senior Developer Review (AI)

**Reviewer:** Cyrille (adversarial code-review workflow)  
**Date:** 2026-01-30

**Issues found:** 2 High, 4 Medium, 3 Low.

**Fixes applied (option 1 — automatic):**
- **HIGH:** execution_service.py — null check for `execution_for_broadcast` before broadcast RUNNING (évite AttributeError).
- **HIGH:** Story non versionnée — rappel : committer le fichier story pour traçabilité.
- **MEDIUM:** execution_service.py — broadcast dashboard avec `step_summary` après chaque step_update (RUNNING + step_summary au début et à la fin de chaque étape).
- **MEDIUM:** RecentExecutions.tsx — région aria-live dédiée (visually hidden) avec texte "Exécution X mise à jour : statut Y" pour AC5.
- **MEDIUM:** useDashboardWebSocket.ts — insertion des nouvelles exécutions (non présentes dans la liste) avec tri par date et limite 10.
- **MEDIUM:** useDashboardWebSocket.ts — console.warn remplacé par log conditionnel (import.meta.env.DEV).
- **LOW:** TopNav.tsx — aria-label sur l’onglet Dashboard quand badge visible ("Dashboard (N erreur(s) non vue(s))").
- **LOW:** TopNav.test.tsx — test Story 5.2 vérifiant l’aria-label du badge Dashboard.

**Résultat:** Tous les points HIGH et MEDIUM traités en code ; story passée en **done**. Action manuelle : committer le fichier story et les changements.
