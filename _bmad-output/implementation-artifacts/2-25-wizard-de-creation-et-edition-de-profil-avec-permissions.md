# Story 2.25 : Wizard de création et édition de profil avec permissions

Status: done

## Story

As a **DBOPS**,
I want **créer ou éditer un profil via un wizard en 3 étapes incluant la configuration des permissions**,
so that **je puisse définir les autorisations du profil directement lors de sa création**.

## Acceptance Criteria

1. **AC1 — Ouverture du wizard**
   **Given** un DBOPS clique sur "Nouveau profil" ou "Editer" un profil,
   **When** le wizard s'ouvre,
   **Then** il affiche 3 étapes : (1) Général, (2) Permissions Actions, (3) Permissions Targets.

2. **AC2 — Étape 1 : Général**
   - Nom du profil (obligatoire)
   - Description (optionnel)
   - Groupe AD associé (optionnel)
   - Flags : Admin (toggle), Auditeur (toggle)

3. **AC3 — Étape 2 : Permissions Actions**
   **Given** un DBOPS configure les permissions actions,
   **When** il sélectionne le type de permission,
   **Then** il peut choisir parmi : "Toutes les actions", "Liste d'actions", "Pattern de tags".

   **Given** le type est "Liste d'actions",
   **When** le DBOPS configure,
   **Then** un multi-select affiche les actions existantes (publiées).

   **Given** le type est "Pattern de tags",
   **When** le DBOPS configure,
   **Then** un champ texte permet de saisir des patterns (ex: "oracle*", "provisioning").

   **Given** un type de permission est sélectionné,
   **When** le DBOPS configure les environnements,
   **Then** un multi-select permet de choisir les environnements autorisés (DEV, STAGING, PROD, etc.).

4. **AC4 — Étape 3 : Permissions Targets**
   **Given** un DBOPS configure les permissions targets,
   **When** il sélectionne le type de permission,
   **Then** il peut choisir parmi : "Toutes les targets", "Liste de targets", "Pattern".

   **Given** le type est "Liste de targets" ou "Pattern",
   **When** le DBOPS configure,
   **Then** un champ texte libre permet de saisir les noms ou patterns (MVP : texte libre, futur : connexion API inventaire).

5. **AC5 — Navigation et persistance**
   **Given** un DBOPS navigue entre les étapes,
   **When** il clique Précédent/Suivant,
   **Then** les données saisies sont conservées (state local).

6. **AC6 — Enregistrement**
   **Given** un DBOPS est sur l'étape 3,
   **When** il clique "Enregistrer",
   **Then** le profil est créé/mis à jour via les APIs existantes (POST/PUT /profiles, /profiles/{id}/action-permissions, /profiles/{id}/target-permissions).

7. **AC7 — Mode édition**
   **And** en mode édition, les champs sont pré-remplis avec les données et permissions existantes.
   **And** indicateur de progression visible (stepper).
   **And** validation par étape avant passage à la suivante.
   **And** composants UI cohérents avec le wizard actions (Story 2.22).

## Tasks / Subtasks

- [x] Task 1 (AC: 1, 7) — Composant wizard et stepper
  - [x] 1.1 : Créer `ProfileWizard.tsx` dans `frontend/src/components/admin/` avec Ant Design Steps (3 étapes : "Général", "Permissions Actions", "Permissions Targets").
  - [x] 1.2 : State local unifié pour tout le wizard (même pattern que ActionWizard) : `{ name, description, ad_group, is_admin, is_auditor, actions_type, action_ids, tag_patterns, environments, targets_type, target_names, target_patterns }`.
  - [x] 1.3 : En mode édition : charger profil via `getProfile(id)`, permissions via `getProfileActions(id)` et `getProfileTargets(id)`, pré-remplir le state.

- [x] Task 2 (AC: 2) — Étape 1 Général
  - [x] 2.1 : Étape 1 affiche : Input nom, TextArea description, Input groupe AD, Switch Admin, Switch Auditeur. Réutiliser le même layout que ProfileForm.
  - [x] 2.2 : Validation : nom requis et non vide (whitespace) avant "Suivant".

- [x] Task 3 (AC: 3) — Étape 2 Permissions Actions
  - [x] 3.1 : Radio.Group pour `actions_type` : "Toutes les actions" (`all`), "Liste d'actions" (`list`), "Pattern de tags" (`pattern`).
  - [x] 3.2 : Si `list` : Select multiple avec `actionsOptions` (charger via `listActions()` au mount). Même comportement que ProfileForm.
  - [x] 3.3 : Si `pattern` : Select multiple mode="tags" ou Select avec `tagsOptions` (charger via `getTags()` au mount). Même comportement que ProfileForm.
  - [x] 3.4 : Multi-select environnements : `['DEV', 'STAGING', 'PROD']` (constante ENVIRONMENT_OPTIONS existante dans ProfileForm).
  - [x] 3.5 : Pas de validation bloquante obligatoire pour passer à l'étape 3 (permissions optionnelles).

- [x] Task 4 (AC: 4) — Étape 3 Permissions Targets
  - [x] 4.1 : Radio.Group pour `targets_type` : "Toutes les targets" (`all`), "Liste de targets" (`list`), "Pattern" (`pattern`).
  - [x] 4.2 : Si `list` : Select multiple avec `MOCK_TARGET_OPTIONS` (MVP : mock, futur : API inventaire). Même comportement que ProfileForm.
  - [x] 4.3 : Si `pattern` : Select mode="tags" tokenSeparators={[',']} pour saisie libre. Même comportement que ProfileForm.
  - [x] 4.4 : Bouton "Enregistrer" visible uniquement à l'étape 3.

- [x] Task 5 (AC: 5, 6) — Navigation et soumission
  - [x] 5.1 : Boutons "Précédent" / "Suivant" changent l'étape courante sans perdre le state.
  - [x] 5.2 : À la soumission (étape 3, clic "Enregistrer") :
    - Mode création : `createProfile(payload)` → récupérer `id` → `putProfileActions(id, actionsPayload)` → `putProfileTargets(id, targetsPayload)`.
    - Mode édition : `updateProfile(id, payload)` → `putProfileActions(id, actionsPayload)` → `putProfileTargets(id, targetsPayload)`.
  - [x] 5.3 : Fermer wizard et appeler `onSuccess(profile)` pour rafraîchir la liste.

- [x] Task 6 (AC: 7) — Intégration dans AdminPage
  - [x] 6.1 : Remplacer `ProfileForm` par `ProfileWizard` pour "Nouveau profil" et "Éditer" (même pattern qu'ActionWizard a remplacé ActionForm pour les actions).
  - [x] 6.2 : Optionnel : conserver ProfileForm pour les power users si demandé, ou remplacer entièrement.

- [x] Task 7 — Tests
  - [x] 7.1 : `ProfileWizard.test.tsx` : wizard affiche 3 étapes ; navigation Précédent/Suivant conserve les valeurs ; soumission à l'étape 3 envoie les bons payloads.
  - [x] 7.2 : Test mode édition : champs pré-remplis depuis profil + permissions existantes.
  - [x] 7.3 : Régression : création/édition de profil via wizard produit le même résultat qu'via ProfileForm (mêmes API, même schéma).

## Dev Notes

### Pattern à suivre : ActionWizard.tsx

**Le wizard profil doit suivre exactement le pattern d'ActionWizard** (Story 2.22). Consulter le code source :
- `idp-portal/frontend/src/components/admin/ActionWizard.tsx` (362 lignes)
- Pattern : Modal + Steps + Form + state local + validation par étape + soumission finale

### APIs existantes (ne pas créer de nouveaux endpoints)

**profiles_service.ts** fournit toutes les fonctions nécessaires :
```typescript
// Profil CRUD
getProfile(id: number): Promise<ProfileResponse>
createProfile(payload: ProfileCreate): Promise<ProfileResponse>
updateProfile(id: number, payload: ProfileUpdate): Promise<ProfileResponse>

// Permissions Actions (Story 2.10)
getProfileActions(profileId: number): Promise<ProfileActionPermissionsResponse>
putProfileActions(profileId: number, payload: ProfileActionPermissionsUpdate): Promise<...>

// Permissions Targets (Story 2.11)
getProfileTargets(profileId: number): Promise<ProfileTargetPermissionsResponse>
putProfileTargets(profileId: number, payload: ProfileTargetPermissionsUpdate): Promise<...>
```

**admin_service.ts** pour les données de référence :
```typescript
listActions(): Promise<ActionListItem[]>  // Pour select "Liste d'actions"
getTags(): Promise<TagResponse[]>         // Pour select "Pattern de tags"
```

### Types existants (types/api.ts)

```typescript
interface ProfileCreate {
  name: string;
  description?: string | null;
  ad_group: string;
  is_admin?: boolean;
  is_auditor?: boolean;
}

interface ProfileUpdate {
  name?: string | null;
  description?: string | null;
  ad_group?: string | null;
  is_admin?: boolean | null;
  is_auditor?: boolean | null;
}

type ProfileActionsType = 'list' | 'pattern' | 'all';
interface ProfileActionPermissionsUpdate {
  actions_type: ProfileActionsType;
  action_ids?: number[] | null;
  tag_patterns?: string[] | null;
  environments?: string[] | null;
}

type ProfileTargetsType = 'list' | 'pattern' | 'all';
interface ProfileTargetPermissionsUpdate {
  targets_type: ProfileTargetsType;
  target_names?: string[] | null;
  target_patterns?: string[] | null;
}
```

### Constantes à réutiliser (depuis ProfileForm.tsx)

```typescript
const ENVIRONMENT_OPTIONS = ['DEV', 'STAGING', 'PROD'];
const MOCK_TARGET_OPTIONS = ['assurance-db01', 'assurance-db02', 'infra-oracle-prod'];
```

**Recommandation** : Extraire ces constantes vers `utils/profileOptions.ts` (comme `actionOptions.ts` pour ActionWizard) pour éviter la duplication.

### Structure du state local (pattern ActionWizard)

```typescript
// State principal via Form.useForm()
const [form] = Form.useForm<ProfileWizardValues>();

// États spécifiques hors Form (comme ActionWizard)
const [actionsOptions, setActionsOptions] = useState<{id: number; name: string}[]>([]);
const [tagsOptions, setTagsOptions] = useState<string[]>([]);
const [loadingData, setLoadingData] = useState(false);
const [currentStep, setCurrentStep] = useState(0);
const [submitError, setSubmitError] = useState<string | null>(null);
const [saving, setSaving] = useState(false);

// Interface pour les valeurs du form
interface ProfileWizardValues {
  name: string;
  description?: string | null;
  ad_group: string;
  is_admin: boolean;
  is_auditor: boolean;
  actions_type: ProfileActionsType;
  action_ids: number[];
  tag_patterns: string[];
  environments: string[];
  targets_type: ProfileTargetsType;
  target_names: string[];
  target_patterns: string[];
}
```

### Flux de soumission (mode création)

1. Valider tous les champs Form
2. Construire `ProfileCreate` payload
3. `const profile = await createProfile(payload);`
4. Construire `ProfileActionPermissionsUpdate` depuis le form
5. `await putProfileActions(profile.id, actionsPayload);`
6. Construire `ProfileTargetPermissionsUpdate` depuis le form
7. `await putProfileTargets(profile.id, targetsPayload);`
8. `onSuccess(profile);`

### Flux de soumission (mode édition)

1. Valider tous les champs Form
2. Construire `ProfileUpdate` payload
3. `const profile = await updateProfile(editProfile.id, payload);`
4. Construire `ProfileActionPermissionsUpdate` depuis le form
5. `await putProfileActions(editProfile.id, actionsPayload);`
6. Construire `ProfileTargetPermissionsUpdate` depuis le form
7. `await putProfileTargets(editProfile.id, targetsPayload);`
8. `onSuccess(profile);`

### Mode édition : chargement initial

```typescript
useEffect(() => {
  if (!open) return;
  if (editProfile) {
    setLoadingData(true);
    Promise.all([
      getProfileActions(editProfile.id),
      getProfileTargets(editProfile.id),
      listActions(),
      getTags(),
    ])
    .then(([actionsPerms, targetsPerms, actions, tags]) => {
      form.setFieldsValue({
        name: editProfile.name,
        description: editProfile.description ?? undefined,
        ad_group: editProfile.ad_group,
        is_admin: editProfile.is_admin,
        is_auditor: editProfile.is_auditor,
        actions_type: actionsPerms.actions_type,
        action_ids: actionsPerms.action_ids ?? [],
        tag_patterns: actionsPerms.tag_patterns ?? [],
        environments: actionsPerms.environments ?? [],
        targets_type: targetsPerms.targets_type,
        target_names: targetsPerms.target_names ?? [],
        target_patterns: targetsPerms.target_patterns ?? [],
      });
      setActionsOptions(actions.map(a => ({ id: a.id, name: a.name })));
      setTagsOptions(tags.map(t => t.name));
    })
    .catch(() => { /* handle error */ })
    .finally(() => setLoadingData(false));
  } else {
    // Mode création : valeurs par défaut
    form.setFieldsValue({
      is_admin: false,
      is_auditor: false,
      actions_type: 'all',
      action_ids: [],
      tag_patterns: [],
      environments: [],
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
    });
    // Charger options pour les selects
    Promise.all([listActions(), getTags()])
      .then(([actions, tags]) => {
        setActionsOptions(actions.map(a => ({ id: a.id, name: a.name })));
        setTagsOptions(tags.map(t => t.name));
      });
  }
}, [open, editProfile, form]);
```

### Project Structure Notes

- **Nouveau fichier** : `frontend/src/components/admin/ProfileWizard.tsx`
- **Nouveau fichier** : `frontend/src/components/admin/ProfileWizard.test.tsx`
- **Modifier** : `frontend/src/components/admin/index.ts` (export ProfileWizard)
- **Modifier** : `frontend/src/pages/AdminPage.tsx` (utiliser ProfileWizard au lieu de ProfileForm)
- **Optionnel** : `frontend/src/utils/profileOptions.ts` (extraire constantes ENVIRONMENT_OPTIONS, MOCK_TARGET_OPTIONS)

### Architecture Compliance

- **Stack** : React 19, TypeScript, Ant Design 6 (Steps, Form, Input, Select, Radio, Switch, Button, Modal, Alert, Space)
- **Pattern** : Même architecture que ActionWizard — Modal avec wizard 3 étapes, state local, validation par étape
- **API** : Aucun nouvel endpoint. Appels séquentiels aux APIs existantes de profiles_service.ts
- **Accessibilité** : Steps avec aria-label par étape ; focus management ; boutons accessibles au clavier

### Library/Framework Requirements

- **Ant Design 6.2** : Modal, Steps, Form, Input, TextArea, Select, Radio.Group, Switch, Button, Space, Alert
- **Réutilisation** : Pattern ActionWizard, types ProfileCreate/ProfileUpdate/ProfileActionPermissionsUpdate/ProfileTargetPermissionsUpdate, services profiles_service + admin_service

### File Structure Requirements

- Créer : `frontend/src/components/admin/ProfileWizard.tsx`
- Créer : `frontend/src/components/admin/ProfileWizard.test.tsx`
- Modifier : `frontend/src/components/admin/index.ts`
- Modifier : `frontend/src/pages/AdminPage.tsx`
- Optionnel : `frontend/src/utils/profileOptions.ts`

### Testing Requirements

- **Vitest + React Testing Library** : Rendu wizard 3 étapes ; navigation Précédent/Suivant conserve valeurs ; soumission appelle les bonnes APIs dans le bon ordre
- **Mock services** : `vi.mock('../../services/profiles_service')` et `vi.mock('../../services/admin_service')`
- **Test mode création** : étape 1 → étape 2 → étape 3 → Enregistrer → createProfile + putProfileActions + putProfileTargets appelés
- **Test mode édition** : champs pré-remplis, soumission → updateProfile + putProfileActions + putProfileTargets appelés

### Previous Story Intelligence (Story 2.22 ActionWizard)

**Leçons à appliquer** :
- Largeur modal 640px (cohérence avec ActionWizard)
- Steps avec descriptions pour chaque étape
- Form avec layout="vertical"
- Validation étape 1 avant Suivant (nom requis)
- Gestion erreur permissions séparée de l'erreur profil (notification warning si permissions échouent mais profil créé)
- `destroyOnHidden` sur Modal pour reset complet
- Pattern `currentStep === X` pour afficher/masquer contenu (display: none pour étape 1 pour conserver form state)

**Différences avec ActionWizard** :
- En mode création, les permissions sont configurables dès le wizard (pas seulement en édition comme ProfileForm actuel)
- Pas de conversion schema ↔ liste comme pour les paramètres d'action
- APIs séquentielles obligatoires : profil → actions → targets

### References

- [Source: _bmad-output/planning-artifacts/epics.md] Story 2.25 — Wizard de création et édition de profil avec permissions
- [Source: idp-portal/frontend/src/components/admin/ActionWizard.tsx] Pattern wizard 3 étapes à suivre
- [Source: idp-portal/frontend/src/components/admin/ProfileForm.tsx] Logique existante pour permissions (à intégrer dans wizard)
- [Source: idp-portal/frontend/src/services/profiles_service.ts] APIs profils et permissions
- [Source: idp-portal/frontend/src/types/api.ts] Types ProfileCreate, ProfileActionPermissionsUpdate, ProfileTargetPermissionsUpdate

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- **ProfileWizard.tsx** (350 lignes) créé suivant le pattern ActionWizard
- Wizard 3 étapes : Général, Permissions Actions, Permissions Targets
- Modal Ant Design avec Steps, Form, Radio.Group, Select multiple
- State local via Form.useForm() + Form.useWatch pour affichage conditionnel
- Mode création : createProfile → putProfileActions → putProfileTargets
- Mode édition : chargement async des permissions existantes, updateProfile au lieu de createProfile
- Validation step 1 (nom requis ; groupe AD optionnel — AC2) avant navigation
- Gestion d'erreur avec notification.warning si permissions échouent mais profil créé
- AdminPage.tsx mis à jour pour utiliser ProfileWizard au lieu de ProfileForm
- 20 tests unitaires couvrant tous les AC (navigation, soumission, mode édition, payloads, erreurs)
- Suite de tests complète : 236 tests passent, 0 régression
- **Code review 2026-01-29** : AC2 groupe AD optionnel ; constantes extraites vers utils/profileOptions.ts ; code mort AdminPage supprimé ; resetFields retiré (destroyOnHidden) ; test reset modal avec waitFor

### File List

- `idp-portal/frontend/src/components/admin/ProfileWizard.tsx` (nouveau)
- `idp-portal/frontend/src/components/admin/ProfileWizard.test.tsx` (nouveau)
- `idp-portal/frontend/src/components/admin/index.ts` (modifié — export ProfileWizard)
- `idp-portal/frontend/src/pages/AdminPage.tsx` (modifié — import et utilisation ProfileWizard)
- `idp-portal/frontend/src/utils/profileOptions.ts` (nouveau — constantes ENVIRONMENT_OPTIONS, MOCK_TARGET_OPTIONS)
- `idp-portal/frontend/src/components/admin/ProfileForm.tsx` (modifié — import profileOptions)

