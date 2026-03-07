# Inventaire des composants UI – Frontend

**Date :** 2026-02-21  
**Design system :** Ant Design (antd) 6.x

---

## Par zone fonctionnelle

### Layout
- `AppLayout` – Layout principal (sidebar, header, contenu).

### Auth
- `ProtectedRoute` – Route protégée (auth).
- `LoginPage` – Page de connexion (SAML).

### Catalogue
- `ActionCard`, `ActionTable`, `ActionDrawerPreview` – Carte, tableau, tiroir d’action.
- `ExecutionWizard` – Assistant d’exécution (étapes : paramètres, cibles, confirmation, planification).
- `ParametersFormStep`, `TargetSelectionStep`, `ConfirmationStep`, `SchedulingPanel` – Étapes du wizard.
- `HorizontalFilters`, `ActiveFiltersChips`, `CategoryTabs`, `TagCloud` – Filtres et navigation.
- `SectionHelp` – Aide contextuelle (markdown).

### Admin
- `ActionForm`, `ActionWizard`, `StepsEditor`, `WorkflowStepsEditor`, `WorkflowBuilderCanvas` – Édition d’actions et de workflows (XYFlow).
- `WorkflowStepNode`, `CustomEdge`, `WorkflowValidationAlert`, `WorkflowStepsRenderer` – Noeuds, arêtes, validation, rendu.
- `ProfileForm`, `ProfileWizard`, `ProfileImportModal` – Profils.
- `IntegrationForm`, `IntegrationsTable` – Intégrations.
- `BusinessRulePolicySelector`, `BusinessRulesPolicyPanel`, `ImpactRulesEditor`, `RemediationRulesEditor` – Règles métier.
- `ChangeTypeConfig`, `NotificationConfigSection`, `StepConfigPanel`, `ValidationReportPanel` – Config et rapports.
- `ActionPalette`, `AvailableActionsPanel`, `ActionStatusBadge`, `AdminPreview` – Palette et prévisualisation.
- `FeatureFlagsPanel` – Feature flags.
- `AdminAnalyticsDashboard`, `EngineBarChart`, `EnvironmentBarChart`, `AdoptionTrendChart`, `TrendLineChart`, `ComparisonPanel`, `ComparisonChart`, `ComparisonModeSelector`, `ComparisonExecutionsDrawer`, `AdvancedFiltersPanel`, `DeltaBadge` – Analytics et reporting.

### Exécutions
- `ExecutionsTabs`, `ExecutionsFiltersPanel`, `ExecutionDetailDrawer` – Liste, filtres, tiroir détail.
- `ExecutionTimeline`, `WorkflowExecutionGraph`, `StepDetailDrawer`, `StructuredErrorCard` – Détail d’exécution.

### Dashboard
- `RecentExecutions`, `ExecutionsChart`, `PendingApprovalsList`, `StatCard` – Dashboard principal.
- `ReportingDashboard` – Vue reporting.

### Calendrier
- `CalendarFiltersPanel`, `EventDetailsPopover`, `CancelExecutionModal` – Calendrier (FullCalendar) et modales.

### Partagés / communs
- `ImpactIndicator`, `CronExpressionHelper` – Indicateurs et utilitaires.
- `WorkflowIcon` – Icône workflow.
- `FeatureGuard`, `FeatureToggle` – Contrôle d’accès par feature.

---

## Technologies UI

- **Ant Design** : composants de base (Layout, Form, Table, Drawer, Modal, etc.).
- **@xyflow/react** : graphes de workflow (édition).
- **FullCalendar** : calendrier.
- **Recharts** : graphiques (dashboard, analytics).
- **react-markdown** : aide et contenu markdown.

---

*Généré par le workflow document-project (étape 4).*
