# Gestion d'état – Frontend

**Date :** 2026-02-21

---

## Contexte React (Context API)

| Contexte | Fichier | Rôle |
|----------|---------|------|
| AuthContext | `contexts/AuthContext.tsx` | Utilisateur courant, token, login/logout/refresh |
| ThemeContext | `contexts/ThemeContext.tsx` | Thème (ex. Desjardins), couleurs |
| FeatureFlagContext | `contexts/FeatureFlagContext.tsx` | Feature flags (consommation API) |
| DashboardContext | `contexts/DashboardContext.tsx` | Contexte dashboard (filtres, données) |

---

## Hooks métier (état serveur + local)

- **Auth / profil :** intégration avec AuthContext.
- **Catalogue / exécutions :** `useExecutionSubmit`, `useExecutionDetail`, `useExecutionFilters`, `useEditExecution`, `useExecutionRestart`, `useCancelExecution`, `usePendingApprovalsCount`, `useWorkflowExportImport`, `useRemediationSuggestions`.
- **Référentiels :** `useEngines`, `usePlatforms`, `useCategories`, `useAAPTemplates`, `useServiceNowIntegrations`, `usePlatformIntegrations`.
- **Admin :** `useHelpContent` (aide contextuelle).
- **UI :** `useMediaQuery`, `useCalendarFilters`.

État serveur : chargement via services (api_client) ; état local dans les composants (useState/useReducer) et dans les contextes ci‑dessus. Pas de Redux/MobX ; stack React + hooks + Context.

---

*Généré par le workflow document-project (étape 4).*
