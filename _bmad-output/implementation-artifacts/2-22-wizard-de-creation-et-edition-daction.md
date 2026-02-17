# Story 2.22 : Wizard de création et édition d'action

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **DBOPS**,
I want **créer ou éditer une action via un wizard en 3 étapes**,
so that **l'expérience soit plus guidée et moins intimidante qu'un long formulaire**.

## Acceptance Criteria

1. **AC1 — Ouverture du wizard**
   **Given** un DBOPS clique sur "Nouvelle action" ou "Éditer",
   **When** le wizard s'ouvre,
   **Then** il affiche 3 étapes : (1) Général, (2) Paramètres, (3) Impact & Changement.

2. **AC2 — Contenu des étapes**
   **Etape 1 — Général** : nom, description, moteur, plateforme, tags.
   **Etape 2 — Paramètres** : éditeur visuel (réutilise composant Story 2.17 — ParametersEditor).
   **Etape 3 — Impact & Changement** : règles d'impact (Story 2.18 — ImpactRulesEditor) + `change_model_code`.

3. **AC3 — Navigation et persistance**
   **Given** un DBOPS navigue entre les étapes,
   **When** il clique Précédent / Suivant,
   **Then** les données saisies sont conservées (state local).

4. **AC4 — Enregistrement**
   **Given** un DBOPS est sur l'étape 3,
   **When** il clique "Enregistrer",
   **Then** l'action est créée ou mise à jour via l'API existante (POST /api/v1/admin/actions ou PUT /api/v1/admin/actions/{id}).

5. **AC5 — Mode édition**
   **And** en mode édition, les champs sont pré-remplis depuis l'action existante.
   **And** indicateur de progression visible (stepper).
   **And** validation par étape avant passage à la suivante.

## Tasks / Subtasks

- [x] Task 1 (AC: 1, 5) — Composant wizard et stepper
  - [x] 1.1 : Créer un composant `ActionWizard` (ou intégrer le stepper dans un modal dédié) avec Ant Design Steps : étapes "Général", "Paramètres", "Impact & Changement".
  - [x] 1.2 : State local unique pour tout le formulaire (même structure que ActionForm : ActionCreate + execution_steps, parameterList, impactRulesList, changeTypeConfig, changeModelCode, selectedTags).
  - [x] 1.3 : En mode édition : charger l'action via GET /api/v1/admin/actions/{id}, pré-remplir le state (conversion parameters_schema → parameterList, impact_rules → impactRulesList comme dans ActionForm).

- [x] Task 2 (AC: 2) — Étape 1 Général
  - [x] 2.1 : Étape 1 affiche : Input nom, TextArea description, Select catégorie, Select moteur, Select plateforme, Tags (multi-select avec auto-complétion comme ActionForm). Réutiliser les constantes CATEGORY_OPTIONS, ENGINE_OPTIONS, PLATFORM_OPTIONS.
  - [x] 2.2 : Validation : nom requis avant "Suivant". Optionnel : validation inline sur chaque champ.

- [x] Task 3 (AC: 2) — Étape 2 Paramètres
  - [x] 3.1 : Afficher le composant `ParametersEditor` avec value/onChange liés au state (parameterList). Même intégration que dans ActionForm (pas de changement au composant ParametersEditor).
  - [x] 3.2 : Pas de validation bloquante obligatoire pour passer à l'étape 3 (les paramètres peuvent être vides). Si validation stricte souhaitée : noms uniques, nom requis par paramètre (comme ActionForm).

- [x] Task 4 (AC: 2) — Étape 3 Impact & Changement
  - [x] 4.1 : Afficher `ImpactRulesEditor` (value/onChange → impactRulesList) et le champ "Code modèle de changement" (change_model_code) comme dans ActionForm. Réutiliser ChangeTypeConfig si les étapes de changement par environnement sont dans le scope (epics : "Impact & Change" = impact + change_model_code ; les étapes d'exécution / ChangeTypeConfig restent dans le formulaire complet ou dans un flux séparé — préciser : pour cette story, étape 3 = ImpactRulesEditor + change_model_code uniquement).
  - [x] 4.2 : Bouton "Enregistrer" appelle la même logique que ActionForm : build payload (parameterListToSchema, listToImpactRules, etc.), POST ou PUT selon mode, puis PUT steps si édition avec étapes.

- [x] Task 5 (AC: 3, 4) — Navigation et soumission
  - [x] 5.1 : Boutons "Précédent" / "Suivant" changent l'étape courante sans perdre le state. "Enregistrer" visible uniquement à l'étape 3.
  - [x] 5.2 : À la soumission : construire ActionCreate depuis le state (comme ActionForm), appeler onSubmit (création) ou PUT action + PUT steps (édition). Fermer le wizard et rafraîchir la liste (onSuccess).

- [x] Task 6 (AC: 5) — Intégration dans l'admin
  - [x] 6.1 : Depuis la page Admin (liste des actions), "Nouvelle action" ouvre le wizard (au lieu du modal ActionForm actuel, ou en parallèle : choix "Formulaire" vs "Wizard" — selon décision produit, par défaut wizard pour cette story). "Éditer" ouvre le wizard en mode édition avec action pré-chargée.
  - [x] 6.2 : Conserver l'accès au formulaire long (ActionForm) pour les power users si souhaité (optionnel), ou remplacer entièrement par le wizard.

- [x] Task 7 — Tests
  - [x] 7.1 : Tests unitaires ou intégration : wizard affiche 3 étapes ; navigation Précédent/Suivant conserve les valeurs ; soumission à l'étape 3 envoie le bon payload. Test mode édition : champs pré-remplis.
  - [x] 7.2 : Régression : création/édition d'action via wizard produit le même résultat qu'via ActionForm (même API, même schéma).

## Dev Notes

- **Objectif** : Offrir un parcours guidé en 3 étapes pour réduire la charge cognitive. Réutilisation stricte de ParametersEditor, ImpactRulesEditor, et de la logique de build payload (parameterListToSchema, listToImpactRules) déjà présentes dans ActionForm.
- **Pas de nouveau backend** : Les API existantes (POST/PUT actions, PUT steps, GET tags, etc.) suffisent. Le wizard est une couche UX côté frontend.
- **Stepper Ant Design** : Utiliser `Steps` (current), `Button` Précédent/Suivant/Enregistrer. Accessibilité : aria-label "Étape 1 sur 3 : Général", etc.
- **Étapes d'exécution (StepsEditor)** : Les epics indiquent étape 3 = "Impact & Change" (règles d'impact + change_model_code). Les étapes d'exécution (execution_steps) ne sont pas dans le wizard 3 étapes. Options : (a) ajouter une 4e étape "Étapes d'exécution" plus tard, ou (b) garder l'édition des étapes dans le formulaire détaillé après création. Pour cette story, rester sur 3 étapes (Général, Paramètres, Impact & Changement) ; les étapes d'exécution peuvent rester éditables après création via le flux existant (ouvrir l'action en édition avec le formulaire complet ou un onglet dédié).

### Project Structure Notes

- **Frontend** : `idp-portal/frontend/src/components/admin/` — nouveau composant `ActionWizard.tsx` (ou `ActionCreationWizard.tsx`). Réutilisation de ParametersEditor, ImpactRulesEditor, ChangeTypeConfig, AdminPreview (optionnel dans le wizard pour preview live). Fichiers à modifier : point d'entrée Admin (liste actions) pour ouvrir le wizard au lieu ou en plus du modal ActionForm.
- **Services** : `admin_service.ts` — pas de nouveau endpoint ; utiliser createAction, updateAction, updateActionSteps, getTags, updateActionTags.
- **Types** : `types/api.ts` — déjà complets (ActionCreate, ParameterDefinition, ImpactRuleDefinition, etc.).

### Architecture Compliance

- **Stack** : React 19, TypeScript, Ant Design 6 (Steps, Form, Input, Select, Button). Même patterns que ActionForm (state local, conversion schema ↔ liste).
- **API** : Aucun nouvel endpoint. Payload identique à ActionForm (parameters_schema, impact_rules, change_model_code, etc.).
- **Accessibilité** : Steps avec aria-label par étape ; focus management à chaque changement d'étape ; boutons Précédent/Suivant/Enregistrer accessibles au clavier.

### Library/Framework Requirements

- **Ant Design 6.2** : Steps, Form, Input, Select, Button, Space. Composants déjà utilisés dans ActionForm.
- **Réutilisation** : ParametersEditor, ImpactRulesEditor (Story 2.17, 2.18), utilitaires parametersSchema.ts, impactRulesSchema.ts. ChangeTypeConfig et champ change_model_code (Story 2.21).

### File Structure Requirements

- Nouveau fichier : `frontend/src/components/admin/ActionWizard.tsx` (ou nom cohérent avec la convention du projet).
- Modifier : page ou conteneur Admin qui affiche le bouton "Nouvelle action" / "Éditer" pour ouvrir le wizard (ex. `AdminActionsPage.tsx` ou équivalent).
- Exporter le wizard depuis `components/admin/index.ts` si besoin.
- Ne pas dupliquer la logique de validation/build payload : extraire si nécessaire en hooks (ex. `useActionFormState`) partagés entre ActionForm et ActionWizard, ou appeler les mêmes helpers (parameterListToSchema, listToImpactRules).

### Testing Requirements

- **Vitest + React Testing Library** : Rendu du wizard avec 3 étapes ; clic Suivant/Précédent ; vérification que les champs de l’étape 1 restent remplis après navigation ; soumission à l’étape 3 (mock admin_service).
- **Régression** : Les tests existants de création/édition d’action (si ciblent l’API) doivent rester verts ; le wizard appelle les mêmes API.

### Previous Story Intelligence

- **Story 2-17 (ParametersEditor)** : Composant contrôlé value/onChange ; conversion schema ↔ liste dans le parent. Ne pas modifier ParametersEditor pour le wizard ; l’inclure tel quel dans l’étape 2.
- **Story 2-18 (ImpactRulesEditor)** : Idem, value/onChange ; conversion impact_rules (objet) ↔ liste. Inclure dans l’étape 3.
- **Story 2-21 (change_model_code)** : Champ optionnel, validation `^[A-Za-z0-9]+$`, max 50. Déjà dans ActionForm ; reprendre le même champ dans l’étape 3 du wizard.
- **ActionForm** : Validation avant submit (paramètres noms uniques, règles d’impact environnements uniques, etc.). Reproduire les mêmes validations dans le wizard à l’étape concernée ou au moment Enregistrer.

### References

- [Source: _bmad-output/planning-artifacts/epics.md] Story 2.22 — Wizard de création et édition d'action (AC détaillés).
- [Source: idp-portal/frontend/src/components/admin/ActionForm.tsx] Structure du formulaire, state, conversion parameters_schema / impact_rules, appel API.
- [Source: idp-portal/frontend/src/components/admin/ParametersEditor.tsx] Réutilisation étape 2.
- [Source: idp-portal/frontend/src/components/admin/ImpactRulesEditor.tsx] Réutilisation étape 3.
- [Source: idp-portal/frontend/src/utils/parametersSchema.ts] parameterListToSchema, schemaToParameterList.
- [Source: idp-portal/frontend/src/utils/impactRulesSchema.ts] listToImpactRules, impactRulesToList.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- Implémentation complète du wizard 3 étapes (Général, Paramètres, Impact & Changement). Composant `ActionWizard.tsx` avec Ant Design Steps, state local aligné sur ActionForm (parameterList, impactRulesList, defaultImpactLevel, changeModelCode, selectedTags). Mode édition : pré-rempli via useEffect + schemaToParameterList / impactRulesToList. AdminPage utilise ActionWizard par défaut pour "Nouvelle action" et "Éditer". Service `updateAction` ajouté pour PUT /admin/actions/{id} (édition métadonnées). Tests : ActionWizard.test.tsx (8 tests, AC1–AC5, navigation, submit payload, edit pre-fill). Suite frontend 214 tests passent.
- Code review (2026-01-29) : gestion d’échec `updateActionTags` (onSuccess + notification warning), constantes partagées `utils/actionOptions.ts` (CATEGORY_OPTIONS, ENGINE_OPTIONS, PLATFORM_OPTIONS), largeur wizard 640px, test mode création (rendu étape 1).

### File List

- idp-portal/frontend/src/components/admin/ActionWizard.tsx (nouveau)
- idp-portal/frontend/src/components/admin/ActionWizard.test.tsx (nouveau)
- idp-portal/frontend/src/components/admin/index.ts (export ActionWizard)
- idp-portal/frontend/src/pages/AdminPage.tsx (ActionWizard au lieu d’ActionForm, handleEditSubmit appelle updateAction)
- idp-portal/frontend/src/services/admin_service.ts (updateAction)
- idp-portal/frontend/src/utils/actionOptions.ts (constantes partagées Catégorie/Moteur/Plateforme)
- _bmad-output/implementation-artifacts/sprint-status.yaml (2-22 → done, code-review 2026-01-29)
- _bmad-output/implementation-artifacts/2-22-wizard-de-creation-et-edition-daction.md (tasks, status, Dev Agent Record)
