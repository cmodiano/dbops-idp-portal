# Guide de développement – idp-portal

**Date :** 2026-02-26

---

## Prérequis globaux

- **Node.js** (LTS) – frontend
- **Python 3.12+** – backend
- **uv** (optionnel) – gestion des paquets Python
- **Oracle 19c+** – base de données (dev local possible via Docker, voir idp-portal/README.md)
- **Redis** – cache et Celery (backend)

---

## Frontend (idp-portal/frontend)

### Installation

```bash
cd idp-portal/frontend
npm install
```

### Commandes

| Commande | Rôle |
|----------|------|
| `npm run dev` | Serveur de dev Vite (HMR) |
| `npm run build` | Build production (`tsc -b && vite build`) |
| `npm run preview` | Prévisualisation du build |
| `npm run test` | Tests Vitest (run) |
| `npm run test:watch` | Tests en mode watch |
| `npm run test:coverage` | Couverture |
| `npm run lint` | ESLint |

### Variables d'environnement

Fichiers `.env`, `.env.docker`, `.env.staging` (ne pas commiter les secrets). Le frontend appelle l’API via une URL relative (`/api/v1`) ; en dev, un proxy (Vite ou Nginx) pointe vers le backend.

---

## Backend (idp-portal/django_backend)

### Installation

```bash
cd idp-portal/django_backend
python3.12 -m venv .venv
source .venv/bin/activate   # Linux/macOS
uv pip install -r requirements-dev.lock --system
# ou: pip install -r requirements-dev.lock
```

### Lancer le serveur

```bash
python manage.py runserver
```

### Tests

```bash
pytest
pytest --cov=. --cov-report=html
pytest path/to/test_file.py -v
```

### Lint et types

```bash
ruff check .
ruff check . --fix
mypy .
```

### Pre-commit (mypy + detect-secrets)

Pre-commit is configured at **repository root** (`.pre-commit-config.yaml`). It runs **mypy** on `idp-portal/django_backend` (blocking on error) and **detect-secrets** on `idp-portal/`.

**1. Install pre-commit** (required once; use a venv or your usual Python):

```bash
pip install pre-commit
# or with uv:  uv tool install pre-commit  (then use `pre-commit` from PATH)
```

**2. Install hooks and run** (from repository root):

```bash
# From repository root (parent of idp-portal/)
pre-commit install
pre-commit run --all-files
```

Mypy requires backend dev deps to be installed (e.g. `cd idp-portal/django_backend && uv pip install -r requirements-dev.lock`).

### Variables d'environnement

Fichier `.env` à la racine de `idp-portal/` ou dans `django_backend/` : `ORACLE_DSN`, `ORACLE_USER`, `ORACLE_PASSWORD`, Redis, secrets SAML/JWT, etc. Voir `.env.example` / `.env.production.template`.

---

## Base de données (Oracle)

- Démarrer Oracle en local : `docker compose up -d oracle` (depuis `idp-portal/`).
- Migrations SQL : Flyway, fichiers `database/migrations/V0xx__*.sql`.
- Migrations Django : `python manage.py migrate` (apps Django).

---

## Contribution

Voir **CONTRIBUTING.md** à la racine du dépôt :

- Onboarding : `idp-portal/django_backend/docs/onboarding/README.md`
- ADRs : `idp-portal/django_backend/docs/decisions/README.md`
- Checklist endpoints : `idp-portal/django_backend/docs/standards/endpoint-checklist.md`
- Sécurité : `idp-portal/django_backend/docs/security/` (common-pitfalls, pre-pr-checklist)
- Tests : viser ≥80% de couverture, pytest-django + factory_boy

---

*Généré par le workflow document-project (étape 6).*
