# test – Vue d’ensemble du projet

**Date :** 2026-02-26  
**Type :** multi-part (Frontend + Backend)  
**Architecture :** SPA React + API REST Django

---

## Résumé

**idp-portal** (Internal Developer Platform) : portail pour les opérations base de données. Deux parties dans le dépôt : **frontend** (React 19, Vite 7, Ant Design, TypeScript) et **django_backend** (Django 5.1, DRF, Oracle, Celery, Channels). Le frontend consomme l’API REST du backend ; authentification SAML/JWT.

---

## Classification

- **Type de dépôt :** multi-part  
- **Types de projet :** web (frontend), backend (django_backend)  
- **Langages :** TypeScript, Python 3.12  
- **Pattern :** SPA composants + API REST centrée services  

---

## Parties

| Partie | Racine | Rôle |
|--------|--------|------|
| Frontend | idp-portal/frontend | SPA : catalogue d’actions, exécutions, dashboard, admin, calendrier, audit |
| Django Backend | idp-portal/django_backend | API REST : catalogue, exécutions, profils, intégrations, inventory, reference, auth, help |

---

## Stack (résumé)

- **Frontend :** React 19, Vite 7, TypeScript, Ant Design 6, React Router 7, XYFlow, FullCalendar, Recharts.  
- **Backend :** Django 5.1, DRF, Oracle (oracledb), Redis, Celery, Channels, JWT/SAML, drf-spectacular.

---

## Documentation générée

- [Architecture Frontend](../architecture/frontend.md)  
- [Architecture Backend](../architecture/backend.md)  
- [Analyse de l’arbre des sources](./source-tree-analysis.md)  
- [Contrats API (Backend)](../api/contracts-backend.md) | [Frontend (client)](../api/contracts-frontend.md)  
- [Modèles de données (Backend)](../backend/data-models.md)  
- [Inventaire composants (Frontend)](../frontend/component-inventory.md)  
- [Gestion d’état (Frontend)](../frontend/state-management.md)  
- [Architecture d’intégration](../architecture/integration.md)  
- [Guide de développement](../reference/development-guide.md)  
- [Configuration déploiement](../operations/deployment.md)  
- [Guide de contribution](../reference/contribution-guide.md)  

---

*Généré par le workflow document-project (étape 9).*
