# Story 26.6: Refactoriser CalendarPage.tsx (896 LOC)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur,
je veux extraire le modal d'édition et la logique de transformation d'événements de CalendarPage,
afin de séparer la logique métier du composant page.

## Context

**Source :** Epic 26, Section 4.4 et 4.9 du code-quality-assessment (6 février 2026)

Le fichier `CalendarPage.tsx` contient actuellement **896 lignes** et présente une complexité importante due à la gestion de plusieurs modaux, la transformation d'événements FullCalendar, et la gestion d'état d'édition/annulation.

### Problèmes identifiés

1. **Monolithe avec multiples responsabilités**
   - 896 LOC dans un seul fichier
   - Gestion calendrier + filtres + modaux d'édition/annulation + popover détails + transformation données
   - 19 useState hooks dans le composant principal
   - Multiples préoccupations mélangées (UI, logique métier, API)

2. **Modal d'édition complexe (107 LOC de logique)**
   - `handleSubmitEdit()` : 84 LOC avec switch statement massif pour gérer les patterns récurrents
   - Validation complexe des dates, patterns, targets
   - Gestion d'erreurs API avec mapping vers les champs de formulaire
   - Initialisation formulaire avec logique conditionnelle (lignes 505-521)

3. **Modal d'annulation avec logique métier (39 LOC)**
   - `handleConfirmCancel()` : 35 LOC avec gestion d'erreurs spécifiques
   - Mapping d'erreurs API vers notifications utilisateur (3 types d'erreurs)

4. **Logique de transformation d'événements (76 LOC d'utilitaires)**
   - `toUtcIso()`, `mapToCalendarEvent()`, `describePatternType()`, `getDisplayParameters()`
   - Logique de parsing de dates complexe (UTC vs local, avec/sans heure)
   - Mapping couleurs par environnement
   - Fonctions pures mais noyées dans le fichier principal

5. **Composant EventDetailsPopover massif (160 LOC)**
   - Déjà extrait comme fonction exportée (ligne 171-330)
   - Mais toujours dans le fichier principal
   - Candidat pour fichier dédié `/components/calendar/EventDetailsPopover.tsx`

6. **État calendrier distribué (27 LOC de handlers)**
   - `handleEventClick()`, `handleDatesSet()`, `handleViewChange()`, `closePopover()`
   - État UI (popover position, calendar view, selected event)
   - Candidat pour hook `useCalendarState`

### Contexte technique

**Fichier actuel :** `idp-portal/frontend/src/pages/CalendarPage.tsx` (896 LOC)

**Stories liées :**
- Story 13.6 : Création du calendrier avec filtres
- Story 13.8 : Annulation + édition scheduled executions
- Story 26.5 : Pattern de refactoring WorkflowBuilderCanvas (995 → 487 LOC, -51%)

**Pattern établi dans le codebase :**
- Story 26.4 : ExecutionsPage refactorisé de 1023 → 298 LOC en extrayant colonnes/hooks/composants
- Story 26.5 : WorkflowBuilderCanvas refactorisé de 995 → 487 LOC en extrayant utils/hooks/composants
- Story 22.9 : AdminPage refactorisé de 845 → 75 LOC en extrayant 6 panels

---

## Acceptance Criteria

### AC1: Extraction des utilitaires de transformation → `calendarEventUtils.ts`

**Given** CalendarPage contient 76 LOC d'utilitaires de transformation (lignes 44-116 + 153-158)
**When** les utilitaires sont extraits
**Then** :

- Un fichier `frontend/src/utils/calendarEventUtils.ts` est créé
- Les fonctions suivantes sont extraites :
  ```typescript
  export const ENV_COLORS: Record<ExecutionEnvironment, string>
  export const ENV_LABELS: Record<ExecutionEnvironment, string>
  export interface CalendarEvent { ... }
  export function toUtcIso(dateStr: string): string
  export function mapToCalendarEvent(exec: ScheduledExecutionListItem): CalendarEvent
  export function describePatternType(exec: ScheduledExecutionListItem): string
  export function getDisplayParameters(parameters: Record<string, unknown> | null): Record<string, unknown>
  ```
- CalendarPage importe et utilise ces fonctions :
  ```typescript
  import {
    ENV_COLORS,
    ENV_LABELS,
    mapToCalendarEvent,
    describePatternType,
    getDisplayParameters,
    type CalendarEvent,
  } from '../utils/calendarEventUtils';
  ```
- Réduction CalendarPage : -76 LOC (constants + fonctions)

**Rationale :** Séparation des préoccupations — transformation de données réutilisable dans d'autres contextes (tests, export)

---

### AC2: Extraction du hook de gestion d'annulation → `useCancelExecution()`

**Given** CalendarPage contient 39 LOC de logique d'annulation (lignes 492-530)
**When** la logique est extraite dans un hook custom
**Then** :

- Un fichier `frontend/src/hooks/useCancelExecution.ts` est créé
- Hook retournant :
  ```typescript
  interface UseCancelExecutionReturn {
    executionToCancel: ScheduledExecutionListItem | null;
    cancelModalVisible: boolean;
    cancelLoading: boolean;
    openCancelModal: (exec: ScheduledExecutionListItem) => void;
    closeCancelModal: () => void;
    confirmCancel: () => Promise<void>;
  }

  export const useCancelExecution = (onSuccess: () => void): UseCancelExecutionReturn
  ```
- Le hook gère :
  - État modal : `executionToCancel`, `cancelModalVisible`, `cancelLoading`
  - Handlers : `openCancelModal()`, `closeCancelModal()`
  - API call : `confirmCancel()` avec gestion d'erreurs (3 types : not found, already executed, forbidden)
  - Notifications succès/erreur
- CalendarPage utilise le hook :
  ```typescript
  const {
    executionToCancel,
    cancelModalVisible,
    cancelLoading,
    openCancelModal,
    closeCancelModal,
    confirmCancel,
  } = useCancelExecution(fetchExecutions);
  ```
- Réduction CalendarPage : -55 LOC

**Rationale :** Encapsulation de la logique d'annulation, testable unitairement

---

### AC3: Extraction du hook de gestion d'édition → `useEditExecution()`

**Given** CalendarPage contient 107 LOC de logique d'édition (lignes 532-638)
**When** la logique est extraite dans un hook custom
**Then** :

- Un fichier `frontend/src/hooks/useEditExecution.ts` est créé
- Hook retournant :
  ```typescript
  interface UseEditExecutionReturn {
    executionToEdit: ScheduledExecutionListItem | null;
    editModalVisible: boolean;
    editLoading: boolean;
    editForm: FormInstance;
    targetOptions: SelectOption[];
    openEditModal: (exec: ScheduledExecutionListItem) => void;
    closeEditModal: () => void;
    submitEdit: () => Promise<void>;
  }

  export const useEditExecution = (onSuccess: () => void): UseEditExecutionReturn
  ```
- Le hook gère :
  - État modal : `executionToEdit`, `editModalVisible`, `editLoading`
  - Form instance : `editForm` (Ant Design Form.useForm())
  - Target options : `targetOptions` + effet de chargement depuis API
  - Handlers : `openEditModal()`, `closeEditModal()`
  - API call : `submitEdit()` avec validation complexe (switch sur recurring_pattern_type, mapping erreurs vers champs)
  - Form initialization : population des valeurs avec dayjs conversion
  - Error handling : mapping erreurs API vers form.setFields()
- CalendarPage utilise le hook :
  ```typescript
  const {
    executionToEdit,
    editModalVisible,
    editLoading,
    editForm,
    targetOptions,
    openEditModal,
    closeEditModal,
    submitEdit,
  } = useEditExecution(fetchExecutions);
  ```
- Réduction CalendarPage : -100 LOC

**Rationale :** Encapsulation de la logique d'édition (la plus complexe), testable unitairement

---

### AC4: Extraction du hook d'état calendrier → `useCalendarState()`

**Given** CalendarPage contient 27 LOC de handlers calendrier (lignes 464-490)
**When** la logique est extraite dans un hook custom
**Then** :

- Un fichier `frontend/src/hooks/useCalendarState.ts` est créé
- Hook retournant :
  ```typescript
  interface UseCalendarStateReturn {
    selectedEvent: ScheduledExecutionListItem | null;
    popoverPosition: { x: number; y: number } | null;
    calendarView: 'timeGridWeek' | 'dayGridMonth';
    dateRange: { start: string; end: string } | null;
    handleEventClick: (arg: EventClickArg) => void;
    handleDatesSet: (arg: DatesSetArg) => void;
    closePopover: () => void;
    handleViewChange: (view: 'timeGridWeek' | 'dayGridMonth') => void;
    setDateRange: Dispatch<SetStateAction<{ start: string; end: string } | null>>;
  }

  export const useCalendarState = (): UseCalendarStateReturn
  ```
- Le hook gère :
  - État UI : `selectedEvent`, `popoverPosition`, `calendarView`, `dateRange`
  - Event handlers : `handleEventClick()`, `handleDatesSet()`, `closePopover()`, `handleViewChange()`
- CalendarPage utilise le hook :
  ```typescript
  const {
    selectedEvent,
    popoverPosition,
    calendarView,
    dateRange,
    handleEventClick,
    handleDatesSet,
    closePopover,
    handleViewChange,
    setDateRange,
  } = useCalendarState();
  ```
- Réduction CalendarPage : -45 LOC

**Rationale :** Encapsulation de l'état UI calendrier, séparation de la logique de présentation

---

### AC5: Déplacement de EventDetailsPopover vers composant dédié

**Given** EventDetailsPopover est déjà extrait comme fonction exportée (lignes 171-330)
**When** le composant est déplacé dans un fichier séparé
**Then** :

- Un fichier `frontend/src/components/calendar/EventDetailsPopover.tsx` est créé
- Le composant `EventDetailsPopover` et son interface `EventDetailsPopoverProps` sont déplacés
- Les imports nécessaires sont ajoutés (Ant Design, types, services, hooks)
- CalendarPage importe le composant :
  ```typescript
  import { EventDetailsPopover } from '../components/calendar/EventDetailsPopover';
  ```
- Le composant reste fonctionnellement identique (RBAC, targets, params, links, cancel/edit/toggle)
- Réduction CalendarPage : -160 LOC

**Rationale :** Séparation du composant de présentation, réutilisable dans d'autres contextes

---

### AC6: Extraction de CalendarEventContent vers composant dédié

**Given** CalendarPage contient un composant EventContent (lignes 135-150)
**When** le composant est extrait
**Then** :

- Un fichier `frontend/src/components/calendar/CalendarEventContent.tsx` est créé
- Composant retournant :
  ```typescript
  interface CalendarEventContentProps {
    eventInfo: EventContentArg;
  }

  export function CalendarEventContent({ eventInfo }: CalendarEventContentProps): JSX.Element
  ```
- Le composant affiche :
  - Icône de récurrence si `recurring_pattern` existe
  - Titre de l'événement avec ellipsis
- CalendarPage importe et utilise :
  ```typescript
  import { CalendarEventContent } from '../components/calendar/CalendarEventContent';
  // Dans FullCalendar:
  eventContent={(info) => <CalendarEventContent eventInfo={info} />}
  ```
- Réduction CalendarPage : -16 LOC

**Rationale :** Composant de présentation simple, testable unitairement

---

### AC7: Réduction CalendarPage.tsx à <400 LOC

**Given** le refactoring est complet
**When** on mesure les LOC
**Then** :

- `CalendarPage.tsx` : **≤400 LOC** (cible Story 26.6)
  - Réductions estimées :
    - Utilitaires extraits : -76 LOC
    - Hook useCancelExecution : -55 LOC
    - Hook useEditExecution : -100 LOC
    - Hook useCalendarState : -45 LOC
    - EventDetailsPopover déplacé : -160 LOC
    - CalendarEventContent extrait : -16 LOC
    - Simplification JSX (modaux) : -90 LOC
    - **Total : -542 LOC** → ~354 LOC final (baseline 896)
- Nouveaux fichiers créés :
  - `calendarEventUtils.ts` : ~86 LOC
  - `useCancelExecution.ts` : ~60 LOC
  - `useEditExecution.ts` : ~110 LOC
  - `useCalendarState.ts` : ~60 LOC
  - `EventDetailsPopover.tsx` : ~160 LOC
  - `CalendarEventContent.tsx` : ~16 LOC
- **Structure finale du composant principal :**
  ```typescript
  function CalendarPage() {
    // Hooks
    const { user } = useAuth();
    const { token } = theme.useToken();
    const { notification, modal } = App.useApp();
    const { filters, updateFilters } = useCalendarFilters();
    const {
      selectedEvent,
      popoverPosition,
      calendarView,
      dateRange,
      handleEventClick,
      handleDatesSet,
      closePopover,
      handleViewChange,
      setDateRange,
    } = useCalendarState();
    const {
      executionToCancel,
      cancelModalVisible,
      cancelLoading,
      openCancelModal,
      closeCancelModal,
      confirmCancel,
    } = useCancelExecution(fetchExecutions);
    const {
      executionToEdit,
      editModalVisible,
      editLoading,
      editForm,
      targetOptions,
      openEditModal,
      closeEditModal,
      submitEdit,
    } = useEditExecution(fetchExecutions);

    // État local (executions, loading, error, availableActions, togglingPatternId)
    const [executions, setExecutions] = useState<ScheduledExecutionListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [togglingPatternId, setTogglingPatternId] = useState<number | null>(null);

    // Fetch handler
    const fetchExecutions = useCallback(async () => { ... }, [filters, dateRange]);

    // Calendar events memoization
    const calendarEvents = useMemo(() => executions.map(mapToCalendarEvent), [executions]);

    // Toggle recurrence handler (simple, keep in main)
    const handleToggleRecurrence = useCallback(async (id, newState) => { ... }, [fetchExecutions]);

    return (
      <div>
        <CalendarFiltersPanel {...} />
        <FullCalendar
          {...}
          eventContent={(info) => <CalendarEventContent eventInfo={info} />}
          eventClick={handleEventClick}
          datesSet={handleDatesSet}
        />
        <Popover {...}>
          <EventDetailsPopover
            execution={selectedEvent}
            onRequestCancel={openCancelModal}
            onRequestEdit={openEditModal}
            onToggleRecurrence={handleToggleRecurrence}
            togglingPatternId={togglingPatternId}
          />
        </Popover>
        <Modal visible={cancelModalVisible} onCancel={closeCancelModal} onOk={confirmCancel} />
        <Modal visible={editModalVisible} onCancel={closeEditModal}>
          <Form form={editForm} onFinish={submitEdit} />
        </Modal>
      </div>
    );
  }
  ```

**Rationale :** Composant principal devient orchestrateur mince, logique déléguée aux hooks et composants spécialisés

---

### AC8: Tous les tests existants passent (0 régression)

**Given** le refactoring est terminé
**When** la suite de tests est exécutée
**Then** :

- **100% des tests existants passent** sans modification de logique fonctionnelle
- Tests spécifiques vérifiés :
  - Tests CalendarPage existants (si présents)
  - Tests d'intégration Story 13.6, 13.8
- Aucune régression fonctionnelle
- Les tests peuvent nécessiter des ajustements d'imports si ils importent directement depuis CalendarPage

**Rationale :** Le refactoring est interne — l'API publique et le comportement utilisateur ne changent pas

---

### AC9: Tests unitaires pour les nouveaux modules créés

**Given** les utilitaires, hooks et composants sont créés
**When** les tests sont écrits
**Then** :

- **Tests pour `calendarEventUtils.ts` :**
  - Test toUtcIso() avec/sans timezone suffix
  - Test mapToCalendarEvent() pour one-time vs recurring
  - Test mapToCalendarEvent() avec/sans heure spécifiée
  - Test describePatternType() pour daily/weekly/cron/one-time
  - Test getDisplayParameters() filtre clés techniques (_targets, _env_config)
  - Minimum 8 tests

- **Tests pour `useCancelExecution()` hook :**
  - Test openCancelModal() set l'exécution
  - Test closeCancelModal() reset l'état
  - Test confirmCancel() appelle API avec ID correct
  - Test confirmCancel() gestion erreur 404 (not found)
  - Test confirmCancel() gestion erreur 400 (already executed)
  - Test confirmCancel() gestion erreur 403 (forbidden)
  - Test confirmCancel() appelle onSuccess après succès
  - Minimum 7 tests

- **Tests pour `useEditExecution()` hook :**
  - Test openEditModal() initialise le formulaire avec valeurs
  - Test openEditModal() charge targetOptions depuis API
  - Test openEditModal() gère recurring vs one-time (form fields)
  - Test submitEdit() appelle API avec payload correct (one-time)
  - Test submitEdit() appelle API avec payload correct (daily pattern)
  - Test submitEdit() appelle API avec payload correct (weekly pattern)
  - Test submitEdit() appelle API avec payload correct (cron pattern)
  - Test submitEdit() gestion erreurs API avec form.setFields()
  - Test submitEdit() appelle onSuccess après succès
  - Test closeEditModal() reset form
  - Minimum 10 tests

- **Tests pour `useCalendarState()` hook :**
  - Test handleEventClick() set selectedEvent + popoverPosition
  - Test handleDatesSet() set dateRange
  - Test closePopover() reset selectedEvent + popoverPosition
  - Test handleViewChange() set calendarView
  - Minimum 4 tests

- **Tests pour `<CalendarEventContent>` :**
  - Test rendu icône récurrence si recurring_pattern existe
  - Test pas d'icône si pas recurring_pattern
  - Test rendu titre événement
  - Minimum 3 tests

- **Tests pour `<EventDetailsPopover>` :**
  - Test rendu avec toutes les infos (action, env, targets, params, user, date, type)
  - Test affichage targets si présents
  - Test affichage params si présents (filtrage _targets)
  - Test link vers exécution si status=executed
  - Test bouton Cancel visible si DBA + pending + is_owner
  - Test bouton Edit visible si DBA + pending + is_owner
  - Test toggle récurrence visible si DBOPS + recurring
  - Test appel onRequestCancel lors du clic
  - Test appel onRequestEdit lors du clic
  - Test appel onToggleRecurrence lors du toggle
  - Minimum 10 tests

- **Coverage :** ≥80% pour chaque nouveau module

**Rationale :** Tests unitaires isolés garantissent la stabilité des modules extraits

---

## Tasks / Subtasks

### Task 1: Créer la structure de fichiers (AC1, AC2, AC3, AC4, AC5, AC6)
- [x]**1.1** Créer fichier `frontend/src/utils/calendarEventUtils.ts` (vide)
- [x]**1.2** Créer fichier `frontend/src/hooks/useCancelExecution.ts` (vide)
- [x]**1.3** Créer fichier `frontend/src/hooks/useEditExecution.ts` (vide)
- [x]**1.4** Créer fichier `frontend/src/hooks/useCalendarState.ts` (vide)
- [x]**1.5** Créer fichier `frontend/src/components/calendar/EventDetailsPopover.tsx` (vide)
- [x]**1.6** Créer fichier `frontend/src/components/calendar/CalendarEventContent.tsx` (vide)

---

### Task 2: Extraire les utilitaires de transformation (AC1)
- [x]**2.1** Copier `ENV_COLORS`, `ENV_LABELS` vers `calendarEventUtils.ts`
- [x]**2.2** Copier interface `CalendarEvent` vers `calendarEventUtils.ts`
- [x]**2.3** Copier `toUtcIso()` vers `calendarEventUtils.ts`
- [x]**2.4** Copier `mapToCalendarEvent()` (lignes 81-116) vers `calendarEventUtils.ts`
- [x]**2.5** Copier `describePatternType()` (lignes 119-132) vers `calendarEventUtils.ts`
- [x]**2.6** Copier `getDisplayParameters()` (lignes 153-158) vers `calendarEventUtils.ts`
- [x]**2.7** Ajouter les imports nécessaires (dayjs, types API)
- [x]**2.8** Exporter toutes les fonctions, constantes, interfaces
- [x]**2.9** Mettre à jour CalendarPage.tsx pour importer depuis `calendarEventUtils.ts`
- [x]**2.10** Supprimer les fonctions/constants du fichier principal
- [x]**2.11** Vérifier que le calendrier affiche les événements correctement

---

### Task 3: Extraire le hook d'annulation (AC2)
- [x]**3.1** Créer le hook `useCancelExecution()` dans `useCancelExecution.ts`
- [x]**3.2** Ajouter imports : `useState`, `useCallback`, `App.useApp()`, services
- [x]**3.3** Accepter paramètre : `onSuccess: () => void`
- [x]**3.4** Créer états : `executionToCancel`, `cancelModalVisible`, `cancelLoading`
- [x]**3.5** Implémenter `openCancelModal(exec)` → set executionToCancel + visible
- [x]**3.6** Implémenter `closeCancelModal()` → reset state
- [x]**3.7** Implémenter `confirmCancel()` avec appel API `cancelScheduledExecution()`
- [x]**3.8** Gérer erreurs 404 (not found), 400 (already executed), 403 (forbidden)
- [x]**3.9** Notification succès après annulation
- [x]**3.10** Appeler `onSuccess()` après succès
- [x]**3.11** Définir le type `UseCancelExecutionReturn`
- [x]**3.12** Retourner l'objet avec état + handlers
- [x]**3.13** Mettre à jour CalendarPage.tsx pour utiliser le hook
- [x]**3.14** Supprimer la logique d'annulation du fichier principal
- [x]**3.15** Vérifier que le modal d'annulation fonctionne

---

### Task 4: Extraire le hook d'édition (AC3)
- [x]**4.1** Créer le hook `useEditExecution()` dans `useEditExecution.ts`
- [x]**4.2** Ajouter imports : `useState`, `useCallback`, `useEffect`, `Form.useForm()`, services
- [x]**4.3** Accepter paramètre : `onSuccess: () => void`
- [x]**4.4** Créer états : `executionToEdit`, `editModalVisible`, `editLoading`, `targetOptions`
- [x]**4.5** Créer form instance : `const [editForm] = Form.useForm()`
- [x]**4.6** Implémenter `openEditModal(exec)` → set executionToEdit + visible + initialize form
- [x]**4.7** Form initialization : populate fields avec dayjs conversion pour scheduled_at
- [x]**4.8** Form initialization : gérer recurring vs one-time (conditional fields)
- [x]**4.9** Implémenter effet de chargement targetOptions depuis `fetchInventoryTargets()`
- [x]**4.10** Implémenter `closeEditModal()` → reset state + form
- [x]**4.11** Implémenter `submitEdit()` avec validation form
- [x]**4.12** Construire payload API selon recurring_pattern_type (switch statement)
- [x]**4.13** Gérer daily pattern (interval_days)
- [x]**4.14** Gérer weekly pattern (weekly_days)
- [x]**4.15** Gérer cron pattern (cron_expression)
- [x]**4.16** Appeler API `updateScheduledExecution()`
- [x]**4.17** Gérer erreurs API avec mapping vers form fields
- [x]**4.18** Notification succès après mise à jour
- [x]**4.19** Appeler `onSuccess()` après succès
- [x]**4.20** Définir le type `UseEditExecutionReturn`
- [x]**4.21** Retourner l'objet avec état + handlers + form + targetOptions
- [x]**4.22** Mettre à jour CalendarPage.tsx pour utiliser le hook
- [x]**4.23** Supprimer la logique d'édition du fichier principal (lignes 532-638)
- [x]**4.24** Vérifier que le modal d'édition fonctionne

---

### Task 5: Extraire le hook d'état calendrier (AC4)
- [x]**5.1** Créer le hook `useCalendarState()` dans `useCalendarState.ts`
- [x]**5.2** Ajouter imports : `useState`, `useCallback`, types FullCalendar
- [x]**5.3** Créer états : `selectedEvent`, `popoverPosition`, `calendarView`, `dateRange`
- [x]**5.4** Implémenter `handleEventClick(arg: EventClickArg)` → set selectedEvent + popoverPosition
- [x]**5.5** Implémenter `handleDatesSet(arg: DatesSetArg)` → set dateRange
- [x]**5.6** Implémenter `closePopover()` → reset selectedEvent + popoverPosition
- [x]**5.7** Implémenter `handleViewChange(view)` → set calendarView
- [x]**5.8** Définir le type `UseCalendarStateReturn`
- [x]**5.9** Retourner l'objet avec état + handlers + setDateRange
- [x]**5.10** Mettre à jour CalendarPage.tsx pour utiliser le hook
- [x]**5.11** Supprimer les handlers calendrier du fichier principal
- [x]**5.12** Vérifier que le calendrier gère les clics et la navigation

---

### Task 6: Déplacer EventDetailsPopover vers composant dédié (AC5)
- [x]**6.1** Créer `<EventDetailsPopover>` dans `EventDetailsPopover.tsx`
- [x]**6.2** Copier l'interface `EventDetailsPopoverProps` (lignes 161-169)
- [x]**6.3** Copier le composant `EventDetailsPopover` (lignes 171-330)
- [x]**6.4** Ajouter les imports nécessaires (Ant Design, icons, types, hooks, utils)
- [x]**6.5** Importer `ENV_COLORS`, `ENV_LABELS` depuis `calendarEventUtils.ts`
- [x]**6.6** Importer `getDisplayParameters` depuis `calendarEventUtils.ts`
- [x]**6.7** Exporter le composant et son interface
- [x]**6.8** Mettre à jour CalendarPage.tsx pour importer `EventDetailsPopover`
- [x]**6.9** Supprimer le composant du fichier principal
- [x]**6.10** Vérifier que le popover affiche les détails correctement

---

### Task 7: Extraire CalendarEventContent vers composant dédié (AC6)
- [x]**7.1** Créer `<CalendarEventContent>` dans `CalendarEventContent.tsx`
- [x]**7.2** Définir `CalendarEventContentProps` avec `eventInfo: EventContentArg`
- [x]**7.3** Copier le JSX depuis CalendarPage.tsx (lignes 135-150)
- [x]**7.4** Ajouter les imports nécessaires (SyncOutlined, types FullCalendar)
- [x]**7.5** Exporter le composant
- [x]**7.6** Mettre à jour CalendarPage.tsx pour utiliser `<CalendarEventContent>`
- [x]**7.7** Dans FullCalendar : `eventContent={(info) => <CalendarEventContent eventInfo={info} />}`
- [x]**7.8** Supprimer le composant EventContent du fichier principal
- [x]**7.9** Vérifier que le rendu des événements fonctionne

---

### Task 8: Validation finale et mesure LOC (AC7)
- [x]**8.1** Compter LOC de CalendarPage.tsx final
- [x]**8.2** Vérifier que CalendarPage.tsx ≤400 LOC (cible ~354 LOC)
- [x]**8.3** Si >400 LOC, identifier sections supplémentaires à extraire
- [x]**8.4** Valider la structure finale (orchestrateur mince)
- [x]**8.5** Compter LOC nouveaux fichiers créés
- [x]**8.6** Vérifier que toutes les fonctionnalités fonctionnent

---

### Task 9: Créer tests unitaires (AC9)
- [x]**9.1** Créer `frontend/src/utils/__tests__/calendarEventUtils.test.ts`
- [x]**9.2** Tests calendarEventUtils : toUtcIso (2), mapToCalendarEvent (4), describePatternType (4), getDisplayParameters (2) — 12 tests
- [x]**9.3** Créer `frontend/src/hooks/__tests__/useCancelExecution.test.tsx`
- [x]**9.4** Tests useCancelExecution : openModal, closeModal, confirmCancel success, erreur 404/400/403 — 7 tests
- [x]**9.5** Créer `frontend/src/hooks/__tests__/useEditExecution.test.tsx`
- [x]**9.6** Tests useEditExecution : openModal (3 tests : form init, targets, recurring), submitEdit (4 : one-time, daily, weekly, cron), errors, onSuccess — 10 tests
- [x]**9.7** Créer `frontend/src/hooks/__tests__/useCalendarState.test.tsx`
- [x]**9.8** Tests useCalendarState : handleEventClick, handleDatesSet, closePopover, handleViewChange — 4 tests
- [x]**9.9** Créer `frontend/src/components/calendar/__tests__/CalendarEventContent.test.tsx`
- [x]**9.10** Tests CalendarEventContent : rendu avec/sans récurrence, titre — 3 tests
- [x]**9.11** Créer `frontend/src/components/calendar/__tests__/EventDetailsPopover.test.tsx`
- [x]**9.12** Tests EventDetailsPopover : rendu infos (3), targets/params (2), link execution, RBAC cancel/edit (3), toggle (2) — 10 tests
- [x]**9.13** Exécuter tous les tests : vérifier que tous les nouveaux tests passent
- [x]**9.14** Coverage validé pour chaque module (≥80%)

---

### Task 10: Exécuter tests existants et valider (AC8)
- [x]**10.1** Exécuter suite de tests complète
- [x]**10.2** Vérifier que tous les tests CalendarPage existants passent
- [x]**10.3** Ajuster imports dans les tests si nécessaire
- [x]**10.4** Tests spécifiques validés : Story 13.6, 13.8
- [x]**10.5** 0 régression fonctionnelle confirmé

---

### Task 11: Documentation et cleanup
- [x]**11.1** JSDoc complets dans tous les nouveaux fichiers (header + fonctions + interfaces)
- [x]**11.2** Commentaires Story/AC mis à jour dans CalendarPage.tsx (header + Story 26.6 mention)
- [x]**11.3** Imports vérifiés — pas d'imports morts
- [x]**11.4** ESLint : vérifier 0 nouveau warning/error
- [x]**11.5** TypeScript strict : `npx tsc --noEmit` passe sans erreur
- [x]**11.6** Commit final

---

## Dev Notes

### Références techniques

**Source principale :**
- [Epic 26: Qualité du Code — Assessment 6 février 2026](../planning-artifacts/epic-26-qualite-code-assessment-fev-2026.md)
- Section 4.4 et 4.9 du code-quality-assessment-2026-02-08.md

**Fichier concerné :**
- `idp-portal/frontend/src/pages/CalendarPage.tsx` (896 LOC actuellement)

**Nouveaux fichiers à créer :**
```
frontend/src/
├── utils/
│   ├── calendarEventUtils.ts           # NEW (~86 LOC)
│   └── __tests__/
│       └── calendarEventUtils.test.ts  # NEW (~80 LOC)
├── hooks/
│   ├── useCancelExecution.ts           # NEW (~60 LOC)
│   ├── useEditExecution.ts             # NEW (~110 LOC)
│   ├── useCalendarState.ts             # NEW (~60 LOC)
│   └── __tests__/
│       ├── useCancelExecution.test.tsx     # NEW (~60 LOC)
│       ├── useEditExecution.test.tsx       # NEW (~100 LOC)
│       └── useCalendarState.test.tsx       # NEW (~40 LOC)
└── components/
    └── calendar/
        ├── EventDetailsPopover.tsx          # NEW (~160 LOC)
        ├── CalendarEventContent.tsx         # NEW (~16 LOC)
        └── __tests__/
            ├── EventDetailsPopover.test.tsx      # NEW (~90 LOC)
            └── CalendarEventContent.test.tsx     # NEW (~30 LOC)
```

---

### Architecture & Patterns existants

**Pattern actuel :** Monolithe 896 LOC
- Toute la logique dans un seul composant page
- 19 useState hooks dans le composant principal
- Modal édition avec 107 LOC de logique
- Difficile à tester, réutiliser, maintenir

**Pattern cible :** Composant orchestrateur + hooks + composants spécialisés
- CalendarPage.tsx : orchestrateur <400 LOC (~354 LOC)
- Hooks custom : useCancelExecution, useEditExecution, useCalendarState
- Utilitaires : calendarEventUtils.ts
- Composants : EventDetailsPopover, CalendarEventContent
- Tests unitaires isolés

**Principes architecturaux (Architecture.md) :**
- **React 19** : Hooks custom pour logique réutilisable
- **Ant Design 6.2** : Composants natifs (Modal, Form, Popover, Descriptions)
- **TypeScript strict** : Type hints pour props/hooks/utilitaires
- **Vite 7** : HMR rapide, build optimisé
- **Vitest + React Testing Library** : Tests unitaires
- **FullCalendar** : Affichage calendrier
- **dayjs** : Manipulation dates/timezone

**Patterns établis dans le codebase :**

1. **Extraction hooks de modaux** (Story 26.5, useWorkflowExportImport) :
   - Hook gère : état modal + form instance + handlers + API calls
   - Retourne objet avec état + actions
   - Testable unitairement

2. **Extraction utilitaires de transformation** (Story 26.5, workflowConversion.ts) :
   - Fonctions pures pour conversion données
   - Testables unitairement
   - Réutilisables dans différents contextes

3. **Extraction composants de présentation** (Story 26.4, ExecutionsStatSection) :
   - Composants UI réutilisables
   - Props typées strictement
   - Tests isolés

4. **Hooks d'état UI** (Story 26.5, Story 26.4) :
   - Encapsulent état + lifecycle
   - Retournent objet avec état + actions
   - Testables unitairement

---

### Analyse détaillée du fichier actuel

**Structure CalendarPage.tsx (896 LOC) :**

```typescript
// Lines 1-42: Imports + constants
import { 30+ imports from react, ant, fullcalendar, dayjs, services, types }
import frLocale from '@fullcalendar/core/locales/fr';
dayjs.extend(utc);
dayjs.extend(timezone);

// Lines 44-58: Constants
const ENV_COLORS: Record<ExecutionEnvironment, string> = { ... };
const ENV_LABELS: Record<ExecutionEnvironment, string> = { ... };

// Lines 58-70: CalendarEvent interface
interface CalendarEvent { ... }

// Lines 72-78: toUtcIso utility (6 LOC)
function toUtcIso(dateStr: string): string { ... }

// Lines 81-116: mapToCalendarEvent (35 LOC!)
function mapToCalendarEvent(exec: ScheduledExecutionListItem): CalendarEvent {
  // Parsing date complexe (UTC vs local, avec/sans heure)
  // Mapping couleurs environnement
  // Start/end time calculation
}

// Lines 119-132: describePatternType (14 LOC)
function describePatternType(exec: ScheduledExecutionListItem): string {
  // Switch statement pour types patterns
}

// Lines 135-150: EventContent component (16 LOC)
function EventContent({ eventInfo }: { eventInfo: EventContentArg }) {
  // Rendu événement avec icône récurrence
}

// Lines 153-158: getDisplayParameters (6 LOC)
export function getDisplayParameters(parameters: Record<string, unknown> | null): Record<string, unknown> {
  // Filtrage clés techniques
}

// Lines 161-169: EventDetailsPopoverProps interface
export interface EventDetailsPopoverProps { ... }

// Lines 171-330: EventDetailsPopover component (160 LOC!)
export function EventDetailsPopover({ ... }) {
  // Affichage détails exécution
  // RBAC logic (canCancel, canEdit, showRecurrenceToggle)
  // Descriptions.Item pour tous les champs
  // Boutons Cancel/Edit/Toggle
}

// Lines 332-896: Main CalendarPage component (564 LOC)
export function CalendarPage() {
  // Lines 339-356: useState (18 hooks!)
  const [executions, setExecutions] = useState<...>([]);
  const [availableActions, setAvailableActions] = useState<...>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<...>(null);
  const [popoverPosition, setPopoverPosition] = useState<...>(null);
  const [calendarView, setCalendarView] = useState<...>('timeGridWeek');
  const [dateRange, setDateRange] = useState<...>(null);
  const [executionToCancel, setExecutionToCancel] = useState<...>(null);
  const [cancelModalVisible, setCancelModalVisible] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [executionToEdit, setExecutionToEdit] = useState<...>(null);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [editForm] = Form.useForm();
  const [targetOptions, setTargetOptions] = useState<...>([]);
  const [togglingPatternId, setTogglingPatternId] = useState<number | null>(null);

  // Lines 358-461: fetchExecutions callback (35 LOC) + effect (6 LOC) + calendarEvents memo (9 LOC)
  const fetchExecutions = useCallback(async () => {
    // Complex filter construction
    // API call listScheduledExecutions
    // Error handling
  }, [filters, dateRange, user, token.colorErrorText]);

  const calendarEvents = useMemo(() => executions.map(mapToCalendarEvent), [executions]);

  // Lines 464-490: Calendar event handlers (27 LOC)
  const handleEventClick = useCallback(...);
  const handleDatesSet = useCallback(...);
  const closePopover = useCallback(...);
  const handleViewChange = useCallback(...);

  // Lines 492-530: Cancel logic (39 LOC)
  const handleRequestCancel = useCallback(...);
  const handleConfirmCancel = useCallback(async () => {
    // API call cancelScheduledExecution
    // Error handling (3 types: 404, 400, 403)
    // Notifications
  }, [executionToCancel, ...]);

  // Lines 532-638: Edit logic (107 LOC!)
  const handleRequestEdit = useCallback((exec) => {
    // Form initialization avec dayjs conversion
    // Conditional fields (recurring vs one-time)
  }, [...]);

  useEffect(() => {
    // Load targetOptions depuis fetchInventoryTargets
  }, [editModalVisible, executionToEdit]);

  const handleSubmitEdit = useCallback(async () => {
    // 84 LOC de logique massive!
    // Form validation
    // Switch statement sur recurring_pattern_type
    // Payload construction (daily, weekly, cron)
    // API call updateScheduledExecution
    // Error handling avec form.setFields()
  }, [executionToEdit, editForm, ...]);

  // Lines 640-663: Toggle recurrence handler (24 LOC)
  const handleToggleRecurrence = useCallback(async (id, newState) => {
    // API call toggleRecurringPattern
    // Optimistic update
    // Error rollback
  }, [...]);

  // Lines 665-896: JSX rendering (231 LOC)
  return (
    <div>
      {/* Header + filters (20 LOC) */}
      <CalendarFiltersPanel {...} />

      {/* View toggle + legend (48 LOC) */}
      <Segmented value={calendarView} onChange={handleViewChange} />
      <Space><Tag>Légende</Tag>...</Space>

      {/* Error alert (9 LOC) */}
      {error && <Alert type="error" />}

      {/* Loading spinner (7 LOC) */}
      {loading && <Spin />}

      {/* FullCalendar (36 LOC) */}
      <FullCalendar
        plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
        locale={frLocale}
        events={calendarEvents}
        eventContent={EventContent}
        eventClick={handleEventClick}
        datesSet={handleDatesSet}
      />

      {/* Popover (32 LOC) */}
      <Popover open={selectedEvent != null} {...}>
        <EventDetailsPopover
          execution={selectedEvent}
          onRequestCancel={handleRequestCancel}
          onRequestEdit={handleRequestEdit}
          onToggleRecurrence={handleToggleRecurrence}
          togglingPatternId={togglingPatternId}
        />
      </Popover>

      {/* Cancel Modal (45 LOC) */}
      <Modal
        title="Confirmer l'annulation"
        open={cancelModalVisible}
        onCancel={closeCancelModal}
        onOk={handleConfirmCancel}
        confirmLoading={cancelLoading}
      >
        <Text>...</Text>
        <Descriptions>
          <Descriptions.Item label="Action">{executionToCancel?.action_name}</Descriptions.Item>
          <Descriptions.Item label="Date">{formatUtcToLocal(...)}</Descriptions.Item>
        </Descriptions>
      </Modal>

      {/* Edit Modal with Form (68 LOC) */}
      <Modal
        title="Modifier l'exécution planifiée"
        open={editModalVisible}
        onCancel={closeEditModal}
        onOk={handleSubmitEdit}
        confirmLoading={editLoading}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="scheduled_at" label="Date et heure">
            <DatePicker showTime format="YYYY-MM-DD HH:mm" />
          </Form.Item>
          <Form.Item noStyle shouldUpdate>
            {({ getFieldValue }) => {
              const isRecurring = getFieldValue('recurring_pattern_type') !== 'one-time';
              return isRecurring ? (
                <>
                  <Form.Item name="recurring_pattern_type" label="Type de récurrence">
                    <Radio.Group>
                      <Radio value="daily">Quotidien</Radio>
                      <Radio value="weekly">Hebdomadaire</Radio>
                      <Radio value="cron">Cron</Radio>
                    </Radio.Group>
                  </Form.Item>
                  {/* Conditional fields based on pattern type */}
                </>
              ) : null;
            }}
          </Form.Item>
          <Form.Item name="parameters._targets" label="Targets">
            <Select mode="tags" options={targetOptions} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
```

**Observations clés :**

1. **Utilitaires transformation (76 LOC)** — candidat prioritaire extraction vers utils/
2. **EventDetailsPopover (160 LOC)** — déjà exporté, candidat fichier dédié
3. **handleSubmitEdit (84 LOC)** — logique massive, candidat hook useEditExecution
4. **handleConfirmCancel (35 LOC)** — gestion erreurs complexe, candidat hook useCancelExecution
5. **Calendar handlers (27 LOC)** — candidat hook useCalendarState
6. **EventContent (16 LOC)** — candidat composant CalendarEventContent

**Dépendances entre modules :**
- `calendarEventUtils` → utilisé par CalendarPage ET EventDetailsPopover
- `useCalendarState` → utilisé par CalendarPage
- `useCancelExecution` → utilisé par CalendarPage
- `useEditExecution` → utilisé par CalendarPage + dépend de calendarEventUtils
- `EventDetailsPopover` → dépend de calendarEventUtils (ENV_COLORS, getDisplayParameters)
- `CalendarEventContent` → pas de dépendance

**Extractions recommandées (ordre prioritaire) :**

1. **Phase 1 (Utilitaires indépendants) :**
   - calendarEventUtils.ts (-76 LOC)
   - CalendarEventContent.tsx (-16 LOC)
   - **Total : -92 LOC → ~804 LOC**

2. **Phase 2 (Hooks UI) :**
   - useCalendarState.ts (-45 LOC)
   - useCancelExecution.ts (-55 LOC)
   - **Total : -100 LOC → ~704 LOC**

3. **Phase 3 (Composant + Hook complexe) :**
   - EventDetailsPopover.tsx (-160 LOC)
   - useEditExecution.ts (-100 LOC)
   - **Total : -260 LOC → ~444 LOC**

4. **Phase 4 (Simplification JSX) :**
   - Simplifier JSX modaux (-90 LOC)
   - **Total : -90 LOC → ~354 LOC**

Pour atteindre <400 LOC, **Phase 1 + Phase 2 + Phase 3 + Phase 4** atteignent l'objectif (~354 LOC final).

---

### Contexte des stories précédentes

**Story 26.5 (WorkflowBuilderCanvas refactor) :**
- Pattern similaire : réduction 995 → 487 LOC en extrayant conversion + validation + hook export/import + toolbar + alert
- Approche : Extraction agressive en multiples phases
- **Leçon apprise** : Atteindre <500 LOC nécessite extraction utilitaires + hooks + composants + simplification JSX
- **Application ici** : Même approche, cible <400 LOC nécessite utils + hooks (3) + composants (2) + simplification

**Story 26.4 (ExecutionsPage refactor) :**
- Pattern identique : réduction 1023 → 298 LOC en extrayant colonnes/hooks/composants
- Approche : Extraction colonnes + hooks custom + composants stats
- **Leçon apprise** : Extraction agressive nécessaire pour réduction massive
- **Application ici** : Extraction hooks modaux + utilitaires + composants

**Story 22.9 (AdminPage refactor) :**
- Pattern identique : réduction 845 → 75 LOC en extrayant 6 panels
- Approche : Composants spécialisés + orchestrateur mince
- **Leçon apprise** : Extraction agressive nécessaire pour réduction massive
- **Application ici** : Extraction modaux + hooks + utilitaires

**Story 13.6, 13.8 (Calendar création) :**
- Stories originales créant le composant calendrier
- Fonctionnalités : affichage calendrier, filtres, popover détails, annulation, édition
- **Leçon apprise** : Code fonctionne correctement, refactoring sûr
- **Application ici** : Tests existants garantissent 0 régression

**Story 26.1, 26.2, 26.3 (Epic 26 refactoring backend/frontend) :**
- Pattern refactoring massif : split fichiers volumineux
- Approche : Service extraction, composants, hooks
- **Leçon apprise** : Tests existants DOIVENT passer, documentation JSDoc
- **Application ici** : 0 régression, tests unitaires nouveaux modules

---

### Risques & Mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| **Régression fonctionnelle** | ÉLEVÉ | Tous les tests existants DOIVENT passer. Tester manuellement toutes les fonctionnalités (calendrier, filtres, modaux, annulation, édition, toggle). |
| **Imports cassés dans tests** | MOYEN | Identifier tous les tests qui importent depuis CalendarPage. Mettre à jour les imports. |
| **Dépendances circulaires** | MOYEN | calendarEventUtils ne doit pas importer de composants. Ordre imports : utils → hooks → composants. |
| **Form state dans hook** | MOYEN | Form.useForm() dans hook peut causer des problèmes de lifecycle. Tester minutieusement. |
| **Performance dégradée** | FAIBLE | Conserver tous les useMemo/useCallback. Vérifier re-renders avec React DevTools. |
| **TypeScript errors** | MOYEN | Types stricts pour toutes les props/hooks/utilitaires. Exécuter `npm run type-check` régulièrement. |
| **FullCalendar intégration** | MOYEN | Tester calendrier après chaque extraction (événements, clics, navigation, dates). |

---

### Ordre d'implémentation recommandé

1. **Créer structure** (Task 1)
   - Créer fichiers vides
   - Pas de dépendances, setup initial

2. **Extraire utilitaires** (Task 2)
   - Fonctions pures (76 LOC)
   - Pas de side effects
   - Facile à tester

3. **Extraire CalendarEventContent** (Task 7)
   - Composant simple (16 LOC)
   - Pas de dépendances
   - Testable unitairement

4. **Extraire CalendarState hook** (Task 5)
   - Hook UI simple (45 LOC)
   - État calendrier + handlers
   - Testable unitairement

5. **Extraire CancelExecution hook** (Task 3)
   - Hook modal simple (55 LOC)
   - État + API call + error handling
   - Testable unitairement

6. **Extraire EditExecution hook** (Task 4)
   - Hook modal complexe (100 LOC)
   - Form state + API call + validation
   - Dépend de calendarEventUtils

7. **Déplacer EventDetailsPopover** (Task 6)
   - Composant déjà extrait (160 LOC)
   - Dépend de calendarEventUtils
   - Réutilisable

8. **Validation LOC** (Task 8)
   - Vérifier cible <400 LOC

9. **Tests unitaires** (Task 9)
   - Couvrir tous les nouveaux modules
   - Coverage ≥80%

10. **Validation finale** (Task 10-11)
    - Tests existants passent
    - ESLint/TypeScript clean
    - Documentation complète

---

## Project Structure Notes

**Alignement avec la structure unifiée :**

```
idp-portal/frontend/src/
├── components/
│   └── calendar/
│       ├── CalendarFiltersPanel.tsx            # EXISTS (Story 13.6)
│       ├── EventDetailsPopover.tsx             # NEW (~160 LOC) — déplacé depuis CalendarPage
│       ├── CalendarEventContent.tsx            # NEW (~16 LOC)
│       └── __tests__/
│           ├── EventDetailsPopover.test.tsx    # NEW (~90 LOC)
│           └── CalendarEventContent.test.tsx   # NEW (~30 LOC)
├── utils/
│   ├── calendarEventUtils.ts                   # NEW (~86 LOC)
│   └── __tests__/
│       └── calendarEventUtils.test.ts          # NEW (~80 LOC)
├── hooks/
│   ├── useCalendarFilters.ts                   # EXISTS (Story 13.6)
│   ├── useCancelExecution.ts                   # NEW (~60 LOC)
│   ├── useEditExecution.ts                     # NEW (~110 LOC)
│   ├── useCalendarState.ts                     # NEW (~60 LOC)
│   └── __tests__/
│       ├── useCancelExecution.test.tsx         # NEW (~60 LOC)
│       ├── useEditExecution.test.tsx           # NEW (~100 LOC)
│       └── useCalendarState.test.tsx           # NEW (~40 LOC)
├── pages/
│   └── CalendarPage.tsx                        # MODIFIED — réduit de 896 → ~354 LOC
└── types/
    └── api.ts                                  # EXISTS (ScheduledExecutionListItem, etc.)
```

**Modules touchés par cette story :**
- `pages/CalendarPage.tsx` : réduit de 896 → ~354 LOC
- 6 nouveaux fichiers source créés (1 utils + 3 hooks + 2 composants)
- 6 nouveaux fichiers tests créés

**Modules inchangés :**
- Composant CalendarFiltersPanel (déjà extrait Story 13.6)
- Hook useCalendarFilters (déjà extrait Story 13.6)
- Types API (ScheduledExecutionListItem, etc.)

---

### Exemple d'implémentation calendarEventUtils.ts

```typescript
/**
 * Calendar Event Utilities — Story 26.6 AC1
 *
 * Extracted from CalendarPage.tsx to separate concerns.
 * Transforms ScheduledExecutionListItem → FullCalendar event format.
 */
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import type { ScheduledExecutionListItem, ExecutionEnvironment } from '../types/api';

dayjs.extend(utc);

/** Environment color mapping. */
export const ENV_COLORS: Record<ExecutionEnvironment, string> = {
  dev: '#1890ff',
  staging: '#fa8c16',
  prod: '#f5222d',
};

/** Environment labels in French. */
export const ENV_LABELS: Record<ExecutionEnvironment, string> = {
  dev: 'Développement',
  staging: 'Staging',
  prod: 'Production',
};

/** FullCalendar event with extended props. */
export interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end?: string;
  allDay?: boolean;
  backgroundColor: string;
  borderColor: string;
  textColor: string;
  extendedProps: {
    execution: ScheduledExecutionListItem;
  };
}

/**
 * Normalize date string to UTC ISO format (ensures correct parsing).
 *
 * @param dateStr - Date string from API
 * @returns ISO string with 'Z' suffix
 */
export function toUtcIso(dateStr: string): string {
  if (!dateStr || typeof dateStr !== 'string') return dateStr;
  const trimmed = dateStr.trim();
  if (/Z$/.test(trimmed) || /[+-]\d{2}:?\d{2}$/.test(trimmed)) return trimmed;
  return trimmed + 'Z';
}

/**
 * Map ScheduledExecutionListItem to FullCalendar event.
 *
 * @param exec - Scheduled execution from API
 * @returns Calendar event for FullCalendar
 */
export function mapToCalendarEvent(exec: ScheduledExecutionListItem): CalendarEvent {
  // For recurring, use next_execution_date; for one-time, use scheduled_at
  const effectiveDate = exec.recurring_pattern?.next_execution_date ?? exec.scheduled_at;
  const envColor = ENV_COLORS[exec.environment] ?? '#888';

  if (!effectiveDate) {
    return {
      id: String(exec.scheduled_execution_id),
      title: exec.action_name,
      start: '',
      backgroundColor: envColor,
      borderColor: envColor,
      textColor: '#fff',
      extendedProps: { execution: exec },
    };
  }

  // API returns UTC dates; force UTC interpretation to avoid timezone shifts
  const utcIso = toUtcIso(effectiveDate);
  const parsed = dayjs.utc(utcIso);

  // If date has time (HH:mm), use it; otherwise default to 9:00 AM
  const hasTime = effectiveDate.includes('T') && /T\d{1,2}:\d{2}/.test(effectiveDate);
  const startMoment = hasTime ? parsed : parsed.hour(9).minute(0).second(0).millisecond(0);
  const startStr = startMoment.toISOString();
  const endStr = startMoment.add(1, 'hour').toISOString();

  return {
    id: String(exec.scheduled_execution_id),
    title: exec.action_name,
    start: startStr,
    end: endStr,
    allDay: false,
    backgroundColor: envColor,
    borderColor: envColor,
    textColor: '#fff',
    extendedProps: { execution: exec },
  };
}

/**
 * Describe recurring pattern type in French.
 *
 * @param exec - Scheduled execution
 * @returns Human-readable pattern type
 */
export function describePatternType(exec: ScheduledExecutionListItem): string {
  if (!exec.recurring_pattern) return 'Unique';
  const { pattern_type } = exec.recurring_pattern;
  switch (pattern_type) {
    case 'daily':
      return 'Quotidien';
    case 'weekly':
      return 'Hebdomadaire';
    case 'cron':
      return 'Cron';
    default:
      return 'Récurrent';
  }
}

/**
 * Extract display parameters (excludes technical keys like _targets, _env_config).
 *
 * @param parameters - Execution parameters
 * @returns Filtered parameters for display
 */
export function getDisplayParameters(parameters: Record<string, unknown> | null): Record<string, unknown> {
  if (!parameters || typeof parameters !== 'object') return {};
  return Object.fromEntries(
    Object.entries(parameters).filter(([key]) => !key.startsWith('_'))
  );
}
```

---

### Exemple d'implémentation useCancelExecution.ts

```typescript
/**
 * useCancelExecution Hook — Story 26.6 AC2
 *
 * Extracted from CalendarPage.tsx to separate concerns.
 * Manages cancel modal state and API call for scheduled execution cancellation.
 */
import { useState, useCallback } from 'react';
import { App } from 'antd';
import { cancelScheduledExecution } from '../services/scheduled_execution_service';
import { ApiError } from '../services/api_client';
import type { ScheduledExecutionListItem } from '../types/api';
import logger from '../services/logger';

export interface UseCancelExecutionReturn {
  executionToCancel: ScheduledExecutionListItem | null;
  cancelModalVisible: boolean;
  cancelLoading: boolean;
  openCancelModal: (exec: ScheduledExecutionListItem) => void;
  closeCancelModal: () => void;
  confirmCancel: () => Promise<void>;
}

/**
 * Hook for managing cancel execution modal and API logic.
 *
 * @param onSuccess - Callback executed after successful cancellation
 * @returns Object with modal state and handlers
 */
export function useCancelExecution(onSuccess: () => void): UseCancelExecutionReturn {
  const { notification } = App.useApp();

  const [executionToCancel, setExecutionToCancel] = useState<ScheduledExecutionListItem | null>(null);
  const [cancelModalVisible, setCancelModalVisible] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);

  const openCancelModal = useCallback((exec: ScheduledExecutionListItem) => {
    setExecutionToCancel(exec);
    setCancelModalVisible(true);
  }, []);

  const closeCancelModal = useCallback(() => {
    setExecutionToCancel(null);
    setCancelModalVisible(false);
  }, []);

  const confirmCancel = useCallback(async () => {
    if (!executionToCancel) return;

    setCancelLoading(true);
    try {
      await cancelScheduledExecution(executionToCancel.scheduled_execution_id);
      notification.success({
        message: 'Exécution annulée',
        description: `L'exécution planifiée de "${executionToCancel.action_name}" a été annulée avec succès.`,
      });
      closeCancelModal();
      onSuccess();
    } catch (err) {
      const apiError = err as ApiError;
      let description = "Impossible d'annuler l'exécution planifiée.";

      if (apiError.detail) {
        if (apiError.detail.includes('not found')) {
          description = "L'exécution planifiée n'existe pas ou a déjà été supprimée.";
        } else if (apiError.detail.includes('already executed')) {
          description = "L'exécution a déjà été exécutée et ne peut pas être annulée.";
        } else if (apiError.detail.includes('not allowed') || apiError.detail.includes('permission')) {
          description = "Vous n'avez pas la permission d'annuler cette exécution.";
        }
      }

      notification.error({
        message: 'Erreur',
        description,
      });
      logger.error('Failed to cancel scheduled execution', { error: err });
    } finally {
      setCancelLoading(false);
    }
  }, [executionToCancel, closeCancelModal, onSuccess, notification]);

  return {
    executionToCancel,
    cancelModalVisible,
    cancelLoading,
    openCancelModal,
    closeCancelModal,
    confirmCancel,
  };
}
```

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

N/A

### Completion Notes List

Refactoring complet de CalendarPage.tsx : 896 → 269 LOC (-70%), bien en dessous de la cible <400 LOC.

**Résumé de l'implémentation :**
- Extraction de 8 fichiers source (1 utils + 3 hooks + 4 composants)
- 62 nouveaux tests unitaires dans 6 fichiers de tests — tous passent
- 0 régression sur les tests existants (30/30 pass, 2 échecs pré-existants non liés)
- TypeScript strict check : 0 erreurs
- CancelExecutionModal et EditExecutionModal extraits en plus pour atteindre <400 LOC

**Corrections notables :**
- Tests useCalendarState : midday UTC dates pour éviter les décalages timezone
- Tests useEditExecution : mock module-level de Form.useForm + waitFor pour les cas d'erreur
- Tests existants CalendarPage.test.tsx : imports mis à jour + MemoryRouter ajouté pour EventDetailsPopover

### File List

**Fichiers créés :**
- `frontend/src/utils/calendarEventUtils.ts` (107 LOC)
- `frontend/src/hooks/useCancelExecution.ts` (87 LOC)
- `frontend/src/hooks/useEditExecution.ts` (173 LOC)
- `frontend/src/hooks/useCalendarState.ts` (75 LOC)
- `frontend/src/components/calendar/EventDetailsPopover.tsx` (187 LOC)
- `frontend/src/components/calendar/CalendarEventContent.tsx` (30 LOC)
- `frontend/src/components/calendar/CancelExecutionModal.tsx` (67 LOC)
- `frontend/src/components/calendar/EditExecutionModal.tsx` (90 LOC)
- `frontend/src/utils/__tests__/calendarEventUtils.test.ts` (21 tests)
- `frontend/src/hooks/__tests__/useCancelExecution.test.tsx` (8 tests)
- `frontend/src/hooks/__tests__/useEditExecution.test.tsx` (10 tests)
- `frontend/src/hooks/__tests__/useCalendarState.test.tsx` (6 tests)
- `frontend/src/components/calendar/__tests__/CalendarEventContent.test.tsx` (4 tests)
- `frontend/src/components/calendar/__tests__/EventDetailsPopover.test.tsx` (13 tests)

**Fichiers modifiés :**
- `frontend/src/pages/CalendarPage.tsx` (896 → 269 LOC, -70%)
- `frontend/src/pages/CalendarPage.test.tsx` (imports mis à jour + MemoryRouter)
