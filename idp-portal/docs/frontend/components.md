# Composants principaux

Ce document décrit les composants React du frontend IDP Portal, organisés par feature.

## Vue d'ensemble

```
components/
├── admin/       # Administration (DBOPS, admins)
├── auth/        # Authentification
├── catalog/     # Catalogue d'actions
├── dashboard/   # Dashboard et statistiques
├── execution/   # Détail exécution
├── executions/  # Liste exécutions
├── layout/      # Layout et navigation
└── shared/      # Composants partagés
```

---

## Admin (`src/components/admin/`)

Composants d'administration pour la gestion des actions, profils et intégrations.

### ActionWizard

Wizard multi-étapes pour créer ou éditer une action.

```typescript
interface ActionWizardProps {
  mode: 'create' | 'edit';
  actionId?: number;          // Requis si mode='edit'
  onSuccess?: () => void;     // Callback après sauvegarde
  onCancel?: () => void;      // Callback annulation
}
```

**Étapes du wizard :**
1. Métadonnées (nom, description, catégorie, tags)
2. Paramètres (éditeur JSON Schema visuel)
3. Étapes d'exécution (configuration plateforme)

**Dépendances :** `ActionForm`, `ParametersEditor`, `StepsEditor`, `admin_service`

**Fichier :** `admin/ActionWizard.tsx` (~23KB)

---

### ProfileWizard

Wizard pour créer ou éditer un profil utilisateur avec permissions.

```typescript
interface ProfileWizardProps {
  mode: 'create' | 'edit';
  profileId?: number;
  onSuccess?: () => void;
  onCancel?: () => void;
}
```

**Étapes :**
1. Informations de base (nom, description)
2. Permissions actions (quelles actions autorisées)
3. Permissions targets (quels environnements)

**Dépendances :** `ProfileForm`, `profiles_service`

**Fichier :** `admin/ProfileWizard.tsx` (~14KB)

---

### ParametersEditor

Éditeur visuel pour les paramètres d'action (JSON Schema).

```typescript
interface ParametersEditorProps {
  value: ParameterDefinition[];
  onChange: (params: ParameterDefinition[]) => void;
  disabled?: boolean;
}

interface ParameterDefinition {
  name: string;
  label: string;
  type: 'string' | 'number' | 'boolean' | 'select' | 'multiselect';
  required?: boolean;
  default?: unknown;
  options?: string[];       // Pour select/multiselect
  validation?: {
    min?: number;
    max?: number;
    pattern?: string;
  };
}
```

**Fichier :** `admin/ParametersEditor.tsx` (~9KB)

---

### ImpactRulesEditor

Éditeur visuel des règles d'impact par environnement.

```typescript
interface ImpactRulesEditorProps {
  value: ImpactRule[];
  onChange: (rules: ImpactRule[]) => void;
  environments: string[];    // Liste des environnements disponibles
}

interface ImpactRule {
  environment: string;
  impact_level: 'low' | 'medium' | 'high' | 'critical';
  requires_approval?: boolean;
  change_type?: string;      // Code modèle ServiceNow
}
```

**Fichier :** `admin/ImpactRulesEditor.tsx` (~6KB)

---

### RemediationRulesEditor

Éditeur des règles d'actions correctives (auto-remédiation).

```typescript
interface RemediationRulesEditorProps {
  actionId: number;
  value: RemediationRule[];
  onChange: (rules: RemediationRule[]) => void;
}

interface RemediationRule {
  error_pattern: string;      // Regex pour matcher l'erreur
  suggestion_text: string;    // Texte affiché à l'utilisateur
  corrective_action_id?: number;
  risk_level: 'low' | 'medium' | 'high';
  auto_trigger?: boolean;     // Déclenchement automatique
}
```

**Fichier :** `admin/RemediationRulesEditor.tsx` (~10KB)

---

### IntegrationForm

Formulaire pour configurer une intégration (AAP, ServiceNow, etc.).

```typescript
interface IntegrationFormProps {
  mode: 'create' | 'edit';
  integrationId?: number;
  onSuccess?: () => void;
  onCancel?: () => void;
}
```

**Champs :**
- `name` : Nom de l'intégration
- `type` : Type (aap, servicenow, terraform, custom)
- `base_url` : URL de la plateforme
- `credential_ref` : Référence Vault pour credentials
- `icon` : Icône personnalisée (upload)

**Fichier :** `admin/IntegrationForm.tsx` (~10KB)

---

### ScheduledExecutionsPage

Page de gestion des exécutions planifiées.

```typescript
// Utilisé comme page dans AdminPage via tabs
// Pas de props - utilise les services directement
```

**Fonctionnalités :**
- Liste des exécutions planifiées (one-time et recurring)
- Annulation d'une planification
- Toggle activation patterns récurrents
- Filtres par statut et action

**Fichier :** `admin/ScheduledExecutionsPage.tsx` (~25KB)

---

## Catalog (`src/components/catalog/`)

Composants du catalogue d'actions pour les utilisateurs.

### ExecutionWizard

Wizard d'exécution d'une action en 4 étapes. **Plus gros composant du frontend (~52KB)**.

```typescript
interface ExecutionWizardProps {
  actionId: number;
  visible: boolean;
  onClose: () => void;
  onSuccess?: (executionId: number) => void;
}
```

**Étapes :**
1. **Paramètres** : Formulaire dynamique selon JSON Schema de l'action
2. **Impact** : Affichage niveau d'impact et approbations requises
3. **Planification** : Exécution immédiate ou planifiée (date/récurrence)
4. **Confirmation** : Résumé et soumission

**Features :**
- Validation temps réel des paramètres
- Calcul impact par environnement
- Support expressions cron pour récurrence
- Gestion approbations production

**Dépendances :** `execution_service`, `useAuth`, `CronExpressionHelper`, `utils/debounce` (validation cron en temps réel)

**Fichier :** `catalog/ExecutionWizard.tsx` (~52KB)

---

### ActionCard

Carte d'action pour la vue grille du catalogue.

```typescript
interface ActionCardProps {
  action: CatalogAction;
  onExecute: (actionId: number) => void;
  onPreview: (actionId: number) => void;
  isFavorite?: boolean;
  onToggleFavorite?: (actionId: number) => void;
}

interface CatalogAction {
  id: number;
  name: string;
  description: string;
  category: string;
  tags: string[];
  engine: 'Oracle' | 'SQL Server' | 'DB2';
  impact_level: 'low' | 'medium' | 'high' | 'critical';
  is_favorite?: boolean;
}
```

**Fichier :** `catalog/ActionCard.tsx` (~9KB)

---

### ActionTable

Table d'actions pour la vue liste du catalogue.

```typescript
interface ActionTableProps {
  actions: CatalogAction[];
  loading?: boolean;
  onExecute: (actionId: number) => void;
  onPreview: (actionId: number) => void;
  favorites: Set<number>;
  onToggleFavorite: (actionId: number) => void;
}
```

**Colonnes :** Nom, Catégorie, Tags, Engine, Impact, Actions

**Fichier :** `catalog/ActionTable.tsx` (~11KB)

---

### ActionDrawerPreview

Drawer latéral avec preview détaillée d'une action.

```typescript
interface ActionDrawerPreviewProps {
  actionId: number | null;
  visible: boolean;
  onClose: () => void;
  onExecute: (actionId: number) => void;
}
```

**Contenu :**
- Description complète
- Documentation markdown
- Métriques (taux succès, durée moyenne)
- Liste des paramètres
- Bouton exécuter

**Fichier :** `catalog/ActionDrawerPreview.tsx` (~14KB)

---

### CategoryTabs

Navigation par catégorie d'actions.

```typescript
interface CategoryTabsProps {
  categories: string[];
  activeCategory: string | null;
  onChange: (category: string | null) => void;
  counts?: Record<string, number>;  // Nombre d'actions par catégorie
}
```

**Fichier :** `catalog/CategoryTabs.tsx` (~3KB)

---

### TagCloud

Nuage de tags pour filtrer les actions.

```typescript
interface TagCloudProps {
  tags: Array<{ name: string; count: number }>;
  selectedTags: string[];
  onChange: (tags: string[]) => void;
  maxVisible?: number;        // Limite affichage (défaut: 20)
}
```

**Fichier :** `catalog/TagCloud.tsx` (~3KB)

---

### HorizontalFilters

Barre de filtres horizontale (recherche, catégorie, tags).

```typescript
interface HorizontalFiltersProps {
  searchValue: string;
  onSearchChange: (value: string) => void;
  categories: string[];
  selectedCategory: string | null;
  onCategoryChange: (category: string | null) => void;
  tags: string[];
  selectedTags: string[];
  onTagsChange: (tags: string[]) => void;
}
```

**Fichier :** `catalog/HorizontalFilters.tsx` (~3KB)

---

## Dashboard (`src/components/dashboard/`)

Composants pour le dashboard et les statistiques.

### StatCard

Carte KPI affichant une statistique.

```typescript
interface StatCardProps {
  title: string;
  value: number | string;
  icon?: React.ReactNode;
  trend?: {
    value: number;
    direction: 'up' | 'down';
  };
  color?: string;
  loading?: boolean;
}
```

**Fichier :** `dashboard/StatCard.tsx` (~3KB)

---

### RecentExecutions

Liste des exécutions récentes avec statut.

```typescript
interface RecentExecutionsProps {
  executions: ExecutionSummary[];
  loading?: boolean;
  onViewDetails: (executionId: number) => void;
  maxItems?: number;          // Défaut: 5
}
```

**Fichier :** `dashboard/RecentExecutions.tsx` (~10KB)

---

### PendingApprovalsList

Liste des approbations en attente pour l'utilisateur.

```typescript
interface PendingApprovalsListProps {
  onApprove: (requestId: number) => void;
  onReject: (requestId: number, reason: string) => void;
}
```

**Fichier :** `dashboard/PendingApprovalsList.tsx` (~7KB)

---

## Execution (`src/components/execution/`)

Composants pour le détail d'une exécution.

### ExecutionTimeline

Timeline temps réel des étapes d'exécution avec WebSocket.

```typescript
interface ExecutionTimelineProps {
  executionId: number;
  onComplete?: () => void;
  onError?: (error: string) => void;
}
```

**Features :**
- Mise à jour temps réel via WebSocket
- Affichage statut par étape (PENDING, RUNNING, COMPLETED, FAILED)
- Logs et output par étape
- Gestion erreurs et suggestions de remédiation

**Dépendances :** `useWebSocket`, `StructuredErrorCard`

**Fichier :** `execution/ExecutionTimeline.tsx` (~25KB)

---

### StructuredErrorCard

Carte d'erreur structurée avec suggestions de correction.

```typescript
interface StructuredErrorCardProps {
  error: StructuredError;
  remediationSuggestions?: RemediationSuggestion[];
  onTriggerRemediation?: (suggestionId: number) => void;
}

interface StructuredError {
  error_code?: string;
  error_message: string;
  error_details?: string;
  stack_trace?: string;
}
```

**Fichier :** `execution/StructuredErrorCard.tsx` (~7KB)

---

## Layout (`src/components/layout/`)

Composants de layout et navigation.

### AppLayout

Layout principal avec header et contenu.

```typescript
interface AppLayoutProps {
  children?: React.ReactNode;  // Via Outlet de react-router
}
```

**Structure :**
```
┌─────────────────────────────────┐
│           TopNav                │
├─────────────────────────────────┤
│                                 │
│          <Outlet />             │
│         (contenu page)          │
│                                 │
└─────────────────────────────────┘
```

**Fichier :** `layout/AppLayout.tsx` (~1KB)

---

### TopNav

Barre de navigation supérieure.

```typescript
// Pas de props - utilise useAuth et useTheme
```

**Éléments :**
- Logo DBOps
- Tabs de navigation (Catalogue, Exécutions, Analytics, Admin, Audit)
- Badge notifications (approbations en attente)
- Toggle dark/light mode
- Menu utilisateur (profil, déconnexion)

**Contrôle d'accès :**
- Tabs visibles selon `user.navigation_tabs`
- Analytics : DBOPS uniquement
- Admin : tab admin requis
- Audit : tab audit ou is_auditor

**Fichier :** `layout/TopNav.tsx` (~10KB)

---

## Shared (`src/components/shared/`)

Composants réutilisables partagés entre features.

### ImpactIndicator

Indicateur visuel du niveau d'impact.

```typescript
interface ImpactIndicatorProps {
  level: 'low' | 'medium' | 'high' | 'critical';
  showLabel?: boolean;        // Afficher le texte (défaut: true)
  size?: 'small' | 'default'; // Taille de l'indicateur
}
```

**Couleurs :**
- `low` : vert (#10B981)
- `medium` : orange (#F59E0B)
- `high` : orange foncé (#F97316)
- `critical` : rouge (#EF4444)

**Fichier :** `shared/ImpactIndicator.tsx` (~2KB)

---

### CronExpressionHelper

Helper pour construire des expressions cron visuellement.

```typescript
interface CronExpressionHelperProps {
  value: string;              // Expression cron actuelle
  onChange: (cron: string) => void;
  presets?: CronPreset[];     // Presets personnalisés
}

// Presets par défaut
const DEFAULT_PRESETS = [
  { label: 'Toutes les heures', cron: '0 * * * *' },
  { label: 'Tous les jours à minuit', cron: '0 0 * * *' },
  { label: 'Tous les lundis', cron: '0 0 * * 1' },
  { label: 'Premier du mois', cron: '0 0 1 * *' },
];
```

**Fichier :** `shared/CronExpressionHelper.tsx` (~4KB)

---

## Auth (`src/components/auth/`)

Composants d'authentification.

### ProtectedRoute

Guard de route pour les pages authentifiées.

```typescript
interface ProtectedRouteProps {
  children: React.ReactNode;
}
```

**Comportement :**
- Si `isLoading` : affiche spinner
- Si non authentifié : redirige vers `/login`
- Si authentifié : affiche `children`

**Fichier :** `auth/ProtectedRoute.tsx`

---

## Patterns communs

### Barrel exports (`index.ts`)

Chaque dossier feature a un fichier `index.ts` pour exports groupés :

```typescript
// components/catalog/index.ts
export { ActionCard } from './ActionCard';
export { ActionTable } from './ActionTable';
export { ExecutionWizard } from './ExecutionWizard';
// ...
```

Usage :
```typescript
import { ActionCard, ActionTable } from './components/catalog';
```

### Tests co-localisés

Les tests sont dans le même dossier que le composant :

```
catalog/
├── ActionCard.tsx
├── ActionCard.test.tsx
├── ExecutionWizard.tsx
└── ExecutionWizard.test.tsx
```

### App wrapper pour tests

Composants utilisant `App.useApp()` doivent être wrappés :

```typescript
import { App } from 'antd';

function renderWithApp(ui: React.ReactElement) {
  return render(<App>{ui}</App>);
}

it('should show notification', () => {
  renderWithApp(<MyComponent />);
  // ...
});
```
