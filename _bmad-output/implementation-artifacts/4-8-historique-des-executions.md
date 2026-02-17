# Story 4.8 : Historique des exécutions

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBA,
I want consulter l'historique de mes propres exécutions,
So that je retrouve facilement les actions que j'ai lancées et leur résultat.

## Acceptance Criteria

1. **AC1 — Table des exécutions**
   **Given** un DBA accède à l'onglet Executions
   **When** la page se charge
   **Then** une table affiche ses exécutions récentes : action, environnement, statut, date, durée

2. **AC2 — Détail et timeline**
   **Given** le DBA clique sur une exécution dans la table
   **When** le détail s'ouvre
   **Then** la timeline complète de l'exécution s'affiche (réutilisation du composant ExecutionTimeline en mode historique)

3. **AC3 — Exécutions en cours en tête**
   **Given** le DBA a des exécutions en cours
   **When** il consulte la table
   **Then** les exécutions en cours apparaissent en haut avec un indicateur visuel (bleu pulsé)

4. **AC4 — API et comportement**
   **And** l'API GET /api/v1/executions retourne les exécutions de l'utilisateur courant (déjà en place ; filtre implicite via JWT).
   **And** la table supporte le tri par date, statut, action
   **And** la pagination est de 25 lignes par page
   **And** les skeleton rows s'affichent pendant le chargement
   **And** FR22 est satisfaite

## Tasks / Subtasks

- [x] Task 1 — Table ExecutionsPage (AC: 1, 3, 4)
  - [x] 1.1 Dans `ExecutionsPage.tsx`, appeler `listExecutions(25, offset)` au chargement. Gérer états loading, error, data. Afficher une Table Ant Design avec colonnes : action (action_name), environnement, statut, date (created_at ou started_at), durée (calculée : completed_at - started_at, ou "—" si en cours).
  - [x] 1.2 Tri : colonnes triables par date, statut, action (tri côté client sur la page courante ou paramètres query si l'API supporte sort — sinon tri client sur les 25 premières lignes). Par défaut : exécutions en cours (RUNNING, SUBMITTED, PENDING_APPROVAL) en tête, puis par date décroissante.
  - [x] 1.3 Pagination : Ant Design Table avec pagination (pageSize 25, total depuis réponse ou paramètre total_count si l'API le fournit). Appels listExecutions(25, (page-1)*25).
  - [x] 1.4 Skeleton : pendant loading, afficher skeleton rows (Ant Design Skeleton.Table ou lignes factices avec Skeleton).

- [x] Task 2 — Indicateur exécutions en cours (AC: 3)
  - [x] 2.1 Pour les lignes dont status est RUNNING, SUBMITTED ou PENDING_APPROVAL, afficher un indicateur visuel (badge bleu pulsé ou icône "en cours"). Les placer en tête de liste (tri côté client : status in [RUNNING, SUBMITTED, PENDING_APPROVAL] d'abord, puis created_at DESC).

- [x] Task 3 — Détail et ExecutionTimeline en mode historique (AC: 2)
  - [x] 3.1 Au clic sur une ligne (ou bouton "Détail"), ouvrir un Drawer (480px ou selon layout) avec le détail de l'exécution : réutiliser ExecutionTimeline avec les steps chargés via getExecutionSteps(executionId). Pas de WebSocket pour le mode historique (données déjà complètes).
  - [x] 3.2 Drawer : titre "Exécution — [action_name]", affichage ExecutionTimeline avec steps, bandeau succès/erreur si COMPLETED/FAILED (comportement existant de ExecutionTimeline). Données execution + steps depuis getExecution(id) et getExecutionSteps(id).

- [x] Task 4 — API et backend (AC: 4)
  - [x] 4.1 Vérifier que GET /api/v1/executions avec limit et offset retourne bien les exécutions de l'utilisateur courant (déjà le cas). Si besoin, documenter que "user=me" est implicite (JWT). Optionnel : ajouter paramètres query sort=created_at&order=desc pour cohérence avec la table.
  - [x] 4.2 Réponse liste : s'assurer que le total count est disponible si pagination frontend en a besoin (sinon pagination "next/prev" sans total). Vérifier execution_repository.list_by_user et API list_executions.

- [x] Task 5 — Tests (AC: tous)
  - [x] 5.1 Backend : tests existants pour GET /executions (list) avec limit/offset et filtrage user. Compléter si besoin (tri, total_count).
  - [x] 5.2 Frontend : tests ExecutionsPage ou composant table : rendu colonnes, skeleton lors du loading, clic ouvre drawer. Test d'intégration : chargement liste → clic ligne → drawer avec timeline.

## Dev Notes

### Contexte métier

- **FR22** : Tout utilisateur peut consulter l'historique de ses propres exécutions.
- **Epic 4** : DBA exécute une action de bout en bout et suit la progression ; cette story fournit la page "Historique" (onglet Executions) pour retrouver les exécutions passées et en cours, avec détail et timeline en lecture seule.

### Patterns à respecter

- **Réponse API** : Format `{ "data": [...] }`. Pas de retour sans wrapper. [Source: architecture.md § Format Patterns]
- **Loading / erreur** : État loading → Skeleton, error → message, data → contenu. [Source: architecture.md § Process Patterns]
- **Frontend** : Données API en snake_case ; conversion au point d'usage si besoin. Pages orchestrent composants et hooks ; pas de fetch direct dans les composants. [Source: architecture.md § Component Boundaries]

### Ce qui existe déjà

- **Backend** : GET /api/v1/executions (list_by_user, limit/offset, ORDER BY created_at DESC), retourne ExecutionResponse avec id, action_id, action_name, user_id, environment, status, started_at, completed_at, created_at. GET /api/v1/executions/{id} et GET /api/v1/executions/{id}/steps déjà en place. [Source: executions.py, execution_repository.py]
- **Frontend** : ExecutionsPage.tsx existe en stub (titre seul). execution_service.listExecutions(limit, offset), getExecution(id), getExecutionSteps(id). ExecutionTimeline prêt pour affichage steps (mode temps réel ou historique). Types ExecutionResponse, ExecutionStepResponse dans api.ts. [Source: ExecutionsPage.tsx, execution_service.ts, ExecutionTimeline.tsx]
- **Architecture** : Page ExecutionsPage et route /executions documentées. Table avec pagination, skeleton. [Source: architecture.md]

### Project Structure Notes

- **Modifier** : `frontend/src/pages/ExecutionsPage.tsx` (table, tri, pagination, skeleton, drawer, ExecutionTimeline).
- **Réutiliser** : `components/execution/ExecutionTimeline.tsx`, `components/execution/StructuredErrorCard` (si erreur dans drawer), `services/execution_service.ts`, `types/api.ts`.
- **Backend** : Aucune modification obligatoire si GET /executions + limit/offset suffisent. Optionnel : ajout paramètres sort/order ou total_count dans la réponse.

### Architecture Compliance

- **API** : REST JSON, snake_case, wrapper `{ "data": ... }`. Endpoints /api/v1/executions déjà conformes. [Source: architecture.md]
- **Composants** : ExecutionTimeline réutilisé en mode "historique" (données passées en props, pas de WebSocket). Table Ant Design, Drawer, Skeleton. [Source: architecture.md § Frontend Architecture]
- **RBAC** : Liste filtrée par user_id côté backend (get_current_user). [Source: architecture.md]

### Library/Framework Requirements

- **React** : useState, useEffect pour chargement liste et détail. [Source: architecture.md]
- **Ant Design** : Table (colonnes, pagination, tri), Drawer, Skeleton, Badge ou Tag pour statut "en cours". [Source: architecture.md]
- **Services** : listExecutions, getExecution, getExecutionSteps depuis execution_service. [Source: architecture.md]

### File Structure Requirements

- **Frontend** : `pages/ExecutionsPage.tsx` (unique fichier à modifier pour la page ; pas de nouveau dossier). Composants execution/ réutilisés.
- **Tests** : Co-localiser ou page test : `ExecutionsPage.test.tsx` ou dans `__tests__/executions_page.test.tsx`.

### Testing Requirements

- **Backend** : Les tests GET /executions (list, limit, offset, 403 si autre user) existent dans test_execution_api.py. Vérifier couverture.
- **Frontend** : Tests unitaires ExecutionsPage : rendu table/skeleton, clic ligne ouvre drawer avec timeline. Pas de mock WebSocket pour la page historique. [Source: architecture.md § Structure Patterns]

### Previous Story Intelligence

- **Story 4.7 (Résultat, logs, erreur)** : ExecutionTimeline affiche bandeau succès, StructuredErrorCard en cas d'échec, logs dans le détail et panneau "Voir logs détaillés". getExecutionSteps et getExecution fournissent toutes les données pour le mode historique. Réutiliser ExecutionTimeline en passant execution + steps en props (mode "read-only", pas de useWebSocket). [Source: 4-7-resultat-execution-logs-et-gestion-erreur.md]
- **Story 4.6 (Timeline temps réel)** : ExecutionTimeline conçu pour temps réel (WebSocket) et peut afficher un état déjà complet ; en mode historique on charge une fois getExecution + getExecutionSteps et on affiche sans WS. [Source: 4-6-timeline-execution-temps-reel.md]
- **Story 4.3 (Moteur exécution)** : execution_repository.list_by_user, get_by_id, get_steps_by_execution_id. Données EXECUTIONS + EXECUTION_STEPS complètes. [Source: 4-3-moteur-execution-et-facade-api.md]

### Git Intelligence Summary

- Derniers changements : ExecutionTimeline, StructuredErrorCard, GET step logs, ExecutionWizard avec onRetry/onContact. ExecutionsPage reste un stub. listExecutions et GET /executions déjà utilisés côté backend et service frontend. [Source: sprint-status, 4-7]

### Latest Tech Information

- **Ant Design 6** : Table avec pagination, sort (controlled ou sorter dans columns), Skeleton, Drawer — pas de changement pour ce scope. [Source: Ant Design 6.x]
- **React** : Pas de dépendance spécifique ; hooks standards suffisent. [Source: architecture.md]

### Project Context Reference

- **Architecture** : [Source: planning-artifacts/architecture.md] — API patterns, ExecutionsPage, Table, pagination, skeleton, ExecutionTimeline.
- **Epics** : [Source: planning-artifacts/epics.md] — Story 4.8, FR22.
- **UX** : [Source: planning-artifacts/ux-design-specification.md] — Si spécifications détaillées pour la page Historique / Executions.

### References

- [Source: planning-artifacts/architecture.md] — Format API, composants, structure projet.
- [Source: planning-artifacts/epics.md] — Story 4.8 acceptance criteria.
- [Source: idp-portal/backend/app/api/v1/executions.py] — GET "" (list), GET /{id}, GET /{id}/steps.
- [Source: idp-portal/backend/app/repositories/execution_repository.py] — list_by_user, get_by_id, get_steps_by_execution_id.
- [Source: idp-portal/frontend/src/components/execution/ExecutionTimeline.tsx] — Réutilisation en mode historique.
- [Source: idp-portal/frontend/src/services/execution_service.ts] — listExecutions, getExecution, getExecutionSteps.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

Aucun problème majeur rencontré.

### Completion Notes List

- **Task 1**: ExecutionsPage.tsx implémenté avec Table Ant Design, colonnes (action, environnement, statut, date, durée), états loading/error/data, tri côté client, pagination 25/page, skeleton pendant le chargement.
- **Task 2**: Badge "processing" bleu pulsé pour les exécutions RUNNING/SUBMITTED/PENDING_APPROVAL. Ces exécutions sont triées en premier.
- **Task 3**: Drawer 480px avec ExecutionTimeline en mode "historical" (props execution + steps, pas de WebSocket). Titre dynamique "Exécution — [action_name]".
- **Task 4**: API GET /executions vérifié — retourne déjà les exécutions de l'utilisateur courant via JWT, limit/offset supportés. Code review: ajout pagination `{ data, pagination: { total_count, ... } }` (AC4 Task 4.2).
- **Task 5**: 18 tests frontend (ExecutionsPage.test.tsx), tests backend list_executions mis à jour (pagination). Test drawer erreur ajouté.
- **Code review 2026-01-30**: 2 HIGH + 4 MEDIUM corrigés — erreur chargement détail affichée dans le drawer (Alert), API retourne total_count (count_by_user + réponse paginée), useCallback stable (sans totalCount), skeleton en forme de table (lignes), test erreur drawer.

### File List

- `idp-portal/frontend/src/pages/ExecutionsPage.tsx` (modified)
- `idp-portal/frontend/src/pages/ExecutionsPage.test.tsx` (created)
- `idp-portal/frontend/src/services/execution_service.ts` (modified — listExecutions retourne ListExecutionsResponse avec pagination)
- `idp-portal/backend/app/api/v1/executions.py` (modified — list_executions retourne pagination)
- `idp-portal/backend/app/repositories/execution_repository.py` (modified — count_by_user)
- `idp-portal/backend/tests/unit/test_execution_api.py` (modified — tests list avec pagination)

## Change Log

- 2026-01-30: Story 4.8 implémentée — Table historique exécutions avec pagination, tri, drawer ExecutionTimeline mode historique. 17 tests frontend ajoutés.
- 2026-01-30: Code review — pagination API (total_count), erreur drawer, skeleton table, useCallback stable. 18 tests frontend, 3 tests list backend.
