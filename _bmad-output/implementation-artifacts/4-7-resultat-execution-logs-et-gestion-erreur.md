# Story 4.7 : Résultat d'exécution, logs et gestion d'erreur

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBA,
I want voir le résultat final de l'exécution avec les logs détaillés et une gestion d'erreur structurée,
So that je comprenne ce qui s'est passé et je dispose de toutes les preuves.

## Acceptance Criteria

1. **AC1 — Bandeau succès**
   **Given** l'exécution se termine avec succès,
   **When** la timeline affiche le résultat,
   **Then** un bandeau vert s'affiche avec le résumé de ce qui a été fait + lien vers la trace d'audit.

2. **AC2 — StructuredErrorCard en cas d'échec**
   **Given** l'exécution échoue à une étape,
   **When** la timeline affiche l'erreur,
   **Then** un StructuredErrorCard s'affiche avec : "Quoi" (étape échouée), "Pourquoi" (cause), "Options" (Relancer, Voir logs, Contacter DBA).

3. **AC3 — Logs au clic sur un nœud**
   **Given** un DBA clique sur un nœud de la timeline,
   **When** le détail s'expande,
   **Then** les logs remontés par la plateforme s'affichent (output, paramètres envoyés, réponse plateforme, durée).

4. **AC4 — Panneau logs détaillés**
   **Given** un DBA clique sur "Voir logs détaillés",
   **When** le panneau de logs s'ouvre,
   **Then** les logs techniques complets de l'étape s'affichent avec horodatage.

5. **AC5 — Accessibilité StructuredErrorCard**
   **And** le composant StructuredErrorCard est accessible : role="alert", sections aria-labelledby, focus automatique sur les options.

6. **AC6 — API logs**
   **And** l'API GET /api/v1/executions/{id}/steps/{step_id}/logs retourne les logs (ou les données step incluent output/error_message suffisants pour afficher les logs).
   **And** FR20 et FR21 sont satisfaites.

## Tasks / Subtasks

- [x] Task 1 — API logs step (AC: 3, 4, 6)
  - [x] 1.1 Ajouter GET /api/v1/executions/{execution_id}/steps/{step_id}/logs (ou étendre GET .../steps pour inclure output/error_message complets). Si endpoint dédié : retourner `{ "step_id": int, "output": {...}, "error_message": str|null, "started_at", "completed_at" }`. RBAC : même règle que GET execution (user_id ou profil).
  - [x] 1.2 execution_repository : s'assurer que get_step_by_id / get_steps_by_execution_id retournent bien OUTPUT et ERROR_MESSAGE (déjà en place — vérifier mapping).
  - [x] 1.3 Documenter l'endpoint dans OpenAPI (docstrings FastAPI).

- [x] Task 2 — StructuredErrorCard frontend (AC: 2, 5)
  - [x] 2.1 Créer `components/execution/StructuredErrorCard.tsx` : props `{ quoi: string, pourquoi: string, stepId?: number, executionId?: number }`. Affichage : section "Quoi", "Pourquoi", boutons Options "Relancer", "Voir logs", "Contacter DBA". role="alert", aria-labelledby pour les sections, focus automatique sur le premier bouton option (useEffect ref).
  - [x] 2.2 Relancer : déclencher callback onRetry (parent relance l'exécution ou renvoie au wizard). Voir logs : callback onViewLogs (ouvre panneau logs pour stepId). Contacter DBA : lien ou callback onContact (lien mailto ou page aide).
  - [x] 2.3 Styles : tokens erreur (#EF4444), contraste fond. Accessibilité : focus visible, navigation clavier.
  - [x] 2.4 Co-localiser StructuredErrorCard.test.tsx : rendu Quoi/Pourquoi/Options, role="alert", aria.

- [x] Task 3 — Bandeau succès (AC: 1)
  - [x] 3.1 Dans ExecutionTimeline (ou parent), quand execution.status === COMPLETED : afficher un bandeau vert (Alert success Ant Design ou bloc custom) avec résumé : "Exécution terminée avec succès", nombre d'étapes, durée totale. Lien "Trace d'audit" : vers /audit?execution_id={id} ou # (si page audit pas encore en place, lien désactivé avec tooltip "Bientôt disponible").
  - [x] 3.2 Si pas de page audit : le lien peut pointer vers une section future ou être masqué pour le MVP ; documenter dans Dev Notes.

- [x] Task 4 — Logs dans timeline expand + panneau détaillé (AC: 3, 4)
  - [x] 4.1 ExecutionTimeline / TimelineNode : à l'expand d'un nœud, afficher output + error_message du step (déjà dans ExecutionStepResponse). Format : output en JSON formaté ou liste lisible ; error_message en rouge si présent. Afficher durée (started_at, completed_at).
  - [x] 4.2 Ajouter bouton "Voir logs détaillés" dans le détail expandé (ou dans StructuredErrorCard quand erreur). Au clic : ouvrir Drawer/Modal avec contenu logs complets (même données : output, error_message, horodatage). Données venant de GET .../steps/{step_id}/logs ou des steps déjà chargés (GET /executions/{id}/steps).
  - [x] 4.3 Panneau logs : préformatage (pre/code) pour output technique, horodatage par étape. Accessibilité : titre du drawer "Logs détaillés - Étape X", focus trap dans le drawer.

- [x] Task 5 — Intégration timeline ↔ erreur et succès (AC: 1, 2, 3)
  - [x] 5.1 Quand execution.status === FAILED : identifier l'étape en échec (step status FAILED), afficher StructuredErrorCard avec quoi = step_name, pourquoi = step.error_message, options Relancer / Voir logs / Contacter DBA.
  - [x] 5.2 Placement : StructuredErrorCard au-dessus ou en dessous de la timeline (selon UX spec). Bandeau succès au-dessus de la timeline quand COMPLETED.
  - [x] 5.3 Vérifier que ExecutionTimeline reçoit bien steps avec output et error_message (types api.ts ExecutionStepResponse).

- [x] Task 6 — Tests (AC: tous)
  - [x] 6.1 Backend : test GET /executions/{id}/steps/{step_id}/logs (ou GET steps avec champs logs). RBAC : 403 si execution.user_id !== current_user. Données retournées avec output/error_message.
  - [x] 6.2 Frontend : StructuredErrorCard.test.tsx (rendu, aria, callbacks). ExecutionTimeline : affichage bandeau succès si COMPLETED, StructuredErrorCard si FAILED, logs au expand.
  - [x] 6.3 Intégration : flow execution échouée → StructuredErrorCard visible → "Voir logs" ouvre panneau.

## Dev Notes

### Contexte métier

- **FR20** : Tout utilisateur peut consulter les logs remontés par la plateforme d'exécution.
- **FR21** : DBA peut accéder aux logs techniques détaillés d'une exécution.
- **Epic 4** : DBA exécute une action de bout en bout et suit la progression ; cette story ajoute le résultat final (succès/erreur), l'affichage des logs et une gestion d'erreur structurée (StructuredErrorCard).

### Patterns à respecter

- **Erreur API** : Format `{ "error": { "code": "...", "message": "...", "details": {...} } }`. Pas de `return {"name": "..."}` sans wrapper. [Source: architecture.md § Format Patterns]
- **Gestion d'erreur** : Pattern unifié quoi/pourquoi/options. Circuit breaker par plateforme. Erreur ≠ crash. [Source: architecture.md § Cross-Cutting Concerns]
- **Frontend loading/error** : État loading, error, data. UI : loading → Skeleton, error → message, data → contenu. [Source: architecture.md § Process Patterns]
- **Composants custom UX** : StructuredErrorCard, ExecutionTimeline (déjà listés). [Source: architecture.md § Frontend Architecture]

### Ce qui existe déjà

- **Backend** : ExecutionStepResponse avec `output`, `error_message`. execution_repository.get_step_by_id, get_steps_by_execution_id. update_step_status avec output/error_message. Pas d'endpoint dédié /steps/{step_id}/logs — les steps retournés par GET /executions/{id}/steps contiennent déjà output et error_message. [Source: execution_repository.py, models/execution.py]
- **Frontend** : ExecutionTimeline avec nœuds, expand/collapse. ExecutionStepResponse dans types/api.ts avec output, error_message. Pas de StructuredErrorCard. Pas de bandeau succès ni panneau "Voir logs détaillés". [Source: ExecutionTimeline.tsx, execution_service.ts]
- **Architecture** : StructuredErrorCard cité (composant custom). API error format, WCAG 2.1 AA. [Source: architecture.md]

### Project Structure Notes

- **Nouveau frontend** : `components/execution/StructuredErrorCard.tsx`, `StructuredErrorCard.test.tsx`.
- **Modifier frontend** : `ExecutionTimeline.tsx` (bandeau succès, affichage output/error dans expand, bouton "Voir logs détaillés"), `TimelineNode` ou bloc expand si séparé, `pages/CatalogPage.tsx` ou parent si placement global.
- **Backend (optionnel)** : si endpoint dédié `/steps/{step_id}/logs` : ajouter dans `api/v1/executions.py`, réutiliser execution_repository.get_step_by_id + RBAC (vérifier execution.user_id).

### Architecture Compliance

- **API** : REST JSON, snake_case, wrapper `{ "data": ... }` / `{ "error": ... }`. Endpoints sous /api/v1/executions. [Source: architecture.md]
- **Composants** : ExecutionTimeline (existant), StructuredErrorCard (nouveau). Ant Design Alert/Drawer pour bandeau et panneau logs. [Source: architecture.md § Frontend Architecture]
- **Accessibilité** : role="alert", aria-labelledby, focus sur options. WCAG 2.1 AA. [Source: architecture.md § UX Architectural Implications]

### Library/Framework Requirements

- **React** : useState, useEffect, useRef (focus StructuredErrorCard). Pas de librairie tierce imposée pour logs. [Source: architecture.md]
- **Ant Design** : Alert (success), Drawer ou Modal pour panneau logs, Button. [Source: architecture.md]
- **FastAPI** : Si nouvel endpoint : router.get, Depends(get_current_user), vérification RBAC execution. [Source: architecture.md]

### File Structure Requirements

- **Frontend** : `src/components/execution/StructuredErrorCard.tsx`, `StructuredErrorCard.test.tsx`, barrel `execution/index.ts` (exporter StructuredErrorCard).
- **Backend** : Si endpoint logs : `api/v1/executions.py` seule modification (pas de nouveau fichier).

### Testing Requirements

- **Backend** : Test GET step logs ou GET steps avec champs complets. RBAC : utilisateur ne peut pas accéder aux steps d'une execution d'un autre user. [Source: architecture.md § Tests]
- **Frontend** : Tests unitaires StructuredErrorCard (rendu, aria, callbacks). ExecutionTimeline : bandeau succès et StructuredErrorCard selon status. Co-localiser tests avec composants. [Source: architecture.md § Structure Patterns]

### Previous Story Intelligence

- **Story 4.6 (Timeline temps réel)** : ExecutionTimeline déjà en place avec nœuds, expand/collapse, useWebSocket, getExecutionSteps. Cette story réutilise ExecutionTimeline et y ajoute : bandeau succès, StructuredErrorCard en cas d'échec, affichage output/error dans l'expand, panneau "Voir logs détaillés". Types ExecutionStepResponse ont déjà output et error_message. [Source: 4-6-timeline-execution-temps-reel.md]
- **Story 4.5 (ServiceNow)** : output step peut contenir change_number, change_id. À afficher dans les logs (déjà prévu dans timeline expand). [Source: 4-5-integration-servicenow-ouverture-automatique-changement.md]
- **Story 4.3 (Moteur exécution)** : _fail_step(step_id, error_message) et update_step_status avec output/error_message. Les données sont déjà persistées ; il reste à les exposer et les afficher. [Source: 4-3-moteur-execution-et-facade-api.md]

### Git Intelligence Summary

- Derniers changements : WebSocket, ExecutionTimeline, execution_repository get_step_by_id, ExecutionStepResponse avec output/error_message. Pas de StructuredErrorCard ni endpoint /steps/{step_id}/logs. [Source: sprint-status, 4-6]

### Latest Tech Information

- **Ant Design 6** : Alert, Drawer, Button — pas de breaking change pour ce usage. [Source: Ant Design 6.x]
- **FastAPI** : Router avec prefix, Depends pour auth. GET avec path params execution_id, step_id. [Source: FastAPI docs]

### Project Context Reference

- **Architecture** : [Source: planning-artifacts/architecture.md] — Error format, StructuredErrorCard composant, API patterns, WCAG.
- **Epics** : [Source: planning-artifacts/epics.md] — Story 4.7 AC complets, FR20, FR21.
- **UX** : [Source: planning-artifacts/ux-design-specification.md] — StructuredErrorCard spécifications si détaillées.

### References

- [Source: planning-artifacts/architecture.md] — Error handling, API response format, composants custom.
- [Source: planning-artifacts/epics.md] — Story 4.7 acceptance criteria.
- [Source: idp-portal/backend/app/repositories/execution_repository.py] — get_step_by_id, get_steps_by_execution_id, champs OUTPUT, ERROR_MESSAGE.
- [Source: idp-portal/frontend/src/components/execution/ExecutionTimeline.tsx] — Point d’intégration bandeau succès, erreur, logs.
- [Source: idp-portal/frontend/src/types/api.ts] — ExecutionStepResponse (output, error_message).

## Dev Agent Record

### Agent Model Used

Amelia (Dev Agent) — Story 4.7 implementation 2026-01-30.

### Debug Log References

- Red-green-refactor : tests Task 1 (GET step logs) puis implémentation endpoint + StepLogsResponse.
- StructuredErrorCard : tests 7 (rendu, aria, callbacks) puis composant + barrel export.
- ExecutionTimeline : bandeau succès (Alert), StructuredErrorCard (FAILED), Drawer logs détaillés, onRetry/onContact passés depuis ExecutionWizard.

### Completion Notes List

- **Task 1** : GET /api/v1/executions/{execution_id}/steps/{step_id}/logs ajouté (StepLogsResponse). RBAC : même règle que GET execution (user_id). Repository get_step_by_id / get_steps_by_execution_id déjà OUTPUT/ERROR_MESSAGE.
- **Task 2** : StructuredErrorCard.tsx créé (quoi, pourquoi, Relancer/Voir logs/Contacter DBA, role="alert", aria-labelledby, focus premier bouton). StructuredErrorCard.test.tsx 7 tests.
- **Task 3** : Bandeau vert Alert (Ant Design) dans ExecutionTimeline quand execution.status === COMPLETED (résumé, durée, lien "Trace d'audit" # + tooltip "Bientôt disponible").
- **Task 4** : Expand nœud affiche output/error_message (existant) ; bouton "Voir logs détaillés" ouvre Drawer avec logs complets (horodatage, pre/code). Données depuis steps déjà chargés.
- **Task 5** : execution.status === FAILED → StructuredErrorCard au-dessus de la timeline (failedStep), onRetry = onBackToCatalog depuis ExecutionWizard.
- **Task 6** : Backend TestGetStepLogs (4 tests). Frontend StructuredErrorCard 7 tests, ExecutionTimeline 3 tests Story 4.7 (bandeau succès, StructuredErrorCard, Voir logs détaillés).

### Code Review (AI) — 2026-01-30

- **Option choisie :** 1 — Corrections automatiques.
- **MEDIUM corrigés :** (1) onContact : ExecutionWizard passe désormais un callback mailto (`mailto:?subject=IDP%20Portal%20-%20Support%20DBA`) pour l’option Contacter DBA (AC2). (2) AC4/Task 4.3 : focus trap dans le Drawer — ref sur le contenu du panneau logs + `tabIndex={-1}` et `useEffect` pour focus à l’ouverture (ExecutionTimeline.tsx). (3) Task 6.3 : test d’intégration ajouté — clic sur « Voir logs » dans StructuredErrorCard ouvre le Drawer (ExecutionTimeline.test.tsx).
- **LOW corrigé :** Lien « Trace d’audit » remplacé par un `<span>` avec tooltip « Bientôt disponible » (lien désactivé, pas de navigation).
- **File List :** Inchangée (scope 4-7). La branche git contient des changements mixtes 4-5/4-6/4-7 ; la File List ci-dessous reflète les fichiers modifiés pour la story 4-7.

### File List

- idp-portal/backend/app/models/execution.py (StepLogsResponse)
- idp-portal/backend/app/api/v1/executions.py (GET step logs, docstrings)
- idp-portal/backend/tests/unit/test_execution_api.py (TestGetStepLogs)
- idp-portal/frontend/src/components/execution/StructuredErrorCard.tsx
- idp-portal/frontend/src/components/execution/StructuredErrorCard.test.tsx
- idp-portal/frontend/src/components/execution/ExecutionTimeline.tsx (bandeau, StructuredErrorCard, Drawer, onRetry/onContact)
- idp-portal/frontend/src/components/execution/ExecutionTimeline.test.tsx (Story 4.7 tests + intégration Voir logs → Drawer)
- idp-portal/frontend/src/components/execution/index.ts (export StructuredErrorCard)
- idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx (onRetry/onContact vers Timeline)
- idp-portal/frontend/src/types/api.ts (StepLogsResponse)
- idp-portal/frontend/src/services/execution_service.ts (getStepLogs)
- _bmad-output/implementation-artifacts/sprint-status.yaml (4-7 in-progress → review en step 9)
- _bmad-output/implementation-artifacts/4-7-resultat-execution-logs-et-gestion-erreur.md
