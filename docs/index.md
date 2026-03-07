# Documentation IDP Portal

**Date :** 2026-03-07

---

## Vue d'ensemble du projet

- **Type :** multi-part (2 parties : Frontend + Django Backend)
- **Langage principal :** TypeScript (frontend), Python 3.12 (backend)
- **Architecture :** SPA React + API REST Django ; intégration via HTTP JSON (`/api/v1`)

---

## Navigation rapide

### Par thème

| Section | Description |
|--------|-------------|
| [Vue d'ensemble](overview/project-overview.md) | Résumé, classification, stack technique |
| [Architecture](architecture/frontend.md) | Frontend, Backend, intégration, patterns |
| [API](api/documentation.md) | Contrats, référence, self-service |
| [Backend](backend/README.md) | Django, ADR, runbooks, standards |
| [Frontend](frontend/README.md) | React, composants, design system |
| [Opérations](operations/deployment.md) | Déploiement, exploitation |
| [Sécurité](security/architecture-global.md) | Architecture, audit, compliance |
| [Intégrations](integrations/index.md) | AAP, ServiceNow, Terraform, etc. |
| [Référence](reference/development-guide.md) | Guides, conventions, contribution |

---

## Démarrer

1. **Lire** [Vue d'ensemble du projet](overview/project-overview.md) et [Architecture d'intégration](architecture/integration.md).
2. **Développement :** [Guide de développement](reference/development-guide.md) (frontend : `npm run dev` ; backend : venv + `python manage.py runserver`).
3. **Contribution :** [Guide de contribution](reference/contribution-guide.md).

---

*Documentation consolidée – MkDocs Material. Point d'entrée pour le développement assisté par IA.*
