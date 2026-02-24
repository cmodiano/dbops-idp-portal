# Story 38.6: Migration DIP services — composants vers hooks

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a développeur frontend,
I want migrer les composants qui importent directement des services (admin_service, catalog_service, execution_service, etc.) vers des hooks ou de l'injection (props/context),
so that le couplage direct aux services soit éliminé, facilitant les tests unitaires, la réutilisation et le respect du principe d'inversion des dépendances (SOLID-FE-4).

## Acceptance Criteria

1. **Premier lot de 5–8 composants migrés** — Les composants sélectionnés n'importent plus directement de fonctions runtime depuis les fichiers `*_service.ts`. Les imports `type`-only (erased at compile time) sont tolérés temporairement.
2. **Hook ou DI pour chaque migration** — Chaque composant migré consomme ses données via un hook dédié (nouveau ou existant) ou via props/context. Pattern de référence : `useCatalogState`, `useExecutionWizardState`, `useActionWizardState`.
3. **Aucune régression fonctionnelle** — Le comportement utilisateur est strictement identique avant/après migration. Les tests existants passent (`npm test` vert).
4. **Aucune régression visuelle** — Couleurs, libellés, layout inchangés.
5. **Tests existants verts** — `npm test` passe sans nouveaux échecs.
6. **Composants non migrés documentés** — Les composants hors périmètre de ce lot sont listés dans les Completion Notes avec raison (complexité, dépendance inter-story, etc.).

## Tasks / Subtasks

### Lot 1 — Composants prioritaires (runtime coupling, impact élevé)

- [x] Task 1 — Migrer `ExecutionView.tsx` (AC: #1, #2, #3)
  - [x] 1.1 Utiliser le hook existant `useExecutionDetail` au lieu d'appeler `getExecution` directement depuis `execution_service`
  - [x] 1.2 Utiliser `useCatalogState` ou créer un hook léger pour `fetchCatalogActionById` au lieu d'importer `catalog_service`
  - [x] 1.3 Supprimer tous les imports runtime de `execution_service` et `catalog_service`
  - [x] 1.4 Vérifier que le polling et le rafraîchissement temps réel fonctionnent toujours

- [x] Task 2 — Migrer `StepDetailDrawer.tsx` (AC: #1, #2, #3)
  - [x] 2.1 Utiliser `useExecutionDetail` ou `useExecutionPolling` pour `getExecution` + `getExecutionSteps`
  - [x] 2.2 Supprimer les imports directs de `execution_service`

- [x] Task 3 — Migrer `WorkflowExecutionGraph.tsx` (AC: #1, #2, #3)
  - [x] 3.1 Recevoir les données de steps via props (depuis le parent qui utilise déjà un hook) OU utiliser `useExecutionPolling`
  - [x] 3.2 Supprimer l'import direct de `getExecutionSteps` depuis `execution_service`

- [x] Task 4 — Migrer `PendingApprovalsList.tsx` (AC: #1, #2, #3)
  - [x] 4.1 Créer un hook `usePendingApprovals` wrappant `approveExecution` + `rejectExecution` depuis `execution_service`
  - [x] 4.2 Remplacer les imports directs dans le composant par le hook

- [x] Task 5 — Migrer `ExecutionsFiltersPanel.tsx` (AC: #1, #2, #3)
  - [x] 5.1 Utiliser `useExecutionsData` (existant) pour les données d'exécution
  - [x] 5.2 Utiliser `useCatalogState` pour `fetchCatalogActions` / `type CatalogAction`
  - [x] 5.3 Utiliser un hook pour `fetchExecutionTags` (existant dans `useExecutionsData` ou créer `useExecutionTags`)
  - [x] 5.4 Supprimer tous les imports directs de `execution_service` et `catalog_service`

- [x] Task 6 — Migrer `ExecutionsPage.tsx` (AC: #1, #2, #3)
  - [x] 6.1 Utiliser `useCancelExecution` (existant) au lieu d'importer `cancelExecution` depuis `execution_service`
  - [x] 6.2 Supprimer l'import direct

- [x] Task 7 — Migrer `CalendarPage.tsx` (AC: #1, #2, #3)
  - [x] 7.1 Créer un hook `useScheduledExecutions` wrappant `listScheduledExecutions` + `toggleRecurringPattern` depuis `scheduled_execution_service`
  - [x] 7.2 Remplacer les imports directs dans la page par le hook

- [x] Task 8 — Migrer `CalendarFiltersPanel.tsx` (AC: #1, #2, #3)
  - [x] 8.1 Utiliser `usePlatformIntegrations` ou `useServiceNowIntegrations` (existants) au lieu d'importer `getIntegrations` depuis `integrations_service`
  - [x] 8.2 Supprimer l'import direct

### Vérification finale

- [x] Task 9 — Lancer les tests et vérifier (AC: #3, #4, #5)
  - [x] 9.1 `npm test` — tous les tests passent
  - [x] 9.2 Vérification manuelle rapide : ExecutionView, StepDetailDrawer, PendingApprovals, ExecutionsPage, CalendarPage
  - [x] 9.3 Documenter les composants restants (hors lot 1) dans Completion Notes

## Dev Notes

### Contexte SOLID-FE-4

**Source :** `idp-portal/CODEBASE-REVIEW.md` §14 — SOLID-FE-4 [HIGH — AMÉLIORÉ, OUVERT].

L'audit a identifié ~25 composants non-test qui importent directement `admin_service`, `catalog_service`, `execution_service` ou d'autres services. Le couplage direct rend les composants difficiles à tester isolément et viole le principe d'inversion des dépendances.

### Pattern cible : hooks DIP

Le projet possède déjà **28+ hooks** qui suivent le pattern DIP. Les modèles de référence :

| Hook existant | Wraps | Pattern |
|---|---|---|
| `useCatalogState` | `catalog_service` (7 fonctions) | Aggregate state hook |
| `useExecutionWizardState` | Orchestre 5 hooks — zéro import service | Composition de hooks |
| `useActionWizardState` | `admin_service` (6 fonctions) | Aggregate state hook |
| `useProfileFormState` | `profiles_service` + `admin_service` | Multi-service hook |
| `useExecutionDetail` | `execution_service` + `catalog_service` | Single-concern hook |
| `useExecutionPolling` | `execution_service` (getExecution + getExecutionSteps) | Polling hook |
| `useExecutionsData` | `execution_service` + `integrations_service` | Data fetching hook |
| `useCancelExecution` | `scheduled_execution_service` | Action hook |

### Stratégie de migration

1. **Réutiliser les hooks existants** — Beaucoup de composants du lot 1 ont déjà un hook correspondant (`useExecutionDetail`, `useExecutionPolling`, `useCancelExecution`, `useCatalogState`). Privilégier la réutilisation.
2. **Créer des hooks seulement si nécessaire** — Pour `PendingApprovalsList` (approve/reject) et `CalendarPage` (scheduled executions), de nouveaux hooks légers sont nécessaires.
3. **Imports type-only tolérés** — Les `import type { CatalogAction }` sont erased at compile time et ne créent pas de couplage runtime. Ils peuvent rester temporairement ou être déplacés vers un fichier `types/` partagé dans un lot ultérieur.
4. **Admin components reportés** — Les composants `admin/` (ActionsAdminPanel, IntegrationsAdminPanel, ProfilesAdminPanel, ActionForm, etc.) sont complexes et couplés à de nombreuses fonctions admin_service. Ils seront traités dans un lot 2 futur.

### Composants sélectionnés pour le lot 1 (8 composants) — Justification

| Composant | Services couplés | Justification lot 1 |
|---|---|---|
| `ExecutionView.tsx` | `execution_service`, `catalog_service` | Hook existant `useExecutionDetail` disponible |
| `StepDetailDrawer.tsx` | `execution_service` | Hook existant `useExecutionPolling` disponible |
| `WorkflowExecutionGraph.tsx` | `execution_service` | Peut recevoir data via props ou hook existant |
| `PendingApprovalsList.tsx` | `execution_service` | Hook léger à créer (2 fonctions) |
| `ExecutionsFiltersPanel.tsx` | `execution_service`, `catalog_service` | Hooks existants `useExecutionsData` + `useCatalogState` |
| `ExecutionsPage.tsx` | `execution_service` | Hook existant `useCancelExecution` |
| `CalendarPage.tsx` | `scheduled_execution_service` | Hook léger à créer (2 fonctions) |
| `CalendarFiltersPanel.tsx` | `integrations_service` | Hook existant `usePlatformIntegrations` |

### Composants hors lot 1 (~17 restants)

**Admin pages (6)** — `ActionsAdminPanel`, `IntegrationsAdminPanel`, `ProfilesAdminPanel`, `ActionForm`, `BusinessRulesPolicyPanel`, `CategoriesAdminTable` — couplage lourd, nécessitent des hooks aggregate complexes.

**Admin components (7)** — `ActionPalette`, `BusinessRulePolicySelector`, `CategoryForm`, `EngineForm`, `EnginesAdminTable`, `IntegrationsTable`, `WizardStep1General`, `ProfileImportModal`, `RemediationRulesEditor`, `AdminAnalyticsDashboard` — effort modéré à élevé.

**Dashboard (2)** — `ExportButton`, `ReportingDashboard` — couplage à `dashboard_service`, lot 2.

**Catalog type-only (7)** — `ActionTable`, `ConfirmationStep`, `ExecutionWizard`, `ParametersFormStep`, `TagCloud`, `TargetSelectionStep`, `WorkflowStepsRenderer` — imports type-only, basse priorité.

### Ce qu'il ne faut PAS faire

- **Ne PAS refactorer la logique métier des composants** — cette story ne change que la source des données (direct → hook)
- **Ne PAS créer de Context providers** — les hooks suffisent pour ce lot. Context uniquement si un même état doit être partagé entre composants distants dans l'arbre
- **Ne PAS déplacer les types** dans un fichier `types/` partagé — c'est un effort séparé, basse priorité
- **Ne PAS migrer les composants admin** — trop complexes pour ce lot, faire un lot 2
- **Ne PAS modifier les services eux-mêmes** — seuls les composants changent
- **Ne PAS ajouter de nouveaux tests** — vérifier que les tests existants passent suffit

### Intelligence story précédente (38.5)

- Story 38.5 (audit except Exception) terminée avec succès — 70 occurrences dans 37 fichiers documentées/annotées
- Commit : `1666e75 docs(backend): audit and annotate all except Exception with noqa: BLE001 justifications (38-5)`
- Stories 38.1–38.4 toutes terminées et code-reviewed
- Pattern tests frontend : `npm test` (vitest + React Testing Library)
- Le frontend est stable — aucune régression introduite par les stories 38.1–38.5

### Commits récents pertinents

```
1666e75 docs(backend): audit and annotate all except Exception with noqa: BLE001 justifications (38-5)
d2c2cb7 refactor(backend): replace asyncio.run() with async_to_sync() in polling task (38-4)
adb8f83 fix(frontend): remove duplicate key prop on nested TopNav button element (NEW-FE-1)
0f21a08 refactor(frontend): consolidate duplicate status config into shared execution-status module (SOLID-FE-10)
3195fd7 fix(backend): quick wins N+1, double update, TODO obsolète, log execution_id
```

### Project Structure Notes

- Frontend : `idp-portal/frontend/src/`
- Services : `idp-portal/frontend/src/services/`
- Hooks : `idp-portal/frontend/src/hooks/`
- Components : `idp-portal/frontend/src/components/`
- Pages : `idp-portal/frontend/src/pages/`
- Tests : `npm test` (vitest + React Testing Library)
- Build : `npm run build` (Vite)
- Pas de conflit avec la structure existante

### References

- [Source: idp-portal/CODEBASE-REVIEW.md §14 — SOLID-FE-4 DIP services, HIGH — AMÉLIORÉ, OUVERT]
- [Source: _bmad-output/planning-artifacts/epic-38-codebase-review-audit-3-corrections.md — Story 38.6]
- [Source: _bmad-output/implementation-artifacts/38-5-audit-except-exception-residuels-documentation.md — story précédente]
- [Source: idp-portal/frontend/src/hooks/ — 28+ hooks DIP existants]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Build error: `useState is not defined` dans WorkflowExecutionGraph.tsx — corrigé en rajoutant `useState` à l'import (toujours utilisé pour `selectedStepId`)
- Build warning: imports inutilisés (`CatalogActionDetail` dans ExecutionView, `logger` dans WorkflowExecutionGraph) — supprimés

### Completion Notes List

**8 composants migrés (lot 1 complet) :**
1. `ExecutionView.tsx` — nouveau hook `useExecutionView` (wraps getExecution + fetchCatalogActionById). Le hook existant `useExecutionDetail` n'était pas adapté (gère drawer/URL routing, incompatible avec le pattern contrôlé par props).
2. `StepDetailDrawer.tsx` — nouveau hook `useChildExecution` (wraps getExecution + getExecutionSteps pour child_execution_id).
3. `WorkflowExecutionGraph.tsx` — nouveau hook `useExecutionSteps` (wraps getExecutionSteps pour terminal fetch). L'import de `logger` est aussi supprimé (déplacé dans le hook).
4. `PendingApprovalsList.tsx` — nouveau hook `usePendingApprovals` (wraps approveExecution + rejectExecution).
5. `ExecutionsFiltersPanel.tsx` — nouveau hook `useExecutionFilterOptions` (wraps fetchExecutionTags + fetchCatalogActions).
6. `ExecutionsPage.tsx` — nouveau hook `useCancelRunningExecution` (wraps cancelExecution pour exécutions courantes). Distinct de `useCancelExecution` qui gère les scheduled executions.
7. `CalendarPage.tsx` — nouveau hook `useScheduledExecutions` (wraps listScheduledExecutions + toggleRecurringPattern).
8. `CalendarFiltersPanel.tsx` — nouveau hook `useIntegrations` (wraps getIntegrations). Créé plutôt que réutiliser `usePlatformIntegrations` pour éviter une régression fonctionnelle (filtrage par role='platform' vs toutes les intégrations).

**8 hooks créés :**
- `useExecutionView` — données ExecutionView (execution + action detail workflow)
- `useChildExecution` — données child execution pour StepDetailDrawer
- `useExecutionSteps` — fetch one-time des steps pour terminal executions
- `usePendingApprovals` — approve/reject actions
- `useExecutionFilterOptions` — tags + catalog actions pour filtres
- `useCancelRunningExecution` — cancel execution courante
- `useScheduledExecutions` — list + toggle récurrence scheduled executions
- `useIntegrations` — toutes les intégrations (pour platform filter)

**Composants hors lot 1 (~17 restants, documentés dans Dev Notes) :**
- Admin pages (6) : `ActionsAdminPanel`, `IntegrationsAdminPanel`, `ProfilesAdminPanel`, `ActionForm`, `BusinessRulesPolicyPanel`, `CategoriesAdminTable` — couplage lourd admin_service
- Admin components (7+) : `ActionPalette`, `BusinessRulePolicySelector`, `CategoryForm`, `EngineForm`, `EnginesAdminTable`, `IntegrationsTable`, `WizardStep1General`, `ProfileImportModal`, `RemediationRulesEditor`, `AdminAnalyticsDashboard` — effort modéré à élevé
- Dashboard (2) : `ExportButton`, `ReportingDashboard` — couplage dashboard_service
- Catalog type-only (7) : imports type-only (erased at compile time), basse priorité

**Tests : 182/182 fichiers, 2500/2500 tests passent. Build Vite OK.**

### File List

- `idp-portal/frontend/src/hooks/useExecutionView.ts` (NEW)
- `idp-portal/frontend/src/hooks/useChildExecution.ts` (NEW)
- `idp-portal/frontend/src/hooks/useExecutionSteps.ts` (NEW)
- `idp-portal/frontend/src/hooks/usePendingApprovals.ts` (NEW)
- `idp-portal/frontend/src/hooks/useExecutionFilterOptions.ts` (NEW)
- `idp-portal/frontend/src/hooks/useCancelRunningExecution.ts` (NEW)
- `idp-portal/frontend/src/hooks/useScheduledExecutions.ts` (NEW)
- `idp-portal/frontend/src/hooks/useIntegrations.ts` (NEW)
- `idp-portal/frontend/src/components/execution/ExecutionView.tsx` (MODIFIED)
- `idp-portal/frontend/src/components/execution/StepDetailDrawer.tsx` (MODIFIED)
- `idp-portal/frontend/src/components/execution/WorkflowExecutionGraph.tsx` (MODIFIED)
- `idp-portal/frontend/src/components/dashboard/PendingApprovalsList.tsx` (MODIFIED)
- `idp-portal/frontend/src/components/executions/ExecutionsFiltersPanel.tsx` (MODIFIED)
- `idp-portal/frontend/src/pages/ExecutionsPage.tsx` (MODIFIED)
- `idp-portal/frontend/src/pages/CalendarPage.tsx` (MODIFIED)
- `idp-portal/frontend/src/components/calendar/CalendarFiltersPanel.tsx` (MODIFIED)

## Change Log

- 2026-02-23: Story 38.6 — Migration DIP services vers hooks pour 8 composants du lot 1. 8 hooks créés, 8 composants migrés. Zéro import runtime de *_service.ts dans les composants migrés. 182/182 tests passent, build OK.
- 2026-02-23: Code Review (AI) — 7 issues trouvés (1 HIGH, 3 MEDIUM, 3 LOW). 4 fixes appliqués : (H1) ajout cancelRunningExecution aux deps de handleCancelExecution dans ExecutionsPage, (M1) remplacement cast unsafe `as Error` par `instanceof` dans useScheduledExecutions, (M2) ajout état error dans useIntegrations, (M3) fusion des 2 useEffect en Promise.all dans useExecutionFilterOptions. (L3) correction comptage "7 hooks" → "8 hooks" dans Completion Notes.
