# IDP Portal

Internal Developer Platform pour les operations base de donnees.

## Stack

- **Frontend** : React 19 + Vite + Ant Design 6 + TypeScript
- **Backend** : FastAPI + python-oracledb (mode Thin) + Pydantic v2
- **Base de donnees** : Oracle (dev local via Docker)

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

**Variables** (identiques au backend) : `ORACLE_DSN`, `ORACLE_USER`, `ORACLE_PASSWORD`. Ex. `ORACLE_DSN=localhost:1521/FREEPDB1`.

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

### Backend

Pour Oracle Docker, definir au minimum `ORACLE_DSN=localhost:1521/FREEPDB1` (voir section Oracle ci-dessus). Copier les cles depuis `.env.example` dans un fichier `.env` a la racine de `idp-portal/`.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
# Optionnel : charger .env (ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD) si pas deja exporte
fastapi dev app/main.py
```

Le backend lit `oracle_dsn`, `oracle_user`, `oracle_password` (variables d'environnement sans prefix : `ORACLE_DSN`, `ORACLE_USER`, `ORACLE_PASSWORD`). Valeurs par defaut dans `backend/app/core/config.py` : `localhost:1521/FREEPDB1`, `idp_app`, `changeme`. Pour Oracle Docker (image Free), utiliser le service `FREEPDB1` : `localhost:1521/FREEPDB1`.

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
cd backend && ORACLE_DSN=localhost:1521/FREEPDB1 ORACLE_USER=idp_app ORACLE_PASSWORD=changeme python3 -m pytest tests/unit tests/integration -v
```

Sans Oracle configure (ORACLE_DSN non defini), les tests d'integration sont ignores (skip).

## Seed de données de test (développement)

Un script de seed insère des données de test pour valider le frontend. Il utilise les mêmes variables d'environnement que le backend (`ORACLE_DSN`, `ORACLE_USER`, `ORACLE_PASSWORD` — voir `backend/app/core/config.py`). À lancer une seule fois sur base vide, ou avec `--reset` pour réinsérer.

**Depuis la racine idp-portal/** (variables Oracle dans l'environnement ou dans un `.env` à la racine) :

```bash
python scripts/seed_dev_data.py --env=dev
```

**Depuis le backend** (avec venv et variables Oracle déjà chargées) :

```bash
cd backend
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

**Important :** Ce script est réservé à la base de développement. Il refuse de s'exécuter si `APP_ENV` n'est pas `development` ou si `--env=dev` n'est pas spécifié. En cas d'échec du script après un `--reset`, la base reste vide (rollback automatique).

## Structure

- `frontend/` : Application React
- `backend/` : API FastAPI
- `database/` : Migrations SQL (`migrations/`), script d'init utilisateur (`init/`)
- `scripts/` : Scripts utilitaires (`run_migrations.sh`, `seed_dev_data.py`, etc.)
- `docker-compose.yml` : Service Oracle pour le dev local

## API Integrations — champ config

Lors de la création ou mise à jour d'une intégration (POST/PUT `/admin/integrations`), le champ optionnel `config` décrit le flow d'authentification par étapes. Il est validé côté backend contre un **JSON Schema** (draft-07).

- **Schéma** : `backend/app/schemas/integration_config_schema.json`
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
