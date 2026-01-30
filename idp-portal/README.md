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

Attendre 1 à 2 minutes que la base soit pret. Au premier demarrage, le script `database/init/01-create-idp-app-user.sql` cree l'utilisateur `idp_app` dans le PDB XEPDB1.

**Variables d'environnement** (a definir dans un fichier `.env` a la racine de `idp-portal/` ou en export) :

| Variable          | Description                    | Valeur typique (Oracle Docker)     |
|-------------------|--------------------------------|------------------------------------|
| `ORACLE_DSN`      | DSN Oracle (hote:port/service) | `localhost:1521/XEPDB1`             |
| `ORACLE_USER`     | Utilisateur Oracle             | `idp_app`                          |
| `ORACLE_PASSWORD` | Mot de passe                   | `changeme`                         |

Le fichier `.env` ne doit pas etre commit (deja dans `.gitignore`). Copier les cles ci-dessus dans un `.env` local ; les valeurs peuvent rester celles indiquees pour le dev.

### Migrations (Flyway)

Les migrations sont gerees par **Flyway** (Community). Format des fichiers : `V001__description_snake_case.sql` dans `database/migrations/`. Flyway utilise sa table native `flyway_schema_history`.

**Installation Flyway (optionnelle)**  
- **CLI** : [Download Flyway](https://flywaydb.org/download) et placer `flyway` dans le PATH, ou  
- **Sans install** : le script `run_migrations.sh` utilise l’image Docker `flyway/flyway` si la CLI n’est pas disponible.

**Variables** (identiques au backend) : `ORACLE_DSN`, `ORACLE_USER`, `ORACLE_PASSWORD`. Ex. `ORACLE_DSN=localhost:1521/XEPDB1`.

**Appliquer les migrations** (depuis la racine `idp-portal/`) :

```bash
export ORACLE_DSN=localhost:1521/XEPDB1
export ORACLE_USER=idp_app
export ORACLE_PASSWORD=changeme
./scripts/run_migrations.sh
```

Ou en une ligne :

```bash
ORACLE_DSN=localhost:1521/XEPDB1 ORACLE_USER=idp_app ORACLE_PASSWORD=changeme ./scripts/run_migrations.sh
```

Le script appelle `flyway migrate` (CLI ou Docker). Configuration : `flyway.conf` (emplacement `database/migrations/`, validation activée).

**Installation vierge** : Les migrations sont conçues pour une base vide (ex. Oracle Docker). Pour une base déjà migrée avec l’ancien système (SCHEMA_VERSION, séquences), voir la doc [Flyway baseline](https://documentation.red-gate.com/flyway/configure/baseline) ou contacter l’équipe.

### Backend

Pour Oracle Docker, definir au minimum `ORACLE_DSN=localhost:1521/XEPDB1` (voir section Oracle ci-dessus). Copier les cles depuis `.env.example` dans un fichier `.env` a la racine de `idp-portal/`.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
# Optionnel : charger .env (ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD) si pas deja exporte
fastapi dev app/main.py
```

Le backend lit `oracle_dsn`, `oracle_user`, `oracle_password` (variables d'environnement sans prefix : `ORACLE_DSN`, `ORACLE_USER`, `ORACLE_PASSWORD`). Valeurs par defaut dans `backend/app/core/config.py` : `localhost:1521/FREEPDB1`, `idp_app`, `changeme`. Pour Oracle Docker (gvenzl/oracle-xe), utiliser le service `XEPDB1` : `localhost:1521/XEPDB1`.

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
cd backend && ORACLE_DSN=localhost:1521/XEPDB1 ORACLE_USER=idp_app ORACLE_PASSWORD=changeme python3 -m pytest tests/unit tests/integration -v
```

Sans Oracle configure (ORACLE_DSN non defini), les tests d'integration sont ignores (skip).

## Structure

- `frontend/` : Application React
- `backend/` : API FastAPI
- `database/` : Migrations SQL (`migrations/`), script d'init utilisateur (`init/`)
- `scripts/` : Scripts utilitaires (`run_migrations.sh`, etc.)
- `docker-compose.yml` : Service Oracle pour le dev local
