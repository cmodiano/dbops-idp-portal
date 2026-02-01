# Story 4.6 : Timeline d'exécution temps réel

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBA,
I want suivre la progression de mon exécution étape par étape en temps réel via une timeline visuelle,
So that je sais exactement où en est l'exécution à tout moment.

## Acceptance Criteria

1. **AC1 — Affichage timeline après confirmation**
   **Given** un DBA confirme l'exécution dans le wizard,
   **When** la timeline s'affiche (remplace le wizard),
   **Then** les étapes sont listées verticalement avec leur statut : en attente (gris), en cours (bleu pulse), terminé (vert check), erreur (rouge X).

2. **AC2 — Mise à jour temps réel via WebSocket**
   **Given** une étape change de statut,
   **When** le backend reçoit un callback ou complète une étape,
   **Then** le frontend reçoit la mise à jour via WebSocket (/ws/executions/{id}) en < 5 secondes (NFR3),
   **And** le nœud correspondant se met à jour visuellement sans refresh.

3. **AC3 — Re-synchronisation sur reconnexion WebSocket**
   **Given** le WebSocket est déconnecté,
   **When** la connexion est rétablie,
   **Then** le frontend re-synchronise l'état complet de l'exécution via GET /api/v1/executions/{id}.

4. **AC4 — Accessibilité et format messages**
   **And** le composant ExecutionTimeline est accessible : role="list", nœuds role="listitem", aria-expanded pour le détail, aria-live="polite" pour les changements de statut,
   **And** les messages WebSocket suivent le format Architecture : `{ "type": "step_update", "execution_id", "data": { step_order, step_name, status, started_at, completed_at } }`,
   **And** FR19 et FR23 sont satisfaites.

## Tasks / Subtasks

- [x] Task 1 — Backend WebSocket endpoint et manager (AC: 2, 4)
  - [x] 1.1 Créer `app/websocket/execution_ws.py` : classe `ExecutionWebSocketManager` avec méthodes `connect(execution_id, websocket)`, `disconnect(websocket)`, `broadcast_step_update(execution_id, step_data)`. Utiliser `set()` pour stocker les connexions actives par execution_id.
  - [x] 1.2 Endpoint WebSocket : ajouter dans `main.py` ou router dédié `@app.websocket("/ws/executions/{execution_id}")`. Vérifier que l'utilisateur a accès à l'exécution (RBAC via execution_repository.get_by_id + user_id). Accepter connexion avec token JWT (query param ou header).
  - [x] 1.3 Format messages : step_update `{"type": "step_update", "execution_id": int, "data": {"step_order": int, "step_name": str, "status": str, "started_at": str|null, "completed_at": str|null}}`, execution_complete `{"type": "execution_complete", "execution_id": int, "status": "COMPLETED"}`, execution_failed `{"type": "execution_failed", "execution_id": int, "error_message": str}`.
  - [x] 1.4 Intégrer dans execution_service : après chaque `update_step_status` et `update_status`, appeler le WebSocket manager pour broadcaster aux clients connectés. Injecter le manager (singleton) dans ExecutionService.

- [x] Task 2 — Hook useWebSocket et service frontend (AC: 2, 3, 4)
  - [x] 2.1 Créer `hooks/useWebSocket.ts` : `useWebSocket(executionId: number | null)` retourne `{ steps, execution, loading, error, lastMessage }`. Connexion WebSocket vers `wss://${window.location.host}/ws/executions/${executionId}`. Token JWT passé en query `?token=...`.
  - [x] 2.2 Gestion reconnexion : onclose → attendre 2s → reconnect. Sur connexion rétablie → appel GET /api/v1/executions/{id} pour re-sync état complet (AC3).
  - [x] 2.3 Parsing messages : step_update → merge dans state steps. execution_complete/execution_failed → update execution status, fermer WS si terminé.
  - [x] 2.4 Ajouter `getExecutionSteps(executionId)` dans `services/execution_service.ts` : GET `/executions/${executionId}/steps`, retourne liste ExecutionStepResponse.

- [x] Task 3 — Composant ExecutionTimeline (AC: 1, 4)
  - [x] 3.1 Créer `components/execution/ExecutionTimeline.tsx` : props `{ executionId, execution?, steps?, mode?: "realtime" | "historical" }`. Si mode realtime et executionId → useWebSocket. Sinon → props execution + steps (historique).
  - [x] 3.2 Rendu vertical : ligne verticale avec nœuds. Chaque nœud : icône statut (cercle coloré), nom étape, durée. États : PENDING (gris), RUNNING (bleu pulse), COMPLETED (vert check), FAILED (rouge X), SKIPPED (gris barre).
  - [x] 3.3 Expandable : clic nœud → expand/collapse détail (logs output, error_message). `aria-expanded`, `role="list"`, `role="listitem"`, `aria-live="polite"` sur zone statut (AC4).
  - [x] 3.4 Styles : palette tokens (success #10B981, error #EF4444, info #3B82F6, neutral #9CA3AF). Animation pulse pour RUNNING (CSS keyframes).
  - [x] 3.5 Badge ServiceNow (Story 4.5) : si step type servicenow et output.change_number → badge "Changement {change_number}" avec lien si output.change_id. Badge "En attente approbation" si output.status="pending_approval".

- [x] Task 4 — Intégration wizard → timeline (AC: 1)
  - [x] 4.1 Modifier `CatalogPage.tsx` : `handleExecutionSuccess(executionId)` → au lieu de fermer uniquement, afficher ExecutionTimeline. Options : (a) remplacer contenu wizard par timeline dans même modal/drawer, ou (b) naviguer vers /executions/{id} avec timeline.
  - [x] 4.2 Option retenue (a) : ExecutionWizard reste ouvert mais passe en "mode timeline" après succès. Ajouter state `activeExecutionId` dans CatalogPage. Si activeExecutionId → afficher ExecutionTimeline au lieu du wizard steps. Bouton "Retour au catalogue" ferme tout.
  - [x] 4.3 Alternative (b) : `handleExecutionSuccess` → `navigate(`/executions?highlight=${executionId}`)` et fermer wizard. ExecutionsPage affiche timeline pour execution highlight.
  - [x] 4.4 Choisir (a) pour rester dans le flow catalogue : le wizard se transforme en timeline. Modal/Drawer 640px (wizard width) avec ExecutionTimeline en contenu.

- [x] Task 5 — Tests (AC: tous)
  - [x] 5.1 Backend : test WebSocket endpoint connect/disconnect, broadcast step_update. Mock execution_repository pour RBAC. Test avec pytest + TestClient WebSocket (starlette).
  - [x] 5.2 Frontend : ExecutionTimeline.test.tsx — rendu nœuds par statut, aria attributes, role list/listitem.
  - [x] 5.3 Intégration : flow wizard → submit → timeline affichée via activeExecutionId.

## Dev Notes

### Contexte métier

- **FR19** : Tout utilisateur peut suivre le statut d'une exécution en temps réel (soumis, en cours, terminé, erreur).
- **FR23** : Le système reçoit les callbacks asynchrones des plateformes d'exécution.
- **NFR3** : La mise à jour du statut en temps réel se rafraîchit avec un délai max 5 secondes après réception du callback.
- **Epic 4** : DBA exécute une action de bout en bout via le wizard et suit la progression étape par étape en temps réel via la timeline. Cette story réalise la timeline temps réel côté frontend + push WebSocket côté backend.

### Patterns à respecter

- **WebSocket FastAPI** : `@app.websocket("/ws/executions/{execution_id}")`, `WebSocket` de Starlette. Vérifier auth (Depends get_current_user ou validation manuelle via token). [Source: architecture.md]
- **Format messages** : JSON `{"type": "...", "execution_id": int, "data": {...}}`. Types : step_update, execution_complete, execution_failed, connection_ack. [Source: architecture.md § Communication Patterns]
- **Re-sync on reconnect** : GET /api/v1/executions/{id} pour état complet. Évite perte de données si WS déconnecté pendant mise à jour. [Source: epics.md AC3]
- **UX Temporal** : Timeline verticale, nœuds cliquables, progressive disclosure (logs au clic). [Source: ux-design-specification.md]

### Ce qui existe déjà

- **Backend** : execution_service.py avec start_execution, update_step_status. execution_repository avec get_by_id, get_steps_by_execution_id, update_step_status. Pas de WebSocket. [Source: execution_service.py]
- **API** : GET /api/v1/executions/{id}, GET /api/v1/executions/{id}/steps. [Source: api/v1/executions.py]
- **Frontend** : ExecutionWizard avec onSuccess(executionId). execution_service.getExecution(), listExecutions(). Pas de getExecutionSteps ni useWebSocket. [Source: ExecutionWizard.tsx, execution_service.ts]
- **Dossier** : frontend/src/components/execution/ existe avec .gitkeep — vide. [Source: project structure]
- **Nginx** : location /ws/ déjà configuré pour proxy WebSocket. [Source: nginx/idp-portal.conf]

### Références techniques

- **FastAPI WebSocket** : `from fastapi import WebSocket`. `await websocket.accept()`, `await websocket.send_json({...})`, `await websocket.receive_text()`. Dépendance : pas de Depends standard pour WS, valider token manuellement. [Source: FastAPI docs]
- **Starlette WebSocket** : Même API. Test : `with TestClient(app).websocket_connect("/ws/executions/1") as ws: ws.receive_json()`. [Source: Starlette docs]
- **React useWebSocket** : Pas de librairie imposée. Implémentation custom avec `new WebSocket(url)`, `onmessage`, `onclose`, `reconnect`. Ou `useEffect` + cleanup. [Source: architecture — pas de lib tierce]
- **Vite proxy WS** : Configurer dans vite.config.ts pour proxy /ws vers backend. Vérifier `ws: true` dans proxy config. [Source: Vite proxy docs]

### Project Structure Notes

- **Nouveau backend** : `app/websocket/execution_ws.py` (ExecutionWebSocketManager).
- **Modifier backend** : `main.py` (router WebSocket, lifespan pour init manager), `services/execution_service.py` (injecter manager, appeler broadcast après updates).
- **Nouveau frontend** : `hooks/useWebSocket.ts`, `components/execution/ExecutionTimeline.tsx`, `components/execution/TimelineNode.tsx` (optionnel).
- **Modifier frontend** : `services/execution_service.ts` (getExecutionSteps), `pages/CatalogPage.tsx` (handleExecutionSuccess → timeline), `components/catalog/ExecutionWizard.tsx` (optionnel — mode timeline post-succès).

### Architecture Compliance

- **WebSocket** : Endpoint /ws/executions/{id}. Messages types step_update, execution_complete, execution_failed. Format JSON Architecture. [Source: architecture.md § API & Communication Patterns]
- **Stack** : FastAPI WebSocket natif (pas de lib externe). React sans lib WebSocket tierce. [Source: architecture.md]
- **Frontend** : Composant ExecutionTimeline (UX spec). Hooks useWebSocket (architecture). [Source: architecture.md § Project Structure]

### Library/Framework Requirements

- **FastAPI** : WebSocket intégré (Starlette). Aucune dépendance additionnelle. [Source: architecture.md]
- **React** : useState, useEffect, useCallback pour useWebSocket. [Source: architecture.md]
- **Ant Design** : Timeline (Ant Design) peut servir de base ou inspirer — mais UX spec décrit composant custom "Temporal-style". Vérifier si Ant Design Timeline convient ou composant custom. [Source: ux-design-specification.md]

### File Structure Requirements

- **Backend** : `app/websocket/execution_ws.py` — manager singleton, méthode broadcast. `main.py` — `@app.websocket("/ws/executions/{execution_id}")`, enregistrer endpoint.
- **Frontend** : `src/hooks/useWebSocket.ts`, `src/components/execution/ExecutionTimeline.tsx`, `src/components/execution/index.ts` (barrel).

### Testing Requirements

- **Backend** : Test WebSocket connect avec auth, broadcast reçu par client. Test RBAC (user B ne peut pas connecter à execution de user A). Mock execution_repository.
- **Frontend** : ExecutionTimeline affiche nœuds corrects par statut. useWebSocket reconnect et re-sync. Accessibilité : role, aria-expanded, aria-live.

### Previous Story Intelligence

- **Story 4.5 (ServiceNow)** : Task 7 prévoyait modification ExecutionTimeline pour badge changement — ExecutionTimeline n'existait pas. Cette story crée ExecutionTimeline et intègre le badge ServiceNow (Task 3.5). [Source: 4-5-integration-servicenow-ouverture-automatique-changement.md]
- **Story 4.3 (Moteur exécution)** : execution_service.start_execution appelle update_step_status. C'est le point d'injection pour broadcast WebSocket. [Source: 4-3-moteur-execution-et-facade-api.md]
- **Story 4.1 (Wizard)** : ExecutionWizard onSuccess(executionId) — point d'intégration pour afficher timeline. [Source: 4-1-wizard-execution-en-3-etapes.md]

### Git Intelligence Summary

- Derniers commits : execution_service avec orchestration étapes, execution_repository update_step_status. Pas de WebSocket. Pattern service async établi.
- Code existant : execution_service met à jour steps mais pas de push vers clients. Backend synchrone côté "vue" — le frontend doit poll ou WebSocket. Cette story ajoute WebSocket.

### Latest Tech Information

- **FastAPI WebSocket 2024** : `@app.websocket("/path")` avec `WebSocket` parameter. Pour auth : passer token en query `?token=xxx` et valider avant `accept()`. Pas de Depends car WebSocket n'a pas de Request standard. [Source: FastAPI WebSocket docs]
- **React 19** : Pas de changements majeurs pour WebSocket. useEffect cleanup important pour fermer WS on unmount. [Source: React docs]

### Project Context Reference

- **Architecture** : [Source: planning-artifacts/architecture.md] — WebSocket /ws/executions/{id}, messages step_update, execution_complete, execution_failed. Format JSON.
- **Epics** : [Source: planning-artifacts/epics.md] — Story 4.6 acceptance criteria, FR19, FR23, NFR3.
- **UX** : [Source: planning-artifacts/ux-design-specification.md] — ExecutionTimeline spécifications (nœuds, états, expandable, aria).

### References

- [Source: planning-artifacts/architecture.md] — WebSocket endpoint, format messages, Communication Patterns.
- [Source: planning-artifacts/epics.md] — Story 4.6 AC complets.
- [Source: planning-artifacts/ux-design-specification.md] — ExecutionTimeline composant custom, accessibilité.
- [Source: 4-5-integration-servicenow-ouverture-automatique-changement.md] — Badge ServiceNow dans timeline (Task 7).
- [Source: 4-3-moteur-execution-et-facade-api.md] — execution_service, update_step_status.
- [Source: idp-portal/backend/app/services/execution_service.py] — Points d'injection broadcast.
- [Source: idp-portal/backend/app/api/v1/executions.py] — GET /executions/{id}/steps.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- ✅ Task 1: ExecutionWebSocketManager dans app/websocket/execution_ws.py. Router WebSocket dans app/api/websocket_routes.py, inclus dans main.py. Auth via token query param, RBAC execution.user_id. execution_repository.get_step_by_id ajouté pour broadcast après update.
- ✅ Task 2: useWebSocket.ts avec reconnexion 2s, re-sync GET on open. getExecutionSteps dans execution_service.ts.
- ✅ Task 3: ExecutionTimeline.tsx avec mode realtime/historical, nœuds par statut, expand/collapse, badge ServiceNow, aria roles.
- ✅ Task 4: CatalogPage activeExecutionId, ExecutionWizard mode timeline avec bouton "Retour au catalogue".
- ✅ Task 5: test_execution_websocket.py (5 tests), ExecutionTimeline.test.tsx (3 tests). 26 backend + 3 frontend tests passent.

### Code Review Fixes Applied

- ✅ **HIGH-1**: WebSocket auth validation moved BEFORE `accept()` to prevent unauthorized connections consuming server resources.
- ✅ **HIGH-2**: Added integration tests for Task 5.3 (wizard→timeline flow) in ExecutionTimeline.test.tsx.
- ✅ **HIGH-3**: Empty catch block in useWebSocket.ts now logs parse errors via `console.warn`.
- ✅ **MEDIUM-2**: Added `isMountedRef` to prevent setState after unmount in useWebSocket.ts.
- ✅ **MEDIUM-3**: Moved `aria-live="polite"` from individual listitems to a dedicated announcement region (AC4 compliance).
- ✅ **MEDIUM-4**: Added tests for realtime mode, loading/error states, and step updates in ExecutionTimeline.test.tsx.

### File List

**Story 4.6 Files:**
- idp-portal/backend/app/websocket/execution_ws.py (new)
- idp-portal/backend/app/api/websocket_routes.py (new, review-fixed: HIGH-1 auth before accept)
- idp-portal/backend/app/main.py (modified)
- idp-portal/backend/app/repositories/execution_repository.py (modified — get_step_by_id)
- idp-portal/backend/app/services/execution_service.py (modified — ws_manager injection)
- idp-portal/backend/app/api/v1/executions.py (modified — pass ws_manager)
- idp-portal/backend/tests/unit/test_execution_websocket.py (new, review-fixed: added HIGH-1 test)
- idp-portal/frontend/src/hooks/useWebSocket.ts (new, review-fixed: HIGH-3 error logging, MEDIUM-2 memory leak)
- idp-portal/frontend/src/services/execution_service.ts (modified — getExecutionSteps)
- idp-portal/frontend/src/types/api.ts (modified — ExecutionStepResponse types)
- idp-portal/frontend/src/components/execution/ExecutionTimeline.tsx (new, review-fixed: MEDIUM-3 aria-live)
- idp-portal/frontend/src/components/execution/index.ts (new)
- idp-portal/frontend/src/components/execution/ExecutionTimeline.test.tsx (new, review-fixed: HIGH-2 Task 5.3 tests, MEDIUM-4)
- idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx (modified — activeExecutionId, timeline mode)
- idp-portal/frontend/src/pages/CatalogPage.tsx (modified — handleExecutionSuccess, activeExecutionId)
- _bmad-output/implementation-artifacts/sprint-status.yaml (modified)

**Note (MEDIUM-1):** Git shows additional modified files not related to Story 4.6:
- Story 4.5 files: servicenow_service.py, servicenow.py, test_servicenow_service.py
- Infrastructure: docker-compose.yml, run_migrations.sh, 01-create-idp-app-user.sql
- Config: _bmad/bmm/config.yaml, idp-portal/README.md
- Other tests: test_execution_api.py, test_execution_service.py, test_oracle_crud.py
- Other: services.py, config.py, integration_repository.py
