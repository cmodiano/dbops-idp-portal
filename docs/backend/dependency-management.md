# Gestion des Dépendances - Django Backend

> **Story 17.8** — Migration vers `pyproject.toml` + lockfiles pour builds reproductibles

## Vue d'ensemble

Le backend Django utilise `pyproject.toml` comme source de vérité pour les dépendances et `uv` pour la résolution déterministe via lockfiles.

| Fichier | Rôle |
|---------|------|
| `pyproject.toml` | Source de vérité — métadonnées, dépendances avec contraintes |
| `requirements.lock` | Lockfile runtime (production) — versions exactes |
| `requirements-dev.lock` | Lockfile dev (runtime + outils dev) — versions exactes |

## Installation des dépendances

### Production (runtime uniquement)

```bash
uv pip install -r requirements.lock
```

### Développement (runtime + outils dev)

```bash
uv pip install -r requirements-dev.lock
```

### Installation de uv

```bash
# Via pip (cross-platform)
pip install uv

# Ou via standalone installer (recommandé)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Ajouter une nouvelle dépendance

1. Éditer `pyproject.toml` — ajouter la dépendance dans `[project.dependencies]` ou `[project.optional-dependencies.dev]`
2. Régénérer les lockfiles :
   ```bash
   uv pip compile pyproject.toml -o requirements.lock --python-version 3.12
   uv pip compile pyproject.toml --extra dev -o requirements-dev.lock --python-version 3.12
   ```
3. Installer la nouvelle dépendance localement :
   ```bash
   uv pip install -r requirements-dev.lock
   ```
4. Commiter `pyproject.toml`, `requirements.lock`, `requirements-dev.lock`

## Mettre à jour toutes les dépendances

```bash
uv pip compile --upgrade pyproject.toml -o requirements.lock --python-version 3.12
uv pip compile --upgrade pyproject.toml --extra dev -o requirements-dev.lock --python-version 3.12
```

## Mettre à jour une dépendance spécifique

```bash
uv pip compile --upgrade-package Django pyproject.toml -o requirements.lock --python-version 3.12
uv pip compile --upgrade-package Django pyproject.toml --extra dev -o requirements-dev.lock --python-version 3.12
```

## Vérifier les vulnérabilités de sécurité

```bash
# Avec pip-audit (inclus dans requirements-dev.lock)
pip-audit -r requirements.lock

# Scanner aussi les dépendances de dev
pip-audit -r requirements-dev.lock
```

## Rollback / Downgrade d'une dépendance

Si une mise à jour de dépendance cause des problèmes :

**1. Revenir à une version précédente des lockfiles :**
```bash
git checkout HEAD~1 -- requirements.lock requirements-dev.lock
uv pip install -r requirements-dev.lock
```

**2. Downgrader une dépendance spécifique :**
```bash
# Éditer pyproject.toml et fixer la version problématique
# Ex: "Django>=5.1.0,<5.2.10" au lieu de "Django>=5.1.0,<6.0"

# Régénérer les lockfiles
uv pip compile pyproject.toml -o requirements.lock --python-version 3.12
uv pip compile pyproject.toml --extra dev -o requirements-dev.lock --python-version 3.12

# Réinstaller
uv pip install -r requirements-dev.lock
```

**3. Tester et valider :**
```bash
pytest tests/ -v
python manage.py check
```

## Différence runtime vs dev

- **`[project.dependencies]`** : Dépendances installées en production (Django, DRF, oracledb, etc.)
- **`[project.optional-dependencies.dev]`** : Outils de développement uniquement (pytest, ruff, mypy, bandit, etc.)
- En production, installer uniquement `requirements.lock` pour éviter d'embarquer des outils de test
