# Tests Django Backend

## Prérequis

Pour exécuter les tests, vous devez avoir installé les dépendances Python dans un environnement virtuel.

### Installation

1. Créer un environnement virtuel (si pas déjà fait):
```bash
python -m venv venv
```

2. Activer l'environnement virtuel:
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. Installer les dépendances:
```bash
pip install -r requirements.txt
```

### Configuration de la base de données de test

Les tests utilisent pytest-django qui configure automatiquement une base de données de test SQLite en mémoire par défaut.

Pour utiliser Oracle comme base de test, configurez les variables d'environnement:
```bash
export ORACLE_DSN="your_oracle_dsn"
export ORACLE_USER="your_user"
export ORACLE_PASSWORD="your_password"
```

### Exécution des tests

Exécuter tous les tests:
```bash
pytest
```

Exécuter avec couverture de code:
```bash
pytest --cov=catalog --cov=profiles --cov=integrations --cov=executions --cov=idp_auth --cov=core --cov-report=html
```

Exécuter les tests d'une app spécifique:
```bash
pytest catalog/tests/
```

Exécuter un fichier de test spécifique:
```bash
pytest catalog/tests/test_managers.py
```

### Structure des tests

Les tests sont organisés par app Django:
- `catalog/tests/` - Tests pour ActionManager et CatalogService
- `profiles/tests/` - Tests pour ProfileManager et ProfileService
- `executions/tests/` - Tests pour ExecutionManager et ExecutionService
- `integrations/tests/` - Tests pour IntegrationManager et IntegrationService
- `idp_auth/tests/` - Tests pour UserManager et AuthService
- `core/tests/` - Tests pour AuditLogManager et AuditService

Chaque app contient:
- `test_managers.py` - Tests unitaires pour les Managers Django
- `test_services.py` - Tests unitaires pour les Services métier

### Couverture de code

La couverture minimale requise est de 80% pour chaque module (AC#2 de Story M.3).

Pour générer un rapport HTML de couverture:
```bash
pytest --cov=. --cov-report=html
```

Le rapport sera généré dans `htmlcov/index.html`.
