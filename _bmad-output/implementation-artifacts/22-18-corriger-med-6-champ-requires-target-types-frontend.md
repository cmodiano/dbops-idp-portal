# Story 22.18: Corriger MED-6 — Ajouter champ `requires_target` dans types frontend

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur,
je veux ajouter le champ `requires_target` dans les types frontend,
afin de permettre au frontend de déterminer si une action nécessite des cibles.

## Acceptance Criteria

1. **AC1 - Ajout du champ dans types/api/catalog.ts**
   - **Given** le backend renvoie `requires_target` dans `ActionResponse` et `ActionDetail`
   - **When** le frontend consomme ces types depuis `types/api/catalog.ts`
   - **Then** `requires_target?: boolean` est ajouté dans l'interface `ActionResponse`
   - **And** le champ est documenté avec un commentaire référençant Story 13.2, AC3

2. **AC2 - Cohérence avec CatalogActionDetail existant**
   - **Given** le type `CatalogActionDetail` dans `catalog_service.ts` inclut déjà `requires_target`
   - **When** les types sont alignés
   - **Then** la définition dans `types/api/catalog.ts` est cohérente avec celle de `catalog_service.ts`
   - **And** aucune duplication ou conflit de type n'existe

3. **AC3 - Vérification des imports dans ExecutionWizard**
   - **Given** `ExecutionWizard.tsx` utilise déjà `action?.requires_target !== false`
   - **When** le type `ActionResponse` ou `ActionDetail` est importé
   - **Then** TypeScript reconnaît le champ `requires_target` sans erreur de type
   - **And** le code défensif existant (`!== false`) reste valide mais TypeScript le typage correctement

4. **AC4 - Vérification des imports dans TargetSelectionStep**
   - **Given** `TargetSelectionStep.tsx` utilise `action?.requires_target !== false`
   - **When** le composant utilise les types d'API
   - **Then** TypeScript reconnaît le champ sans erreur
   - **And** l'auto-complétion suggère le champ `requires_target`

5. **AC5 - Mise à jour de types/api.ts (backward compatibility)**
   - **Given** le fichier monolithique `types/api.ts` existe encore (bien que déprécié)
   - **When** des composants legacy l'importent
   - **Then** le champ `requires_target` est également ajouté dans ce fichier
   - **And** un commentaire indique que `types/api/catalog.ts` est la source de vérité

6. **AC6 - Tests de validation TypeScript**
   - **Given** les tests existants utilisent des mocks avec `requires_target`
   - **When** les tests TypeScript sont exécutés
   - **Then** aucune erreur de type n'est levée pour les propriétés `requires_target`
   - **And** les tests de `ExecutionWizard.test.tsx`, `TargetSelectionStep.test.tsx` compilent sans erreur

7. **AC7 - Documentation de la migration**
   - **Given** la correction est liée au rapport de qualité MED-6
   - **When** un développeur consulte le code
   - **Then** un commentaire dans les types référence le rapport d'assessment (code-quality-assessment-2026-02-08.md)
   - **And** la documentation explique pourquoi ce champ est optionnel (`?:`) avec default `true`

## Tasks / Subtasks

- [x] Task 1: Ajouter `requires_target` dans types/api/catalog.ts (AC: #1, #2)
  - [x] 1.1: Ouvrir `frontend/src/types/api/catalog.ts`
  - [x] 1.2: Localiser l'interface `ActionResponse` (lignes ~46-71)
  - [x] 1.3: Ajouter le champ `requires_target?: boolean;` après le champ `tags` ou `documentation_md`
  - [x] 1.4: Ajouter commentaire JSDoc : `/** Story 13.2, AC3: Whether action requires target selection (default true). MED-6 fix. */`
  - [x] 1.5: Vérifier que `ActionDetail` hérite correctement du champ (extends ActionResponse)

- [x] Task 2: Ajouter `requires_target` dans types/api.ts (backward compat) (AC: #5)
  - [x] 2.1: `types/api.ts` est un barrel re-export (`export * from './api/index'`) — pas d'interfaces locales
  - [x] 2.2: Le champ ajouté dans `catalog.ts` se propage automatiquement via le barrel export
  - [x] 2.3: Note de dépréciation déjà présente dans le fichier (Story 22.8)
  - [x] 2.4: Aucune modification nécessaire — backward compat assurée par design

- [x] Task 3: Vérification de cohérence avec catalog_service.ts (AC: #2)
  - [x] 3.1: Ouvrir `frontend/src/services/catalog_service.ts` (ligne ~55)
  - [x] 3.2: Vérifier que `CatalogActionDetail` définit `requires_target?: boolean;` (✅ déjà présent)
  - [x] 3.3: Comparer la documentation des deux types (catalog.ts vs catalog_service.ts)
  - [x] 3.4: Commentaires cohérents — les deux référencent Story 13.2, AC3

- [x] Task 4: Validation TypeScript dans ExecutionWizard (AC: #3)
  - [x] 4.1: Ouvrir `frontend/src/components/catalog/ExecutionWizard.tsx`
  - [x] 4.2: Vérifier ligne 207: `const requiresTarget = action?.requires_target !== false;`
  - [x] 4.3: Exécuter `tsc --noEmit` → 0 erreur
  - [x] 4.4: Aucune erreur TS2339 levée

- [x] Task 5: Validation TypeScript dans TargetSelectionStep (AC: #4)
  - [x] 5.1: Ouvrir `frontend/src/components/catalog/TargetSelectionStep.tsx`
  - [x] 5.2: Vérifier ligne 87: `const requiresTarget = action?.requires_target !== false;`
  - [x] 5.3: TypeScript reconnaît le champ `requires_target` via héritage ActionResponse

- [x] Task 6: Validation des tests TypeScript (AC: #6)
  - [x] 6.1: ExecutionWizard.test.tsx → 53/53 pass
  - [x] 6.2: TargetSelectionStep.test.tsx → 13/13 pass
  - [x] 6.3: Tests additionnels validés :
    - ExecutionWizard.targets.test.tsx → 6/6 pass
    - ConfirmationStep.test.tsx → pass (inclus dans batch)
    - ExecutionWizard.scheduling.test.tsx → 10/10 pass
  - [x] 6.4: 96 tests au total, 0 échec, 0 erreur de compilation TypeScript

- [x] Task 7: Documentation et validation finale (AC: #7)
  - [x] 7.1: Commentaire JSDoc ajouté référençant MED-6 dans `types/api/catalog.ts`
  - [x] 7.2: Champ optionnel `?:` — le backend renvoie toujours, mais défensif pour compatibilité
  - [x] 7.3: Cohérence backend confirmée — `catalog/serializers.py:124` inclut `requires_target`
  - [x] 7.4: Note ajoutée dans Dev Agent Record

## Dev Notes

### Contexte du Problème (Source: code-quality-assessment-2026-02-08.md#MED-6)

**Problème identifié:**
- **Backend:** Le serializer `catalog/serializers.py:124` inclut le champ `requires_target` dans l'API response
- **Frontend:** Les types `ActionResponse` et `ActionDetail` dans `types/api.ts` et `types/api/catalog.ts` ne déclarent PAS ce champ
- **Impact:** TypeScript ne valide pas l'utilisation du champ, le code défensif masque le problème (`action?.requires_target !== false`)
- **Risque:** Si le backend change le comportement par défaut ou supprime le champ, le frontend ne détectera pas l'erreur à la compilation

**Solution retenue:**
- Ajouter `requires_target?: boolean` dans les types frontend
- Type optionnel (`?:`) car la logique défensive existante assume `true` par défaut
- Cohérence avec le type `CatalogActionDetail` dans `catalog_service.ts` (déjà correct)

### Architecture Actuelle

**Backend (Django/DRF):**
```python
# catalog/models.py:184
requires_target = models.BooleanField(default=True, db_column='REQUIRES_TARGET')

# catalog/serializers.py:124
fields = [
    'id', 'name', 'description', ..., 'tags', 'documentation_md',
    'remediation_rules', 'execution_steps', 'change_type_config',
    'workflow_steps', 'requires_target'  # ← Envoyé dans l'API
]
```

**Backend Validation (Story 13.4):**
```python
# executions/views.py:143-153
requires_target = getattr(action, 'requires_target', True)
if requires_target:
    if not target_names:
        raise BadRequestError(message="target_names est requis pour cette action")
```

**Frontend Types (ÉTAT ACTUEL - INCOMPLET):**

**Fichier 1: `types/api/catalog.ts` (split structure, Story 22.8)**
```typescript
export interface ActionResponse {
  id: number;
  name: string;
  description: string | null;
  item_type: ItemType;
  // ... autres champs ...
  tags?: string[];
  documentation_md?: string | null;
  // ❌ MANQUANT: requires_target?: boolean;
}

export interface ActionDetail extends ActionResponse {
  execution_steps: ExecutionStep[] | null;
  workflow_steps: WorkflowStep[] | null;
  // ... autres champs ...
  // ❌ HÉRITE du problème ActionResponse
}
```

**Fichier 2: `catalog_service.ts` (définition service-specific)**
```typescript
export interface CatalogActionDetail extends CatalogAction {
  /** Story 13.2, AC3: Whether action requires target selection (default true). */
  requires_target?: boolean;  // ✅ CORRECT - déjà présent
  // ...
}
```

**Utilisation dans les composants:**
```typescript
// ExecutionWizard.tsx:207
const requiresTarget = action?.requires_target !== false;
// ☑️ Fonctionne à l'exécution, mais TypeScript ne valide pas le champ

// TargetSelectionStep.tsx:87
const requiresTarget = action?.requires_target !== false;
// ☑️ Même situation
```

### Fichiers à Modifier

**1. `frontend/src/types/api/catalog.ts`** (PRIORITAIRE - nouvelle structure Story 22.8)
   - Ajouter `requires_target?: boolean;` dans `ActionResponse`
   - `ActionDetail` hérite automatiquement

**2. `frontend/src/types/api.ts`** (backward compatibility - fichier déprécié)
   - Ajouter le même champ pour les imports legacy
   - Ajouter note de dépréciation

**3. Vérification (pas de modification requise):**
   - `catalog_service.ts` → déjà correct
   - `ExecutionWizard.tsx` → code défensif existant fonctionnera mieux avec types corrects
   - `TargetSelectionStep.tsx` → idem

### Tests Existants à Valider

Les tests suivants utilisent déjà `requires_target` dans leurs mocks et doivent passer après la correction:

```typescript
// ExecutionWizard.test.tsx (lignes 127, 336, 415, 1126)
const mockAction = { ..., requires_target: true };
const mockActionNoTarget = { ..., requires_target: false };

// TargetSelectionStep.test.tsx (lignes 33, 206, 221, 236)
const mockAction = { ..., requires_target: true };
```

**Validation:** Aucune modification des tests n'est requise, mais TypeScript doit maintenant valider correctement ces usages.

### Références

- **Story source:** Epic 22, Story 22.18 (epic-22-amelioration-qualite-code.md:413-430)
- **Assessment report:** code-quality-assessment-2026-02-08.md:442-445 (MED-6)
- **Story originale (backend):** Story 13.2, AC3 - Ajout du champ `requires_target` dans le modèle
- **Story split types:** Story 22.8 - Découpage de types/api.ts par domaine
- **Migration Oracle:** V046 (ajout colonne REQUIRES_TARGET)

### Dépendances et Impacts

**Dépendances:**
- ✅ Story 13.2 (backend) - DONE: Champ `requires_target` existe dans le modèle et l'API
- ✅ Story 22.8 (split types) - DONE: Structure de fichiers types/api/ déjà en place

**Impact sur autres stories:**
- Aucun impact bloquant
- Améliore la sécurité de type pour toutes les stories utilisant ExecutionWizard
- Facilite le refactoring futur (détection d'erreurs à la compilation)

**Composants affectés (amélioration de type safety):**
- `ExecutionWizard.tsx` → TypeScript validera maintenant `action.requires_target`
- `TargetSelectionStep.tsx` → idem
- `ConfirmationStep.tsx` → si utilise le champ
- Tous les tests mockant des actions

### Patterns de Code

**Pattern défensif actuel (à conserver):**
```typescript
// Assume true si undefined (cohérent avec backend default=True)
const requiresTarget = action?.requires_target !== false;
```

**Après la correction, TypeScript comprendra:**
```typescript
// Type: ActionResponse = { ..., requires_target?: boolean }
// Valeur possible: undefined | true | false
// Logique: undefined → true (safe default), false → false, true → true
const requiresTarget = action?.requires_target !== false;  // ✅ Type-safe
```

### Project Structure Notes

**Alignement avec unified project structure:**
- Types API organisés par domaine (Story 22.8): ✅ Aligné
- Séparation types/services: ✅ Cohérent
- Commentaires JSDoc avec références de story: ✅ Standard respecté

**Patterns établis:**
- Champs optionnels backend → types optionnels frontend (`?:`)
- Commentaires de documentation: `/** Story X.Y, ACZ: Description */`
- Fichiers découpés par domaine fonctionnel (catalog, executions, profiles, etc.)

### Validation de Cohérence Backend/Frontend

**Backend API Response (catalog/serializers.py):**
```json
{
  "id": 1,
  "name": "Backup Oracle",
  "item_type": "action",
  "requires_target": true,  // ← Toujours présent dans la réponse
  // ...
}
```

**Frontend Type Attendu (après correction):**
```typescript
interface ActionResponse {
  id: number;
  name: string;
  item_type: ItemType;
  requires_target?: boolean;  // ← Optionnel côté TS (défense contre undefined)
  // ...
}
```

**Justification `?:` (optionnel) au lieu de requis:**
1. Le backend renvoie toujours le champ (default=True dans le modèle)
2. Mais le code frontend utilise déjà une logique défensive (`!== false`)
3. En cas d'absence (bug backend ou réponse partielle), le frontend assume `true` par défaut
4. Rendre le champ requis casserait la compatibilité avec le code défensif existant

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- Investigation complète via Explore agent (agent ID: af090a8)
- Analyse des 8 fichiers impactés (backend + frontend + tests)
- Vérification de cohérence backend/frontend types

### Implementation Notes

- `types/api.ts` n'est plus un fichier monolithique — c'est un barrel re-export (`export * from './api/index'`) depuis Story 22.8. Aucune modification nécessaire pour backward compat.
- Cohérence backend/frontend confirmée : `catalog/serializers.py:124` inclut `requires_target` dans les fields du serializer.
- Le champ est optionnel (`?:`) côté TypeScript car la logique défensive existante (`!== false`) assume `true` par défaut, cohérent avec `models.BooleanField(default=True)`.
- `tsc --noEmit` : 0 erreurs après ajout du champ.
- 96 tests exécutés (53 ExecutionWizard + 13 TargetSelectionStep + 6 targets + 10 scheduling + 14 ConfirmationStep) : tous passent.

### Completion Notes List

- ✅ Ajouté `requires_target?: boolean` dans `ActionResponse` (types/api/catalog.ts) avec JSDoc complet référençant Story 13.2 AC3, Story 22.18 et MED-6 (code-quality-assessment-2026-02-08.md:442-445)
- ✅ Ajouté `requires_target?: boolean` dans `ActionListItem` pour cohérence avec le serializer backend
- ✅ Ajouté `requires_target?: boolean` dans `ActionPreviewData` pour preview admin complet
- ✅ `ActionDetail` hérite automatiquement via `extends ActionResponse`
- ✅ Backward compat assurée : `types/api.ts` re-exporte via barrel
- ✅ Cohérence vérifiée avec `CatalogActionDetail` dans `catalog_service.ts`
- ✅ Correction ExecutionWizard.tsx:248 — ajout optional chaining `action?.` pour cohérence avec ligne 207
- ✅ TypeScript validation : `tsc --noEmit` = 0 erreurs après corrections
- ✅ Tests : 53/53 ExecutionWizard passent (ExecutionWizard, TargetSelectionStep, targets, scheduling, ConfirmationStep)
- ✅ Backend sync confirmé (serializers.py:124)
- ✅ Code review adversarial : 6 issues trouvées et corrigées (3 HIGH, 3 MEDIUM)

### File List

- `idp-portal/frontend/src/types/api/catalog.ts` — Ajouté `requires_target?: boolean` dans `ActionResponse`, `ActionListItem`, `ActionPreviewData` avec documentation complète
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx` — Correction ligne 248: ajout optional chaining `action?.requires_target`

### Change Log

- 2026-02-09 (initial): Story 22.18 implémentée — Ajout champ `requires_target?: boolean` dans interface `ActionResponse` (types/api/catalog.ts) pour corriger MED-6. 1 fichier modifié, 96 tests validés, 0 régression.
- 2026-02-09 (code review): Corrections adversarial review — Ajouté `requires_target` dans `ActionListItem` et `ActionPreviewData`, documentation JSDoc enrichie avec référence assessment report, correction optional chaining ExecutionWizard.tsx:248. 2 fichiers modifiés (catalog.ts, ExecutionWizard.tsx), 6 issues corrigées (3 HIGH, 3 MEDIUM), TypeScript 0 erreurs.
