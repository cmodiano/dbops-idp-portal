# Architecture – Frontend (idp-portal/frontend)

**Date :** 2026-02-26

---

## Résumé

SPA React 19 + Vite 7 + TypeScript, avec Ant Design pour l’UI. Le frontend consomme l’API REST du backend Django ; auth JWT après flux SAML. Architecture composants + hooks + Context API, sans Redux.

---

## Stack technique

Voir **[technology-stack.md](../overview/technology-stack.md)** (section Frontend). Principaux éléments : React 19, Vite 7, TypeScript ~5.9, Ant Design 6, React Router 7, @xyflow/react, FullCalendar, Recharts, Vitest.

---

## Pattern d’architecture

- **Type :** SPA (Single Page Application), architecture par **composants** et **routage client**.
- **État :** Context API (Auth, Theme, FeatureFlag, Dashboard) + hooks métier (exécutions, catalogue, référentiels). Voir **[state-management.md](../frontend/state-management.md)**.
- **Données :** Pas de base locale ; types TypeScript dans `src/types/api/` alignés sur l’API backend.

---

## API (client)

- Client central : `src/services/api_client.ts` (fetch authentifié, retries 401/429/503, `X-Correlation-ID`).
- Services par domaine : catalog, execution, profiles, integrations, reference, admin, help, etc. Voir **[contracts-frontend.md](../api/contracts-frontend.md)** et **[integration.md](./integration.md)**.

---

## Composants

Inventaire dans **[component-inventory.md](../frontend/component-inventory.md)** : layout (AppLayout), auth (ProtectedRoute, LoginPage), catalogue (ActionCard, ExecutionWizard, filtres), admin (ActionForm, WorkflowBuilder, profils, intégrations, analytics), exécutions, dashboard, calendrier, partagés.

---

## Arbre des sources

Voir **[source-tree-analysis.md](../overview/source-tree-analysis.md)** (section Frontend). Points d’entrée : `main.tsx`, `App.tsx`. Dossiers clés : `components/`, `pages/`, `services/`, `hooks/`, `contexts/`, `types/`, `utils/`.

---

## Développement

- **Prérequis :** Node.js LTS.
- **Commandes :** `npm run dev`, `npm run build`, `npm run test`, `npm run test:coverage`, `npm run lint`. Voir **[development-guide.md](../reference/development-guide.md)**.

---

## Déploiement

- Build : `npm run build` ; artefacts servis par Nginx (ou équivalent). Voir **[deployment.md](../operations/deployment.md)**.

---

## Tests

- **Framework :** Vitest + Testing Library (React, user-event, jest-dom).
- **Couverture :** `npm run test:coverage`. Tests unitaires et composants dans `**/*.test.ts(x)`, `**/__tests__/**`.

---

*Généré par le workflow document-project (étape 8).*
