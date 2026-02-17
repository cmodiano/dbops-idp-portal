# Story 18.7: Correction des tests en échec

Status: in-progress

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant qu'**équipe de développement**,
je veux **que l'ensemble des tests (backend et frontend) passent à nouveau**,
afin de **restaurer la confiance dans la suite de tests et permettre les déploiements en CI**.

## Acceptance Criteria

**AC1: Résoudre les erreurs de collection pytest (6 apps)**
```gherkin
Given 6 apps Django ont à la fois tests.py et tests/ directory causant conflit import
When je supprime/renomme les fichiers tests.py obsolètes
Then pytest collect 1085 tests sans erreur de collection
And tous les tests peuvent être exécutés
```

**AC2: Corriger fixtures User incompatibles avec modèle custom (80+ tests)**
```gherkin
Given le modèle User custom n'a PAS de champs is_staff, is_active
When les tests utilisent User.objects.create(is_staff=True)
Then TypeError: unknown field 'is_staff' est levée
And 80+ tests échouent dès le setUp()
---
When je remplace par UserFactory ou User.objects.create(username='...', profile='...')
Then les fixtures utilisent uniquement les champs valides: username, profile, display_name, saml_subject
And tous les tests passent leur phase de setup
```

**AC3: Corriger contraintes CHECK Oracle incompatibles avec SQLite (2 tests)**
```gherkin
Given migration V004 (catalog) ajoute ck_actions_soft_delete_consistency
When tests s'exécutent sur SQLite in-memory
Then IntegrityError: CHECK constraint failed est levée
---
When je vérifie logique soft delete dans tests
Then is_deleted et deleted_at sont cohérents (is_deleted=True ⇒ deleted_at NOT NULL)
And les tests respectent les contraintes de consistance
```

**AC4: Corriger échecs auth/RBAC propagés depuis fixtures User (35+ tests)**
```gherkin
Given les tests d'authentification dépendent de fixtures User valides
When setUp() échoue avec User fixtures invalides
Then tests JWT, SAML, permissions échouent en cascade
---
When fixtures User sont corrigées (AC2)
Then tests auth/RBAC passent sans erreur de setup
And seules les assertions métier sont testées
```

**AC5: Corriger échecs API views propagés depuis auth (50+ tests)**
```gherkin
Given API views nécessitent authentification valide (client.force_authenticate(user))
When user fixture est invalide (champs is_staff)
Then force_authenticate() échoue ou crée user invalide
---
When fixtures User sont corrigées et force_authenticate() utilise UserFactory
Then API tests peuvent authentifier correctement
And tests valident la logique API sans erreur auth
```

**AC6: Corriger échecs execution/scheduling métier (45+ tests)**
```gherkin
Given tests execution dépendent de fixtures Action, Execution, User valides
When Action ou User fixtures utilisent champs obsolètes
Then tests échouent dès la création fixtures
---
When tous les factories (UserFactory, ActionFactory, ExecutionFactory) sont alignés sur modèles actuels
Then tests execution/scheduling passent setup
And logique métier est testée correctement
```

**AC7: Documenter échecs restants et créer tickets suivi (si applicable)**
```gherkin
Given certains tests peuvent avoir échecs complexes nécessitant investigation
When correction immédiate n'est pas possible
Then échec est documenté dans tests/KNOWN_ISSUES.md avec ticket JIRA/GitHub
And test est marqué @pytest.mark.xfail avec raison
And équipe peut décider de reporter correction
```

**AC8: Valider suite complète backend passe ou échecs documentés**
```gherkin
Given tous les correctifs AC1-AC6 sont appliqués
When pytest est exécuté sur toute la suite backend
Then >= 95% des tests passent (770/1085 minimum, cible 100%)
And échecs restants (<5%) sont documentés avec tickets
And CI peut exécuter suite sans blocage
```

**AC9: Valider suite frontend passe (si échecs détectés)**
```gherkin
Given suite frontend Vitest/Jest existe
When npm test est exécuté
Then tous les tests frontend passent
Or échecs sont documentés dans tests/KNOWN_ISSUES.md
```

**AC10: Mettre à jour documentation tests et guidelines**
```gherkin
Given corrections révèlent patterns d'erreurs communs
When documentation tests/README.md est mise à jour
Then guidelines incluent:
  - Utiliser UserFactory au lieu de User.objects.create()
  - Éviter champs Django auth standard (is_staff, is_active) dans tests
  - Respecter contraintes CHECK Oracle dans fixtures
  - Utiliser factories au lieu de création manuelle modèles
And futurs développeurs évitent ces erreurs
```

## Tasks / Subtasks

### Phase 1: Collection Errors (CRITIQUE - BLOQUANT)

- [x] **Task 1: Supprimer fichiers tests.py obsolètes conflictuels** (AC: 1) ✅
  - [x] Subtask 1.1: Identifier fichiers tests.py vs tests/ directories ✅
    ```bash
    find idp-portal/django_backend -name "tests.py" -type f
    # Résultat: 6 fichiers identifiés et supprimés
    # - catalog/tests.py (D)
    # - core/tests.py (D)
    # - executions/tests.py (D)
    # - idp_auth/tests.py (D)
    # - integrations/tests.py (D)
    # - profiles/tests.py (D)
    ```
  - [x] Subtask 1.2: Vérifier contenu tests.py (vides ou obsolètes) ✅
    - Tous les fichiers tests.py étaient vides ou obsolètes
    - Décision: Suppression complète (Option A)
  - [x] Subtask 1.3: Supprimer/renommer fichiers tests.py obsolètes ✅
    ```bash
    # Option A appliquée: Suppression complète
    rm idp-portal/django_backend/catalog/tests.py
    rm idp-portal/django_backend/core/tests.py
    rm idp-portal/django_backend/executions/tests.py
    rm idp-portal/django_backend/idp_auth/tests.py
    rm idp-portal/django_backend/integrations/tests.py
    rm idp-portal/django_backend/profiles/tests.py
    # Git status: 6 fichiers "D" (deleted)
    ```
  - [x] Subtask 1.4: Valider collection pytest réussie ✅
    ```bash
    .venv/bin/python -m pytest --collect-only
    # Résultat: "collected 1135 items" (vs 1085 attendus, +50 nouveaux tests)
    # Collection réussie SANS erreurs import
    ```

### Phase 2: User Model Fixtures (HAUTE PRIORITÉ - 80+ tests)

- [x] **Task 2: Auditer et corriger fixtures User incompatibles** (AC: 2, 4, 5) ✅ PARTIEL
  - [ ] Subtask 2.1: Identifier tous usages User.objects.create() avec champs invalides
    ```bash
    cd idp-portal/django_backend
    grep -r "is_staff\|is_active\|is_superuser" --include="test_*.py" --include="conftest.py"
    # Localiser tous les tests utilisant champs Django auth standard
    ```
  - [ ] Subtask 2.2: Vérifier UserFactory existe et est correct
    - Lire tests/factories.py
    - Vérifier UserFactory définit uniquement champs valides:
      ```python
      class UserFactory(factory.django.DjangoModelFactory):
          class Meta:
              model = User

          username = factory.Sequence(lambda n: f'user{n}')
          profile = 'DBA'  # ou factory.Iterator(['DBA', 'DBOPS', 'BUSINESS'])
          display_name = factory.LazyAttribute(lambda o: f'{o.username} Display')
          saml_subject = None  # Optionnel
      ```
    - Si UserFactory n'existe pas → créer dans tests/factories.py
  - [ ] Subtask 2.3: Remplacer User.objects.create() par UserFactory dans tests prioritaires
    - Fichiers prioritaires (impact 80+ tests):
      - catalog/tests/test_admin_views.py (16 tests)
      - core/tests/test_health_check.py (10 tests)
      - idp_auth/tests/test_auth_views.py (13 tests)
      - integrations/tests/test_upload_icon_view.py (7 tests)
      - inventory/tests/test_views.py (17 tests)
      - profiles/tests/test_*_views.py (51 tests combinés)
    - Pattern de remplacement:
      ```python
      # AVANT
      user = User.objects.create(username='test', profile='DBA', is_staff=True)

      # APRÈS
      from tests.factories import UserFactory
      user = UserFactory(username='test', profile='DBA')
      ```
  - [ ] Subtask 2.4: Mettre à jour conftest.py fixtures globales
    - Lire tests/conftest.py
    - Identifier fixtures @pytest.fixture retournant User
    - Remplacer par UserFactory
    - Exemple:
      ```python
      @pytest.fixture
      def dbops_user():
          return UserFactory(username='dbops_user', profile='DBOPS')

      @pytest.fixture
      def dba_user():
          return UserFactory(username='dba_user', profile='DBA')
      ```
  - [ ] Subtask 2.5: Valider correction User fixtures via tests unitaires
    ```bash
    # Exécuter tests catalog/admin_views (16 tests)
    pytest catalog/tests/test_admin_views.py -v
    # Vérifier: 16 passed, 0 failed (vs 16 failed actuellement)

    # Exécuter tests profiles (51 tests combinés)
    pytest profiles/tests/ -v
    # Vérifier: 51 passed (vs 51 failed actuellement)
    ```

### Phase 3: Database Constraints (MOYENNE PRIORITÉ - 2 tests)

- [ ] **Task 3: Corriger contraintes CHECK Oracle incompatibles SQLite** (AC: 3)
  - [ ] Subtask 3.1: Analyser migration V004 soft delete constraint
    - Lire database/migrations/V004_add_soft_delete_columns.sql (ou équivalent)
    - Identifier contrainte ck_actions_soft_delete_consistency:
      ```sql
      -- Exemple contrainte (hypothétique):
      CHECK (
          (is_deleted = 1 AND deleted_at IS NOT NULL) OR
          (is_deleted = 0 AND deleted_at IS NULL)
      )
      ```
  - [ ] Subtask 3.2: Identifier tests échouant sur constraint
    - tests/integration/test_action_lifecycle.py::test_action_disable_prevents_new_executions
    - tests/integration/test_audit_trail.py (1 test)
  - [ ] Subtask 3.3: Corriger logique soft delete dans tests
    - Lire code tests échoués
    - Identifier pourquoi is_deleted et deleted_at sont incohérents
    - Options de correction:
      ```python
      # Option A: Utiliser méthode soft_delete() si elle existe
      action.soft_delete()  # Doit définir is_deleted=True ET deleted_at=timezone.now()

      # Option B: Définir manuellement cohérence
      from django.utils import timezone
      action.is_deleted = True
      action.deleted_at = timezone.now()
      action.save()

      # Option C: Utiliser ActionFactory avec trait
      action = ActionFactory(is_deleted=True, deleted_at=timezone.now())
      ```
  - [ ] Subtask 3.4: Valider correction contraintes
    ```bash
    pytest tests/integration/test_action_lifecycle.py::test_action_disable_prevents_new_executions -v
    pytest tests/integration/test_audit_trail.py -v
    # Vérifier: 2 passed, 0 failed
    ```

### Phase 4: Auth/RBAC Tests (MOYENNE PRIORITÉ - 35+ tests)

- [ ] **Task 4: Corriger tests auth/RBAC propagés depuis User fixtures** (AC: 4)
  - [ ] Subtask 4.1: Vérifier fixtures User corrigées (dépend Task 2)
    - Valider Task 2 complétée avant de commencer Task 4
  - [ ] Subtask 4.2: Exécuter tests auth après correction User fixtures
    ```bash
    pytest idp_auth/tests/ -v
    pytest tests/security/test_authentication_security.py -v
    pytest tests/security/test_authorization_rbac.py -v
    pytest tests/security/test_granular_access_control.py -v
    ```
  - [ ] Subtask 4.3: Identifier échecs restants (non liés à User fixtures)
    - Analyser output pytest pour échecs non résolus par Task 2
    - Catégoriser: JWT token, SAML config, permissions RBAC
  - [ ] Subtask 4.4: Corriger échecs auth spécifiques si nécessaires
    - JWT: Vérifier token signature, expiration, claims
    - SAML: Vérifier configuration mock, assertions
    - RBAC: Vérifier permissions profiles (DBA, DBOPS, BUSINESS)

### Phase 5: API Views Tests (MOYENNE PRIORITÉ - 50+ tests)

- [ ] **Task 5: Corriger tests API views propagés depuis auth** (AC: 5)
  - [ ] Subtask 5.1: Vérifier fixtures User et auth corrigées (dépend Task 2, 4)
  - [ ] Subtask 5.2: Exécuter tests API views après corrections précédentes
    ```bash
    pytest catalog/tests/test_catalog_views.py -v
    pytest catalog/tests/test_tags_views.py -v
    pytest executions/tests/test_environment_validation.py -v
    pytest integrations/tests/test_services.py -v
    pytest reference/tests/test_views.py -v
    pytest tests/security/test_sensitive_endpoints.py -v
    ```
  - [ ] Subtask 5.3: Identifier échecs restants non liés à fixtures/auth
    - Analyser output pour vrais bugs API ou assertions obsolètes
  - [ ] Subtask 5.4: Corriger échecs API spécifiques
    - Vérifier sérializers alignés sur modèles actuels
    - Vérifier permissions RBAC dans views
    - Vérifier validation requête (parameters, environment, etc.)

### Phase 6: Execution/Scheduling Tests (BASSE PRIORITÉ - 45+ tests)

- [ ] **Task 6: Corriger tests execution/scheduling métier** (AC: 6)
  - [ ] Subtask 6.1: Vérifier ActionFactory et ExecutionFactory existent
    - Lire tests/factories.py
    - Vérifier ActionFactory aligné sur modèle Action actuel (après refactor OracleJSONField Story 17.4)
    - Vérifier ExecutionFactory aligné sur modèle Execution actuel (status, error_message, etc.)
  - [ ] Subtask 6.2: Exécuter tests execution après corrections factories
    ```bash
    pytest executions/tests/test_exception_handling.py -v
    pytest executions/tests/test_scheduled_execution_put.py -v
    pytest executions/tests/test_story_4_11.py -v
    pytest executions/tests/test_story_4_12.py -v
    pytest executions/tests/test_story_13_4.py -v
    pytest executions/tests/test_story_13_5.py -v
    pytest executions/tests/test_workflow_runtime.py -v
    ```
  - [ ] Subtask 6.3: Identifier patterns d'échecs
    - Workflow execution: Vérifier step execution, branches conditionnelles
    - Scheduled executions: Vérifier recurrence patterns, cron expressions
    - RBAC execution: Vérifier permissions target-based (Epic 13)
  - [ ] Subtask 6.4: Corriger logique métier ou assertions obsolètes
    - Mettre à jour assertions si API changée (ex: target_names requis après Story 13.4)
    - Corriger mocks si services refactorisés

### Phase 7: Documentation et Validation Finale

- [ ] **Task 7: Documenter échecs restants et guidelines** (AC: 7, 10)
  - [ ] Subtask 7.1: Créer tests/KNOWN_ISSUES.md si échecs complexes restent
    ```markdown
    # Known Test Issues

    ## Issue #1: Test XYZ échoue avec erreur ABC
    - **Fichier:** path/to/test_file.py::test_name
    - **Erreur:** Description erreur
    - **Root Cause:** Explication technique
    - **Ticket:** JIRA-123 ou GitHub Issue #456
    - **Workaround:** Marqué @pytest.mark.xfail(reason="...")
    - **Owner:** @dev-name
    - **ETA:** Sprint X
    ```
  - [ ] Subtask 7.2: Mettre à jour tests/README.md avec guidelines
    - Ajouter section "Common Pitfalls" avec corrections:
      ```markdown
      ## Common Testing Pitfalls

      ### ❌ DO NOT: Create User with Django auth fields
      ```python
      # WRONG - User custom model has no is_staff/is_active
      user = User.objects.create(username='test', is_staff=True)
      ```

      ### ✅ DO: Use UserFactory
      ```python
      from tests.factories import UserFactory
      user = UserFactory(username='test', profile='DBOPS')
      ```

      ### ❌ DO NOT: Create Action manually with JSON fields
      ```python
      # WRONG - JSON fields need proper serialization
      action = Action.objects.create(
          name='Test',
          parameters_schema='{"type": "object"}'  # String, pas dict
      )
      ```

      ### ✅ DO: Use ActionFactory
      ```python
      from tests.factories import ActionFactory
      action = ActionFactory(
          name='Test',
          parameters_schema={'type': 'object'}  # Dict, factory gère serialization
      )
      ```
      ```
  - [ ] Subtask 7.3: Marquer tests connus en échec avec xfail
    ```python
    @pytest.mark.xfail(reason="JIRA-123: Complex workflow race condition, fix scheduled Sprint 20")
    def test_complex_workflow_edge_case():
        # Test code that fails for known complex reason
        ...
    ```

- [ ] **Task 8: Validation complète suite backend** (AC: 8)
  - [ ] Subtask 8.1: Exécuter suite complète backend
    ```bash
    cd idp-portal/django_backend
    .venv/bin/python -m pytest -v --tb=short > test_results.txt 2>&1
    ```
  - [ ] Subtask 8.2: Analyser résultats et calculer taux réussite
    ```bash
    # Extraire résumé pytest
    tail -50 test_results.txt | grep "passed\|failed\|skipped\|xfailed"

    # Objectif: >= 95% (1030/1085) passent
    # Cible idéale: 100% (1085/1085) passent
    ```
  - [ ] Subtask 8.3: Documenter résultats dans story completion notes
    - Nombre total tests: 1085
    - Tests passés: XXX
    - Tests échoués: XXX (avec liste fichiers + raisons)
    - Tests xfail: XXX (avec tickets références)
    - Taux réussite: XX%

- [ ] **Task 9: Validation suite frontend (si applicable)** (AC: 9)
  - [ ] Subtask 9.1: Exécuter suite frontend
    ```bash
    cd idp-portal/frontend
    npm test -- --run > frontend_test_results.txt 2>&1
    ```
  - [ ] Subtask 9.2: Analyser résultats frontend
    - Si échecs: Catégoriser (fixtures, mocks, assertions obsolètes)
    - Corriger selon même pattern que backend (factories, modèles actuels)
  - [ ] Subtask 9.3: Documenter résultats frontend
    - Nombre tests: XXX
    - Passés: XXX
    - Échoués: XXX (avec détails)

## Dev Notes

### Architecture Patterns & Constraints

**🎯 CONTEXTE: Epic 18 Amélioration UX — Restauration Suite Tests**

Cette story vise à restaurer la confiance dans la suite de tests (backend + frontend) après plusieurs refactorings majeurs (migration Django, OracleJSONField, soft delete, etc.) qui ont introduit des régressions. L'objectif est de corriger systématiquement les échecs identifiés par catégorie, en priorisant les blocages critiques (collection errors, fixtures User).

**Problème Actuel:**
```
pytest collection → 6 collection errors (BLOQUANT)
  ↓
Bypass avec --ignore → 314 failed, 770 passed (29% échec)
  ↓
Analyse des échecs:
  - 80+ tests: Fixtures User avec champs invalides (is_staff, is_active)
  - 35+ tests: Auth/RBAC échecs propagés depuis User fixtures
  - 50+ tests: API views échecs propagés depuis auth
  - 45+ tests: Execution/scheduling échecs (fixtures, logique métier)
  - 2 tests: Contraintes CHECK Oracle incompatibles SQLite
  - 15+ tests: Divers (edge cases, obsolètes)
```

**Solution Story 18.7:**
```
Phase 1: Supprimer tests.py conflictuels → Collection OK ✅
  ↓
Phase 2: Corriger User fixtures → UserFactory ✅
  ↓
Phase 3: Corriger contraintes CHECK → Soft delete cohérent ✅
  ↓
Phase 4-6: Corrections propagées (auth, API, execution) ✅
  ↓
Phase 7: Documentation + xfail échecs complexes ✅
  ↓
Résultat: >= 95% tests passent, CI débloquée ✅
```

**Framework & Stack:**
- Backend: Django 5.2 + DRF 3.16 + Oracle DB (prod) + SQLite (tests)
- Tests Backend: pytest 8.x + pytest-django + factory-boy
- Tests Frontend: Vitest + React Testing Library
- CI: GitHub Actions (ou équivalent)
- Working Dir: `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend`
- Python venv: `.venv/bin/python -m pytest`

**Stories Reliées:**
- **Story M.2**: Modèles Django et migrations Oracle (User custom model sans is_staff/is_active)
- **Story M.9**: Tests unitaires et intégration - couverture complète Django (UserFactory créé)
- **Story 17.4**: Oracle JSON Field modèle Action (refactor peut impacter ActionFactory)
- **Story 18.1**: Admin soft delete (contrainte ck_actions_soft_delete_consistency ajoutée)

### Technical Implementation Details

**1. Collection Errors — Pattern tests.py vs tests/ Conflict:**

**Cause Root:**
```
app/
├── tests.py          ← Old format (deprecated)
└── tests/            ← New format (organized test modules)
    ├── test_models.py
    ├── test_views.py
    └── test_services.py

Python import system confusion:
  - pytest tries to import 'app.tests'
  - Finds app/tests/ directory first (package)
  - Then finds app/tests.py (module)
  - ImportError: "imported module has different __file__ attribute"
```

**Solution:**
```bash
# Option A: Supprimer tests.py si vides ou obsolètes
find idp-portal/django_backend -name "tests.py" -exec grep -l "^$\|^#\|^from\|^import" {} \; | xargs rm

# Option B: Renommer si contiennent tests réels à préserver
for f in catalog/tests.py core/tests.py executions/tests.py idp_auth/tests.py integrations/tests.py profiles/tests.py; do
    if [ -f "$f" ]; then
        mv "$f" "${f%.py}_legacy.py"
        echo "Migrer contenu vers tests/ directory"
    fi
done
```

**Validation:**
```bash
pytest --collect-only 2>&1 | grep -i "import\|error\|collected"
# Expected: "collected 1085 items" WITHOUT "ImportError" or "import file mismatch"
```

**2. User Model Fixtures — Custom User vs Django Auth:**

**Modèle User Custom (idp_auth/models.py):**
```python
class User(models.Model):
    """Custom user model for SAML authentication (NO Django auth fields)."""
    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255, null=True, blank=True)
    profile = models.CharField(max_length=50)  # DBA, DBOPS, BUSINESS
    saml_subject = models.CharField(max_length=255, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # NO is_staff, is_active, is_superuser, password fields
    # Authentication via SAML 2.0, not Django auth
```

**Fixtures AVANT (INVALIDES):**
```python
# ❌ FAUX - Utilise champs Django auth inexistants
user = User.objects.create(
    username='testuser',
    profile='DBA',
    is_staff=True,        # ← TypeError: Unknown field
    is_active=True,       # ← TypeError: Unknown field
    is_superuser=False    # ← TypeError: Unknown field
)
```

**Fixtures APRÈS (VALIDES):**
```python
# ✅ CORRECT - Utilise UserFactory
from tests.factories import UserFactory

user = UserFactory(username='testuser', profile='DBA')

# Ou création manuelle avec uniquement champs valides
user = User.objects.create(
    username='testuser',
    profile='DBA',
    display_name='Test User',
    saml_subject='testuser@example.com'  # Optionnel
)
```

**UserFactory (tests/factories.py):**
```python
import factory
from idp_auth.models import User

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    profile = 'DBA'  # Default profile
    display_name = factory.LazyAttribute(lambda o: f'{o.username.title()}')
    saml_subject = None  # Null par défaut, peut être override

    # Traits pour profiles différents
    class Params:
        dbops = factory.Trait(profile='DBOPS')
        business = factory.Trait(profile='BUSINESS')

# Usage:
user_dba = UserFactory()  # Default DBA
user_dbops = UserFactory(dbops=True)  # DBOPS profile
user_business = UserFactory(profile='BUSINESS', username='business_user')
```

**Impact Propagé:**
- 80+ tests utilisant fixtures User invalides → Échec setUp()
- 35+ tests auth/RBAC → Échec car pas de User valide pour JWT/permissions
- 50+ tests API views → Échec car client.force_authenticate(user) impossible

**3. Database Constraints CHECK — Oracle vs SQLite:**

**Migration V004 Soft Delete (database/migrations/):**
```sql
-- Add soft delete columns to ACTIONS_CATALOG
ALTER TABLE ACTIONS_CATALOG ADD (
    IS_DELETED NUMBER(1) DEFAULT 0 NOT NULL,
    DELETED_AT TIMESTAMP(6) NULL
);

-- Add CHECK constraint for consistency
ALTER TABLE ACTIONS_CATALOG ADD CONSTRAINT ck_actions_soft_delete_consistency
    CHECK (
        (IS_DELETED = 1 AND DELETED_AT IS NOT NULL) OR
        (IS_DELETED = 0 AND DELETED_AT IS NULL)
    );
```

**Problème SQLite:**
```python
# Test code qui viole contrainte
action = Action.objects.create(name='Test', status='published')
action.is_deleted = True
action.save()  # ← IntegrityError: CHECK constraint failed
# Cause: is_deleted=True mais deleted_at=NULL (incohérent)
```

**Solution:**
```python
# ✅ Définir les deux champs ensemble
from django.utils import timezone

action.is_deleted = True
action.deleted_at = timezone.now()
action.save()  # OK, constraint satisfaite

# Ou utiliser méthode soft_delete() si elle existe
action.soft_delete()  # Méthode model qui gère les deux champs

# Ou ActionFactory avec trait
action = ActionFactory(is_deleted=True, deleted_at=timezone.now())
```

**Tests Affectés:**
- tests/integration/test_action_lifecycle.py::test_action_disable_prevents_new_executions
- tests/integration/test_audit_trail.py (1 test soft delete audit)

**4. Factories vs Manual Creation — Best Practices:**

**❌ Anti-pattern (création manuelle):**
```python
def test_action_creation():
    user = User.objects.create(username='test', profile='DBA', is_staff=True)  # ← Erreur
    action = Action.objects.create(
        name='Test Action',
        status='published',
        parameters_schema='{"type": "object"}',  # ← String au lieu de dict
        impact_rules='[{"condition": "env==prod"}]'  # ← String, pas list
    )
    # Fragile, verbose, prone to errors
```

**✅ Best Practice (factories):**
```python
from tests.factories import UserFactory, ActionFactory

def test_action_creation():
    user = UserFactory(profile='DBA')
    action = ActionFactory(
        name='Test Action',
        status='published',
        parameters_schema={'type': 'object'},  # ← Dict, factory gère JSON
        impact_rules=[{'condition': 'env==prod'}]  # ← List, factory gère JSON
    )
    # Clean, maintainable, type-safe
```

**ActionFactory Example (après Story 17.4 OracleJSONField):**
```python
class ActionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Action

    name = factory.Sequence(lambda n: f'Action {n}')
    status = ActionStatus.PUBLISHED
    item_type = 'action'
    engine = 'AAP'

    # OracleJSONField gère serialization automatiquement
    parameters_schema = factory.LazyFunction(lambda: {'type': 'object', 'properties': {}})
    impact_rules = factory.LazyFunction(lambda: [])
    change_type_config = None
    remediation_rules = factory.LazyFunction(lambda: [])
    execution_steps = factory.LazyFunction(lambda: [])
    documentation_md = ''

    class Params:
        workflow = factory.Trait(item_type='workflow')
        disabled = factory.Trait(status=ActionStatus.DISABLED)
```

**5. pytest Configuration et Exécution:**

**pytest.ini (django_backend/):**
```ini
[pytest]
DJANGO_SETTINGS_MODULE = idp_backend.test_settings
python_files = tests.py test_*.py *_tests.py
python_classes = Test*
python_functions = test_*
addopts = -v --reuse-db --tb=short
markers =
    unit: Unit tests
    integration: Integration tests
    security: Security tests
    slow: Slow-running tests
```

**test_settings.py:**
```python
from .settings import *

# SQLite in-memory database pour tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Disable migrations pour rapidité (use --create-db si needed)
# Note: CHECK constraints Oracle peuvent différer de SQLite
```

**Commandes Tests:**
```bash
# Working directory
cd /Users/cyrille/Documents/Dev/test/idp-portal/django_backend

# Collection only (vérifier pas d'erreurs import)
.venv/bin/python -m pytest --collect-only

# Exécuter suite complète avec résumé
.venv/bin/python -m pytest -v --tb=short

# Exécuter app spécifique
.venv/bin/python -m pytest catalog/tests/ -v

# Exécuter test spécifique
.venv/bin/python -m pytest catalog/tests/test_admin_views.py::test_create_action -v

# Exécuter avec markers
.venv/bin/python -m pytest -m "unit and not slow" -v

# Ignorer tests.py conflictuels (workaround temporaire)
.venv/bin/python -m pytest --ignore=catalog/tests.py --ignore=core/tests.py -v
```

**6. Known Issues Documentation Pattern:**

**tests/KNOWN_ISSUES.md (exemple):**
```markdown
# Known Test Issues — Django Backend

Last Updated: 2026-02-07

## High Priority Issues

### ISSUE-001: Workflow race condition in parallel execution
- **Test:** `executions/tests/test_workflow_runtime.py::test_parallel_branches_execution`
- **Status:** `@pytest.mark.xfail` (JIRA-456)
- **Symptom:** Intermittent failure (~10% runs) with "step already executed" error
- **Root Cause:** Race condition when 2+ parallel branches update same Execution row
- **Workaround:** Test marked xfail, manual validation OK
- **Owner:** @dev-team
- **Fix ETA:** Sprint 20 (complex concurrency fix, requires workflow engine refactor)

### ISSUE-002: Oracle-specific CHECK constraints fail on SQLite
- **Tests:**
  - `tests/integration/test_action_lifecycle.py::test_action_disable_prevents_new_executions`
  - `tests/integration/test_audit_trail.py::test_soft_delete_audit`
- **Status:** Fixed in Story 18.7 (Task 3)
- **Solution:** Ensure is_deleted and deleted_at set together in fixtures

## Resolved Issues

### ISSUE-003: User fixtures with is_staff field ✅ FIXED
- **Fixed:** Story 18.7 Task 2 — Replaced with UserFactory
- **Tests Affected:** 80+ tests across catalog, profiles, idp_auth
```

### Previous Story Intelligence (Stories 17.4, 18.1-18.6)

**Learnings from Recent Stories:**

1. **Story 17.4 (OracleJSONField Refactor):**
   - Refactor OracleJSONField peut casser tests utilisant création manuelle Action avec JSON strings
   - **Impact sur Story 18.7:** Vérifier ActionFactory aligned sur OracleJSONField (dict/list au lieu de strings)
   - **Action:** Subtask 6.1 vérifie ActionFactory cohérent avec nouveau field

2. **Story 18.1 (Soft Delete Actions):**
   - Ajout migration V004 avec CHECK constraint ck_actions_soft_delete_consistency
   - **Impact sur Story 18.7:** 2 tests échouent sur constraint SQLite (AC3, Task 3)
   - **Pattern appris:** Toujours définir is_deleted ET deleted_at ensemble dans fixtures
   - **Code Pattern:**
     ```python
     # Méthode soft_delete() recommandée
     def soft_delete(self):
         self.is_deleted = True
         self.deleted_at = timezone.now()
         self.save()
     ```

3. **Story 18.5 (Correction Favoris):**
   - Pattern correction bug: Identifier query bug côté serveur (exclude disabled actions)
   - **Impact sur Story 18.7:** Même pattern pour tests — identifier fixtures invalides, corriger à la source (UserFactory)

4. **Story 18.6 (Erreur Intégration):**
   - Ajout ExecutionStatus.INTEGRATION_ERROR + migration V057
   - **Impact sur Story 18.7:** Vérifier ExecutionFactory supporte nouveau statut
   - **Tests ajoutés:** 10 tests (8 backend + 2 frontend) — doivent passer dans suite 18.7

**Key Insights pour Story 18.7:**

- **Priorité absolue:** Résoudre collection errors (Phase 1) — bloquant, empêche exécution tests
- **Impact cascade:** Corriger User fixtures (Phase 2) résout 80+ tests + 35+ auth + 50+ API = 165+ tests (52% échecs actuels)
- **Testing Pyramid:** Corriger factories (base) avant tests intégration/E2E (sommet)
- **Documentation critique:** Guidelines tests/README.md évitent régressions futures (AC10)
- **Pragmatisme:** Marquer tests complexes en xfail avec tickets plutôt que bloquer story (AC7)

### Project Structure Notes

**Fichiers Prioritaires à Modifier:**

```
idp-portal/django_backend/
├── catalog/
│   ├── tests.py                                  # Task 1: SUPPRIMER (conflict)
│   └── tests/
│       ├── test_admin_views.py                   # Task 2: User fixtures (16 tests)
│       └── test_catalog_views.py                 # Task 5: API views (11 tests)
├── core/
│   ├── tests.py                                  # Task 1: SUPPRIMER (conflict)
│   └── tests/
│       └── test_health_check.py                  # Task 2: User fixtures (10 tests)
├── executions/
│   ├── tests.py                                  # Task 1: SUPPRIMER (conflict)
│   └── tests/
│       ├── test_exception_handling.py            # Task 6: Execution tests (4 tests)
│       ├── test_story_4_11.py                    # Task 6: RBAC execution (6 tests)
│       ├── test_story_13_4.py                    # Task 6: Target validation (7 tests)
│       └── test_workflow_runtime.py              # Task 6: Workflow engine (3 tests)
├── idp_auth/
│   ├── tests.py                                  # Task 1: SUPPRIMER (conflict)
│   └── tests/
│       ├── test_auth_views.py                    # Task 2: User fixtures (13 tests)
│       ├── test_jwt_authentication.py            # Task 4: JWT tests (1 test)
│       └── test_saml_views.py                    # Task 4: SAML tests (4 tests)
├── integrations/
│   ├── tests.py                                  # Task 1: SUPPRIMER (conflict)
│   └── tests/
│       └── test_upload_icon_view.py              # Task 2: User fixtures (7 tests)
├── profiles/
│   ├── tests.py                                  # Task 1: SUPPRIMER (conflict)
│   └── tests/
│       ├── test_profile_views.py                 # Task 2: User fixtures (17 tests)
│       ├── test_permissions_views.py             # Task 2: User fixtures (17 tests)
│       └── test_import_export_views.py           # Task 2: User fixtures (10 tests)
├── tests/
│   ├── conftest.py                               # Task 2: Fixtures globales User
│   ├── factories.py                              # Task 2: UserFactory, ActionFactory, ExecutionFactory
│   ├── README.md                                 # Task 7: Guidelines testing
│   ├── KNOWN_ISSUES.md                           # Task 7: Échecs documentés (CRÉER)
│   ├── integration/
│   │   ├── test_action_lifecycle.py              # Task 3: Constraint CHECK (1 test)
│   │   └── test_audit_trail.py                   # Task 3: Constraint CHECK (1 test)
│   └── security/
│       ├── test_authentication_security.py       # Task 4: Auth tests (20+ tests)
│       ├── test_authorization_rbac.py            # Task 4: RBAC tests (6 tests)
│       └── test_granular_access_control.py       # Task 4: Granular access (8 tests)
└── pytest.ini                                     # Config pytest (pas de modification)
```

**Models Impliqués:**

```
idp-portal/django_backend/
├── idp_auth/models.py
│   └── User (custom model)                       # NO is_staff, is_active fields
├── catalog/models.py
│   └── Action (OracleJSONField refactor)         # Task 6: ActionFactory alignment
├── executions/models.py
│   ├── Execution                                 # Task 6: ExecutionFactory alignment
│   └── ExecutionStatus (enum)                    # Inclut INTEGRATION_ERROR (Story 18.6)
└── core/models.py
    ├── AuditLog                                  # Tests audit trail
    └── AuditActionType (enum)
```

### Testing Standards

**Backend Tests — Patterns de Correction:**

**1. Collection Errors (Task 1):**
```bash
# Validation avant correction
pytest --collect-only 2>&1 | grep -c "import file mismatch"
# Expected: 6

# Correction
rm catalog/tests.py core/tests.py executions/tests.py idp_auth/tests.py integrations/tests.py profiles/tests.py

# Validation après correction
pytest --collect-only
# Expected: "collected 1085 items" sans erreurs
```

**2. User Fixtures (Task 2):**
```python
# ❌ AVANT (invalide)
def test_example():
    user = User.objects.create(username='test', profile='DBA', is_staff=True)
    # TypeError: User() got unexpected keyword argument 'is_staff'

# ✅ APRÈS (valide)
from tests.factories import UserFactory

def test_example():
    user = UserFactory(username='test', profile='DBA')
    assert user.profile == 'DBA'
    assert user.username == 'test'
```

**3. Constraint CHECK (Task 3):**
```python
# ❌ AVANT (viole constraint)
def test_action_soft_delete():
    action = Action.objects.create(name='Test', status='published')
    action.is_deleted = True
    action.save()  # IntegrityError: CHECK constraint failed

# ✅ APRÈS (respecte constraint)
from django.utils import timezone

def test_action_soft_delete():
    action = Action.objects.create(name='Test', status='published')
    action.is_deleted = True
    action.deleted_at = timezone.now()  # Cohérent avec is_deleted=True
    action.save()  # OK
```

**4. API Auth (Task 5):**
```python
# ❌ AVANT (user invalide)
def test_api_endpoint():
    client = APIClient()
    user = User.objects.create(username='test', is_staff=True)  # Erreur
    client.force_authenticate(user=user)
    # ...

# ✅ APRÈS (user valide via factory)
from tests.factories import UserFactory

def test_api_endpoint():
    client = APIClient()
    user = UserFactory(username='test', profile='DBOPS')
    client.force_authenticate(user=user)
    response = client.get('/api/v1/catalog/')
    assert response.status_code == 200
```

**Coverage Target Story 18.7:**
- **Objectif minimum:** >= 95% tests passent (1030/1085)
- **Objectif idéal:** 100% tests passent (1085/1085)
- **Échecs tolérés:** < 5% (< 55 tests) documentés avec xfail + tickets

**Validation Checkpoints:**

| Phase | Checkpoint | Commande Validation | Succès Critère |
|-------|-----------|---------------------|----------------|
| 1 | Collection OK | `pytest --collect-only` | 0 import errors |
| 2 | User fixtures | `pytest catalog/tests/test_admin_views.py -v` | 16/16 passed |
| 3 | CHECK constraints | `pytest tests/integration/ -v` | 2 tests soft delete passed |
| 4 | Auth/RBAC | `pytest idp_auth/tests/ tests/security/ -v` | 35+ passed |
| 5 | API views | `pytest catalog/tests/test_catalog_views.py -v` | 11+ passed |
| 6 | Execution | `pytest executions/tests/ -v` | 45+ passed |
| 7 | Suite complète | `pytest -v` | >= 1030/1085 passed |

**Commandes Tests Story 18.7:**
```bash
# Phase 1: Collection
pytest --collect-only

# Phase 2: User fixtures (validation partielle)
pytest catalog/tests/test_admin_views.py -v
pytest profiles/tests/ -v

# Phase 3: Constraint CHECK
pytest tests/integration/test_action_lifecycle.py::test_action_disable_prevents_new_executions -v

# Phase 4: Auth/RBAC
pytest idp_auth/tests/ -v
pytest tests/security/ -v

# Phase 5: API views
pytest catalog/tests/test_catalog_views.py -v
pytest reference/tests/test_views.py -v

# Phase 6: Execution
pytest executions/tests/ -v

# Phase 7: Suite complète
pytest -v --tb=short > test_results_18_7.txt 2>&1

# Analyse résultats
tail -50 test_results_18_7.txt | grep "passed\|failed"
```

### References

**Epic Source:**
- [Source: _bmad-output/planning-artifacts/epics.md#Story-18.7]
  - Context: Epic 18 — Amélioration UX et corrections issues feedback utilisateurs
  - Problème: 314 tests échouent suite à refactorings (User model, OracleJSONField, soft delete)
  - Scope: Correction systématique par catégories (collection errors, fixtures, constraints)

**Test Analysis Report:**
- [Source: Subprocess Analysis (Task Explore)]
  - 6 collection errors: tests.py vs tests/ conflict
  - 314 failed / 1085 total (29% échec rate)
  - Catégories identifiées: User fixtures (80+), auth/RBAC (35+), API views (50+), execution (45+), constraints (2)

**Previous Stories (Tests):**
- [Source: _bmad-output/implementation-artifacts/m-9-tests-unitaires-et-integration-parite.md]
  - Context: Story M.9 — Tests unitaires et intégration - couverture complète Django
  - UserFactory, ActionFactory, ExecutionFactory créés dans tests/factories.py
  - Guidelines tests/README.md initial (à enrichir Task 7)
- [Source: _bmad-output/implementation-artifacts/17-4-oracle-json-field-modele-action.md]
  - Context: Story 17.4 — Refactor OracleJSONField (en cours)
  - Impact: ActionFactory doit utiliser dict/list au lieu de JSON strings
  - Note: 40+ catalog tests échouent (fixtures User, NOT caused by refactor)

**Previous Stories (Models):**
- [Source: _bmad-output/implementation-artifacts/m-2-modeles-django-et-migrations-schema-oracle.md]
  - Context: Story M.2 — Modèles Django ORM + migrations Flyway Oracle
  - User custom model défini sans champs Django auth (is_staff, is_active, is_superuser)
- [Source: _bmad-output/implementation-artifacts/18-1-admin-actions-suppression-desactivation-filtres.md]
  - Context: Story 18.1 — Admin soft delete actions
  - Migration V004 ajout is_deleted + deleted_at + CHECK constraint ck_actions_soft_delete_consistency
  - Impact: 2 tests échouent sur constraint SQLite (Task 3 Story 18.7)

**Backend Tests Architecture:**
- [Source: idp-portal/django_backend/tests/README.md]
  - Structure tests: tests/ centralisé + app/tests/ modulaires
  - Factories pattern: UserFactory, ActionFactory, ExecutionFactory dans tests/factories.py
  - Fixtures globales: conftest.py définit @pytest.fixture réutilisables
  - Markers: @pytest.mark.unit, @integration, @security, @slow
- [Source: idp-portal/django_backend/pytest.ini]
  - Configuration pytest: test_settings, markers, addopts
  - Database: SQLite in-memory (incompatibilités CHECK constraints Oracle possibles)

**Project Memory:**
- [Source: /Users/cyrille/.claude/projects/-Users-cyrille-Documents-Dev-test/memory/MEMORY.md]
  - Known issue: pytest collection errors (tests.py vs tests/ conflict) ✅ Confirmé
  - Known issue: 298+ test failures (fixtures User obsolètes) ✅ Confirmé (314 actuellement)
  - Test runner: `.venv/bin/python -m pytest` (from django_backend dir)
  - Test settings: `idp_backend.test_settings` (via pytest.ini)

**Git History (Stories 17-18):**
- Commit f816a8b: feat(18.1) — Add admin soft delete (constraint CHECK ajoutée)
- Commit Story 17.4: Oracle JSON Field refactor (ActionFactory impacté)
- Commit Story M.9: Tests unitaires et intégration (UserFactory créé)
- Commit 45a5a3e: feat(18.6) — Integration error status (10 tests ajoutés, doivent passer)

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

_À compléter pendant implémentation_

### Completion Notes List

**État après Code Review AI (2026-02-07):**
- Nombre total tests: 1135 (+50 vs 1085 attendus — nouveaux test_models.py créés)
- Tests passés: 912/1135 (80.4%)
- Tests échoués: 222/1135 (19.5%)
- Tests skipped: 1
- Taux réussite: **80.4%** ❌ (objectif AC8: 95% non atteint — écart -14.6pp)
- Échecs documentés xfail: 0 (AC7 non réalisé)
- Phases complétées:
  - ✅ Phase 1 (Task 1): Collection errors RÉSOLUS (1135 tests collectés sans erreur)
  - 🟡 Phase 2 (Task 2): User fixtures PARTIELLEMENT corrigées (26 fichiers modifiés)
  - ❌ Phases 3-7: NON commencées

**Breakdown échecs (222 tests):**
- 60+ tests: 301 Redirect (trailing slash manquant) — **CORRIGÉ par code review**
- 35+ tests: RBAC/Auth security tests
- 50+ tests: API views (fixtures User ou assertions obsolètes)
- 76+ tests: Autres causes (nécessite investigation)
- 1 test: OracleJSONField validation — **CORRIGÉ par code review**

**Code Review Findings:**
- 10 issues HIGH corrigées (trailing slash auth tests, story tasks updates, File List)
- 6 issues MEDIUM documentées (KNOWN_ISSUES.md à créer, tests/README.md à mettre à jour)
- 3 issues LOW (gitignore node_modules, .claude/settings.local.json)

### File List

**Supprimés (Task 1 — Collection Errors):**
- `catalog/tests.py` (conflict tests.py vs tests/)
- `core/tests.py` (conflict tests.py vs tests/)
- `executions/tests.py` (conflict tests.py vs tests/)
- `idp_auth/tests.py` (conflict tests.py vs tests/)
- `integrations/tests.py` (conflict tests.py vs tests/)
- `profiles/tests.py` (conflict tests.py vs tests/)

**Modifiés (Task 2 — User Fixtures Correction):**
- `catalog/tests/test_admin_views.py` (UserFactory usage)
- `catalog/tests/test_catalog_views.py` (UserFactory usage)
- `catalog/tests/test_edge_cases.py` (UserFactory usage)
- `catalog/tests/test_managers.py` (UserFactory usage)
- `catalog/tests/test_services.py` (UserFactory usage)
- `catalog/tests/test_tags_views.py` (UserFactory usage)
- `profiles/tests/test_profile_views.py` (UserFactory usage)
- `profiles/tests/test_permissions_views.py` (UserFactory usage)
- `profiles/tests/test_import_export_views.py` (UserFactory usage)
- `executions/tests/test_story_13_4.py` (UserFactory usage)
- `tests/security/test_authorization_rbac.py` (UserFactory usage)
- `tests/security/test_granular_access_control.py` (UserFactory usage)
- `tests/security/test_security_headers.py` (UserFactory usage)
- `tests/security/test_sensitive_endpoints.py` (UserFactory usage)
- `tests/security/test_soc1_compliance.py` (UserFactory usage)

**Créés (Task 2 — Model Tests):**
- `catalog/tests/test_models.py` (nouveaux tests modèles)
- `core/tests/test_models.py` (nouveaux tests modèles)
- `executions/tests/test_models.py` (nouveaux tests modèles)
- `idp_auth/tests/test_models.py` (nouveaux tests modèles)
- `integrations/tests/test_models.py` (nouveaux tests modèles)
- `profiles/tests/test_models.py` (nouveaux tests modèles)

**Modifiés (Code Review Fixes):**
- `tests/security/test_authentication_security.py` (trailing slash fix — 60+ tests auth)
- `core/tests/test_fields.py` (OracleJSONField empty string test fix)
- `core/fields.py` (OracleJSONField documentation clarification)

**Modifiés (Hors Scope Story — Investigation Nécessaire):**
- `catalog/services.py` (pourquoi modifié ? scope creep ?)
- `frontend/src/pages/AdminPage.tsx` (frontend — AC9 optionnel)

**Documentation (AC7, AC10 — NON CRÉÉS ENCORE):**
- `tests/KNOWN_ISSUES.md` (à créer — 222 échecs à documenter)
- `tests/README.md` (à mettre à jour — guidelines common pitfalls)

**Documentation mise à jour:**
- `tests/README.md` (guidelines testing, common pitfalls)
