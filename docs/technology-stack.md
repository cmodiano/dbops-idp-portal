# Stack technique – test (idp-portal)

**Date :** 2026-02-21

---

## Frontend (idp-portal/frontend)

| Catégorie | Technologie | Version | Justification |
|-----------|-------------|---------|---------------|
| Langage | TypeScript | ~5.9.3 | Typage statique, tooling |
| Framework UI | React | ^19.2.0 | SPA, écosystème |
| Build / Dev | Vite | ^7.2.4 | Bundler, HMR |
| UI / Design | Ant Design (antd) | ^6.2.2 | Composants, thème |
| Routage | React Router | ^7.13.0 | Routing client |
| Graph / workflows | @xyflow/react | ^12.10.0 | Diagrammes, flows |
| Calendrier | FullCalendar (daygrid, timegrid, interaction, react) | ^6.1.20 | Planning, calendrier |
| Drag & drop | @dnd-kit (core, sortable, utilities) | ^6.3.1 / ^10.0.0 | Listes réordonnables |
| Graphiques | Recharts | ^3.7.0 | Visualisations |
| Markdown | react-markdown, remark-gfm, rehype-sanitize | ^10.1.0, ^4.0.1, ^6.0.0 | Contenu markdown sécurisé |
| Utilitaires | js-yaml, html2canvas | ^4.1.1, ^1.4.1 | YAML, capture écran |
| Tests | Vitest, Testing Library (React, user-event, jest-dom) | ^4.0.18, ^16.3.2 / ^14.6.1 / ^6.9.1 | Unit / composants |
| Lint / qualité | ESLint, typescript-eslint, plugins React/Hooks/Refresh/Security | ^9.39.1, ^8.46.4 | Standards, sécurité |
| Couverture | @vitest/coverage-v8 | ^4.0.18 | Couverture de code |

---

## Django Backend (idp-portal/django_backend)

| Catégorie | Technologie | Version | Justification |
|-----------|-------------|---------|---------------|
| Langage | Python | >=3.12 | Runtime backend |
| Framework | Django | >=5.1.0,<6.0 | API, ORM, admin |
| API REST | Django REST Framework | >=3.15.0 | REST, sérialisation |
| Serveur WSGI | Gunicorn | >=22.0.0 | Production |
| Async / WebSocket | Daphne, Channels | >=4.1.0 | ASGI, temps réel |
| Base de données | oracledb | >=3.4.1 | Oracle |
| Cache / tâches | Redis, Celery[redis] | >=5.0.0, >=5.4.0 | Cache, file de tâches |
| Auth | python-jose[cryptography], python3-saml | >=3.3.0, >=1.16.0 | JWT, SAML/SSO |
| HTTP client | httpx, requests | >=0.27.0, >=2.32.5 | Appels sortants |
| Config / secrets | python-dotenv | >=1.0.0 | Variables d’environnement |
| Logging | structlog | >=24.1.0 | Logs structurés |
| Planification | croniter | >=6.0.0 | Crons |
| Cache applicatif | cachetools | >=5.3.0 | Cache en mémoire |
| API docs | drf-spectacular | >=0.27.0 | OpenAPI/Swagger |
| PDF | reportlab | >=3.6.0 | Génération PDF |
| CORS | django-cors-headers | >=4.3.0 | CORS |
| Sécurité / XML | defusedxml | >=0.7.1 | Parsing XML sécurisé |
| Dev / tests | pytest, pytest-django, pytest-cov, pytest-mock, factory-boy, Faker, mypy, ruff, bandit, pip-audit, detect-secrets | (voir pyproject) | Tests, typage, qualité, sécurité |

---

*Généré par le workflow document-project (étape 3).*
