# Index de la documentation – test (idp-portal)

**Date :** 2026-02-26

---

## Vue d’ensemble du projet

- **Type :** multi-part (2 parties : Frontend + Django Backend)  
- **Langage principal :** TypeScript (frontend), Python 3.12 (backend)  
- **Architecture :** SPA React + API REST Django ; intégration via HTTP JSON (`/api/v1`)

---

## Référence rapide

### Frontend (idp-portal/frontend)

- **Stack :** React 19, Vite 7, TypeScript, Ant Design 6, React Router 7  
- **Point d’entrée :** `src/main.tsx`, `src/App.tsx`  
- **Pattern :** Composants + Context API + hooks ; client API central dans `src/services/api_client.ts`

### Django Backend (idp-portal/django_backend)

- **Stack :** Django 5.1, DRF, Oracle, Redis, Celery, Channels  
- **Point d’entrée :** `idp_backend/urls.py`, `manage.py`, ASGI/Celery  
- **Pattern :** API REST par domaine (apps), services métier, OpenAPI (`/api/schema/`)

---

## Documentation générée (workflow document-project)

| Document | Description |
|----------|-------------|
| [Vue d’ensemble du projet](./project-overview.md) | Résumé, classification, liens vers les docs |
| [Architecture – Frontend](./architecture-frontend.md) | Architecture SPA, stack, composants, dev, déploiement, tests |
| [Architecture – Django Backend](./architecture-django_backend.md) | Architecture API, stack, modèles, endpoints, dev, déploiement, tests |
| [Analyse de l’arbre des sources](./source-tree-analysis.md) | Arbre des répertoires, dossiers critiques, points d’intégration |
| [Contrats API – Backend](./api-contracts-django_backend.md) | Liste des endpoints REST (`/api/v1/*`) |
| [Contrats API – Frontend](./api-contracts-frontend.md) | Client API, services, auth, retries |
| [Modèles de données – Backend](./data-models-django_backend.md) | Modèles Django par app |
| [Inventaire composants – Frontend](./component-inventory-frontend.md) | Composants UI par zone |
| [Gestion d’état – Frontend](./state-management-frontend.md) | Contextes et hooks |
| [Architecture d’intégration](./integration-architecture.md) | Frontend ↔ Backend, flux, erreurs |
| [Stack technique](./technology-stack.md) | Tableaux techno frontend + backend |
| [Patterns d’architecture](./architecture-patterns.md) | SPA vs API centrée services |
| [Guide de développement](./development-guide.md) | Prérequis, installation, commandes (frontend + backend) |
| [Configuration déploiement](./deployment-configuration.md) | Docker, CI/CD, Nginx |
| [Guide de contribution](./contribution-guide.md) | Résumé + lien vers CONTRIBUTING.md |
| [Structure du projet](./project-structure.md) | Métadonnées parties (project_parts) |
| [Inventaire doc existante](./existing-documentation-inventory.md) | Doc déjà présente dans le dépôt |
| [Analyse conditionnelle](./comprehensive-analysis.md) | Synthèse par exigence (web/backend) |

**Métadonnées :** [project-parts.json](./project-parts.json) (parts + integration_points)

---

## Documentation existante (dans le dépôt)

Voir **[Inventaire de la documentation existante](./existing-documentation-inventory.md)** pour la liste détaillée (README, ADR, sécurité, API, backend, frontend, ops). Exemples : idp-portal/README.md, idp-portal/django_backend/docs/, idp-portal/docs/, CONTRIBUTING.md.

---

## Démarrer

1. **Lire** [Vue d’ensemble du projet](./project-overview.md) et [Architecture d’intégration](./integration-architecture.md).  
2. **Développement :** [Guide de développement](./development-guide.md) (frontend : `npm run dev` ; backend : venv + `python manage.py runserver`).  
3. **Contribution :** [Guide de contribution](./contribution-guide.md) et [CONTRIBUTING.md](../CONTRIBUTING.md) à la racine.

---

*Point d’entrée principal pour le développement assisté par IA. Généré par le workflow document-project (étape 10).*
