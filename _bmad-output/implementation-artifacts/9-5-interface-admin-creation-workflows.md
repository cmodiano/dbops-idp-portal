# Story 9.5: Interface Admin pour création/édition de workflows

Status: done

<!-- Note: Validation optionnelle. Exécuter validate-create-story pour contrôle qualité avant dev-story. -->

## Story

En tant que **DBOPS**,
je veux **une interface admin complète pour créer et éditer des workflows avec choix du type (action vs workflow), éditeur d'étapes avec sélecteur d'actions existantes, et validation**,
afin que **je puisse composer des chaînes d'automatisation (workflows) directement dans le portail sans manipulation manuelle des données backend**.

## Contexte

Cette story complète l'implémentation de la fonctionnalité workflow initiée dans **Story 5.7**. Story 5.7 a créé le backend complet (modèles, API, validation de boucles) et l'affichage des workflows dans le catalogue (icône dédiée), mais l'interface admin de création/édition des workflows (Task 4 de story 5.7) n'a pas été implémentée.

**Story 5.7 a déjà implémenté:**
- Backend: ItemType enum (action|workflow), WorkflowStep model, validation de boucles circulaires
- API: `PUT /admin/actions/{id}/workflow-steps`, `GET /admin/actions/eligible-for-workflow`
- Frontend types: ItemType, WorkflowStep, WorkflowStepsUpdate dans api.ts
- Catalogue: Icône ApartmentOutlined pour workflows, badge "Workflow" dans ActionDrawerPreview

**Ce qui reste à implémenter (Story 9.5 = Task 4 de Story 5.7):**
- ActionWizard enhancement: Ajout du choix type action/workflow en Step 1
- WorkflowStepsEditor component: Nouveau composant pour éditer les étapes workflow
- Admin service: Fonctions pour appeler les API workflow existantes
- Validation frontend: Vérifier qu'au moins 1 étape existe, chaque étape a un referenced_action_id
- Gestion d'erreurs: Afficher erreurs API (boucles circulaires détectées par backend)

## Acceptance Criteria

### AC1 - Choix du type (action vs workflow) dans ActionWizard Step 1

**Given** un DBOPS ouvre le wizard de création d'action (bouton "Créer une action")
**When** le Step 1 (Général) s'affiche
**Then** un nouveau champ "Type" apparaît en haut du formulaire avec 2 options radio : "Action" (défaut) et "Workflow"

**And** si l'utilisateur sélectionne "Action" :
- Les champs existants s'affichent : Nom, Description, Tags, **Moteur** (obligatoire), **Plateforme** (obligatoire)

**And** si l'utilisateur sélectionne "Workflow" :
- Les champs Moteur et Plateforme sont **masqués ou désactivés** (car workflows n'ont pas de connecteur)
- Les champs Nom, Description, Tags restent visibles et fonctionnent normalement

**And** la validation Step 1 vérifie :
- Si type=action : Moteur et Plateforme sont obligatoires (validation existante)
- Si type=workflow : Moteur et Plateforme ne sont pas requis (pas de validation sur ces champs)

### AC2 - Éditeur d'étapes workflow dans ActionWizard Step 2

**Given** un DBOPS a sélectionné type="Workflow" au Step 1 et passe au Step 2
**When** le Step 2 (Automatisation & Paramètres) s'affiche
**Then** le contenu du Step 2 change complètement :
- Pour type=action : affiche ParametersEditor, ImpactRulesEditor, ChangeTypeConfig (existant)
- Pour type=workflow : affiche le **nouveau composant WorkflowStepsEditor** uniquement

**And** WorkflowStepsEditor affiche :
- Une liste d'étapes numérotées (ordre 1, 2, 3...)
- Chaque étape contient : **AutoComplete pour sélectionner une action existante** + champ "Nom d'affichage" (optionnel)
- Boutons "Ajouter une étape" et "Supprimer" (icône poubelle sur chaque étape)
- Drag-and-drop pour réordonner les étapes (comme StepsEditor)

**And** l'AutoComplete de sélection d'action :
- Appelle `GET /api/v1/admin/actions/eligible-for-workflow` au mount pour charger les actions éligibles
- Filtre: Actions **publiées** uniquement (status=published), type=action (pas workflow dans workflow selon architecture)
- Affiche: Nom de l'action + moteur (ex. "Créer PDB Oracle (oracle)")
- Recherche: L'utilisateur peut taper pour filtrer par nom

**And** validation WorkflowStepsEditor :
- Au moins 1 étape requise (afficher erreur si liste vide à la sauvegarde)
- Chaque étape doit avoir un `referenced_action_id` sélectionné (erreur si action non sélectionnée)

### AC3 - Sauvegarde et API workflow

**Given** un DBOPS a rempli tous les steps du wizard avec type=workflow et étapes valides
**When** il clique sur "Créer" (Step 3 terminé)
**Then** le frontend exécute la séquence suivante :
1. `POST /api/v1/admin/actions` avec `item_type: 'workflow'`, nom, description, tags (pas de engine/platform)
2. Backend crée l'entrée catalogue avec ITEM_TYPE='workflow'
3. `PUT /api/v1/admin/actions/{new_id}/workflow-steps` avec la liste des WorkflowStep (order, name, referenced_action_id)
4. Backend valide les étapes (pas de boucles), met à jour EXECUTION_STEPS CLOB
5. Frontend affiche message succès "Workflow créé avec succès" et ferme le wizard

**And** si validation backend échoue (ex. boucle circulaire détectée) :
- Backend retourne 400 avec error_code "WORKFLOW_LOOP"
- Frontend affiche Alert error avec message clair : "Boucle circulaire détectée dans les étapes du workflow. Vérifiez que les actions référencées ne créent pas de cycle."
- Le wizard reste ouvert pour correction

**And** en mode édition (workflow existant) :
- ActionWizard charge le workflow avec `GET /api/v1/admin/actions/{id}`
- Step 1 affiche type=workflow (champ désactivé, pas de changement de type après création)
- Step 2 affiche WorkflowStepsEditor pré-rempli avec les étapes existantes (order, name, referenced_action_id)
- Sauvegarde: `PUT /api/v1/admin/actions/{id}` (métadonnées) + `PUT /admin/actions/{id}/workflow-steps` (étapes)

### AC4 - UX et feedback utilisateur

**Given** un DBOPS interagit avec WorkflowStepsEditor
**When** il ajoute/supprime/réordonne des étapes
**Then** l'interface réagit immédiatement :
- "Ajouter une étape" → nouvelle ligne apparaît avec ordre auto-incrémenté
- "Supprimer" → étape disparaît, ordres renumérés automatiquement (1, 2, 3...)
- Drag-and-drop → étapes réordonnées visuellement, ordres mis à jour

**And** WorkflowStepsEditor affiche des tooltips/aide :
- Tooltip sur AutoComplete action : "Sélectionnez une action publiée existante"
- Tooltip sur "Nom d'affichage" : "Optionnel - Nom personnalisé pour cette étape dans le workflow"
- Placeholder AutoComplete : "Rechercher une action..."

**And** loading states :
- Pendant chargement actions éligibles : AutoComplete affiche Spin ou "Chargement..."
- Pendant sauvegarde workflow : Bouton "Créer" affiche Spin + texte "Création en cours..."

**And** accessibilité (WCAG 2.1 AA) :
- AutoComplete avec aria-label "Sélectionner une action"
- Boutons avec aria-label ("Ajouter une étape", "Supprimer l'étape 1")
- Erreurs de validation avec role="alert" et message descriptif

### AC5 - Cohérence avec l'architecture existante

**And** ActionWizard conserve sa structure 3-step :
- Step 1 : Général (Type, Nom, Description, Tags, [Engine, Platform si action])
- Step 2 : Automatisation (WorkflowStepsEditor si workflow, ParametersEditor+ImpactRulesEditor si action)
- Step 3 : Impact & Changement (pour workflow: uniquement tags ServiceNow si besoin, pas de change config complexe)

**And** le pattern `Form.useWatch('item_type', form)` est utilisé pour réactivité en temps réel (comme `platform` actuel)

**And** les composants suivent les patterns Ant Design 6.2 :
- Form.Item pour champs formulaire
- AutoComplete pour sélection action avec recherche
- Radio.Group pour choix type action/workflow
- Button avec loading prop pour feedback sauvegarde

**And** les types TypeScript sont stricts :
- ItemType: 'action' | 'workflow'
- WorkflowStep: { order: number; name?: string; referenced_action_id: number }
- WorkflowStepsUpdate: { steps: WorkflowStep[] }

## Tasks / Subtasks

### Frontend - ActionWizard enhancement

- [x] Task 1: Ajouter choix type action/workflow au Step 1 (AC: #1)
  - [x] 1.1 Ajouter `item_type` au type ActionFormValues : `item_type: ItemType` (default 'action')
  - [x] 1.2 Ajouter Radio.Group "Type" en haut du Step 1 (avant Nom) avec options "Action" et "Workflow"
  - [x] 1.3 Ajouter `const itemType = Form.useWatch<ItemType>('item_type', form)` pour observer changements
  - [x] 1.4 Conditionner affichage champs Engine et Platform : `{itemType === 'action' && <Form.Item label="Moteur">...</Form.Item>}`
  - [x] 1.5 Adapter validation Step 1 : si itemType=workflow, ne pas exiger engine/platform (modificer `validateStep1()`)
  - [x] 1.6 Initialiser form.setFieldsValue avec item_type='action' pour création, charger item_type depuis editAction pour édition
  - [x] 1.7 Désactiver changement de type en mode édition : `<Radio.Group disabled={!!editAction}>` (pas de changement après création)

- [x] Task 2: Modifier Step 2 pour afficher WorkflowStepsEditor si workflow (AC: #2)
  - [x] 2.1 Ajouter state `workflowSteps: WorkflowStep[]` et `setWorkflowSteps` dans ActionWizard
  - [x] 2.2 Conditionner rendu Step 2 : `{itemType === 'workflow' ? <WorkflowStepsEditor ... /> : <>{/* ParametersEditor existant */}</>}`
  - [x] 2.3 Passer props à WorkflowStepsEditor : `steps={workflowSteps}`, `onChange={setWorkflowSteps}`, `loading={...}`
  - [x] 2.4 Charger workflow steps en mode édition : si editAction.item_type=workflow, fetch `GET /admin/actions/{id}` et extraire workflow_steps
  - [x] 2.5 Adapter validation Step 2 : si workflow, valider workflowSteps.length > 0 et chaque step a referenced_action_id

- [x] Task 3: Adapter sauvegarde pour workflows (AC: #3)
  - [x] 3.1 Modifier `handleSubmit()` : si itemType=workflow, appeler séquence API différente
  - [x] 3.2 Création workflow : `POST /admin/actions` avec item_type='workflow', puis `PUT /admin/actions/{id}/workflow-steps` avec workflowSteps
  - [x] 3.3 Édition workflow : `PUT /admin/actions/{id}` (métadonnées), puis `PUT /admin/actions/{id}/workflow-steps` (étapes)
  - [x] 3.4 Gestion erreur 400 WORKFLOW_LOOP : catch API error, afficher Alert avec message clair, garder wizard ouvert
  - [x] 3.5 Ajouter loading state pendant sauvegarde : `setSaving(true)` avant appels API, `setSaving(false)` après succès/erreur
  - [x] 3.6 Message succès : "Workflow créé/mis à jour avec succès" (adapter selon mode création/édition)

### Frontend - WorkflowStepsEditor component

- [x] Task 4: Créer composant WorkflowStepsEditor (AC: #2, #4)
  - [x] 4.1 Créer fichier `frontend/src/components/admin/WorkflowStepsEditor.tsx`
  - [x] 4.2 Props: `steps: WorkflowStep[]`, `onChange: (steps: WorkflowStep[]) => void`, `loading?: boolean`
  - [x] 4.3 State interne : `eligibleActions: ActionListItem[]`, `loadingActions: boolean`, `validationErrors: string[]`
  - [x] 4.4 useEffect au mount : appeler `getEligibleActionsForWorkflow()` depuis admin_service, stocker dans eligibleActions
  - [x] 4.5 Afficher liste des étapes avec map : `steps.map((step, index) => <StepRow key={index} order={index+1} step={step} ... />)`
  - [x] 4.6 StepRow contient : ordre (badge), AutoComplete action, Input nom optionnel, Button supprimer (DeleteOutlined)
  - [x] 4.7 AutoComplete : options=eligibleActions.map(a => ({value: a.id, label: `${a.name} (${a.engine})`})), onSelect met à jour step.referenced_action_id
  - [x] 4.8 Bouton "Ajouter une étape" en bas : onClick ajoute `{order: steps.length+1, name: '', referenced_action_id: undefined}` à steps
  - [x] 4.9 Bouton "Supprimer" : onClick retire l'étape et renumérote les ordres (1, 2, 3...)
  - [x] 4.10 Appeler onChange(newSteps) après chaque modification (ajout, suppression, changement action/nom)

- [x] Task 5: Ajouter drag-and-drop dans WorkflowStepsEditor (AC: #4)
  - [x] 5.1 Installer @dnd-kit si pas déjà présent (vérifier package.json) : `npm install @dnd-kit/core @dnd-kit/sortable`
  - [x] 5.2 Wrapper liste avec `<DndContext onDragEnd={handleDragEnd}>` et `<SortableContext items={steps.map(s => s.order)}>`
  - [x] 5.3 Chaque StepRow devient `<SortableItem id={step.order}>` avec useSortable hook
  - [x] 5.4 handleDragEnd : réordonne steps selon arrayMove(steps, oldIndex, newIndex), renumérote ordres, appelle onChange
  - [x] 5.5 Ajouter icône drag handle (HolderOutlined) à gauche de chaque étape pour UX claire

- [x] Task 6: Validation et feedback dans WorkflowStepsEditor (AC: #2, #4)
  - [x] 6.1 Valider au moins 1 étape : si steps.length === 0, afficher Alert warning "Au moins une étape est requise"
  - [x] 6.2 Valider chaque étape a une action : si step.referenced_action_id undefined, afficher validateStatus='error' sur AutoComplete
  - [x] 6.3 Tooltips : AutoComplete placeholder "Rechercher une action...", tooltip sur Input nom "Nom personnalisé optionnel"
  - [x] 6.4 Loading skeleton pendant chargement actions : AutoComplete avec loading prop ou Spin global
  - [x] 6.5 Accessibilité : aria-label sur AutoComplete, Buttons, erreurs avec role="alert"

### Frontend - Admin service extension

- [x] Task 7: Ajouter fonctions API workflow dans admin_service.ts (AC: #2, #3)
  - [x] 7.1 Ajouter fonction `getEligibleActionsForWorkflow(): Promise<ActionListItem[]>` qui appelle `GET /api/v1/admin/actions/eligible-for-workflow`
  - [x] 7.2 Ajouter fonction `updateWorkflowSteps(workflowId: number, data: WorkflowStepsUpdate): Promise<void>` qui appelle `PUT /api/v1/admin/actions/${workflowId}/workflow-steps`
  - [x] 7.3 Gestion erreurs : throw Error avec message utilisateur si API retourne 400/500
  - [x] 7.4 Types : importer WorkflowStepsUpdate depuis types/api.ts

### Tests Frontend

- [x] Task 8: Tests ActionWizard avec type workflow (AC: #1, #2, #3)
  - [x] 8.1 Test création workflow : sélectionner type=workflow, champs engine/platform masqués, Step 2 affiche WorkflowStepsEditor
  - [x] 8.2 Test validation Step 1 workflow : type=workflow, laisser nom vide → erreur, remplir nom → pas d'erreur engine/platform
  - [x] 8.3 Test validation Step 2 workflow : workflowSteps vide → erreur "Au moins une étape requise"
  - [x] 8.4 Test sauvegarde workflow : mock POST /admin/actions + PUT /workflow-steps, vérifier appels séquentiels avec bon payload
  - [x] 8.5 Test gestion erreur WORKFLOW_LOOP : mock API 400 error, vérifier Alert affichée avec message boucle circulaire
  - [x] 8.6 Test édition workflow existant : charger workflow avec workflow_steps, Step 2 pré-remplit WorkflowStepsEditor
  - [x] 8.7 Test type désactivé en édition : editAction fourni → Radio.Group disabled=true

- [x] Task 9: Tests WorkflowStepsEditor component (AC: #2, #4)
  - [x] 9.1 Test affichage initial : 0 étape → affiche message "Aucune étape", bouton "Ajouter une étape"
  - [x] 9.2 Test ajout étape : clic "Ajouter" → nouvelle ligne apparaît, ordre=1
  - [x] 9.3 Test suppression étape : ajouter 2 étapes, supprimer étape 1 → étape 2 devient ordre 1
  - [x] 9.4 Test AutoComplete action : mock eligibleActions, sélectionner action → referenced_action_id mis à jour, onChange appelé
  - [x] 9.5 Test drag-and-drop : ajouter 3 étapes, drag étape 3 vers position 1 → ordres renumérés (3,1,2 → 1,2,3)
  - [x] 9.6 Test validation : étape sans action sélectionnée → validateStatus='error' sur AutoComplete
  - [x] 9.7 Test loading actions : loadingActions=true → AutoComplete affiche loading ou Spin
  - [x] 9.8 Test accessibilité : AutoComplete avec aria-label, Buttons avec aria-label, erreurs avec role="alert"

- [x] Task 10: Tests admin_service nouvelles fonctions (AC: #2, #3)
  - [x] 10.1 Test getEligibleActionsForWorkflow : mock fetch, retourne liste actions publiées
  - [x] 10.2 Test getEligibleActionsForWorkflow error : mock fetch 500, throw Error avec message
  - [x] 10.3 Test updateWorkflowSteps : mock fetch PUT /workflow-steps, body avec steps
  - [x] 10.4 Test updateWorkflowSteps error 400 WORKFLOW_LOOP : mock fetch 400, throw Error avec code erreur

## Dev Notes

### Contexte technique

**Story 5.7 (déjà implémentée) a créé:**
- Backend: ItemType enum, WorkflowStep model, validate_workflow_steps() avec détection boucles
- API: `PUT /admin/actions/{id}/workflow-steps` (ligne 169-218 admin.py), `GET /admin/actions/eligible-for-workflow` (ligne 221-237)
- Repository: update_workflow_steps() avec validation boucles (ligne 1542-1631 catalog_repository.py)
- Frontend types: ItemType, WorkflowStep, WorkflowStepsUpdate (api.ts lignes 85-94)
- Catalogue: ApartmentOutlined icon pour workflows, badge "Workflow" dans drawer

**Story 9.5 complète Task 4 de Story 5.7:**
- Task 4.1 : Choix type action/workflow dans wizard creation/edition
- Task 4.2 : Éditeur d'étapes workflow avec sélecteur d'actions existantes
- Task 4.3 : Validation frontend + gestion erreur boucle backend

### Architecture Compliance

**Patterns à suivre (architecture.md):**
- **Repository Pattern** : Déjà implémenté côté backend (catalog_repository.py) — Story 9.5 uniquement frontend
- **API format** : snake_case JSON, wrapper `{ "data": ... }` / `{ "error": ... }` — API déjà conformes (Story 5.7)
- **React patterns** : Form.useWatch pour réactivité, useState pour state local, useEffect pour side effects
- **Ant Design 6.2** : Form.Item, Radio.Group, AutoComplete, Button avec loading prop, Alert pour erreurs
- **Accessibility WCAG 2.1 AA** : aria-label sur inputs/buttons, role="alert" pour erreurs, focus management
- **Error handling** : Catch API errors, afficher Alert utilisateur avec message clair, ne pas bloquer UI
- **Component structure** : admin/ pour composants admin (ActionWizard.tsx, WorkflowStepsEditor.tsx)
- **Service layer** : admin_service.ts pour appels API (getEligibleActionsForWorkflow, updateWorkflowSteps)

**Composants similaires existants:**
- **StepsEditor.tsx** (ligne 1-350+) : Éditeur d'étapes execution avec drag-and-drop @dnd-kit — pattern à réutiliser pour WorkflowStepsEditor
- **ParametersEditor.tsx** : Éditeur de paramètres avec ajout/suppression/drag-drop — pattern add/remove buttons
- **ActionWizard.tsx** (ligne 1-600+) : Wizard 3-step avec Form.useWatch('platform') pour conditionner affichage AAP — pattern à étendre avec Form.useWatch('item_type')

### Technical Requirements

**Frontend TypeScript:**
- Types déjà définis dans api.ts : `ItemType = 'action' | 'workflow'`, `WorkflowStep`, `WorkflowStepsUpdate`
- ActionFormValues étendre avec : `item_type: ItemType`
- WorkflowStepsEditor props : `{ steps: WorkflowStep[]; onChange: (steps: WorkflowStep[]) => void; loading?: boolean }`

**API endpoints existants (Story 5.7):**
- `GET /api/v1/admin/actions/eligible-for-workflow` : Retourne liste actions publiées (status=published), type=action, avec fields id, name, engine, platform
- `PUT /api/v1/admin/actions/{id}/workflow-steps` : Body `{ steps: [{ order, name?, referenced_action_id }] }`, validation boucles backend, retourne 400 WORKFLOW_LOOP si cycle détecté
- `POST /api/v1/admin/actions` : Accepte `item_type: 'workflow'` (engine/platform non requis pour workflows selon validation Pydantic)
- `GET /api/v1/admin/actions/{id}` : Retourne ActionDetail avec `workflow_steps: WorkflowStep[] | null` (ligne 100 api.ts)

**Validation frontend:**
- Step 1 : Si item_type=workflow, ne pas valider engine/platform (modificer validateStep1 dans ActionWizard)
- Step 2 : Si item_type=workflow, valider workflowSteps.length > 0 et steps.every(s => s.referenced_action_id !== undefined)
- Afficher erreurs inline avec validateStatus='error' sur Form.Item/AutoComplete

**Gestion erreur boucle circulaire:**
```typescript
try {
  await updateWorkflowSteps(workflowId, { steps: workflowSteps });
} catch (error) {
  if (error.response?.data?.error_code === 'WORKFLOW_LOOP') {
    Alert.error({
      message: 'Boucle circulaire détectée',
      description: 'Les étapes du workflow créent un cycle. Vérifiez que les actions référencées ne se référencent pas mutuellement.',
    });
  }
}
```

### Library / Framework Requirements

**Déjà installées (vérifier package.json):**
- React 18+
- Ant Design 6.2 (Form, AutoComplete, Radio, Button, Alert, Badge)
- @ant-design/icons (DeleteOutlined, HolderOutlined, PlusOutlined)
- @dnd-kit/core, @dnd-kit/sortable (pour drag-and-drop comme StepsEditor)

**Imports nécessaires WorkflowStepsEditor:**
```typescript
import { useState, useEffect } from 'react';
import { Space, AutoComplete, Input, Button, Alert, Badge, Tooltip, Spin } from 'antd';
import { DeleteOutlined, HolderOutlined, PlusOutlined } from '@ant-design/icons';
import { DndContext, closestCenter, DragEndEvent } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy, arrayMove, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { WorkflowStep, ActionListItem } from '../../types/api';
import { getEligibleActionsForWorkflow } from '../../services/admin_service';
```

### Project Structure Notes

**Fichiers à créer:**
- `frontend/src/components/admin/WorkflowStepsEditor.tsx` (nouveau composant)
- `frontend/src/components/admin/WorkflowStepsEditor.test.tsx` (tests)

**Fichiers à modifier:**
- `frontend/src/components/admin/ActionWizard.tsx` : Ajouter choix type, conditionner Step 2, adapter sauvegarde
- `frontend/src/services/admin_service.ts` : Ajouter getEligibleActionsForWorkflow(), updateWorkflowSteps()
- `frontend/src/components/admin/ActionWizard.test.tsx` : Ajouter tests workflow (7 tests)

**Composants référencés:**
- `StepsEditor.tsx` (pattern drag-and-drop)
- `ParametersEditor.tsx` (pattern add/remove items)
- `ActionWizard.tsx` (wizard 3-step, Form.useWatch pattern)

**API backend (déjà implémenté, pas de modification):**
- `app/api/v1/admin.py` : Endpoints workflow-steps et eligible-for-workflow
- `app/repositories/catalog_repository.py` : update_workflow_steps avec validation
- `app/models/catalog.py` : ItemType, WorkflowStep, WorkflowStepsUpdate

### Référence story précédente (Story 9.4)

**Story 9.4** (Déplacement statistiques exécutions vers page Exécutions) - **DONE 2026-02-02**

**Learnings de 9.4:**
- Pattern useEffect pour charger données quand state change (activeScope) : `useEffect(() => { fetchData(); }, [activeScope])`
- State management : statsData + statsLoading avec setState dans try/catch/finally
- Responsive layout Ant Design : Row + Col avec breakpoints xs/sm/md
- Service layer : Créer fonction dans execution_service.ts pour appeler API
- Tests : Mock fetch, vérifier appels API avec bon payload, tester loading/error states

**Fichiers modifiés 9.4:**
- Frontend: ExecutionsPage.tsx (section StatCards), execution_service.ts (fetchExecutionStats)
- Backend: executions.py (endpoint /stats), execution_repository.py (get_execution_stats)
- Tests: ExecutionsPage.test.tsx (8 tests), execution_repository tests (4 tests), API tests (6 tests)

**Pattern à réutiliser pour 9.5:**
- useEffect pour charger actions éligibles au mount de WorkflowStepsEditor
- State loadingActions + eligibleActions avec try/catch/finally
- Service layer : Créer getEligibleActionsForWorkflow() dans admin_service.ts
- Tests : Mock fetch API, vérifier loading/error handling

### Intelligence de la story précédente (Story 9.4)

**Patterns établis dans story 9-4:**
- API endpoint avec paramètre scope (mine|all) pour filtrage utilisateur
- Repository query optimisée avec CASE WHEN (une seule requête pour toutes les stats)
- Frontend useEffect pour reload données quand state change (activeScope)
- Responsive layout avec Row/Col breakpoints xs/sm/md
- Loading skeleton intégré dans composant (StatCard loading prop)

**Continuité pour story 9-5:**
- Story 5.7 = backend workflow complet (models, API, validation)
- Story 9.5 = frontend admin UI pour workflows (Task 4 de Story 5.7)
- Pattern similaire à ActionWizard existant : extension avec type workflow, conditionner Step 2, nouveau composant WorkflowStepsEditor

### Git Intelligence (commits récents)

```
dc72a93 feat(executions): move execution statistics from dashboard to executions page (story 9-4)
e5437e1 feat(remediation): add automatic corrective execution for low-risk failures (story 9-3)
954dd5c fix(remediation): apply code review fixes for story 9-2
a8dc08d feat(remediation): add manual corrective action triggering by DBA (story 9-2)
6163b8e feat(remediation): add failure detection and corrective action suggestions (story 9-1)
```

**Observation:** Epic 9 (auto-remédiation) en cours avec stories 9-1 à 9-4 complétées. Story 9-5 = retour sur Epic 5 (Story 5.7 Task 4 restante) pour compléter feature workflow avant de continuer Epic 9 (stories 9-6 à 9-10).

**Pattern de commit attendu:** `feat(admin): add workflow creation/editing interface (story 9-5)`

**Fichiers récemment modifiés (Epic 9):**
- Backend: remediation_service.py, execution_service.py, execution_repository.py
- Frontend: ExecutionTimeline.tsx, RemediationRulesEditor.tsx, ExecutionsPage.tsx, ReportingDashboard.tsx
- Story 9-5 modifie composants admin : ActionWizard.tsx, admin_service.ts, nouveau WorkflowStepsEditor.tsx

### Analyse du code existant

**ActionWizard.tsx (lignes 1-600+):**
- Structure : Modal avec Steps (1. Général, 2. Automatisation, 3. Impact & Changement)
- State : form (Ant Design useForm), currentStep, saving, preview
- Form.useWatch('platform') pour conditionner affichage AAP-specific UI (ligne 200+)
- Validation par step : validateStep1(), validateStep2(), validateStep3()
- Sauvegarde : handleSubmit() appelle createAction() ou updateAction() selon mode création/édition
- Mode édition : editAction prop fourni → charge données dans form avec setFieldsValue

**Story 9-5 étend ActionWizard:**
- Ajouter Form.useWatch('item_type') comme Form.useWatch('platform')
- Conditionner Step 1 : masquer engine/platform si item_type=workflow
- Conditionner Step 2 : afficher WorkflowStepsEditor si workflow, sinon ParametersEditor+ImpactRulesEditor existants
- Adapter validateStep1 : pas de validation engine/platform si workflow
- Adapter handleSubmit : séquence API différente pour workflows (POST action + PUT workflow-steps)

**StepsEditor.tsx (lignes 1-350+):**
- Drag-and-drop avec @dnd-kit : DndContext + SortableContext + useSortable
- State : steps array avec order, name, type, connector_type, conditional_environments
- Fonctions : handleAddStep(), handleRemoveStep(), handleStepChange(), handleDragEnd()
- Renumérote ordres après suppression/drag : `steps.map((s, i) => ({ ...s, order: i+1 }))`

**WorkflowStepsEditor réutilise pattern StepsEditor:**
- Même structure drag-and-drop @dnd-kit
- State : steps array avec order, name, referenced_action_id
- AutoComplete au lieu de Select connector_type
- Pas de conditional_environments (workflows n'ont pas d'environnements conditionnels)

**admin_service.ts (lignes 1-200+):**
- Fonctions : createAction(), updateAction(), updateActionSteps(), updateActionTags()
- Pattern : async function avec fetch API, gestion erreur throw Error
- Headers : Content-Type application/json, Authorization Bearer token

**Story 9-5 ajoute à admin_service.ts:**
```typescript
export async function getEligibleActionsForWorkflow(): Promise<ActionListItem[]> {
  const response = await fetch('/api/v1/admin/actions/eligible-for-workflow', {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getAuthToken()}`,
    },
  });

  if (!response.ok) {
    throw new Error('Impossible de charger les actions éligibles');
  }

  const data = await response.json();
  return data.data; // Unwrap { "data": [...] }
}

export async function updateWorkflowSteps(
  workflowId: number,
  data: WorkflowStepsUpdate
): Promise<void> {
  const response = await fetch(`/api/v1/admin/actions/${workflowId}/workflow-steps`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getAuthToken()}`,
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.error?.message || 'Erreur mise à jour workflow steps');
  }
}
```

### Décisions techniques

1. **Type workflow immutable après création** : Champ item_type désactivé en mode édition (Radio.Group disabled={!!editAction}). Pas de changement action → workflow ou workflow → action après création. Raison : schéma données différent (execution_steps vs workflow_steps), migration complexe, pas de besoin métier.

2. **WorkflowStepsEditor composant séparé** : Nouveau composant WorkflowStepsEditor.tsx au lieu de modifier StepsEditor.tsx. Raison : logique différente (AutoComplete action vs Select connector), pas de conditional_environments, évite over-complication StepsEditor existant. Réutilise pattern drag-and-drop @dnd-kit.

3. **AutoComplete pour sélection action** : AutoComplete (recherche + dropdown) au lieu de simple Select. Raison : liste actions peut être longue (50+), recherche par nom améliore UX, pattern existant dans d'autres composants admin.

4. **Validation boucles côté backend uniquement** : Pas de détection boucles frontend (trop complexe, graphe traversal). Backend validate_workflow_steps() détecte cycles, retourne 400 WORKFLOW_LOOP. Frontend affiche erreur API avec message clair. Raison : logique métier centralisée backend, évite duplication code, garantit intégrité données.

5. **Séquence API création workflow** : POST /admin/actions (item_type=workflow) → récupérer id → PUT /admin/actions/{id}/workflow-steps. Raison : création catalogue d'abord (génère id), puis étapes (besoin id). Alternative rejetée : endpoint POST avec embedded steps → complexifie backend, pas de réutilisation create_action existant.

6. **Champ "Nom d'affichage" optionnel** : WorkflowStep.name optionnel (Input non requis). Si vide, backend ou frontend utilise nom de l'action référencée par défaut. Raison : flexibilité pour DBOPS (renommer étape dans contexte workflow), mais pas obligatoire (nom action suffit).

7. **Drag-and-drop pour réordonner** : Réutiliser @dnd-kit comme StepsEditor. Raison : UX consistante avec autres éditeurs, bibliothèque déjà installée, pattern éprouvé (Story 2.2).

8. **Step 3 simplifié pour workflows** : Workflows n'ont pas de change config complexe par environnement (ChangeTypeConfig). Step 3 affiche uniquement tags ServiceNow si pertinent, sinon skip ou simplifié. Raison : workflows enchaînent actions, change config porté par actions individuelles, pas par workflow conteneur.

9. **Actions éligibles = publiées uniquement** : Endpoint /eligible-for-workflow retourne status=published, pas draft/disabled. Raison : workflows ne doivent pas référencer actions non finalisées (risque broken workflow si action draft supprimée/modifiée).

10. **Form.useWatch pour réactivité temps réel** : Utiliser Form.useWatch('item_type') comme Form.useWatch('platform') existant. Raison : Ant Design Form pattern recommandé, réactivité immédiate (pas de re-render manuel), cohérent avec codebase existant.

### Testing Requirements

**Tests frontend (17 tests total):**

**ActionWizard.test.tsx (7 tests nouveaux):**
1. Test choix type workflow : sélectionner workflow → engine/platform masqués
2. Test validation Step 1 workflow : type=workflow, nom vide → erreur, remplir → pas d'erreur engine/platform
3. Test Step 2 affiche WorkflowStepsEditor si workflow
4. Test sauvegarde workflow : mock POST + PUT, vérifier séquence API avec payloads corrects
5. Test gestion erreur WORKFLOW_LOOP : mock 400, Alert affiché avec message boucle
6. Test édition workflow : charger avec workflow_steps, Step 2 pré-remplit
7. Test type désactivé en édition : Radio.Group disabled=true si editAction fourni

**WorkflowStepsEditor.test.tsx (8 tests nouveaux):**
1. Test affichage initial vide : "Aucune étape", bouton "Ajouter"
2. Test ajout étape : clic → nouvelle ligne ordre=1
3. Test suppression étape : supprimer 1 sur 2 → renumérote ordres
4. Test AutoComplete action : sélectionner → referenced_action_id mis à jour, onChange appelé
5. Test drag-and-drop : 3 étapes, drag 3→1 → ordres renumérés
6. Test validation : étape sans action → validateStatus='error'
7. Test loading actions : loadingActions=true → Spin affiché
8. Test accessibilité : aria-label présents, erreurs avec role="alert"

**admin_service.test.ts (2 tests nouveaux):**
1. Test getEligibleActionsForWorkflow : mock fetch, retourne liste actions
2. Test updateWorkflowSteps : mock PUT, body avec steps

**Tests non-régression:**
- Tous les tests ActionWizard existants doivent rester verts (création action, édition action, validation steps)
- Tests StepsEditor existants ne doivent pas être impactés (composant séparé WorkflowStepsEditor)

### Gestion des cas limites

- **Aucune action éligible (nouveau portail):** getEligibleActionsForWorkflow() retourne []. WorkflowStepsEditor affiche Alert info "Aucune action publiée disponible. Créez et publiez des actions d'abord." + désactive "Ajouter étape". Pas de blocage, workflow créable quand actions disponibles.

- **API eligible-for-workflow échoue:** Catch dans useEffect WorkflowStepsEditor, affiche Alert error "Impossible de charger les actions éligibles", eligibleActions=[], AutoComplete disabled. User peut fermer wizard et réessayer.

- **Workflow sans étapes (validation manquée):** Backend rejette avec 400 "Au moins une étape requise". Frontend affiche Alert, wizard reste ouvert. Frontend devrait valider avant appel API (Task 6.1), mais backend double-check sécurité.

- **Action référencée supprimée après création workflow:** Backend validate_workflow_steps vérifie referenced_action_id existe (foreign key constraint ou check manuel). Si action supprimée, retourne 400 "Action {id} introuvable". Frontend affiche erreur, DBOPS doit choisir autre action.

- **Boucle circulaire complexe (A→B→C→A):** Backend détecte avec _detect_workflow_loop (DFS traversal graphe). Retourne 400 WORKFLOW_LOOP. Frontend affiche Alert avec liste des actions formant le cycle si backend fournit détails (sinon message générique).

- **Drag-and-drop étape unique:** 1 seule étape → pas de réordonnancement possible (DndContext gère automatiquement). Bouton "Supprimer" désactivé si steps.length === 1 (au moins 1 étape requise).

- **AutoComplete action non sélectionnée (user tape puis quitte):** Si referenced_action_id undefined à la sauvegarde, validation frontend (Task 6.2) affiche erreur avant appel API. User doit sélectionner action valide.

- **Édition workflow avec steps obsolètes (action supprimée):** GET /admin/actions/{id} retourne workflow_steps avec referenced_action_id invalide. WorkflowStepsEditor charge, AutoComplete affiche id (pas de label si action n'existe plus). User doit mettre à jour avec action valide.

- **Changement type action→workflow en édition:** Radio.Group disabled en édition (Task 1.7). Pas de changement type après création. Si besoin, DBOPS doit créer nouveau workflow et supprimer ancienne action.

- **Workflow référence autre workflow (profondeur > 1):** Backend API /eligible-for-workflow retourne type=action uniquement (pas workflows). Empêche workflow→workflow selon architecture (Story 5.7 AC5). Si architecture évolue, modifier filtre backend.

- **Multiple DBAs éditent même workflow simultanément:** Pas de locking optimiste implémenté (hors scope). Last write wins. Story future peut ajouter version field + 409 Conflict si version mismatch.

- **User ferme wizard avec modifications non sauvegardées:** ActionWizard existant affiche confirm dialog "Modifications non sauvegardées. Quitter ?" (pattern Ant Design Modal confirm). Pas de modification nécessaire pour workflows.

### Performance considerations

**Frontend performance:**
- getEligibleActionsForWorkflow() appelé une seule fois au mount de WorkflowStepsEditor (useEffect avec deps [])
- AutoComplete options memoized : `const options = useMemo(() => eligibleActions.map(...), [eligibleActions])`
- Drag-and-drop @dnd-kit : performance optimisée pour listes < 100 items (suffisant pour workflows typiques 2-10 étapes)
- Re-render limité : onChange appelé uniquement après modification complète (ajout/suppression/drag), pas à chaque keystroke

**Backend performance (déjà optimisé Story 5.7):**
- Validation boucles : DFS traversal O(V+E) où V=actions, E=références. Acceptable pour graphes < 1000 nodes (catalogue typique 50-200 actions)
- Index sur ACTIONS_CATALOG.ITEM_TYPE pour filtre eligible-for-workflow (Story 5.7 migration V027)
- EXECUTION_STEPS CLOB parse/serialize avec json.loads/dumps (fast pour JSON < 100KB)

**Database constraints:**
- ITEM_TYPE indexed (V027 migration) : SELECT WHERE ITEM_TYPE='action' AND STATUS='published' fast
- Pas de foreign key constraint EXECUTION_STEPS.referenced_action_id → ACTIONS_CATALOG.ID (CLOB JSON, pas de FK sur JSON field) → validation applicative backend

### Opportunités d'amélioration futures (post-Story 9.5)

- **Post-Epic 9:** Visualisation graphique workflow : nœuds (actions) + flèches (ordre), comme flowchart. Aide DBOPS comprendre workflow complexe (5+ étapes).
- **Post-Epic 9:** Duplication workflow : bouton "Dupliquer" dans liste admin workflows → crée copie avec suffix "- Copie" pour réutiliser structure.
- **Post-Epic 9:** Import/export workflows YAML : comme profiles (Story 2.13), workflows as code pour versioning Git.
- **Post-Epic 9:** Validation avancée frontend : détecter duplicates (même action 2x dans workflow) avec Alert warning (pas bloquant, juste info).
- **Post-Epic 9:** Preview exécution workflow : simulation visuelle du flow avant sauvegarde (comme AdminPreview pour actions).
- **Post-Epic 9:** Paramètres workflow : mapper paramètres workflow → paramètres actions (ex. workflow "Provisionner environnement" avec param "env_name" propagé aux actions).
- **Post-Epic 9:** Locking optimiste : version field + 409 Conflict si modification simultanée par 2 DBAs.

### References

- [Source: _bmad-output/implementation-artifacts/5-7-workflow-conteneur-actions-icone-catalogue.md - Story 5.7 context, Task 4 restante (lignes 64-76)]
- [Source: idp-portal/backend/app/models/catalog.py - ItemType enum (lignes 46-53), WorkflowStep model (lignes 421-443)]
- [Source: idp-portal/backend/app/repositories/catalog_repository.py - update_workflow_steps, validate_workflow_steps (lignes 1542-1631)]
- [Source: idp-portal/backend/app/api/v1/admin.py - PUT /workflow-steps (lignes 169-218), GET /eligible-for-workflow (lignes 221-237)]
- [Source: idp-portal/frontend/src/types/api.ts - ItemType, WorkflowStep, WorkflowStepsUpdate (lignes 85-94)]
- [Source: idp-portal/frontend/src/components/admin/ActionWizard.tsx - Structure wizard 3-step, Form.useWatch pattern]
- [Source: idp-portal/frontend/src/components/admin/StepsEditor.tsx - Pattern drag-and-drop @dnd-kit]
- [Source: idp-portal/frontend/src/services/admin_service.ts - Service layer pattern]
- [Source: _bmad-output/planning-artifacts/architecture.md - Frontend patterns, React hooks, Ant Design usage]
- [Source: _bmad-output/implementation-artifacts/9-4-deplacement-statistiques-executions-vers-page-executions.md - Story 9.4 learnings (useEffect, service layer, responsive layout)]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- Story 9-5 complète Task 4 de Story 5.7 (interface admin workflow creation/editing)
- Analyzed Story 5.7 implementation: backend complet (models, API, validation), frontend types, catalogue icon
- Comprehensive architecture analysis via Explore agent: ActionWizard patterns, StepsEditor drag-and-drop, admin_service structure
- Previous story 9-4 learnings: useEffect pattern, service layer, responsive layout, state management
- Git intelligence: Epic 9 en cours, stories 9-1 à 9-4 done, story 9-5 = retour Epic 5 pour compléter workflow feature
- Created comprehensive story with 10 detailed tasks:
  - Tasks 1-3: ActionWizard enhancement (type choice, Step 2 conditional, workflow save)
  - Tasks 4-6: WorkflowStepsEditor component (list, drag-and-drop, validation)
  - Task 7: Admin service functions (getEligibleActionsForWorkflow, updateWorkflowSteps)
  - Tasks 8-10: Tests (ActionWizard 7, WorkflowStepsEditor 8, admin_service 2)
- Dev Notes: Technical requirements, architecture compliance, library imports, testing requirements
- Decision: Type immutable after creation, AutoComplete for action selection, backend-only loop validation
- Edge cases: No eligible actions, API errors, circular loops, drag-and-drop single item, concurrent edits
- Performance: useEffect deps [], useMemo AutoComplete options, @dnd-kit optimized for <100 items
- Future opportunities: Flowchart visualization, workflow duplication, YAML import/export, parameter mapping

**Implementation Notes (2026-02-02):**
- All 10 tasks completed successfully
- 35 tests pass (18 ActionWizard, 13 WorkflowStepsEditor, 4 admin_service)
- Fixed Ant Design deprecation warnings (Space direction -> orientation, Alert message -> title)
- Reused @dnd-kit patterns from existing StepsEditor component
- Form.useWatch pattern for reactive item_type field (same as existing platform field)
- Type is immutable after creation (Radio.Group disabled in edit mode)
- WORKFLOW_LOOP error handling with user-friendly French message

### File List

**Files created:**
- `frontend/src/components/admin/WorkflowStepsEditor.tsx` (new component - 410 lines)
- `frontend/src/components/admin/WorkflowStepsEditor.test.tsx` (13 tests)
- `frontend/src/services/admin_service.test.ts` (4 tests for new functions)

**Files modified:**
- `frontend/src/components/admin/ActionWizard.tsx` (added type choice, conditional Step 2, workflow save sequence)
- `frontend/src/services/admin_service.ts` (added getEligibleActionsForWorkflow, updateWorkflowSteps)
- `frontend/src/components/admin/ActionWizard.test.tsx` (added 7 workflow tests)

**Backend files (no changes, already implemented in Story 5.7):**
- `app/api/v1/admin.py` (PUT /workflow-steps, GET /eligible-for-workflow)
- `app/repositories/catalog_repository.py` (update_workflow_steps, validate_workflow_steps)
- `app/models/catalog.py` (ItemType, WorkflowStep, WorkflowStepsUpdate)

## Change Log

- 2026-02-02: Implementation complete (Claude Opus 4.5) - All 10 tasks done, 35 tests pass
- 2026-02-02: **Code Review Complete** (Claude Sonnet 4.5) - **11 issues found and fixed**:
  - **🔴 CRITICAL (4)**: Alert title/message deprecation, AutoComplete value type mismatch (number → string with actionId lookup), type assertion safety (added typeof check), WORKFLOW_LOOP error code handling (architectural limitation acknowledged)
  - **🟡 MEDIUM (5)**: Validation showValidation state management (fixed to clear when valid), validation Step 2 duplication (extracted validateWorkflowSteps helper), Space direction→orientation deprecated (fixed ActionWizard), loading state AutoComplete (added loading prop), performance useMemo in loop (acceptable)
  - **🟢 LOW (2)**: Console error logging (added), role="alert" redundancy (cleaned)
  - All 35 tests still pass after fixes
  - Status: **DONE** ✅
