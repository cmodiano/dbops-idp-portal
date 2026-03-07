# Configuration déploiement – idp-portal

**Date :** 2026-02-26

---

## Conteneurs

| Composant | Fichier | Rôle |
|-----------|---------|------|
| Frontend | `idp-portal/frontend/Dockerfile` | Build et service frontend (Nginx ou serveur statique) |
| Backend | `idp-portal/django_backend/Dockerfile` | Django + Gunicorn/Daphne |

---

## CI/CD

| Fichier | Rôle |
|---------|------|
| `.github/workflows/ci.yml` | Pipeline CI (build, tests) |
| `.github/workflows/django-tests.yml` | Tests Django |
| `.github/workflows/deploy.yml` | Déploiement |

---

## Serveur / reverse proxy

- `idp-portal/frontend/nginx.conf` – Config Nginx pour le frontend.
- `idp-portal/nginx/idp-portal.service` – Unité systemd (si applicable).

---

## Scripts et config

- `idp-portal/scripts/deploy.sh` – Script de déploiement.
- Variables d’environnement : `.env.example`, `.env.production.template` (backend).

---

*Généré par le workflow document-project (étape 4).*
