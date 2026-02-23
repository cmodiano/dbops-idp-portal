# Contrats API – Frontend (client)

**Date :** 2026-02-21

---

## Vue d'ensemble

- **Base URL :** `/api/v1` (relative, même origine)
- **Client central :** `src/services/api_client.ts` – `handleAuthenticatedFetch`, `apiFetch`, `apiFetchRaw`
- **Auth :** Bearer JWT injecté via `setAuthAccessors(getToken, refreshFn)` ; retry 401 après refresh
- **Retry :** 429 (rate limit) avec backoff ; 503 `DB_UNAVAILABLE` retenté (configurable)
- **Header :** `X-Correlation-ID` pour traçabilité

---

## Services consommateurs (appels API)

| Service | Rôle |
|---------|------|
| `api_client.ts` | Fetch authentifié, retries, erreurs |
| `auth_service.ts` | Login SAML, refresh, logout, profil |
| `catalog_service.ts` | Catalogue actions, favoris |
| `execution_service.ts` | Exécutions, étapes, logs, approve/reject/cancel |
| `scheduled_execution_service.ts` | Exécutions planifiées, cron |
| `profiles_service.ts` | Profils, export/import |
| `integrations_service.ts` | Intégrations, types |
| `reference_service.ts` | Engines, platforms, categories |
| `categories_service.ts` | Catégories |
| `business_rules_service.ts` | Politiques de règles métier |
| `admin_service.ts` | Admin (actions, analytics, etc.) |
| `featureFlagService.ts` | Feature flags |
| `help_service.ts` | Aide contextuelle (help topics) |

Les chemins appelés reflètent les routes du backend (`/api/v1/...` avec trailing slash).

---

*Généré par le workflow document-project (étape 4).*
