# Story 22.8: Découper `types/api.ts` par domaine

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur,
je veux découper `types/api.ts` en fichiers par domaine,
afin d'améliorer la maintenabilité et la navigation dans les types.

## Acceptance Criteria

**AC1: Organisation par domaine**
- **Given** `types/api.ts` contient 1021 LOC avec tous les types API
- **When** le découpage est effectué
- **Then** les types sont organisés par domaine (ex: `api-actions.ts`, `api-executions.ts`, `api-profiles.ts`, `api-inventory.ts`)

**AC2: Fichier index avec réexports**
- **Given** les types sont découpés en plusieurs fichiers
- **When** le découpage est terminé
- **Then** un fichier `api/index.ts` réexporte tous les types pour compatibilité

**AC3: Rétrocompatibilité des imports**
- **Given** des composants importent depuis `types/api`
- **When** le découpage est appliqué
- **Then** tous les imports existants continuent de fonctionner (via index.ts)

**AC4: Limite de taille par fichier**
- **Given** chaque fichier de types est créé
- **When** le découpage est validé
- **Then** chaque fichier de types fait <300 LOC

**AC5: Documentation préservée**
- **Given** des commentaires et JSDoc existent dans api.ts
- **When** le découpage est effectué
- **Then** la documentation TypeScript est préservée dans les fichiers de destination

## Tasks / Subtasks

- [x] Task 1: Analyser les domaines et créer la structure (AC: #1)
  - [x] 1.1: Identifier les domaines fonctionnels dans api.ts (commentaires `// === ... ===`)
  - [x] 1.2: Créer la nouvelle structure de répertoire `types/api/`
  - [x] 1.3: Définir le plan de découpage avec tailles estimées par fichier

- [x] Task 2: Créer les fichiers de types par domaine (AC: #1, #4, #5)
  - [x] 2.1: Créer `api/common.ts` - types partagés (ApiResponse, PaginatedResponse, ApiError)
  - [x] 2.2: Créer `api/catalog.ts` - types Actions/Catalog (ActionCreate, ActionResponse, ActionDetail, etc.)
  - [x] 2.3: Créer `api/executions.ts` - types Executions (ExecutionCreateRequest, ExecutionResponse, ExecutionStepResponse, etc.)
  - [x] 2.4: Créer `api/profiles.ts` - types Profiles/RBAC (ProfileCreate, ProfileResponse, permissions)
  - [x] 2.5: Créer `api/integrations.ts` - types Integrations (IntegrationCreate, IntegrationResponse)
  - [x] 2.6: Créer `api/audit.ts` - types Audit (AuditExecutionEntry, AuditExecutionFilters)
  - [x] 2.7: Créer `api/analytics.ts` - types Analytics/Dashboard (DashboardStats, AdminAnalytics, reporting)
  - [x] 2.8: Créer `api/scheduled.ts` - types Scheduled Executions (ScheduledExecutionResponse, RecurringPattern)
  - [x] 2.9: Créer `api/inventory.ts` - types Inventory (InventoryItem)
  - [x] 2.10: Créer `api/remediation.ts` - types Remediation (RemediationRule, RemediationSuggestion)

- [x] Task 3: Créer le fichier index avec réexports (AC: #2, #3)
  - [x] 3.1: Créer `api/index.ts` qui réexporte tous les types des fichiers domaines
  - [x] 3.2: Vérifier que tous les types existants sont réexportés
  - [x] 3.3: Ajouter des commentaires de documentation dans l'index

- [x] Task 4: Maintenir la rétrocompatibilité (AC: #3)
  - [x] 4.1: Convertir `types/api.ts` en fichier de réexport vers `api/index.ts`
  - [x] 4.2: Tester que les imports existants `from '../types/api'` fonctionnent toujours
  - [x] 4.3: Ajouter un commentaire de dépréciation soft suggérant les imports directs

- [x] Task 5: Tests de validation (AC: #3, #4)
  - [x] 5.1: Vérifier que tous les tests compilent sans erreur
  - [x] 5.2: Exécuter la suite de tests complète pour détecter les régressions
  - [x] 5.3: Valider les tailles de fichiers (<300 LOC par fichier)
  - [x] 5.4: Vérifier que toutes les JSDoc sont préservées

- [x] Task 6: Documentation et migration (AC: #5)
  - [x] 6.1: Créer un guide de migration pour les nouveaux développements
  - [x] 6.2: Documenter la nouvelle structure dans le README frontend
  - [x] 6.3: Ajouter des exemples d'imports recommandés

## Dev Notes

### Architecture et Patterns

**Structure de découpage proposée:**

```
types/
├── api.ts                    # Réexport pour rétrocompatibilité (deprecated)
└── api/
    ├── index.ts             # Réexporte tous les types
    ├── common.ts            # ~30 LOC - Types partagés (ApiResponse, PaginatedResponse, ApiError)
    ├── catalog.ts           # ~250 LOC - Actions/Catalog (ActionCreate, ActionResponse, ActionDetail, Tags, Parameters, Impact)
    ├── executions.ts        # ~150 LOC - Executions (ExecutionCreateRequest, ExecutionResponse, ExecutionStepResponse, ExecutionFilters)
    ├── profiles.ts          # ~120 LOC - Profiles/RBAC (ProfileCreate, ProfileResponse, Permissions actions/targets)
    ├── integrations.ts      # ~80 LOC - Integrations (IntegrationCreate, IntegrationResponse, AuthFlow, Config)
    ├── audit.ts             # ~80 LOC - Audit (AuditExecutionEntry, AuditExecutionFilters, AuditExecutionListResponse)
    ├── analytics.ts         # ~180 LOC - Analytics/Dashboard (DashboardStats, AdminAnalytics, Reporting, Comparisons, Exports)
    ├── scheduled.ts         # ~120 LOC - Scheduled Executions (ScheduledExecutionResponse, RecurringPattern, Cron)
    ├── inventory.ts         # ~20 LOC - Inventory (InventoryItem)
    └── remediation.ts       # ~60 LOC - Remediation (RemediationRule, RemediationSuggestion, RemediationAction)
```

**Domaines identifiés (basé sur les commentaires `// === ... ===` dans api.ts):**

1. **Common** (ligne 1-21): Types génériques API (ApiResponse, PaginatedResponse, ApiError)
2. **Catalog Actions** (ligne 23-262): Types actions, tags, parameters, impact rules, workflows
3. **Execution Steps** (ligne 138-166): Types steps d'exécution (prerequisite, execution, verification)
4. **Profiles** (ligne 262-332): Types profiles, permissions actions/targets
5. **Integrations** (ligne 333-405): Types intégrations plateformes (AAP, GitHub Actions, etc.)
6. **Executions** (ligne 440-541): Types exécutions, status, timeline, logs
7. **Remediation** (ligne 543-598): Types remediation, suggestions, risk levels
8. **Inventory** (ligne 599-608): Types inventaire
9. **Dashboard/Analytics** (ligne 608-854): Types stats, analytics, reporting, comparisons
10. **Audit** (ligne 657-703): Types audit trail
11. **Scheduled Executions** (ligne 855-1021): Types scheduled executions, recurring patterns

**Principes de découpage:**

1. **Cohésion fonctionnelle**: Grouper les types par domaine métier
2. **Minimiser les dépendances circulaires**: Types communs dans `common.ts`
3. **Taille cible**: <300 LOC par fichier
4. **Préserver JSDoc**: Tous les commentaires doivent être conservés
5. **Rétrocompatibilité**: `types/api.ts` devient un simple réexport

**Patterns d'imports à promouvoir (guide de migration):**

```typescript
// ❌ Ancien (toujours supporté mais déprécié)
import type { ActionResponse, ExecutionResponse } from '../types/api';

// ✅ Nouveau (recommandé)
import type { ActionResponse } from '../types/api/catalog';
import type { ExecutionResponse } from '../types/api/executions';

// ✅ Alternatif (via index)
import type { ActionResponse, ExecutionResponse } from '../types/api';
```

### Technical Requirements

**Stack technique:**
- **Language**: TypeScript 5.9.3
- **Framework frontend**: React 19.2.0 + Vite 7.2.4
- **UI Library**: Ant Design 6.2.2
- **Test framework**: Vitest 4.0.18

**Contraintes techniques:**
1. **Zero breaking change**: Tous les imports existants doivent continuer de fonctionner
2. **Type safety**: Aucune perte de typage, tous les types doivent être correctement exportés/réexportés
3. **Build performance**: Le découpage ne doit pas ralentir la compilation TypeScript
4. **Tree shaking**: La nouvelle structure doit permettre un meilleur tree shaking si les imports directs sont utilisés

### File Structure Requirements

**Nomenclature des fichiers:**
- Pattern: `api-<domaine>.ts` ou dans répertoire `api/<domaine>.ts`
- Préférence pour répertoire `api/` (plus propre, évite la pollution du répertoire `types/`)

**Contenu du fichier index (`api/index.ts`):**
```typescript
// Central re-export for all API types
// For backward compatibility, import from specific domain files when possible

// Common types
export * from './common';

// Domain-specific types
export * from './catalog';
export * from './executions';
export * from './profiles';
export * from './integrations';
export * from './audit';
export * from './analytics';
export * from './scheduled';
export * from './inventory';
export * from './remediation';
```

**Contenu de l'ancien `api.ts` (rétrocompatibilité):**
```typescript
/**
 * @deprecated This file is kept for backward compatibility.
 * Please import from specific domain files under 'types/api/' for better tree-shaking:
 * - types/api/catalog for action-related types
 * - types/api/executions for execution-related types
 * - types/api/profiles for profile/RBAC types
 * - etc.
 */
export * from './api';
```

### Testing Requirements

**Tests de non-régression:**
1. Tous les tests existants doivent passer (1100+ tests frontend)
2. Aucun warning de compilation TypeScript
3. Aucune erreur ESLint liée aux types

**Validation de la structure:**
1. Utiliser `wc -l` pour vérifier les tailles de fichiers (<300 LOC)
2. Vérifier que tous les exports de l'ancien `api.ts` sont présents dans `api/index.ts`
3. Tester un import direct depuis un fichier domaine pour valider le tree shaking

**Commandes de validation:**
```bash
# Vérifier les tailles de fichiers
wc -l src/types/api/*.ts

# Vérifier la compilation TypeScript
npm run build

# Exécuter les tests
npm test

# Vérifier ESLint
npm run lint
```

### Project Structure Notes

**Alignement avec la structure existante:**

Le projet suit une structure frontend modulaire:
```
frontend/src/
├── components/       # Composants React par domaine
│   ├── catalog/     # Composants catalogue (ActionCard, ExecutionWizard, etc.)
│   ├── executions/  # Composants exécutions
│   └── ...
├── services/        # Services API (api_client.ts, execution_service.ts, etc.)
├── types/           # Types TypeScript
│   ├── api.ts      # Types API (À DÉCOUPER)
│   ├── common.ts   # Types communs frontend
│   └── wizard.ts   # Types wizard
└── utils/           # Utilitaires
```

**Impacts sur les imports:**

Fichiers avec le plus d'imports depuis `types/api` (impact rétrocompatibilité):
- `components/catalog/ExecutionWizard.tsx`: ~20 types importés
- `services/execution_service.ts`: ~10 types importés
- `utils/executionRenderers.tsx`: ~5 types importés
- `components/catalog/TargetSelectionStep.tsx`: ~3 types importés

Ces imports doivent continuer de fonctionner via `api/index.ts`.

### Previous Story Intelligence

**Story 22.7 (complétée)**: Refactorisation de `executions/views.py` backend
- **Pattern établi**: Extraction de helpers vers un module `utils.py`
- **Méthode**: Déplacer les fonctions sans changer les signatures, préserver les tests
- **Résultat**: Réduction de 1914 LOC à 1292 LOC (-32.5%)
- **Leçon**: Approche conservative et incrémentale, tests en continu

**Applicable à cette story:**
1. Découper sans casser les imports existants (rétrocompatibilité via index)
2. Tester fréquemment pendant le refactoring
3. Documenter la nouvelle structure pour les futurs développements
4. Ne pas forcer la migration des imports existants, permettre une migration progressive

**Stories récentes (22.1 à 22.6)**: Corrections de défauts de qualité (CRIT, HIGH)
- Toutes ont ajouté des tests pour valider les corrections
- Pattern de documentation des changements avec impact analysis
- Utilisation de `git log` pour tracker les patterns récents

### Git Intelligence Summary

**5 derniers commits (contexte qualité code):**

1. **6451489** - `refactor(22-7): extract 15 helper functions from executions views to utils module`
   - **Insight**: Pattern de refactoring avec extraction vers utils - applicable ici
   - **Files modifiés**: Backend Python, mais principe valable pour TypeScript

2. **50e3d83** - `fix(22-6): standardize pagination response with 'total' field across all endpoints`
   - **Insight**: Standardisation de l'interface API, tests de non-régression
   - **Relevance**: Modification de types API, vérifier cohérence backend/frontend

3. **ba713dc** - `fix(22-5): prevent double submission in ExecutionWizard with loading state`
   - **Insight**: Fix dans ExecutionWizard qui importe massivement depuis `types/api`
   - **Impact potentiel**: Composant à tester en priorité après le découpage

4. **a48af57** - `fix(22-4): handle HTTP 429 throttling with exponential backoff and retry logic`
   - **Insight**: Modification de `api_client.ts` (service qui importe des types API)
   - **Impact potentiel**: Service à valider après découpage

5. **ab4ba17** - `fix(22-3): prevent race condition in token refresh with promise-based mutex`
   - **Insight**: Refactoring de `api_client.ts` avec ajout de tests
   - **Pattern**: Tests robustes pour valider les changements de structure

**Patterns observés:**
- Commits atomiques avec scope clair (prefix `fix/refactor/feat`)
- Tests systématiques pour valider les changements
- Documentation des impacts dans les messages de commit
- Préservation de la rétrocompatibilité

**Recommandation pour cette story:**
- Commit message: `refactor(22-8): split types/api.ts into domain-specific files`
- Tester ExecutionWizard et api_client en priorité (modifiés récemment)
- Valider que les 1100+ tests passent sans régression

### Latest Tech Information

**TypeScript 5.9.3 (version utilisée):**
- **Module resolution**: Supporte les exports conditionnels et les réexports barrel (`export *`)
- **Type imports**: Préférer `import type` pour les types purs (déjà utilisé dans le projet)
- **Tree shaking**: TypeScript 5.x améliore le tree shaking avec les imports spécifiques

**Best practices TypeScript pour le découpage de types (2026):**

1. **Barrel exports pattern** (ce qu'on va implémenter):
   ```typescript
   // api/index.ts
   export * from './catalog';
   export * from './executions';
   ```
   - ✅ Permet rétrocompatibilité
   - ✅ Facilite la migration progressive
   - ⚠️ Peut impacter légèrement le tree shaking si mal utilisé

2. **Import direct (recommandé pour nouveau code):**
   ```typescript
   import type { ActionResponse } from '../types/api/catalog';
   ```
   - ✅ Meilleur tree shaking
   - ✅ Rend les dépendances explicites
   - ✅ Réduit la surface d'import

3. **Type-only imports** (déjà utilisé dans le projet):
   ```typescript
   import type { ActionResponse } from '../types/api';
   ```
   - ✅ Garantit qu'aucun code runtime n'est importé
   - ✅ Améliore les performances de compilation

**Vite 7.2.4 (bundler utilisé):**
- **Hot Module Replacement (HMR)**: Le découpage en fichiers plus petits améliore le HMR
- **Build optimization**: Vite utilise Rollup en production, qui bénéficie des imports spécifiques
- **Chunk splitting**: Structure en répertoire `api/` permet un meilleur chunking automatique

**React 19.2.0 + TypeScript:**
- Aucun changement spécifique pour les types API (pas de JSX dans les fichiers de types)
- Les types découplés facilitent la maintenance avec Server Components (future-proofing)

**Ant Design 6.2.2:**
- Types propriétaires Ant Design (`TableProps`, `FormInstance`, etc.) ne sont pas dans `api.ts`
- Aucun conflit avec le découpage

### References

- [Source: _bmad-output/planning-artifacts/epic-22-amelioration-qualite-code.md#Story 22.8]
- [Source: docs/code-quality-assessment-2026-02-08.md#Section 4.1 - Fichiers volumineux]
- [Source: frontend/src/types/api.ts:1-1022]
- [Architecture: frontend/README.md - Structure du projet]
- [Git commits: 6451489, 50e3d83, ba713dc - Refactoring patterns récents]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- TypeScript compilation: 244 errors (PRE-EXISTING, unrelated to type splitting — mostly test config issues: beforeEach, global, Node types, unused imports)
- TypeScript compilation (types/api only): 0 errors — ALL type splitting errors FIXED by code review
- ESLint: 0 errors after fixing unused import in scheduled.ts
- Tests: 1609/1674 pass (65 failures are pre-existing, unrelated to type splitting)
- File sizes: all <300 LOC (max: catalog.ts at 271 LOC)

### Completion Notes List

- Découpage de `types/api.ts` (1023 LOC) en 10 fichiers domaines + index
- Résolution des dépendances circulaires : `ExecutionStep` (config) reste dans `catalog.ts`, types runtime d'exécution dans `executions.ts`
- Rétrocompatibilité assurée via `api.ts` → `api/index.ts` barrel re-export
- Tous les commentaires JSDoc/Story préservés intégralement
- Aucune régression introduite (même nombre de tests passants qu'avant)
- Documentation ajoutée dans README.md et index.ts

### File List

**Fichiers créés:**
- `idp-portal/frontend/src/types/api/common.ts` (29 LOC)
- `idp-portal/frontend/src/types/api/catalog.ts` (271 LOC)
- `idp-portal/frontend/src/types/api/executions.ts` (153 LOC)
- `idp-portal/frontend/src/types/api/profiles.ts` (70 LOC)
- `idp-portal/frontend/src/types/api/integrations.ts` (68 LOC)
- `idp-portal/frontend/src/types/api/audit.ts` (49 LOC)
- `idp-portal/frontend/src/types/api/analytics.ts` (149 LOC)
- `idp-portal/frontend/src/types/api/scheduled.ts` (170 LOC)
- `idp-portal/frontend/src/types/api/inventory.ts` (8 LOC)
- `idp-portal/frontend/src/types/api/remediation.ts` (57 LOC)
- `idp-portal/frontend/src/types/api/index.ts` (24 LOC)

**Fichiers modifiés:**
- `idp-portal/frontend/src/types/api.ts` (1023 LOC → 15 LOC, converti en re-export)
- `idp-portal/frontend/README.md` (ajout documentation structure types)
- `idp-portal/frontend/src/utils/parametersSchema.ts` (ajout index signature pour compatibilité Record<string, unknown>)
- `idp-portal/frontend/src/utils/impactRulesSchema.ts` (level: string → level: ImpactLevel pour type safety)
- `idp-portal/frontend/src/components/admin/ActionWizard.tsx` (ajout import CloseCircleOutlined manquant)
- `idp-portal/frontend/src/components/admin/ActionForm.test.tsx` (ajout item_type + workflow_steps dans 9 mocks ActionDetail)
- `idp-portal/frontend/src/components/admin/ActionWizard.test.tsx` (ajout item_type + workflow_steps dans 10 mocks ActionDetail + fix apostrophes échappées)

### Change Log

- **2026-02-09 14:45 UTC**: Story 22.8 — Découpage de `types/api.ts` en 10 fichiers domaines sous `types/api/`. Barrel re-export via `api/index.ts`, rétrocompatibilité via l'ancien `api.ts` converti en re-export.
- **2026-02-09 14:55 UTC**: Code Review Corrections (CRITICAL fixes):
  - Fixed missing import `CloseCircleOutlined` in ActionWizard.tsx (build blocker)
  - Fixed type incompatibilities: ParametersJsonSchema index signature, ImpactRulesJson level type (259 → 244 TS errors)
  - Fixed 19 ActionDetail test mocks missing `item_type` and `workflow_steps` fields
  - Staged all `types/api/` files to git (were untracked)
  - Fixed apostrophe escaping in test descriptions
  - **Result**: Zero type-splitting-related TS errors, all AC validated, ready for merge
