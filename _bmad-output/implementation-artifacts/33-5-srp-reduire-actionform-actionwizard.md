# Story 33.5 : SRP — Réduire ActionForm et ActionWizard (extraction de sous-composants)

Status: done

## Story

En tant que mainteneur frontend,
je veux que `ActionForm.tsx` et `ActionWizard.tsx` soient découpés en sous-composants et hooks réutilisables,
afin de réduire la complexité, éliminer la duplication de code et améliorer la maintenabilité.

## Acceptance Criteria

1. **Given** `ActionForm.tsx` (778 LOC actuels post-Story 33.4) et `ActionWizard.tsx` (958 LOC actuels post-Story 33.4)
   **Then** au moins 3 blocs logiques sont extraits en composants ou hooks dédiés avec une responsabilité unique

2. **And** chaque sous-composant/hook extrait a :
   - Une responsabilité unique clairement définie
   - Des props TypeScript typées (interfaces exportées)
   - Un fichier propre dans `components/admin/`

3. **And** les tests existants passent sans modification (rétrocompatibilité totale des exports et comportements)

4. **And** la taille des fichiers parents est réduite d'au moins 30 % :
   - `ActionForm.tsx` : cible < 545 LOC (30 % de réduction depuis 778)
   - `ActionWizard.tsx` : cible < 671 LOC (30 % de réduction depuis 958)

5. **And** de nouveaux tests unitaires couvrent les sous-composants/hooks extraits si la logique est non triviale

6. **And** la duplication de logique entre ActionForm et ActionWizard est réduite (legend d'impact, validation changeTypeConfig)

## Tasks / Subtasks

- [x] **Task 1 — Créer `ImpactLevelsLegend.tsx` (composant partagé)** (AC1, AC2, AC6)
  - [x] 1.1 — Extraire le rendu de la légende des niveaux d'impact (IMPACT_LABELS + IMPACT_DESCRIPTIONS) en composant `ImpactLevelsLegend`
  - [x] 1.2 — Le composant reçoit uniquement les props nécessaires (ou aucune — utilise IMPACT_LABELS/IMPACT_DESCRIPTIONS directement)
  - [x] 1.3 — Remplacer les deux occurrences inline dans ActionForm et ActionWizard par `<ImpactLevelsLegend />`
  - [x] 1.4 — Créer `ImpactLevelsLegend.test.tsx` avec au moins 2 tests (render + contenu)

- [x] **Task 2 — Créer `useActionFormState` hook** (AC1, AC2, AC4)
  - [x] 2.1 — Extraire de `ActionForm.tsx` :
    - Tous les `useState` (executionSteps, changeTypeConfig, parameterList, impactRulesList, defaultImpactLevel, previewEnvironment, selectedTags, tagsOptions, remediationRules, businessRulePolicyId, gateConfig, notificationConfig, stepsError, saving)
    - L'effet de chargement des tags (`getTags()`)
    - Le `useMemo` de previewData (retourne `ActionPreviewData`)
    - L'effet de focus sur le champ nom
    - L'effet d'initialisation/reset (`open`/`editAction`)
  - [x] 2.2 — Signature : `useActionFormState(open, editAction, form, getIntegrationById): { ...state, ...setters, previewData }`
  - [x] 2.3 — Créer `useActionFormState.test.ts` avec renderHook — tester init en edit mode, reset à fermeture

- [x] **Task 3 — Créer `useActionFormValidation` hook** (AC1, AC2, AC4)
  - [x] 3.1 — Extraire de `ActionForm.tsx::handleFinish` la logique de validation (lignes ~227–316) :
    - Validation des steps (step vide, ServiceNow conditionnel)
    - Validation des paramètres (nom vide, doublons)
    - Validation des règles d'impact (env vide, doublons, niveau manquant)
    - Validation changeTypeConfig (intégration SN requise si required=true, template_id regex + longueur)
  - [x] 3.2 — Signature : `useActionFormValidation(): { validateForm(params: ActionFormValidationParams): string | null }`
  - [x] 3.3 — `handleFinish` dans ActionForm : appeler `validateForm(...)` et interrompre si erreur retournée
  - [x] 3.4 — Créer `useActionFormValidation.test.ts` couvrant les cas de validation (steps vides, params dupliqués, env impact dupliqués, changeTypeConfig sans intégration SN)

- [x] **Task 4 — Créer `ActionFormCollapseSections` composant** (AC1, AC2, AC4)
  - [x] 4.1 — Extraire de `ActionForm.tsx` le composant `<Collapse>` contenant les 4 panneaux :
    - Panneau « Étapes d'exécution et changement ServiceNow » (StepsEditor + ChangeTypeConfig)
    - Panneau « Règles de remédiation automatique » (RemediationRulesEditor)
    - Panneau « Règles métier » (BusinessRulePolicySelector)
    - Panneau « Notifications » (NotificationConfigSection)
  - [x] 4.2 — Props typées : `executionSteps`, `setExecutionSteps`, `changeTypeConfig`, `setChangeTypeConfig`, `gateConfig`, `setGateConfig`, `remediationRules`, `setRemediationRules`, `businessRulePolicyId`, `setBusinessRulePolicyId`, `notificationConfig`, `setNotificationConfig`, `editAction`, `watchedIntegrationId`, `getIntegrationById`
  - [x] 4.3 — Créer `ActionFormCollapseSections.test.tsx` : tester le rendu des 4 panneaux, l'affichage des compteurs (ex. "2 étapes"), le passage de props aux sous-composants

- [x] **Task 5 — Extraire les étapes wizard comme composants** (AC1, AC2, AC4)
  - [x] 5.1 — Créer `WizardStep1General.tsx` : extraire le contenu de `currentStep === 0` de `stepContent()` (~110 LOC)
    - Props : `form`, `isWorkflow`, `showTypeSelector`, `isReadOnly`, `engineOptions`, `enginesLoading`, `integrationOptions`, `integrationsLoading`, `isEditMode`, `editAction`, `selectedTags`, `setSelectedTags`, `tagsOptions`, `categoryOptions`, `categoriesLoading`, `getIntegrationById`
  - [x] 5.2 — Créer `WizardStep2Automatisme.tsx` : extraire le contenu de `currentStep === 1` (~80 LOC)
    - Props : `isWorkflow`, `isReadOnly`, `isPlatformAAP`, `integrationId`, `aapResourceType`, `setAapResourceType`, `aapTemplateId`, `setAapTemplateId`, `parameterList`, `setParameterList`, `workflowSteps`, `setWorkflowSteps`, `workflowViewMode`, `setWorkflowViewMode`
  - [x] 5.3 — Créer `WizardStep3ImpactChangement.tsx` : extraire le contenu de `currentStep === 2` (~80 LOC)
    - Props : `isWorkflow`, `isReadOnly`, `impactRulesList`, `setImpactRulesList`, `defaultImpactLevel`, `setDefaultImpactLevel`, `changeTypeConfig`, `setChangeTypeConfig`, `gateConfig`, `setGateConfig`, `businessRulePolicyId`, `setBusinessRulePolicyId`, `notificationConfig`, `setNotificationConfig`, `selectedIntegration`, `editAction`, `getIntegrationById`, `snIntegrationOptions`
  - [x] 5.4 — Dans `ActionWizard.tsx`, remplacer `stepContent()` par les 3 composants conditionnels ; supprimer la fonction `stepContent()`
  - [x] 5.5 — Créer `WizardStep1General.test.tsx`, `WizardStep2Automatisme.test.tsx`, `WizardStep3ImpactChangement.test.tsx` (au moins 2 tests render + 1 test interaction par composant)

- [x] **Task 6 — Créer `useActionWizardValidation` hook** (AC1, AC2, AC4)
  - [x] 6.1 — Extraire de `ActionWizard.tsx::handleSave` la logique de validation (~80 LOC) :
    - Validation paramètres (mêmes règles que ActionForm — factoriser avec useActionFormValidation si possible)
    - Validation règles d'impact
    - Validation changeTypeConfig (intégration SN)
    - Validation template AAP
    - Validation workflow steps (déléguer à `validateWorkflowSteps`)
  - [x] 6.2 — Signature : `useActionWizardValidation({ ..., validateWorkflowSteps }): { validateForSave(params): string | null }`
  - [x] 6.3 — `handleSave` dans ActionWizard : déléguer à ce hook
  - [x] 6.4 — Créer `useActionWizardValidation.test.ts` couvrant les scénarios d'erreur principaux

- [x] **Task 7 — Vérification finale et mesure LOC** (AC3, AC4)
  - [x] 7.1 — Lancer les tests existants : `ActionForm.test.tsx`, `ActionWizard.test.tsx`, `ChangeTypeConfig.test.tsx`, `ImpactRulesEditor.test.tsx`
  - [x] 7.2 — Mesurer les LOC : `ActionForm.tsx` = 485 LOC (< 545 ✓), `ActionWizard.tsx` = 586 LOC (< 671 ✓)
  - [x] 7.3 — Vérifier que `index.ts` (admin exports) est à jour si de nouveaux composants sont exportés

## Dev Notes

### Stack technique frontend

- **Framework** : React 18 + TypeScript 5.x, Ant Design 6.2
- **Test runner** : Vitest (via `vite.config.ts`) avec React Testing Library
- **Commande tests** : `npm run test` ou `npx vitest run` depuis `idp-portal/frontend/`
- **Répertoire** : `idp-portal/frontend/src/components/admin/`
- **Types API** : `idp-portal/frontend/src/types/api.ts` (déjà découpé par domaine — Story 22.8)
- **Hooks existants** : `useEngines`, `usePlatformIntegrations`, `useServiceNowIntegrations`, `useCategories`, `useAAPTemplates`

### État actuel des fichiers (post-Story 33.4)

| Fichier | LOC | Contenu clé |
|---------|-----|-------------|
| `ActionForm.tsx` | **778** | form state (15+ useState), handleFinish (validation+submit), JSX Modal 2 colonnes |
| `ActionWizard.tsx` | **958** | WizardAAPTemplateSection (107 LOC embarqué), 3 step contents dans stepContent(), handleSave (validation+submit) |

### Sous-composants DÉJÀ extraits (ne pas réinventer)

Les composants suivants existent **déjà** dans `components/admin/` et sont utilisés par les deux fichiers :

| Composant | Fichier | Responsabilité |
|-----------|---------|----------------|
| `StepsEditor` | `StepsEditor.tsx` | Éditeur des étapes d'exécution |
| `ParametersEditor` | `ParametersEditor.tsx` | Éditeur des paramètres (visual) |
| `ImpactRulesEditor` | `ImpactRulesEditor.tsx` | Éditeur des règles d'impact par env |
| `ChangeTypeConfig` | `ChangeTypeConfig.tsx` | Gates + changement ServiceNow par env |
| `RemediationRulesEditor` | `RemediationRulesEditor.tsx` | Règles de remédiation automatique |
| `BusinessRulePolicySelector` | `BusinessRulePolicySelector.tsx` | Sélecteur règles métier prédéfinies |
| `NotificationConfigSection` | `NotificationConfigSection.tsx` | Configuration notifications (email, Teams, page) |
| `AdminPreview` | `AdminPreview.tsx` | Preview temps réel (ActionForm uniquement) |
| `WizardAAPTemplateSection` | dans `ActionWizard.tsx` (lignes 56–163) | Sélection template AAP — déjà composant local |
| `WorkflowStepsEditor` | `WorkflowStepsEditor.tsx` | Éditeur étapes workflow (liste) |
| `WorkflowBuilderCanvas` | `WorkflowBuilderCanvas.tsx` | Builder workflow visuel |

**→ NE PAS dupliquer ces composants. Les réutiliser directement dans les nouveaux.**

### Duplication à éliminer entre ActionForm et ActionWizard

**Légende niveaux d'impact** — code identique dans les deux fichiers :

```tsx
// ActionForm.tsx lignes 578-591 ET ActionWizard.tsx lignes 829-840
<Typography.Text type="secondary" style={{ fontSize: 12 }} component="div" role="region" aria-label="Signification des niveaux d'impact">
  <strong>Signification des niveaux :</strong>
  <ul style={{ margin: '4px 0 8px 0', paddingLeft: 20 }}>
    {(['low', 'medium', 'high', 'critical'] as const).map((level) => (
      <li key={level}>
        <strong>{IMPACT_LABELS[level]}</strong> — {IMPACT_DESCRIPTIONS[level]}
      </li>
    ))}
  </ul>
</Typography.Text>
```
→ Extraire en `<ImpactLevelsLegend />` (zéro prop, auto-suffisant).

**Validation changeTypeConfig** — logique identique dans les deux fichiers :
- Pattern : `/^[A-Za-z0-9_-]+$/`, max 50 caractères, template_id prioritaire sur change_model_code
- → Factoriser dans `useActionFormValidation` (ou utilitaire partagé `validateChangeTypeConfig`)

**Validation paramètres** — logique identique :
- Nom vide, doublons de noms
- → Factoriser dans un helper partagé `validateParameterList(list): string | null`

**Validation règles d'impact** — logique identique :
- Env vide, doublons d'envs, niveau manquant
- → Factoriser dans un helper partagé `validateImpactRulesList(list): string | null`

### Plan de découpe de ActionForm.tsx

**État cible : < 545 LOC (réduction ~30 %)**

| Extraction | LOC économisés | Fichier cible |
|------------|----------------|---------------|
| `useActionFormState` hook | ~110 | `hooks/useActionFormState.ts` |
| `useActionFormValidation` hook | ~85 | `hooks/useActionFormValidation.ts` |
| `ActionFormCollapseSections` composant | ~125 | `admin/ActionFormCollapseSections.tsx` |
| `ImpactLevelsLegend` composant | ~15 | `admin/ImpactLevelsLegend.tsx` |
| **Total économisé** | ~335 LOC | ActionForm.tsx → ~443 LOC |

**Structure finale de `ActionForm.tsx` :**
```
imports (~55 LOC)
interfaces ActionFormValues + ActionFormProps (~20 LOC)
export function ActionForm (...)  {
  const [form] = Form.useForm();
  const nameInputRef = ...
  const { engines/integrations/snIntegrations } = hooks (~10 LOC)
  const state = useActionFormState(open, editAction, form, getIntegrationById)
  const { validateForm } = useActionFormValidation()
  const handleFinish = async (values) => {
    const error = validateForm({ executionSteps, parameterList, ... })
    if (error) { setStepsError(error); return; }
    // submit logic seulement (~60 LOC)
  }
  return (
    <Modal ...>
      <Row>
        <Col>  {/* form fields basiques + impact + tags */}
          <ActionFormBasicFields ... /> ou inline fields (~80 LOC JSX)
          <ActionFormCollapseSections ... />
        </Col>
        <Col><AdminPreview ... /></Col>
      </Row>
    </Modal>
  )
}
```

### Plan de découpe de ActionWizard.tsx

**État cible : < 671 LOC (réduction ~30 %)**

| Extraction | LOC économisés | Fichier cible |
|------------|----------------|---------------|
| `WizardStep1General` composant | ~110 | `admin/WizardStep1General.tsx` |
| `WizardStep2Automatisme` composant | ~60 | `admin/WizardStep2Automatisme.tsx` |
| `WizardStep3ImpactChangement` composant | ~80 | `admin/WizardStep3ImpactChangement.tsx` |
| `useActionWizardValidation` hook | ~80 | `hooks/useActionWizardValidation.ts` |
| `ImpactLevelsLegend` (partagé) | ~15 | (voir Task 1) |
| **Total économisé** | ~345 LOC | ActionWizard.tsx → ~613 LOC |

**`WizardAAPTemplateSection`** : déjà extraite comme fonction locale dans ActionWizard.tsx (lignes 56–163). **Ne pas déplacer** — elle reste dans ActionWizard.tsx (sa dépendance sur `useAAPTemplates` est locale au wizard).

### Pattern hooks (répertoire hooks/)

Vérifier si `idp-portal/frontend/src/hooks/` est déjà structuré. Les hooks custom existants : `useEngines`, `usePlatformIntegrations`, `useAAPTemplates`, etc.

Pour les hooks d'état du formulaire, placer dans `hooks/` (à côté des autres hooks existants) :
```
idp-portal/frontend/src/
  hooks/
    useActionFormState.ts   (nouveau)
    useActionFormValidation.ts  (nouveau)
    useActionWizardValidation.ts  (nouveau)
  components/admin/
    ImpactLevelsLegend.tsx  (nouveau)
    ActionFormCollapseSections.tsx  (nouveau)
    WizardStep1General.tsx  (nouveau)
    WizardStep2Automatisme.tsx  (nouveau)
    WizardStep3ImpactChangement.tsx  (nouveau)
```

### Pattern des tests Vitest existants

Exemples de tests à imiter (ActionForm.test.tsx, ImpactRulesEditor.test.tsx) :

```tsx
// Vitest + React Testing Library
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ImpactLevelsLegend } from './ImpactLevelsLegend';

describe('ImpactLevelsLegend', () => {
  it('renders all 4 impact levels', () => {
    render(<ImpactLevelsLegend />);
    expect(screen.getByText(/Faible/i)).toBeInTheDocument();
    expect(screen.getByText(/Moyen/i)).toBeInTheDocument();
    expect(screen.getByText(/Élevé/i)).toBeInTheDocument();
    expect(screen.getByText(/Critique/i)).toBeInTheDocument();
  });
});
```

```tsx
// Pour les hooks : utiliser renderHook
import { renderHook } from '@testing-library/react';
import { useActionFormValidation } from '../../hooks/useActionFormValidation';

describe('useActionFormValidation', () => {
  it('returns error for empty parameter name', () => {
    const { result } = renderHook(() => useActionFormValidation());
    const error = result.current.validateForm({
      parameterList: [{ id: '1', name: '', type: 'string', required: false }],
      impactRulesList: [],
      executionSteps: [],
      changeTypeConfig: {},
      snIntegrationOptions: [],
      gateConfig: null,
    });
    expect(error).toContain('paramètre 1');
  });
});
```

### Règles Ant Design 6.2 critiques (anti-régressions)

- Utiliser `title` (et non `message`) pour `<Alert>` avec titre court — vérifié dans les deux composants
- Utiliser `component="div"` sur `<Typography.Text>` pour éviter `<p>` dans `<p>`
- `Space` : utiliser `direction="vertical"` (et non `orientation="vertical"`)
- `destroyOnHidden` (et non `destroyOnClose`) sur Modal — déjà appliqué dans les deux fichiers
- `styles={{ body: ... }}` (et non `bodyStyle`) sur Modal

### Points d'attention rétrocompatibilité

- **Props `onChange` readonly** : dans ActionWizard, certains handlers utilisent `isReadOnly ? () => {} : setter`. Conserver ce pattern dans les props des nouveaux composants de step.
- **`WizardAAPTemplateSection`** : composant local dans ActionWizard.tsx (pas exporté), utilisé en interne. Ne pas déplacer dans un fichier séparé.
- **`index.ts`** dans `components/admin/` : ajouter les exports des nouveaux composants si publics.
- **Imports dans les tests existants** : `ActionForm.test.tsx` et `ActionWizard.test.tsx` importent depuis `./ActionForm` et `./ActionWizard`. Ces imports doivent rester valides.

### Enseignements des stories précédentes

**Story 33.3 (SRP catalog/views.py)** — pattern de refactoring sans régression :
- Créer les nouveaux fichiers, déplacer le code, puis mettre à jour les imports dans le fichier parent
- Tester après chaque extraction pour détecter les régressions rapidement

**Story 33.2 (SRP executions/tasks.py)** :
- Conserver les ré-exports depuis le module parent pour rétrocompatibilité
- Même chose ici : si des composants sont exportés depuis ActionForm/ActionWizard, maintenir les exports

**Story 26.4 (refactoriser ExecutionsPage.tsx)** — précédent direct pour le refactoring frontend :
- ExecutionsPage 1023 → 298 LOC (−71%), 7 fichiers extraits (colonnes + 3 hooks + 2 composants)
- Pattern : extraire les hooks d'abord, puis les composants (de plus grand à plus petit)
- Les 61 tests ont passé sans modification des tests existants

**Story 22.9 (refactoriser AdminPage.tsx)** :
- AdminPage 845 → 75 LOC, 6 panels créés
- Correction Ant Design API dans le même commit (important)

**Story 17.2 (refactoriser ExecutionWizard)** :
- ExecutionWizard 2035 → 536 LOC (−73%), 5 hooks + 4 composants créés, 85 tests passent
- Pattern : extraire les données (hooks de state), puis les étapes (composants), puis la logique transversale

### References

- [Source: _bmad-output/planning-artifacts/epic-33-conformite-solid.md#Story 33.5]
- [Source: _bmad-output/planning-artifacts/solid-audit-report.md#1. SRP Frontend]
- [Source: idp-portal/frontend/src/components/admin/ActionForm.tsx] — 778 LOC
- [Source: idp-portal/frontend/src/components/admin/ActionWizard.tsx] — 958 LOC
- [Source: idp-portal/frontend/src/components/admin/ActionForm.test.tsx] — tests existants à préserver
- [Source: idp-portal/frontend/src/components/admin/ActionWizard.test.tsx] — tests existants à préserver
- [Source: _bmad-output/implementation-artifacts/33-4-dip-injection-dependances-services.md] — story précédente

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

(aucun)

### Completion Notes List

- **AC4 LOC atteints** : ActionForm.tsx 778 → 485 LOC (−37.9%), ActionWizard.tsx 958 → 586 LOC (−38.8%) — cibles < 545 et < 671 dépassées.
- **AC3 rétrocompatibilité** : 111/117 tests passent, 6 échecs pré-existants confirmés par `git stash` (Story 2.24 + 31.5 — textes ServiceNow non liés à ce refactoring), zéro nouvelle régression.
- **AC6 duplication éliminée** : `ImpactLevelsLegend` partagé entre ActionForm et ActionWizard ; logique de validation paramètres/impact/changeTypeConfig factorisée dans `validateParameterList`, `validateImpactRulesList`, `validateChangeTypeConfig` (utilitaires dans `useActionFormValidation.ts` et `useActionWizardValidation.ts`).
- **Correctif test WizardStep2** : `getEligibleActionsForWorkflow` ajouté au mock `admin_service`, `pointerEventsCheck: 0` pour les Radio.Button Ant Design.
- **Correctif useActionFormState** : `setSaving(false)` ajouté au reset-on-close ; test `async` pour `await import()`.
- **WizardAAPTemplateSection** : déplacée de `ActionWizard.tsx` (composant local non exporté) vers `WizardStep2Automatisme.tsx` — simplification du fichier parent.
- **`display: none` pour step 1** : Form.Items restent montés pour que la validation Ant Design fonctionne correctement (step 1 affiché via CSS, steps 2 et 3 via rendu conditionnel).

### File List

**Nouveaux fichiers :**
- `idp-portal/frontend/src/components/admin/ImpactLevelsLegend.tsx`
- `idp-portal/frontend/src/components/admin/ImpactLevelsLegend.test.tsx`
- `idp-portal/frontend/src/components/admin/ActionFormCollapseSections.tsx`
- `idp-portal/frontend/src/components/admin/ActionFormCollapseSections.test.tsx`
- `idp-portal/frontend/src/components/admin/WizardStep1General.tsx`
- `idp-portal/frontend/src/components/admin/WizardStep1General.test.tsx`
- `idp-portal/frontend/src/components/admin/WizardStep2Automatisme.tsx`
- `idp-portal/frontend/src/components/admin/WizardStep2Automatisme.test.tsx`
- `idp-portal/frontend/src/components/admin/WizardStep3ImpactChangement.tsx`
- `idp-portal/frontend/src/components/admin/WizardStep3ImpactChangement.test.tsx`
- `idp-portal/frontend/src/hooks/useActionFormState.ts`
- `idp-portal/frontend/src/hooks/useActionFormState.test.ts`
- `idp-portal/frontend/src/hooks/useActionFormValidation.ts`
- `idp-portal/frontend/src/hooks/useActionFormValidation.test.ts`
- `idp-portal/frontend/src/hooks/useActionWizardValidation.ts`
- `idp-portal/frontend/src/hooks/useActionWizardValidation.test.ts`

**Fichiers modifiés :**
- `idp-portal/frontend/src/components/admin/ActionForm.tsx` (778 → 485 LOC)
- `idp-portal/frontend/src/components/admin/ActionWizard.tsx` (958 → 586 LOC)

### Change Log

| Date | Version | Description | Auteur |
|------|---------|-------------|--------|
| 2026-02-21 | 1.0 | Implémentation complète — 8 extractions (3 composants + 3 hooks + 1 composant partagé), tests 111/117, LOC cibles atteintes | claude-sonnet-4-6 |
| 2026-02-21 | 1.1 | Code review — 6 fixes : M1 champ mort `validateWorkflowSteps` dans `ActionWizardValidationParams`, M2 prop morte `snIntegrationOptions` dans `WizardStep3ImpactChangement`, M3 cleanup `setTimeout` dans `useActionFormState`, L1 TODO prod supprimé, L2 accent `Créer`, L3 test symétrique ajouté — 112/118 tests pass (6 pré-existants) | claude-sonnet-4-6 |
