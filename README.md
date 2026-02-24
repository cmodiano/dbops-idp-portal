# IDP Portal — Plateforme interne pour les opérations base de données

[![CI](https://github.com/cmodiano/dbops-idp-portal/actions/workflows/ci.yml/badge.svg)](https://github.com/cmodiano/dbops-idp-portal/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/cmodiano/dbops-idp-portal/graph/badge.svg)](https://codecov.io/gh/cmodiano/dbops-idp-portal)
[![Couverture Backend](https://codecov.io/gh/cmodiano/dbops-idp-portal/branch/main/graph/badge.svg?flag=django-backend)](https://codecov.io/gh/cmodiano/dbops-idp-portal?flag=django-backend)
[![Couverture Frontend](https://codecov.io/gh/cmodiano/dbops-idp-portal/branch/main/graph/badge.svg?flag=frontend)](https://codecov.io/gh/cmodiano/dbops-idp-portal?flag=frontend)

**IDP Portal** est une plateforme interne pour les opérations base de données. Elle offre un portail unifié pour les équipes DBOPS afin de gérer les actions, exécuter des workflows, suivre les exécutions et administrer le catalogue, les profils et les intégrations.

---

## Vue d'ensemble

| Composant | Technologie | Description |
|-----------|-------------|-------------|
| **Frontend** | React 19, Vite 7, TypeScript, Ant Design 6 | SPA : catalogue d'actions, exécutions, dashboard, admin, calendrier, audit |
| **Backend** | Django 5.1, DRF, Oracle, Redis, Celery, Channels | API REST : catalogue, exécutions, profils, intégrations, inventaire, auth, aide |

Le frontend consomme l'API REST du backend via HTTP JSON (`/api/v1`). L'authentification utilise SAML/JWT.

---

## Fonctionnalités

- **Catalogue d'actions** — Parcourir, rechercher et exécuter des opérations base de données (backup, patching, provisioning, etc.)
- **Exécutions** — Lancer des actions, suivre le statut, consulter les logs, approuver/rejeter les workflows
- **Dashboard** — Statistiques et activité récente
- **Admin** — Gérer les actions, profils, intégrations et cibles d'inventaire
- **Audit** — Journal d'audit et export
- **RBAC** — Contrôle d'accès par rôles (profils DBOPS, DBA, Business)

---

## Démarrage rapide

### Prérequis

- **Node.js** (LTS) — frontend
- **Python 3.12+** — backend
- **Oracle 19c+** — base de données (dev local via Docker)
- **Redis** — cache et Celery

### Frontend

```bash
cd idp-portal/frontend
npm install
npm run dev
```

### Backend

```bash
cd idp-portal/django_backend
python -m venv .venv
source .venv/bin/activate
uv pip install -r requirements-dev.lock
python manage.py runserver
```

### Oracle (Docker)

```bash
cd idp-portal
docker compose up -d oracle
```

Voir [idp-portal/README.md](idp-portal/README.md) pour la configuration complète, les variables d'environnement, les migrations et le déploiement Docker.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Vue d'ensemble du projet](docs/project-overview.md) | Résumé, classification, liens |
| [Index](docs/index.md) | Point d'entrée de la documentation |
| [Architecture — Frontend](docs/architecture-frontend.md) | Architecture SPA, composants |
| [Architecture — Backend](docs/architecture-django_backend.md) | Architecture API, modèles |
| [Architecture d'intégration](docs/integration-architecture.md) | Frontend ↔ Backend, auth, erreurs |
| [Stack technique](docs/technology-stack.md) | Technologies frontend et backend |
| [Guide de développement](docs/development-guide.md) | Installation, commandes, pre-commit |
| [Guide de contribution](docs/contribution-guide.md) | Standards, checklist PR |

---

## Structure du projet

```text
├── idp-portal/
│   ├── frontend/          # SPA React
│   ├── django_backend/    # API REST Django
│   ├── database/          # Migrations Flyway, scripts d'init
│   ├── scripts/           # Utilitaires (migrations, seed, validation)
│   └── docs/              # Documentation technique
├── docs/                  # Documentation du projet
└── .github/workflows/     # CI (lint, tests, sécurité, build)
```

---

## Contribution

Voir [CONTRIBUTING.md](CONTRIBUTING.md) et [docs/contribution-guide.md](docs/contribution-guide.md) pour les standards, l'onboarding et les guidelines PR.
