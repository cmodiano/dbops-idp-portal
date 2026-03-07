# Analyse conditionnelle – Résumé

**Date :** 2026-02-21  
**Niveau de scan :** deep

---

## Frontend (web)

| Exigence | Fait | Livrable |
|----------|------|----------|
| API scan | Oui | api-contracts-frontend.md (client), backend = api-contracts-django_backend.md |
| Data models | Types/schémas côté client | Types dans src/types/api/, reflètent l’API backend |
| State management | Oui | state-management-frontend.md |
| UI components | Oui | component-inventory-frontend.md |
| Deployment config | Oui | deployment-configuration.md (partagé) |

---

## Django Backend (backend)

| Exigence | Fait | Livrable |
|----------|------|----------|
| API scan | Oui | api-contracts-django_backend.md |
| Data models | Oui | data-models-django_backend.md |
| State management | N/A (backend) | — |
| UI components | N/A (backend) | — |
| Deployment config | Oui | deployment-configuration.md (partagé) |

---

## Autres patterns couverts

- **Config :** .env, pyproject.toml, vite.config.ts, settings Django.
- **Auth / sécurité :** JWT, SAML, idp_auth, CORS, middleware.
- **Entry points :** main.tsx (frontend), ASGI/WSGI (backend).
- **Shared code :** src/utils/, src/services/, lib partagée entre composants.
- **Async / events :** Celery, Channels, WebSockets (backend) ; pas de workers côté frontend.
- **CI/CD :** .github/workflows (ci, django-tests, deploy).

---

*Généré par le workflow document-project (étape 4).*
