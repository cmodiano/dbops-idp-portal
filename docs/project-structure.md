# Structure du projet – test

**Date :** 2026-02-21  
**Type de dépôt :** multi-part (2 parties)

---

## Résumé de la structure

Le dépôt contient **deux parties** sous `idp-portal/` :

- **Frontend** : application React/Vite (TypeScript) – type **web**
- **Django Backend** : API REST Django (Python) – type **backend**

Chaque partie est documentée séparément selon les exigences de son type (web / backend).

---

## Métadonnées des parties (project_parts)

| part_id       | Chemin racine           | project_type_id | Nom affiché   |
|---------------|-------------------------|-----------------|---------------|
| frontend      | idp-portal/frontend     | web             | Frontend      |
| django_backend| idp-portal/django_backend | backend       | Django Backend |

- **frontend** : SPA React 19 + Vite 7, Ant Design, React Router ; consomme l’API du backend.
- **django_backend** : Django 5.1, Django REST Framework, Python 3.12 ; API REST, modèles, exécutions, catalogue, intégrations.

---

*Généré par le workflow document-project (étape 1).*
