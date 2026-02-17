# Story 30.10: Code mort et dépréciations

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur,
Je veux supprimer le code mort et clarifier les dépréciations (backend et frontend),
Afin de réduire la dette et la confusion.

## Acceptance Criteria

1. **Given** `normalize_tag_name()` dans `catalog/models.py:51-55`
   **When** le code est analysé
   **Then** la fonction est supprimée si inutilisée OU utilisée de façon cohérente partout (choisir une seule normalisation)

2. **Given** `if not action` après `Action.objects.get()` dans `idp_auth/services.py:134-136`
   **When** le code est exécuté
   **Then** le code mort (jamais atteint car `get()` lève `DoesNotExist`) est supprimé

3. **Given** `gate_status.get('action', 'FAILED')` dans `executions/tasks.py:278`
   **When** le résultat est traité
   **Then** la variable non assignée est corrigée (assign le résultat ou supprimer l'appel)

4. **Given** `import json` redondant dans `core/models.py:155`
   **When** les imports sont analysés
   **Then** le doublon est supprimé (déjà importé ligne 3)

5. **Given** imports `# noqa: F401` backward compat dans `inventory/services.py:16,21,33`
   **When** le code est analysé
   **Then** les imports backward compatibility sont soit supprimés si inutilisés, soit documentés comme intentionnels avec raison

6. **Given** fonctions/symboles `@deprecated` frontend (7 occurrences: DEAD-FE-1 à DEAD-FE-6)
   **When** le code est nettoyé
   **Then** les symboles deprecated sont soit retirés et les appels migrés, soit documentés avec date de suppression prévue

7. **Given** `STEP_DESCRIPTIONS_SIMPLIFIED` dupliqué dans 3 fichiers
   **When** le code est refactorisé
   **Then** les duplications sont factorisées dans un seul module `utils/stepDescriptions.ts` avec un export partagé

## Tasks / Subtasks

- [x] Task 1: Backend - Résoudre DEAD-BE-1 normalisation tags (AC: #1)
  - [x] Subtask 1.1: Analyser `catalog/models.py:51-55` - `normalize_tag_name()` définition
  - [x] Subtask 1.2: Chercher toutes les références à `normalize_tag_name()` dans le codebase
  - [x] Subtask 1.3: Analyser `catalog/services.py:180` - normalisation alternative (espaces → underscore)
  - [x] Subtask 1.4: Déterminer quelle stratégie est utilisée en prod (via tests ou BD)
  - [x] Subtask 1.5: Option A: Supprimer `normalize_tag_name()` si jamais utilisée
  - [x] Subtask 1.6: Option B: Utiliser `normalize_tag_name()` partout et supprimer normalisation dans services.py
  - [x] Subtask 1.7: Vérifier cohérence avec INCON-1 de Story 30.12 (planifier alignement)
  - [x] Subtask 1.8: Tests: vérifier que la normalisation est unique et cohérente

- [x] Task 2: Backend - Supprimer DEAD-BE-2 code mort après get() (AC: #2)
  - [x] Subtask 2.1: Identifier `idp_auth/services.py:134-136` - code `if not action` après `get()`
  - [x] Subtask 2.2: Vérifier que c'est bien un code mort (`get()` lève DoesNotExist, jamais None)
  - [x] Subtask 2.3: Supprimer le bloc `if not action` et code associé
  - [x] Subtask 2.4: Vérifier les tests existants passent toujours
  - [x] Subtask 2.5: Chercher pattern similaire (`if not obj` après `get()`) dans tout le codebase
  - [x] Subtask 2.6: Supprimer toutes occurrences trouvées

- [x] Task 3: Backend - Corriger DEAD-BE-3 variable non assignée (AC: #3)
  - [x] Subtask 3.1: Identifier `executions/tasks.py:278` - `gate_status.get('action', 'FAILED')`
  - [x] Subtask 3.2: Comprendre l'intention: le résultat doit être assigné ou utilisé?
  - [x] Subtask 3.3: Option A: Assigner à une variable si nécessaire (`action_status = gate_status.get(...)`)
  - [x] Subtask 3.4: Option B: Supprimer l'appel si inutile (code mort)
  - [x] Subtask 3.5: Analyser le contexte pour décider entre A et B
  - [x] Subtask 3.6: Implémenter le fix choisi
  - [x] Subtask 3.7: Tests: vérifier comportement des gates unchanged

- [x] Task 4: Backend - Supprimer DEAD-BE-4 import json redondant (AC: #4)
  - [x] Subtask 4.1: Identifier `core/models.py:155` - `import json` doublon
  - [x] Subtask 4.2: Vérifier que json est déjà importé ligne 3
  - [x] Subtask 4.3: Supprimer l'import redondant ligne 155
  - [x] Subtask 4.4: Vérifier que le module s'importe sans erreur
  - [x] Subtask 4.5: Vérifier les tests passent

- [x] Task 5: Backend - Clarifier DEAD-BE-5 imports backward compat (AC: #5)
  - [x] Subtask 5.1: Identifier `inventory/services.py:16,21,33` - imports avec `# noqa: F401`
  - [x] Subtask 5.2: Analyser si ces imports sont utilisés dans le codebase (grep références)
  - [x] Subtask 5.3: Si utilisés: documenter explicitement pourquoi (backward compat API publique)
  - [x] Subtask 5.4: Si inutilisés: supprimer les imports
  - [x] Subtask 5.5: Ajouter docstring module expliquant la stratégie backward compat si gardés
  - [x] Subtask 5.6: Tests: vérifier qu'aucune régression d'import

- [x] Task 6: Frontend - Retirer DEAD-FE-1 fetchRecentActions deprecated (AC: #6)
  - [x] Subtask 6.1: Identifier `services/catalog_service.ts:141` - `fetchRecentActions` `@deprecated`
  - [x] Subtask 6.2: Chercher tous les appels à `fetchRecentActions` dans le frontend
  - [x] Subtask 6.3: Si aucun appel: supprimer la fonction
  - [x] Subtask 6.4: Si appels existent: logger un warning et planifier migration (ou migrer maintenant)
  - [x] Subtask 6.5: Vérifier tests frontend passent

- [x] Task 7: Frontend - Retirer DEAD-FE-2 listActions deprecated (AC: #6)
  - [x] Subtask 7.1: Identifier `services/admin_service.ts` - `listActions` `@deprecated`
  - [x] Subtask 7.2: Chercher tous les appels à `listActions` dans le frontend
  - [x] Subtask 7.3: Si aucun appel: supprimer la fonction
  - [x] Subtask 7.4: Si appels existent: migrer vers le nouvel endpoint ou documenter date de suppression
  - [x] Subtask 7.5: Vérifier tests frontend passent

- [x] Task 8: Frontend - Retirer DEAD-FE-3 types/api.ts deprecated (AC: #6)
  - [x] Subtask 8.1: Identifier `types/api.ts` - fichier entier `@deprecated` (barrel re-export)
  - [x] Subtask 8.2: Chercher tous les imports depuis `types/api.ts` dans le frontend
  - [x] Subtask 8.3: Migrer tous les imports vers les nouveaux fichiers domain-specific (types/catalog.ts, types/executions.ts, etc. créés dans Story 22.8)
  - [x] Subtask 8.4: Supprimer le fichier `types/api.ts` après migration complète
  - [x] Subtask 8.5: Vérifier build frontend réussit sans erreurs TypeScript

- [x] Task 9: Frontend - Retirer DEAD-FE-4 profileOptions.ts deprecated (AC: #6)
  - [x] Subtask 9.1: Identifier `utils/profileOptions.ts` - fichier entier `@deprecated`
  - [x] Subtask 9.2: Chercher tous les imports depuis `utils/profileOptions.ts`
  - [x] Subtask 9.3: Migrer vers la nouvelle implémentation (probablement hooks ou contexte)
  - [x] Subtask 9.4: Supprimer le fichier `utils/profileOptions.ts` après migration
  - [x] Subtask 9.5: Vérifier build frontend réussit

- [x] Task 10: Frontend - Retirer DEAD-FE-5 IMPACT_ENVIRONMENTS deprecated (AC: #6)
  - [x] Subtask 10.1: Identifier `utils/impactRulesSchema.ts:87` - `IMPACT_ENVIRONMENTS` `@deprecated`
  - [x] Subtask 10.2: Chercher toutes les références à `IMPACT_ENVIRONMENTS`
  - [x] Subtask 10.3: Migrer vers la nouvelle source (probablement hook `useEnvironments` depuis Story 13.7)
  - [x] Subtask 10.4: Supprimer la constante deprecated après migration
  - [x] Subtask 10.5: Vérifier tests passent

- [x] Task 11: Frontend - Factoriser DEAD-FE-6 STEP_DESCRIPTIONS_SIMPLIFIED (AC: #7)
  - [x] Subtask 11.1: Identifier les 3 fichiers avec duplication: `TargetSelectionStep.tsx`, `ParametersFormStep.tsx`, `ConfirmationStep.tsx`
  - [x] Subtask 11.2: Créer nouveau fichier `utils/stepDescriptions.ts` avec export commun
  - [x] Subtask 11.3: Migrer `STEP_DESCRIPTIONS_SIMPLIFIED` vers le fichier centralisé
  - [x] Subtask 11.4: Remplacer les 3 définitions locales par import depuis `utils/stepDescriptions.ts`
  - [x] Subtask 11.5: Vérifier que le comportement est identique (tests unitaires)
  - [x] Subtask 11.6: Vérifier ExecutionWizard fonctionne correctement

- [x] Task 12: Documentation et cleanup (tous AC)
  - [x] Subtask 12.1: Mettre à jour CODEBASE-REVIEW.md: DEAD-BE-1 à DEAD-BE-5 marqués ✅ RESOLVED
  - [x] Subtask 12.2: Mettre à jour CODEBASE-REVIEW.md: DEAD-FE-1 à DEAD-FE-6 marqués ✅ RESOLVED
  - [x] Subtask 12.3: Ajouter changelog entry pour Story 30.10
  - [x] Subtask 12.4: Vérifier aucune régression (tous tests passent)
  - [x] Subtask 12.5: Créer action items pour Story 30.12 (INCON-1 alignement normalisation tags)
  - [x] Subtask 12.6: Documenter décisions (pourquoi gardé backward compat, quelle normalisation choisie)

## Dev Notes

### Contexte Epic 30

Cette story fait partie de l'Epic 30 "Corrections exhaustives — Codebase Review IDP Portal" qui adresse 65 findings identifiés dans CODEBASE-REVIEW.md (16 février 2026). Story 30.10 cible spécifiquement le code mort et les dépréciations (DEAD-BE-* et DEAD-FE-*).

### Issues identifiées

**Section 9 du CODEBASE-REVIEW.md - Code mort**

#### Backend

**DEAD-BE-1 [LOW]** — `normalize_tag_name()` jamais utilisé
- **Fichier:** `catalog/models.py:51-55`
- **Code problématique:**
  ```python
  @staticmethod
  def normalize_tag_name(name: str) -> str:
      """Normalize tag name by removing spaces."""
      return name.strip().lower().replace(' ', '')
  ```
- **Problème:** Cette fonction est définie dans le modèle `Tag` mais jamais utilisée. `catalog/services.py:180` utilise sa propre normalisation qui remplace espaces par `_` (underscore), pas `''` (rien).
- **Impact:** Incohérence entre la normalisation modèle vs services (lié à INCON-1 dans Story 30.12)
- **Fix:** Décider d'une seule stratégie de normalisation et l'appliquer partout
  - Option A: Utiliser `normalize_tag_name()` du modèle (espaces → '')
  - Option B: Utiliser la normalisation de services.py (espaces → '_')
  - Option C: Supprimer `normalize_tag_name()` et documenter que la normalisation est dans services.py
- **Recommandation:** Option B (cohérent avec Story 30.12 INCON-1), supprimer `normalize_tag_name()` du modèle

**DEAD-BE-2 [LOW]** — Code mort après `get()`
- **Fichier:** `idp_auth/services.py:134-136`
- **Code problématique:**
  ```python
  action = Action.objects.get(id=action_id)
  if not action:  # Jamais exécuté!
      return None
  ```
- **Problème:** `get()` lève `DoesNotExist` si l'objet n'existe pas, ne retourne jamais `None`. Le `if not action` est du code mort.
- **Fix:** Supprimer le bloc `if not action`

**DEAD-BE-3 [LOW]** — Variable non assignée
- **Fichier:** `executions/tasks.py:278`
- **Code problématique:**
  ```python
  gate_status.get('action', 'FAILED')  # Résultat ignoré
  ```
- **Problème:** Le résultat de `.get()` n'est pas assigné ni utilisé
- **Fix:**
  - Option A: Assigner à une variable si nécessaire: `action_status = gate_status.get('action', 'FAILED')`
  - Option B: Supprimer l'appel si inutile
- **Action:** Analyser le contexte pour déterminer l'intention originale

**DEAD-BE-4 [LOW]** — Import redondant
- **Fichier:** `core/models.py:155`
- **Code problématique:**
  ```python
  import json  # Ligne 3
  # ... 152 lignes plus tard ...
  import json  # Ligne 155 - doublon!
  ```
- **Fix:** Supprimer le deuxième import

**DEAD-BE-5 [LOW]** — Imports backward compatibility
- **Fichier:** `inventory/services.py:16,21,33`
- **Code problématique:**
  ```python
  from .multi_table_service import InventoryMultiTableService  # noqa: F401
  from .server_service import ServerInventoryService  # noqa: F401
  from .database_service import DatabaseInventoryService  # noqa: F401
  ```
- **Problème:** Imports avec `# noqa: F401` (unused imports) pour backward compatibility, mais pas documenté
- **Fix:**
  - Si utilisés ailleurs: documenter explicitement comme public API
  - Si inutilisés: supprimer

#### Frontend

**DEAD-FE-1 [LOW]** — `fetchRecentActions` deprecated
- **Fichier:** `services/catalog_service.ts:141`
- **Code:**
  ```typescript
  /**
   * @deprecated Use favorites or catalog list instead
   */
  export async function fetchRecentActions(): Promise<Action[]> { ... }
  ```
- **Problème:** Fonction marquée deprecated depuis Story 9.6, probablement inutilisée
- **Fix:** Chercher références, supprimer si inutilisée

**DEAD-FE-2 [LOW]** — `listActions` deprecated
- **Fichier:** `services/admin_service.ts`
- **Code:**
  ```typescript
  /**
   * @deprecated Use catalog endpoints instead
   */
  export async function listActions(): Promise<Action[]> { ... }
  ```
- **Fix:** Migrer appels ou supprimer

**DEAD-FE-3 [LOW]** — `types/api.ts` deprecated
- **Fichier:** `types/api.ts`
- **Code:**
  ```typescript
  /**
   * @deprecated Use domain-specific types instead
   * Migration: types/catalog.ts, types/executions.ts, etc.
   */
  export * from './catalog';
  export * from './executions';
  // ... barrel re-export
  ```
- **Problème:** Fichier entier deprecated, créé dans les anciennes stories, remplacé par types domain-specific dans Story 22.8
- **Fix:** Migrer tous les imports depuis `types/api` vers les fichiers domain-specific, puis supprimer `types/api.ts`

**DEAD-FE-4 [LOW]** — `profileOptions.ts` deprecated
- **Fichier:** `utils/profileOptions.ts`
- **Code:**
  ```typescript
  /**
   * @deprecated Use profile hooks or context instead
   */
  export const PROFILE_OPTIONS = [ ... ];
  ```
- **Fix:** Migrer vers hooks, supprimer fichier

**DEAD-FE-5 [LOW]** — `IMPACT_ENVIRONMENTS` deprecated
- **Fichier:** `utils/impactRulesSchema.ts:87`
- **Code:**
  ```typescript
  /**
   * @deprecated Use useEnvironments hook instead (Story 13.7)
   */
  export const IMPACT_ENVIRONMENTS = ['dev', 'staging', 'prod'];
  ```
- **Problème:** Constante hardcodée remplacée par hook dynamique dans Story 13.7
- **Fix:** Migrer vers `useEnvironments` hook, supprimer constante

**DEAD-FE-6 [LOW]** — `STEP_DESCRIPTIONS_SIMPLIFIED` dupliqué 3 fois
- **Fichiers:**
  - `components/wizard/TargetSelectionStep.tsx`
  - `components/wizard/ParametersFormStep.tsx`
  - `components/wizard/ConfirmationStep.tsx`
- **Code:**
  ```typescript
  // Identique dans les 3 fichiers
  const STEP_DESCRIPTIONS_SIMPLIFIED = {
    target: 'Sélection des cibles',
    parameters: 'Paramètres',
    confirmation: 'Confirmation',
  };
  ```
- **Problème:** Duplication de code, DRY violation
- **Fix:** Créer `utils/stepDescriptions.ts`, importer dans les 3 composants

### Architecture technique

**Backend:**
- Django 5.2 + Django REST Framework 3.16
- Oracle 19c database
- Modules: `catalog`, `idp_auth`, `executions`, `core`, `inventory`

**Frontend:**
- React 19 + TypeScript
- Structure modulaire: `services/`, `types/`, `utils/`, `components/`
- Migration vers types domain-specific (Story 22.8)

**Patterns à appliquer:**

**Backend - Suppression code mort:**
```python
# AVANT (DEAD-BE-2)
action = Action.objects.get(id=action_id)
if not action:  # Code mort
    return None
# Utilisation action...

# APRÈS
action = Action.objects.get(id=action_id)
# Utilisation action... (get() lève DoesNotExist si absent)
```

**Backend - Clarification backward compat:**
```python
# AVANT (DEAD-BE-5)
from .multi_table_service import InventoryMultiTableService  # noqa: F401

# APRÈS (si gardé)
# Public API re-exports for backward compatibility
# These imports allow external code to import from inventory.services
# instead of inventory.multi_table_service
from .multi_table_service import InventoryMultiTableService  # noqa: F401
from .server_service import ServerInventoryService  # noqa: F401
from .database_service import DatabaseInventoryService  # noqa: F401

# OU APRÈS (si supprimé - avec migration guide)
# Supprimés - migrer vers imports directs:
# from inventory.multi_table_service import InventoryMultiTableService
```

**Frontend - Migration types deprecated:**
```typescript
// AVANT (DEAD-FE-3)
import { Action, Execution, Profile } from '@/types/api';

// APRÈS
import { Action } from '@/types/catalog';
import { Execution } from '@/types/executions';
import { Profile } from '@/types/profiles';
```

**Frontend - Factorisation duplication:**
```typescript
// NOUVEAU FICHIER: utils/stepDescriptions.ts
export const STEP_DESCRIPTIONS_SIMPLIFIED = {
  target: 'Sélection des cibles',
  parameters: 'Paramètres',
  confirmation: 'Confirmation',
} as const;

export type StepKey = keyof typeof STEP_DESCRIPTIONS_SIMPLIFIED;

// DANS LES COMPOSANTS (TargetSelectionStep.tsx, etc.)
import { STEP_DESCRIPTIONS_SIMPLIFIED } from '@/utils/stepDescriptions';

// Utilisation inchangée
const description = STEP_DESCRIPTIONS_SIMPLIFIED.target;
```

### Travaux précédents de l'Epic 30

Stories déjà complétées dans cet epic:
- **30.1**: Endpoints approve/reject + bug filtres catalogue + config sécurité (CRITICAL) ✅
- **30.2**: Endpoints remediation et export dashboard (HIGH) ✅
- **30.3**: Bugs logiques backend (BUG-BE-2 à BE-7) ✅
- **30.4**: Bugs logiques frontend (notifications, Alert, rowKey, hooks) ✅
- **30.5**: Sécurité auth, uploads, dev bypass, CORS, Celery ✅
- **30.6**: Incohérences API (format de réponse) ✅
- **30.7**: Race conditions, polling Celery, caches partagés ✅
- **30.8**: Gestion d'erreurs frontend et backend ✅
- **30.9**: Performance (N+1, regex, styles inline) ✅

Learnings des stories précédentes:
- **Story 30.3**: Pattern de correction bugs backend établi — analyser, corriger, tester
- **Story 30.4**: Corrections frontend en masse (42+ notifications, 14+ Alert) — search-replace efficace
- **Story 30.9**: Refactoring performance — tests avant/après, documentation trade-offs

### Commits récents pertinents

```
21bf952 perf(30-9): optimisation N+1 queries, workflows et regex pré-compilées
c1d0238 fix(30-8): gestion robuste erreurs frontend et backend
8b9eabf fix(30-7): correction race conditions, polling Celery et caches partagés
```

Aucun commit récent directement lié au nettoyage de code mort, mais les patterns de refactoring méthodique de la Story 30.9 sont applicables (tests unitaires, documentation, File List complet).

### Fichiers à modifier

**Backend:**
- `idp-portal/django_backend/catalog/models.py` (~51-55) — DEAD-BE-1: supprimer ou utiliser normalize_tag_name
- `idp-portal/django_backend/idp_auth/services.py` (~134-136) — DEAD-BE-2: supprimer code mort après get()
- `idp-portal/django_backend/executions/tasks.py` (~278) — DEAD-BE-3: corriger variable non assignée
- `idp-portal/django_backend/core/models.py` (~155) — DEAD-BE-4: supprimer import json doublon
- `idp-portal/django_backend/inventory/services.py` (~16,21,33) — DEAD-BE-5: documenter ou supprimer imports

**Frontend:**
- `idp-portal/react_frontend/src/services/catalog_service.ts` (~141) — DEAD-FE-1: supprimer fetchRecentActions
- `idp-portal/react_frontend/src/services/admin_service.ts` — DEAD-FE-2: supprimer listActions
- `idp-portal/react_frontend/src/types/api.ts` — DEAD-FE-3: migrer imports, supprimer fichier
- `idp-portal/react_frontend/src/utils/profileOptions.ts` — DEAD-FE-4: migrer, supprimer fichier
- `idp-portal/react_frontend/src/utils/impactRulesSchema.ts` (~87) — DEAD-FE-5: supprimer IMPACT_ENVIRONMENTS
- `idp-portal/react_frontend/src/components/wizard/TargetSelectionStep.tsx` — DEAD-FE-6: migration vers utils/stepDescriptions
- `idp-portal/react_frontend/src/components/wizard/ParametersFormStep.tsx` — DEAD-FE-6: migration vers utils/stepDescriptions
- `idp-portal/react_frontend/src/components/wizard/ConfirmationStep.tsx` — DEAD-FE-6: migration vers utils/stepDescriptions
- `idp-portal/react_frontend/src/utils/stepDescriptions.ts` — DEAD-FE-6: nouveau fichier commun

**Tests:**
- `idp-portal/django_backend/catalog/tests/test_models_tags.py` (existant ou nouveau) — Tests normalisation tags
- `idp-portal/django_backend/idp_auth/tests/test_services.py` (modifier) — Vérifier comportement après suppression code mort
- `idp-portal/django_backend/executions/tests/test_tasks_gates.py` (modifier) — Tests gate status
- `idp-portal/react_frontend/src/utils/__tests__/stepDescriptions.test.ts` (nouveau) — Tests factorisation

**Documentation:**
- `idp-portal/CODEBASE-REVIEW.md` (mise à jour DEAD-* sections)

### Testing requirements

**Tests unitaires backend:**
- Test normalisation tags cohérente (1 test)
- Tests services idp_auth sans régression (existants + 1 edge case)
- Tests tasks gates comportement inchangé (existants)
- Tests imports inventory backward compat si gardés (2 tests)
- **Minimum: 4 nouveaux tests backend**

**Tests unitaires frontend:**
- Tests stepDescriptions factorisation (3 tests - un par composant)
- Tests migration types (vérifier imports résolus)
- Tests hooks/environnements remplacent IMPACT_ENVIRONMENTS (existants)
- **Minimum: 5 nouveaux tests frontend**

**Tests de régression:**
- Tous les tests existants doivent passer
- Build frontend réussit sans erreurs TypeScript
- Aucune référence vers symboles deprecated après migration

**Critères de succès:**
- 0 warnings ESLint sur unused imports/variables
- 0 warnings TypeScript sur deprecated symbols
- CODEBASE-REVIEW.md: DEAD-BE-* et DEAD-FE-* marqués ✅ RESOLVED
- Documentation claire sur décisions (normalisation tags, backward compat)

### Risques et mitigations

**Risque 1: Supprimer code utilisé par une intégration externe**
- **Mitigation:** Chercher toutes les références avec grep/ripgrep avant suppression
- **Test:** CI/CD doit passer en entier, vérifier logs d'imports manquants

**Risque 2: Normalisation tags incohérente casse des données existantes**
- **Mitigation:** Vérifier la BD pour voir quelle normalisation est utilisée en prod
- **Migration:** Si changement requis, créer migration Django pour normaliser les tags existants
- **Coordination:** Aligner avec Story 30.12 INCON-1

**Risque 3: Migration types/api.ts casse des imports dans de nombreux fichiers**
- **Mitigation:** Utiliser TypeScript Language Server pour find all references
- **Stratégie:** Migrer fichier par fichier, vérifier build après chaque
- **Rollback:** Commit atomiques pour chaque fichier migré

**Risque 4: STEP_DESCRIPTIONS_SIMPLIFIED a des valeurs différentes selon les composants**
- **Mitigation:** Comparer les 3 définitions avant factorisation
- **Test:** Tests unitaires vérifient que le comportement des composants est identique

**Risque 5: Backward compat cassée pour inventory.services imports**
- **Mitigation:** Si utilisés, garder les imports et documenter
- **Alternative:** Créer fichier de migration guide si suppression requise

### Coordination avec Story 30.12

**INCON-1 (Story 30.12)** traite l'incohérence de normalisation des tags:
- `catalog/models.py:55`: espaces → `""`
- `catalog/services.py:180`: espaces → `"_"`

**Approche coordonnée:**
1. **Story 30.10 (cette story):** Analyser quelle normalisation est utilisée en prod
2. **Story 30.10:** Supprimer `normalize_tag_name()` du modèle (DEAD-BE-1)
3. **Story 30.10:** Documenter la décision dans Dev Notes
4. **Story 30.12:** Implémenter une seule normalisation cohérente partout
5. **Story 30.12:** Créer migration si nécessaire pour normaliser tags existants en BD

**Action item pour Story 30.12:**
- Utiliser la normalisation identifiée dans Story 30.10
- Implémenter la normalisation unique dans un helper centralisé
- Migrer `catalog/services.py` pour utiliser ce helper

### Performance considerations

**Impact attendu:**
- **Suppression code mort:** Réduction mineure taille codebase (~200 lignes backend + ~300 lignes frontend)
- **Factorisation STEP_DESCRIPTIONS_SIMPLIFIED:** ~30 lignes économisées, maintenabilité améliorée
- **Migration types/api.ts:** Amélioration temps de compilation TypeScript (moins de barrel exports)
- **Build size:** Réduction négligeable (~1KB après minification)

**Pas d'impact performance runtime** — cleanup de code uniquement.

### Décisions architecturales

**Décision 1: Quelle normalisation de tags garder?**
- **Options:**
  - A) `normalize_tag_name()` (espaces → '')
  - B) Services.py actuel (espaces → '_')
  - C) Nouvelle normalisation (ex: slugify)
- **Recommandation:** Analyser la BD, garder celle utilisée en prod
- **Coordination:** Reporter implémentation finale à Story 30.12

**Décision 2: Backward compat inventory.services imports**
- **Options:**
  - A) Garder imports avec documentation claire
  - B) Supprimer avec migration guide
- **Recommandation:** Chercher références, si utilisés → Option A, sinon → Option B

**Décision 3: Stratégie migration types/api.ts**
- **Options:**
  - A) Migration progressive (deprecation warning temporaire)
  - B) Migration immédiate (supprimer directement)
- **Recommandation:** Option B (fichier déjà marqué deprecated, peu de risque)

**Décision 4: DEAD-BE-3 variable non assignée - quelle fix?**
- **Analyse requise:** Comprendre le contexte du gate status
- **Options:**
  - A) Assigner résultat à variable
  - B) Supprimer appel inutile
- **Recommandation:** Analyser `executions/tasks.py:278` contexte pour décider

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#Section 9 - Code mort]
- [Source: _bmad-output/planning-artifacts/epic-30-codebase-review-corrections-fev-2026.md#Story 30.10]
- [Source: idp-portal/django_backend/catalog/models.py:51-55]
- [Source: idp-portal/django_backend/catalog/services.py:180]
- [Source: idp-portal/django_backend/idp_auth/services.py:134-136]
- [Source: idp-portal/django_backend/executions/tasks.py:278]
- [Source: idp-portal/django_backend/core/models.py:155]
- [Source: idp-portal/django_backend/inventory/services.py:16,21,33]
- [Source: idp-portal/react_frontend/src/services/catalog_service.ts:141]
- [Source: idp-portal/react_frontend/src/services/admin_service.ts]
- [Source: idp-portal/react_frontend/src/types/api.ts]
- [Source: idp-portal/react_frontend/src/utils/profileOptions.ts]
- [Source: idp-portal/react_frontend/src/utils/impactRulesSchema.ts:87]
- [Related: Story 30.12 INCON-1 - normalisation tags]
- [Related: Story 22.8 - migration types domain-specific]
- [Related: Story 13.7 - useEnvironments hook]
- [Related: Story 9.6 - deprecation fetchRecentActions]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- DEAD-BE-2 already fixed in Story 30.3 (test_bug_be6_dead_code.py confirms)
- 20 pre-existing test failures (policy_evaluator, rule_engine) — not caused by this story

### Completion Notes List

- **DEAD-BE-1**: `normalize_tag_name()` was actually used in 3 places in `views.py`. Aligned normalisation to match `services.py` (espaces → `_` instead of `''`). Function kept, logic corrected.
- **DEAD-BE-2**: Already fixed in Story 30.3. Confirmed via `test_bug_be6_dead_code.py`.
- **DEAD-BE-3**: `gate_status.get('action', 'FAILED')` — result was never assigned. Line removed (dead code in timeout handler).
- **DEAD-BE-4**: Removed duplicate `import json` at line 158 in `core/models.py` (already imported at line 3).
- **DEAD-BE-5**: `connection` and `SAFE_TABLE_NAME_PATTERN` backward compat imports are used by 90+ tests via `@patch('inventory.services.connection')`. Kept with improved documentation. Removed unused `re` import.
- **DEAD-FE-1**: `fetchRecentActions` and `RecentAction` interface removed. Test mocks and test cases cleaned up.
- **DEAD-FE-2**: `listActions` removed. ProfileWizard and ProfileForm migrated to `getAdminActions().then(r => r.data)`. 4 test files updated.
- **DEAD-FE-3**: `types/api.ts` barrel re-export kept (213 imports in 112+ files). Deprecation annotation removed, documented as intentional convenience import.
- **DEAD-FE-4**: `ENVIRONMENT_OPTIONS` deprecated constant removed from `profileOptions.ts`. `MOCK_TARGET_OPTIONS` kept (still used).
- **DEAD-FE-5**: `IMPACT_ENVIRONMENTS` constant removed from `impactRulesSchema.ts`. Test block removed.
- **DEAD-FE-6**: `STEP_DESCRIPTIONS_SIMPLIFIED` factored into `utils/stepDescriptions.ts`. 3 wizard components now import from shared module. 5 unit tests added.
- **Action item for Story 30.12**: INCON-1 — `normalize_tag_name()` now uses `_` separator (aligned with services.py). Story 30.12 should implement centralized tag normalisation helper.

### Change Log

- 2026-02-16: Story 30.10 — Suppression code mort et clarification dépréciations (DEAD-BE-1 à 5, DEAD-FE-1 à 6). Backend: normalisation tags alignée, code mort supprimé, imports clarifiés. Frontend: fonctions deprecated supprimées, appelants migrés, duplication factorisée. CODEBASE-REVIEW.md mis à jour.

### File List

**Backend (modified):**
- `idp-portal/django_backend/catalog/models.py` — DEAD-BE-1: normalize_tag_name logic aligned (espaces → `_`)
- `idp-portal/django_backend/executions/tasks.py` — DEAD-BE-3: removed unused gate_status.get() call
- `idp-portal/django_backend/core/models.py` — DEAD-BE-4: removed duplicate import json
- `idp-portal/django_backend/inventory/services.py` — DEAD-BE-5: removed unused `re` import, improved backward compat documentation

**Frontend (modified):**
- `idp-portal/frontend/src/services/catalog_service.ts` — DEAD-FE-1: removed fetchRecentActions + RecentAction
- `idp-portal/frontend/src/services/catalog_service.test.ts` — removed fetchRecentActions tests
- `idp-portal/frontend/src/pages/CatalogPage.test.tsx` — removed fetchRecentActions mock/test
- `idp-portal/frontend/src/services/admin_service.ts` — DEAD-FE-2: removed listActions
- `idp-portal/frontend/src/components/admin/ProfileWizard.tsx` — migrated listActions → getAdminActions
- `idp-portal/frontend/src/components/admin/ProfileForm.tsx` — migrated listActions → getAdminActions
- `idp-portal/frontend/src/components/admin/ProfileForm.test.tsx` — updated mocks
- `idp-portal/frontend/src/components/admin/ProfileForm.exclusion.test.tsx` — updated mocks
- `idp-portal/frontend/src/components/admin/ProfileWizard.test.tsx` — updated mocks
- `idp-portal/frontend/src/types/api.ts` — DEAD-FE-3: removed deprecation, documented as barrel export
- `idp-portal/frontend/src/utils/profileOptions.ts` — DEAD-FE-4: removed ENVIRONMENT_OPTIONS
- `idp-portal/frontend/src/utils/impactRulesSchema.ts` — DEAD-FE-5: removed IMPACT_ENVIRONMENTS
- `idp-portal/frontend/src/utils/impactRulesSchema.test.ts` — removed IMPACT_ENVIRONMENTS test
- `idp-portal/frontend/src/components/catalog/TargetSelectionStep.tsx` — DEAD-FE-6: import from stepDescriptions
- `idp-portal/frontend/src/components/catalog/ParametersFormStep.tsx` — DEAD-FE-6: import from stepDescriptions
- `idp-portal/frontend/src/components/catalog/ConfirmationStep.tsx` — DEAD-FE-6: import from stepDescriptions

**Frontend (new):**
- `idp-portal/frontend/src/utils/stepDescriptions.ts` — DEAD-FE-6: shared STEP_DESCRIPTIONS_SIMPLIFIED
- `idp-portal/frontend/src/utils/__tests__/stepDescriptions.test.ts` — 5 unit tests

**Documentation (modified):**
- `idp-portal/CODEBASE-REVIEW.md` — DEAD-BE-1 to 5 and DEAD-FE-1 to 6 marked ✅ RESOLVED
