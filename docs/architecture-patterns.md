# Patterns d’architecture – test (idp-portal)

**Date :** 2026-02-21

---

## Frontend (idp-portal/frontend)

- **Type projet :** web  
- **Style d’architecture :** SPA (Single Page Application) à base de **composants** (React), avec **routage client** (React Router) et **état local / hooks**.  
- **Points clés :**
  - Hiérarchie de composants (layout, pages, composants métier, partagés).
  - Client API dédié (services/*) appelant le backend Django REST.
  - Design system via Ant Design (thème, accessibilité).
  - Build et dev via Vite (ESM, HMR).
- **Justification :** Alignement avec le type « web » du documentation-requirements : frontend riche, composants, intégration API.

---

## Django Backend (idp-portal/django_backend)

- **Type projet :** backend  
- **Style d’architecture :** **API REST centrée services** : couche HTTP (DRF), services métier, modèles Django/ORM, intégrations externes (Ansible, ServiceNow, Jira, etc.).  
- **Points clés :**
  - Apps Django par domaine (catalog, executions, integrations, profiles, reference, etc.).
  - REST via ViewSets / serializers (DRF), documentation OpenAPI (drf-spectacular).
  - Tâches asynchrones (Celery + Redis), WebSockets (Channels/Daphne).
  - Auth : JWT, SAML/SSO.
  - Base Oracle (oracledb), résilience et runbooks documentés.
- **Justification :** Alignement avec le type « backend » : API, modèles de données, déploiement, patterns service/API.

---

## Vue multi-part (frontend + backend)

- **Intégration :** Le frontend consomme l’API REST du backend (appels HTTP depuis `api_client` / services).  
- **Contrat :** Types TypeScript côté frontend alignés avec les réponses/sérializers backend ; documentation API (OpenAPI) partagée.

---

*Généré par le workflow document-project (étape 3).*
