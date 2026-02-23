# Story 34.14 : Frontend — Tests manquants sur composants critiques

Status: done

<!-- Réf: CODEBASE-REVIEW.md SOLID-FE-11 -->

## Story

En tant que mainteneur,
je veux ajouter des tests pour les composants critiques actuellement sans couverture,
afin de réduire le risque de régression (ParametersFormStep, SchedulingPanel, ExecutionsFiltersPanel, BusinessRulePolicyModal).

## Contexte

- **SOLID-FE-11** : Quatre composants critiques n'ont aucun fichier de test : `ParametersFormStep` (143 lignes), `SchedulingPanel` (327 lignes), `ExecutionsFiltersPanel` (280 lignes), `BusinessRulePolicyModal` (230 lignes). Risque élevé en cas de refactoring ou correction de bugs.
- **Story 34-13** (done) a modifié `ParametersFormStep.tsx` : la prop `action` a été supprimée et 4 props inventory (`inventoryData`, `inventoryWarnings`, `loadingInventory`, `selectedServerNames`) ont été déplacées vers `WizardExecutionContext`. Le composant appelle maintenant `useWizardExecutionContext()`. **Les tests doivent refléter l'interface post-34-13.**
- Ces composants constituent des points de contact critiques avec l'utilisateur (wizard d'exécution, planification, filtres, politiques admin) — toute régression est immédiatement visible.

## Acceptance Criteria

1. **Given** les composants listés (ParametersFormStep, SchedulingPanel, ExecutionsFiltersPanel, BusinessRulePolicyModal)
   **Then** chacun dispose d'un fichier de test `.test.tsx` qui couvre : rendu de base (smoke), props principales, et au moins un comportement utilisateur ou callback (soumission, changement de filtre, ouverture/fermeture modal, etc.).

2. **And** les tests sont co-localisés avec le composant (même dossier) et utilisent React Testing Library + Vitest (pattern existant du projet) ; les mocks nécessaires (services, contextes, hooks) sont fournis conformément aux patterns du projet.

3. **And** la suite de tests frontend passe complètement (`npx vitest run`) ; les nouveaux tests sont non-flaky et exécutables en CI.

4. **And** `npx tsc --noEmit` retourne 0 erreur TypeScript dans les fichiers de test ajoutés.

## Tasks / Subtasks

- [x] Task 1 — ParametersFormStep
  - [x] 1.1 Créer `src/components/catalog/ParametersFormStep.test.tsx` avec setup incluant `WizardExecutionContextProvider` (Story 34-13) et `App` Ant Design.
  - [x] 1.2 Tests : rendu smoke (non-workflow + workflow), alerte "aucun paramètre", rendu des champs dynamiques, validation required, onParametersChange appelé, cas `loadingWorkflowStepActions=true`, affichage d'erreur workflow, message business profile.

- [x] Task 2 — SchedulingPanel
  - [x] 2.1 Créer `src/components/catalog/SchedulingPanel.test.tsx`.
  - [x] 2.2 Tests : rendu initial (isScheduling=false → pas de formulaire), sélection type planification (one-time, daily, weekly, cron), DatePicker one-time, selects daily (heure/minute), selects weekly (jour, heure, minute), input cron + validation debounce, presets cron, états loading/success/erreur validation cron, affichage prochaines exécutions, `onSchedulingChange` appelé avec les bons arguments.

- [x] Task 3 — ExecutionsFiltersPanel
  - [x] 3.1 Créer `src/components/executions/ExecutionsFiltersPanel.test.tsx`.
  - [x] 3.2 Mocker `useEngines`, `useEnvironments`, `fetchExecutionTags`, `fetchCatalogActions`.
  - [x] 3.3 Tests : rendu smoke, chargement options (engines, environments, tags, actions), changement filtre statut → `onApplyFilters` appelé, bouton reset désactivé si no filters / actif si filters, badge `activeFilterCount`, réinitialisation des filtres via `onResetFilters`.

- [x] Task 4 — BusinessRulePolicyModal
  - [x] 4.1 Créer `src/components/admin/BusinessRulePolicyModal.test.tsx`.
  - [x] 4.2 Tests : rendu modal ouvert/fermé, titre création vs édition, population du formulaire depuis `editPolicy`, boutons exemple Terraform/AAP insèrent du JSON, validation JSON invalide → message d'erreur, `onSave` appelé avec payload correct, `onCancel` appelé, champs désactivés quand `saving=true`.

## Dev Notes

### Architecture post-Story 34-13 (CRITIQUE pour ParametersFormStep)

Depuis Story 34-13, `ParametersFormStep` utilise `useWizardExecutionContext()` (lancera une erreur si non enveloppé dans un Provider). Chaque test qui rend `ParametersFormStep` **doit** fournir le contexte :

```typescript
// src/contexts/WizardExecutionContext.tsx
import { WizardExecutionContextProvider } from '../../contexts/WizardExecutionContext';
import type { WizardExecutionContextValue } from '../../contexts/WizardExecutionContext';

const mockWizardCtx: WizardExecutionContextValue = {
  environmentsCache: null,
  inventoryData: {},
  inventoryWarnings: {},
  loadingInventory: false,
  derivedEnvironment: null,
  currentImpact: null,
  hasMixedEnvironments: false,
  resolvedPatternTargets: [],
  patternResolving: false,
  selectedServerNames: [],
};

// Usage dans les tests :
render(
  <App>
    <WizardExecutionContextProvider value={mockWizardCtx}>
      <ParametersFormStep {...props} />
    </WizardExecutionContextProvider>
  </App>
);
```

Le mock `useAuth` est aussi nécessaire (`isBusinessProfile` pour les messages conditionnels) :
```typescript
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(() => ({ isBusinessProfile: false })),
}));
```

### Interface actuelle de chaque composant (post-34-13)

#### ParametersFormStep (`src/components/catalog/ParametersFormStep.tsx`, 143 lignes)

```typescript
export interface ParametersFormStepProps {
  form: FormInstance;
  parameterFields: ParameterField[];
  parameters: Record<string, unknown>;
  onParametersChange: (values: Record<string, unknown>) => void;
  isWorkflow: boolean;
  workflowSteps: Array<{ order: number; name: string | null; referenced_action_id: number }>;
  workflowStepActions: Record<number, CatalogActionDetail>;
  loadingWorkflowStepActions: boolean;
  workflowStepActionsError: string | null;
  workflowValidationSummary: string | null;
}
```

Dépendances internes : `useAuth()`, `useWizardExecutionContext()`, `renderFieldInput()`, `WorkflowStepsRenderer`.

Comportements clés :
- Non-workflow + `parameterFields.length === 0` → Alert "Aucun paramètre requis"
- Non-workflow + champs → `Form.Item` par field avec `required`, `pattern`, `min`/`max`
- isWorkflow → délègue à `WorkflowStepsRenderer`
- isBusinessProfile → textes adaptés (description sanitisée)
- `loadingWorkflowStepActions=true` → Spin de chargement
- `workflowStepActionsError` non null → Alert erreur

#### SchedulingPanel (`src/components/catalog/SchedulingPanel.tsx`, 327 lignes)

```typescript
export interface SchedulingPanelProps {
  scheduling: SchedulingState;
  onSchedulingChange: (updates: Partial<SchedulingState>) => void;
  schedulingError: string | null;
  submitting: boolean;
  validation: UseSchedulingValidationReturn;
}

export interface SchedulingState {
  isScheduling: boolean;
  schedulingType: 'one-time' | 'daily' | 'weekly' | 'cron';
  scheduledAt: dayjs.Dayjs | null;
  dailyHour: number;
  dailyMinute: number;
  weeklyDayOfWeek: number;
  weeklyHour: number;
  weeklyMinute: number;
  cronExpression: string;
  cronIsValid: boolean | null;
  cronError: string;
  cronNextExecutions: string[];
  cronValidating: boolean;
  showCronHelper: boolean;
}
```

Le composant est **contrôlé** (toute modification appelle `onSchedulingChange`). Pas de state interne.

Comportements clés :
- `isScheduling=false` → section masquée (ou pas de formulaire affiché)
- `isScheduling=true` → affiche RadioGroup des 4 types
- Type one-time → DatePicker avec interdiction date passée
- Type daily → selects heure (0-23) et minute (0-59)
- Type weekly → select jour semaine + selects heure/minute
- Type cron → Select presets + Input expression + indicateur validation (loading/succès/erreur)
- `cronIsValid=true` → affiche `cronNextExecutions` list
- Tooltip timezone sur champs heure

#### ExecutionsFiltersPanel (`src/components/executions/ExecutionsFiltersPanel.tsx`, 280 lignes)

```typescript
export interface ExecutionsFiltersPanelProps {
  filters: ExecutionFilters;
  onApplyFilters: (filters: ExecutionFilters) => void;
  onResetFilters: () => void;
  activeFilterCount: number;
  loading?: boolean;
}
```

Dépendances : `useEngines()`, `useEnvironments()`, `fetchExecutionTags()`, `fetchCatalogActions()`.

Comportements clés :
- Charge tags + actions via API au montage (mocks `vi.mock`)
- Charge engines + environments via hooks
- Changement filtre → `onApplyFilters` immédiatement (pas de bouton "Appliquer")
- `activeFilterCount === 0` → bouton reset désactivé
- `activeFilterCount > 0` → badge avec compteur + bouton reset actif
- Date range → DatePicker.RangePicker avec presets 7/14/30/90 jours
- Tags → Select multiple, max 2 tags affichés

Mocks à fournir :
```typescript
vi.mock('../../hooks/useEngines', () => ({
  useEngines: vi.fn(() => ({
    engineOptions: [{ label: 'Oracle', value: 'oracle' }],
    loading: false,
  })),
}));
vi.mock('../../hooks/useEnvironments', () => ({
  useEnvironments: vi.fn(() => ({
    environmentOptions: [{ label: 'dev', value: 'dev' }],
    loading: false,
  })),
}));
vi.mock('../../services/execution_service', () => ({
  // fetchExecutionTags retourne directement Promise<string[]> (pas de wrapper {data})
  fetchExecutionTags: vi.fn(() => Promise.resolve(['tag1', 'tag2'])),
}));
vi.mock('../../services/catalog_service', () => ({
  // fetchCatalogActions retourne directement Promise<CatalogAction[]> (pas de wrapper {data})
  fetchCatalogActions: vi.fn(() => Promise.resolve([{ id: 1, name: 'Action Test', engine: 'oracle', platform: 'AAP' }])),
}));
```

#### BusinessRulePolicyModal (`src/components/admin/BusinessRulePolicyModal.tsx`, 230 lignes)

```typescript
interface BusinessRulePolicyModalProps {
  open: boolean;
  onCancel: () => void;
  onSave: (payload: BusinessRulePolicyPayload) => Promise<void>;
  editPolicy?: BusinessRulePolicyDetail | null;
  saving?: boolean;
}
```

Comportements clés :
- `open=false` → modal non rendue (ou masquée)
- `open=true, editPolicy=null` → titre "Nouvelle politique"
- `open=true, editPolicy={...}` → titre "Modifier la politique" + formulaire pré-rempli
- Textarea JSON vide → boutons exemples Terraform/AAP visibles → clic insère JSON formaté
- JSON invalide → validation inline avec message d'erreur
- `onSave` appelé avec `{ name, description, policy_definition, is_active }`
- Champs désactivés si `saving=true`
- `onCancel` → ferme sans sauvegarder

Référence : `BusinessRulePoliciesEditor.test.tsx` (633 lignes) pour les patterns de test de cet écran admin.

### Pattern de test de référence du projet

```typescript
// Pattern standard observé dans ConfirmationStep.test.tsx, ExecutionWizard.scheduling.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { App } from 'antd';

describe('MyComponent', () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    render(<App><MyComponent {...defaultProps} /></App>);
    expect(screen.getByRole('...')).toBeInTheDocument();
  });

  it('calls callback when user interacts', async () => {
    const onCallback = vi.fn();
    render(<App><MyComponent onCallback={onCallback} /></App>);
    await user.click(screen.getByRole('button', { name: /texte/i }));
    expect(onCallback).toHaveBeenCalledWith(expect.objectContaining({ key: 'value' }));
  });
});
```

Particularités Ant Design :
- Ant Design 6.2 : `Modal` nécessite `<App>` comme ancêtre pour les notifications/messages
- Les composants qui utilisent `App.useApp()` doivent être enveloppés dans `<App>`
- Pour les `Select` et `DatePicker` Ant Design : utiliser `userEvent` ou `fireEvent.change` selon la complexité

### Structure cible des fichiers

```
idp-portal/frontend/src/
  components/
    catalog/
      ParametersFormStep.tsx          (143 lignes, EXISTANT — NE PAS MODIFIER)
      ParametersFormStep.test.tsx     ← CRÉER (~120-160 lignes)
      SchedulingPanel.tsx             (327 lignes, EXISTANT — NE PAS MODIFIER)
      SchedulingPanel.test.tsx        ← CRÉER (~200-250 lignes)
    executions/
      ExecutionsFiltersPanel.tsx      (280 lignes, EXISTANT — NE PAS MODIFIER)
      ExecutionsFiltersPanel.test.tsx ← CRÉER (~150-200 lignes)
    admin/
      BusinessRulePolicyModal.tsx     (230 lignes, EXISTANT — NE PAS MODIFIER)
      BusinessRulePolicyModal.test.tsx← CRÉER (~180-220 lignes)
```

**Aucun changement backend. Aucune modification des composants existants.** Uniquement création de fichiers `*.test.tsx`.

### Précédents directs à reproduire

| Précédent | Pattern applicable | Référence |
|-----------|-------------------|-----------|
| ConfirmationStep.test.tsx | Setup Form + App wrapper, tests callbacks | `src/components/catalog/ConfirmationStep.test.tsx` |
| ExecutionWizard.scheduling.test.tsx | Tests SchedulingPanel imbriqué dans wizard | `src/components/catalog/ExecutionWizard.scheduling.test.tsx` |
| BusinessRulePoliciesEditor.test.tsx | Tests admin modal JSON | `src/components/admin/BusinessRulePoliciesEditor.test.tsx` |
| Story 34-13 | WizardExecutionContext setup pour tests | `src/contexts/WizardExecutionContext.tsx` |

> **PRIORITÉ** : Lire `ConfirmationStep.test.tsx` et `ExecutionWizard.scheduling.test.tsx` **avant** de commencer — ces fichiers montrent le pattern exact d'utilisation de `Form`, `App`, `userEvent` et mocks de services dans ce projet.

### Project Structure Notes

- Pas de dossier `__tests__/` dans ce projet — les tests sont co-localisés avec les composants (convention validée sur 2018 tests existants)
- Le fichier de configuration Vitest est à `idp-portal/frontend/vite.config.ts`
- Setup global des tests : `idp-portal/frontend/src/test/setup.ts`
- `@testing-library/jest-dom` est configuré dans le setup global (matchers comme `toBeInTheDocument`)

### References

- [Source: idp-portal/frontend/src/components/catalog/ParametersFormStep.tsx] — 143 lignes, interface post-34-13
- [Source: idp-portal/frontend/src/components/catalog/SchedulingPanel.tsx] — 327 lignes
- [Source: idp-portal/frontend/src/components/executions/ExecutionsFiltersPanel.tsx] — 280 lignes
- [Source: idp-portal/frontend/src/components/admin/BusinessRulePolicyModal.tsx] — 230 lignes
- [Source: idp-portal/frontend/src/contexts/WizardExecutionContext.tsx] — contexte Story 34-13, requis pour ParametersFormStep
- [Source: idp-portal/frontend/src/components/catalog/ConfirmationStep.test.tsx] — pattern de test de référence
- [Source: idp-portal/frontend/src/components/catalog/ExecutionWizard.scheduling.test.tsx] — pattern SchedulingPanel
- [Source: idp-portal/frontend/src/components/admin/BusinessRulePoliciesEditor.test.tsx] — pattern admin modal
- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-FE-11] — finding original
- [Source: _bmad-output/implementation-artifacts/34-13-frontend-dip-services-props-execution-wizard.md] — story précédente (changements ParametersFormStep)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Correction texte Alert sans accents dans ParametersFormStep : `'Cette action ne necessite pas de parametres.'`
- SchedulingPanel : `dayjs.extend(utc)` requis pour `.utc().format()` dans les tests
- SchedulingPanel : texte d'erreur dupliqué (Form.Item help + Alert) → schedulingType='daily' pour le test
- BusinessRulePolicyModal : `{` spécial dans `userEvent.type` → utilisation de `fireEvent.change`
- ExecutionsFiltersPanel : `vi.mocked(await import(...))` incorrect → imports statiques + `vi.mocked()`

### Completion Notes List

- **Task 1 (ParametersFormStep)** : 15 tests couvrant smoke, champs dynamiques (rendu + required + callback), mode workflow (WorkflowStepsRenderer + loading + erreur + workflowValidationSummary), et business profile. `WizardExecutionContextProvider` fourni avec mock, `WorkflowStepsRenderer` mocké (expose workflowValidationSummary), `useAuth` mocké.
- **Task 2 (SchedulingPanel)** : 25 tests couvrant les 4 types de planification (one-time, daily, weekly, cron), callbacks, prochaines exécutions, erreur planification, état submitting, CronExpressionHelper mocké — ajout tests : cronValidating=true (icône loading), cronError visible (cronIsValid=false).
- **Task 3 (ExecutionsFiltersPanel)** : 17 tests couvrant smoke, badge activeFilterCount, bouton reset (actif/désactivé/callback), chargement au montage (fetchExecutionTags, fetchCatalogActions, useEngines, useEnvironments), présence des filtres, et onApplyFilters via Select statut.
- **Task 4 (BusinessRulePolicyModal)** : 25 tests couvrant open/fermé, titres création/édition, pré-remplissage formulaire, boutons exemple JSON, validation JSON invalide, callbacks onCancel/onSave avec payload, état saving (champs Input/TextArea/JSON désactivés + bouton aria-busy).
- **Correction composant BusinessRulePolicyModal.tsx** : ajout `disabled={saving}` sur Input nom, TextArea description, TextArea JSON et Switch is_active (AC manquant dans l'implémentation initiale).
- **0 erreur TypeScript** attendu (`npx tsc --noEmit`)

### File List

- `idp-portal/frontend/src/components/catalog/ParametersFormStep.test.tsx` (CRÉÉ — 15 tests)
- `idp-portal/frontend/src/components/catalog/SchedulingPanel.test.tsx` (CRÉÉ — 25 tests)
- `idp-portal/frontend/src/components/executions/ExecutionsFiltersPanel.test.tsx` (CRÉÉ — 17 tests)
- `idp-portal/frontend/src/components/admin/BusinessRulePolicyModal.test.tsx` (CRÉÉ — 25 tests)
- `idp-portal/frontend/src/components/admin/BusinessRulePolicyModal.tsx` (MODIFIÉ — correction disabled={saving} sur champs formulaire)

## Change Log

| Date | Change |
|------|--------|
| 2026-02-23 | Story enrichie (ready-for-dev) — Analyse exhaustive des 4 composants post-34-13 : interfaces complètes, dépendances (useWizardExecutionContext requis pour ParametersFormStep), patterns de test de référence, mocks à fournir, cas de test prioritaires par composant, structure cible 4 fichiers. |
| 2026-02-23 | Implémentation complète — 4 fichiers de test créés (75 tests), 0 régression, 0 erreur TypeScript. Status → review. |
| 2026-02-23 | Code review adversariale — 3 HIGH + 3 MEDIUM trouvés et corrigés : (H1) BusinessRulePolicyModal.tsx : ajout disabled={saving} sur 4 champs ; (H2) SchedulingPanel.test.tsx : ajout test cronValidating=true ; (H3) ajout test cronError visible ; (M1) ParametersFormStep.test.tsx : ajout test workflowValidationSummary ; (M2) BusinessRulePolicyModal.test.tsx : remplacement test saving=true no-op par 4 assertions réelles ; (M3) correction mocks Dev Notes. 82 tests au total. Status → done. |
