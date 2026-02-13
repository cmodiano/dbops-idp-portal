# Story 17.5: Sécuriser la gestion des secrets

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **équipe sécurité et DevOps**,
I want **supprimer les secrets par défaut risquant de fuiter en production et appliquer un fail-fast si variables manquantes en environnement non-dev**,
so that **aucun secret exploitable ne soit présent dans le code et le démarrage soit refusé si configuration incomplète**.

## Acceptance Criteria

**Given** l'application Django démarre en environnement non-dev (staging, production)
**When** une variable d'environnement critique est absente ou contient une valeur par défaut dangereuse
**Then** l'application refuse de démarrer avec une exception `ImproperlyConfigured` explicite indiquant quelle(s) variable(s) sont manquantes

**Given** l'application Django utilise actuellement des secrets par défaut hardcodés (SECRET_KEY, JWT_SECRET_KEY, ORACLE_PASSWORD)
**When** le refactoring est terminé
**Then** ces secrets n'ont plus de valeur par défaut dans settings.py et lèvent une exception si non fournis en non-dev

**Given** l'application démarre en environnement de développement (APP_ENV=development)
**When** des secrets par défaut sont utilisés
**Then** un avertissement de sécurité est loggué au démarrage mais l'application continue (développement local seulement)

**Given** un développeur consulte settings.py après refactoring
**When** il cherche des secrets hardcodés
**Then** aucune valeur sensible par défaut n'est trouvée (search pour `'changeme'`, `'django-insecure'`, `'change-me-in-production'` retourne vide)

**Given** les certificats SAML sont absents en production (SAML_SP_CERT_PATH vide)
**When** l'authentification SAML est configurée (AUTH_DEV_BYPASS=false)
**Then** le démarrage échoue avec message clair : "SAML_SP_CERT_PATH requis en production avec SAML activé"

**Given** le fichier .env.production.template contient des placeholders `CHANGE_*`
**When** un administrateur déploie sans remplacer les placeholders
**Then** le démarrage échoue avec message : "Configuration de production incomplète : CHANGE_* détectés dans SECRET_KEY/JWT_SECRET_KEY/ORACLE_PASSWORD"

**Given** l'environnement APP_ENV=development est actif
**When** l'application démarre avec AUTH_DEV_BYPASS=true
**Then** un avertissement sécurité est loggué : "⚠️ DEV MODE: AUTH_DEV_BYPASS activé - NE PAS utiliser en production"

**Given** Vault est configuré (VAULT_ADDR défini et différent de localhost)
**When** le health check s'exécute en production
**Then** Vault down entraîne un statut "degraded" (comportement actuel conservé, pas de changement)

**Given** la validation des secrets réussit au démarrage
**When** l'application démarre
**Then** un message de confirmation est loggué : "✓ Configuration des secrets validée pour environnement {APP_ENV}"

**Given** tous les secrets critiques sont validés au démarrage
**When** les tests de sécurité s'exécutent
**Then** un nouveau test `test_secret_validation_production` vérifie que les secrets par défaut déclenchent ImproperlyConfigured en non-dev

## Tasks / Subtasks

### Task 1: Identifier et documenter tous les secrets à sécuriser (AC: #1, #2, #4)

- [x] Subtask 1.1: Audit complet des secrets dans settings.py
  - Lire `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend/idp_backend/settings.py` lignes 28-30 (SECRET_KEY)
  - Identifier ligne 104 (ORACLE_PASSWORD)
  - Identifier ligne 230 (JWT_SECRET_KEY)
  - Identifier lignes 217-224 (SAML_SP_CERT_PATH, SAML_SP_KEY_PATH, SAML_IDP_CERT_PATH)
  - Documenter valeurs par défaut actuelles : `'django-insecure-...'`, `'changeme'`, `'change-me-in-production'`
  - Vérifier .env.example ligne 14 (JWT_SECRET_KEY placeholder)

- [x] Subtask 1.2: Catégoriser secrets par criticité
  - **CRITICAL (fail-fast requis):** SECRET_KEY, JWT_SECRET_KEY, ORACLE_PASSWORD
  - **HIGH (fail-fast si SAML actif):** SAML_SP_CERT_PATH, SAML_SP_KEY_PATH, SAML_IDP_CERT_PATH (seulement si AUTH_DEV_BYPASS=false)
  - **MEDIUM (graceful degradation):** VAULT_TOKEN, VAULT_ROLE_ID (Vault optionnel actuellement)
  - **LOW (dev-only):** CORS_ORIGIN, DEBUG (déjà correctement gérés)

- [x] Subtask 1.3: Analyser comportement actuel en production simulée
  - Tester démarrage avec .env.production.template contenant placeholders `CHANGE_*`
  - Vérifier si l'application démarre avec succès (attendu: oui, comportement à corriger)
  - Tester démarrage sans SECRET_KEY défini (attendu: utilise django-insecure-...)
  - Documenter que aucun échec de validation n'existe actuellement

### Task 2: Créer module de validation des secrets au démarrage (AC: #1, #3, #9)

- [x] Subtask 2.1: Créer `core/startup_checks.py`
  - Créer fichier `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend/core/startup_checks.py`
  - Importer `django.core.exceptions.ImproperlyConfigured`
  - Importer `os`, `structlog` pour logging structuré
  - Définir constantes: `INSECURE_DEFAULTS`, `PLACEHOLDER_PATTERNS`

- [x] Subtask 2.2: Implémenter fonction `validate_required_secrets()`
  ```python
  import os
  import re
  from django.core.exceptions import ImproperlyConfigured
  import structlog

  logger = structlog.get_logger(__name__)

  # Liste des secrets avec valeurs interdites en production
  INSECURE_DEFAULTS = {
      'SECRET_KEY': ['django-insecure-', 'changeme', ''],
      'JWT_SECRET_KEY': ['change-me-in-production', 'changeme', ''],
      'ORACLE_PASSWORD': ['changeme', ''],
  }

  # Pattern pour détecter placeholders non remplacés
  PLACEHOLDER_PATTERN = re.compile(r'^CHANGE_[A-Z_]+$|^<[A-Z_]+>$|^TODO:')

  def validate_required_secrets(app_env: str, auth_dev_bypass: bool):
      """
      Valide que tous les secrets critiques sont configurés correctement.

      Args:
          app_env: Environnement applicatif (development, staging, production)
          auth_dev_bypass: Si True, avertissement seulement (dev mode)

      Raises:
          ImproperlyConfigured: Si secrets manquants/insecure en non-dev
      """
      is_dev = app_env.lower() == 'development'
      errors = []
      warnings = []

      # Validation secrets critiques
      for secret_name, forbidden_values in INSECURE_DEFAULTS.items():
          secret_value = os.getenv(secret_name, '')

          # Secret absent
          if not secret_value:
              errors.append(f"{secret_name} is not set")
              continue

          # Valeur interdite en production
          for forbidden in forbidden_values:
              if forbidden and secret_value.startswith(forbidden):
                  if is_dev:
                      warnings.append(f"{secret_name} uses default value (dev mode)")
                  else:
                      errors.append(f"{secret_name} contains insecure default value")
                  break

          # Placeholder non remplacé
          if PLACEHOLDER_PATTERN.match(secret_value):
              errors.append(f"{secret_name} contains unreplaced placeholder: {secret_value}")

      # Validation SAML si authentification requise
      if not auth_dev_bypass and not is_dev:
          saml_certs = ['SAML_SP_CERT_PATH', 'SAML_SP_KEY_PATH', 'SAML_IDP_CERT_PATH']
          for cert_var in saml_certs:
              cert_path = os.getenv(cert_var, '')
              if not cert_path:
                  errors.append(f"{cert_var} required for SAML authentication in production")

      # Log warnings en dev
      if warnings:
          for warning in warnings:
              logger.warning("secret_validation_warning", message=warning, environment=app_env)
          logger.warning("dev_mode_active", message="⚠️ DEV MODE: Using default secrets - DO NOT use in production")

      # Fail-fast en non-dev
      if errors and not is_dev:
          error_msg = "\n".join([
              "❌ SECURITY: Secret validation failed in production environment",
              f"Environment: {app_env}",
              "Missing or insecure secrets:",
              *[f"  - {err}" for err in errors],
              "",
              "Fix by setting environment variables in .env or system environment.",
              "See .env.production.template for required variables."
          ])
          logger.error("secret_validation_failed", errors=errors, environment=app_env)
          raise ImproperlyConfigured(error_msg)

      # Log succès
      logger.info("secret_validation_success", environment=app_env,
                  warnings_count=len(warnings), is_dev=is_dev)
  ```

- [x] Subtask 2.3: Tester la fonction `validate_required_secrets()` isolément
  - Créer `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend/core/tests/test_startup_checks.py`
  - Cas 1: Dev mode avec secrets par défaut → warnings logged, pas d'exception
  - Cas 2: Production sans SECRET_KEY → ImproperlyConfigured levée
  - Cas 3: Production avec SECRET_KEY=CHANGE_SECRET → ImproperlyConfigured levée
  - Cas 4: Production avec tous secrets valides → succès
  - Cas 5: Production + AUTH_DEV_BYPASS=false + SAML_SP_CERT_PATH vide → ImproperlyConfigured
  - Cas 6: Dev + AUTH_DEV_BYPASS=true → warning logged
  - Utiliser `@override_settings()` et `@patch('os.getenv')` pour tests isolés

### Task 3: Intégrer validation au démarrage de l'application (AC: #1, #3, #7)

- [x] Subtask 3.1: Appeler validation dans `core/apps.py`
  - Modifier `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend/core/apps.py`
  - Dans méthode `ready()`, après configuration structlog (ligne ~35):
  ```python
  from core.startup_checks import validate_required_secrets
  from django.conf import settings

  def ready(self):
      # ... (code structlog existant) ...

      # Story 17.5: Secret validation au démarrage
      try:
          validate_required_secrets(
              app_env=settings.APP_ENV,
              auth_dev_bypass=settings.AUTH_DEV_BYPASS
          )
      except ImproperlyConfigured:
          # Re-raise pour stopper le démarrage
          raise
  ```

- [x] Subtask 3.2: Vérifier que l'exception stoppe bien le démarrage
  - Tester avec `python manage.py check` (doit échouer si secrets invalides)
  - Tester avec `python manage.py runserver` (doit refuser de démarrer)
  - Vérifier que le message d'erreur est clair et actionnable

### Task 4: Retirer les valeurs par défaut dangereuses de settings.py (AC: #2, #4)

- [x] Subtask 4.1: Modifier settings.py - Retirer defaults des secrets critiques
  - **Ligne 29:** Remplacer
    ```python
    SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-bvc0qsxvq0dly--u$d1pge47!6f^r+wf%9e4c^2sn!=z(-wkqf')
    ```
    Par:
    ```python
    # Story 17.5: No default value - fail-fast if missing in production
    # Dev fallback: Use .env with DEV_SECRET_KEY or set APP_ENV=development for warnings
    SECRET_KEY = os.getenv('SECRET_KEY', os.getenv('DEV_SECRET_KEY', ''))
    if not SECRET_KEY:
        # Temporary fallback for dev - startup_checks.py will validate properly
        SECRET_KEY = 'django-insecure-dev-fallback-will-be-validated'
    ```

  - **Ligne 104:** Remplacer
    ```python
    ORACLE_PASSWORD = os.getenv('ORACLE_PASSWORD', 'changeme')
    ```
    Par:
    ```python
    # Story 17.5: No default value - fail-fast if missing in production
    ORACLE_PASSWORD = os.getenv('ORACLE_PASSWORD', '')
    ```

  - **Ligne 230:** Remplacer
    ```python
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'change-me-in-production')
    ```
    Par:
    ```python
    # Story 17.5: No default value - fail-fast if missing in production
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', '')
    ```

- [x] Subtask 4.2: Mettre à jour .env.example avec valeurs dev explicites
  - Modifier `/Users/cyrille/Documents/Dev/test/idp-portal/.env.example`
  - Ajouter après ligne 13:
    ```env
    # Django Secret Key (Story 17.5 - REQUIRED in production)
    # Generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
    SECRET_KEY=django-insecure-dev-only-NOT-FOR-PRODUCTION-replace-me

    # JWT Secret Key (Story 17.5 - REQUIRED in production)
    JWT_SECRET_KEY=dev-jwt-secret-NOT-FOR-PRODUCTION-replace-me
    ```
  - Modifier ligne 4:
    ```env
    # Oracle Database Password (Story 17.5 - REQUIRED in production)
    ORACLE_PASSWORD=dev_password_NOT_FOR_PRODUCTION
    ```

- [x] Subtask 4.3: Vérifier qu'aucun secret hardcodé ne reste
  - Exécuter: `grep -rn "django-insecure-bvc0qsxvq0dly" idp_backend/`
  - Exécuter: `grep -rn "change-me-in-production" idp_backend/`
  - Exécuter: `grep -rn "ORACLE_PASSWORD.*changeme" idp_backend/`
  - Tous doivent retourner vide (ou seulement commentaires/docs)

### Task 5: Créer .env.development explicite pour développement (AC: #3, #7)

- [x] Subtask 5.1: Créer fichier .env.development
  - Créer `/Users/cyrille/Documents/Dev/test/idp-portal/.env.development`
  - Copier .env.example et renommer en .env.development
  - Ajouter en header:
    ```env
    # Development environment configuration (Story 17.5)
    # SECURITY: These values are INSECURE and for local development ONLY
    # DO NOT use in staging/production environments

    APP_ENV=development
    APP_DEBUG=true

    # Dev-only secrets (Story 17.5 - startup_checks.py will warn but allow)
    SECRET_KEY=django-insecure-dev-only-NOT-FOR-PRODUCTION-replace-me
    JWT_SECRET_KEY=dev-jwt-secret-NOT-FOR-PRODUCTION-replace-me
    ORACLE_PASSWORD=dev_password_NOT_FOR_PRODUCTION

    # Dev bypass for local testing without IdP
    AUTH_DEV_BYPASS=false  # Set to true for testing without SAML
    ```

- [x] Subtask 5.2: Mettre à jour README développeur
  - Modifier `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend/README.md` section Configuration
  - Ajouter note Story 17.5:
    ```markdown
    ## Configuration des secrets (Story 17.5)

    L'application refuse de démarrer en production si des secrets critiques sont manquants ou contiennent des valeurs par défaut.

    ### Développement local
    1. Copier `.env.development` vers `.env` (ou créer depuis .env.example)
    2. L'application démarre avec warnings mais pas d'erreur
    3. Logs affichent: "⚠️ DEV MODE: Using default secrets"

    ### Production/Staging
    1. Copier `.env.production.template` vers `/etc/idp/django.env`
    2. Remplacer TOUS les placeholders `CHANGE_*`
    3. Générer SECRET_KEY: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
    4. Vérifier: `grep "CHANGE_" /etc/idp/django.env` doit retourner vide
    5. L'application refuse de démarrer si placeholders restent

    ### Variables requises en production
    - `SECRET_KEY` (Django session/CSRF)
    - `JWT_SECRET_KEY` (Token signing)
    - `ORACLE_PASSWORD` (Database access)
    - `SAML_SP_CERT_PATH`, `SAML_SP_KEY_PATH`, `SAML_IDP_CERT_PATH` (si AUTH_DEV_BYPASS=false)
    ```

### Task 6: Créer tests de sécurité pour validation des secrets (AC: #10)

- [x] Subtask 6.1: Créer test de validation production
  - Modifier `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend/tests/security/test_soc1_compliance.py`
  - Ajouter classe `TestSecretValidation` après ligne 250:
  ```python
  from django.core.exceptions import ImproperlyConfigured
  from core.startup_checks import validate_required_secrets
  from unittest.mock import patch

  class TestSecretValidation:
      """Story 17.5: Tests de validation des secrets au démarrage."""

      def test_production_missing_secret_key_fails(self):
          """Production sans SECRET_KEY doit échouer."""
          with patch.dict('os.environ', {'SECRET_KEY': ''}, clear=False):
              with pytest.raises(ImproperlyConfigured, match="SECRET_KEY is not set"):
                  validate_required_secrets(app_env='production', auth_dev_bypass=False)

      def test_production_insecure_secret_key_fails(self):
          """Production avec SECRET_KEY par défaut doit échouer."""
          with patch.dict('os.environ', {'SECRET_KEY': 'django-insecure-test'}, clear=False):
              with pytest.raises(ImproperlyConfigured, match="SECRET_KEY contains insecure default"):
                  validate_required_secrets(app_env='production', auth_dev_bypass=False)

      def test_production_placeholder_jwt_secret_fails(self):
          """Production avec placeholder JWT_SECRET_KEY doit échouer."""
          env_vars = {
              'SECRET_KEY': 'valid-production-secret-key-abc123',
              'JWT_SECRET_KEY': 'CHANGE_JWT_SECRET',
              'ORACLE_PASSWORD': 'valid-oracle-password'
          }
          with patch.dict('os.environ', env_vars, clear=False):
              with pytest.raises(ImproperlyConfigured, match="JWT_SECRET_KEY contains unreplaced placeholder"):
                  validate_required_secrets(app_env='production', auth_dev_bypass=False)

      def test_production_missing_saml_certs_with_saml_active_fails(self):
          """Production avec SAML activé (AUTH_DEV_BYPASS=false) mais certs manquants doit échouer."""
          env_vars = {
              'SECRET_KEY': 'valid-production-secret-key-abc123',
              'JWT_SECRET_KEY': 'valid-jwt-secret-key-xyz789',
              'ORACLE_PASSWORD': 'valid-oracle-password',
              'SAML_SP_CERT_PATH': '',  # Manquant
          }
          with patch.dict('os.environ', env_vars, clear=False):
              with pytest.raises(ImproperlyConfigured, match="SAML_SP_CERT_PATH required"):
                  validate_required_secrets(app_env='production', auth_dev_bypass=False)

      def test_production_all_valid_secrets_succeeds(self):
          """Production avec tous secrets valides doit réussir."""
          env_vars = {
              'SECRET_KEY': 'valid-production-secret-key-abc123',
              'JWT_SECRET_KEY': 'valid-jwt-secret-key-xyz789',
              'ORACLE_PASSWORD': 'valid-oracle-password',
              'SAML_SP_CERT_PATH': '/etc/idp/certs/sp.crt',
              'SAML_SP_KEY_PATH': '/etc/idp/certs/sp.key',
              'SAML_IDP_CERT_PATH': '/etc/idp/certs/idp.crt',
          }
          with patch.dict('os.environ', env_vars, clear=False):
              # Ne doit pas lever d'exception
              validate_required_secrets(app_env='production', auth_dev_bypass=False)

      def test_development_insecure_secrets_warns_but_succeeds(self, caplog):
          """Dev mode avec secrets par défaut doit avertir mais réussir."""
          env_vars = {
              'SECRET_KEY': 'django-insecure-dev-only',
              'JWT_SECRET_KEY': 'change-me-in-production',
              'ORACLE_PASSWORD': 'changeme',
          }
          with patch.dict('os.environ', env_vars, clear=False):
              # Ne doit pas lever d'exception en dev
              validate_required_secrets(app_env='development', auth_dev_bypass=True)
              # Doit logger des warnings
              assert "dev_mode_active" in caplog.text
              assert "DEV MODE" in caplog.text

      def test_staging_env_treated_as_production(self):
          """Staging doit être traité comme production (fail-fast)."""
          with patch.dict('os.environ', {'SECRET_KEY': 'changeme'}, clear=False):
              with pytest.raises(ImproperlyConfigured):
                  validate_required_secrets(app_env='staging', auth_dev_bypass=False)
  ```

- [x] Subtask 6.2: Créer test d'intégration démarrage application
  - Créer `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend/tests/integration/test_startup.py`
  ```python
  import pytest
  from django.core.exceptions import ImproperlyConfigured
  from django.test import override_settings
  from unittest.mock import patch

  class TestApplicationStartup:
      """Story 17.5: Tests d'intégration du démarrage de l'application."""

      def test_app_startup_fails_without_secrets_in_production(self):
          """L'application refuse de démarrer en production sans secrets."""
          with patch.dict('os.environ', {
              'APP_ENV': 'production',
              'SECRET_KEY': '',
              'JWT_SECRET_KEY': '',
              'ORACLE_PASSWORD': ''
          }, clear=False):
              with pytest.raises(ImproperlyConfigured):
                  # Simuler le démarrage via apps.ready()
                  from core.apps import CoreConfig
                  config = CoreConfig('core', 'core')
                  config.ready()

      def test_app_startup_succeeds_in_development(self):
          """L'application démarre en dev avec secrets par défaut."""
          with patch.dict('os.environ', {
              'APP_ENV': 'development',
              'SECRET_KEY': 'django-insecure-dev',
              'JWT_SECRET_KEY': 'change-me-in-production',
              'ORACLE_PASSWORD': 'changeme'
          }, clear=False):
              # Ne doit pas lever d'exception
              from core.apps import CoreConfig
              config = CoreConfig('core', 'core')
              config.ready()  # Warnings logged mais pas d'erreur
  ```

### Task 7: Validation finale et documentation (AC: #4, #9)

- [x] Subtask 7.1: Exécuter tous les tests
  - `pytest tests/security/test_soc1_compliance.py::TestSecretValidation -v`
  - `pytest tests/integration/test_startup.py -v`
  - `pytest tests/core/test_startup_checks.py -v`
  - Vérifier 100% des tests passent

- [x] Subtask 7.2: Tester scénarios réels
  - **Scénario 1:** Démarrer avec .env.development → SUCCESS + warnings
  - **Scénario 2:** Démarrer avec APP_ENV=production + secrets vides → FAIL avec message clair
  - **Scénario 3:** Démarrer avec APP_ENV=production + SECRET_KEY=CHANGE_SECRET → FAIL avec placeholder détecté
  - **Scénario 4:** Démarrer avec APP_ENV=production + tous secrets valides → SUCCESS
  - **Scénario 5:** Health check GET /api/v1/health → status 200 (pas de régression)

- [x] Subtask 7.3: Mettre à jour documentation de sécurité
  - Modifier `/Users/cyrille/Documents/Dev/test/docs/security/security-architecture.md`
  - Section "Secret Management" - Ajouter subsection "Startup Validation (Story 17.5)":
    ```markdown
    ### Startup Secret Validation (Story 17.5)

    **Fail-Fast Pattern:** Application refuses to start if critical secrets are missing or contain insecure defaults in non-dev environments.

    **Protected Secrets:**
    - `SECRET_KEY`: Django session/CSRF protection
    - `JWT_SECRET_KEY`: Token signing key
    - `ORACLE_PASSWORD`: Database credentials
    - `SAML_*_CERT_PATH`: SAML certificate paths (if AUTH_DEV_BYPASS=false)

    **Validation Rules:**
    1. Production/Staging: Missing or default values → `ImproperlyConfigured` exception
    2. Development: Default values allowed but logged as warnings
    3. Placeholder detection: `CHANGE_*`, `<VARIABLE>`, `TODO:` patterns rejected

    **Implementation:**
    - Module: `core/startup_checks.py`
    - Entry point: `core/apps.CoreConfig.ready()`
    - Tests: `tests/security/test_soc1_compliance.py::TestSecretValidation`
    ```

- [x] Subtask 7.4: Créer guide de déploiement sécurisé
  - Créer `/Users/cyrille/Documents/Dev/test/docs/deployment/production-secrets-checklist.md`
  ```markdown
  # Production Secrets Checklist (Story 17.5)

  ## Pre-Deployment Validation

  ### Step 1: Generate Secrets
  ```bash
  # Django SECRET_KEY
  python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

  # JWT SECRET_KEY (minimum 32 caractères aléatoires)
  openssl rand -base64 32
  ```

  ### Step 2: Configure Environment File
  ```bash
  # Copier template
  cp .env.production.template /etc/idp/django.env

  # Remplacer placeholders
  vi /etc/idp/django.env
  ```

  ### Step 3: Validate Configuration
  ```bash
  # Vérifier aucun placeholder restant
  grep -E "CHANGE_|<[A-Z_]+>|TODO:" /etc/idp/django.env
  # Doit retourner vide

  # Vérifier variables critiques présentes
  grep -E "^SECRET_KEY=|^JWT_SECRET_KEY=|^ORACLE_PASSWORD=" /etc/idp/django.env
  # Doit afficher 3 lignes avec valeurs non-vides
  ```

  ### Step 4: Test Startup
  ```bash
  # Charger environnement
  export $(cat /etc/idp/django.env | grep -v '^#' | xargs)

  # Vérifier configuration Django
  python manage.py check --deploy

  # Démarrer application
  python manage.py runserver
  # Doit démarrer sans erreur et logger: "✓ Configuration des secrets validée"
  ```

  ## Post-Deployment Validation

  ### Health Check
  ```bash
  curl http://localhost:8000/api/v1/health
  # Expected: {"status": "healthy", "oracle": "connected", ...}
  ```

  ### Security Test
  ```bash
  # Vérifier AUTH_DEV_BYPASS désactivé
  grep "AUTH_DEV_BYPASS=true" /etc/idp/django.env
  # Doit retourner vide

  # Vérifier APP_ENV production
  grep "APP_ENV=production" /etc/idp/django.env
  # Doit retourner la ligne
  ```

  ## Troubleshooting

  ### Error: "SECRET_KEY is not set"
  - Cause: Variable SECRET_KEY absente ou vide
  - Fix: `export SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")`

  ### Error: "SECRET_KEY contains unreplaced placeholder"
  - Cause: Placeholder `CHANGE_SECRET` non remplacé
  - Fix: Remplacer par valeur générée (voir Step 1)

  ### Error: "SAML_SP_CERT_PATH required"
  - Cause: Certificat SAML manquant en production avec AUTH_DEV_BYPASS=false
  - Fix: Configurer chemins vers certificats ou activer AUTH_DEV_BYPASS=true (non recommandé en prod)
  ```

## Dev Notes

### Contexte Epic 17: Réduction dette technique
- **Epic 17.5** fait partie de l'Epic 17 "Réduction de la dette technique & amélioration qualité (audit 06/02/2026)"
- Scope Epic: Sécurité & Tooling - "Supprimer les secrets par défaut risquant de fuiter en prod et appliquer un fail-fast en environnement non-dev si variables manquantes"
- Definition of Done Epic: "Aucun secret 'par défaut' exploitable n'est présent ; démarrage refusé en non-dev si secrets non configurés"

### Architecture Compliance

**Pattern "Zero Credential Stocké" (PRD NFR21):**
- ✅ Vault obligatoire pour credentials d'exécution (déjà implémenté Story 4.2bis)
- ✅ Aucun secret applicatif en code source (hardcoded defaults supprimés)
- ✅ Fail-fast si Vault down → execution refusée (comportement existant conservé)

**Security Architecture (security-architecture.md):**
- Section "Secret Management" ligne 94-95: "Vault at runtime. Aucun secret en transit sauf entre Vault et plateforme cible"
- Pattern credential_ref: `integrations/models.py` ligne 73 utilise références Vault, pas plaintext
- Pre-commit hook detect-secrets: `.pre-commit-config.yaml` lignes 6-19 empêche commit de secrets

**Settings.py Structure:**
- Ligne 29: SECRET_KEY actuellement avec default `'django-insecure-...'` → RETIRER
- Ligne 104: ORACLE_PASSWORD actuellement avec default `'changeme'` → RETIRER
- Ligne 230: JWT_SECRET_KEY actuellement avec default `'change-me-in-production'` → RETIRER
- Ligne 240: AUTH_DEV_BYPASS = `os.getenv('AUTH_DEV_BYPASS', 'False').lower() == 'true'` → CONSERVER (correct)

### Library & Framework Requirements

**Django Core:**
- `django.core.exceptions.ImproperlyConfigured`: Exception standard pour erreurs de configuration
- `django.core.management.utils.get_random_secret_key`: Génération SECRET_KEY sécurisée

**Logging structuré:**
- `structlog`: Déjà utilisé dans `core/apps.py` ligne ~27-35 pour logging JSON
- Pattern: `logger.info("event_name", key=value, correlation_id=...)`

**Python Standard Library:**
- `os.getenv()`: Lecture variables environnement
- `re.compile()`: Pattern matching pour placeholders
- `unittest.mock.patch`: Tests avec environnement mocké

### File Structure Requirements

**Nouveaux fichiers:**
```
idp-portal/django_backend/
├── core/
│   ├── startup_checks.py          # NEW - Validation secrets au démarrage
│   └── tests/
│       └── test_startup_checks.py # NEW - Tests unitaires validation
├── tests/
│   ├── integration/
│   │   └── test_startup.py        # NEW - Tests intégration démarrage
│   └── security/
│       └── test_soc1_compliance.py # MODIFY - Ajouter TestSecretValidation
└── .env.development               # NEW - Config dev explicite
```

**Fichiers modifiés:**
```
idp-portal/
├── django_backend/
│   ├── idp_backend/settings.py    # MODIFY - Retirer defaults lignes 29, 104, 230
│   ├── core/apps.py               # MODIFY - Appeler validate_required_secrets()
│   └── README.md                  # MODIFY - Ajouter section secrets
├── .env.example                   # MODIFY - Ajouter SECRET_KEY, JWT_SECRET_KEY explicites
└── docs/
    ├── security/security-architecture.md  # MODIFY - Ajouter section Startup Validation
    └── deployment/production-secrets-checklist.md  # NEW - Guide déploiement
```

### Testing Requirements

**Coverage cible: 100% des fonctions de validation**
- `validate_required_secrets()`: 7 tests (missing, insecure, placeholder, SAML, valid, dev warnings, staging)
- `CoreConfig.ready()`: 2 tests intégration (production fail, dev success)
- Total: 9 tests minimum (AC#10)

**Frameworks de test:**
- `pytest`: Framework principal
- `pytest-django`: Fixtures Django
- `pytest-mock`: Mocking (déjà installé)
- `unittest.mock.patch`: Patch environnement

### Previous Story Intelligence

**Story 17.4 (Oracle JSON Field):**
- Status: done (2026-02-07)
- Impact: OracleJSONField custom field créé dans `core/fields.py`
- Learnings: Pattern de test robuste avec fixtures, validation optionnelle via paramètre
- Code review: 7 HIGH + 4 MEDIUM fixes appliqués, importance validation avant sérialisation

**Story 17.3 (API client duplication):**
- Status: done (2026-02-06)
- Impact: Helpers HTTP partagés dans `frontend/src/services/api_client.ts`
- Learnings: Élimination duplication code, pattern retry 401, centralisation parsing erreurs

**Story 17.1 (FastAPI decommissioning):**
- Status: done (2026-02-06)
- Impact: Backend FastAPI entièrement supprimé, Django seul backend
- Learnings: Importance tests de non-régression, vérification aucune référence legacy

**Story 15.3 (SOC1 compliance):**
- Status: done (2026-02-06)
- Impact: Tests conformité SOC1 dans `tests/security/test_soc1_compliance.py`
- Learnings: Validation immutabilité audit, chiffrement données sensibles, trigger V054
- Tests: 22 tests SOC1, rapport conformité généré

**Story M.7 (Auth & Security):**
- Status: done (2026-02-04)
- Impact: Middleware SAML, JWT, security headers, audit trail
- Learnings: Importance validation certificats SAML, gestion graceful degradation
- Code: `idp_auth/middleware.py`, `core/middleware.py` (SecurityHeadersMiddleware)

### Git Intelligence Summary

**Commits récents (2026-02-06 to 2026-02-07):**
- `02f2f70`: refactor(17.4) - OracleJSONField implementation
- `325f8f4`: refactor(17.3) - API client shared helpers
- `b778ea6`: refactor(17.2) - ExecutionWizard decomposition
- `e36098b`: feat(17.1) - FastAPI decommissioning complete

**Patterns observés:**
- Commits atomiques par story avec préfixe `feat()`, `refactor()`, `fix()`
- Code review systematic avec fixes appliqués avant done
- Tests coverage validation systématique (pytest report)
- Documentation mise à jour avec chaque story (README, architecture.md)

**Code patterns établis:**
- Logging structuré: `structlog.get_logger(__name__)` + événements nommés
- Validation paramètres: Lever `ValidationError` ou `ImproperlyConfigured`
- Tests: Fixtures pytest + `@override_settings` + `@patch` pour isolation
- Commentaires: `# Story XX.X - Description` pour traçabilité

### Project Context Reference

**Documentation critique:**
- `/Users/cyrille/Documents/Dev/test/_bmad-output/planning-artifacts/architecture.md`:
  - Ligne 79: "Zero credential stocké" - Vault obligatoire, aucun fallback
  - Ligne 94-95: "Sécurité des secrets" - Vault at runtime, aucun secret en transit
  - Ligne 52: NFR Sécurité - "TLS 1.2+, zero credential stocke, logs immutables"

- `/Users/cyrille/Documents/Dev/test/_bmad-output/planning-artifacts/epics.md`:
  - Ligne 3520: Epic 17 scope - "Supprimer les secrets par défaut risquant de fuiter en prod et appliquer un fail-fast"
  - Ligne 3531: DoD Epic 17 - "Aucun secret 'par défaut' exploitable n'est présent ; démarrage refusé en non-dev"

- `/Users/cyrille/Documents/Dev/test/docs/security/security-architecture.md`:
  - Section "Secret Management" - credential_ref pattern, Vault runtime, detect-secrets baseline

**Configuration actuelle:**
- `.env.example`: Contient placeholders mais pas SECRET_KEY/JWT_SECRET_KEY explicites
- `.env.production.template`: Contient placeholders `CHANGE_*` non validés
- `settings.py`: Hardcoded defaults pour SECRET_KEY, JWT_SECRET_KEY, ORACLE_PASSWORD

**Risques identifiés (analyse subagent a9ea498):**
- CRITICAL: SECRET_KEY hardcodé visible en source → session/cookie hijacking
- CRITICAL: JWT_SECRET_KEY hardcodé → JWT forgery, token impersonation
- CRITICAL: ORACLE_PASSWORD hardcodé → database compromise
- HIGH: Aucun fail-fast validation → production misconfigurée silencieusement

### Story Completion Status

**Status:** ready-for-dev

**Prochaines étapes après dev-story:**
1. Code review adversarial (`code-review` workflow)
2. Validation sécurité: Tester démarrage avec/sans secrets en prod simulée
3. Update sprint-status.yaml: `17-5-securiser-gestion-secrets: done`
4. Optional: Exécuter `automate` workflow TEA pour tests guardrails supplémentaires

**Critères de validation finale:**
- ✅ Tous tests passent (pytest 9+ tests minimum)
- ✅ Application refuse démarrage en production sans secrets
- ✅ Application démarre en dev avec warnings seulement
- ✅ Aucun secret hardcodé dans settings.py (`grep` returns empty)
- ✅ Documentation déploiement créée et validée
- ✅ Code review approuvé sans CRITICAL/HIGH bloquant

## Dev Agent Record

### Agent Model Used

claude-opus-4-6

### Debug Log References

- Aucun incident de debug pendant l'implémentation
- 1 test pré-existant en échec (test_health_check_servicenow_unreachable) - non lié à Story 17.5

### Completion Notes List

- ✅ Task 1: Audit confirmé - 3 secrets CRITICAL (SECRET_KEY, JWT_SECRET_KEY, ORACLE_PASSWORD) avec valeurs hardcodées, 3 SAML cert paths HIGH, aucune validation existante
- ✅ Task 2: Module `core/startup_checks.py` créé avec `validate_required_secrets()` - pattern fail-fast en non-dev, warnings en dev, détection placeholders CHANGE_*
- ✅ Task 3: Intégration dans `core/apps.py` via `CoreConfig.ready()` - validation appelée après structlog config
- ✅ Task 4: Suppression des 3 secrets hardcodés de settings.py (SECRET_KEY, JWT_SECRET_KEY, ORACLE_PASSWORD) - defaults vides avec fallback dev pour SECRET_KEY. test_settings.py mis à jour avec valeurs test-safe
- ✅ Task 5: `.env.development` créé avec valeurs dev explicites, `.env.example` mis à jour avec SECRET_KEY et JWT_SECRET_KEY
- ✅ Task 6: 21 tests créés (10 unitaires + 8 SOC1 compliance + 3 intégration) - tous passent
- ✅ Task 7: Documentation sécurité mise à jour (security-architecture.md section Startup Validation), guide déploiement production créé

### Change Log

- 2026-02-07: Story 17.5 - Sécurisation gestion secrets. Suppression secrets hardcodés, module validation fail-fast au démarrage, 21 tests, documentation déploiement

### File List

**Nouveaux fichiers:**
- `idp-portal/django_backend/core/startup_checks.py` - Module validation secrets au démarrage
- `idp-portal/django_backend/core/tests/test_startup_checks.py` - 10 tests unitaires validation
- `idp-portal/django_backend/tests/integration/test_startup.py` - 3 tests intégration démarrage
- `idp-portal/.env.development` - Configuration développement explicite
- `idp-portal/docs/production-secrets-checklist.md` - Guide déploiement sécurisé

**Fichiers modifiés:**
- `idp-portal/django_backend/idp_backend/settings.py` - Suppression defaults SECRET_KEY, JWT_SECRET_KEY, ORACLE_PASSWORD
- `idp-portal/django_backend/idp_backend/test_settings.py` - Ajout valeurs test-safe pour secrets
- `idp-portal/django_backend/core/apps.py` - Appel validate_required_secrets() dans ready()
- `idp-portal/django_backend/tests/security/test_soc1_compliance.py` - Ajout TestSecretValidation (8 tests)
- `idp-portal/.env.example` - Ajout SECRET_KEY, JWT_SECRET_KEY, mise à jour ORACLE_PASSWORD
- `idp-portal/docs/security-architecture.md` - Section Startup Secret Validation ajoutée
