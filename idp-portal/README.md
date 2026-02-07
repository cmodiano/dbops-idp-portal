# IDP Portal

Internal Developer Platform pour les operations base de donnees.

## Stack

- **Frontend** : React 19 + Vite + Ant Design 6 + TypeScript
- **Backend** : Django 5.1+ / Django REST Framework 3.15+ (officiel depuis février 2026)
- **Base de donnees** : Oracle 19c+ (dev local via Docker)

> **Note:** Migration FastAPI→Django terminée. Le code FastAPI est archivé dans la branche `legacy/fastapi-final` et le tag `v1.0.0-fastapi`. Voir [docs/MIGRATION_ARCHIVE.md](docs/MIGRATION_ARCHIVE.md) pour référence historique.

## Environnement de developpement

### Oracle (Docker)

Demarrer Oracle en local avec Docker Compose (port 1521) :

```bash
docker compose up -d oracle
```

Attendre 1 à 2 minutes que la base soit pret. Au premier demarrage, le script `database/init/01-create-idp-app-user.sql` cree l'utilisateur `idp_app` dans le PDB FREEPDB1 (image Oracle Free).

**Variables d'environnement** (a definir dans un fichier `.env` a la racine de `idp-portal/` ou en export) :

| Variable          | Description                    | Valeur typique (Oracle Docker)     |
|-------------------|--------------------------------|------------------------------------|
| `ORACLE_DSN`      | DSN Oracle (hote:port/service) | `localhost:1521/FREEPDB1`           |
| `ORACLE_USER`     | Utilisateur Oracle             | `idp_app`                          |
| `ORACLE_PASSWORD` | Mot de passe (utilisateur idp_app) | `changeme`                     |
| `ORACLE_PWD`      | Mot de passe sys (conteneur, optionnel) | `Oracle123!` (defaut)        |

Le fichier `.env` ne doit pas etre commit (deja dans `.gitignore`). Copier les cles ci-dessus dans un `.env` local ; les valeurs peuvent rester celles indiquees pour le dev.

### Migrations (Flyway)

Les migrations sont gerees par **Flyway** (Community). Format des fichiers : `V001__description_snake_case.sql` dans `database/migrations/`. Flyway utilise sa table native `flyway_schema_history`.

**Installation Flyway (optionnelle)**  
- **CLI** : [Download Flyway](https://flywaydb.org/download) et placer `flyway` dans le PATH, ou  
- **Sans install** : le script `run_migrations.sh` utilise l’image Docker `flyway/flyway` si la CLI n’est pas disponible.

**Variables** (identiques au backend Django) : `ORACLE_DSN`, `ORACLE_USER`, `ORACLE_PASSWORD`. Ex. `ORACLE_DSN=localhost:1521/FREEPDB1`.

**Appliquer les migrations** (depuis la racine `idp-portal/`) :

```bash
export ORACLE_DSN=localhost:1521/FREEPDB1
export ORACLE_USER=idp_app
export ORACLE_PASSWORD=changeme
./scripts/run_migrations.sh
```

Ou en une ligne :

```bash
ORACLE_DSN=localhost:1521/FREEPDB1 ORACLE_USER=idp_app ORACLE_PASSWORD=changeme ./scripts/run_migrations.sh
```

Le script appelle `flyway migrate` (CLI ou Docker). Configuration : `flyway.conf` (emplacement `database/migrations/`, validation activée).

**Installation vierge** : Les migrations sont conçues pour une base vide (ex. Oracle Docker). Pour une base déjà migrée avec l’ancien système (SCHEMA_VERSION, séquences), voir la doc [Flyway baseline](https://documentation.red-gate.com/flyway/configure/baseline) ou contacter l’équipe.

### Backend (Django)

Pour Oracle Docker, définir les variables d'environnement Oracle (voir section Oracle ci-dessus).

```bash
cd django_backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install uv
uv pip install -r requirements-dev.lock  # ou --system si dans Docker/CI

# Variables d'environnement (ou dans .env)
export ORACLE_HOST=localhost
export ORACLE_PORT=1521
export ORACLE_SERVICE_NAME=FREEPDB1
export ORACLE_USER=idp_app
export ORACLE_PASSWORD=changeme

# Démarrer le serveur de développement
python manage.py runserver
```

Le backend Django utilise le schéma Oracle existant. Pas de migration de données nécessaire.

**Configuration production :** Voir `django_backend/.env.production.template` et `django_backend/deployment/`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Tests avec Oracle Docker

Pour lancer les tests d'integration contre le container Oracle (depuis la racine `idp-portal/`) :

```bash
docker compose up -d oracle
# Attendre ~1-2 min
cd django_backend && ORACLE_DSN=localhost:1521/FREEPDB1 ORACLE_USER=idp_app ORACLE_PASSWORD=changeme python3 -m pytest tests/ -v
```

Sans Oracle configure (ORACLE_DSN non defini), les tests d'integration sont ignores (skip).

## Seed de données de test (développement)

Un script de seed insère des données de test pour valider le frontend. Il utilise les mêmes variables d'environnement que le backend Django (`ORACLE_DSN`, `ORACLE_USER`, `ORACLE_PASSWORD`). À lancer une seule fois sur base vide, ou avec `--reset` pour réinsérer.

**Depuis la racine idp-portal/** (variables Oracle dans l'environnement ou dans un `.env` à la racine) :

```bash
python scripts/seed_dev_data.py --env=dev
```

**Depuis le backend Django** (avec venv et variables Oracle déjà chargées) :

```bash
cd django_backend
source .venv/bin/activate
python ../scripts/seed_dev_data.py --env=dev
```

**Options :**
- `--env=dev` : Obligatoire (ou `APP_ENV=development` en variable d'environnement)
- `--reset` : Supprime les données existantes avant insertion (idempotent). Sans `--reset`, le script refuse de s'exécuter si des données seed existent déjà.

**Données insérées :**

| Entité | Quantité | Description |
|--------|----------|-------------|
| Users | 3 | dbops1, dba1, user1 avec profils associés |
| Profiles | 3 | DBOPS (admin), DBA, BUSINESS avec permissions |
| Tags | 8 | oracle, patching, backup, dev, prod, urgente, provisioning, monitoring |
| Integrations | 2 | AAP Demo, ServiceNow Demo |
| Actions | 8 | Variées (backup, patching, provisioning), draft/published |
| Favorites | 5 | Favoris utilisateurs |
| Executions | 15 | Tous statuts (COMPLETED, FAILED, RUNNING, SUBMITTED, CANCELLED, PENDING_APPROVAL) |
| Execution Steps | 20 | Timeline détaillée pour 5 exécutions |

**Écrans à tester après seed :**
- **Catalogue** : liste avec actions, filtres par tags, favoris, fiche détail
- **Admin** : onglets Actions (draft/published), Profils, Intégrations
- **Exécutions** : liste avec tous les statuts, détail avec timeline/logs/erreur
- **Dashboard** : stats et activité récente avec données

### Test du mode Business (Story 7.1)

Le profil BUSINESS dans le seed data utilise une interface simplifiée :
- **Descriptions sanitizées** : termes techniques (pipeline, playbook, webhook, etc.) remplacés par des équivalents accessibles
- **Onglet Admin masqué** : seuls les onglets Catalogue, Exécutions et Dashboard sont visibles
- **Fiche action simplifiée** : métadonnées techniques masquées, indicateur d'impact avec callout visuel

Pour tester en mode business, utiliser l'utilisateur `user1` (profil BUSINESS) avec le système d'authentification, ou modifier temporairement le mock user dans `frontend/src/contexts/AuthContext.tsx` :

```typescript
const DEV_MOCK_USER: User = {
  id: 1,
  username: 'fatima.business',
  display_name: 'Fatima Business',
  profile: 'business',  // ou 'client_business'
  navigation_tabs: ['catalog', 'executions', 'dashboard'],
  is_auditor: false,
};
```

Le flag `is_business_profile` est retourné par l'API `/auth/me` et conditionne l'affichage simplifié.

**Important :** Ce script est réservé à la base de développement. Il refuse de s'exécuter si `APP_ENV` n'est pas `development` ou si `--env=dev` n'est pas spécifié. En cas d'échec du script après un `--reset`, la base reste vide (rollback automatique).

## Build Docker Images

### Build individuel

```bash
# Backend Django (Gunicorn)
docker build -t idp-backend:latest ./django_backend

# Frontend React/Vite (Nginx)
docker build -t idp-frontend:latest ./frontend
```

### Docker Compose (orchestration complète)

Démarrer tous les services (Oracle + Backend + Frontend) :

```bash
docker compose up -d
```

Démarrer uniquement la base de données :

```bash
docker compose up -d oracle-db
```

Builder et démarrer backend + frontend :

```bash
docker compose up -d --build backend frontend
```

### Ports exposés

| Service | Port local | Description |
|---------|-----------|-------------|
| Oracle DB | 1521 | SQL*Net |
| Backend | 8000 | API Django (Gunicorn) |
| Frontend | 8080 | SPA React (Nginx) |

### Variables d'environnement (production)

Le backend nécessite des variables d'environnement pour les secrets et la configuration.
Voir `django_backend/.env.production.template` pour la liste complète.

En développement avec Docker Compose, les variables sont pré-configurées dans `docker-compose.yml`.

### Notes production vs développement

- **Développement** : `docker compose up -d` utilise les valeurs par défaut (Oracle local, AUTH_DEV_BYPASS=true)
- **Production** : Construire les images et les déployer avec des variables d'environnement sécurisées (Vault, secrets CI/CD). Ne jamais utiliser `AUTH_DEV_BYPASS=true` en production.
- Les images Docker ne contiennent pas de fichiers `.env` — les secrets sont injectés via variables d'environnement runtime.

## Structure

- `frontend/` : Application React
- `django_backend/` : API Django REST Framework
- `database/` : Migrations SQL Flyway (`migrations/`), script d'init utilisateur (`init/`)
- `scripts/` : Scripts utilitaires (`run_migrations.sh`, `seed_dev_data.py`, `post-switchover-validation.sh`)
- `docs/` : Documentation technique (migration, déploiement, architecture)
- `docker-compose.yml` : Services Docker (Oracle, Backend, Frontend)

### Documentation

- [Plan de bascule FastAPI → Django](docs/migration-switchover-plan.md)
- [Récapitulatif migration](docs/fastapi-to-django-migration.md)
- [Parité schéma base de données](docs/schema-differences.md)
- [Templates de communication](docs/communication-templates.md)

## API Integrations — champ config

Lors de la création ou mise à jour d'une intégration (POST/PUT `/admin/integrations`), le champ optionnel `config` décrit le flow d'authentification par étapes. Il est validé côté backend contre un **JSON Schema** (draft-07).

- **Schéma** : `django_backend/catalog/schemas/integration_config_schema.json`
- **Règles** : `auth_flow` est un tableau d'étapes ; chaque étape a `step` ∈ `obtain_token` | `call_api`, optionnellement `url_ref` ∈ `base_url` | `token_url`, et `credentials` (référence `credential_ref` de l'intégration, pas de chemin Vault arbitraire). En cas de config invalide, l'API retourne **400** avec `code: "INVALID_CONFIG"` et détails (champ, message).

Exemple de config valide :

```json
{
  "auth_flow": [
    {
      "step": "obtain_token",
      "url_ref": "token_url",
      "credentials": { "ref": "credential_ref", "keys": ["username", "password"] },
      "response_token_path": "access_token"
    },
    {
      "step": "call_api",
      "url_ref": "base_url",
      "credentials": { "use_token_from_step": 0 }
    }
  ]
}
```
