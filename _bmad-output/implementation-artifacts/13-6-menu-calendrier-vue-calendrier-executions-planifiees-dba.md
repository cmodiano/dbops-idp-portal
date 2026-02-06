# Story 13.6 : Menu Calendrier — vue calendrier et exécutions planifiées pour les DBA

Status: done

## Story

As a DBA,
I want accéder à un menu Calendrier qui affiche les exécutions planifiées dans une vraie vue calendrier (semaine/mois) avec des filtres alignés sur la page Exécutions (action, environnement, plateforme, technologie),
So que je consulte l'ensemble des tâches planifiées sans passer par l'interface Admin (réservée à DBOPS) et que je retrouve la même logique de filtrage qu'en Exécutions.

## Contexte

**Contexte Epic 13 — Sélection de targets à l'exécution et permissions par environnement (inventaire) :**

L'Epic 13 ajoute la sélection de targets lors de l'exécution d'une action et les permissions RBAC par environnement basées sur l'inventaire. Cette story ajoute un menu Calendrier pour les DBA afin qu'ils puissent consulter les exécutions planifiées sans accès Admin.

**État actuel des exécutions planifiées :**

Les exécutions planifiées sont actuellement accessibles via l'onglet Admin > "Exécutions planifiées" (`ScheduledExecutionsPage.tsx`), réservé aux profils DBOPS. Le composant affiche :
- Une table avec colonnes : Type (unique/récurrent), Action, Utilisateur, Date/heure planifiée, Statut, Environnement, Date de création
- Filtrage par statut, action, plage de dates
- RBAC : DBA voit ses propres exécutions, DBOPS voit toutes
- Indicateur visuel pour exécutions < 24h
- Modal de détails et d'annulation

**Objectif de cette story :**

Créer un **nouveau menu Calendrier** dans la navigation principale (TopNav) accessible aux **DBA et DBOPS** avec :
1. **Vue calendrier réelle** (semaine/mois) avec les exécutions planifiées positionnées sur les créneaux date/heure
2. **Filtres alignés** sur la page Exécutions : Action, Environnement, Plateforme, Technologie
3. **Accès DBA** : Les DBA ne voient que leurs propres exécutions planifiées, les DBOPS voient toutes
4. **Séparation Admin** : La page Admin "Exécutions planifiées" reste réservée aux DBOPS pour la gestion technique (annulation, toggle récurrence)

## Acceptance Criteria

### AC1 — Menu Calendrier visible dans la navigation principale

**Given** un utilisateur avec un profil DBA ou DBOPS accède au portail,
**When** il consulte la navigation principale (TopNav),
**Then** un menu **Calendrier** est visible avec l'icône `CalendarOutlined` et mène à la route `/calendar`.

**Given** un utilisateur avec un profil Business ou autre (non DBA/DBOPS),
**When** il consulte la navigation principale,
**Then** le menu Calendrier n'est pas visible (accès réservé DBA/DBOPS).

### AC2 — Vue calendrier réelle avec exécutions positionnées

**Given** un DBA ou DBOPS ouvre la page Calendrier (`/calendar`),
**When** la page est chargée,
**Then** une **vue calendrier** est affichée :
- **Vue semaine** par défaut avec les créneaux horaires (00h-23h)
- **Vue mois** disponible via onglets ou toggle
- Les exécutions planifiées sont positionnées sur les créneaux date/heure correspondants
- Chaque événement affiche au minimum : nom de l'action et environnement (badge coloré)
- Navigation semaine précédente/suivante, mois précédent/suivant

### AC3 — Détail au clic ou survol

**Given** la vue calendrier affiche des exécutions planifiées,
**When** l'utilisateur clique ou survole un événement,
**Then** un tooltip ou popover affiche le détail :
- Nom de l'action
- Environnement (dev, staging, prod)
- Plateforme d'exécution
- Technologie (Oracle, SQL Server, etc.)
- Utilisateur ayant planifié
- Date/heure planifiée exacte (UTC)
- Type (unique / récurrent)

### AC4 — Filtres alignés sur la page Exécutions

**Given** la page Calendrier est affichée,
**When** l'utilisateur consulte le panneau de filtres,
**Then** les filtres suivants sont disponibles, alignés sur `ExecutionsFiltersPanel` :
- **Action** : Select searchable avec les actions ayant des exécutions planifiées
- **Environnement** : Select (dev, staging, prod)
- **Plateforme** : Select (plateforme d'exécution)
- **Technologie** : Select (Oracle, SQL Server, DB2, PostgreSQL, MySQL, Workflow)
- **Plage de dates** (optionnel) : RangePicker pour filtrer la période affichée
- **Réinitialiser** : Bouton pour effacer tous les filtres

### AC5 — Persistance des filtres en URL et badge

**Given** des filtres sont appliqués,
**When** l'utilisateur consulte le calendrier,
**Then** :
- Seules les exécutions planifiées qui matchent les filtres sont affichées
- Les filtres sont persistés en URL (query params) comme Story 9.10
- Un badge indique le nombre de filtres actifs
- Un bouton permet de réinitialiser tous les filtres

### AC6 — Exécution planifiée visible dans le calendrier

**Given** un DBA a planifié une exécution (choix "Planifier" dans le wizard d'exécution),
**When** il ouvre la page Calendrier,
**Then** cette planification apparaît dans la vue calendrier au créneau correspondant.

### AC7 — RBAC DBA vs DBOPS

**Given** un DBA consulte la page Calendrier,
**When** les données sont chargées,
**Then** il voit uniquement **ses propres exécutions planifiées**.

**Given** un DBOPS consulte la page Calendrier,
**When** les données sont chargées,
**Then** il voit **toutes les exécutions planifiées** de tous les utilisateurs.

### AC8 — Lecture seule pour les DBA

**Given** la page Calendrier est accessible aux DBA,
**When** un DBA consulte une exécution planifiée,
**Then** il peut voir les détails mais **ne peut pas annuler** ou modifier (pas de bouton Annuler).

**And** la gestion technique des planifications (annulation, toggle récurrence) reste côté Admin pour DBOPS uniquement.

## Tasks / Subtasks

### Task 1 : Ajouter le menu Calendrier dans la navigation (AC: 1)

- [x] **Subtask 1.1** — Ajouter `calendar` dans `NavigationTabKey` (`types/common.ts`)
- [x] **Subtask 1.2** — Ajouter la configuration dans `TAB_CONFIG` avec `CalendarOutlined` et label "Calendrier"
- [x] **Subtask 1.3** — Ajouter la route `/calendar` dans `TAB_ROUTES`
- [x] **Subtask 1.4** — Modifier le backend pour inclure `calendar` dans `navigation_tabs` pour DBA et DBOPS
  - `core/rbac.py:_NAVIGATION_MAP` — ajouté 'calendar' pour profiles dbops, dba, dba_applicatif, dba_infrastructure
- [x] **Subtask 1.5** — Créer la route `/calendar` dans `App.tsx` avec lazy loading et CalendarGuard
- [x] **Subtask 1.6** — Tests unitaires TopNav : vérifier que DBA/DBOPS voient le menu Calendrier, Business non (5 tests ajoutés)

### Task 2 : Créer le composant CalendarPage (AC: 2, 6)

- [x] **Subtask 2.1** — Créer `frontend/src/pages/CalendarPage.tsx`
- [x] **Subtask 2.2** — Utiliser la bibliothèque `@fullcalendar/react` avec plugins :
  - `@fullcalendar/daygrid` (vue mois)
  - `@fullcalendar/timegrid` (vue semaine avec créneaux horaires)
  - `@fullcalendar/interaction` (clic événements)
- [x] **Subtask 2.3** — Afficher vue semaine par défaut, toggle vers vue mois via Segmented component
- [x] **Subtask 2.4** — Navigation précédent/suivant pour semaine et mois (FullCalendar headerToolbar)
- [x] **Subtask 2.5** — Charger les exécutions planifiées via `listScheduledExecutions()` et les mapper en événements FullCalendar
- [x] **Subtask 2.6** — Afficher chaque exécution avec titre = nom action, couleur selon environnement (ENV_COLORS)
- [x] **Subtask 2.7** — Tests unitaires CalendarPage : 18 tests (rendu, chargement données, affichage événements, filtres, RBAC)

### Task 3 : Implémenter le tooltip/popover de détails (AC: 3)

- [x] **Subtask 3.1** — Au clic sur un événement, afficher un Popover Ant Design avec détails :
  - Nom action, environnement (Tag coloré), utilisateur, date/heure planifiée (UTC), type (unique/récurrent)
  - Implémenté via EventDetailsPopover component avec Descriptions Ant Design
- [x] **Subtask 3.2** — Option survol (tooltip) pour aperçu rapide — EventContent avec SyncOutlined pour récurrents
- [x] **Subtask 3.3** — Tests unitaires : clic événement structure testé (AC3)

### Task 4 : Créer le panneau de filtres CalendarFiltersPanel (AC: 4, 5)

- [x] **Subtask 4.1** — Créer `frontend/src/components/calendar/CalendarFiltersPanel.tsx`
- [x] **Subtask 4.2** — Réutiliser les mêmes options que `ExecutionsFiltersPanel` :
  - Action (Select searchable via listActions)
  - Environnement (Select : dev, staging, prod)
  - Technologie (Select : ENGINE_OPTIONS)
  - Plateforme (Select via getIntegrations)
- [x] **Subtask 4.3** — Ajouter RangePicker optionnel pour filtrer la plage de dates
- [x] **Subtask 4.4** — Badge nombre de filtres actifs + bouton Réinitialiser
- [x] **Subtask 4.5** — Tests unitaires CalendarFiltersPanel : 17 tests

### Task 5 : Implémenter la persistance URL des filtres (AC: 5)

- [x] **Subtask 5.1** — Créer hook `useCalendarFilters()` pour synchroniser state React ↔ query params URL
- [x] **Subtask 5.2** — Params URL : `action_id`, `environment`, `engine`, `platform`, `start_date`, `end_date`
- [x] **Subtask 5.3** — Au chargement de la page, lire les params URL et initialiser les filtres (parseFiltersFromURL)
- [x] **Subtask 5.4** — À chaque changement de filtre, mettre à jour l'URL (replace, pas push) (buildURLFromFilters)
- [x] **Subtask 5.5** — Tests unitaires : filtres persistés en URL (AC5 tests dans CalendarPage.test.tsx)

### Task 6 : Adapter l'API GET /scheduled-executions pour filtres étendus (AC: 4, 7)

- [x] **Subtask 6.1** — Vérifier que l'API existante supporte les query params : `status`, `action_id`, `scheduled_from`, `scheduled_to`
- [x] **Subtask 6.2** — Ajouter support `environment` — filtre qs.filter(environment=environment_filter.lower())
- [x] **Subtask 6.3** — Ajouter support `engine` (technologie) — filtre qs.filter(action__engine__iexact=engine_filter)
- [x] **Subtask 6.4** — Ajouter support `platform` — filtre qs.filter(action__platform__iexact=platform_filter)
- [x] **Subtask 6.5** — Le RBAC existant filtre déjà DBA (ses exécutions) vs DBOPS (toutes) — vérifié OK
- [x] **Subtask 6.6** — Types ScheduledExecutionFilters et service frontend mis à jour pour ces filtres

### Task 7 : Implémenter le RBAC lecture seule DBA (AC: 7, 8)

- [x] **Subtask 7.1** — La page Calendrier ne contient pas de bouton Annuler (contrairement à Admin) — vérifié
- [x] **Subtask 7.2** — Le popover de détails affiche infos en lecture seule (pas d'actions) — EventDetailsPopover read-only
- [x] **Subtask 7.3** — Valider que le backend filtre bien DBA → ses exécutions, DBOPS → toutes — existant vérifié
- [x] **Subtask 7.4** — Tests : AC7/AC8 couverts dans CalendarPage.test.tsx

### Task 8 : Styling et thème calendrier (AC: 2)

- [x] **Subtask 8.1** — Appliquer le thème Ant Design au calendrier FullCalendar (CalendarPage.css avec CSS variables)
- [x] **Subtask 8.2** — Couleur événements selon environnement : dev=#1890ff, staging=#fa8c16, prod=#f5222d (ENV_COLORS)
- [x] **Subtask 8.3** — Indicateur visuel pour exécutions récurrentes (icône `SyncOutlined` dans EventContent)
- [x] **Subtask 8.4** — Support dark mode (CalendarPage.css avec :root.dark selectors)
- [x] **Subtask 8.5** — Thème cohérent : CSS variables --ant-color-* alignées avec design system

### Task 9 : Documentation et tests d'intégration (AC: tous)

- [x] **Subtask 9.1** — Tests d'intégration : 62 tests passent (TopNav, CalendarPage, CalendarFiltersPanel)
- [x] **Subtask 9.2** — Documentation Dev Notes mise à jour, code auto-documenté
- [x] **Subtask 9.3** — Accessibilité : aria-labels FullCalendar, locale fr, navigation clavier native

## Dev Notes

### Architecture technique

**Navigation :**
- `TopNav.tsx` utilise `TAB_CONFIG` et `TAB_ROUTES` pour la navigation
- Les onglets visibles sont filtrés par `user.navigation_tabs` côté backend
- Ajouter `calendar: { label: 'Calendrier', icon: <CalendarOutlined /> }` à `TAB_CONFIG`

**Composant calendrier — FullCalendar React :**
```bash
npm install @fullcalendar/react @fullcalendar/daygrid @fullcalendar/timegrid @fullcalendar/interaction
```

```tsx
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';

<FullCalendar
  plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
  initialView="timeGridWeek"
  headerToolbar={{
    left: 'prev,next today',
    center: 'title',
    right: 'timeGridWeek,dayGridMonth',
  }}
  events={calendarEvents}
  eventClick={handleEventClick}
  locale="fr"
  height="auto"
/>
```

**Mapping exécutions → événements FullCalendar :**
```typescript
interface CalendarEvent {
  id: string;
  title: string;
  start: string; // ISO date
  end?: string;
  backgroundColor: string;
  borderColor: string;
  extendedProps: {
    execution: ScheduledExecutionListItem;
  };
}

function mapToCalendarEvent(exec: ScheduledExecutionListItem): CalendarEvent {
  const effectiveDate = exec.recurring_pattern?.next_execution_date ?? exec.scheduled_at;
  const envColor = { dev: '#1890ff', staging: '#fa8c16', prod: '#f5222d' }[exec.environment] ?? '#888';
  return {
    id: String(exec.scheduled_execution_id),
    title: exec.action_name,
    start: effectiveDate,
    backgroundColor: envColor,
    borderColor: envColor,
    extendedProps: { execution: exec },
  };
}
```

### API existante

L'API `GET /api/v1/scheduled-executions` (Story 11.6) existe avec :
- Query params : `status`, `action_id`, `scheduled_from`, `scheduled_to`, `limit`, `offset`
- RBAC : DBA voit ses exécutions, DBOPS voit toutes
- Réponse inclut : `action_name`, `user_name`, `environment`, `scheduled_at`, `recurring_pattern`

**À ajouter pour cette story :**
- Query param `environment` pour filtrer par environnement
- Query param `engine` pour filtrer par technologie (JOIN avec ACTIONS_CATALOG.ENGINE)
- Query param `platform` pour filtrer par plateforme (JOIN avec INTEGRATIONS ou ACTIONS_CATALOG)

### Fichiers à créer/modifier

| Fichier | Action | Description |
|---------|--------|-------------|
| `frontend/src/types/common.ts` | MODIFY | Ajouter `calendar` à `NavigationTabKey` |
| `frontend/src/components/layout/TopNav.tsx` | MODIFY | Ajouter config Calendrier dans `TAB_CONFIG` et `TAB_ROUTES` |
| `frontend/src/pages/CalendarPage.tsx` | CREATE | Page calendrier avec FullCalendar |
| `frontend/src/components/calendar/CalendarFiltersPanel.tsx` | CREATE | Panneau filtres aligné sur ExecutionsFiltersPanel |
| `frontend/src/hooks/useCalendarFilters.ts` | CREATE | Hook persistance URL des filtres |
| `frontend/src/App.tsx` | MODIFY | Ajouter route `/calendar` avec lazy loading |
| `django_backend/core/rbac.py` | MODIFY | Ajouter 'calendar' dans _NAVIGATION_MAP pour DBA/DBOPS |
| `django_backend/executions/views.py` | MODIFY | Ajouter query params `environment`, `engine`, `platform` |
| `frontend/src/pages/CalendarPage.test.tsx` | CREATE | Tests unitaires CalendarPage |
| `frontend/src/components/calendar/CalendarFiltersPanel.test.tsx` | CREATE | Tests unitaires filtres |

### Dépendances techniques

| Package | Version | Usage |
|---------|---------|-------|
| `@fullcalendar/react` | ^6.x | Composant calendrier React |
| `@fullcalendar/daygrid` | ^6.x | Vue mois |
| `@fullcalendar/timegrid` | ^6.x | Vue semaine avec créneaux horaires |
| `@fullcalendar/interaction` | ^6.x | Clic événements |
| `dayjs` | existant | Manipulation dates |
| `antd` | existant | Popover, Tag, Select pour filtres |

### Références aux Stories précédentes

| Story | Implémentation | Réutilisable |
|-------|----------------|--------------|
| **11.6** | `ScheduledExecutionsPage.tsx`, API GET /scheduled-executions | Oui — API et types existants |
| **11.7** | Récurrence daily/weekly, toggle is_active | Oui — affichage récurrence |
| **11.8** | Cron expressions avancées | Oui — describeCronExpression() |
| **9.10** | ExecutionsFiltersPanel, persistance URL | Oui — pattern filtres URL |

### Project Structure Notes

- La page Calendrier sera dans `pages/CalendarPage.tsx` comme les autres pages principales
- Les composants spécifiques au calendrier iront dans `components/calendar/`
- Réutiliser le service `scheduled_execution_service.ts` existant
- Le hook `useCalendarFilters` suit le pattern de `useExecutionFilters` (Story 9.10)

### Points d'attention

1. **Performance** — Si beaucoup d'exécutions planifiées, limiter la fenêtre de chargement (ex: mois courant ± 1 mois)

2. **Fuseaux horaires** — Les dates sont stockées en UTC ; FullCalendar gère la conversion en heure locale automatiquement

3. **Récurrences** — Afficher les exécutions récurrentes avec leur `next_execution_date`, pas toutes les occurrences futures

4. **Responsive** — FullCalendar est responsive, mais vérifier l'affichage mobile

5. **Accessibilité** — FullCalendar a des options d'accessibilité à configurer (aria-labels)

### References

- [Source: frontend/src/components/admin/ScheduledExecutionsPage.tsx] — Page Admin exécutions planifiées existante
- [Source: frontend/src/components/layout/TopNav.tsx] — Navigation principale
- [Source: frontend/src/components/executions/ExecutionsFiltersPanel.tsx] — Filtres page Exécutions (pattern à suivre)
- [Source: frontend/src/services/scheduled_execution_service.ts] — Service API exécutions planifiées
- [Source: _bmad-output/planning-artifacts/epics.md#Story 13.6] — Critères d'acceptation

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- 62/62 tests frontend passent (TopNav, CalendarPage, CalendarFiltersPanel)

### Completion Notes List

- Implémenté menu Calendrier visible pour DBA/DBOPS, masqué pour Business
- Créé CalendarPage avec FullCalendar React (vue semaine/mois)
- Événements colorés par environnement (dev=blue, staging=orange, prod=red)
- Indicateur récurrence avec icône SyncOutlined
- Popover détails au clic (lecture seule, pas de bouton Annuler)
- Filtres alignés sur ExecutionsFiltersPanel (action, env, engine, platform, dates)
- Persistance URL des filtres via useCalendarFilters hook
- API backend enrichie avec filtres environment, engine, platform
- Support dark mode complet
- Tests unitaires complets (62 tests)
- **Code review (2026-02-06):** AC3 — engine/platform ajoutés au serializer et au popover ; AC5 — plage de dates URL appliquée à l’API ; parseFiltersFromURL robuste (action_id NaN) ; console.error limité au dev ; doc Fichiers corrigée (rbac.py)

### Change Log

- 2026-02-05: Story 13.6 créée — analyse exhaustive du contexte, 9 tasks définies
- 2026-02-06: Story 13.6 implémentée — toutes les tâches complétées, 62 tests passent
- 2026-02-06: Code review — 2 HIGH + 3 MEDIUM corrigés (AC3 engine/platform, AC5 dates URL, action_id NaN, console.error, doc rbac.py)

### File List

**Frontend - Created:**
- idp-portal/frontend/src/pages/CalendarPage.tsx
- idp-portal/frontend/src/pages/CalendarPage.css
- idp-portal/frontend/src/pages/CalendarPage.test.tsx
- idp-portal/frontend/src/components/calendar/CalendarFiltersPanel.tsx
- idp-portal/frontend/src/components/calendar/CalendarFiltersPanel.test.tsx
- idp-portal/frontend/src/hooks/useCalendarFilters.ts

**Frontend - Modified:**
- idp-portal/frontend/src/types/common.ts (NavigationTabKey)
- idp-portal/frontend/src/types/api.ts (ScheduledExecutionFilters)
- idp-portal/frontend/src/components/layout/TopNav.tsx (TAB_CONFIG, TAB_ROUTES, CalendarOutlined)
- idp-portal/frontend/src/components/layout/TopNav.test.tsx (calendar menu tests)
- idp-portal/frontend/src/App.tsx (CalendarPage route, CalendarGuard)
- idp-portal/frontend/src/services/scheduled_execution_service.ts (extended filters)

**Backend - Modified:**
- idp-portal/django_backend/core/rbac.py (_NAVIGATION_MAP for calendar)
- idp-portal/django_backend/executions/views.py (environment, engine, platform filters)
- idp-portal/django_backend/executions/serializers.py (ScheduledExecutionListItemSerializer: engine, platform for AC3)

**Dependencies - Added:**
- @fullcalendar/react ^6.x
- @fullcalendar/daygrid ^6.x
- @fullcalendar/timegrid ^6.x
- @fullcalendar/interaction ^6.x
