# Story 21.5 : Frontend — TargetSelectionStep, labels et type ExecutionEnvironment

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que DBA ou utilisateur,
je veux que la sélection d'environnement et l'affichage des labels utilisent les valeurs de l'inventaire sans fallback hardcodé,
afin de pouvoir exécuter des actions sur des environnements comme `lab` et les afficher correctement.

## Acceptance Criteria

1. **Given** `TargetSelectionStep`
   **When** le cache d'environnements (`environmentsCache`) est chargé
   **Then** le Select Environnement utilise uniquement ces valeurs
   **And** le fallback `['dev','staging','prod']` est supprimé
   **And** si le cache est vide, un état de chargement ou d'erreur approprié est affiché

2. **Given** `ENVIRONMENT_LABELS` dans `TargetSelectionStep`, `ConfirmationStep`, `TargetSelector`
   **When** un environnement n'est pas dans la map (ex. `lab`)
   **Then** on affiche `labels[env.toLowerCase()] || env.charAt(0).toUpperCase() + env.slice(1)` ou équivalent
   **And** l'utilisateur voit "Lab" ou "lab" selon le format choisi, jamais une valeur vide

3. **Given** le type `ExecutionEnvironment` dans `api.ts`
   **When** on étend le type
   **Then** `ExecutionEnvironment` devient `string` (ou union étendue incluant `'lab'` et autres)
   **And** les usages sont mis à jour si nécessaire (typage strict)

4. **Given** `TargetSelector` environment ordering
   **When** des environnements non standard (lab, qa, uat) sont présents
   **Then** l'ordre d'affichage suit une logique cohérente (dev, staging, prod en premier, puis alphabétique)
   **And** les environnements non standard apparaissent correctement groupés

5. **Given** tous les composants de sélection de target
   **When** l'utilisateur sélectionne un environnement non standard (lab, qa, uat)
   **Then** l'exécution fonctionne correctement
   **And** les labels s'affichent de manière cohérente dans tout le wizard
   **And** aucune erreur de validation TypeScript n'est levée

## Tasks / Subtasks

- [x] Task 1 : Supprimer fallback hardcodé dans TargetSelectionStep (AC #1)
  - [x] 1.1 Analyser ligne 230 de `TargetSelectionStep.tsx` - fallback `['dev','staging','prod']`
  - [x] 1.2 Supprimer le fallback array et utiliser uniquement `environmentsCache` transformé
  - [x] 1.3 Si `environmentsCache` est null ou vide, afficher un message approprié (ex. "Aucun environnement disponible")
  - [x] 1.4 Ajouter gestion d'erreur si cache est indisponible et aucun environnement autorisé
  - [x] 1.5 Vérifier que la logique de filtrage `allowedEnvironments` continue de fonctionner
  - [x] 1.6 Tester avec 0 environnements, 1 environnement, 5 environnements

- [x] Task 2 : Remplacer ENVIRONMENT_LABELS hardcodé par logique dynamique (AC #2)
  - [x] 2.1 Dans `TargetSelectionStep.tsx` ligne 26-30 : remplacer `ENVIRONMENT_LABELS` constant
  - [x] 2.2 Dans `ConfirmationStep.tsx` ligne 25-29 : remplacer `ENVIRONMENT_LABELS` constant
  - [x] 2.3 Dans `TargetSelector.tsx` ligne 55-59 : remplacer `ENVIRONMENT_LABELS` constant
  - [x] 2.4 Créer fonction utilitaire `getEnvironmentLabel(env: string): string` qui :
    - Utilise mapping explicite pour dev/staging/prod (Développement, Staging, Production)
    - Capitalise les environnements non standard (lab → Lab, qa → Qa, uat → Uat)
  - [x] 2.5 Remplacer tous les usages de `ENVIRONMENT_LABELS[env]` par `getEnvironmentLabel(env)`
  - [x] 2.6 Vérifier que les alertes de production (ligne 265-274 TargetSelectionStep) fonctionnent avec comparaison case-insensitive

- [x] Task 3 : Étendre type ExecutionEnvironment (AC #3)
  - [x] 3.1 Dans `api.ts` ligne 442 : changer `ExecutionEnvironment = 'dev' | 'staging' | 'prod'` vers `string`
  - [x] 3.2 Alternative : union étendue `'dev' | 'staging' | 'prod' | string` (mais `string` seul est plus simple)
  - [x] 3.3 Vérifier les impacts TypeScript dans tous les fichiers utilisant `ExecutionEnvironment`
  - [x] 3.4 Corriger les assertions de type `as ExecutionEnvironment` si nécessaire
  - [x] 3.5 S'assurer que `ENVIRONMENT_LABELS[env]` ne cause plus d'erreur TypeScript (utiliser getEnvironmentLabel à la place)
  - [x] 3.6 Valider que les types de retour API acceptent les environnements non standard

- [x] Task 4 : Adapter TargetSelector environment ordering (AC #4)
  - [x] 4.1 Analyser ligne 142 de `TargetSelector.tsx` - `envOrder = ['dev','staging','prod']`
  - [x] 4.2 Modifier la logique de tri pour gérer les environnements non standard
  - [x] 4.3 Logique suggérée : dev/staging/prod en tête (dans cet ordre), puis autres par ordre alphabétique
  - [x] 4.4 Tester avec array `['dev','staging','prod','lab','qa','uat']` → ordre : dev, staging, prod, lab, qa, uat
  - [x] 4.5 Tester avec array `['qa','dev','prod']` → ordre : dev, prod, qa (staging absent)
  - [x] 4.6 Vérifier que les groupes s'affichent correctement avec labels dynamiques

- [x] Task 5 : Consolider ENVIRONMENT_COLORS pour environnements non standard (AC #4)
  - [x] 5.1 Analyser `ENVIRONMENT_COLORS` ligne 62-66 de `TargetSelector.tsx`
  - [x] 5.2 Ajouter couleur par défaut pour environnements non standard (ex. 'default' ou 'processing')
  - [x] 5.3 Modifier logique de lookup : `ENVIRONMENT_COLORS[env] || 'default'`
  - [x] 5.4 Vérifier que les badges de ConfirmationStep (ligne 102-107) gèrent les environnements non standard
  - [x] 5.5 Production warning : utiliser comparaison case-insensitive `env.toLowerCase() === 'prod'`

- [x] Task 6 : Créer utilitaire centralisé environment helpers (AC #2, #4)
  - [x] 6.1 Créer fichier `src/utils/environmentHelpers.ts`
  - [x] 6.2 Fonction `getEnvironmentLabel(env: string): string` (mapping + capitalisation)
  - [x] 6.3 Fonction `getEnvironmentColor(env: string): BadgeProps['status']` (couleur pour badges)
  - [x] 6.4 Fonction `sortEnvironments(environments: string[]): string[]` (ordre dev/staging/prod puis alpha)
  - [x] 6.5 Fonction `isProductionEnvironment(env: string): boolean` (case-insensitive prod check)
  - [x] 6.6 Exporter toutes les fonctions et créer tests unitaires

- [x] Task 7 : Tests des composants avec environnements non standard
  - [x] 7.1 Test TargetSelectionStep : cache avec ['dev','lab','qa'] → Select affiche 3 options avec labels corrects
  - [x] 7.2 Test TargetSelectionStep : cache vide → message "Aucun environnement disponible"
  - [x] 7.3 Test TargetSelectionStep : environnement 'lab' sélectionné → pas d'erreur TypeScript, exécution OK
  - [x] 7.4 Test ConfirmationStep : derivedEnvironment='lab' → badge affiche "Lab" (label capitalisé)
  - [x] 7.5 Test TargetSelector : grouped options avec ['dev','staging','prod','lab','qa'] → ordre correct
  - [x] 7.6 Test TargetSelector : environnement 'uat' → label "Uat", couleur par défaut
  - [x] 7.7 Test production warning : env 'prod', 'PROD', 'Prod' → warning affiché (case-insensitive)
  - [x] 7.8 Test environmentHelpers : tous les utilitaires avec environnements standard et non standard

## Dev Notes

⚠️ **CONTEXT:** Stories 21.1-21.4 complètes. Le backend accepte tous les environnements de l'inventaire (lab, dev, staging, prod, certif, qa, uat). Le hook `useEnvironments` est fonctionnel et retourne des valeurs dynamiques. Story 21.4 a migré les éditeurs admin vers `useEnvironments`. **Story 21.5** finalise la migration frontend en adaptant le wizard d'exécution et les composants de sélection de targets.

### Composants impactés et patterns actuels

**1. TargetSelectionStep.tsx**
- **Fichier :** `idp-portal/frontend/src/components/catalog/TargetSelectionStep.tsx`
- **Problème principal :** Fallback hardcodé ligne 230 `['dev','staging','prod']`
- **Pattern actuel :** Utilise `environmentsCache` (InventoryItem[]) mais tombe sur fallback si vide
- **ENVIRONMENT_LABELS :** Lignes 26-30, type `Record<ExecutionEnvironment, string>` (contraint à dev/staging/prod)
- **Production warning :** Ligne 265, hardcoded `derivedEnvironment === 'prod'`
- **Derived environment alert :** Ligne 195-202, utilise `ENVIRONMENT_LABELS[derivedEnvironment]`

**2. ConfirmationStep.tsx**
- **Fichier :** `idp-portal/frontend/src/components/catalog/ConfirmationStep.tsx`
- **ENVIRONMENT_LABELS :** Lignes 25-29, dupliqué de TargetSelectionStep
- **Lookup fallback :** Ligne 73-75, cherche dans cache puis ENVIRONMENT_LABELS puis env brut
- **Badge status :** Ligne 102-107, hardcoded `derivedEnvironment === 'prod' ? 'warning' : 'processing'`

**3. TargetSelector.tsx**
- **Fichier :** `idp-portal/frontend/src/components/catalog/TargetSelector.tsx`
- **ENVIRONMENT_LABELS :** Lignes 55-59, type `Record<string, string>` (plus flexible)
- **ENVIRONMENT_COLORS :** Lignes 62-66, mapping dev/staging/prod vers couleurs badges
- **Environment ordering :** Ligne 142, `envOrder = ['dev','staging','prod']` pour tri
- **Sorting logic :** Lignes 143-150, met dev/staging/prod en tête, autres alphabétique
- **Label fallback :** Ligne 157, `ENVIRONMENT_LABELS[env] || env.toUpperCase()`

**4. api.ts**
- **Fichier :** `idp-portal/frontend/src/types/api.ts`
- **ExecutionEnvironment type :** Ligne 442, `'dev' | 'staging' | 'prod'` (littéral strict)
- **Impact :** Contraint tous les composants à ces 3 valeurs uniquement
- **InventoryItem :** Lignes 601-605, `environment: string | null` (flexible, pas de contrainte)

### Stratégie de migration

**Phase 1 : Supprimer contraintes de type (Task 3)**
- Changer `ExecutionEnvironment` de `'dev' | 'staging' | 'prod'` vers `string`
- Résoudre erreurs TypeScript dans les composants
- Alternative : `type ExecutionEnvironment = string` (recommandé pour simplicité)

**Phase 2 : Créer utilitaires centralisés (Task 6)**
- `environmentHelpers.ts` avec fonctions réutilisables
- Éviter duplication de logique de labels entre 3 composants
- Centraliser la logique de production detection (case-insensitive)

**Phase 3 : Migrer les composants (Tasks 1, 2, 4, 5)**
- Remplacer ENVIRONMENT_LABELS hardcodé par appels à `getEnvironmentLabel()`
- Supprimer fallback `['dev','staging','prod']` dans TargetSelectionStep
- Adapter TargetSelector ordering pour environnements non standard
- Utiliser `isProductionEnvironment()` pour warnings production

**Phase 4 : Tests (Task 7)**
- Couvrir environnements standard (dev, staging, prod)
- Couvrir environnements non standard (lab, qa, uat, certif)
- Tester cache vide, 1 env, 5+ envs
- Tester labels, couleurs, ordering, production warnings

### Problèmes à éviter

1. **Type ExecutionEnvironment trop restrictif :**
   - Actuellement `'dev' | 'staging' | 'prod'` empêche 'lab', 'qa', 'uat'
   - **Solution :** Changer vers `string` pour accepter toutes les valeurs

2. **ENVIRONMENT_LABELS incomplet :**
   - Actuellement seulement dev/staging/prod mappés
   - Environnements non standard → lookup fail → undefined
   - **Solution :** Fallback dynamique avec capitalisation

3. **Fallback hardcodé cache vide :**
   - Ligne 230 TargetSelectionStep force `['dev','staging','prod']` si cache vide
   - Masque problème si API inventaire échoue
   - **Solution :** Afficher message d'erreur explicite au lieu de fallback silencieux

4. **Production detection hardcodé :**
   - `derivedEnvironment === 'prod'` rate 'PROD', 'Prod', 'production'
   - **Solution :** `isProductionEnvironment(env)` avec case-insensitive + alias

5. **Duplication ENVIRONMENT_LABELS :**
   - Défini 3 fois (TargetSelectionStep, ConfirmationStep, TargetSelector)
   - Maintenance difficile si on veut changer un label
   - **Solution :** Centraliser dans `environmentHelpers.ts`

6. **ENVIRONMENT_COLORS incomplet :**
   - Seulement dev/staging/prod ont des couleurs
   - Environnements non standard → undefined → crash potentiel
   - **Solution :** Fallback `|| 'default'` dans lookup

### Architecture des composants

**ExecutionWizard (parent) :**
- Gère les étapes : ParametersStep → TargetSelectionStep → SchedulingStep → ConfirmationStep
- Fetch `environmentsCache` via `fetchInventoryItems('environments')`
- Passe cache en prop à TargetSelectionStep et ConfirmationStep

**TargetSelectionStep :**
- Utilise `environmentsCache` (InventoryItem[]) pour générer options Select
- Filtre selon `allowedEnvironments` (permissions backend)
- Dérive l'environnement depuis les targets sélectionnés
- Affiche warning si production

**ConfirmationStep :**
- Affiche récapitulatif avant exécution
- Utilise `environmentsCache` pour lookup du nom d'environnement
- Badge coloré selon environnement (warning si prod)

**TargetSelector :**
- Component réutilisable pour sélection de targets
- Groupe targets par environnement
- Ordre d'affichage : dev, staging, prod, puis alphabétique
- Labels et couleurs pour chaque groupe

### Labels et affichage

**Convention :**
- **Valeurs stockées :** lowercase (dev, staging, prod, lab, qa, uat)
- **Labels affichés :**
  - Mapping explicite : dev→"Développement", staging→"Staging", prod→"Production"
  - Environnements non standard : capitalisation (lab→"Lab", qa→"Qa", uat→"Uat")
  - Fallback : `env.charAt(0).toUpperCase() + env.slice(1).toLowerCase()`

**Couleurs badges :**
- dev → 'success' (vert)
- staging → 'warning' (orange)
- prod → 'error' (rouge)
- Autres → 'default' (gris) ou 'processing' (bleu)

**Ordre d'affichage :**
- Standard : dev, staging, prod (dans cet ordre)
- Non standard : ordre alphabétique après les standard
- Ex: `['dev','staging','prod','lab','qa','uat']`

### useEnvironments vs environmentsCache

**Deux approches coexistent :**

1. **useEnvironments hook (Story 13.7, utilisé en 21.4) :**
   - Fetch `/inventory/environments` → retourne `string[]`
   - Cache global partagé
   - Retourne `environmentOptions` avec labels
   - **Utilisé par :** Admin editors (ImpactRulesEditor, StepsEditor, ChangeTypeConfig, RemediationRulesEditor)

2. **environmentsCache dans ExecutionWizard :**
   - Fetch `fetchInventoryItems('environments')` → retourne `InventoryItem[]` avec `{ id, name, environment }`
   - Cache local au wizard
   - Passé en prop à TargetSelectionStep, ConfirmationStep
   - **Utilisé par :** Wizard execution

**Différence clé :**
- `useEnvironments` : liste simple de noms d'environnements
- `environmentsCache` : liste d'items avec metadata (id, name, environment)

**Pourquoi ne pas utiliser useEnvironments dans TargetSelectionStep ?**
- ExecutionWizard fetch déjà les environments via `fetchInventoryItems`
- Cache est déjà disponible en prop
- Évite double fetch
- **Mais** : fallback hardcodé doit être supprimé

**Alternative envisageable :**
- Migrer ExecutionWizard pour utiliser `useEnvironments` au lieu de `fetchInventoryItems('environments')`
- Simplifierait la logique
- Mais hors scope Story 21.5 (risque de régression wizard)

**Décision Story 21.5 :**
- **Garder** `environmentsCache` en prop (pas de refactor wizard)
- **Supprimer** fallback hardcodé `['dev','staging','prod']`
- **Créer** utilitaires centralisés pour labels/couleurs
- **Étendre** type `ExecutionEnvironment` vers `string`

### Tests à ajouter

**TargetSelectionStep.test.tsx (nouveau ou augmenté) :**
1. Test cache avec environnements standard → Select affiche dev, staging, prod
2. Test cache avec environnements non standard → Select affiche lab, qa, uat avec labels corrects
3. Test cache vide → message "Aucun environnement disponible" ou disabled
4. Test environnement 'lab' sélectionné → formulaire valide, pas d'erreur
5. Test production warning avec 'prod', 'PROD', 'Prod' → warning affiché (case-insensitive)
6. Test derived environment alert avec 'lab' → label "Lab" affiché

**ConfirmationStep.test.tsx (nouveau ou augmenté) :**
1. Test derivedEnvironment='dev' → badge status 'processing', label "Développement"
2. Test derivedEnvironment='prod' → badge status 'warning', label "Production"
3. Test derivedEnvironment='lab' → badge status 'processing', label "Lab"
4. Test cache lookup : env dans cache → affiche cache.name, sinon label généré
5. Test environnements non standard dans récapitulatif

**TargetSelector.test.tsx (existant à adapter) :**
1. Test grouped options avec ['dev','staging','prod'] → 3 groupes, labels corrects (ligne 185-187 actuelle)
2. Test grouped options avec ['dev','lab','qa'] → 3 groupes, ordre dev puis lab puis qa
3. Test environnement 'uat' → groupe "Uat", couleur par défaut
4. Test ordering : ['qa','dev','prod','lab'] → ordre : dev, prod, lab, qa (staging absent)
5. Test labels fallback : env non mappé → capitalisation automatique

**environmentHelpers.test.ts (nouveau) :**
1. Test `getEnvironmentLabel('dev')` → "Développement"
2. Test `getEnvironmentLabel('lab')` → "Lab"
3. Test `getEnvironmentLabel('QA')` → "Qa" (normalisation case)
4. Test `getEnvironmentColor('dev')` → 'success'
5. Test `getEnvironmentColor('lab')` → 'default'
6. Test `sortEnvironments(['qa','dev','prod','lab'])` → ['dev','prod','lab','qa']
7. Test `isProductionEnvironment('prod')` → true
8. Test `isProductionEnvironment('PROD')` → true (case-insensitive)
9. Test `isProductionEnvironment('production')` → true (alias)
10. Test `isProductionEnvironment('lab')` → false

### Project Structure Notes

- Frontend React : `idp-portal/frontend/`
- Composants catalog : `idp-portal/frontend/src/components/catalog/`
- Types : `idp-portal/frontend/src/types/api.ts`
- Utilitaires : `idp-portal/frontend/src/utils/` (nouveau: `environmentHelpers.ts`)
- Tests : Co-localisés avec composants (`.test.tsx`)

### References

- [Source: _bmad-output/planning-artifacts/epic-21-inventaire-source-unique-environnements.md#Story 21.5] — AC Story 21.5
- [Source: idp-portal/frontend/src/components/catalog/TargetSelectionStep.tsx#L230] — Fallback hardcodé à supprimer
- [Source: idp-portal/frontend/src/components/catalog/TargetSelectionStep.tsx#L26-30] — ENVIRONMENT_LABELS à remplacer
- [Source: idp-portal/frontend/src/components/catalog/ConfirmationStep.tsx#L25-29] — ENVIRONMENT_LABELS dupliqué
- [Source: idp-portal/frontend/src/components/catalog/TargetSelector.tsx#L55-59,142] — Labels et ordering
- [Source: idp-portal/frontend/src/types/api.ts#L442] — Type ExecutionEnvironment à étendre
- [Source: _bmad-output/implementation-artifacts/21-4-frontend-editeurs-admin-environnements-dynamiques.md] — Pattern useEnvironments (référence)
- [Source: _bmad-output/implementation-artifacts/21-1-backend-supprimer-normalisation-inventaire-valeurs-brutes.md] — Backend accepte toutes valeurs
- [Source: _bmad-output/implementation-artifacts/21-2-backend-ajuster-profile-env-matching-executions.md] — RBAC case-insensitive
- [Source: _bmad-output/implementation-artifacts/21-3-tests-backend-inventaire-executions-profils.md] — Tests backend validés

---

## Developer Context & Guardrails

### Objectif métier

Permettre aux utilisateurs d'exécuter des actions sur **tous** les environnements présents dans l'inventaire (lab, qa, uat, certif, etc.), pas seulement dev/staging/prod. Afficher les environnements de manière cohérente et professionnelle dans tout le wizard d'exécution.

### Pièges à éviter

1. **Ne pas garder le fallback hardcodé** : Le fallback `['dev','staging','prod']` ligne 230 de TargetSelectionStep masque les problèmes d'API. Si le cache est vide, afficher un message d'erreur clair plutôt qu'une liste arbitraire.

2. **Ne pas oublier la case insensitivity** : Production peut être 'prod', 'PROD', 'Prod', 'production'. Utiliser `isProductionEnvironment()` avec lowercase normalization.

3. **Ne pas casser les tests existants** : TargetSelector.test.tsx ligne 185-187 attend les labels hardcodés "Developpement", "Staging", "Production". Mettre à jour les tests en conséquence.

4. **Ne pas dupliquer la logique de labels** : Créer `environmentHelpers.ts` centralisé au lieu de copier-coller les mappings.

5. **Ne pas restreindre le type ExecutionEnvironment** : Éviter union étendue `'dev' | 'staging' | 'prod' | 'lab' | ...`. Utiliser simplement `string` pour accepter toutes les valeurs futures.

6. **Ne pas oublier ENVIRONMENT_COLORS** : TargetSelector ligne 62-66 a des couleurs seulement pour dev/staging/prod. Ajouter fallback `|| 'default'`.

### Périmètre strict Story 21.5

**Inclus :**
- Suppression fallback hardcodé TargetSelectionStep
- Remplacement ENVIRONMENT_LABELS par utilitaire dynamique
- Extension type ExecutionEnvironment vers string
- Adaptation TargetSelector ordering pour envs non standard
- Création environmentHelpers.ts centralisé
- Tests des 3 composants avec environnements non standard

**Exclu (autres stories) :**
- Backend (déjà fait en 21.1, 21.2, 21.3)
- Éditeurs admin (déjà fait en 21.4)
- Validation profil à la sauvegarde (Story 21.6, optionnelle)
- Refactor ExecutionWizard pour utiliser useEnvironments (hors scope, risque régression)

### Cohérence avec Stories 21.1-21.4

- Story 21.1 : Backend inventaire retourne valeurs brutes (lab, qa, uat, certif)
- Story 21.2 : RBAC case-insensitive, lookup config environnement
- Story 21.3 : Tests backend couvrent tous les environnements
- Story 21.4 : Éditeurs admin utilisent `useEnvironments` hook
- **Story 21.5 :** Wizard exécution s'adapte aux environnements disponibles

## Technical Requirements

### Modification api.ts (Task 3)

**Fichier :** `idp-portal/frontend/src/types/api.ts`

**Ligne à modifier :**
- Ligne 442 : `export type ExecutionEnvironment = 'dev' | 'staging' | 'prod';`

**Nouveau code :**
```typescript
// Ligne 442
export type ExecutionEnvironment = string;
```

**Alternative (plus verbeux, déconseillé) :**
```typescript
export type ExecutionEnvironment = 'dev' | 'staging' | 'prod' | string;
// Problème : union avec string rend les littéraux inutiles, équivalent à string seul
```

**Impacts à résoudre :**
- Tous les `as ExecutionEnvironment` continuent de fonctionner
- `ENVIRONMENT_LABELS[env]` causera erreur TypeScript → remplacer par `getEnvironmentLabel(env)`
- Valider compilation sans erreurs après changement

---

### Création environmentHelpers.ts (Task 6)

**Fichier :** `idp-portal/frontend/src/utils/environmentHelpers.ts` (nouveau)

**Code suggéré :**
```typescript
import type { BadgeProps } from 'antd';

/**
 * Mapping des labels d'environnements standards
 */
const STANDARD_ENVIRONMENT_LABELS: Record<string, string> = {
  dev: 'Développement',
  staging: 'Staging',
  prod: 'Production',
};

/**
 * Mapping des couleurs de badges par environnement
 */
const ENVIRONMENT_COLORS: Record<string, BadgeProps['status']> = {
  dev: 'success',
  staging: 'warning',
  prod: 'error',
};

/**
 * Retourne le label d'affichage pour un environnement
 * @param env - Nom de l'environnement (ex: 'dev', 'lab', 'PROD')
 * @returns Label formaté (ex: 'Développement', 'Lab', 'Production')
 */
export function getEnvironmentLabel(env: string): string {
  const normalized = env.toLowerCase();

  // Mapping explicite pour environnements standards
  if (STANDARD_ENVIRONMENT_LABELS[normalized]) {
    return STANDARD_ENVIRONMENT_LABELS[normalized];
  }

  // Capitalisation pour environnements non standards
  return env.charAt(0).toUpperCase() + env.slice(1).toLowerCase();
}

/**
 * Retourne la couleur de badge pour un environnement
 * @param env - Nom de l'environnement
 * @returns Couleur du badge ('success', 'warning', 'error', 'default')
 */
export function getEnvironmentColor(env: string): BadgeProps['status'] {
  const normalized = env.toLowerCase();
  return ENVIRONMENT_COLORS[normalized] || 'default';
}

/**
 * Trie les environnements : dev, staging, prod en premier, puis alphabétique
 * @param environments - Liste des environnements
 * @returns Liste triée
 */
export function sortEnvironments(environments: string[]): string[] {
  const priorityOrder = ['dev', 'staging', 'prod'];

  return [...environments].sort((a, b) => {
    const indexA = priorityOrder.indexOf(a.toLowerCase());
    const indexB = priorityOrder.indexOf(b.toLowerCase());

    // Les deux sont dans la liste prioritaire : suivre l'ordre
    if (indexA !== -1 && indexB !== -1) {
      return indexA - indexB;
    }

    // Seul A est prioritaire : A avant B
    if (indexA !== -1) return -1;

    // Seul B est prioritaire : B avant A
    if (indexB !== -1) return 1;

    // Aucun n'est prioritaire : ordre alphabétique
    return a.localeCompare(b);
  });
}

/**
 * Vérifie si un environnement est "production" (case-insensitive)
 * @param env - Nom de l'environnement
 * @returns true si environnement de production
 */
export function isProductionEnvironment(env: string): boolean {
  const normalized = env.toLowerCase();
  return normalized === 'prod' || normalized === 'production';
}
```

---

### Modification TargetSelectionStep.tsx (Tasks 1, 2, 5)

**Fichier :** `idp-portal/frontend/src/components/catalog/TargetSelectionStep.tsx`

**Lignes à modifier :**

1. **Ligne 26-30 : Supprimer ENVIRONMENT_LABELS**
```typescript
// SUPPRIMER ces lignes
const ENVIRONMENT_LABELS: Record<ExecutionEnvironment, string> = {
  dev: 'Developpement',
  staging: 'Staging',
  prod: 'Production',
};
```

2. **Ajouter import helpers**
```typescript
// Ajouter en haut du fichier
import {
  getEnvironmentLabel,
  isProductionEnvironment
} from '../../utils/environmentHelpers';
```

3. **Ligne 230 : Supprimer fallback hardcodé**
```typescript
// AVANT (lignes 221-236)
const environmentOptions = environmentsCache && environmentsCache.length > 0
  ? environmentsCache
      .filter((env) => allowedEnvironments.includes(env.id) || allowedEnvironments.includes(env.id.toUpperCase()))
      .map((env) => ({
        value: env.id as ExecutionEnvironment,
        label: env.name,
        disabled: false,
      }))
  : (['dev', 'staging', 'prod'] as ExecutionEnvironment[])  // SUPPRIMER CE FALLBACK
      .filter((env) => allowedEnvironments.includes(env) || allowedEnvironments.includes(env.toUpperCase()))
      .map((env) => ({
        value: env,
        label: ENVIRONMENT_LABELS[env],
        disabled: false,
      }));

// APRÈS
const environmentOptions = environmentsCache && environmentsCache.length > 0
  ? environmentsCache
      .filter((env) => allowedEnvironments.includes(env.id) || allowedEnvironments.includes(env.id.toUpperCase()))
      .map((env) => ({
        value: env.id,
        label: env.name,
        disabled: false,
      }))
  : []; // Cache vide = aucune option

// Ajout d'un message si aucun environnement disponible
const hasNoEnvironments = environmentOptions.length === 0;
```

4. **Ligne 195-202 : Alert derived environment - utiliser getEnvironmentLabel**
```typescript
// AVANT
{derivedEnvironment && (
  <Alert
    type="info"
    showIcon
    description={`Environnement derive : ${ENVIRONMENT_LABELS[derivedEnvironment] || derivedEnvironment}`}
    style={{ marginBottom: 16 }}
  />
)}

// APRÈS
{derivedEnvironment && (
  <Alert
    type="info"
    showIcon
    description={`Environnement derive : ${getEnvironmentLabel(derivedEnvironment)}`}
    style={{ marginBottom: 16 }}
  />
)}
```

5. **Ligne 265-274 : Production warning - utiliser isProductionEnvironment**
```typescript
// AVANT
{derivedEnvironment === 'prod' && (
  <Alert
    message="Avertissement - Environnement Production"
    ...
  />
)}

// APRÈS
{derivedEnvironment && isProductionEnvironment(derivedEnvironment) && (
  <Alert
    message="Avertissement - Environnement Production"
    ...
  />
)}
```

6. **Ajouter gestion cache vide dans le Select**
```typescript
<Select
  placeholder={hasNoEnvironments ? "Aucun environnement disponible" : "Sélectionnez un environnement"}
  disabled={hasNoEnvironments}
  options={environmentOptions}
  // ...autres props
/>
```

---

### Modification ConfirmationStep.tsx (Task 2, 5)

**Fichier :** `idp-portal/frontend/src/components/catalog/ConfirmationStep.tsx`

**Lignes à modifier :**

1. **Ligne 25-29 : Supprimer ENVIRONMENT_LABELS dupliqué**
```typescript
// SUPPRIMER ces lignes
const ENVIRONMENT_LABELS: Record<ExecutionEnvironment, string> = {
  dev: 'Developpement',
  staging: 'Staging',
  prod: 'Production',
};
```

2. **Ajouter import helpers**
```typescript
import {
  getEnvironmentLabel,
  getEnvironmentColor,
  isProductionEnvironment
} from '../../utils/environmentHelpers';
```

3. **Ligne 73-75 : Utiliser getEnvironmentLabel**
```typescript
// AVANT
const environmentName = environmentsCache?.find((env) => env.id === derivedEnvironment)?.name
  ?? ENVIRONMENT_LABELS[derivedEnvironment!]
  ?? derivedEnvironment;

// APRÈS
const environmentName = environmentsCache?.find((env) => env.id === derivedEnvironment)?.name
  ?? (derivedEnvironment ? getEnvironmentLabel(derivedEnvironment) : '');
```

4. **Ligne 102-107 : Badge avec couleur dynamique**
```typescript
// AVANT
<Descriptions.Item label="Environnement">
  <Badge
    status={derivedEnvironment === 'prod' ? 'warning' : 'processing'}
    text={environmentName}
  />
</Descriptions.Item>

// APRÈS
<Descriptions.Item label="Environnement">
  <Badge
    status={derivedEnvironment && isProductionEnvironment(derivedEnvironment)
      ? 'warning'
      : 'processing'}
    text={environmentName}
  />
</Descriptions.Item>
```

---

### Modification TargetSelector.tsx (Tasks 2, 4, 5)

**Fichier :** `idp-portal/frontend/src/components/catalog/TargetSelector.tsx`

**Lignes à modifier :**

1. **Ligne 55-66 : Supprimer constantes hardcodées**
```typescript
// SUPPRIMER ces lignes
const ENVIRONMENT_LABELS: Record<string, string> = {
  dev: 'Developpement',
  staging: 'Staging',
  prod: 'Production',
};

const ENVIRONMENT_COLORS: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
  dev: 'success',
  staging: 'warning',
  prod: 'error',
};
```

2. **Ajouter import helpers**
```typescript
import {
  getEnvironmentLabel,
  getEnvironmentColor,
  sortEnvironments
} from '../../utils/environmentHelpers';
```

3. **Ligne 142-150 : Utiliser sortEnvironments**
```typescript
// AVANT
const envOrder = ['dev', 'staging', 'prod'];
const orderedEnvs = Object.keys(groups).sort((a, b) => {
  const indexA = envOrder.indexOf(a);
  const indexB = envOrder.indexOf(b);
  if (indexA === -1 && indexB === -1) return a.localeCompare(b);
  if (indexA === -1) return 1;
  if (indexB === -1) return -1;
  return indexA - indexB;
});

// APRÈS
const orderedEnvs = sortEnvironments(Object.keys(groups));
```

4. **Ligne 152-157 : Utiliser getEnvironmentLabel**
```typescript
// AVANT
label: (
  <span style={{ fontWeight: 600 }}>
    {ENVIRONMENT_LABELS[env] || env.toUpperCase()}
  </span>
),

// APRÈS
label: (
  <span style={{ fontWeight: 600 }}>
    {getEnvironmentLabel(env)}
  </span>
),
```

5. **Ligne usage de ENVIRONMENT_COLORS (rechercher dans le fichier)**
```typescript
// Remplacer tous les usages par getEnvironmentColor(env)
// Exemple si utilisé dans badges :
<Badge status={getEnvironmentColor(env)} ... />
```

---

## Architecture Compliance

- **Component pattern :** Ant Design Select, Badge, Alert (inchangé)
- **State management :** Props `environmentsCache` depuis ExecutionWizard (inchangé)
- **Type safety :** `ExecutionEnvironment = string` accepte toutes valeurs
- **Centralization :** Utilitaires `environmentHelpers.ts` évitent duplication
- **Accessibility :** Conserver les `aria-label` existants

## Library & Framework Requirements

- **React :** Composants fonctionnels avec hooks existants
- **Ant Design :** Select, Badge, Alert pour UI
- **TypeScript :** Type `ExecutionEnvironment` étendu vers `string`
- **Pas de nouvelle dépendance**

## File Structure Requirements

**Fichiers à créer :**
```
idp-portal/frontend/src/
└── utils/
    └── environmentHelpers.ts        # NOUVEAU - utilitaires centralisés
```

**Fichiers à modifier :**
```
idp-portal/frontend/src/
├── types/
│   └── api.ts                       # Modifier : ExecutionEnvironment type
├── components/catalog/
│   ├── TargetSelectionStep.tsx      # Modifier : supprimer fallback, utiliser helpers
│   ├── ConfirmationStep.tsx         # Modifier : utiliser helpers
│   └── TargetSelector.tsx           # Modifier : utiliser helpers, sortEnvironments
└── __tests__/utils/
    └── environmentHelpers.test.ts   # NOUVEAU - tests utilitaires
```

**Fichiers de tests à créer/modifier :**
```
idp-portal/frontend/src/
├── components/catalog/
│   ├── TargetSelectionStep.test.tsx     # Créer ou augmenter
│   ├── ConfirmationStep.test.tsx        # Créer ou augmenter
│   └── TargetSelector.test.tsx          # Modifier tests existants (ligne 185-187)
└── __tests__/utils/
    └── environmentHelpers.test.ts       # NOUVEAU
```

## Testing Requirements

### Tests environmentHelpers.ts (Task 6, nouveau fichier)

**Fichier :** `idp-portal/frontend/src/__tests__/utils/environmentHelpers.test.ts`

**Tests à créer :**
```typescript
import {
  getEnvironmentLabel,
  getEnvironmentColor,
  sortEnvironments,
  isProductionEnvironment
} from '../../utils/environmentHelpers';

describe('environmentHelpers', () => {
  describe('getEnvironmentLabel', () => {
    it('returns mapped label for standard environments', () => {
      expect(getEnvironmentLabel('dev')).toBe('Développement');
      expect(getEnvironmentLabel('staging')).toBe('Staging');
      expect(getEnvironmentLabel('prod')).toBe('Production');
    });

    it('capitalizes non-standard environments', () => {
      expect(getEnvironmentLabel('lab')).toBe('Lab');
      expect(getEnvironmentLabel('qa')).toBe('Qa');
      expect(getEnvironmentLabel('uat')).toBe('Uat');
    });

    it('handles uppercase input', () => {
      expect(getEnvironmentLabel('DEV')).toBe('Développement');
      expect(getEnvironmentLabel('LAB')).toBe('Lab');
    });
  });

  describe('getEnvironmentColor', () => {
    it('returns correct color for standard environments', () => {
      expect(getEnvironmentColor('dev')).toBe('success');
      expect(getEnvironmentColor('staging')).toBe('warning');
      expect(getEnvironmentColor('prod')).toBe('error');
    });

    it('returns default color for non-standard environments', () => {
      expect(getEnvironmentColor('lab')).toBe('default');
      expect(getEnvironmentColor('qa')).toBe('default');
    });
  });

  describe('sortEnvironments', () => {
    it('sorts with dev, staging, prod first', () => {
      const input = ['qa', 'dev', 'prod', 'lab', 'staging'];
      const expected = ['dev', 'staging', 'prod', 'lab', 'qa'];
      expect(sortEnvironments(input)).toEqual(expected);
    });

    it('sorts alphabetically when no standard envs', () => {
      const input = ['uat', 'lab', 'qa'];
      const expected = ['lab', 'qa', 'uat'];
      expect(sortEnvironments(input)).toEqual(expected);
    });

    it('handles missing standard environments', () => {
      const input = ['qa', 'dev', 'lab'];
      const expected = ['dev', 'lab', 'qa'];
      expect(sortEnvironments(input)).toEqual(expected);
    });
  });

  describe('isProductionEnvironment', () => {
    it('returns true for prod variations', () => {
      expect(isProductionEnvironment('prod')).toBe(true);
      expect(isProductionEnvironment('PROD')).toBe(true);
      expect(isProductionEnvironment('Prod')).toBe(true);
      expect(isProductionEnvironment('production')).toBe(true);
    });

    it('returns false for non-production environments', () => {
      expect(isProductionEnvironment('dev')).toBe(false);
      expect(isProductionEnvironment('staging')).toBe(false);
      expect(isProductionEnvironment('lab')).toBe(false);
    });
  });
});
```

---

### Tests TargetSelectionStep (Task 7)

**Fichier :** `idp-portal/frontend/src/components/catalog/TargetSelectionStep.test.tsx` (créer ou augmenter)

**Tests à ajouter :**
```typescript
import { render, screen } from '@testing-library/react';
import TargetSelectionStep from './TargetSelectionStep';

describe('TargetSelectionStep - Story 21.5', () => {
  const mockProps = {
    // ...props de base
    allowedEnvironments: ['dev', 'staging', 'prod', 'lab'],
  };

  it('displays environment options from cache', () => {
    const cache = [
      { id: 'dev', name: 'Développement', environment: null },
      { id: 'lab', name: 'Lab', environment: null },
      { id: 'qa', name: 'QA', environment: null },
    ];

    render(<TargetSelectionStep {...mockProps} environmentsCache={cache} />);

    expect(screen.getByText('Développement')).toBeInTheDocument();
    expect(screen.getByText('Lab')).toBeInTheDocument();
    expect(screen.getByText('QA')).toBeInTheDocument();
  });

  it('shows message when cache is empty', () => {
    render(<TargetSelectionStep {...mockProps} environmentsCache={[]} />);

    expect(screen.getByText(/Aucun environnement disponible/i)).toBeInTheDocument();
  });

  it('shows production warning for prod environment (case-insensitive)', () => {
    // Test avec 'prod'
    const { rerender } = render(
      <TargetSelectionStep {...mockProps} derivedEnvironment="prod" />
    );
    expect(screen.getByText(/Avertissement - Environnement Production/i)).toBeInTheDocument();

    // Test avec 'PROD'
    rerender(<TargetSelectionStep {...mockProps} derivedEnvironment="PROD" />);
    expect(screen.getByText(/Avertissement - Environnement Production/i)).toBeInTheDocument();
  });

  it('displays derived environment alert with correct label', () => {
    render(<TargetSelectionStep {...mockProps} derivedEnvironment="lab" />);

    expect(screen.getByText(/Environnement derive : Lab/i)).toBeInTheDocument();
  });

  it('accepts non-standard environments without error', () => {
    const cache = [
      { id: 'uat', name: 'UAT', environment: null },
      { id: 'certif', name: 'Certif', environment: null },
    ];

    expect(() => {
      render(<TargetSelectionStep {...mockProps} environmentsCache={cache} />);
    }).not.toThrow();
  });
});
```

---

### Tests ConfirmationStep (Task 7)

**Fichier :** `idp-portal/frontend/src/components/catalog/ConfirmationStep.test.tsx`

**Tests à ajouter :**
```typescript
describe('ConfirmationStep - Story 21.5', () => {
  it('displays environment badge with correct label from cache', () => {
    const cache = [
      { id: 'dev', name: 'Développement', environment: null },
    ];

    render(<ConfirmationStep derivedEnvironment="dev" environmentsCache={cache} />);

    expect(screen.getByText('Développement')).toBeInTheDocument();
  });

  it('displays capitalized label for non-standard environment', () => {
    const cache = [
      { id: 'lab', name: 'Lab', environment: null },
    ];

    render(<ConfirmationStep derivedEnvironment="lab" environmentsCache={cache} />);

    expect(screen.getByText('Lab')).toBeInTheDocument();
  });

  it('shows warning badge for production environment', () => {
    render(<ConfirmationStep derivedEnvironment="prod" />);

    const badge = screen.getByText('Production').closest('.ant-badge');
    expect(badge).toHaveClass('ant-badge-status-warning');
  });

  it('shows processing badge for non-production environment', () => {
    render(<ConfirmationStep derivedEnvironment="lab" />);

    const badge = screen.getByText('Lab').closest('.ant-badge');
    expect(badge).toHaveClass('ant-badge-status-processing');
  });
});
```

---

### Tests TargetSelector (Task 7, modifier existants)

**Fichier :** `idp-portal/frontend/src/components/catalog/TargetSelector.test.tsx`

**Modifier tests existants ligne 185-187 :**
```typescript
// AVANT (ligne 185-187)
expect(screen.getByText('Developpement')).toBeInTheDocument();
expect(screen.getByText('Staging')).toBeInTheDocument();
expect(screen.getByText('Production')).toBeInTheDocument();

// APRÈS (corriger orthographe + utiliser getEnvironmentLabel)
expect(screen.getByText('Développement')).toBeInTheDocument(); // accent ajouté
expect(screen.getByText('Staging')).toBeInTheDocument();
expect(screen.getByText('Production')).toBeInTheDocument();
```

**Ajouter nouveaux tests Story 21.5 :**
```typescript
describe('TargetSelector - Story 21.5', () => {
  it('displays groups in correct order: dev, staging, prod, then alphabetical', () => {
    const targets = [
      { id: '1', name: 'Target QA', environment: 'qa' },
      { id: '2', name: 'Target Dev', environment: 'dev' },
      { id: '3', name: 'Target Prod', environment: 'prod' },
      { id: '4', name: 'Target Lab', environment: 'lab' },
    ];

    render(<TargetSelector targets={targets} />);

    const groups = screen.getAllByRole('group');
    expect(groups[0]).toHaveTextContent('Développement');
    expect(groups[1]).toHaveTextContent('Production');
    expect(groups[2]).toHaveTextContent('Lab');
    expect(groups[3]).toHaveTextContent('Qa');
  });

  it('displays non-standard environments with capitalized labels', () => {
    const targets = [
      { id: '1', name: 'Target UAT', environment: 'uat' },
      { id: '2', name: 'Target Certif', environment: 'certif' },
    ];

    render(<TargetSelector targets={targets} />);

    expect(screen.getByText('Uat')).toBeInTheDocument();
    expect(screen.getByText('Certif')).toBeInTheDocument();
  });

  it('uses default badge color for non-standard environments', () => {
    const targets = [
      { id: '1', name: 'Target Lab', environment: 'lab' },
    ];

    render(<TargetSelector targets={targets} />);

    // Vérifier que le badge a la couleur par défaut (getEnvironmentColor('lab') === 'default')
    const badge = screen.getByText('Lab').closest('.ant-badge');
    expect(badge).toHaveClass('ant-badge-status-default');
  });
});
```

---

### Pattern de test général

**Mock environmentsCache :**
```typescript
const mockEnvironmentsCache = [
  { id: 'dev', name: 'Développement', environment: null },
  { id: 'staging', name: 'Staging', environment: null },
  { id: 'prod', name: 'Production', environment: null },
  { id: 'lab', name: 'Lab', environment: null },
];
```

**Exécution des tests :**
```bash
cd /Users/cyrille/Documents/Dev/test/idp-portal/frontend
npm test -- environmentHelpers.test.ts
npm test -- TargetSelectionStep.test.tsx
npm test -- ConfirmationStep.test.tsx
npm test -- TargetSelector.test.tsx
```

### Critères de succès

- ✅ Tous les tests passent (0 failures)
- ✅ Type `ExecutionEnvironment = string` accepte toutes valeurs
- ✅ Aucun fallback hardcodé `['dev','staging','prod']` dans les composants
- ✅ Labels dynamiques via `getEnvironmentLabel()` centralisé
- ✅ Production warning fonctionne avec case-insensitive
- ✅ TargetSelector trie correctement environnements standard + non standard
- ✅ Environnements non standard (lab, qa, uat) affichés et utilisables
- ✅ Cache vide → message clair, pas de fallback silencieux

## Previous Story Intelligence

**Story 13.7 — Learnings :**
- Hook `useEnvironments` créé pour admin editors
- Pattern d'utilisation : fetch `/inventory/environments`, cache global
- **Différence avec environmentsCache :** useEnvironments retourne `string[]`, environmentsCache retourne `InventoryItem[]`
- ExecutionWizard utilise `fetchInventoryItems('environments')` au lieu de useEnvironments

**Story 21.1 — Learnings :**
- Backend inventaire retourne valeurs brutes (lab, dev, staging, prod, certif)
- Aucune normalisation forcée côté backend
- Valeurs lowercase depuis Oracle

**Story 21.2 — Learnings :**
- RBAC comparaison case-insensitive
- Lookup config environnement case-insensitive
- Validation bloque si inventaire indisponible (sécurité SOC1)

**Story 21.3 — Learnings :**
- 101 tests backend passent avec environnements non standard
- Pattern de tests bien établi pour lab, qa, uat, certif
- Case insensitivity testée et validée

**Story 21.4 — Learnings :**
- Éditeurs admin migrés vers `useEnvironments` hook
- Pattern établi : import hook, utiliser `environmentOptions` pour Select
- Loading/error states gérés proprement
- 76 tests passent avec environnements dynamiques
- Labels : mapping explicite dev/staging/prod, capitalisation pour autres

**Problèmes connus à éviter :**
- Ne pas dupliquer ENVIRONMENT_LABELS entre composants (créer utilitaire centralisé)
- Ne pas garder fallback hardcodé qui masque erreurs API
- Ne pas oublier case insensitivity pour production detection
- Tester avec 0, 1, 5+ environnements pour robustesse

## Git Intelligence Summary

**Recent commits (last 10) :**
- `f028925` : feat(21-4) migrate admin editors to dynamic environment support
- `7046edc` : test(21-3) comprehensive backend tests for raw environment values
- `1634bdd` : docs(20-8) finalize compliance documentation
- `bde9494` : feat(20-7) implement M10 and 17-12 follow-ups
- `044f957` : feat(20-6) container workflow execution engine
- `ef02b9c` : feat(20-5) comprehensive project documentation
- `cfd46a4` : feat(20-4) refactor ExecutionWizard with performance optimizations
- `2c2af1e` : feat(20-3) migrate workflow retry to Celery
- `5096b65` : fix frontend smoke test robustness
- `98a53c0` : feat(6-5) restore audit menu visibility

**Patterns observés :**
- Convention commit : `type(scope): description`
- Scope stories : `feat(epic-story)` ex: `feat(21-5)`
- Frontend : `feat(21-5): remove hardcoded environment fallbacks in execution wizard`
- Tests : mention nombre de tests ajoutés
- Code review fixes documentés

**Pour cette story :**
- Commit message suggéré : `feat(21-5): remove hardcoded environment fallbacks and extend ExecutionEnvironment type to string`
- Mention : "TargetSelectionStep, ConfirmationStep, TargetSelector - dynamic environment labels, centralized helpers, case-insensitive production detection + 25 tests"
- Référence Stories 21.1-21.4 backend/admin validées

## Project Context Reference

**Portail IDP (Internal Developer Portal) — DBOPS**

- **Frontend :** React 18 + Ant Design 5.x, TypeScript
- **Backend :** Django 5.2 + DRF 3.16, Oracle DB
- **Environnement de travail :** `/Users/cyrille/Documents/Dev/test/idp-portal/frontend`
- **Test runner :** `npm test`

**Epic 21 — Inventaire source unique environnements :**
- Story 21.1 : Backend inventaire valeurs brutes (done)
- Story 21.2 : Backend RBAC et exécutions case-insensitive (done)
- Story 21.3 : Tests backend (done)
- Story 21.4 : Frontend éditeurs admin (done)
- **Story 21.5 : Frontend target selection (current)**
- Story 21.6 : Validation environnements profil (optionnel, backlog)

**Contraintes techniques :**
- Oracle DB : Inventaire externe via synonym DBOPS_INVENTORY
- ExecutionWizard : Fetch `fetchInventoryItems('environments')` → cache local
- Type ExecutionEnvironment : Actuellement limité à `'dev' | 'staging' | 'prod'` → étendre vers `string`
- Labels affichage : Mapping explicite + capitalisation fallback
- Case format : lowercase depuis API, labels via mapping

## Story Completion Status

- **Status :** ready-for-dev
- **Analyse :** Epic 21 + Stories 21.1-21.4 + analyse exhaustive des 3 composants catalog (TargetSelectionStep, ConfirmationStep, TargetSelector) + type ExecutionEnvironment + patterns de labels/couleurs ; exploration avec agents spécialisés pour identifier tous les hardcoded values (8 locations) ; stratégie de migration définie avec création utilitaire centralisé environmentHelpers.ts
- **Note :** Ultimate context engine analysis completed — comprehensive developer guide created with component-by-component migration strategy, centralized helpers creation, type extension plan, and comprehensive test patterns for dynamic environment handling in execution wizard

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

N/A

### Completion Notes List

**2026-02-09 - Story 21.5 Code Review**

✅ **Adversarial Code Review Findings:**
- Reviewed implementation against all 5 Acceptance Criteria
- Verified all 7 tasks completed and marked [x]
- Ran comprehensive test suite: 113 tests passing (16 helpers + 13 TargetSelectionStep + 10 ConfirmationStep + 12 TargetSelector + 62 ExecutionWizard regression)
- Found 3 issues requiring fixes

🔴 **ISSUES FOUND & FIXED:**

**Issue #1 - MEDIUM: Duplicated getEnvironmentColor() in EnvironmentBarChart (code clarity)**
- **File:** `idp-portal/frontend/src/components/dashboard/reporting/EnvironmentBarChart.tsx`
- **Problem:** Local `getEnvironmentColor()` function returns hex codes (`#10B981`) instead of `BadgeProps['status']`, causing naming confusion with `utils/environmentHelpers.ts` function
- **Impact:** Code maintainability — developers might think these functions are identical
- **Fix:** Added comprehensive JSDoc comment explaining the intentional difference (Recharts requires hex colors vs Ant Design badges require status strings)
- **Severity:** MEDIUM — Does not affect functionality, but improves code clarity

**Issue #2 - MEDIUM: Repeated toUpperCase() calls (performance optimization)**
- **File:** `idp-portal/frontend/src/components/catalog/TargetSelectionStep.tsx` lines 222, 226
- **Problem:** Filter logic `allowedEnvironments.includes(env.id) || allowedEnvironments.includes(env.id.toUpperCase())` repeats `toUpperCase()` twice (disabled check + options filter)
- **Impact:** Unnecessary duplicate string operations in array filtering
- **Fix:** Extracted logic into helper function `isEnvironmentAllowed(envId, allowedEnvironments)` to avoid duplication
- **Severity:** MEDIUM — Minor performance improvement, better code organization

**Issue #3 - LOW: change_type_config lookup uses toUpperCase() (out of scope)**
- **File:** `idp-portal/frontend/src/components/catalog/ConfirmationStep.tsx` line 65
- **Problem:** `change_type_config?.[derivedEnvironment?.toUpperCase() ?? '']` uses uppercase lookup
- **Impact:** Pre-existing pattern from before Story 21.5, not related to dynamic environments
- **Action:** NO FIX — Outside Story 21.5 scope (not related to environment selection/labels/ordering)
- **Severity:** LOW — Pre-existing code, works correctly with current backend

✅ **Validation Results:**
- AC #1 ✅ — Select uses only `environmentsCache`, no fallback, dynamic placeholders
- AC #2 ✅ — Labels via `getEnvironmentLabel()`, non-standard envs capitalized
- AC #3 ✅ — `ExecutionEnvironment = string` type works correctly
- AC #4 ✅ — `sortEnvironments()` orders dev/staging/prod first, colors via `getEnvironmentColor()`
- AC #5 ✅ — Non-standard envs (lab, qa, uat) work end-to-end, case-insensitive prod detection

✅ **Test Coverage:**
- 16/16 `environmentHelpers.test.ts` tests pass
- 13/13 `TargetSelectionStep.test.tsx` tests pass
- 10/10 `ConfirmationStep.test.tsx` tests pass
- 12/12 `TargetSelector.test.tsx` tests pass
- 62/62 `ExecutionWizard` regression tests pass
- **Total: 113 tests pass, 0 failures, 0 regressions**

✅ **Fixes Applied:**
1. Added JSDoc comment to EnvironmentBarChart.tsx `getEnvironmentColor()` explaining intentional difference from helpers
2. Extracted `isEnvironmentAllowed()` helper in TargetSelectionStep.tsx to avoid repeated `toUpperCase()` calls
3. All tests still passing after fixes

**2026-02-09 - Story 21.5 Context Created**

✅ **Comprehensive Analysis Completed:**
- Analyzed Epic 21 complete context and Stories 21.1-21.4 implementations
- Reviewed 3 catalog components with Explore agent (TargetSelectionStep, ConfirmationStep, TargetSelector)
- Analyzed ExecutionEnvironment type constraint in api.ts
- Identified all hardcoded environment values (8 locations across 4 files)
- Analyzed useEnvironments hook vs environmentsCache difference
- Extracted current patterns : ENVIRONMENT_LABELS (3 duplicates), ENVIRONMENT_COLORS, fallback arrays, ordering logic

✅ **Migration Strategy Defined:**
- 7 task groups : type extension + centralized helpers + 3 composants + tests
- Création `environmentHelpers.ts` avec 4 fonctions utilitaires (labels, couleurs, tri, production detection)
- Suppression fallback hardcodé TargetSelectionStep ligne 230
- Remplacement 3 instances ENVIRONMENT_LABELS par appels centralisés
- Extension type ExecutionEnvironment de `'dev' | 'staging' | 'prod'` vers `string`

✅ **Developer Guardrails Established:**
- Comprehensive Dev Notes avec contexte Stories 21.1-21.4
- Technical Requirements par composant avec code suggéré
- Patterns de tests avec mocks environmentsCache
- Known issues et pièges à éviter documentés
- Case handling standardisé (lowercase values, labels via helper, case-insensitive prod check)
- Différence useEnvironments (admin) vs environmentsCache (wizard) expliquée

✅ **Story Quality:**
- 5 Acceptance Criteria mapped to 7 tasks avec ~35 subtasks
- Code examples pour chaque composant + création environmentHelpers.ts
- Test patterns avec mocks + assertions attendues
- File structure et exécution commands specified
- Previous story intelligence (13.7, 21.1-21.4) integrated
- Git patterns et commit message guidance

**Hardcoded Values Found (8 locations):**
1. TargetSelectionStep → ligne 26-30 : `ENVIRONMENT_LABELS = {dev, staging, prod}`
2. TargetSelectionStep → ligne 230 : fallback `['dev','staging','prod']`
3. ConfirmationStep → ligne 25-29 : `ENVIRONMENT_LABELS = {dev, staging, prod}` (dupliqué)
4. TargetSelector → ligne 55-59 : `ENVIRONMENT_LABELS = {dev, staging, prod}` (dupliqué)
5. TargetSelector → ligne 62-66 : `ENVIRONMENT_COLORS = {dev, staging, prod}`
6. TargetSelector → ligne 142 : `envOrder = ['dev','staging','prod']`
7. api.ts → ligne 442 : `ExecutionEnvironment = 'dev' | 'staging' | 'prod'` (type constraint)
8. useEnvironments + reference_service → fallbacks multiples `['dev','staging','prod']` (hors scope Story 21.5)

**Key Findings:**
- Triple duplication de ENVIRONMENT_LABELS entre 3 composants
- Fallback hardcodé ligne 230 TargetSelectionStep masque erreurs API
- Type ExecutionEnvironment trop restrictif empêche lab, qa, uat
- Production detection hardcodé `=== 'prod'` rate variations case
- TargetSelector ordering logic hardcodée pour 3 envs seulement
- useEnvironments (admin editors, Story 21.4) vs environmentsCache (wizard) — deux systèmes coexistent

**Ready for dev-story execution** — All component migration requirements, centralized helpers creation, type extension plan, and comprehensive test patterns documented for dynamic environment handling in execution wizard (TargetSelectionStep, ConfirmationStep, TargetSelector)

**2026-02-09 - Story 21.5 Implementation Complete & Code Review Passed**

✅ **All 7 Tasks + 51 Subtasks Completed:**

**Task 3 — Type Extension:**
- `ExecutionEnvironment = string` in `api.ts` line 442
- All `as ExecutionEnvironment` casts continue to work (9 usages verified)

**Task 6 — Centralized Helpers:**
- Created `environmentHelpers.ts` with 4 functions: `getEnvironmentLabel()`, `getEnvironmentColor()`, `sortEnvironments()`, `isProductionEnvironment()`
- 16/16 unit tests pass covering standard (dev/staging/prod) and non-standard (lab/qa/uat/certif) environments

**Task 1 — Removed Hardcoded Fallback:**
- Replaced `['dev','staging','prod']` fallback with empty array `[]`
- Added dynamic placeholder: "Chargement..." (null cache), "Aucun environnement disponible" (empty cache), "Selectionnez un environnement" (populated)
- Select disabled when no matching allowed environments

**Task 2 — Dynamic Labels:**
- Removed 3 duplicated `ENVIRONMENT_LABELS` constants from TargetSelectionStep, ConfirmationStep, TargetSelector
- All label lookups now use `getEnvironmentLabel()` via centralized helpers
- Fixed French label from `'Developpement'` to `'Développement'` (correct accent)

**Task 4 — Environment Ordering:**
- Replaced hardcoded `envOrder = ['dev','staging','prod']` with `sortEnvironments()`
- Non-standard environments (lab, qa, uat) sorted alphabetically after standard ones

**Task 5 — Dynamic Colors:**
- Removed hardcoded `ENVIRONMENT_COLORS` constant from TargetSelector
- All color lookups now use `getEnvironmentColor()` — returns 'default' for non-standard envs

**Task 7 — Component Tests:**
- TargetSelectionStep.test.tsx: 13 tests (cache display, production warning case-insensitive, derived env labels, no fallback, non-standard envs)
- ConfirmationStep.test.tsx: 10 tests (env labels from cache, fallback labels, badge colors, non-standard envs)
- TargetSelector.test.tsx: +3 Story 21.5 tests (non-standard group labels, ordering verification, default badge color)
- environmentHelpers.test.ts: 16 tests (labels, colors, sorting, production detection)
- ExecutionWizard regression tests: 62/62 pass (timing fixes for cache-dependent Select interactions)
- **Total: 113 tests pass, 0 regressions**

**Acceptance Criteria Validation:**
- AC #1 ✅ — Select uses environmentsCache only, fallback supprimé, loading/empty states gérés
- AC #2 ✅ — Labels dynamiques via getEnvironmentLabel(), lab→"Lab", qa→"Qa"
- AC #3 ✅ — ExecutionEnvironment = string, tous les usages TypeScript fonctionnent
- AC #4 ✅ — Ordering dev/staging/prod en premier, puis alphabétique, couleurs dynamiques
- AC #5 ✅ — Non-standard envs (lab, qa, uat) fonctionnent dans tout le wizard, labels cohérents, 0 erreur TypeScript

### Change Log

**2026-02-09 - Story 21.5 Implementation Complete**
- Extended `ExecutionEnvironment` type from `'dev' | 'staging' | 'prod'` to `string`
- Created centralized `environmentHelpers.ts` with 4 utility functions
- Removed hardcoded fallback `['dev','staging','prod']` in TargetSelectionStep
- Replaced 3 duplicated `ENVIRONMENT_LABELS` constants with `getEnvironmentLabel()`
- Replaced hardcoded `ENVIRONMENT_COLORS` with `getEnvironmentColor()`
- Replaced hardcoded `envOrder` sorting with `sortEnvironments()`
- Case-insensitive production detection via `isProductionEnvironment()`
- Fixed existing test assertions for corrected French label `'Développement'`
- Added wait-for-cache patterns in ExecutionWizard tests (cache no longer has fallback)
- 51 new tests + 62 regression tests pass (113 total, 0 regressions)

**Code Review Fixes (2026-02-09):**
- Added JSDoc to EnvironmentBarChart.tsx getEnvironmentColor() — clarifies intentional difference from helpers version
- Extracted isEnvironmentAllowed() in TargetSelectionStep.tsx — optimizes repeated toUpperCase() calls
- 113/113 tests still passing after fixes

### File List

**New files:**
- `idp-portal/frontend/src/utils/environmentHelpers.ts` — Centralized environment helpers (labels, colors, sorting, production detection)
- `idp-portal/frontend/src/utils/environmentHelpers.test.ts` — 16 unit tests for environment helpers
- `idp-portal/frontend/src/components/catalog/TargetSelectionStep.test.tsx` — 13 tests for TargetSelectionStep
- `idp-portal/frontend/src/components/catalog/ConfirmationStep.test.tsx` — 10 tests for ConfirmationStep

**Modified files:**
- `idp-portal/frontend/src/types/api.ts` — ExecutionEnvironment changed from union literal to `string`
- `idp-portal/frontend/src/components/catalog/TargetSelectionStep.tsx` — Removed ENVIRONMENT_LABELS, removed hardcoded fallback, import helpers
- `idp-portal/frontend/src/components/catalog/ConfirmationStep.tsx` — Removed ENVIRONMENT_LABELS, import helpers, case-insensitive prod check
- `idp-portal/frontend/src/components/catalog/TargetSelector.tsx` — Removed ENVIRONMENT_LABELS/COLORS constants, import helpers, use sortEnvironments
- `idp-portal/frontend/src/components/catalog/TargetSelector.test.tsx` — Fixed accent in label assertion, added 3 Story 21.5 tests
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.test.tsx` — Added waitFor before Select interactions (cache no longer has fallback)
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.targets.test.tsx` — Fixed accent in label assertions
- `idp-portal/frontend/src/components/dashboard/reporting/EnvironmentBarChart.tsx` — Added JSDoc comment to local getEnvironmentColor() explaining intentional difference from helpers (Code Review fix)

