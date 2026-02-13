# Story 26.7: Créer EnvironmentNormalizer unique

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur,
je veux centraliser la normalisation d'environnements dans une classe unique,
afin d'avoir une source unique de vérité pour l'environnement canonique et simplifier la gestion des comparaisons case-insensitive.

## Context

**Source :** Epic 26, Section 4.5 du code-quality-assessment (6 février 2026)

**⚠️ IMPORTANT — CONTEXTE MODIFIÉ PAR EPIC 21:**

Cette story a été conçue initialement pour créer un `EnvironmentNormalizer` avec aliases (`certif` → `staging`, `stg` → `staging`). **Cependant, l'Epic 21 (Stories 21.1-21.6) a SUPPRIMÉ toute normalisation d'environnements** et utilise maintenant l'inventaire comme source unique de vérité avec valeurs brutes (lab, dev, qa, uat, certif, staging, prod).

**Situation actuelle (post-Epic 21) :**
- Normalisation via aliases **SUPPRIMÉE** (Stories 21.1, 21.2)
- Environnements utilisent valeurs **brutes** de l'inventaire
- Comparaisons **case-insensitive** uniquement (`.lower()`)
- Inventaire = seule source de vérité (Epic 21.1 AC1)

**Nouveau scope Story 26.7 :**
Au lieu de créer un normaliseur avec aliases (obsolète), la story crée maintenant un **helper case-insensitive** pour centraliser la logique de comparaison d'environnements qui est actuellement dupliquée dans 4+ endroits.

### Problème identifié

**Duplication logique case-insensitive (4+ occurrences) :**

1. **`executions/utils.py::_get_env_config_case_insensitive()`** (ligne 70-104)
   - Comparaison `(key or '').strip().lower() == env_lower`
   - Utilisée pour résoudre config d'environnement dans actions

2. **`executions/utils.py::_validate_environment_against_inventory()`** (ligne 106-149)
   - Comparaison `environment.lower() not in valid_envs_lower`
   - Validation environnement contre inventaire

3. **`profiles/validation.py::validate_profile_environments()`** (ligne 27-100)
   - Normalisation `normalized_envs = [env.lower() for env in environments]`
   - Comparaison `env not in valid_envs_lower`
   - Validation profils contre inventaire

4. **`inventory/services.py` (diverses méthodes)**
   - Comparaisons case-insensitive dans filtres RBAC
   - Logique répétée pour matching environnements

**Conséquences de la duplication :**
- Logique case-insensitive répartie sur 4+ fichiers
- Risque d'incohérence (trim, lower, null handling)
- Tests dupliqués pour la même logique
- Difficile à modifier (ex: ajouter support Unicode normalization)

---

## Acceptance Criteria

### AC1: Créer la classe EnvironmentHelper case-insensitive

**Given** la logique case-insensitive est dupliquée à 4+ endroits
**When** la classe `EnvironmentHelper` est créée
**Then** :

- Un fichier `core/environment.py` est créé
- Classe `EnvironmentHelper` avec méthodes statiques :
  ```python
  class EnvironmentHelper:
      """
      Helper for case-insensitive environment comparison and matching.
      Story 26.7 — Centralized environment logic post-Epic 21.

      Epic 21 removed normalization via aliases (certif→staging).
      Inventory is now the single source of truth with raw values.
      This helper provides case-insensitive comparison only.
      """

      @staticmethod
      def normalize(env: str | None) -> str:
          """
          Normalize environment string to lowercase for comparison.

          Args:
              env: Environment string (e.g., 'DEV', 'Staging', 'PROD')

          Returns:
              Lowercase, trimmed string. Empty string if None.

          Examples:
              >>> EnvironmentHelper.normalize('DEV')
              'dev'
              >>> EnvironmentHelper.normalize('  Staging  ')
              'staging'
              >>> EnvironmentHelper.normalize(None)
              ''
          """
          if not env:
              return ''
          return str(env).strip().lower()

      @staticmethod
      def matches(a: str | None, b: str | None) -> bool:
          """
          Check if two environment strings match (case-insensitive).

          Args:
              a: First environment string
              b: Second environment string

          Returns:
              True if normalized strings are equal, False otherwise.

          Examples:
              >>> EnvironmentHelper.matches('DEV', 'dev')
              True
              >>> EnvironmentHelper.matches('Staging', 'STAGING')
              True
              >>> EnvironmentHelper.matches('prod', 'staging')
              False
              >>> EnvironmentHelper.matches(None, '')
              True
          """
          return EnvironmentHelper.normalize(a) == EnvironmentHelper.normalize(b)

      @staticmethod
      def is_in(env: str | None, env_list: list[str]) -> bool:
          """
          Check if environment is in list (case-insensitive).

          Args:
              env: Environment string to check
              env_list: List of environment strings

          Returns:
              True if env (normalized) is in list (normalized), False otherwise.

          Examples:
              >>> EnvironmentHelper.is_in('DEV', ['dev', 'staging', 'prod'])
              True
              >>> EnvironmentHelper.is_in('Staging', ['DEV', 'PROD'])
              False
              >>> EnvironmentHelper.is_in(None, ['dev'])
              False
          """
          if not env:
              return False
          normalized_env = EnvironmentHelper.normalize(env)
          normalized_list = {EnvironmentHelper.normalize(e) for e in env_list}
          return normalized_env in normalized_list

      @staticmethod
      def find_in_dict(config: dict, env: str | None) -> dict | None:
          """
          Find environment key in dict (case-insensitive).

          Used for resolving environment-specific config.

          Args:
              config: Dictionary with environment keys
              env: Environment string to find

          Returns:
              Value for matching key, or None if not found.

          Examples:
              >>> config = {'DEV': {'required': False}, 'PROD': {'required': True}}
              >>> EnvironmentHelper.find_in_dict(config, 'dev')
              {'required': False}
              >>> EnvironmentHelper.find_in_dict(config, 'staging')
              None
          """
          if not config or not env:
              return None
          normalized_env = EnvironmentHelper.normalize(env)
          for key, value in config.items():
              if EnvironmentHelper.normalize(key) == normalized_env:
                  return value
          return None
  ```
- Docstrings complètes avec exemples
- Type hints stricts (Python 3.9+)
- **PAS d'alias** (certif, stg, etc.) — Epic 21 a supprimé la normalisation

**Rationale :** Centraliser logique case-insensitive dans une classe testable réutilisable

---

### AC2: Migrer executions/utils.py vers EnvironmentHelper

**Given** `executions/utils.py` contient 2 fonctions avec logique case-insensitive
**When** les fonctions sont migrées vers `EnvironmentHelper`
**Then** :

- **Fonction `_get_env_config_case_insensitive()` (ligne 70-104) :**
  - Remplacer la boucle case-insensitive par `EnvironmentHelper.find_in_dict(config, env)`
  - Conserver validation `isinstance(value, dict)` et logging
  - Retourner `{}` si not found (comportement actuel)

  ```python
  def _get_env_config_case_insensitive(config: dict, env: str) -> dict:
      """
      Story 21.2, Task 4.1: Helper to get environment-specific config with case-insensitive lookup.
      Story 26.7 AC2: Migrated to use EnvironmentHelper.find_in_dict().
      ...
      """
      if not config or not env:
          return {}

      value = EnvironmentHelper.find_in_dict(config, env)
      if value is None:
          return {}

      # HIGH-5 FIX: Log warning if config value is not a dict
      if not isinstance(value, dict):
          exec_logger.warning(
              "invalid_env_config_value",
              env=env,
              value_type=type(value).__name__,
              correlation_id=get_correlation_id(),
              message="Environment config value should be a dict, returning empty dict",
          )
          return {}

      return value
  ```

- **Fonction `_validate_environment_against_inventory()` (ligne 106-149) :**
  - Remplacer `valid_envs_lower = {e.lower() for e in valid_environments}` par helper
  - Remplacer `environment.lower() not in valid_envs_lower` par `not EnvironmentHelper.is_in(environment, valid_environments)`

  ```python
  def _validate_environment_against_inventory(environment: str, *, user_id: int | None = None) -> None:
      """
      ...
      Story 26.7 AC2: Migrated to use EnvironmentHelper.is_in().
      """
      if not environment:
          return

      inventory_service = InventoryService()
      valid_environments = inventory_service.list_environments()

      if not EnvironmentHelper.is_in(environment, valid_environments):
          # Audit trail...
          raise BadRequestError(...)
  ```

- Import ajouté : `from core.environment import EnvironmentHelper`
- Tests existants `test_utils.py` passent sans modification

**Rationale :** Réduire duplication dans executions/utils.py

---

### AC3: Migrer profiles/validation.py vers EnvironmentHelper

**Given** `profiles/validation.py::validate_profile_environments()` contient logique case-insensitive
**When** la fonction est migrée vers `EnvironmentHelper`
**Then** :

- Remplacer `normalized_envs = [env.lower() for env in environments]` par `EnvironmentHelper.normalize()`
- Remplacer `valid_envs_lower = {e.lower() for e in valid_environments}` par helper
- Remplacer `env not in valid_envs_lower` par `not EnvironmentHelper.is_in(env, valid_environments)` (direct, sans pré-normalization)

```python
def validate_profile_environments(
    environments: list[str],
    *,
    user_id: int | None = None,
) -> list[str]:
    """
    Validate profile environments against inventory (Story 21.6, AC1-3).
    Story 26.7 AC3: Migrated to use EnvironmentHelper.is_in().
    ...
    """
    if not environments:
        return []

    inventory_service = InventoryService()
    valid_environments = inventory_service.list_environments()

    # Find invalid environments using helper (AC3)
    invalid_envs = [env for env in environments if not EnvironmentHelper.is_in(env, valid_environments)]

    if invalid_envs:
        # Audit trail BEFORE raising error...
        raise BadRequestError(...)

    # Return normalized list (AC3)
    return [EnvironmentHelper.normalize(env) for env in environments]
```

- Import ajouté : `from core.environment import EnvironmentHelper`
- Tests existants `test_environment_validation_integration.py` passent sans modification

**Rationale :** Réduire duplication dans profiles/validation.py

---

### AC4: Migrer inventory/services.py vers EnvironmentHelper

**Given** `inventory/services.py` et modules délégués contiennent comparaisons case-insensitive
**When** les comparaisons sont migrées vers `EnvironmentHelper`
**Then** :

- **Identifier occurrences :**
  - `inventory/services.py` : comparaisons `.lower()` dans méthodes
  - `inventory/rbac_filter.py` : comparaisons environnements dans filtres RBAC
  - `inventory/query_executor.py` : comparaisons dans queries SQL

- **Migrer vers helper :**
  - Remplacer `env.lower() == other.lower()` par `EnvironmentHelper.matches(env, other)`
  - Remplacer `[e.lower() for e in envs]` par `[EnvironmentHelper.normalize(e) for e in envs]`
  - Remplacer `env.lower() in [x.lower() for x in list]` par `EnvironmentHelper.is_in(env, list)`

- **Exemples spécifiques à identifier (grep puis migrer) :**
  - `inventory/rbac_filter.py` : Comparaisons environnements dans `_filter_targets_by_permissions()`
  - `inventory/query_executor.py` : Comparaisons dans `_build_filter_clause()`

- Import ajouté : `from core.environment import EnvironmentHelper`
- Tests existants `test_services.py`, `test_rbac_filter.py`, `test_query_executor.py` passent sans modification

**Rationale :** Réduire duplication dans inventory (module le plus volumineux)

---

### AC5: Supprimer duplication hardcodée

**Given** les usages ont été migrés vers `EnvironmentHelper`
**When** la migration est complète
**Then** :

- **Vérifier grep :** aucune occurrence de logique case-insensitive manuelle pour environnements
  - Pattern : `(env|environment).*\.strip\(\).*\.lower\(\)` dans fichiers migrated
  - Pattern : `\{.*\.lower\(\).*for.*in.*\}` pour set comprehensions environnements

- **Supprimer commentaires obsolètes** mentionnant "normalisation certif→staging" si présents
- **Pas de suppression de code** — les fonctions existantes sont conservées, seule leur implémentation interne change

**Rationale :** Garantir que toute la logique passe par le helper centralisé

---

### AC6: Tests unitaires EnvironmentHelper

**Given** la classe `EnvironmentHelper` est créée
**When** les tests sont écrits
**Then** :

- Fichier `core/tests/test_environment.py` créé
- Tests pour `normalize()` :
  ```python
  def test_normalize_lowercase():
      assert EnvironmentHelper.normalize('DEV') == 'dev'
      assert EnvironmentHelper.normalize('PROD') == 'prod'

  def test_normalize_trim():
      assert EnvironmentHelper.normalize('  staging  ') == 'staging'

  def test_normalize_none():
      assert EnvironmentHelper.normalize(None) == ''

  def test_normalize_empty():
      assert EnvironmentHelper.normalize('') == ''
  ```

- Tests pour `matches()` :
  ```python
  def test_matches_case_insensitive():
      assert EnvironmentHelper.matches('DEV', 'dev') is True
      assert EnvironmentHelper.matches('Staging', 'STAGING') is True

  def test_matches_different():
      assert EnvironmentHelper.matches('dev', 'prod') is False

  def test_matches_none():
      assert EnvironmentHelper.matches(None, '') is True
      assert EnvironmentHelper.matches(None, 'dev') is False
  ```

- Tests pour `is_in()` :
  ```python
  def test_is_in_found():
      assert EnvironmentHelper.is_in('DEV', ['dev', 'staging', 'prod']) is True
      assert EnvironmentHelper.is_in('Staging', ['DEV', 'STAGING', 'PROD']) is True

  def test_is_in_not_found():
      assert EnvironmentHelper.is_in('qa', ['dev', 'prod']) is False

  def test_is_in_none():
      assert EnvironmentHelper.is_in(None, ['dev']) is False
  ```

- Tests pour `find_in_dict()` :
  ```python
  def test_find_in_dict_found():
      config = {'DEV': {'required': False}, 'PROD': {'required': True}}
      result = EnvironmentHelper.find_in_dict(config, 'dev')
      assert result == {'required': False}

  def test_find_in_dict_case_insensitive():
      config = {'STAGING': {'change': True}}
      result = EnvironmentHelper.find_in_dict(config, 'staging')
      assert result == {'change': True}

  def test_find_in_dict_not_found():
      config = {'DEV': {'x': 1}}
      result = EnvironmentHelper.find_in_dict(config, 'prod')
      assert result is None

  def test_find_in_dict_none():
      config = {'DEV': {'x': 1}}
      result = EnvironmentHelper.find_in_dict(config, None)
      assert result is None
  ```

- **Total : 15+ tests** couvrant tous les edge cases
- **Coverage : ≥95%** pour `core/environment.py`

**Rationale :** Tests unitaires garantissent stabilité du helper

---

### AC7: Tous les tests existants passent (0 régression)

**Given** la migration est terminée
**When** la suite de tests est exécutée
**Then** :

- **100% des tests existants passent** sans modification de logique fonctionnelle
- Tests spécifiques vérifiés :
  - `executions/tests/test_utils.py` — tests de `_get_env_config_case_insensitive()` et `_validate_environment_against_inventory()`
  - `executions/tests/test_environment_validation.py` — tests validation environnement
  - `profiles/tests/test_environment_validation_integration.py` — tests validation profils
  - `inventory/tests/test_services.py` — tests inventory service avec environnements
  - `inventory/tests/test_rbac_filter.py` — tests filtres RBAC environnements
- Aucune régression fonctionnelle
- Les tests peuvent nécessiter des ajustements d'imports si ils mock directement la logique case-insensitive

**Rationale :** La migration est transparente — comportement externe identique

---

## Tasks / Subtasks

### Task 1: Créer la classe EnvironmentHelper (AC1)
- [x]**1.1** Créer fichier `core/environment.py`
- [x]**1.2** Définir la classe `EnvironmentHelper` avec docstring Story 26.7
- [x]**1.3** Implémenter méthode `normalize(env: str | None) -> str`
- [x]**1.4** Implémenter méthode `matches(a: str | None, b: str | None) -> bool`
- [x]**1.5** Implémenter méthode `is_in(env: str | None, env_list: list[str]) -> bool`
- [x]**1.6** Implémenter méthode `find_in_dict(config: dict, env: str | None) -> dict | None`
- [x]**1.7** Ajouter type hints complets (Python 3.9+)
- [x]**1.8** Ajouter docstrings avec exemples pour chaque méthode
- [x]**1.9** Vérifier mypy: `npx mypy core/environment.py` (0 erreurs)

---

### Task 2: Créer tests unitaires EnvironmentHelper (AC6)
- [x]**2.1** Créer fichier `core/tests/test_environment.py`
- [x]**2.2** Tests `normalize()` : lowercase, trim, none, empty (6 tests)
- [x]**2.3** Tests `matches()` : case-insensitive, different, none (6 tests)
- [x]**2.4** Tests `is_in()` : found, not found, none (6 tests)
- [x]**2.5** Tests `find_in_dict()` : found, case-insensitive, not found, none (8 tests)
- [x]**2.6** Tests edge cases : whitespace, empty dict, numeric coercion (included above)
- [x]**2.7** Exécuter tests : `pytest core/tests/test_environment.py` — 26/26 passent
- [x]**2.8** Vérifier coverage : `pytest --cov=core.environment` — 100%

---

### Task 3: Migrer executions/utils.py (AC2)
- [x]**3.1** Ajouter import : `from core.environment import EnvironmentHelper`
- [x]**3.2** Migrer `_get_env_config_case_insensitive()` vers `EnvironmentHelper.find_in_dict()`
- [x]**3.3** Conserver validation `isinstance(value, dict)` et logging (HIGH-5 fix)
- [x]**3.4** Migrer `_validate_environment_against_inventory()` vers `EnvironmentHelper.is_in()`
- [x]**3.5** Conserver audit trail et error handling (HIGH-4 fix)
- [x]**3.6** Exécuter tests : `pytest executions/tests/test_utils.py` — 55/55 passent
- [x]**3.7** Exécuter tests : `pytest executions/tests/test_environment_validation.py` — 24/26 passent (2 pré-existants: mock path incorrect)

---

### Task 4: Migrer profiles/validation.py (AC3)
- [x]**4.1** Ajouter import : `from core.environment import EnvironmentHelper`
- [x]**4.2** Remplacer normalization manuelle par `EnvironmentHelper.normalize()`
- [x]**4.3** Remplacer validation manuelle par `EnvironmentHelper.is_in()`
- [x]**4.4** Conserver audit trail et error handling (SOC1 compliance)
- [x]**4.5** Exécuter tests : `pytest profiles/tests/` — 29/29 passent

---

### Task 5: Migrer inventory/ modules (AC4)
- [x]**5.1** Identifier occurrences logique case-insensitive (15+ trouvées, 6 env-related migrées)
- [x]**5.2** Ajouter import dans fichiers concernés (services.py, views.py, query_executor.py)
- [x]**5.3** Migrer `inventory/services.py` : 5 occurrences env comparisons → EnvironmentHelper
- [x]**5.4** `inventory/rbac_filter.py` : non migré — `.lower()` pour target names/attributes, pas environnements
- [x]**5.5** Migrer `inventory/query_executor.py` : 1 occurrence raw_env normalization
- [x]**5.6** Migrer `inventory/views.py` : 1 occurrence env validation
- [x]**5.7** Migrer `executions/views/scheduled_views.py` : 4 occurrences environment.lower()
- [x]**5.8** Exécuter tests : `pytest inventory/tests/test_services.py` — 75/75 passent, 280 total inventory passent

---

### Task 6: Vérification finale (AC5, AC7)
- [x]**6.1** Grep vérification : 0 occurrences `env.strip().lower()` dans executions/, profiles/, inventory/
- [x]**6.2** Commentaires `certif→staging` conservés dans `_normalize_environment()` (alias legacy, pas de suppression)
- [x]**6.3** Suite complète tests: 1099 passed (core + executions + profiles + inventory)
- [x]**6.4** Tests passent — échecs pré-existants uniquement (views.py 301 redirect, test_environments normalization)
- [x]**6.5** Ruff check : 0 warnings sur core/environment.py et tests
- [x]**6.6** Coverage helper : 100% pour `core/environment.py`

---

### Task 7: Documentation et cleanup
- [x]**7.1** Docstrings complets dans `core/environment.py` (header + méthodes avec exemples)
- [x]**7.2** Mentions Story 26.7 ajoutées dans docstrings des fichiers modifiés
- [x]**7.3** `core/__init__.py` vide — import direct `from core.environment import EnvironmentHelper`
- [x]**7.4** Imports vérifiés : pas d'imports morts (ruff 0 warnings)
- [x]**7.5** Ruff : `ruff check core/environment.py` — 0 warnings
- [x]**7.6** Story file mis à jour avec File List, Change Log, Dev Agent Record

---

## Dev Notes

### Références techniques

**Source principale :**
- [Epic 26: Qualité du Code — Assessment 6 février 2026](../planning-artifacts/epic-26-qualite-code-assessment-fev-2026.md)
- Section 4.5 du code-quality-assessment.md

**Fichiers concernés :**
- `idp-portal/django_backend/core/environment.py` (NOUVEAU)
- `idp-portal/django_backend/core/tests/test_environment.py` (NOUVEAU)
- `idp-portal/django_backend/executions/utils.py` (MODIFIÉ)
- `idp-portal/django_backend/profiles/validation.py` (MODIFIÉ)
- `idp-portal/django_backend/inventory/services.py` (MODIFIÉ)
- `idp-portal/django_backend/inventory/rbac_filter.py` (MODIFIÉ — si occurrences trouvées)
- `idp-portal/django_backend/inventory/query_executor.py` (MODIFIÉ — si occurrences trouvées)

---

### Architecture & Patterns existants

**Pattern actuel :** Logique case-insensitive dupliquée
- `.strip().lower()` répété dans 4+ fichiers
- Set comprehensions `{e.lower() for e in envs}` dupliquées
- Comparaisons manuelles `env.lower() == other.lower()`
- Tests dupliqués pour la même logique

**Pattern cible :** Helper centralisé réutilisable
- `EnvironmentHelper.normalize()` : normalisation lowercase
- `EnvironmentHelper.matches()` : comparaison case-insensitive
- `EnvironmentHelper.is_in()` : membership case-insensitive
- `EnvironmentHelper.find_in_dict()` : dict lookup case-insensitive
- Tests unitaires isolés dans `test_environment.py`

**Principes architecturaux (Architecture.md) :**
- **Django 5.2** : Modèles + migrations
- **Python 3.9+** : Type hints, dataclasses
- **Oracle DB** : Queries SQL via python-oracledb
- **Structlog** : Logging JSON structuré
- **pytest** : Tests unitaires + intégration

**Patterns établis dans le codebase :**

1. **Helper classes statiques** (Story 22.7, executions/utils.py) :
   - Méthodes statiques pour logique réutilisable
   - Type hints stricts
   - Docstrings avec exemples

2. **Centralisation logique commune** (Story 26.1, inventory/) :
   - Extraction logique dupliquée vers services/helpers
   - Réduction duplication
   - Tests unitaires isolés

3. **Migration sans régression** (Stories 26.1-26.6) :
   - Tests existants DOIVENT passer
   - Comportement externe identique
   - Documentation mise à jour

---

### Contexte Epic 21 — CRITICAL

**⚠️ Epic 21 a SUPPRIMÉ la normalisation via aliases**

**Avant Epic 21 (obsolète) :**
```python
# OBSOLETE — DO NOT USE
ENVIRONMENT_ALIASES = {
    'certif': 'staging',
    'stg': 'staging',
    'cert': 'staging',
}

def normalize_environment(env: str) -> str:
    """OBSOLETE — Epic 21 removed this."""
    normalized = env.lower()
    return ENVIRONMENT_ALIASES.get(normalized, normalized)
```

**Après Epic 21 (actuel) :**
```python
# Story 21.1, 21.2: Inventory = single source of truth, raw values
valid_environments = inventory_service.list_environments()  # Returns: ['dev', 'lab', 'qa', 'uat', 'certif', 'staging', 'prod']

# Comparison: case-insensitive only (NO alias transformation)
if environment.lower() in {e.lower() for e in valid_environments}:
    pass  # Valid
```

**Références Epic 21 :**
- Story 21.1: Backend supprimer normalisation, utiliser valeurs brutes inventaire
- Story 21.2: Backend ajuster profil env matching + executions (case-insensitive)
- Story 21.4: Frontend éditeurs admin environnements dynamiques
- Story 21.6: Validation environnements profil à sauvegarde

**Implications pour Story 26.7 :**
- **PAS d'alias** (certif, stg, etc.) dans `EnvironmentHelper`
- Méthodes helper = case-insensitive comparison UNIQUEMENT
- Inventaire = source de vérité (pas de transformation)
- Backward compatibility avec Epic 21 (tests passent sans modification)

---

### Analyse détaillée duplication actuelle

**1. executions/utils.py (2 occurrences) :**

```python
# Occurrence 1: _get_env_config_case_insensitive (lignes 70-104)
def _get_env_config_case_insensitive(config: dict, env: str) -> dict:
    env_lower = (env or '').strip().lower()  # ← DUPLICATION
    for key, value in config.items():
        if (key or '').strip().lower() == env_lower:  # ← DUPLICATION
            return value
    return {}

# Occurrence 2: _validate_environment_against_inventory (lignes 106-149)
def _validate_environment_against_inventory(environment: str, *, user_id: int | None = None) -> None:
    valid_environments = inventory_service.list_environments()
    valid_envs_lower = {e.lower() for e in valid_environments}  # ← DUPLICATION
    if environment.lower() not in valid_envs_lower:  # ← DUPLICATION
        raise BadRequestError(...)
```

**2. profiles/validation.py (1 occurrence) :**

```python
# validate_profile_environments (lignes 27-100)
def validate_profile_environments(environments: list[str], *, user_id: int | None = None) -> list[str]:
    valid_environments = inventory_service.list_environments()
    valid_envs_lower = {e.lower() for e in valid_environments}  # ← DUPLICATION
    normalized_envs = [env.lower() for env in environments]  # ← DUPLICATION
    invalid_envs = [env for env in normalized_envs if env not in valid_envs_lower]  # ← DUPLICATION

    if invalid_envs:
        raise BadRequestError(...)

    return normalized_envs
```

**3. inventory/ modules (occurrences à identifier via grep) :**

Potentiellement dans :
- `inventory/services.py` : méthodes `list_targets_for_user()`, `get_allowed_environments_for_user()`
- `inventory/rbac_filter.py` : méthode `_filter_targets_by_permissions()` (comparaisons env)
- `inventory/query_executor.py` : méthodes `read_servers()`, `read_instances()`, `read_databases()` (filtres WHERE)

**Total estimé : 6-8 occurrences** de logique case-insensitive à centraliser

---

### Stratégie de migration

**Phase 1 : Créer helper + tests (Task 1-2)**
- Créer `core/environment.py` avec `EnvironmentHelper`
- Créer `core/tests/test_environment.py` avec 15+ tests
- Vérifier que tous les tests helper passent
- **Pas de modification des modules existants**

**Phase 2 : Migrer executions/utils.py (Task 3)**
- Migrer 2 fonctions vers helper
- Exécuter tests `test_utils.py`, `test_environment_validation.py`
- Vérifier 0 régression

**Phase 3 : Migrer profiles/validation.py (Task 4)**
- Migrer 1 fonction vers helper
- Exécuter tests `test_environment_validation_integration.py`
- Vérifier 0 régression

**Phase 4 : Migrer inventory/ (Task 5)**
- Identifier occurrences via grep
- Migrer vers helper
- Exécuter tests `test_services.py`, `test_rbac_filter.py`, `test_query_executor.py`
- Vérifier 0 régression

**Phase 5 : Validation finale (Task 6-7)**
- Grep vérification : pas de duplication restante
- Suite complète de tests backend
- Mypy, ruff, coverage
- Documentation et commit

---

### Exemple d'implémentation EnvironmentHelper

```python
"""
Environment helper utilities — Story 26.7.

Centralized case-insensitive environment comparison and matching.
Epic 21 removed normalization via aliases (certif→staging).
Inventory is now the single source of truth with raw values.
This helper provides case-insensitive comparison only.
"""
from __future__ import annotations


class EnvironmentHelper:
    """
    Helper for case-insensitive environment comparison and matching.

    Story 26.7 — Centralized environment logic post-Epic 21.
    Epic 21 removed normalization via aliases.
    Inventory is the single source of truth with raw values (dev, lab, qa, uat, certif, staging, prod).
    This helper provides case-insensitive comparison only.

    Examples:
        >>> EnvironmentHelper.normalize('DEV')
        'dev'
        >>> EnvironmentHelper.matches('DEV', 'dev')
        True
        >>> EnvironmentHelper.is_in('Staging', ['dev', 'STAGING', 'prod'])
        True
        >>> config = {'DEV': {'required': False}, 'PROD': {'required': True}}
        >>> EnvironmentHelper.find_in_dict(config, 'dev')
        {'required': False}
    """

    @staticmethod
    def normalize(env: str | None) -> str:
        """
        Normalize environment string to lowercase for comparison.

        Args:
            env: Environment string (e.g., 'DEV', 'Staging', 'PROD')

        Returns:
            Lowercase, trimmed string. Empty string if None.

        Examples:
            >>> EnvironmentHelper.normalize('DEV')
            'dev'
            >>> EnvironmentHelper.normalize('  Staging  ')
            'staging'
            >>> EnvironmentHelper.normalize(None)
            ''
        """
        if not env:
            return ''
        return str(env).strip().lower()

    @staticmethod
    def matches(a: str | None, b: str | None) -> bool:
        """
        Check if two environment strings match (case-insensitive).

        Args:
            a: First environment string
            b: Second environment string

        Returns:
            True if normalized strings are equal, False otherwise.

        Examples:
            >>> EnvironmentHelper.matches('DEV', 'dev')
            True
            >>> EnvironmentHelper.matches('Staging', 'STAGING')
            True
            >>> EnvironmentHelper.matches('prod', 'staging')
            False
            >>> EnvironmentHelper.matches(None, '')
            True
        """
        return EnvironmentHelper.normalize(a) == EnvironmentHelper.normalize(b)

    @staticmethod
    def is_in(env: str | None, env_list: list[str]) -> bool:
        """
        Check if environment is in list (case-insensitive).

        Args:
            env: Environment string to check
            env_list: List of environment strings

        Returns:
            True if env (normalized) is in list (normalized), False otherwise.

        Examples:
            >>> EnvironmentHelper.is_in('DEV', ['dev', 'staging', 'prod'])
            True
            >>> EnvironmentHelper.is_in('Staging', ['DEV', 'PROD'])
            False
            >>> EnvironmentHelper.is_in(None, ['dev'])
            False
        """
        if not env:
            return False
        normalized_env = EnvironmentHelper.normalize(env)
        normalized_list = {EnvironmentHelper.normalize(e) for e in env_list}
        return normalized_env in normalized_list

    @staticmethod
    def find_in_dict(config: dict, env: str | None) -> dict | None:
        """
        Find environment key in dict (case-insensitive).

        Used for resolving environment-specific config.

        Args:
            config: Dictionary with environment keys
            env: Environment string to find

        Returns:
            Value for matching key, or None if not found.

        Examples:
            >>> config = {'DEV': {'required': False}, 'PROD': {'required': True}}
            >>> EnvironmentHelper.find_in_dict(config, 'dev')
            {'required': False}
            >>> EnvironmentHelper.find_in_dict(config, 'staging')
            None
        """
        if not config or not env:
            return None
        normalized_env = EnvironmentHelper.normalize(env)
        for key, value in config.items():
            if EnvironmentHelper.normalize(key) == normalized_env:
                return value
        return None
```

---

### Risques & Mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| **Régression fonctionnelle** | ÉLEVÉ | Tous les tests existants DOIVENT passer. Migrer progressivement (executions → profiles → inventory). Exécuter tests après chaque phase. |
| **Performance dégradée** | FAIBLE | Helper utilise mêmes opérations (`.strip().lower()`). Pas de surcoût performance. |
| **Imports circulaires** | MOYEN | `core/environment.py` ne doit importer AUCUN module métier (executions, profiles, inventory). Importer uniquement builtins. |
| **Epic 21 compatibility** | ÉLEVÉ | NE PAS ajouter d'alias (certif→staging). Helper = case-insensitive comparison UNIQUEMENT. Vérifier que tests Epic 21 passent. |
| **Tests mocks cassés** | MOYEN | Certains tests peuvent mock directement `.lower()`. Identifier avec `grep -rn "mock.*lower" tests/`. Mettre à jour mocks pour utiliser helper. |
| **Mypy errors** | MOYEN | Type hints stricts (Python 3.9+). Vérifier `mypy core/environment.py` régulièrement. Utiliser `str | None` au lieu de `Optional[str]`. |

---

### Ordre d'implémentation recommandé

1. **Créer helper + tests (Task 1-2)**
   - Pas de dépendances, setup initial
   - Vérifier que tous les tests helper passent

2. **Migrer executions/utils.py (Task 3)**
   - Module le plus simple (2 fonctions)
   - Tests existants bien couverts
   - Facile à valider

3. **Migrer profiles/validation.py (Task 4)**
   - Module simple (1 fonction)
   - Tests existants bien couverts
   - Dépend de executions/utils (déjà migré)

4. **Migrer inventory/ (Task 5)**
   - Module le plus complexe (occurrences multiples)
   - Nécessite grep pour identifier toutes les occurrences
   - Dépend de executions + profiles (déjà migrés)

5. **Validation finale (Task 6-7)**
   - Grep vérification : pas de duplication restante
   - Suite complète de tests
   - Documentation et commit

---

## Project Structure Notes

**Alignement avec la structure unifiée :**

```
idp-portal/django_backend/
├── core/
│   ├── environment.py                        # NEW — Story 26.7
│   ├── tests/
│   │   └── test_environment.py              # NEW — Story 26.7 (15+ tests)
│   └── __init__.py                          # EXISTS (export helper si nécessaire)
├── executions/
│   ├── utils.py                             # MODIFIED — Story 26.7 AC2
│   └── tests/
│       ├── test_utils.py                    # EXISTS (tests passent sans modification)
│       └── test_environment_validation.py   # EXISTS (tests passent sans modification)
├── profiles/
│   ├── validation.py                        # MODIFIED — Story 26.7 AC3
│   └── tests/
│       └── test_environment_validation_integration.py  # EXISTS (tests passent)
└── inventory/
    ├── services.py                          # MODIFIED — Story 26.7 AC4 (si occurrences)
    ├── rbac_filter.py                       # MODIFIED — Story 26.7 AC4 (si occurrences)
    ├── query_executor.py                    # MODIFIED — Story 26.7 AC4 (si occurrences)
    └── tests/
        ├── test_services.py                 # EXISTS (tests passent)
        ├── test_rbac_filter.py              # EXISTS (tests passent)
        └── test_query_executor.py           # EXISTS (tests passent)
```

**Modules touchés par cette story :**
- `core/environment.py` : NOUVEAU (~80 LOC)
- `core/tests/test_environment.py` : NOUVEAU (~120 LOC, 15+ tests)
- `executions/utils.py` : MODIFIÉ (2 fonctions migrées)
- `profiles/validation.py` : MODIFIÉ (1 fonction migrée)
- `inventory/` : MODIFIÉ (occurrences à identifier)

**Modules inchangés :**
- Tests existants (passent sans modification)
- Modèles Django (aucun changement schéma)
- APIs REST (comportement externe identique)

---

## References

**Stories liées :**
- **Epic 21 (Stories 21.1-21.6)** : Inventaire source unique, suppression normalisation aliases
- **Story 26.1** : Split inventory/services.py (pattern similaire centralisation)
- **Story 26.2** : Split executions/views.py (pattern similaire refactoring)
- **Story 22.7** : Extraire executions/views.py helpers (pattern similaire utils extraction)

**Documentation externe :**
- [Epic 26: Qualité du Code](../planning-artifacts/epic-26-qualite-code-assessment-fev-2026.md)
- [Epic 21: Inventaire source unique](../planning-artifacts/epic-21-inventaire-source-unique-environnements.md)

---

## File List

**New files:**
- `idp-portal/django_backend/core/environment.py` — EnvironmentHelper class (4 static methods)
- `idp-portal/django_backend/core/tests/test_environment.py` — 26 unit tests, 100% coverage

**Modified files:**
- `idp-portal/django_backend/executions/utils.py` — Import + migrate 2 functions to EnvironmentHelper
- `idp-portal/django_backend/executions/views/scheduled_views.py` — Import + migrate 4 environment.lower() calls
- `idp-portal/django_backend/profiles/validation.py` — Import + migrate to EnvironmentHelper.normalize/is_in
- `idp-portal/django_backend/inventory/services.py` — Import + migrate 5 env comparisons to EnvironmentHelper
- `idp-portal/django_backend/inventory/views.py` — Import + migrate 1 env validation to EnvironmentHelper.is_in
- `idp-portal/django_backend/inventory/query_executor.py` — Import + migrate 1 raw_env normalization

---

## Dev Agent Record

### Implementation Plan
- Phase 1: Create `EnvironmentHelper` class with 4 static methods (normalize, matches, is_in, find_in_dict)
- Phase 2: Create 26 unit tests with 100% coverage
- Phase 3: Migrate executions/utils.py (2 functions)
- Phase 4: Migrate profiles/validation.py (1 function)
- Phase 5: Migrate inventory modules (services.py, views.py, query_executor.py) + executions/views/scheduled_views.py
- Phase 6: Verify 0 remaining manual env .lower() patterns, run full test suite

### Completion Notes
- EnvironmentHelper created at `core/environment.py` with 4 static methods, all with complete docstrings and type hints
- 26 unit tests at `core/tests/test_environment.py` — 100% coverage
- Migrated 13 occurrences of manual `.lower()` / `.strip().lower()` environment comparison across 7 files
- `inventory/rbac_filter.py` NOT migrated — its `.lower()` calls are for target names and attribute values, not environments
- `inventory/services.py::_normalize_environment()` kept alias logic (certif→staging) — this is inventory data import, not comparison
- 1099 tests pass across all modified modules (core, executions, profiles, inventory)
- Pre-existing failures unchanged: 2 in test_environment_validation.py (wrong mock path), 23 in inventory test_views.py (301 redirect), 1 in test_environments.py (Epic 21 behavior change)
- Ruff 0 warnings, 100% coverage on helper

### Debug Log
- profiles/validation.py: initial migration caused test_audit_trail_preserves_original_case to fail — `invalid_envs` returned original case instead of normalized. Fixed by normalizing first, then finding invalids.

---

## Change Log

- **2026-02-13** — Story 26.7: Created `EnvironmentHelper` class in `core/environment.py`, migrated case-insensitive environment comparison logic from 7 files (executions/utils.py, executions/views/scheduled_views.py, profiles/validation.py, inventory/services.py, inventory/views.py, inventory/query_executor.py). 26 unit tests, 100% coverage, 0 regression.

---
