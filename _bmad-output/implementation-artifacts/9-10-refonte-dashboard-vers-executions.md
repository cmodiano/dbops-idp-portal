# Story 9.10: Refonte dashboard vers exécutions

Status: review

<!-- Note: Validation optionnelle. Exécuter validate-create-story pour contrôle qualité avant dev-story. -->

## Story

En tant qu'**utilisateur DBA consultant les exécutions et statistiques**,
je veux **un point d'accès unifié dans la page Exécutions pour filtrer, analyser et suivre toutes les activités**,
afin que **je n'aie plus besoin de naviguer entre Dashboard et Exécutions pour accomplir mes tâches opérationnelles quotidiennes**.

## Contexte

**État actuel (Post-Story 9-9):**

La navigation actuelle sépare artificiellement deux aspects d'un même besoin opérationnel:

1. **Page Exécutions** (`/executions`):
   - StatCards (4 métriques: exécutions du jour, taux de succès, en cours, en erreur) - **Déplacées depuis Dashboard par Story 9-4**
   - Liste/tableau des exécutions avec colonnes: Statut, Action, Technologie, Plateforme, Utilisateur, Environnement, Date, Durée
   - Tabs: "Toutes les exécutions" vs "Mes exécutions" (scope-aware)
   - Pending Approvals section (pour DBA/DBOPS)
   - **Filtrage limité**: Uniquement scope (mine/all) + tri colonnes (Date, Action)
   - Click sur ligne → Drawer avec ExecutionTimeline détaillée

2. **Dashboard** (`/dashboard`):
   - Rend uniquement `ReportingDashboard` component
   - **TrendLineChart**: Graphique lignes Success (vert) vs Failed (rouge) sur période temporelle
   - **Filtres avancés**: Engine/Technology, Environment, Tags (multi-select), Status, Date range (custom + presets 7/14/30/90j)
   - **AdvancedFiltersPanel**: Panel filtres avec badge count + reset button
   - **Autres charts**: TechnologyBarChart, EnvironmentBarChart (analytics avancées)
   - **Mode Comparison**: Analyse comparative (Technology vs Technology, Environment vs Environment, Period vs Period)
   - **Export**: CSV/PDF des données filtrées
   - Lien "Voir toutes les executions" vers `/executions`

**Problématique identifiée:**

1. **Fragmentation du workflow DBA**: Un DBA analysant un problème doit:
   - Aller sur Dashboard pour voir la tendance échecs/succès et identifier un pic d'erreurs
   - Appliquer des filtres (ex: "Environnement: PROD, 7 derniers jours")
   - Cliquer "Voir toutes les exécutions"
   - **Perdre ses filtres** → la page Exécutions n'a pas de filtres avancés
   - Chercher manuellement dans le tableau pour trouver les exécutions problématiques
   - **Navigation inefficace**: 3-4 clics + scroll, perte de contexte

2. **Duplication StatCards**: Story 9-4 a déjà déplacé les StatCards vers Exécutions. Le Dashboard ne montre plus de KPI "exécutions du jour" — il y a une **incohérence** entre Dashboard (analytics) et Exécutions (opérationnel).

3. **Dashboard devenu "Analytics avancées uniquement"**: Le Dashboard est désormais un outil d'analyse comparative et de reporting pour DBOPS, mais pas pour les opérations quotidiennes. Les DBA cherchant une exécution spécifique n'ont **aucun outil de filtrage** dans Exécutions.

4. **TrendLineChart isolé**: Le graphique de tendance Success/Failed est pertinent pour un DBA dans Exécutions, mais il est caché dans Dashboard. Un DBA ne peut pas voir "combien d'échecs aujourd'hui" **et** "quelle tendance depuis 7 jours" **au même endroit**.

**Objectif de cette story:**

Refactoriser la navigation en **consolidant les fonctionnalités opérationnelles dans Exécutions** et en repositionnant le Dashboard comme **outil d'analytics avancées pour DBOPS uniquement**.

**Bénéfices attendus:**

- **Workflow DBA simplifié**: Filtrer + voir tendance + consulter liste des exécutions dans un seul écran
- **Filtrage avancé accessible**: Date range, action, technologie, tags, statut, environnement directement dans Exécutions
- **Contexte préservé**: Pas de navigation entre pages pour affiner la recherche
- **Dashboard repositionné**: Analytics avancées, comparaisons, exports pour DBOPS (pas pour opérations quotidiennes)
- **Réduction charge cognitive**: Un seul point d'entrée pour "Je cherche une exécution spécifique" ou "Je veux voir l'activité récente"

## Acceptance Criteria

### AC1 - Suppression Dashboard classique et repositionnement

**Given** je suis un utilisateur DBA ou DBOPS
**When** je consulte la navigation principale (Sidebar)
**Then** le lien "Dashboard" n'existe plus
**And** un nouveau lien "Analytics" (ou "Reporting") apparaît pour accéder à `/reporting` (ou `/dashboard` renommé en "Analytics")
**And** ce lien affiche uniquement `ReportingDashboard` pour analyses avancées (comparison mode, exports, charts multiples)

**Given** je suis un utilisateur non-DBA (client business)
**When** je consulte la navigation principale
**Then** le lien "Analytics" est **absent** (RBAC: réservé DBOPS)
**And** je vois uniquement "Catalogue" et "Exécutions" (scope="mine" auto-activé)

**Note:** Le contenu du ReportingDashboard reste inchangé (charts, comparison mode, exports) — seule la **navigation** change.

### AC2 - Déplacement TrendLineChart dans Exécutions

**Given** je consulte la page Exécutions (`/executions`)
**When** la page se charge avec StatCards en haut (story 9-4)
**Then** une nouvelle section apparaît **immédiatement sous les StatCards** contenant:
  - **TrendLineChart**: Graphique lignes Success (vert) vs Failed (rouge)
  - **Données synchronisées**: Le graphique reflète les mêmes filtres appliqués aux StatCards et au tableau d'exécutions
  - **Période affichée**: 7 derniers jours par défaut (aligne avec preset date range)
  - **Responsive**: Graphique prend toute la largeur (Col span={24})

**And** le graphique se met à jour dynamiquement quand les filtres sont appliqués (ex: filtre "Environment: PROD" → le graphique montre uniquement les exécutions PROD)

### AC3 - Ajout filtres avancés dans Exécutions (UI)

**Given** je consulte la page Exécutions
**When** la page se charge
**Then** une nouvelle section **AdvancedFiltersPanel** apparaît au-dessus du tableau d'exécutions (sous StatCards + TrendLineChart)
**And** le panel contient les contrôles suivants (alignement horizontal sur 2 lignes):

**Ligne 1 - Filtres principaux:**
- **Date Range Picker** (RangePicker Ant Design):
  - Label: "Période"
  - Placeholder: "Sélectionner dates"
  - Format: DD/MM/YYYY
  - Presets rapides: "7 derniers jours" (default), "14 jours", "30 jours", "90 jours", "Tout"
  - Largeur: Col span={8} (md) ou span={24} (xs)

- **Action Select** (Select searchable):
  - Label: "Action"
  - Placeholder: "Toutes les actions"
  - Options: Liste des actions disponibles dans le catalogue (filtrées par RBAC utilisateur)
  - Searchable: true
  - Largeur: Col span={8} (md) ou span={24} (xs)

- **Technologie Select** (Select):
  - Label: "Technologie"
  - Placeholder: "Toutes les technologies"
  - Options: Oracle, SQL Server, DB2, PostgreSQL, MySQL, Workflow
  - Largeur: Col span={8} (md) ou span={24} (xs)

**Ligne 2 - Filtres secondaires:**
- **Tags Select** (Select mode="multiple"):
  - Label: "Tags"
  - Placeholder: "Tous les tags"
  - Options: Liste des tags disponibles (chargés depuis API `/tags`)
  - Multi-select avec badges
  - Largeur: Col span={8} (md) ou span={24} (xs)

- **Statut Select** (Select):
  - Label: "Statut"
  - Placeholder: "Tous les statuts"
  - Options: SUBMITTED, PENDING_APPROVAL, RUNNING, COMPLETED, FAILED, CANCELLED, REJECTED
  - Labels français: "Soumise", "En attente", "En cours", "Terminée", "Échouée", "Annulée", "Rejetée"
  - Largeur: Col span={8} (md) ou span={24} (xs)

- **Environnement Select** (Select):
  - Label: "Environnement"
  - Placeholder: "Tous les environnements"
  - Options: DEV, STAGING, PROD
  - Largeur: Col span={4} (md) ou span={24} (xs)

- **Boutons actions**:
  - **Appliquer** (Button type="primary"): Déclenche le fetch avec filtres
  - **Réinitialiser** (Button): Reset tous les filtres + badge avec nombre de filtres actifs
  - Largeur: Col span={4} (md) ou span={24} (xs)

**And** le panel est **collapsible** (optionnel) avec icône DownOutlined/UpOutlined pour masquer/afficher

### AC4 - Application des filtres backend (API)

**Given** l'endpoint `/api/v1/executions` existe déjà avec paramètres `scope`, `limit`, `offset`, `sort_by`
**When** les filtres avancés sont appliqués dans le frontend
**Then** l'API `/api/v1/executions` accepte les nouveaux paramètres query suivants:
  - `start_date` (string ISO 8601 ou date): Date début (inclusive)
  - `end_date` (string ISO 8601 ou date): Date fin (inclusive)
  - `action_id` (int | null): ID de l'action filtrée
  - `engine` (ActionEngine | null): Technologie filtrée (Oracle, SQL Server, DB2, etc.)
  - `tags` (list[str] | null): Liste de tags (logique AND: exécution doit avoir **tous** les tags)
  - `status` (ExecutionStatusType | null): Statut filtré
  - `environment` (ExecutionEnvironment | null): Environnement filtré

**And** le repository `execution_repository.py` applique les filtres SQL via clauses WHERE:
  - `start_date` / `end_date`: `e.CREATED_AT BETWEEN :start_date AND :end_date`
  - `action_id`: `e.ACTION_ID = :action_id`
  - `engine`: `ac.ENGINE = :engine` (JOIN sur ACTIONS_CATALOG déjà présent Story 9-9)
  - `tags`: JOIN sur table de liaison ACTION_TAGS + filter avec ALL/ANY (selon logique métier)
  - `status`: `e.STATUS = :status`
  - `environment`: `e.ENVIRONMENT = :environment`

**And** les filtres sont **combinables** (logique AND entre tous les filtres actifs)

### AC5 - Synchronisation TrendLineChart avec filtres

**Given** les filtres avancés sont appliqués (ex: "Environment: PROD, Status: FAILED, 30 derniers jours")
**When** le fetch des exécutions se termine
**Then** le **TrendLineChart** se met à jour avec les données filtrées:
  - Appel API `/api/v1/executions/timeseries` (ou endpoint similaire) avec les mêmes filtres
  - Le graphique affiche uniquement les exécutions correspondant aux filtres
  - L'axe X s'ajuste automatiquement à la période filtrée
  - Les lignes Success/Failed reflètent les données filtrées

**Given** aucun filtre n'est appliqué (état par défaut)
**When** la page se charge
**Then** le TrendLineChart affiche les 7 derniers jours (preset par défaut) pour toutes les exécutions (scope-aware: mine ou all)

### AC6 - Synchronisation StatCards avec filtres

**Given** les filtres avancés sont appliqués
**When** le fetch des exécutions se termine
**Then** les **StatCards** (4 métriques) se mettent à jour:
  - **Exécutions du jour**: Compte uniquement les exécutions filtrées créées aujourd'hui
  - **Taux de succès**: Calcul basé uniquement sur les exécutions filtrées
  - **En cours**: Compte uniquement les exécutions filtrées avec status RUNNING/SUBMITTED/PENDING_APPROVAL
  - **En erreur**: Compte uniquement les exécutions filtrées avec status FAILED

**Given** aucun filtre n'est appliqué
**When** la page se charge
**Then** les StatCards affichent les métriques globales (7 derniers jours par défaut, scope-aware)

**Note:** Les StatCards doivent refléter **la période filtrée** (ex: si date range = "30 derniers jours", "Exécutions du jour" devient "Exécutions de la période")

### AC7 - Persistence des filtres (URL query params)

**Given** j'applique des filtres (ex: Environment=PROD, Engine=Oracle, Date range=30j)
**When** je clique sur une exécution pour ouvrir le Drawer
**Then** l'URL se met à jour avec query params: `/executions?environment=PROD&engine=Oracle&period=30`
**And** le Drawer s'ouvre sans perdre les filtres appliqués

**Given** je partage l'URL `/executions?environment=PROD&status=FAILED&period=7` avec un collègue
**When** il ouvre le lien
**Then** la page Exécutions se charge avec les filtres pré-appliqués (Environment=PROD, Status=FAILED, 7 derniers jours)
**And** le tableau et les charts reflètent ces filtres

**Given** je rafraîchis la page (F5) avec des filtres appliqués
**When** la page se recharge
**Then** les filtres restent actifs (lus depuis query params)

### AC8 - Badge nombre de filtres actifs

**Given** aucun filtre n'est appliqué
**When** je consulte le panel de filtres
**Then** le bouton "Réinitialiser" est **disabled**
**And** aucun badge n'apparaît

**Given** j'applique 3 filtres (ex: Environment=PROD, Status=FAILED, Date range=30j)
**When** je consulte le panel de filtres
**Then** un **Badge** avec le nombre "3" apparaît à côté du titre du panel (ou sur le bouton "Réinitialiser")
**And** le badge est coloré (bleu primaire)
**And** le bouton "Réinitialiser" devient **enabled**

**Given** je clique sur "Réinitialiser"
**When** l'action se termine
**Then** tous les filtres sont supprimés
**And** le badge disparaît
**And** les StatCards, TrendLineChart, et tableau se mettent à jour avec les données par défaut

### AC9 - État vide et skeleton loading

**Given** la page Exécutions se charge avec filtres appliqués
**When** le fetch est en cours
**Then** un **skeleton** (shimmer) s'affiche:
  - StatCards: 4 Card.Meta skeletons
  - TrendLineChart: Skeleton.Input pour le graphique
  - Tableau: 10 lignes skeleton (déjà implémenté Story 9-9)

**Given** aucun résultat ne correspond aux filtres appliqués
**When** le fetch se termine avec tableau vide
**Then** un message "Aucune exécution trouvée pour les filtres sélectionnés" s'affiche dans le tableau
**And** les StatCards affichent tous "0" ou "—"
**And** le TrendLineChart affiche "Aucune donnée sur la période"

### AC10 - Navigation et RBAC

**Given** je suis un utilisateur DBA ou DBOPS
**When** je consulte la sidebar navigation
**Then** je vois les liens suivants (ordre):
  1. **Catalogue** (`/catalog`)
  2. **Exécutions** (`/executions`)
  3. **Analytics** (`/analytics` ou `/reporting`) — nouveau nom pour Dashboard
  4. **Admin** (`/admin`)

**Given** je suis un utilisateur non-DBA (client business)
**When** je consulte la sidebar navigation
**Then** je vois uniquement:
  1. **Catalogue** (`/catalog`)
  2. **Exécutions** (`/executions`) — scope="mine" auto-activé
**And** les liens "Analytics" et "Admin" sont **absents** (RBAC)

**Given** un utilisateur non-DBA tente d'accéder à `/analytics` directement (URL)
**When** la route se charge
**Then** une page **403 Forbidden** ou une redirection vers `/catalog` s'affiche
**And** un message toast "Accès non autorisé" apparaît

## Tasks / Subtasks

### Task 1: Analyse et préparation (AC: all)

- [ ] 1.1 Lire `ReportingDashboard.tsx` pour comprendre structure filtres et charts
- [ ] 1.2 Identifier composants réutilisables:
  - [ ] `AdvancedFiltersPanel` (peut être extrait et adapté)
  - [ ] `TrendLineChart` (doit être déplacé)
  - [ ] Hooks: `useDashboardStats`, `useDashboardTimeSeriesData`
- [ ] 1.3 Lire `ExecutionsPage.tsx` structure actuelle (StatCards, Tabs, Table)
- [ ] 1.4 Planifier layout: StatCards → TrendLineChart → AdvancedFiltersPanel → Table
- [ ] 1.5 Identifier API endpoints à modifier/créer:
  - [ ] `/executions` avec nouveaux paramètres de filtrage
  - [ ] `/executions/timeseries` pour TrendLineChart (vérifier si existe)
  - [ ] `/tags` pour charger liste tags disponibles

### Task 2: Backend - Enrichir endpoint /executions avec filtres (AC: #4)

- [ ] 2.1 Ouvrir `backend/app/api/routes/executions.py`
- [ ] 2.2 Ajouter paramètres query à `GET /executions`:
  - [ ] `start_date: date | None = None`
  - [ ] `end_date: date | None = None`
  - [ ] `action_id: int | None = None`
  - [ ] `engine: ActionEngine | None = None`
  - [ ] `tags: str | None = None` (comma-separated list, ex: "backup,production")
  - [ ] `status: ExecutionStatusType | None = None`
  - [ ] `environment: ExecutionEnvironment | None = None`
- [ ] 2.3 Valider paramètres (ex: start_date <= end_date, tags parsing)
- [ ] 2.4 Passer paramètres à `execution_repository.list_executions()`
- [ ] 2.5 Modifier signature `list_executions()` dans `execution_repository.py`:
  - [ ] Ajouter paramètres optionnels: `start_date`, `end_date`, `action_id`, `engine`, `tags_list`, `status`, `environment`
- [ ] 2.6 Construire clauses SQL WHERE dynamiques:
  - [ ] `WHERE 1=1` (base clause)
  - [ ] `AND e.CREATED_AT >= :start_date` si start_date présent
  - [ ] `AND e.CREATED_AT <= :end_date` si end_date présent
  - [ ] `AND e.ACTION_ID = :action_id` si action_id présent
  - [ ] `AND ac.ENGINE = :engine` si engine présent
  - [ ] `AND e.STATUS = :status` si status présent
  - [ ] `AND e.ENVIRONMENT = :environment` si environment présent
- [ ] 2.7 Implémenter filtrage tags (JOIN sur ACTION_TAGS si table existe):
  - [ ] Si tags_list présent: `JOIN ACTION_TAGS at ON ac.ID = at.ACTION_ID WHERE at.TAG_NAME IN (:tags)`
  - [ ] Grouper avec HAVING COUNT(DISTINCT at.TAG_NAME) = :tags_count (logique AND)
- [ ] 2.8 Tester manuellement endpoint avec curl ou httpx:
  - [ ] `GET /executions?environment=PROD&status=FAILED&start_date=2026-01-01`

### Task 3: Backend - Endpoint /executions/stats avec filtres (AC: #6)

- [ ] 3.1 Vérifier si endpoint `/executions/stats` existe déjà (créé Story 9-4)
- [ ] 3.2 Si existe: ajouter paramètres de filtrage (mêmes que Task 2.2)
- [ ] 3.3 Si n'existe pas: créer endpoint `GET /executions/stats`:
  - [ ] Paramètres: scope, start_date, end_date, action_id, engine, tags, status, environment
  - [ ] Retourner `DashboardStats` (executions_jour, taux_succes_pct, en_cours, en_erreur)
- [ ] 3.4 Modifier repository `get_dashboard_stats()` pour accepter filtres
- [ ] 3.5 Adapter requêtes SQL avec clauses WHERE (même logique que Task 2.6)
- [ ] 3.6 Ajuster calcul "Exécutions du jour":
  - [ ] Si start_date/end_date présents: "Exécutions de la période" (total dans range)
  - [ ] Sinon: "Exécutions du jour" (créées aujourd'hui)
- [ ] 3.7 Tester endpoint avec filtres:
  - [ ] `GET /executions/stats?scope=all&environment=PROD&start_date=2026-01-01&end_date=2026-01-31`

### Task 4: Backend - Endpoint /executions/timeseries avec filtres (AC: #5)

- [ ] 4.1 Vérifier si endpoint `/executions/timeseries` existe (utilisé par ReportingDashboard)
- [ ] 4.2 Si existe: ajouter paramètres de filtrage (mêmes que Task 2.2)
- [ ] 4.3 Si n'existe pas: créer endpoint `GET /executions/timeseries`:
  - [ ] Paramètres: scope, start_date, end_date, action_id, engine, tags, status, environment
  - [ ] Retourner `list[DashboardTimeSeriesPoint]` (date, success, failed)
- [ ] 4.4 Créer fonction repository `get_timeseries_data()` avec filtres:
  - [ ] Requête SQL: `SELECT DATE(e.CREATED_AT) as date, COUNT(CASE WHEN e.STATUS='COMPLETED' THEN 1 END) as success, COUNT(CASE WHEN e.STATUS='FAILED' THEN 1 END) as failed FROM EXECUTIONS e ...`
  - [ ] Appliquer clauses WHERE (même logique que Task 2.6)
  - [ ] Grouper par date: `GROUP BY DATE(e.CREATED_AT) ORDER BY date ASC`
- [ ] 4.5 Tester endpoint:
  - [ ] `GET /executions/timeseries?scope=all&environment=PROD&start_date=2026-01-01&end_date=2026-01-31`
  - [ ] Vérifier que response contient array de points [{date, success, failed}, ...]

### Task 5: Backend - Endpoint /tags pour charger liste tags (AC: #3)

- [ ] 5.1 Créer endpoint `GET /api/v1/tags`:
  - [ ] Retourner liste des tags disponibles (array de strings)
  - [ ] Filtrer par RBAC utilisateur: ne retourner que les tags des actions visibles
- [ ] 5.2 Créer fonction repository `get_available_tags()`:
  - [ ] Requête SQL: `SELECT DISTINCT at.TAG_NAME FROM ACTION_TAGS at JOIN ACTIONS_CATALOG ac ON at.ACTION_ID = ac.ID WHERE ...`
  - [ ] Appliquer filtres RBAC (JOIN sur RBAC_POLICIES si nécessaire)
- [ ] 5.3 Tester endpoint:
  - [ ] `GET /tags` → response: ["backup", "production", "maintenance", ...]

### Task 6: Frontend - Types et interfaces (AC: #3, #4)

- [ ] 6.1 Ouvrir `frontend/src/types/api.ts`
- [ ] 6.2 Créer interface `ExecutionFilters`:
  - [ ] `scope?: 'mine' | 'all';`
  - [ ] `start_date?: string | null;`
  - [ ] `end_date?: string | null;`
  - [ ] `action_id?: number | null;`
  - [ ] `engine?: ActionEngine | null;`
  - [ ] `tags?: string[] | null;`
  - [ ] `status?: ExecutionStatusType | null;`
  - [ ] `environment?: ExecutionEnvironment | null;`
- [ ] 6.3 Ajouter types pour paramètres API:
  - [ ] `ExecutionListParams` extends `ExecutionFilters` avec `limit`, `offset`, `sort_by`
  - [ ] `DashboardStatsParams` extends `ExecutionFilters`
  - [ ] `TimeSeriesParams` extends `ExecutionFilters`

### Task 7: Frontend - Service API pour filtres (AC: #4, #5, #6)

- [ ] 7.1 Ouvrir `frontend/src/services/executionService.ts`
- [ ] 7.2 Modifier fonction `fetchExecutions()`:
  - [ ] Ajouter paramètre `filters: ExecutionFilters`
  - [ ] Construire query params: `const params = new URLSearchParams({ scope, limit, offset, ...filters })`
  - [ ] Serializer tags: `tags.join(',')` si présent
  - [ ] Appeler: `axios.get('/api/v1/executions', { params })`
- [ ] 7.3 Modifier fonction `fetchDashboardStats()` (si existe):
  - [ ] Ajouter paramètre `filters: ExecutionFilters`
  - [ ] Construire query params avec filtres
- [ ] 7.4 Créer ou modifier fonction `fetchTimeSeriesData()`:
  - [ ] Paramètres: `scope`, `filters: ExecutionFilters`
  - [ ] Appeler: `axios.get('/api/v1/executions/timeseries', { params })`
- [ ] 7.5 Créer fonction `fetchTags()`:
  - [ ] Appeler: `axios.get('/api/v1/tags')`
  - [ ] Retourner: `Promise<string[]>`

### Task 8: Frontend - Hook useExecutionFilters (AC: #7, #8)

- [ ] 8.1 Créer fichier `frontend/src/hooks/useExecutionFilters.ts`
- [ ] 8.2 Implémenter hook custom:
  - [ ] State: `filters: ExecutionFilters` (initial depuis URL query params)
  - [ ] State: `activeFilterCount: number` (compteur filtres actifs)
  - [ ] Fonction: `applyFilters(newFilters: ExecutionFilters)` → met à jour state + URL
  - [ ] Fonction: `resetFilters()` → clear state + URL
  - [ ] Effet: `useEffect(() => { syncFiltersFromURL() }, [location.search])`
  - [ ] Effet: `useEffect(() => { updateActiveFilterCount() }, [filters])`
- [ ] 8.3 Implémenter `syncFiltersFromURL()`:
  - [ ] Parser query params: `new URLSearchParams(location.search)`
  - [ ] Deserializer tags: `params.get('tags')?.split(',')`
  - [ ] Mapper preset period ("7j", "30j") vers start_date/end_date
  - [ ] Set state `filters`
- [ ] 8.4 Implémenter `applyFilters()`:
  - [ ] Update state `filters`
  - [ ] Construire query string: `new URLSearchParams(filters).toString()`
  - [ ] Navigate: `navigate({ search: queryString })`
- [ ] 8.5 Implémenter `resetFilters()`:
  - [ ] Reset state à valeurs par défaut (scope="all", period="7j")
  - [ ] Navigate: `navigate({ search: '' })`
- [ ] 8.6 Calculer `activeFilterCount`:
  - [ ] Compter nombre de filtres non-null/non-default
  - [ ] Exclude `scope` du compteur (c'est un tab, pas un filtre)

### Task 9: Frontend - Composant AdvancedFiltersPanel (AC: #3, #8)

- [ ] 9.1 Créer fichier `frontend/src/components/executions/AdvancedFiltersPanel.tsx`
- [ ] 9.2 Props:
  - [ ] `filters: ExecutionFilters`
  - [ ] `onApplyFilters: (filters: ExecutionFilters) => void`
  - [ ] `onResetFilters: () => void`
  - [ ] `activeFilterCount: number`
- [ ] 9.3 State local pour form values (avant apply)
- [ ] 9.4 Layout: Card avec Collapse (optionnel) + Form Ant Design
- [ ] 9.5 Ligne 1 - Contrôles:
  - [ ] **DatePicker.RangePicker** pour start_date/end_date:
    - [ ] Presets: 7j (default), 14j, 30j, 90j, "Tout"
    - [ ] onChange → update local state
  - [ ] **Select action** (searchable):
    - [ ] Charger liste actions depuis API `/actions` (existant)
    - [ ] Filtrer par RBAC (API retourne uniquement actions autorisées)
  - [ ] **Select technologie**:
    - [ ] Options statiques: Oracle, SQL Server, DB2, PostgreSQL, MySQL, Workflow
- [ ] 9.6 Ligne 2 - Contrôles:
  - [ ] **Select tags** (mode="multiple"):
    - [ ] Charger liste tags depuis `useTags()` hook (à créer Task 10)
    - [ ] maxTagCount={3} (afficher max 3 badges, puis "+N")
  - [ ] **Select statut**:
    - [ ] Options: SUBMITTED, PENDING_APPROVAL, RUNNING, COMPLETED, FAILED, CANCELLED, REJECTED
    - [ ] Labels français (utiliser `STATUS_CONFIG` existant)
  - [ ] **Select environnement**:
    - [ ] Options: DEV, STAGING, PROD
- [ ] 9.7 Boutons:
  - [ ] **Appliquer** (Button type="primary") → `onApplyFilters(localState)`
  - [ ] **Réinitialiser** (Button) → `onResetFilters()` + clear local state
  - [ ] Badge nombre filtres actifs sur bouton "Réinitialiser" si `activeFilterCount > 0`
- [ ] 9.8 Responsive: Col spans adaptés (xs=24, md=8/4 selon contrôle)

### Task 10: Frontend - Hook useTags (AC: #3)

- [ ] 10.1 Créer fichier `frontend/src/hooks/useTags.ts`
- [ ] 10.2 Utiliser React Query (ou useState + useEffect):
  - [ ] `const { data: tags, isLoading } = useQuery('tags', fetchTags)`
- [ ] 10.3 Retourner: `{ tags: string[], isLoading: boolean }`
- [ ] 10.4 Cache: TTL 5 minutes (tags changent rarement)

### Task 11: Frontend - Déplacer TrendLineChart (AC: #2, #5)

- [ ] 11.1 Lire `frontend/src/components/dashboard/reporting/TrendLineChart.tsx`
- [ ] 11.2 Déplacer composant vers `frontend/src/components/executions/TrendLineChart.tsx`
  - [ ] OU: Laisser dans `dashboard/reporting/` et importer dans ExecutionsPage (réutilisabilité)
- [ ] 11.3 Vérifier props: `data: DashboardTimeSeriesPoint[]`, `loading: boolean`
- [ ] 11.4 Ajouter prop optionnelle `title?: string` pour personnaliser titre
- [ ] 11.5 Aucun changement logique — composant réutilisé tel quel

### Task 12: Frontend - Hook useTrendLineData avec filtres (AC: #5)

- [ ] 12.1 Créer fichier `frontend/src/hooks/useTrendLineData.ts`
- [ ] 12.2 Paramètres: `scope: 'mine' | 'all'`, `filters: ExecutionFilters`
- [ ] 12.3 Utiliser React Query:
  - [ ] `useQuery(['timeseries', scope, filters], () => fetchTimeSeriesData(scope, filters))`
- [ ] 12.4 Retourner: `{ data: DashboardTimeSeriesPoint[], isLoading: boolean, error }`
- [ ] 12.5 Refetch automatique quand `filters` change

### Task 13: Frontend - Hook useDashboardStats avec filtres (AC: #6)

- [ ] 13.1 Modifier hook existant `useDashboardStats` (si existe dans ExecutionsPage)
- [ ] 13.2 Ajouter paramètre `filters: ExecutionFilters`
- [ ] 13.3 Modifier appel API: `fetchDashboardStats(scope, filters)`
- [ ] 13.4 Refetch automatique quand `filters` change
- [ ] 13.5 Adapter labels StatCards selon filtres:
  - [ ] Si date range custom: "Exécutions de la période" au lieu de "Exécutions du jour"
  - [ ] Tooltip StatCard explique période filtrée

### Task 14: Frontend - Refactorer ExecutionsPage layout (AC: #2, #3, all)

- [ ] 14.1 Ouvrir `frontend/src/pages/ExecutionsPage.tsx`
- [ ] 14.2 Intégrer hook `useExecutionFilters()`:
  - [ ] `const { filters, applyFilters, resetFilters, activeFilterCount } = useExecutionFilters()`
- [ ] 14.3 Modifier appels API avec `filters`:
  - [ ] `useDashboardStats(scope, filters)` pour StatCards
  - [ ] `useTrendLineData(scope, filters)` pour TrendLineChart
  - [ ] `useExecutions(scope, pagination, sorting, filters)` pour Table
- [ ] 14.4 Layout (ordre vertical):
  - [ ] **Row 1**: StatCards (4 cards en Row avec Col responsive) - **Existant**
  - [ ] **Row 2 (NOUVEAU)**: TrendLineChart (Col span={24})
  - [ ] **Row 3 (NOUVEAU)**: AdvancedFiltersPanel (Col span={24})
  - [ ] **Row 4**: PendingApprovalsList (si DBA/DBOPS) - **Existant**
  - [ ] **Row 5**: ExecutionsTabs (Toutes/Mes) - **Existant**
  - [ ] **Row 6**: Executions Table - **Existant**
- [ ] 14.5 Passer props à AdvancedFiltersPanel:
  - [ ] `filters={filters}`
  - [ ] `onApplyFilters={applyFilters}`
  - [ ] `onResetFilters={resetFilters}`
  - [ ] `activeFilterCount={activeFilterCount}`
- [ ] 14.6 Passer `filters` à hooks data-fetching (déjà fait 14.3)
- [ ] 14.7 Skeleton loading:
  - [ ] TrendLineChart: `<Skeleton.Input active style={{ width: '100%', height: 300 }} />` si loading
  - [ ] Table: skeleton existant (Story 9-9)

### Task 15: Frontend - Renommer Dashboard en Analytics (AC: #1, #10)

- [ ] 15.1 Ouvrir `frontend/src/App.tsx` (ou fichier de routing principal)
- [ ] 15.2 Modifier route:
  - [ ] Avant: `<Route path="/dashboard" element={<DashboardPage />} />`
  - [ ] Après: `<Route path="/analytics" element={<DashboardPage />} />` (ou `/reporting`)
- [ ] 15.3 Ouvrir `frontend/src/components/layout/Sidebar.tsx` (ou Navigation)
- [ ] 15.4 Modifier lien navigation:
  - [ ] Avant: `{ path: '/dashboard', icon: <DashboardOutlined />, label: 'Dashboard' }`
  - [ ] Après: `{ path: '/analytics', icon: <BarChartOutlined />, label: 'Analytics' }`
- [ ] 15.5 Ajouter RBAC au lien:
  - [ ] `visible: user.role === 'DBOPS'` (ou vérifier permission spécifique)
  - [ ] Le lien n'apparaît pas pour utilisateurs non-DBOPS
- [ ] 15.6 Ajouter redirect optionnel:
  - [ ] `<Route path="/dashboard" element={<Navigate to="/analytics" />} />` (backward compatibility)

### Task 16: Frontend - Route protection RBAC /analytics (AC: #10)

- [ ] 16.1 Créer composant `ProtectedRoute` (si n'existe pas déjà):
  - [ ] Props: `requiredRole: string`, `children: ReactNode`
  - [ ] Si user.role !== requiredRole → redirect vers `/catalog` ou afficher 403
- [ ] 16.2 Wrapper route `/analytics`:
  - [ ] `<Route path="/analytics" element={<ProtectedRoute requiredRole="DBOPS"><DashboardPage /></ProtectedRoute>} />`
- [ ] 16.3 Afficher message toast "Accès non autorisé" si redirection

### Task 17: Tests backend filtres (AC: #4)

- [ ] 17.1 Ouvrir `backend/tests/unit/test_execution_repository.py`
- [ ] 17.2 Ajouter test `test_list_executions_with_filters()`:
  - [ ] Mock DB avec exécutions variées (différents statuts, environnements, engines)
  - [ ] Appeler `list_executions(filters={'environment': 'PROD', 'status': 'FAILED'})`
  - [ ] Assert que seules exécutions PROD + FAILED sont retournées
- [ ] 17.3 Ajouter test `test_list_executions_with_date_range()`:
  - [ ] Mock exécutions avec dates variées
  - [ ] Appeler avec `start_date='2026-01-01'`, `end_date='2026-01-31'`
  - [ ] Assert que seules exécutions dans range sont retournées
- [ ] 17.4 Ajouter test `test_list_executions_with_tags_filter()`:
  - [ ] Mock exécutions avec tags
  - [ ] Appeler avec `tags=['backup', 'production']`
  - [ ] Assert que seules exécutions avec **tous** les tags sont retournées (logique AND)
- [ ] 17.5 Ajouter test `test_get_timeseries_data_with_filters()`:
  - [ ] Mock exécutions
  - [ ] Appeler `get_timeseries_data(filters={'environment': 'PROD'})`
  - [ ] Assert que points timeseries reflètent uniquement exécutions PROD
- [ ] 17.6 Exécuter tests: `pytest backend/tests/unit/test_execution_repository.py -v`

### Task 18: Tests backend endpoints API (AC: #4, #5, #6)

- [ ] 18.1 Ouvrir `backend/tests/integration/test_executions_api.py`
- [ ] 18.2 Ajouter test `test_get_executions_with_filters()`:
  - [ ] Créer exécutions test (PROD/DEV, FAILED/COMPLETED)
  - [ ] Appeler `GET /executions?environment=PROD&status=FAILED`
  - [ ] Assert response contient uniquement exécutions matchant filtres
- [ ] 18.3 Ajouter test `test_get_executions_stats_with_filters()`:
  - [ ] Créer exécutions test
  - [ ] Appeler `GET /executions/stats?environment=PROD`
  - [ ] Assert stats reflètent uniquement exécutions PROD
- [ ] 18.4 Ajouter test `test_get_executions_timeseries_with_filters()`:
  - [ ] Créer exécutions test avec dates variées
  - [ ] Appeler `GET /executions/timeseries?start_date=2026-01-01&end_date=2026-01-31`
  - [ ] Assert points timeseries couvrent uniquement période filtrée
- [ ] 18.5 Ajouter test `test_get_tags()`:
  - [ ] Créer actions avec tags
  - [ ] Appeler `GET /tags`
  - [ ] Assert response contient liste tags distincts
- [ ] 18.6 Exécuter tests: `pytest backend/tests/integration/test_executions_api.py -v`

### Task 19: Tests frontend hook useExecutionFilters (AC: #7, #8)

- [ ] 19.1 Créer fichier `frontend/src/__tests__/hooks/useExecutionFilters.test.tsx`
- [ ] 19.2 Ajouter test `syncs filters from URL on mount`:
  - [ ] Mock location.search avec query params
  - [ ] Render hook avec `renderHook(() => useExecutionFilters())`
  - [ ] Assert `filters` state contient valeurs depuis URL
- [ ] 19.3 Ajouter test `updates URL when applyFilters called`:
  - [ ] Render hook
  - [ ] Appeler `applyFilters({ environment: 'PROD', status: 'FAILED' })`
  - [ ] Assert `navigate()` appelé avec query string correct
- [ ] 19.4 Ajouter test `counts active filters correctly`:
  - [ ] Render hook
  - [ ] Appeler `applyFilters({ environment: 'PROD', status: 'FAILED', engine: 'Oracle' })`
  - [ ] Assert `activeFilterCount === 3`
- [ ] 19.5 Ajouter test `resets filters and URL`:
  - [ ] Render hook avec filtres actifs
  - [ ] Appeler `resetFilters()`
  - [ ] Assert `filters` revient à default
  - [ ] Assert `navigate()` appelé avec search vide

### Task 20: Tests frontend composant AdvancedFiltersPanel (AC: #3, #8)

- [ ] 20.1 Créer fichier `frontend/src/__tests__/components/AdvancedFiltersPanel.test.tsx`
- [ ] 20.2 Ajouter test `renders all filter controls`:
  - [ ] Render composant avec props mock
  - [ ] Assert présence: DatePicker, Select action, Select technologie, Select tags, Select statut, Select environnement
  - [ ] Assert présence boutons "Appliquer" et "Réinitialiser"
- [ ] 20.3 Ajouter test `calls onApplyFilters when Apply button clicked`:
  - [ ] Render composant
  - [ ] Modifier valeur Select environnement → "PROD"
  - [ ] Cliquer bouton "Appliquer"
  - [ ] Assert `onApplyFilters` appelé avec `{ environment: 'PROD' }`
- [ ] 20.4 Ajouter test `displays active filter count badge`:
  - [ ] Render composant avec `activeFilterCount={3}`
  - [ ] Assert Badge avec texte "3" visible sur bouton "Réinitialiser"
- [ ] 20.5 Ajouter test `resets local state when Reset button clicked`:
  - [ ] Render composant avec filtres actifs
  - [ ] Cliquer bouton "Réinitialiser"
  - [ ] Assert `onResetFilters` appelé
  - [ ] Assert local state cleared (tous selects vides)

### Task 21: Tests frontend ExecutionsPage intégration (AC: all)

- [ ] 21.1 Ouvrir `frontend/src/__tests__/pages/ExecutionsPage.test.tsx`
- [ ] 21.2 Ajouter test `renders TrendLineChart below StatCards`:
  - [ ] Render ExecutionsPage
  - [ ] Assert StatCards présents
  - [ ] Assert TrendLineChart présent immédiatement après (ordre DOM)
- [ ] 21.3 Ajouter test `renders AdvancedFiltersPanel above table`:
  - [ ] Render ExecutionsPage
  - [ ] Assert AdvancedFiltersPanel présent avant table
- [ ] 21.4 Ajouter test `updates table when filters applied`:
  - [ ] Render ExecutionsPage
  - [ ] Mock API responses
  - [ ] Modifier filtres et cliquer "Appliquer"
  - [ ] Assert table refetch avec nouveaux filtres
  - [ ] Assert tableau affiche données filtrées
- [ ] 21.5 Ajouter test `updates StatCards when filters applied`:
  - [ ] Render ExecutionsPage
  - [ ] Mock API responses
  - [ ] Appliquer filtres
  - [ ] Assert StatCards affichent stats filtrées
- [ ] 21.6 Ajouter test `updates TrendLineChart when filters applied`:
  - [ ] Render ExecutionsPage
  - [ ] Mock API timeseries
  - [ ] Appliquer filtres
  - [ ] Assert TrendLineChart refetch avec filtres
- [ ] 21.7 Ajouter test `preserves filters on drawer open/close`:
  - [ ] Render ExecutionsPage avec filtres actifs
  - [ ] Cliquer sur exécution (ouvrir drawer)
  - [ ] Assert URL contient query params filtres
  - [ ] Fermer drawer
  - [ ] Assert filtres toujours actifs
- [ ] 21.8 Exécuter tests: `npm test -- ExecutionsPage.test.tsx`

### Task 22: Tests frontend navigation et RBAC (AC: #10)

- [ ] 22.1 Créer test `Sidebar shows Analytics link only for DBOPS`:
  - [ ] Mock user role="DBOPS"
  - [ ] Render Sidebar
  - [ ] Assert lien "Analytics" visible
  - [ ] Mock user role="DBA"
  - [ ] Re-render Sidebar
  - [ ] Assert lien "Analytics" absent
- [ ] 22.2 Créer test `redirects non-DBOPS users from /analytics`:
  - [ ] Mock user role="DBA"
  - [ ] Navigate to `/analytics`
  - [ ] Assert redirect vers `/catalog` ou 403 page
  - [ ] Assert toast "Accès non autorisé" affiché
- [ ] 22.3 Exécuter tests: `npm test -- Sidebar Navigation RBAC`

### Task 23: Validation manuelle et polissage UX (AC: all)

- [ ] 23.1 Lancer backend dev: `cd backend && uvicorn app.main:app --reload`
- [ ] 23.2 Lancer frontend dev: `cd frontend && npm run dev`
- [ ] 23.3 Naviguer vers `/executions` avec utilisateur DBA
- [ ] 23.4 Vérifier layout:
  - [ ] StatCards en haut (4 cards)
  - [ ] TrendLineChart en dessous (graphique lignes visible)
  - [ ] AdvancedFiltersPanel en dessous (tous contrôles présents)
  - [ ] PendingApprovalsList (si DBA)
  - [ ] Tabs (Toutes/Mes)
  - [ ] Table exécutions
- [ ] 23.5 Tester filtres:
  - [ ] Modifier Environment → PROD
  - [ ] Cliquer "Appliquer"
  - [ ] Vérifier que StatCards, TrendLineChart, Table se mettent à jour
  - [ ] Vérifier que URL contient `?environment=PROD`
  - [ ] Refresh page (F5) → vérifier que filtre reste actif
- [ ] 23.6 Tester date range:
  - [ ] Sélectionner preset "30 derniers jours"
  - [ ] Appliquer
  - [ ] Vérifier que TrendLineChart affiche 30 jours de données
  - [ ] Vérifier que StatCards reflètent période (label "Exécutions de la période" si custom)
- [ ] 23.7 Tester combinaison filtres:
  - [ ] Environment=PROD, Status=FAILED, Engine=Oracle, Date range=7j
  - [ ] Appliquer
  - [ ] Vérifier que badge affiche "4" (4 filtres actifs)
  - [ ] Vérifier que table affiche uniquement exécutions matchant tous filtres
- [ ] 23.8 Tester reset:
  - [ ] Cliquer "Réinitialiser"
  - [ ] Vérifier que tous filtres cleared
  - [ ] Vérifier que badge disparaît
  - [ ] Vérifier que données reviennent à défaut (7j, scope=all)
- [ ] 23.9 Tester persistence URL:
  - [ ] Appliquer filtres
  - [ ] Copier URL
  - [ ] Ouvrir nouvel onglet
  - [ ] Coller URL
  - [ ] Vérifier que page se charge avec filtres actifs
- [ ] 23.10 Tester navigation Analytics:
  - [ ] Ouvrir sidebar
  - [ ] Vérifier lien "Analytics" présent (si DBOPS)
  - [ ] Cliquer lien → naviguer vers `/analytics`
  - [ ] Vérifier que ReportingDashboard s'affiche (charts, comparison mode, exports)
  - [ ] Vérifier que lien "Voir toutes les executions" pointe vers `/executions`
- [ ] 23.11 Tester RBAC non-DBOPS:
  - [ ] Se connecter avec user role="DBA" (non-DBOPS)
  - [ ] Vérifier que lien "Analytics" absent dans sidebar
  - [ ] Tenter accès direct `/analytics`
  - [ ] Vérifier redirect ou 403 + toast "Accès non autorisé"
- [ ] 23.12 Responsive:
  - [ ] Tester sur mobile/tablet (DevTools responsive mode)
  - [ ] Vérifier que filtres s'empilent verticalement (Col span={24})
  - [ ] Vérifier que TrendLineChart reste lisible
- [ ] 23.13 Performance:
  - [ ] Appliquer filtres lourds (tags multiples, date range large)
  - [ ] Vérifier que fetch < 2s (NFR1)
  - [ ] Vérifier skeleton loading pendant fetch
- [ ] 23.14 Edge cases:
  - [ ] Appliquer filtres qui ne matchent aucune exécution
  - [ ] Vérifier message "Aucune exécution trouvée"
  - [ ] Vérifier que StatCards affichent "0" ou "—"
  - [ ] Vérifier que TrendLineChart affiche "Aucune donnée"

### Task 24: Documentation et mise à jour sprint status (AC: all)

- [ ] 24.1 Mettre à jour Dev Notes avec décisions techniques:
  - [ ] Refonte navigation: Dashboard → Analytics (RBAC DBOPS uniquement)
  - [ ] TrendLineChart déplacé dans ExecutionsPage
  - [ ] AdvancedFiltersPanel créé avec 7 contrôles filtres
  - [ ] API `/executions` enrichie avec 7 paramètres filtrage
  - [ ] Persistence filtres via URL query params
  - [ ] Badge active filter count
- [ ] 24.2 Documenter layout ExecutionsPage finalisé:
  - [ ] Row 1: StatCards (4) → scope + filters aware
  - [ ] Row 2: TrendLineChart → filters aware
  - [ ] Row 3: AdvancedFiltersPanel → 7 contrôles
  - [ ] Row 4: PendingApprovalsList (RBAC)
  - [ ] Row 5: Tabs (Toutes/Mes)
  - [ ] Row 6: Table exécutions → filters aware
- [ ] 24.3 Documenter endpoints backend modifiés:
  - [ ] `GET /executions` + 7 query params
  - [ ] `GET /executions/stats` + filters
  - [ ] `GET /executions/timeseries` + filters
  - [ ] `GET /tags`
- [ ] 24.4 Ajouter références aux fichiers modifiés dans File List
- [ ] 24.5 Mettre à jour `sprint-status.yaml`: `9-10-refonte-dashboard-vers-executions: review`
- [ ] 24.6 Commit avec message descriptif:
  - [ ] `feat(executions): consolidate dashboard into executions page with advanced filters (story 9-10)`

## Dev Notes

### Contexte technique

**Origine de la story:**
- Epic 9 (Autoremediation) - Story 9.10 identifiée comme refonte UX majeure
- Sprint status commentaire: "Refonte majeure : (1) Supprimer dashboard classique (2) Déplacer graphique échecs/succès dans Exécutions avec filtres (3) Ajouter filtres avancés dans Exécutions : range dates, action, technologie, tags, statut, environnement (4) Dashboard admin DBOPS reste pour analyses avancées"
- Problématique: Fragmentation workflow DBA, duplication StatCards, TrendLineChart isolé, absence filtres dans Exécutions

**État actuel de ExecutionsPage (Post-Story 9-9):**
- StatCards: 4 métriques (déplacées depuis Dashboard par Story 9-4)
- Pending Approvals: Section DBA/DBOPS (déplacée par Story 8-8)
- Tabs: "Toutes les exécutions" (scope=all) vs "Mes exécutions" (scope=mine) (Story 8-9)
- Table: 8 colonnes (Statut, Action, Technologie, Plateforme, Utilisateur, Environnement, Date, Durée) - Refactorées Story 9-9
- **Limitation**: Aucun filtre avancé, uniquement scope (tabs) + tri colonnes

**État actuel de Dashboard (Post-Story 9-4):**
- Rend uniquement `ReportingDashboard` component
- TrendLineChart + TechnologyBarChart + EnvironmentBarChart
- AdvancedFiltersPanel avec 7 filtres (Engine, Environment, Tags, Status, Date range)
- Mode Comparison (Technology vs Technology, Environment vs Environment, Period vs Period)
- Export CSV/PDF
- **Limitation**: Dashboard est devenu "analytics avancées uniquement", mais StatCards ont été déplacées vers Exécutions — incohérence

### Architecture Compliance

**Patterns à suivre:**

1. **Repository Pattern SQL brut**: Enrichir `execution_repository.py` avec clauses WHERE dynamiques pour filtrage. Utiliser requêtes paramétrées pour éviter SQL injection.
   - [Source: _bmad-output/planning-artifacts/architecture.md - Section Repository Pattern (ligne 258)]

2. **URL-based state management**: Utiliser query params pour persistence filtres. Pattern déjà utilisé dans ReportingDashboard — réutiliser approche.
   - Avantages: Partageabilité liens, refresh-safe, navigation back/forward fonctionne
   - Implémentation: Hook `useExecutionFilters` avec `useSearchParams` React Router

3. **RBAC middleware frontend**: Lien "Analytics" visible uniquement si `user.role === 'DBOPS'`. Utiliser composant `ProtectedRoute` pour route protection.
   - [Source: _bmad-output/planning-artifacts/architecture.md - Section RBAC (ligne 90)]

4. **Design System Ant Design 6.2**: Utiliser composants natifs pour filtres (DatePicker.RangePicker, Select mode="multiple", Badge). Tokens design pour couleurs.
   - [Source: Story 5-5 - Alignement React & Ant 6.2 bonnes pratiques]

5. **Cache in-memory**: Cache catalogue (actions, tags) TTL 5min. Pas de cache filtres côté backend (query params dynamiques). Cache React Query côté frontend.
   - [Source: _bmad-output/planning-artifacts/architecture.md - Section Cache (ligne 263)]

6. **WebSocket temps réel**: ExecutionTimeline déjà WebSocket (Story 4-6). Table exécutions peut aussi recevoir updates WebSocket pour statut running → completed sans refresh (optionnel, post-Story 9.10).

### Technical Requirements

**Modifications backend:**

1. **Endpoint `/executions` enrichi** (`backend/app/api/routes/executions.py`):
   ```python
   @router.get("/executions", response_model=ExecutionListResponse)
   async def list_executions(
       scope: Literal["mine", "all"] = "mine",
       limit: int = 25,
       offset: int = 0,
       sort_by: str = "created_at",
       sort_order: Literal["asc", "desc"] = "desc",
       # NEW: Advanced filters (Story 9-10)
       start_date: date | None = None,
       end_date: date | None = None,
       action_id: int | None = None,
       engine: ActionEngine | None = None,
       tags: str | None = None,  # Comma-separated: "backup,production"
       status: ExecutionStatusType | None = None,
       environment: ExecutionEnvironment | None = None,
       current_user: User = Depends(get_current_user),
       db: Connection = Depends(get_db_connection)
   ):
       # Parse tags
       tags_list = tags.split(',') if tags else None

       # Apply RBAC filtering
       if scope == "mine":
           user_id_filter = current_user.id
       elif not current_user.has_permission("view_all_executions"):
           raise HTTPException(403, "Access denied")
       else:
           user_id_filter = None

       # Call repository with filters
       executions = execution_repository.list_executions(
           db=db,
           user_id=user_id_filter,
           limit=limit,
           offset=offset,
           sort_by=sort_by,
           sort_order=sort_order,
           start_date=start_date,
           end_date=end_date,
           action_id=action_id,
           engine=engine,
           tags_list=tags_list,
           status=status,
           environment=environment
       )

       return {"executions": executions, "total": len(executions)}
   ```

2. **Repository SQL dynamique** (`backend/app/repositories/execution_repository.py`):
   ```python
   def list_executions(
       db: Connection,
       user_id: int | None,
       limit: int,
       offset: int,
       sort_by: str,
       sort_order: str,
       start_date: date | None = None,
       end_date: date | None = None,
       action_id: int | None = None,
       engine: ActionEngine | None = None,
       tags_list: list[str] | None = None,
       status: ExecutionStatusType | None = None,
       environment: ExecutionEnvironment | None = None
   ) -> list[ExecutionResponse]:
       # Base query
       sql = """
       SELECT
           e.ID, e.ACTION_ID, e.USER_ID, e.ENVIRONMENT, e.STATUS,
           e.SERVICENOW_CHANGE_ID, e.STARTED_AT, e.COMPLETED_AT, e.CREATED_AT,
           u.NAME AS user_display_name,
           ac.NAME AS action_name,
           ac.ENGINE AS action_engine,
           ac.PLATFORM AS action_platform,
           ac.ITEM_TYPE AS action_item_type,
           i.NAME AS integration_name,
           i.ICON AS integration_icon
       FROM EXECUTIONS e
       LEFT JOIN USERS u ON e.USER_ID = u.ID
       LEFT JOIN ACTIONS_CATALOG ac ON e.ACTION_ID = ac.ID
       LEFT JOIN INTEGRATIONS i ON ac.INTEGRATION_ID = i.ID
       WHERE 1=1
       """

       params = {}

       # Dynamic WHERE clauses
       if user_id is not None:
           sql += " AND e.USER_ID = :user_id"
           params['user_id'] = user_id

       if start_date:
           sql += " AND e.CREATED_AT >= :start_date"
           params['start_date'] = start_date

       if end_date:
           sql += " AND e.CREATED_AT <= :end_date"
           params['end_date'] = end_date

       if action_id:
           sql += " AND e.ACTION_ID = :action_id"
           params['action_id'] = action_id

       if engine:
           sql += " AND ac.ENGINE = :engine"
           params['engine'] = engine.value

       if status:
           sql += " AND e.STATUS = :status"
           params['status'] = status.value

       if environment:
           sql += " AND e.ENVIRONMENT = :environment"
           params['environment'] = environment.value

       # Tags filtering (JOIN on ACTION_TAGS)
       if tags_list:
           # Subquery: actions having ALL specified tags (AND logic)
           sql += """
           AND ac.ID IN (
               SELECT at.ACTION_ID
               FROM ACTION_TAGS at
               WHERE at.TAG_NAME IN ({tags_placeholders})
               GROUP BY at.ACTION_ID
               HAVING COUNT(DISTINCT at.TAG_NAME) = :tags_count
           )
           """.format(tags_placeholders=','.join([f':tag_{i}' for i in range(len(tags_list))]))

           for i, tag in enumerate(tags_list):
               params[f'tag_{i}'] = tag
           params['tags_count'] = len(tags_list)

       # Order and pagination
       sql += f" ORDER BY e.{sort_by} {sort_order.upper()}"
       sql += " OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"
       params['offset'] = offset
       params['limit'] = limit

       # Execute query
       cursor = db.cursor()
       cursor.execute(sql, params)
       rows = cursor.fetchall()

       return [_row_to_execution_response(row) for row in rows]
   ```

3. **Endpoint `/executions/timeseries` avec filtres**:
   ```python
   @router.get("/executions/timeseries", response_model=list[DashboardTimeSeriesPoint])
   async def get_executions_timeseries(
       scope: Literal["mine", "all"] = "mine",
       start_date: date | None = None,
       end_date: date | None = None,
       action_id: int | None = None,
       engine: ActionEngine | None = None,
       tags: str | None = None,
       status: ExecutionStatusType | None = None,
       environment: ExecutionEnvironment | None = None,
       current_user: User = Depends(get_current_user),
       db: Connection = Depends(get_db_connection)
   ):
       # Same RBAC logic as /executions
       # ...

       # Call repository
       timeseries = execution_repository.get_timeseries_data(
           db=db,
           user_id=user_id_filter,
           start_date=start_date or (date.today() - timedelta(days=7)),  # Default 7 days
           end_date=end_date or date.today(),
           # ... other filters
       )

       return timeseries
   ```

4. **Repository `get_timeseries_data()` avec filtres**:
   ```python
   def get_timeseries_data(
       db: Connection,
       user_id: int | None,
       start_date: date,
       end_date: date,
       # ... same filters as list_executions
   ) -> list[DashboardTimeSeriesPoint]:
       sql = """
       SELECT
           DATE(e.CREATED_AT) as date,
           COUNT(CASE WHEN e.STATUS = 'COMPLETED' THEN 1 END) as success,
           COUNT(CASE WHEN e.STATUS = 'FAILED' THEN 1 END) as failed
       FROM EXECUTIONS e
       LEFT JOIN ACTIONS_CATALOG ac ON e.ACTION_ID = ac.ID
       WHERE e.CREATED_AT BETWEEN :start_date AND :end_date
       """

       params = {'start_date': start_date, 'end_date': end_date}

       # Apply same dynamic filters as list_executions (WHERE clauses)
       # ...

       sql += " GROUP BY DATE(e.CREATED_AT) ORDER BY date ASC"

       cursor = db.cursor()
       cursor.execute(sql, params)
       rows = cursor.fetchall()

       return [
           DashboardTimeSeriesPoint(
               date=row[0].strftime('%Y-%m-%d'),
               success=row[1],
               failed=row[2]
           )
           for row in rows
       ]
   ```

5. **Endpoint `/tags` pour charger liste tags**:
   ```python
   @router.get("/tags", response_model=list[str])
   async def list_tags(
       current_user: User = Depends(get_current_user),
       db: Connection = Depends(get_db_connection)
   ):
       # Query distinct tags from ACTION_TAGS
       # Filter by RBAC: only tags of actions visible to user
       sql = """
       SELECT DISTINCT at.TAG_NAME
       FROM ACTION_TAGS at
       JOIN ACTIONS_CATALOG ac ON at.ACTION_ID = ac.ID
       WHERE ac.ID IN (
           SELECT action_id FROM user_allowed_actions WHERE user_id = :user_id
       )
       ORDER BY at.TAG_NAME ASC
       """

       cursor = db.cursor()
       cursor.execute(sql, {'user_id': current_user.id})
       rows = cursor.fetchall()

       return [row[0] for row in rows]
   ```

**Modifications frontend:**

1. **Types** (`frontend/src/types/api.ts`):
   ```typescript
   export interface ExecutionFilters {
       scope?: 'mine' | 'all';
       start_date?: string | null;  // ISO 8601
       end_date?: string | null;
       action_id?: number | null;
       engine?: ActionEngine | null;
       tags?: string[] | null;
       status?: ExecutionStatusType | null;
       environment?: ExecutionEnvironment | null;
   }

   export interface ExecutionListParams extends ExecutionFilters {
       limit: number;
       offset: number;
       sort_by: string;
       sort_order: 'asc' | 'desc';
   }
   ```

2. **Hook `useExecutionFilters`** (`frontend/src/hooks/useExecutionFilters.ts`):
   ```typescript
   import { useState, useEffect } from 'react';
   import { useNavigate, useLocation } from 'react-router-dom';
   import type { ExecutionFilters } from '../types/api';

   export function useExecutionFilters() {
       const navigate = useNavigate();
       const location = useLocation();

       const [filters, setFilters] = useState<ExecutionFilters>({});
       const [activeFilterCount, setActiveFilterCount] = useState(0);

       // Sync filters from URL on mount
       useEffect(() => {
           const params = new URLSearchParams(location.search);
           const urlFilters: ExecutionFilters = {
               start_date: params.get('start_date') || null,
               end_date: params.get('end_date') || null,
               action_id: params.get('action_id') ? parseInt(params.get('action_id')!) : null,
               engine: (params.get('engine') as ActionEngine) || null,
               tags: params.get('tags')?.split(',') || null,
               status: (params.get('status') as ExecutionStatusType) || null,
               environment: (params.get('environment') as ExecutionEnvironment) || null,
           };
           setFilters(urlFilters);
       }, [location.search]);

       // Count active filters
       useEffect(() => {
           const count = Object.entries(filters).filter(([key, value]) => {
               // Exclude scope from count (it's a tab, not a filter)
               if (key === 'scope') return false;
               return value !== null && value !== undefined && value !== '';
           }).length;
           setActiveFilterCount(count);
       }, [filters]);

       const applyFilters = (newFilters: ExecutionFilters) => {
           setFilters(newFilters);

           // Build query string
           const params = new URLSearchParams();
           Object.entries(newFilters).forEach(([key, value]) => {
               if (value !== null && value !== undefined && value !== '') {
                   if (Array.isArray(value)) {
                       params.set(key, value.join(','));
                   } else {
                       params.set(key, String(value));
                   }
               }
           });

           navigate({ search: params.toString() });
       };

       const resetFilters = () => {
           const defaultFilters: ExecutionFilters = {
               scope: filters.scope || 'all',  // Preserve scope
               start_date: null,
               end_date: null,
               action_id: null,
               engine: null,
               tags: null,
               status: null,
               environment: null,
           };
           setFilters(defaultFilters);
           navigate({ search: '' });
       };

       return { filters, applyFilters, resetFilters, activeFilterCount };
   }
   ```

3. **Composant `AdvancedFiltersPanel`** (`frontend/src/components/executions/AdvancedFiltersPanel.tsx`):
   ```tsx
   import React, { useState } from 'react';
   import { Card, Form, Row, Col, DatePicker, Select, Button, Badge, Space } from 'antd';
   import { FilterOutlined, ReloadOutlined } from '@ant-design/icons';
   import type { ExecutionFilters } from '../../types/api';
   import { useTags } from '../../hooks/useTags';
   import { useActions } from '../../hooks/useActions';  // Hook to fetch actions list
   import dayjs, { Dayjs } from 'dayjs';

   const { RangePicker } = DatePicker;

   interface AdvancedFiltersPanelProps {
       filters: ExecutionFilters;
       onApplyFilters: (filters: ExecutionFilters) => void;
       onResetFilters: () => void;
       activeFilterCount: number;
   }

   export const AdvancedFiltersPanel: React.FC<AdvancedFiltersPanelProps> = ({
       filters,
       onApplyFilters,
       onResetFilters,
       activeFilterCount,
   }) => {
       // Local state for form
       const [localFilters, setLocalFilters] = useState<ExecutionFilters>(filters);

       // Load options from API
       const { tags, isLoading: tagsLoading } = useTags();
       const { actions, isLoading: actionsLoading } = useActions();

       // Date range presets
       const rangePresets = [
           { label: '7 derniers jours', value: [dayjs().subtract(7, 'd'), dayjs()] as [Dayjs, Dayjs] },
           { label: '14 derniers jours', value: [dayjs().subtract(14, 'd'), dayjs()] as [Dayjs, Dayjs] },
           { label: '30 derniers jours', value: [dayjs().subtract(30, 'd'), dayjs()] as [Dayjs, Dayjs] },
           { label: '90 derniers jours', value: [dayjs().subtract(90, 'd'), dayjs()] as [Dayjs, Dayjs] },
       ];

       const handleApply = () => {
           onApplyFilters(localFilters);
       };

       const handleReset = () => {
           setLocalFilters({});
           onResetFilters();
       };

       return (
           <Card
               title={
                   <Space>
                       <FilterOutlined />
                       Filtres avancés
                       {activeFilterCount > 0 && (
                           <Badge count={activeFilterCount} showZero={false} />
                       )}
                   </Space>
               }
               style={{ marginBottom: 16 }}
           >
               <Form layout="vertical">
                   {/* Row 1 */}
                   <Row gutter={16}>
                       <Col xs={24} md={8}>
                           <Form.Item label="Période">
                               <RangePicker
                                   style={{ width: '100%' }}
                                   format="DD/MM/YYYY"
                                   presets={rangePresets}
                                   value={
                                       localFilters.start_date && localFilters.end_date
                                           ? [dayjs(localFilters.start_date), dayjs(localFilters.end_date)]
                                           : null
                                   }
                                   onChange={(dates) => {
                                       setLocalFilters({
                                           ...localFilters,
                                           start_date: dates?.[0]?.format('YYYY-MM-DD') || null,
                                           end_date: dates?.[1]?.format('YYYY-MM-DD') || null,
                                       });
                                   }}
                               />
                           </Form.Item>
                       </Col>
                       <Col xs={24} md={8}>
                           <Form.Item label="Action">
                               <Select
                                   placeholder="Toutes les actions"
                                   allowClear
                                   showSearch
                                   loading={actionsLoading}
                                   value={localFilters.action_id}
                                   onChange={(value) =>
                                       setLocalFilters({ ...localFilters, action_id: value })
                                   }
                                   options={actions?.map((action) => ({
                                       label: action.name,
                                       value: action.id,
                                   }))}
                               />
                           </Form.Item>
                       </Col>
                       <Col xs={24} md={8}>
                           <Form.Item label="Technologie">
                               <Select
                                   placeholder="Toutes les technologies"
                                   allowClear
                                   value={localFilters.engine}
                                   onChange={(value) =>
                                       setLocalFilters({ ...localFilters, engine: value })
                                   }
                                   options={[
                                       { label: 'Oracle', value: 'Oracle' },
                                       { label: 'SQL Server', value: 'SQL Server' },
                                       { label: 'DB2', value: 'DB2' },
                                       { label: 'PostgreSQL', value: 'PostgreSQL' },
                                       { label: 'MySQL', value: 'MySQL' },
                                       { label: 'Workflow', value: 'Workflow' },
                                   ]}
                               />
                           </Form.Item>
                       </Col>
                   </Row>

                   {/* Row 2 */}
                   <Row gutter={16}>
                       <Col xs={24} md={8}>
                           <Form.Item label="Tags">
                               <Select
                                   mode="multiple"
                                   placeholder="Tous les tags"
                                   allowClear
                                   maxTagCount={3}
                                   loading={tagsLoading}
                                   value={localFilters.tags}
                                   onChange={(value) =>
                                       setLocalFilters({ ...localFilters, tags: value })
                                   }
                                   options={tags?.map((tag) => ({
                                       label: tag,
                                       value: tag,
                                   }))}
                               />
                           </Form.Item>
                       </Col>
                       <Col xs={24} md={8}>
                           <Form.Item label="Statut">
                               <Select
                                   placeholder="Tous les statuts"
                                   allowClear
                                   value={localFilters.status}
                                   onChange={(value) =>
                                       setLocalFilters({ ...localFilters, status: value })
                                   }
                                   options={[
                                       { label: 'Soumise', value: 'SUBMITTED' },
                                       { label: 'En attente', value: 'PENDING_APPROVAL' },
                                       { label: 'En cours', value: 'RUNNING' },
                                       { label: 'Terminée', value: 'COMPLETED' },
                                       { label: 'Échouée', value: 'FAILED' },
                                       { label: 'Annulée', value: 'CANCELLED' },
                                       { label: 'Rejetée', value: 'REJECTED' },
                                   ]}
                               />
                           </Form.Item>
                       </Col>
                       <Col xs={24} md={4}>
                           <Form.Item label="Environnement">
                               <Select
                                   placeholder="Tous"
                                   allowClear
                                   value={localFilters.environment}
                                   onChange={(value) =>
                                       setLocalFilters({ ...localFilters, environment: value })
                                   }
                                   options={[
                                       { label: 'DEV', value: 'DEV' },
                                       { label: 'STAGING', value: 'STAGING' },
                                       { label: 'PROD', value: 'PROD' },
                                   ]}
                               />
                           </Form.Item>
                       </Col>
                       <Col xs={24} md={4}>
                           <Form.Item label=" ">
                               <Space>
                                   <Button type="primary" icon={<FilterOutlined />} onClick={handleApply}>
                                       Appliquer
                                   </Button>
                                   <Button
                                       icon={<ReloadOutlined />}
                                       onClick={handleReset}
                                       disabled={activeFilterCount === 0}
                                   >
                                       Réinitialiser
                                   </Button>
                               </Space>
                           </Form.Item>
                       </Col>
                   </Row>
               </Form>
           </Card>
       );
   };
   ```

4. **ExecutionsPage refactoré** (`frontend/src/pages/ExecutionsPage.tsx`):
   ```tsx
   // Imports existants + nouveaux
   import { AdvancedFiltersPanel } from '../components/executions/AdvancedFiltersPanel';
   import { TrendLineChart } from '../components/dashboard/reporting/TrendLineChart';
   import { useExecutionFilters } from '../hooks/useExecutionFilters';
   import { useTrendLineData } from '../hooks/useTrendLineData';

   export const ExecutionsPage: React.FC = () => {
       // Existing state
       const [activeScope, setActiveScope] = useState<'mine' | 'all'>('mine');

       // NEW: Filters hook
       const { filters, applyFilters, resetFilters, activeFilterCount } = useExecutionFilters();

       // Data fetching hooks with filters
       const { stats, statsLoading } = useDashboardStats(activeScope, filters);
       const { timeseriesData, timeseriesLoading } = useTrendLineData(activeScope, filters);
       const { executions, executionsLoading, total } = useExecutions(
           activeScope,
           pagination,
           sorting,
           filters  // NEW: Pass filters
       );

       return (
           <div style={{ padding: '24px' }}>
               {/* Row 1: StatCards (existing) */}
               <Row gutter={16} style={{ marginBottom: 24 }}>
                   {/* 4 StatCards */}
               </Row>

               {/* Row 2: TrendLineChart (NEW) */}
               <Row style={{ marginBottom: 24 }}>
                   <Col span={24}>
                       {timeseriesLoading ? (
                           <Skeleton.Input active style={{ width: '100%', height: 300 }} />
                       ) : (
                           <Card>
                               <TrendLineChart
                                   data={timeseriesData}
                                   loading={timeseriesLoading}
                                   title="Tendances des exécutions"
                               />
                           </Card>
                       )}
                   </Col>
               </Row>

               {/* Row 3: AdvancedFiltersPanel (NEW) */}
               <AdvancedFiltersPanel
                   filters={filters}
                   onApplyFilters={applyFilters}
                   onResetFilters={resetFilters}
                   activeFilterCount={activeFilterCount}
               />

               {/* Row 4: PendingApprovalsList (existing, if RBAC) */}

               {/* Row 5: Tabs (existing) */}

               {/* Row 6: Table (existing) */}
           </div>
       );
   };
   ```

### Library/Framework Requirements

**Backend:**
- **python-oracledb** (déjà utilisé): Requêtes SQL paramétrées avec clauses WHERE dynamiques
- **FastAPI** (déjà utilisé): Query params parsing, validation Pydantic
- **Pydantic** (déjà utilisé): Validation paramètres filtres (date range, enum values)

**Frontend:**
- **Ant Design 6.2** (déjà utilisé): DatePicker.RangePicker, Select mode="multiple", Badge, Card, Form
- **React Router 7** (déjà utilisé): `useSearchParams` pour URL query params persistence
- **React Query** (recommandé): Cache fetching, auto-refetch on filters change
- **dayjs** (déjà utilisé): Date manipulation pour presets et formatting

**Aucune nouvelle dépendance requise** - tous les outils nécessaires sont déjà installés dans le projet.

### File Structure Requirements

**Fichiers à créer:**
```
idp-portal/
├── frontend/src/
│   ├── components/executions/
│   │   └── AdvancedFiltersPanel.tsx              # NEW: Panel filtres avancés
│   ├── hooks/
│   │   ├── useExecutionFilters.ts                # NEW: Hook gestion filtres + URL persistence
│   │   ├── useTrendLineData.ts                   # NEW: Hook fetch timeseries data
│   │   └── useTags.ts                            # NEW: Hook fetch tags list
│   └── __tests__/
│       ├── hooks/
│       │   └── useExecutionFilters.test.tsx      # NEW: Tests hook filtres
│       └── components/
│           └── AdvancedFiltersPanel.test.tsx     # NEW: Tests composant panel
├── backend/app/api/routes/
│   └── tags.py                                   # NEW: Endpoint /tags (ou ajouter à executions.py)
```

**Fichiers à modifier:**
```
idp-portal/
├── frontend/src/
│   ├── pages/ExecutionsPage.tsx                  # MODIFY: Intégrer TrendLineChart + AdvancedFiltersPanel
│   ├── components/layout/Sidebar.tsx             # MODIFY: Renommer "Dashboard" → "Analytics" + RBAC
│   ├── App.tsx                                   # MODIFY: Renommer route "/dashboard" → "/analytics" + protection
│   ├── services/executionService.ts              # MODIFY: Ajouter paramètres filtres aux appels API
│   ├── hooks/useDashboardStats.ts                # MODIFY: Ajouter paramètre filters
│   └── __tests__/pages/ExecutionsPage.test.tsx  # MODIFY: Ajouter tests filtres
├── backend/app/
│   ├── api/routes/executions.py                  # MODIFY: Enrichir endpoints avec query params filtres
│   ├── repositories/execution_repository.py      # MODIFY: Ajouter clauses WHERE dynamiques
│   └── tests/
│       ├── unit/test_execution_repository.py     # MODIFY: Ajouter tests filtres
│       └── integration/test_executions_api.py    # MODIFY: Ajouter tests endpoints filtres
```

**Fichiers à déplacer/réorganiser:**
```
frontend/src/components/dashboard/reporting/TrendLineChart.tsx
→ Laisser en place (utilisé par ReportingDashboard ET ExecutionsPage)
OU
→ Déplacer vers frontend/src/components/shared/TrendLineChart.tsx (réutilisabilité)
```

**Aucun fichier à supprimer** - Dashboard (ReportingDashboard) reste disponible pour analytics avancées DBOPS.

### Référence story précédente (Story 9-9)

**Story 9-9** (Amélioration table exécutions) - **DONE 2026-02-02**

**Learnings de 9-9 applicables à 9-10:**
- **Enrichissement API**: Story 9-9 a ajouté 6 champs à ExecutionResponse (engine, platform, item_type, integration_*). Story 9-10 réutilise ces champs pour filtrage.
- **Utilitaires réutilisables**: Story 9-9 a créé `executionRenderers.tsx` pour éviter duplication. Story 9-10 suit même pattern avec `AdvancedFiltersPanel` réutilisable.
- **Tests complets**: Story 9-9 a ajouté tests backend (repository + API) + tests frontend (components + hooks). Story 9-10 doit suivre même niveau de coverage.

**Différences:**
- 9-9: Refactoring colonnes table (UX visuelle)
- 9-10: Ajout filtrage avancé + consolidation navigation (UX workflow)

**Similarités:**
- Les deux stories touchent ExecutionsPage (9-9: table columns, 9-10: layout + filtres)
- Les deux enrichissent API `/executions` (9-9: nouveaux champs response, 9-10: nouveaux query params)
- Les deux nécessitent tests backend + frontend complets

### Git Intelligence (commits récents)

Commits Epic 9 récents (Story 9-1 à 9-9):
```
fa7b203 feat(executions): improve table UX with status column first, technology and platform icons (story 9-9)
21f0b96 fix(backend): add missing approval action types to audit log constraint (story 9-8)
dc72a93 feat(executions): move execution statistics from dashboard to executions page (story 9-4)
```

Commits pertinents pour Story 9-10:
- **Story 9-4** (Déplacement StatCards vers Exécutions): `dc72a93 feat(executions): move execution statistics from dashboard to executions page`
  - A déplacé les StatCards depuis Dashboard → ExecutionsPage
  - Story 9-10 complète ce déplacement en ajoutant TrendLineChart et filtres
- **Story 8-9** (Tabs all/my executions): `a0f2e61 feat(executions): add tabs for all executions and my executions with RBAC filtering`
  - A introduit scope='all'/'mine' dans ExecutionsPage
  - Story 9-10 réutilise ce concept de scope pour filtres
- **Story 8-3** (Dashboard reporting statistiques): `8a4f2c1 feat(dashboard): add reporting dashboard with technology and environment statistics`
  - A créé ReportingDashboard avec TrendLineChart et AdvancedFiltersPanel
  - Story 9-10 déplace TrendLineChart vers ExecutionsPage et adapte filtres

**Pattern de commit attendu pour 9-10:**
```
feat(executions): consolidate dashboard into executions page with advanced filters (story 9-10)

- Move TrendLineChart from ReportingDashboard to ExecutionsPage (AC2)
- Add AdvancedFiltersPanel with 7 filter controls (AC3)
- Enrich /executions API endpoint with filtering params (AC4)
- Add /executions/timeseries and /executions/stats endpoints with filter support (AC5, AC6)
- Create useExecutionFilters hook for URL-based state persistence (AC7, AC8)
- Rename Dashboard to Analytics with RBAC protection for DBOPS only (AC1, AC10)
- Synchronize StatCards, TrendLineChart, and Table with applied filters (AC5, AC6)
- Add comprehensive tests: backend repository, API endpoints, frontend hooks, components (AC: all)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Analyse fichiers existants

**Fichiers à lire/analyser:**
1. `frontend/src/pages/ExecutionsPage.tsx` (lignes complètes): Structure layout actuelle (StatCards, Tabs, Table)
2. `frontend/src/components/dashboard/reporting/ReportingDashboard.tsx` (lignes complètes): AdvancedFiltersPanel à adapter, TrendLineChart à déplacer
3. `frontend/src/components/dashboard/reporting/TrendLineChart.tsx`: Composant à réutiliser
4. `backend/app/repositories/execution_repository.py` (fonction `list_executions`): Requête SQL à enrichir
5. `backend/app/api/routes/executions.py`: Endpoints à enrichir avec query params

**Fichiers de référence (patterns établis):**
- `frontend/src/components/dashboard/reporting/AdvancedFiltersPanel.tsx`: Pattern filtres à adapter
- `frontend/src/hooks/useDashboardStats.ts`: Hook à modifier pour ajouter filtres
- `backend/app/repositories/execution_repository.py`: Repository pattern SQL brut

### Décisions techniques

1. **Choix URL query params pour persistence**: Utiliser `useSearchParams` React Router pour stocker filtres dans URL. Avantages: partageabilité liens, refresh-safe, navigation back/forward.
   - Alternative écartée: Local storage (non partageable, non visible dans URL)

2. **Logique tags: AND vs OR**: Utiliser logique **AND** (exécution doit avoir **tous** les tags sélectionnés). Plus restrictif mais plus précis pour DBA cherchant cas spécifique.
   - Alternative: Logique OR (plus permissive, moins précise)

3. **TrendLineChart: déplacer vs dupliquer**: **Laisser en place** dans `dashboard/reporting/` et importer dans ExecutionsPage. Évite duplication, maintient réutilisabilité.
   - Alternative écartée: Dupliquer composant (maintenance x2)

4. **Dashboard → Analytics naming**: Renommer lien navigation "Dashboard" → "Analytics" pour clarifier que c'est analytics avancées DBOPS. Route reste `/dashboard` ou `/analytics` (à décider).
   - Alternative: Garder "Dashboard" mais masquer pour non-DBOPS (moins clair)

5. **Filtres: collapsible ou toujours visible**: **Toujours visible** par défaut (Card non-collapsible). Les DBA utilisent souvent les filtres, pas besoin de masquer.
   - Alternative: Collapsible avec state local (ajoute complexité inutile)

6. **StatCards label dynamique**: Si date range custom appliqué, label "Exécutions du jour" devient "Exécutions de la période". Plus clair pour utilisateur.
   - Alternative: Toujours "Exécutions du jour" même si filtré (moins précis)

7. **Badge active filter count: position**: Afficher badge à côté du titre du panel ("Filtres avancés [3]") ou sur bouton "Réinitialiser" ([3] Réinitialiser). **Choix: Sur bouton** (plus actionnable).
   - Alternative: À côté titre (moins visible)

### Gestion des cas limites

**Edge case 1: Filtres appliqués ne matchent aucune exécution**
- Symptôme: Query retourne array vide
- Handling: Afficher message "Aucune exécution trouvée pour les filtres sélectionnés" dans table. StatCards affichent "0" ou "—". TrendLineChart affiche "Aucune donnée sur la période".
- Test: `test_get_executions_with_filters_no_results()`

**Edge case 2: Date range invalide (start_date > end_date)**
- Symptôme: Backend reçoit start_date=2026-02-01, end_date=2026-01-01
- Handling: Validation Pydantic côté backend → HTTP 400 "Invalid date range". Frontend: DatePicker.RangePicker empêche sélection invalide nativement.
- Test: `test_get_executions_with_invalid_date_range()`

**Edge case 3: Tags inexistants sélectionnés**
- Symptôme: Frontend envoie tags=["nonexistent_tag"]
- Handling: Query SQL retourne 0 résultats (aucune action n'a ce tag). Pas d'erreur 400, juste résultat vide.
- Prévention: Frontend charge tags depuis API `/tags` — seuls tags existants sont proposés.

**Edge case 4: Refresh page avec filtres en query params**
- Symptôme: URL contient `/executions?environment=PROD&status=FAILED`, utilisateur refresh (F5)
- Handling: Hook `useExecutionFilters` parse query params dans `useEffect` on mount → filtres restaurés automatiquement.
- Test: `test_filters_restored_from_url_on_mount()`

**Edge case 5: Scope "mine" + aucun filtre appliqué**
- Symptôme: Utilisateur non-DBA (scope="mine" auto-activé) n'applique aucun filtre
- Handling: Query backend filtre par `user_id=current_user.id` + date range default 7j. StatCards et TrendLineChart affichent données scope="mine".
- Clarté: Label StatCard "Mes exécutions du jour" au lieu de "Exécutions du jour" si scope="mine".

**Edge case 6: Navigation depuis Dashboard (Analytics) vers Exécutions avec filtres**
- Symptôme: Utilisateur DBOPS sur Dashboard applique filtres, clique "Voir toutes les executions"
- Handling actuel (Story 9-10): Lien "Voir toutes les executions" dans Dashboard ne passe **pas** les filtres (navigation simple `/executions`). Exécutions s'ouvre sans filtres.
- Amélioration future (post-Story 9-10): Passer query params dans lien (`/executions?environment=PROD&...`) pour préserver filtres. **Hors scope Story 9-10** (Dashboard reste outil séparé).

**Edge case 7: RBAC utilisateur non-DBOPS tente accès `/analytics`**
- Symptôme: URL directe `/analytics` tapée par utilisateur sans permission
- Handling: Route protégée par `ProtectedRoute` component → redirect `/catalog` + toast "Accès non autorisé".
- Test: `test_redirects_non_dbops_users_from_analytics()`

**Edge case 8: Tags multi-select: limite 50+ tags**
- Symptôme: Select tags charge 100+ tags distincts
- Handling: Ant Design Select mode="multiple" avec `maxTagCount={3}` affiche max 3 badges, puis "+N". Searchable pour trouver tag spécifique. Pas de limite backend sur nombre de tags filtrables (logique AND peut retourner 0 résultats si trop de tags).

**Edge case 9: Backend timeout sur query avec trop de filtres**
- Symptôme: Combinaison filtres lourds (ex: tags=["tag1", "tag2", "tag3", "tag4"], date range 90j, scope=all) → query Oracle lente
- Prévention: Index sur EXECUTIONS.CREATED_AT, EXECUTIONS.ACTION_ID, ACTION_TAGS.TAG_NAME. Si nécessaire: ajouter timeout API 10s + message "Recherche trop large, essayez de restreindre les filtres".
- NFR: Requête < 2s (NFR1). Si dépassé en tests E2E, optimiser requête SQL (EXPLAIN PLAN Oracle).

### Performance Considerations

**Impact performance backend:**

1. **Clauses WHERE dynamiques**:
   - Ajout 7 conditions WHERE optionnelles → impact minime (filtres réduisent résultats, query plus rapide)
   - Index existants: EXECUTIONS(CREATED_AT, STATUS, ENVIRONMENT), ACTIONS_CATALOG(ID, ENGINE)
   - **Nouveau index recommandé**: ACTION_TAGS(TAG_NAME, ACTION_ID) pour optimiser filtrage tags

2. **JOIN supplémentaire sur ACTION_TAGS**:
   - Si tags filtres actifs: subquery avec HAVING COUNT(DISTINCT tag_name)
   - Impact: +50-100ms sur query si 1000+ exécutions
   - Optimisation: Index composite (TAG_NAME, ACTION_ID)

3. **Endpoint /timeseries**:
   - Query agrégée par date: `GROUP BY DATE(CREATED_AT)`
   - Impact: Query scan complet si date range large (90j)
   - Optimisation: Index EXECUTIONS(CREATED_AT, STATUS) — Oracle utilise index pour GROUP BY

**Impact performance frontend:**

1. **Refetch multi-composants**:
   - Appliquer filtres déclenche 3 fetches: StatCards, TrendLineChart, Table
   - **Solution**: React Query avec `queryKey` identique → fetches parallèles, cache partagé
   - Temps total: Max(fetch1, fetch2, fetch3) au lieu de Sum (grâce à parallélisme)

2. **URL navigation**:
   - `navigate({ search: queryString })` déclenche re-render page
   - **Solution**: React Router optimise navigation interne (pas de reload page), seuls composants dépendant de `location.search` re-render

3. **Select tags avec 100+ options**:
   - Ant Design Select virtual scrolling intégré → rendering performant même avec 500+ options
   - Searchable réduit cognitive load

**Benchmarking cible (NFR1):**
- Temps réponse API `/executions?filters=...` < 2s (avec 10 000 exécutions)
- Temps réponse API `/timeseries?filters=...` < 1s
- Rendering ExecutionsPage complet avec filtres < 500ms (skeleton loading pendant fetch)

**Optimisations futures (post-Story 9-10):**
- **Cache backend Redis**: Cache résultats queries communes (ex: "PROD + 7j") TTL 1min
- **Pagination TrendLineChart**: Si date range très large (>1 an), limiter points à max 100 (downsample)
- **Debounce Apply button**: Si utilisateur modifie filtres rapidement, debounce 300ms avant fetch

### Opportunités d'amélioration futures (post-Story 9-10)

**UX:**
- **Filtres favoris**: Permettre sauvegarder combinaison filtres (ex: "Échecs PROD 30j") pour réutilisation rapide
- **Filtres suggestions**: Afficher filtres suggérés selon contexte (ex: si échecs détectés, suggérer "Status: FAILED")
- **Export avec filtres**: Ajouter bouton "Export CSV/PDF" dans ExecutionsPage avec données filtrées (actuellement export existe uniquement dans Dashboard/Analytics)

**Performance:**
- **WebSocket live updates table**: Mettre à jour statuts exécutions en temps réel sans refresh (déjà implémenté pour ExecutionTimeline, étendre à table)
- **Infinite scroll table**: Remplacer pagination classique par infinite scroll (améliore UX si recherche exécution dans longue liste)

**Analytics:**
- **Filtre "Équipe" ou "Département"**: Ajouter filtre par équipe utilisateur (si métadonnée disponible)
- **Filtres avancés côté Dashboard/Analytics**: Garder synchronisation entre filtres ExecutionsPage et Dashboard pour workflow "analyser → explorer" fluide

**Accessibilité:**
- **Keyboard shortcuts**: Ajouter raccourcis (ex: Ctrl+F focus date picker, Ctrl+R reset filtres)
- **Screen reader**: Améliorer annonces vocales pour badge active filter count ("3 filtres actifs")

### References

**Code source:**
- [Source: idp-portal/frontend/src/pages/ExecutionsPage.tsx - Layout actuel StatCards + Tabs + Table]
- [Source: idp-portal/frontend/src/components/dashboard/reporting/ReportingDashboard.tsx - AdvancedFiltersPanel pattern + TrendLineChart]
- [Source: idp-portal/frontend/src/components/dashboard/reporting/TrendLineChart.tsx - Composant graphique lignes]
- [Source: idp-portal/backend/app/repositories/execution_repository.py - Fonction list_executions()]
- [Source: idp-portal/backend/app/api/routes/executions.py - Endpoint GET /executions]

**Documentation:**
- [Source: _bmad-output/planning-artifacts/architecture.md - Repository Pattern SQL brut (ligne 258)]
- [Source: _bmad-output/planning-artifacts/architecture.md - RBAC middleware (ligne 90)]
- [Source: _bmad-output/planning-artifacts/architecture.md - Cache in-memory (ligne 263)]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml - Story 9-10 definition (ligne 154)]

**Stories liées:**
- [Source: _bmad-output/implementation-artifacts/9-9-amelioration-table-executions.md - Story précédente Epic 9]
- [Source: Sprint status - Story 9-4: Déplacement statistiques exécutions vers page Exécutions (line 148)]
- [Source: Sprint status - Story 8-9: Tabs all/my executions with RBAC (line 140)]
- [Source: Sprint status - Story 8-3: Dashboard reporting statistiques (line 134)]
- [Source: Sprint status - Story 5-5: Alignement React & Ant 6.2 best practices (line 112)]

**Migrations database:**
- [Source: idp-portal/database/migrations/V002__create_actions_catalog.sql - Table ACTIONS_CATALOG avec ENGINE]
- [Source: idp-portal/database/migrations/VXX__create_action_tags.sql - Table ACTION_TAGS pour filtrage tags (si existe)]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
