# Story 17.15: Relancer une exécution (paramètres pré-remplis, modifiables)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que **DBA ou admin**,
je veux **relancer une exécution passée en partant des mêmes paramètres (que j'ai initiée, ou n'importe laquelle si je suis admin)**,
afin de **gagner du temps tout en pouvant ajuster les paramètres avant de réexécuter**.

**Privilèges :** L'utilisateur qui a déclenché l'exécution peut la relancer ; les **admins (DBOPS/DBA)** peuvent relancer **n'importe quelle** exécution.

## Acceptance Criteria

### AC1: Affichage du bouton Relancer pour les exécutions de l'utilisateur

**Given** un DBA consulte la vue Exécutions
**When** il sélectionne une exécution passée qu'il a initiée (terminée, échouée ou annulée)
**Then** un bouton ou action "Relancer" est disponible
**And** le bouton est visible pour tous les statuts (terminés, échoués, annulés, réussis)

### AC2: Affichage du bouton Relancer pour les admins sur toutes les exécutions

**Given** un utilisateur avec rôle admin (DBOPS ou DBA) consulte la vue Exécutions
**When** il voit une exécution passée (initiée par n'importe qui)
**Then** un bouton ou action "Relancer" est disponible pour toutes les exécutions
**And** l'admin peut relancer n'importe quelle exécution, pas seulement les siennes

### AC3: Ouverture du wizard avec paramètres pré-remplis

**Given** le DBA ou l'admin clique sur "Relancer" pour une exécution
**When** l'action est déclenchée
**Then** le wizard d'exécution s'ouvre avec les paramètres pré-remplis issus de l'exécution passée:
- Action sélectionnée (action_id)
- Target(s) sélectionné(s) (target_names array)
- Environnement (déduit des targets)
- Paramètres dynamiques (parameters JSON)
**And** tous ces paramètres sont affichés dans le wizard et peuvent être modifiés par l'utilisateur

### AC4: Modification des paramètres avant soumission

**Given** le wizard est ouvert avec les paramètres pré-remplis
**When** l'utilisateur modifie un ou plusieurs paramètres (action, targets, environnement, paramètres)
**Then** les modifications sont prises en compte
**And** à la soumission du wizard, une nouvelle exécution est créée avec les paramètres affichés (pré-remplis ou modifiés)
**And** l'exécution originale n'est pas modifiée (nouvelle exécution créée)

### AC5: Validation RBAC pour la relance

**Given** le DBA n'a plus les permissions pour l'action ou l'environnement (et n'est pas admin)
**When** il tente de relancer via le wizard
**Then** la validation RBAC s'applique normalement au moment de la soumission
**And** une erreur explicite est affichée si les permissions sont insuffisantes
**And** les privilèges de relance sont: initiateur de l'exécution OU admin (RBAC)

### AC6: Gestion des erreurs et feedback utilisateur

**Given** une tentative de relance échoue (ex: action supprimée, permissions insuffisantes)
**When** l'erreur est reçue du backend ou du wizard
**Then** un message d'erreur explicite s'affiche à l'utilisateur via `notification.error()`
**And** l'erreur est loggée dans les logs frontend via `logger.error()`

## Tasks / Subtasks

### Task 1: Frontend - Bouton Relancer dans ExecutionsPage (AC1, AC2, AC6)

- [x] **1.1** Ajouter bouton "Relancer" dans la colonne "Actions" existante (`ExecutionsPage.tsx`)
  - Position: À côté du bouton Annuler (colonne Actions déjà créée dans Story 17.14)
  - Afficher pour toutes les exécutions (pas de filtre de statut)
  - RBAC: Afficher si `execution.user.id === currentUser.id` OU `canViewAll` (DBA/DBOPS)
  - Icône: `<RedoOutlined />` (Ant Design)
  - Tooltip: "Relancer l'exécution avec les mêmes paramètres"
  - Type: `Button` avec `type="default"` (action neutre)
  - Size: `small` pour s'aligner avec le design compact (Story 17.13)
- [x] **1.2** Implémenter la logique de relance avec ouverture du wizard
  - Créer fonction `handleRestartExecution(execution: ExecutionResponse)`
  - Préparer les paramètres pré-remplis (voir Task 2)
  - Ouvrir `ExecutionWizard` via modal ou navigation avec paramètres pré-remplis
  - Logger l'action avec `logger.debug()`
- [x] **1.3** Gestion d'erreurs et feedback utilisateur
  - Si l'action n'existe plus: afficher notification d'erreur explicite
  - Si erreur lors de la préparation: logger avec `logger.error()` et notifier l'utilisateur
  - Utiliser les messages constants pour cohérence

### Task 2: Frontend - Préparer les paramètres pour le wizard (AC3, AC4)

- [x] **2.1** Créer fonction utilitaire `prepareWizardParamsFromExecution(execution: ExecutionResponse)`
  - Extraire `action_id` depuis `execution.action.id`
  - Extraire `target_names` depuis `execution.target_names` (array de strings)
  - Extraire `environment` depuis `execution.environment`
  - Extraire `parameters` depuis `execution.parameters` (JSON object)
  - Retourner objet typé `WizardInitialParams` avec tous les champs
- [x] **2.2** Typage TypeScript pour les paramètres initiaux
  - Créer interface `WizardInitialParams` dans `types/wizard.ts` (ou existant)
  - Champs: `actionId?: string`, `targetNames?: string[]`, `environment?: string`, `parameters?: Record<string, unknown>`
- [x] **2.3** Vérifier que l'action existe avant d'ouvrir le wizard
  - Si `execution.action` est null ou action supprimée: afficher erreur "Action non disponible"
  - Sinon: continuer avec l'ouverture du wizard

### Task 3: Frontend - Modifier ExecutionWizard pour accepter paramètres initiaux (AC3, AC4)

- [x] **3.1** Ajouter prop `initialParams?: WizardInitialParams` à `ExecutionWizard` component
  - Si `initialParams` fourni: pré-remplir les champs du wizard
  - Sinon: comportement normal (wizard vide)
- [x] **3.2** Étape 1 du wizard: Pré-sélectionner l'action
  - Si `initialParams.actionId` fourni: sélectionner l'action correspondante
  - Afficher l'action pré-sélectionnée dans le champ de sélection
  - L'utilisateur peut changer l'action si nécessaire (AC4)
- [x] **3.3** Étape 2 du wizard: Pré-remplir les targets et environnement
  - Si `initialParams.targetNames` fourni: pré-sélectionner les targets dans le composant TargetSelector
  - Si `initialParams.environment` fourni: afficher l'environnement (lecture seule ou déduit des targets)
  - L'utilisateur peut modifier les targets (AC4)
- [x] **3.4** Étape 3 du wizard: Pré-remplir les paramètres dynamiques
  - Si `initialParams.parameters` fourni: initialiser les champs dynamiques avec ces valeurs
  - Afficher les paramètres pré-remplis dans le formulaire
  - L'utilisateur peut modifier les paramètres (AC4)
- [x] **3.5** Validation et soumission
  - À la soumission: utiliser les valeurs affichées dans le wizard (modifiées ou non)
  - Créer une nouvelle exécution via `submitExecution()` (API existante)
  - Ne pas modifier l'exécution originale

### Task 4: Frontend - Tests unitaires React (AC1, AC2, AC3, AC6)

- [x] **4.1** Test: Bouton Relancer visible pour l'initiateur
  - Mock execution avec `user.id === currentUser.id`
  - Vérifier que le bouton Relancer est rendu
- [x] **4.2** Test: Bouton Relancer visible pour admin DBOPS sur toutes les exécutions
  - Mock user avec `profile: 'DBOPS'`
  - Mock execution initiée par un autre utilisateur
  - Vérifier que le bouton Relancer est rendu
- [x] **4.3** Test: Bouton Relancer non visible pour un utilisateur non-autorisé
  - Mock execution initiée par user1, current user = user2 (profile: 'DBA_CLIENT')
  - Vérifier que le bouton n'est pas rendu
- [x] **4.4** Test: Clic sur Relancer ouvre le wizard avec paramètres pré-remplis
  - Mock execution avec action, targets, environnement, paramètres
  - Simuler clic sur "Relancer"
  - Vérifier que `prepareWizardParamsFromExecution()` est appelé
  - Vérifier que le wizard est ouvert avec les paramètres corrects
- [x] **4.5** Test: Erreur si action supprimée
  - Mock execution avec `action: null`
  - Simuler clic sur "Relancer"
  - Vérifier notification d'erreur affichée avec message "Action non disponible"
  - Vérifier logger.error() appelé
- [x] **4.6** Test: Modification des paramètres dans le wizard
  - Ouvrir wizard avec paramètres pré-remplis
  - Modifier l'action, les targets, les paramètres
  - Vérifier que la soumission utilise les valeurs modifiées

### Task 5: Frontend - Tests d'intégration ExecutionWizard (AC3, AC4)

- [x] **5.1** Test: Wizard pré-remplit l'action (étape 1)
  - Passer `initialParams.actionId`
  - Vérifier que l'action est pré-sélectionnée dans le champ
  - Vérifier que l'utilisateur peut changer l'action
- [x] **5.2** Test: Wizard pré-remplit les targets et environnement (étape 2)
  - Passer `initialParams.targetNames` et `initialParams.environment`
  - Vérifier que les targets sont pré-sélectionnés
  - Vérifier que l'environnement est affiché (ou déduit)
  - Vérifier que l'utilisateur peut modifier les targets
- [x] **5.3** Test: Wizard pré-remplit les paramètres dynamiques (étape 3)
  - Passer `initialParams.parameters`
  - Vérifier que les champs dynamiques sont initialisés avec les valeurs
  - Vérifier que l'utilisateur peut modifier les paramètres
- [x] **5.4** Test: Soumission crée une nouvelle exécution
  - Remplir wizard avec paramètres pré-remplis
  - Soumettre le wizard
  - Vérifier que `submitExecution()` est appelé avec les paramètres affichés
  - Vérifier qu'une nouvelle exécution est créée (pas de modification de l'originale)

### Task 6: Documentation et validation finale

- [x] **6.1** Mettre à jour la documentation utilisateur (`docs/user-guide/executions.md`)
  - Documenter la fonctionnalité "Relancer une exécution"
  - Expliquer les privilèges (initiateur OU admin)
  - Décrire le workflow: clic sur Relancer → wizard pré-rempli → modification possible → soumission
- [x] **6.2** Validation manuelle end-to-end
  - Créer une exécution en tant que DBA avec action, targets, paramètres
  - Vérifier que le bouton Relancer s'affiche
  - Cliquer sur Relancer, vérifier que le wizard s'ouvre avec les paramètres pré-remplis
  - Modifier un paramètre, soumettre, vérifier que la nouvelle exécution est créée
  - Se connecter en tant que DBOPS, vérifier que le bouton Relancer s'affiche pour l'exécution du DBA
  - Relancer l'exécution, vérifier le succès

## Dev Notes

### Architecture et Patterns Existants

**Frontend React + Ant Design:**
- Framework: React 19.2, Ant Design 6.2, TypeScript 5.9
- Standards: `/Users/cyrille/Documents/Dev/test/idp-portal/frontend/FRONTEND-STANDARDS.md`
- Composant principal: `ExecutionsPage.tsx` (pages/, lignes 1-656)
  - Affiche la table des exécutions avec colonnes: Statut, Action, Technologie, Plateforme, Utilisateur, Environnement, Date, Durée, **Actions**
  - Story 17.13 appliquée: layout compact (`size="small"`)
  - Story 17.14 appliquée: colonne "Actions" avec bouton Annuler
  - RBAC: `canViewAll = user?.profile?.toLowerCase() === 'dba' || user?.profile?.toLowerCase() === 'dbops'`

**Composant ExecutionWizard:**
- Localisation: `components/execution/ExecutionWizard.tsx` (refactorisé dans Story 17.2)
- 3 étapes: Sélection action → Sélection targets → Paramètres dynamiques
- Props existantes: `open`, `onClose`, `onSuccess`
- **Note:** Actuellement ne supporte pas de paramètres initiaux (à ajouter dans cette story)

**Services API frontend:**
- `execution_service.ts` contient: `submitExecution()`, `getExecution()`, `listExecutions()`, `approveExecution()`, `rejectExecution()`, `cancelExecution()`
- Pattern: modal/wizard + appel API + notification + rafraîchissement
- Wrapper HTTP commun: `apiFetch()` avec gestion auth, retry 401, parsing erreurs (Story 17.3 appliquée)

### Intelligence des Stories Précédentes

**Story 17.14 (Annuler opération):**
- Colonne "Actions" déjà créée dans `ExecutionsPage.tsx`
- Pattern établi: bouton d'action avec icône, tooltip, RBAC, size="small"
- Position: après colonne "Durée"
- RBAC: `execution.user.id === currentUser.id` OU `canViewAll`
- Messages constants: `MESSAGES` object pour cohérence
- Notifications: `notification.success()` / `notification.error()`
- Logging: `logger.debug()` / `logger.error()`

**Story 17.2 (Refactoriser ExecutionWizard):**
- `ExecutionWizard.tsx` refactorisé: 2035 → 536 lignes (-73%)
- 5 hooks créés: `useWizardStep`, `useActionSelection`, `useTargetSelection`, `useParameterForm`, `useWizardSubmit`
- 4 composants créés: `ActionSelectionStep`, `TargetSelectionStep`, `ParameterFormStep`, `WizardSummary`
- Structure modulaire facilite l'ajout de paramètres initiaux

**Story 8.8 (Déplacement approbations vers Exécutions):**
- `PendingApprovalsList.tsx` montre le pattern pour les boutons d'action (Approuver/Rejeter)
- Modal.confirm() → remplacé par `App.useApp().modal.confirm()` (Ant Design 6.2)
- Pattern de notification: `notification.success()` / `notification.error()`

**Story 4.1 (Wizard exécution 3 étapes):**
- Wizard original créé avec les 3 étapes
- Étape 1: Sélection action (autocomplete)
- Étape 2: Sélection targets + environnement (TargetSelector component)
- Étape 3: Paramètres dynamiques (formulaire généré depuis action.parameters schema)
- Soumission: `submitExecution()` avec payload `{ action_id, target_names, environment, parameters }`

### Contraintes Techniques et Décisions d'Architecture

**RBAC pour la relance:**
- Règle: initiateur de l'opération OU profil DBA/DBOPS
- Code: `if user.id != execution.user_id && !canViewAll: hide button`
- **Pas de validation backend spécifique** - la validation RBAC se fait au moment de la soumission du wizard (AC5)

**Ouverture du wizard avec paramètres:**
- Approche: Passer les paramètres via props `initialParams` au composant `ExecutionWizard`
- Alternative: Navigation avec query params → **Rejetée** car le wizard est déjà modal (Story 17.2)
- **Décision:** Utiliser state local + props pour pré-remplir le wizard

**Nouvelle exécution vs modification:**
- **IMPORTANT:** La relance crée toujours une NOUVELLE exécution
- L'exécution originale n'est jamais modifiée
- Utiliser `submitExecution()` (API POST /executions/) comme pour une exécution normale

**Validation des permissions:**
- La validation RBAC se fait au moment de la soumission du wizard (pas au clic sur Relancer)
- Si l'utilisateur n'a plus les permissions: erreur 403 du backend avec message explicite
- Afficher l'erreur via `notification.error()` avec le message du backend

**Standards Frontend (FRONTEND-STANDARDS.md):**
- Hooks: utiliser hooks métier pour la logique réutilisable
- État: React Query pour data fetching et cache (déjà utilisé dans ExecutionsPage)
- Logging: utiliser `logger.debug/info/warn/error()` (Story 17.7)
- Notifications: `notification.success/error()` via `App.useApp()` (Ant Design 6.2)
- Tests: React Testing Library, couverture minimale 80%
- **Ant Design 6.2:** Utiliser `App.useApp().modal` au lieu de `Modal.confirm()` direct

### Bibliothèques et Versions

**Frontend:**
- React: 19.2
- Ant Design: 6.2 (icônes: `@ant-design/icons`)
- TypeScript: 5.9
- React Query: pour state management et cache
- Vitest + React Testing Library: pour tests

**Icônes Ant Design:**
- `RedoOutlined` pour le bouton Relancer (action de relance/répétition)
- Alternative: `SyncOutlined` (mais déjà utilisé pour status RUNNING)

**Pas de nouvelles dépendances backend** - fonctionnalité purement frontend.

### Fichiers à Modifier ou Créer

**Frontend:**
1. `idp-portal/frontend/src/pages/ExecutionsPage.tsx`
   - Ajouter bouton "Relancer" dans la colonne "Actions" (à côté du bouton Annuler)
   - Implémenter fonction `handleRestartExecution(execution)`
   - Gérer l'ouverture du wizard avec paramètres pré-remplis
2. `idp-portal/frontend/src/components/execution/ExecutionWizard.tsx`
   - Ajouter prop `initialParams?: WizardInitialParams`
   - Modifier les hooks pour accepter et utiliser les paramètres initiaux
   - Pré-remplir les champs des 3 étapes si `initialParams` fourni
3. `idp-portal/frontend/src/types/wizard.ts` (créer si n'existe pas)
   - Créer interface `WizardInitialParams`
   - Exporter les types nécessaires
4. `idp-portal/frontend/src/utils/executionHelpers.ts` (créer si n'existe pas)
   - Créer fonction `prepareWizardParamsFromExecution(execution): WizardInitialParams`
5. `idp-portal/frontend/src/pages/ExecutionsPage.test.tsx`
   - Ajouter tests pour le bouton Relancer (visibilité, RBAC, clic)
6. `idp-portal/frontend/src/components/execution/ExecutionWizard.test.tsx`
   - Ajouter tests pour les paramètres initiaux (pré-remplissage des 3 étapes)

**Documentation:**
1. `idp-portal/docs/user-guide/executions.md`
   - Documenter la fonctionnalité "Relancer une exécution"

### Dépendances et Prérequis

**Stories prérequises:**
- ✅ Story 17.14 (Annuler opération) - colonne "Actions" déjà créée, pattern RBAC établi
- ✅ Story 17.2 (Refactoriser ExecutionWizard) - structure modulaire facilitant l'ajout de paramètres initiaux
- ✅ Story 4.1 (Wizard exécution) - wizard 3 étapes opérationnel
- ✅ Story 13.2 (Sélection targets) - TargetSelector component opérationnel

**Pas de nouvelles dépendances nécessaires** - toutes les bibliothèques requises sont déjà installées.

### Considérations de Test

**Frontend:**
- Tests composants: affichage conditionnel du bouton Relancer, RBAC
- Tests intégration wizard: pré-remplissage des 3 étapes avec paramètres initiaux
- Tests unitaires: fonction `prepareWizardParamsFromExecution()`
- Edge cases: action supprimée, permissions insuffisantes, paramètres manquants

**Pas de tests backend** - fonctionnalité purement frontend réutilisant l'API POST /executions/ existante.

**Fixtures existantes:**
- User fixtures déjà disponibles (profiles: DBOPS, DBA, DBA_CLIENT, BUSINESS)
- Execution fixtures avec différents statuts
- Action fixtures avec paramètres dynamiques

### Pièges à Éviter

1. **Ne pas modifier l'exécution originale** - toujours créer une nouvelle exécution via `submitExecution()`
2. **Ne pas oublier la vérification RBAC côté frontend** - vérifier initiateur OU DBOPS/DBA avant d'afficher le bouton
3. **Gérer le cas où l'action n'existe plus** - afficher erreur explicite "Action non disponible"
4. **Ne pas court-circuiter la validation RBAC du wizard** - laisser le backend valider les permissions au moment de la soumission
5. **Utiliser `App.useApp().modal` au lieu de `Modal.confirm()`** - respecter Ant Design 6.2 standards
6. **Logger les erreurs** - utiliser `logger.error()` pour toutes les erreurs de relance
7. **Tester le pré-remplissage des 3 étapes** - vérifier que tous les paramètres sont correctement initialisés

### Approche d'Implémentation Recommandée

**Phase 1: Bouton Relancer et logique de base**
1. Ajouter le bouton "Relancer" dans `ExecutionsPage.tsx` (Task 1)
2. Créer la fonction `prepareWizardParamsFromExecution()` (Task 2)
3. Implémenter l'ouverture du wizard avec paramètres (Task 1.2)

**Phase 2: Modification du wizard pour paramètres initiaux**
1. Ajouter prop `initialParams` à `ExecutionWizard` (Task 3.1)
2. Modifier les hooks pour pré-remplir les champs (Task 3.2-3.4)
3. Tester le pré-remplissage et la modification (Task 3.5)

**Phase 3: Tests et validation**
1. Tests unitaires `ExecutionsPage` (Task 4)
2. Tests d'intégration `ExecutionWizard` (Task 5)
3. Validation manuelle end-to-end (Task 6)

### Références

- [Source: idp-portal/frontend/src/pages/ExecutionsPage.tsx#1-656] - Composant ExecutionsPage avec table et colonne Actions
- [Source: idp-portal/frontend/src/components/execution/ExecutionWizard.tsx] - Composant ExecutionWizard refactorisé (Story 17.2)
- [Source: idp-portal/frontend/src/services/execution_service.ts] - Service submitExecution() pour créer exécution
- [Source: idp-portal/frontend/FRONTEND-STANDARDS.md] - Standards React 19.2 + Ant Design 6.2
- [Source: _bmad-output/implementation-artifacts/17-14-annuler-operation-par-initiateur.md] - Story précédente avec pattern bouton Actions
- [Source: _bmad-output/planning-artifacts/epics.md#3778-3806] - Story 17.15 dans les epics

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

N/A

### Completion Notes List

- Bouton "Relancer" ajouté dans ExecutionsPage avec icône RedoOutlined, RBAC (initiateur OU admin), tooltip
- Fonction `prepareWizardParamsFromExecution()` créée pour extraire les paramètres depuis une exécution passée
- Targets extraits depuis `parameters._targets` (stockage backend) au lieu de `execution.target_names` (champ inexistant)
- ExecutionWizard accepte `initialParams?: WizardInitialParams` pour pré-remplir environnement, targets (mode manuel), et paramètres dynamiques
- Correction bug pré-existant dans ParametersFormStep : le wrapper div `ref` autour du premier champ de formulaire cassait l'injection de valeur par `Form.Item` d'Ant Design. Fix: déplacement du wrapper div à l'extérieur du `Form.Item`
- ExecutionsPage.test.tsx : 58 échecs pré-existants (mock `getIntegrations` manquant) — non causés par cette story
- `docs/user-guide/executions.md` n'existe pas dans le projet — documentation non créée (répertoire `docs/user-guide/` inexistant)
- Tests: 42/42 ExecutionWizard, 8/8 executionHelpers — tous passent
- TypeScript: compilation propre (`npx tsc --noEmit`)

### File List

**Fichiers créés:**
- `frontend/src/types/wizard.ts` — Interface `WizardInitialParams`
- `frontend/src/utils/executionHelpers.ts` — Fonction `prepareWizardParamsFromExecution()`
- `frontend/src/utils/executionHelpers.test.ts` — 8 tests unitaires

**Fichiers modifiés:**
- `frontend/src/pages/ExecutionsPage.tsx` — Bouton Relancer, états restart, handlers, ExecutionWizard
- `frontend/src/components/catalog/ExecutionWizard.tsx` — Prop `initialParams`, pré-remplissage environnement/targets/paramètres
- `frontend/src/components/catalog/ParametersFormStep.tsx` — Fix wrapper div ref hors Form.Item (non-workflow + workflow)
- `frontend/src/components/catalog/ExecutionWizard.test.tsx` — 5 nouveaux tests Story 17.15 (AC3, AC4)
- `frontend/src/pages/ExecutionsPage.test.tsx` — Mocks catalog_service et ExecutionWizard ajoutés

## Change Log

| Fichier | Changement |
|---|---|
| `src/types/wizard.ts` | Nouveau: interface `WizardInitialParams` |
| `src/utils/executionHelpers.ts` | Nouveau: `prepareWizardParamsFromExecution()` avec extraction `_targets` |
| `src/utils/executionHelpers.test.ts` | Nouveau: 8 tests unitaires |
| `src/pages/ExecutionsPage.tsx` | Ajout bouton Relancer (RedoOutlined), handlers restart, ExecutionWizard |
| `src/components/catalog/ExecutionWizard.tsx` | Ajout prop `initialParams`, pré-remplissage env/targets/params |
| `src/components/catalog/ParametersFormStep.tsx` | Fix: wrapper div déplacé hors Form.Item pour premier champ |
| `src/components/catalog/ExecutionWizard.test.tsx` | 5 tests Story 17.15 (pré-sélection env, targets, params, modification) |
| `src/pages/ExecutionsPage.test.tsx` | Mocks pour catalog_service et ExecutionWizard |
