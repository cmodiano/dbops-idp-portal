# Architecture d'intégration – Frontend ↔ Backend

**Date :** 2026-02-26

---

## Vue d'ensemble

- **Frontend** (React/Vite) et **Backend** (Django REST) communiquent via **HTTP REST** sur la même origine en production (reverse proxy sert le frontend et proxy `/api/v1` vers Django).
- **Auth :** JWT Bearer ; le frontend obtient le token via flux SAML (redirect login/callback) puis envoie `Authorization: Bearer <token>` à chaque requête ; refresh via `auth/refresh/`.

---

## Flux d'intégration

| Sens | Mécanisme | Détails |
|------|-----------|---------|
| Frontend → Backend | REST (JSON) | `src/services/api_client.ts` : `fetch()` vers `/api/v1/*`, trailing slash, headers (Authorization, X-Correlation-ID, Content-Type). |
| Backend → Frontend | Réponses JSON | Format standardisé (ex. `{ "data": ... }` ou `{ "error": { "code", "message", "details" } }`). |
| Temps réel (optionnel) | WebSockets | Backend : Django Channels (ASGI) ; frontend : abonnements pour mises à jour (ex. dashboard). |

---

## Points d'intégration par domaine

- **Auth :** `auth/saml/login`, `auth/saml/callback`, `auth/me`, `auth/refresh`, `auth/logout`.
- **Catalogue :** `catalog/actions/`, `admin/actions/`, `tags/`, `users/me/favorites/`.
- **Exécutions :** `executions/`, `executions/<id>/`, approve/reject/cancel, steps, logs, scheduled-executions.
- **Profils :** `admin/profiles/profiles/`, export/import.
- **Intégrations :** `admin/integrations/`, `integrations/types/`.
- **Référentiels :** `reference/engines/`, `reference/platforms/`, `reference/categories/`.
- **Inventory :** `inventory/targets/`, `inventory/environments/`, servers/instances/databases.
- **Dashboard / Audit / Help :** `dashboard/*`, `audit/*`, `help/<topic_id>/`.

Les types TypeScript (`src/types/api/`) reflètent les contrats backend ; la doc OpenAPI (`/api/schema/`) fait référence unique pour l’API.

---

## Gestion des erreurs et résilience

- **401 :** le client tente un refresh du token puis rejoue la requête (une fois).
- **429 :** retry avec backoff (header Retry-After ou exponentiel).
- **503 DB_UNAVAILABLE :** retry configurable (résilience DB backend).
- Les erreurs sont exposées via `ApiError` (status, responseBody) pour affichage côté UI.

---

*Généré par le workflow document-project (étape 7).*
