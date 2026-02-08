# Internal Developer Portal - Django Backend

API REST Django pour le portail interne des développeurs.

## Prérequis

- Python 3.12+
- uv (gestionnaire de paquets Python)

## Installation

```bash
# Créer un environnement virtuel
python3.12 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Installer les dépendances
uv pip install -r requirements-dev.lock --system
```

## Développement

### Lancer le serveur

```bash
python manage.py runserver
```

### Tests

```bash
# Tous les tests
pytest

# Tests avec couverture
pytest --cov=. --cov-report=html

# Tests spécifiques
pytest tests/test_auth.py -v
```

### Linting

```bash
# Vérifier le code avec ruff
ruff check .

# Auto-fix
ruff check . --fix
```

### Type Checking (Story 17.9)

**Mypy est configuré en mode bloquant progressif** : les nouvelles erreurs de type bloquent le CI, les 89 erreurs existantes sont tolérées via un baseline.

```bash
# Vérifier les types localement
mypy .

# Vérifier par rapport au baseline (comme en CI)
scripts/check_mypy_baseline.sh

# Mettre à jour le baseline après corrections
scripts/generate_mypy_baseline.sh
git add .mypy-baseline-count
git commit -m 'chore: update mypy baseline'
```

**Documentation mypy :**
- [Guide développeur mypy](docs/mypy-developer-guide.md) - Comment ajouter des annotations de type
- [Workflow baseline](docs/mypy-baseline-workflow.md) - Comment fonctionne le baseline
- [Roadmap amélioration](docs/mypy-improvement-roadmap.md) - Plan de réduction du baseline

### Pre-commit Hooks

```bash
# Installer les hooks (recommandé)
pip install pre-commit
pre-commit install

# Exécuter manuellement
pre-commit run --all-files
```

## Structure du projet

```
django_backend/
├── core/                 # Fonctionnalités communes (auth, logging, RBAC)
├── catalog/              # Gestion du catalogue d'actions
├── executions/           # Exécution d'actions
├── integrations/         # Intégrations externes
├── profiles/             # Profils utilisateurs
├── idp_auth/             # Authentification (JWT, SAML)
├── utils/                # Utilitaires (JSON helpers)
├── scripts/              # Scripts d'automatisation
├── docs/                 # Documentation
└── idp_backend/          # Configuration Django
```

## Worker Celery (Story 20.3)

Le retry asynchrone des workflows utilise Celery avec Redis comme broker.

### Prérequis

- Redis server ≥ 7.x sur `localhost:6379` (ou URL configurée via `CELERY_BROKER_URL`)

### Développement

```bash
# Terminal 1 : Backend Django
python manage.py runserver

# Terminal 2 : Worker Celery
celery -A idp_backend worker -l info
```

Voir [docs/workflow-retry-celery.md](docs/workflow-retry-celery.md) pour la documentation complète (architecture, backoff, déploiement production).

## Mode Simulation (Story 19.0)

En environnement de développement, les exécutions peuvent être simulées sans intégrations réelles (AAP, ServiceNow, Vault).

```bash
# .env
SIMULATE_EXECUTION_DEV=true           # Active le mode simulation (default: même que DEBUG)
SIMULATE_EXECUTION_FAILURE_RATE=0.1   # 10% d'échecs aléatoires
SIMULATE_EXECUTION_STEP_DURATION=2    # 2 secondes par étape
```

Voir [docs/simulation-mode.md](docs/simulation-mode.md) pour la documentation complète.

## CI/CD

Le pipeline GitHub Actions exécute :
- **lint-backend** : Ruff
- **typecheck-backend** : Mypy (bloquant avec baseline)
- **test-backend** : Pytest
- **security-*** : Scans de sécurité (Bandit, pip-audit, detect-secrets)

## Sécurité

Voir [docs/security-remediation-plan.md](docs/security-remediation-plan.md) pour le plan de remédiation des vulnérabilités.

## Licence

Propriétaire - DB Automation Team
