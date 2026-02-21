# test – Analyse de l'arbre des sources

**Date :** 2026-02-21

---

## Vue d'ensemble

Projet **multi-part** : frontend (SPA React/Vite) et backend (Django REST) sous `idp-portal/`. La racine du dépôt contient aussi `_bmad-output/`, `docs/` (documentation générée), et des artefacts de planification/implémentation.

---

## Structure multi-part

| Partie | Racine | Rôle |
|--------|--------|------|
| **Frontend** | `idp-portal/frontend/` | SPA React 19, Vite 7, Ant Design ; consomme l’API backend |
| **Django Backend** | `idp-portal/django_backend/` | API REST Django 5.1, DRF, Celery, Channels |

---

## Arbre des répertoires (essentiel)

```
idp-portal/
├── frontend/                    # Partie : Frontend (web)
│   ├── public/                  # Assets statiques (favicon, icons)
│   ├── src/
│   │   ├── main.tsx              # Point d'entrée app
│   │   ├── App.tsx               # Racine React
│   │   ├── components/           # Composants UI (admin, catalog, dashboard, execution, layout, …)
│   │   ├── pages/                # Pages (CatalogPage, ExecutionsPage, AdminPage, DashboardPage, …)
│   │   ├── services/             # Client API (api_client, auth, catalog, execution, …)
│   │   ├── hooks/                # Hooks métier et UI
│   │   ├── contexts/             # Auth, Theme, FeatureFlag, Dashboard
│   │   ├── types/                # Types TS (api/, common)
│   │   ├── utils/                # Helpers, rendus, formatage
│   │   ├── theme/                # Thème (ex. Desjardins)
│   │   └── styles/               # CSS (ex. glass.css)
│   ├── vite.config.ts            # Config Vite
│   ├── tsconfig.json
│   ├── package.json
│   ├── Dockerfile
│   └── nginx.conf
│
├── django_backend/               # Partie : Backend
│   ├── idp_backend/              # Projet Django (settings, urls, asgi, celery)
│   │   ├── settings.py
│   │   ├── urls.py               # Racine URL → include apps
│   │   ├── asgi.py
│   │   └── celery.py
│   ├── core/                     # Health, feature flags, audit, middleware
│   ├── catalog/                  # Actions, tags, business rules, ViewSets
│   ├── executions/               # Exécutions, étapes, planifiées, webhooks
│   ├── dashboard/                # Stats, recent, timeseries, export
│   ├── audit/                    # Audit exécutions, export
│   ├── idp_auth/                 # SAML, JWT, users, favorites
│   ├── integrations/             # Intégrations, types, upload icônes
│   ├── profiles/                 # Profils, permissions, export/import
│   ├── inventory/                # Cibles, environnements, serveurs, instances, DB
│   ├── reference/                # Engines, platforms, categories
│   ├── help/                     # Aide contextuelle (topics)
│   ├── admin_analytics/          # Analytics admin
│   ├── adapters/                 # Ansible Tower, GitHub, Terraform Cloud, …
│   ├── services/                 # Services métier (Jira, ServiceNow, notification, …)
│   ├── manage.py
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── docs/                     # Doc technique backend
│
├── database/                     # Migrations SQL (Flyway-style, ex. V079–V082)
├── docs/                         # Doc transverse (sécurité, API, ops, …)
├── nginx/                        # Config Nginx / systemd
└── scripts/                      # deploy.sh, etc.

docs/                             # Documentation générée (project knowledge)
_bmad-output/                     # Artefacts BMad (planning, implementation)
```

---

## Dossiers critiques

### Frontend (`idp-portal/frontend/`)

| Dossier | Rôle | Points d'entrée / contenu clé |
|---------|------|-------------------------------|
| `src/` | Code source SPA | `main.tsx`, `App.tsx` |
| `src/components/` | Composants React (layout, admin, catalog, dashboard, execution, shared) | Composants réutilisables et par page |
| `src/pages/` | Pages / routes | CatalogPage, ExecutionsPage, AdminPage, DashboardPage, AuditPage, CalendarPage, LoginPage |
| `src/services/` | Couche API | `api_client.ts`, auth, catalog, execution, profiles, integrations, reference, … |
| `src/hooks/` | Hooks métier et UI | useExecution*, useEngines, useCategories, useHelpContent, … |
| `src/contexts/` | État global | AuthContext, ThemeContext, FeatureFlagContext, DashboardContext |
| `src/types/` | Types TypeScript | `api/` (contrats API), `common` |
| `src/utils/` | Helpers | formatage, rendus, conversion workflow |
| `public/` | Assets statiques | favicon, icons (engines, etc.) |

### Django Backend (`idp-portal/django_backend/`)

| Dossier | Rôle | Points d'entrée / contenu clé |
|---------|------|-------------------------------|
| `idp_backend/` | Projet Django | `settings.py`, `urls.py`, `asgi.py`, `celery.py` |
| `core/` | Santé, feature flags, audit, middleware, résilience DB | `views.py`, `models.py`, `middleware.py` |
| `catalog/` | Catalogue d’actions, tags, règles métier | `views.py`, `models.py`, `urls.py`, ViewSets |
| `executions/` | Exécutions, étapes, planifiées, webhooks | `views/`, `models.py`, `urls.py`, `consumers.py` |
| `dashboard/` | Statistiques et exports | `views.py`, `export_views.py` |
| `audit/` | Journal d’audit | `views.py`, `urls.py` |
| `idp_auth/` | Auth SAML/JWT, profil, favoris | `views.py`, `urls.py`, `models.py` |
| `integrations/` | Intégrations et types | ViewSets, `upload_views.py`, `catalogue_views.py` |
| `profiles/` | Profils et permissions | ViewSets, export/import |
| `inventory/` | Cibles, environnements, multi-tables | `views.py`, `mapper.py`, `query_executor.py` |
| `reference/` | Engines, platforms, categories | `views.py`, `models.py`, `admin_urls.py` |
| `help/` | Aide contextuelle | `views.py`, `topics.py` |
| `admin_analytics/` | Analytics admin | `views.py` |
| `adapters/` | Intégrations externes (Tower, GitHub, Terraform, …) | Adapters AAP, Terraform, GitHub |
| `services/` | Services métier (Jira, ServiceNow, notification) | Services externes |

---

## Points d'intégration (Frontend → Backend)

| Depuis (Frontend) | Vers (Backend) | Détails |
|-------------------|----------------|---------|
| `src/services/api_client.ts` | `/api/v1/*` | Client HTTP unique (Bearer JWT, retries, X-Correlation-ID) |
| `src/services/*_service.ts` | Endpoints REST par domaine | Catalogue, exécutions, profils, intégrations, reference, auth, dashboard, audit, help |

Les appels passent par la même origine (proxy ou Nginx) vers `/api/v1/` ; pas de CORS cross-origin en production si tout est servi ensemble.

---

*Généré par le workflow document-project (étape 5).*
