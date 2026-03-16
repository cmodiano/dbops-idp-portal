# Documentation IDP Portal

Portail développeur interne pour l'orchestration d'opérations de bases de données.

- **Stack** : React 19 + TypeScript (frontend), Django 5.2 + DRF (backend), Oracle 19c+, Redis, Celery
- **Architecture** : SPA React + API REST Django (`/api/v1`) + WebSocket temps réel

---

## Navigation

| Section | Point d'entrée | Description |
|---------|---------------|-------------|
| Architecture | [workflow-architecture.md](architecture/workflow-architecture.md) | Vue d'ensemble complète du système |
| Guide développeur | [developer-guide.md](architecture/developer-guide.md) | Référence technique pour les développeurs |
| API | [documentation.md](api/documentation.md) | Swagger UI, contrats, self-service |
| Backend | [README.md](backend/README.md) | Modules Django, services, tests |
| Frontend | [README.md](frontend/README.md) | Composants React, routing, state |
| Intégrations | [index.md](integrations/index.md) | AAP, ServiceNow, Terraform, GitHub, Azure |
| Opérations | [deployment.md](operations/deployment.md) | Déploiement, exploitation production |
| Sécurité | [architecture-global.md](security/architecture-global.md) | Architecture sécurité, compliance |
| Référence | [glossary.md](reference/glossary.md) | Glossaire, conventions, feature flags |

---

## Démarrer

1. Lire [Architecture des workflows](architecture/workflow-architecture.md) pour comprendre le système
2. Consulter le [Guide développeur](architecture/developer-guide.md) pour la référence technique
3. Suivre le [Guide de développement](reference/development-guide.md) pour le setup local
