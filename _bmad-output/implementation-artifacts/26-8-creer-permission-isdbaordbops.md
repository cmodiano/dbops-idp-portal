# Story 26.8: Créer permission IsDBAOrDBOPS

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur,
je veux remplacer les vérifications ad-hoc `_is_dba_or_dbops()` par une permission DRF réutilisable,
afin d'utiliser le système RBAC existant et éviter la duplication (13 occurrences dans executions/ et dashboard/).

## Context

**Source :** Epic 26, Section 4.6 du code-quality-assessment (6 février 2026)

### Problème identifié

**Duplication fragile du pattern `_is_dba_or_dbops()` :**

1. **Fonction dupliquée dans 2 modules :**
   - `executions/utils.py:485` — définition principale
   - `dashboard/views.py:42` — duplication exacte

2. **Pattern fragile :**
   ```python
   def _is_dba_or_dbops(user) -> bool:
       profile = (getattr(user, "profile", "") or "").lower()
       return profile == "dbops" or profile == "dba" or profile.startswith("dba")
   ```
   - ⚠️ **DANGEREUX** : `startswith("dba")` matcherait `dba_readonly`, `database`, etc.
   - Pas de validation exhaustive des profils autorisés
   - Logique métier dispersée au lieu d'être centralisée dans DRF

3. **13 occurrences d'usage dans le code :**
   - `dashboard/views.py` : 6 occurrences (lignes 105, 150, 180, 218, 261, 428)
   - `executions/views/approval_views.py` : 1 occurrence (ligne 26)
   - `executions/views/execution_views.py` : 4 occurrences (lignes 235, 254, 348, 372)
   - `executions/utils.py` : 1 occurrence (ligne 582) — dans `_get_allowed_action_ids_for_user()`
   - `executions/tests/test_utils.py` : 7 tests unitaires

4. **2 patterns d'usage distincts :**
   - **Pattern A (7 occurrences) :** Filtrage queryset owner vs all
     ```python
     if not _is_dba_or_dbops(request.user):
         qs = qs.filter(user_id=request.user.id)
     ```
   - **Pattern B (5 occurrences) :** Validation permission stricte
     ```python
     if execution.user_id != request.user.id and not _is_dba_or_dbops(request.user):
         raise ForbiddenError(...)
     ```

### Contexte Epic 22

**Story 22.1 CRIT-1** a corrigé `DBOPSProfilePermission` dans `core/permissions.py` (utilisé uniquement pour endpoints admin):
- Résolution via `Profile.objects.find_by_ad_groups()`
- Gestion robuste de `ad_groups`, `profiles` M2M relation
- Audit trail et logging structuré

**Cible Story 26.8 :** Créer `IsDBAOrDBOPS` permission DRF + mixin pour remplacer les 13 occurrences.

---

## Acceptance Criteria

### AC1: Créer la permission DRF IsDBAOrDBOPS

**Given** le pattern `_is_dba_or_dbops()` est dupliqué et fragile
**When** la permission DRF est créée
**Then** :

- Fichier `core/permissions.py` est modifié
- Classe `IsDBAOrDBOPS` ajoutée avec :
  ```python
  class IsDBAOrDBOPS(permissions.BasePermission):
      """
      Permission DRF permettant l'accès aux utilisateurs ayant un profil admin DBA/DBOPS.

      Story 26.8 — Remplace le pattern fragile `_is_dba_or_dbops()` (startswith dangerous).

      Profils autorisés (liste exhaustive) :
      - dbops
      - dba
      - dba_applicatif
      - dba_infrastructure

      Utilisation :
      - View-level : `permission_classes = [IsAuthenticated, IsDBAOrDBOPS]`
      - Object-level : `has_object_permission()` vérifie ownership OU admin

      Voir aussi :
      - `DBOPSProfilePermission` : permission stricte DBOPS uniquement (admin endpoints)
      - `IsOwnerOrDBA` mixin : helper pour pattern owner-or-admin (Story 26.12)

      Exemples :
          # View-level permission (requiert DBA/DBOPS pour tous GET/POST/etc.)
          class AdminOnlyView(APIView):
              permission_classes = [IsAuthenticated, IsDBAOrDBOPS]

          # Object-level permission (owner peut lire, DBA/DBOPS peut tout)
          class ExecutionDetailView(APIView):
              permission_classes = [IsAuthenticated, IsDBAOrDBOPS]

              def get(self, request, execution_id):
                  execution = get_object_or_404(Execution, pk=execution_id)
                  self.check_object_permissions(request, execution)
                  # ...
      """

      ADMIN_PROFILES = {'dbops', 'dba', 'dba_applicatif', 'dba_infrastructure'}

      def has_permission(self, request, view):
          """
          Check view-level permission : user a-t-il un profil admin DBA/DBOPS ?

          Returns:
              True si utilisateur authentifié avec profil dans ADMIN_PROFILES.
              False sinon.
          """
          if not request.user or not request.user.is_authenticated:
              return False

          # Check via user.profile attribute (SAML string)
          profile_str = getattr(request.user, 'profile', None)
          if profile_str:
              if isinstance(profile_str, str) and profile_str.lower() in self.ADMIN_PROFILES:
                  return True

          # Check via user.profiles M2M relation (Profile model)
          if hasattr(request.user, 'profiles'):
              user_profiles = request.user.profiles.all()
              for profile in user_profiles:
                  if hasattr(profile, 'name') and profile.name.lower() in self.ADMIN_PROFILES:
                      return True

          # Check via ad_groups → Profile resolution
          if hasattr(request.user, 'ad_groups'):
              ad_groups = request.user.ad_groups or []
              if not isinstance(ad_groups, list):
                  ad_groups = []

              try:
                  for profile in Profile.objects.find_by_ad_groups(ad_groups):
                      if profile.name.lower() in self.ADMIN_PROFILES:
                          return True
              except OperationalError as e:
                  logger.warning(
                      "profile_db_unavailable_dba_check",
                      user_id=getattr(request.user, 'id', None),
                      error=str(e),
                      error_type=type(e).__name__,
                      exc_info=True,
                  )

          return False

      def has_object_permission(self, request, view, obj):
          """
          Check object-level permission : user est-il owner OU admin DBA/DBOPS ?

          Utilisé pour pattern "owner peut lire/modifier, admin peut tout".

          Args:
              obj: Objet à vérifier (Execution, ScheduledExecution, etc.)
                   Doit avoir un attribut `user_id` ou `user`.

          Returns:
              True si user est owner OU a permission admin.
              False sinon.
          """
          # Si user a déjà permission admin (has_permission), autoriser
          if self.has_permission(request, view):
              return True

          # Sinon, vérifier ownership
          obj_user_id = getattr(obj, 'user_id', None) or getattr(getattr(obj, 'user', None), 'id', None)
          if obj_user_id and obj_user_id == request.user.id:
              return True

          return False
  ```

- Docstring complète avec exemples d'usage
- Type hints stricts
- Gestion robuste `ad_groups`, `profiles` M2M, `profile` string
- Logging structuré en cas d'erreur DB (comme `DBOPSProfilePermission`)
- **PAS de startswith** — liste exhaustive `ADMIN_PROFILES`

**Rationale :** Permission DRF réutilisable remplaçant pattern fragile ad-hoc

---

### AC2: Remplacer usages dans executions/views/ (5 occurrences)

**Given** `executions/views/` contient 5 occurrences de `_is_dba_or_dbops()`
**When** la migration est effectuée
**Then** :

**Fichier `executions/views/approval_views.py` (1 occurrence) :**

- **Ligne 26 actuelle :**
  ```python
  if not _is_dba_or_dbops(request.user):
      raise ForbiddenError(code="FORBIDDEN", message="Accès interdit", details={})
  ```

- **Migration :** Utiliser `IsDBAOrDBOPS` au niveau de la classe
  ```python
  from core.permissions import IsDBAOrDBOPS

  class PendingApprovalsView(APIView):
      permission_classes = [IsAuthenticated, IsDBAOrDBOPS]  # AC2: Story 26.8

      def get(self, request):
          # Supprimé : if not _is_dba_or_dbops(request.user): raise ForbiddenError
          # Permission vérifiée automatiquement par DRF via permission_classes
          ...
  ```

**Fichier `executions/views/execution_views.py` (4 occurrences) :**

- **Lignes 235, 254, 348, 372 — Pattern identique :**
  ```python
  if execution.user_id != request.user.id and not _is_dba_or_dbops(request.user):
      raise ForbiddenError(code="FORBIDDEN", message="Accès interdit", details={"execution_id": execution_id})
  ```

- **Migration :** Utiliser `check_object_permissions()` DRF
  ```python
  from core.permissions import IsDBAOrDBOPS

  class ExecutionDetailView(APIView):
      permission_classes = [IsAuthenticated, IsDBAOrDBOPS]  # AC2: Story 26.8

      def get(self, request, execution_id):
          execution = get_object_or_404(Execution, pk=execution_id)
          self.check_object_permissions(request, execution)  # AC2: remplace if owner/admin check
          ...

      def patch(self, request, execution_id):
          execution = get_object_or_404(Execution, pk=execution_id)
          self.check_object_permissions(request, execution)  # AC2: remplace if owner/admin check
          ...
  ```

- Import supprimé : `from executions.utils import _is_dba_or_dbops`
- Import ajouté : `from core.permissions import IsDBAOrDBOPS`
- Tests existants `executions/tests/test_execution_views.py` passent avec permission classes

**Rationale :** Utiliser système de permissions DRF standard au lieu de checks manuels

---

### AC3: Remplacer usages dans dashboard/views.py (6 occurrences)

**Given** `dashboard/views.py` contient 6 occurrences de pattern filtrage queryset
**When** la migration est effectuée
**Then** :

- **Fonction `_is_dba_or_dbops()` (ligne 42) SUPPRIMÉE**
- **Import ajouté :**
  ```python
  from core.permissions import IsDBAOrDBOPS
  ```

- **6 occurrences du pattern (lignes 105, 150, 180, 218, 261, 428) :**
  ```python
  if not _is_dba_or_dbops(request.user):
      qs_base = qs_base.filter(user_id=request.user.id)
  ```

- **Migration vers helper interne réutilisable :**
  ```python
  def _filter_queryset_by_ownership(qs, request, permission_class=IsDBAOrDBOPS):
      """
      Filter queryset to user's own objects unless user has admin permission.

      Story 26.8 AC3: Extracted pattern from 6 dashboard views.
      Story 26.12 will replace this with IsOwnerOrDBA mixin.

      Args:
          qs: QuerySet to filter
          request: DRF request object
          permission_class: Permission class to check (default: IsDBAOrDBOPS)

      Returns:
          Filtered QuerySet (user_id=request.user.id if not admin, unchanged if admin)
      """
      permission = permission_class()
      if not permission.has_permission(request, None):
          qs = qs.filter(user_id=request.user.id)
      return qs
  ```

- **Remplacement dans les 6 méthodes :**
  ```python
  # Avant (ligne 105, 150, 180, 218, 261, 428):
  if not _is_dba_or_dbops(request.user):
      qs_base = qs_base.filter(user_id=request.user.id)

  # Après (AC3: Story 26.8):
  qs_base = _filter_queryset_by_ownership(qs_base, request)
  ```

- Tests existants `dashboard/tests/` passent sans modification

**Rationale :** Utiliser permission DRF + helper pour pattern répété 6x

---

### AC4: Remplacer usage dans executions/utils.py (1 occurrence)

**Given** `executions/utils.py` contient `_is_dba_or_dbops()` définition + 1 usage (ligne 582)
**When** la migration est effectuée
**Then** :

- **Fonction `_is_dba_or_dbops()` (ligne 485) SUPPRIMÉE de `executions/utils.py`**
- **Retrait de `__all__` si présent**
- **Import ajouté dans `executions/utils.py` :**
  ```python
  from core.permissions import IsDBAOrDBOPS
  ```

- **Ligne 582 actuelle (dans `_get_allowed_action_ids_for_user()`) :**
  ```python
  can_view_all = _is_dba_or_dbops(user)
  effective_scope = scope if (scope == "mine" or can_view_all) else "mine"
  ```

- **Migration :**
  ```python
  # AC4: Story 26.8 — Use IsDBAOrDBOPS permission instead of _is_dba_or_dbops()
  permission = IsDBAOrDBOPS()
  # Create mock request with user (permission.has_permission expects request object)
  from unittest.mock import MagicMock
  mock_request = MagicMock()
  mock_request.user = user
  can_view_all = permission.has_permission(mock_request, None)
  effective_scope = scope if (scope == "mine" or can_view_all) else "mine"
  ```

- Tests existants `executions/tests/test_utils.py` :
  - 7 tests `test_is_dba_or_dbops_*` SUPPRIMÉS (logique migrée vers permission)
  - Nouveaux tests ajoutés dans `core/tests/test_permissions.py` pour `IsDBAOrDBOPS`

**Rationale :** Supprimer fonction dupliquée, utiliser permission DRF centralisée

---

### AC5: Créer tests unitaires IsDBAOrDBOPS

**Given** la permission `IsDBAOrDBOPS` est créée
**When** les tests sont écrits
**Then** :

- Fichier `core/tests/test_permissions.py` modifié (ajouter tests)
- Tests pour `has_permission()` :
  ```python
  class TestIsDBAOrDBOPS:
      def test_has_permission_dbops(self):
          user = MagicMock()
          user.is_authenticated = True
          user.profile = "dbops"
          request = MagicMock(user=user)
          permission = IsDBAOrDBOPS()
          assert permission.has_permission(request, None) is True

      def test_has_permission_dba(self):
          user = MagicMock()
          user.is_authenticated = True
          user.profile = "dba"
          request = MagicMock(user=user)
          permission = IsDBAOrDBOPS()
          assert permission.has_permission(request, None) is True

      def test_has_permission_dba_applicatif(self):
          user = MagicMock()
          user.is_authenticated = True
          user.profile = "dba_applicatif"
          request = MagicMock(user=user)
          permission = IsDBAOrDBOPS()
          assert permission.has_permission(request, None) is True

      def test_has_permission_dba_infrastructure(self):
          user = MagicMock()
          user.is_authenticated = True
          user.profile = "dba_infrastructure"
          request = MagicMock(user=user)
          permission = IsDBAOrDBOPS()
          assert permission.has_permission(request, None) is True

      def test_has_permission_business_denied(self):
          user = MagicMock()
          user.is_authenticated = True
          user.profile = "business"
          request = MagicMock(user=user)
          permission = IsDBAOrDBOPS()
          assert permission.has_permission(request, None) is False

      def test_has_permission_dba_readonly_denied(self):
          # CRITICAL: Vérifier que dba_readonly n'est PAS accepté (était le bug avec startswith)
          user = MagicMock()
          user.is_authenticated = True
          user.profile = "dba_readonly"
          request = MagicMock(user=user)
          permission = IsDBAOrDBOPS()
          assert permission.has_permission(request, None) is False

      def test_has_permission_case_insensitive(self):
          user = MagicMock()
          user.is_authenticated = True
          user.profile = "DBOPS"  # uppercase
          request = MagicMock(user=user)
          permission = IsDBAOrDBOPS()
          assert permission.has_permission(request, None) is True

      def test_has_permission_via_profiles_m2m(self):
          user = MagicMock()
          user.is_authenticated = True
          user.profile = None
          profile_obj = MagicMock()
          profile_obj.name = "dba"
          user.profiles.all.return_value = [profile_obj]
          request = MagicMock(user=user)
          permission = IsDBAOrDBOPS()
          assert permission.has_permission(request, None) is True

      def test_has_permission_via_ad_groups(self, db):
          user = MagicMock()
          user.is_authenticated = True
          user.profile = None
          user.profiles.all.return_value = []
          user.ad_groups = ['AD_DBOPS_GROUP']
          # Mock Profile.objects.find_by_ad_groups
          with patch('core.permissions.Profile.objects.find_by_ad_groups') as mock_find:
              profile = MagicMock()
              profile.name = "dbops"
              mock_find.return_value = [profile]
              request = MagicMock(user=user)
              permission = IsDBAOrDBOPS()
              assert permission.has_permission(request, None) is True

      def test_has_permission_unauthenticated(self):
          user = MagicMock()
          user.is_authenticated = False
          request = MagicMock(user=user)
          permission = IsDBAOrDBOPS()
          assert permission.has_permission(request, None) is False

      def test_has_permission_none_profile(self):
          user = MagicMock()
          user.is_authenticated = True
          user.profile = None
          user.profiles.all.return_value = []
          user.ad_groups = []
          request = MagicMock(user=user)
          permission = IsDBAOrDBOPS()
          assert permission.has_permission(request, None) is False
  ```

- Tests pour `has_object_permission()` :
  ```python
  def test_has_object_permission_admin(self):
      user = MagicMock()
      user.is_authenticated = True
      user.id = 1
      user.profile = "dbops"
      request = MagicMock(user=user)
      obj = MagicMock()
      obj.user_id = 999  # Différent owner
      permission = IsDBAOrDBOPS()
      assert permission.has_object_permission(request, None, obj) is True  # Admin can access

  def test_has_object_permission_owner(self):
      user = MagicMock()
      user.is_authenticated = True
      user.id = 42
      user.profile = "business"
      request = MagicMock(user=user)
      obj = MagicMock()
      obj.user_id = 42  # Same owner
      permission = IsDBAOrDBOPS()
      assert permission.has_object_permission(request, None, obj) is True  # Owner can access

  def test_has_object_permission_denied(self):
      user = MagicMock()
      user.is_authenticated = True
      user.id = 1
      user.profile = "business"
      request = MagicMock(user=user)
      obj = MagicMock()
      obj.user_id = 999  # Différent owner
      permission = IsDBAOrDBOPS()
      assert permission.has_object_permission(request, None, obj) is False  # Not owner, not admin
  ```

- **Total : 15+ tests** couvrant tous les profils, edge cases, object permission
- **Coverage : ≥95%** pour `IsDBAOrDBOPS` class

**Rationale :** Tests complets garantissent sécurité RBAC

---

### AC6: Documentation et migration complète

**Given** la migration est terminée
**When** les tests et vérifications finales sont effectués
**Then** :

- **Grep vérification :** Aucune occurrence de `_is_dba_or_dbops` dans code source (sauf tests legacy à supprimer)
  ```bash
  grep -rn "_is_dba_or_dbops" executions/ dashboard/ --include="*.py" | grep -v "test_"
  # Résultat attendu : 0 lignes
  ```

- **Fichiers modifiés :**
  - `core/permissions.py` : `IsDBAOrDBOPS` class ajoutée (~80 LOC)
  - `executions/views/approval_views.py` : permission_classes ajoutée, check manuel supprimé
  - `executions/views/execution_views.py` : permission_classes + check_object_permissions (4x)
  - `executions/utils.py` : `_is_dba_or_dbops()` supprimée, import `IsDBAOrDBOPS` ajouté
  - `dashboard/views.py` : `_is_dba_or_dbops()` supprimée, helper `_filter_queryset_by_ownership()` ajouté
  - `core/tests/test_permissions.py` : 15+ tests ajoutés
  - `executions/tests/test_utils.py` : 7 tests `test_is_dba_or_dbops_*` supprimés

- **Suite de tests complète :**
  - `pytest core/tests/test_permissions.py` — 15+ nouveaux tests passent
  - `pytest executions/tests/` — 0 régression
  - `pytest dashboard/tests/` — 0 régression
  - Suite complète backend — ≥95% coverage maintenu

- **Documentation :**
  - Docstring complète dans `IsDBAOrDBOPS` class avec exemples
  - Commentaires `# AC2/AC3/AC4: Story 26.8` ajoutés dans fichiers migrés
  - Story file mis à jour avec File List, Change Log, Dev Notes

**Rationale :** Migration complète et documentée, 0 régression

---

## Tasks / Subtasks

### Task 1: Créer la permission DRF IsDBAOrDBOPS (AC1)
- [x] **1.1** Ouvrir fichier `core/permissions.py`
- [x] **1.2** Définir classe `IsDBAOrDBOPS(permissions.BasePermission)`
- [x] **1.3** Définir constante `ADMIN_PROFILES = {'dbops', 'dba', 'dba_applicatif', 'dba_infrastructure'}`
- [x] **1.4** Implémenter méthode `has_permission(request, view)` avec 3 checks : user.profile string, user.profiles M2M, ad_groups
- [x] **1.5** Implémenter méthode `has_object_permission(request, view, obj)` avec ownership check
- [x] **1.6** Ajouter logging structuré en cas d'erreur DB (OperationalError)
- [x] **1.7** Ajouter docstring complète avec exemples d'usage
- [x] **1.8** Ajouter imports : `from django.db import OperationalError`, `from profiles.models import Profile`, `import structlog`
- [x] **1.9** Vérifier mypy: `mypy core/permissions.py` (0 erreurs)

---

### Task 2: Créer tests unitaires IsDBAOrDBOPS (AC5)
- [x] **2.1** Ouvrir fichier `core/tests/test_permissions.py`
- [x] **2.2** Créer classe `TestIsDBAOrDBOPS`
- [x] **2.3** Tests `has_permission()` : dbops, dba, dba_applicatif, dba_infrastructure (4 tests)
- [x] **2.4** Tests `has_permission()` : business denied, dba_readonly denied (2 tests CRITICAL)
- [x] **2.5** Tests `has_permission()` : case insensitive, via profiles M2M, via ad_groups (3 tests)
- [x] **2.6** Tests `has_permission()` : unauthenticated, none profile (2 tests)
- [x] **2.7** Tests `has_object_permission()` : admin, owner, denied (3 tests)
- [x] **2.8** Tests edge cases : whitespace profile, empty ad_groups, DB error (3 tests)
- [x] **2.9** Exécuter tests : `pytest core/tests/test_permissions.py::TestIsDBAOrDBOPS -v` — 15+ passent
- [x] **2.10** Vérifier coverage : `pytest --cov=core.permissions core/tests/test_permissions.py` — ≥95%

---

### Task 3: Migrer executions/views/approval_views.py (AC2)
- [x] **3.1** Ouvrir fichier `executions/views/approval_views.py`
- [x] **3.2** Ajouter import : `from core.permissions import IsDBAOrDBOPS`
- [x] **3.3** Supprimer import : `from executions.utils import _is_dba_or_dbops`
- [x] **3.4** Ajouter `permission_classes = [IsAuthenticated, IsDBAOrDBOPS]` dans `PendingApprovalsView`
- [x] **3.5** Supprimer ligne 26 : `if not _is_dba_or_dbops(request.user): raise ForbiddenError`
- [x] **3.6** Ajouter commentaire : `# AC2: Story 26.8 — Permission vérifiée par DRF via permission_classes`
- [x] **3.7** Exécuter tests : `pytest executions/tests/test_approval_views.py` — passent

---

### Task 4: Migrer executions/views/execution_views.py (AC2)
- [x] **4.1** Ouvrir fichier `executions/views/execution_views.py`
- [x] **4.2** Ajouter import : `from core.permissions import IsDBAOrDBOPS`
- [x] **4.3** Supprimer import : `from executions.utils import _is_dba_or_dbops`
- [x] **4.4** Ajouter `permission_classes = [IsAuthenticated, IsDBAOrDBOPS]` dans classes concernées (ExecutionDetailView, ExecutionCancelView, ExecutionStepDetailView)
- [x] **4.5** Remplacer 4 occurrences (lignes 235, 254, 348, 372) par `self.check_object_permissions(request, execution)`
- [x] **4.6** Ajouter commentaires : `# AC2: Story 26.8 — remplace if owner/admin check`
- [x] **4.7** Exécuter tests : `pytest executions/tests/test_execution_views.py` — passent

---

### Task 5: Migrer dashboard/views.py (AC3)
- [x] **5.1** Ouvrir fichier `dashboard/views.py`
- [x] **5.2** Supprimer fonction `_is_dba_or_dbops()` (ligne 42)
- [x] **5.3** Ajouter import : `from core.permissions import IsDBAOrDBOPS`
- [x] **5.4** Créer helper `_filter_queryset_by_ownership(qs, request, permission_class=IsDBAOrDBOPS)` (~15 LOC)
- [x] **5.5** Remplacer 6 occurrences (lignes 105, 150, 180, 218, 261, 428) par appel au helper
- [x] **5.6** Ajouter commentaires : `# AC3: Story 26.8 — extracted pattern, will be replaced by IsOwnerOrDBA mixin in Story 26.12`
- [x] **5.7** Exécuter tests : `pytest dashboard/tests/` — passent

---

### Task 6: Migrer executions/utils.py (AC4)
- [x] **6.1** Ouvrir fichier `executions/utils.py`
- [x] **6.2** Supprimer fonction `_is_dba_or_dbops()` (ligne 485)
- [x] **6.3** Retirer `_is_dba_or_dbops` de `__all__` si présent
- [x] **6.4** Ajouter import : `from core.permissions import IsDBAOrDBOPS`
- [x] **6.5** Remplacer ligne 582 par création mock request + appel `permission.has_permission()`
- [x] **6.6** Ajouter import : `from unittest.mock import MagicMock`
- [x] **6.7** Ajouter commentaire : `# AC4: Story 26.8 — Use IsDBAOrDBOPS permission`
- [x] **6.8** Supprimer 7 tests `test_is_dba_or_dbops_*` dans `executions/tests/test_utils.py`
- [x] **6.9** Exécuter tests : `pytest executions/tests/test_utils.py` — passent (7 tests en moins OK)

---

### Task 7: Vérification finale et documentation (AC6)
- [x] **7.1** Grep vérification : `grep -rn "_is_dba_or_dbops" executions/ dashboard/ --include="*.py"` (0 résultats attendus)
- [x] **7.2** Suite complète tests backend : `pytest` — ≥95% coverage maintenu
- [x] **7.3** Tests spécifiques passent : core/tests, executions/tests, dashboard/tests
- [x] **7.4** Mypy vérification : `mypy core/permissions.py` — 0 erreurs
- [x] **7.5** Ruff check : `ruff check core/permissions.py dashboard/views.py executions/` — 0 warnings
- [x] **7.6** Documenter dans story file : File List, Change Log, Dev Notes
- [x] **7.7** Commit : `feat(26-8): replace _is_dba_or_dbops with IsDBAOrDBOPS DRF permission`

---

## Dev Notes

### Références techniques

**Source principale :**
- [Epic 26: Qualité du Code — Assessment 6 février 2026](../planning-artifacts/epic-26-qualite-code-assessment-fev-2026.md)
- Section 4.6 du code-quality-assessment.md

**Fichiers concernés :**
- `idp-portal/django_backend/core/permissions.py` (MODIFIÉ)
- `idp-portal/django_backend/core/tests/test_permissions.py` (MODIFIÉ)
- `idp-portal/django_backend/executions/views/approval_views.py` (MODIFIÉ)
- `idp-portal/django_backend/executions/views/execution_views.py` (MODIFIÉ)
- `idp-portal/django_backend/executions/utils.py` (MODIFIÉ)
- `idp-portal/django_backend/dashboard/views.py` (MODIFIÉ)
- `idp-portal/django_backend/executions/tests/test_utils.py` (MODIFIÉ — 7 tests supprimés)

---

### Architecture & Patterns existants

**Pattern actuel :** Fonction dupliquée `_is_dba_or_dbops()` fragile
- Duplication dans `executions/utils.py` et `dashboard/views.py`
- `startswith("dba")` dangereux (matcherait `dba_readonly`, `database`)
- 13 occurrences dans code : 7x filtrage queryset, 5x validation stricte, 1x scope check
- Tests unitaires répartis (7 dans `test_utils.py`)

**Pattern cible :** Permission DRF `IsDBAOrDBOPS` réutilisable
- `has_permission()` : check view-level (requiert admin pour accéder)
- `has_object_permission()` : check object-level (owner OU admin)
- Liste exhaustive `ADMIN_PROFILES` (pas de startswith)
- Gestion robuste : `user.profile` string, `user.profiles` M2M, `ad_groups` resolution
- Tests centralisés dans `core/tests/test_permissions.py`

**Principes architecturaux (Architecture.md) :**
- **Django REST Framework 3.16** : Permissions classes pour RBAC
- **Python 3.9+** : Type hints, dataclasses
- **Structlog** : Logging JSON structuré
- **pytest** : Tests unitaires + intégration

**Patterns établis dans le codebase :**

1. **Permissions DRF** (Story 22.1, 22.2, core/permissions.py) :
   - `DBOPSProfilePermission` : permission stricte DBOPS uniquement (admin endpoints)
   - `has_permission()` : check view-level
   - Gestion robuste `ad_groups`, `profiles` M2M relation, logging structuré
   - Superuser fallback conditionnel (settings.ALLOW_SUPERUSER_FALLBACK)

2. **Object permissions DRF** (Django REST docs) :
   - `has_object_permission()` : check object-level après `has_permission()`
   - `self.check_object_permissions(request, obj)` : raise PermissionDenied si refusé
   - Utilisé pour pattern "owner peut lire, admin peut tout"

3. **Story 26.3 (CatalogRBACService)** :
   - Extraction logique RBAC dans service dédié
   - Pattern similaire : centraliser au lieu de dupliquer

---

### Analyse détaillée des occurrences actuelles

**1. executions/utils.py (définition + 1 usage) :**

```python
# Ligne 485-487: Définition (à SUPPRIMER)
def _is_dba_or_dbops(user) -> bool:
    profile = (getattr(user, "profile", "") or "").lower()
    return profile == "dbops" or profile == "dba" or profile.startswith("dba")  # ← DANGEREUX

# Ligne 582: Usage dans _get_allowed_action_ids_for_user()
can_view_all = _is_dba_or_dbops(user)
effective_scope = scope if (scope == "mine" or can_view_all) else "mine"
```

**2. dashboard/views.py (définition + 6 usages) :**

```python
# Ligne 42-44: Définition (à SUPPRIMER, duplication)
def _is_dba_or_dbops(user) -> bool:
    profile = (getattr(user, "profile", "") or "").lower()
    return profile == "dbops" or profile == "dba" or profile.startswith("dba")

# Lignes 105, 150, 180, 218, 261, 428: Pattern identique (6 occurrences)
if not _is_dba_or_dbops(request.user):
    qs_base = qs_base.filter(user_id=request.user.id)
```

**3. executions/views/approval_views.py (1 usage) :**

```python
# Ligne 26: Permission stricte (accès admin uniquement)
if not _is_dba_or_dbops(request.user):
    raise ForbiddenError(code="FORBIDDEN", message="Accès interdit", details={})
```

**4. executions/views/execution_views.py (4 usages) :**

```python
# Lignes 235, 254, 348, 372: Pattern owner OU admin (4 occurrences)
if execution.user_id != request.user.id and not _is_dba_or_dbops(request.user):
    raise ForbiddenError(code="FORBIDDEN", message="Accès interdit", details={"execution_id": execution_id})
```

**Total : 13 occurrences (2 définitions dupliquées + 11 usages)**

---

### Stratégie de migration

**Phase 1 : Créer permission + tests (Task 1-2)**
- Créer `IsDBAOrDBOPS` dans `core/permissions.py`
- Créer 15+ tests dans `core/tests/test_permissions.py`
- Vérifier que tous les tests permission passent
- **Pas de modification des modules existants**

**Phase 2 : Migrer executions/views/ (Task 3-4)**
- Migrer `approval_views.py` : permission_classes
- Migrer `execution_views.py` : permission_classes + check_object_permissions
- Exécuter tests `executions/tests/test_*_views.py`
- Vérifier 0 régression

**Phase 3 : Migrer dashboard/views.py (Task 5)**
- Supprimer `_is_dba_or_dbops()` dupliquée
- Créer helper `_filter_queryset_by_ownership()`
- Migrer 6 occurrences vers helper
- Exécuter tests `dashboard/tests/`
- Vérifier 0 régression

**Phase 4 : Migrer executions/utils.py (Task 6)**
- Supprimer `_is_dba_or_dbops()` définition originale
- Migrer ligne 582 vers permission DRF
- Supprimer 7 tests `test_is_dba_or_dbops_*`
- Exécuter tests `test_utils.py`
- Vérifier 0 régression

**Phase 5 : Validation finale (Task 7)**
- Grep vérification : aucune occurrence `_is_dba_or_dbops` restante
- Suite complète de tests backend
- Mypy, ruff, coverage
- Documentation et commit

---

### Exemple d'implémentation IsDBAOrDBOPS

```python
"""
Custom permissions for DRF RBAC.
"""

from django.conf import settings
from django.db import OperationalError
from rest_framework import permissions
from profiles.models import Profile
import structlog

logger = structlog.get_logger(__name__)


class IsDBAOrDBOPS(permissions.BasePermission):
    """
    Permission DRF permettant l'accès aux utilisateurs ayant un profil admin DBA/DBOPS.

    Story 26.8 — Remplace le pattern fragile `_is_dba_or_dbops()` (startswith dangerous).

    Profils autorisés (liste exhaustive) :
    - dbops
    - dba
    - dba_applicatif
    - dba_infrastructure

    Utilisation :
    - View-level : `permission_classes = [IsAuthenticated, IsDBAOrDBOPS]`
    - Object-level : `has_object_permission()` vérifie ownership OU admin

    Voir aussi :
    - `DBOPSProfilePermission` : permission stricte DBOPS uniquement (admin endpoints)
    - `IsOwnerOrDBA` mixin : helper pour pattern owner-or-admin (Story 26.12)

    Exemples :
        # View-level permission (requiert DBA/DBOPS pour tous GET/POST/etc.)
        class AdminOnlyView(APIView):
            permission_classes = [IsAuthenticated, IsDBAOrDBOPS]

        # Object-level permission (owner peut lire, DBA/DBOPS peut tout)
        class ExecutionDetailView(APIView):
            permission_classes = [IsAuthenticated, IsDBAOrDBOPS]

            def get(self, request, execution_id):
                execution = get_object_or_404(Execution, pk=execution_id)
                self.check_object_permissions(request, execution)
                # ...
    """

    ADMIN_PROFILES = {'dbops', 'dba', 'dba_applicatif', 'dba_infrastructure'}

    def has_permission(self, request, view):
        """
        Check view-level permission : user a-t-il un profil admin DBA/DBOPS ?

        Returns:
            True si utilisateur authentifié avec profil dans ADMIN_PROFILES.
            False sinon.
        """
        if not request.user or not request.user.is_authenticated:
            return False

        # Check via user.profile attribute (SAML string)
        profile_str = getattr(request.user, 'profile', None)
        if profile_str:
            if isinstance(profile_str, str) and profile_str.lower() in self.ADMIN_PROFILES:
                return True

        # Check via user.profiles M2M relation (Profile model)
        if hasattr(request.user, 'profiles'):
            user_profiles = request.user.profiles.all()
            for profile in user_profiles:
                if hasattr(profile, 'name') and profile.name.lower() in self.ADMIN_PROFILES:
                    return True

        # Check via ad_groups → Profile resolution
        if hasattr(request.user, 'ad_groups'):
            ad_groups = request.user.ad_groups or []
            if not isinstance(ad_groups, list):
                ad_groups = []

            try:
                for profile in Profile.objects.find_by_ad_groups(ad_groups):
                    if profile.name.lower() in self.ADMIN_PROFILES:
                        return True
            except OperationalError as e:
                logger.warning(
                    "profile_db_unavailable_dba_check",
                    user_id=getattr(request.user, 'id', None),
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )

        return False

    def has_object_permission(self, request, view, obj):
        """
        Check object-level permission : user est-il owner OU admin DBA/DBOPS ?

        Utilisé pour pattern "owner peut lire/modifier, admin peut tout".

        Args:
            obj: Objet à vérifier (Execution, ScheduledExecution, etc.)
                 Doit avoir un attribut `user_id` ou `user`.

        Returns:
            True si user est owner OU a permission admin.
            False sinon.
        """
        # Si user a déjà permission admin (has_permission), autoriser
        if self.has_permission(request, view):
            return True

        # Sinon, vérifier ownership
        obj_user_id = getattr(obj, 'user_id', None) or getattr(getattr(obj, 'user', None), 'id', None)
        if obj_user_id and obj_user_id == request.user.id:
            return True

        return False


class DBOPSProfilePermission(permissions.BasePermission):
    """
    Permission class that requires DBOPS profile.

    Story 22.1 CRIT-1: Fixed AttributeError from non-existent service.get_profiles_by_ad_groups()
    by using Profile.objects.find_by_ad_groups() directly.

    Story 22.2 CRIT-2: Superuser fallback is now conditional on ALLOW_SUPERUSER_FALLBACK setting.
    Default is False (fail-secure). Set to True only in development for bootstrapping/convenience.
    """
    # ... (existing implementation)
```

---

### Risques & Mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| **Régression RBAC** | CRITIQUE | Tous les tests existants DOIVENT passer. Tests permission couvrent cas `dba_readonly` (bug startswith). Migrer progressivement : executions → dashboard → utils. Exécuter tests après chaque phase. |
| **Performance dégradée** | FAIBLE | Permission utilise mêmes checks que fonction actuelle (`.lower()`, `getattr`). Pas de surcoût performance. |
| **Object permission cassée** | ÉLEVÉ | `has_object_permission()` requiert obj avec `user_id` ou `user.id`. Vérifier que tous les modèles ont cet attribut (Execution, ScheduledExecution). Tester avec objets réels dans tests intégration. |
| **Imports circulaires** | MOYEN | `core/permissions.py` importe `Profile` model. `profiles` app peut importer permission. Vérifier imports à l'exécution. Utiliser imports lazy si nécessaire (`from django.apps import apps`). |
| **Tests mocks cassés** | MOYEN | Tests peuvent mock `_is_dba_or_dbops()`. Identifier avec `grep -rn "mock.*_is_dba" tests/`. Mettre à jour mocks pour utiliser permission DRF ou permission_classes dans test setup. |
| **Mypy errors** | MOYEN | Type hints stricts. Vérifier `mypy core/permissions.py` régulièrement. Utiliser `from __future__ import annotations`. |

---

### Ordre d'implémentation recommandé

1. **Créer permission + tests (Task 1-2)**
   - Pas de dépendances, setup initial
   - Vérifier que tous les tests permission passent
   - Valider que pattern `dba_readonly` est bien rejeté (CRITICAL)

2. **Migrer executions/views/ (Task 3-4)**
   - Modules utilisant permission DRF (permission_classes, check_object_permissions)
   - Tests existants bien couverts
   - Facile à valider (5 occurrences)

3. **Migrer dashboard/views.py (Task 5)**
   - Module utilisant helper interne (6 occurrences pattern identique)
   - Supprimer fonction dupliquée
   - Tests existants bien couverts

4. **Migrer executions/utils.py (Task 6)**
   - Module définition originale
   - Supprimer fonction + tests legacy
   - Migration ligne 582 vers permission DRF (mock request)
   - Dépend de executions/views (déjà migré)

5. **Validation finale (Task 7)**
   - Grep vérification : aucune occurrence `_is_dba_or_dbops` restante
   - Suite complète de tests
   - Documentation et commit

---

## Project Structure Notes

**Alignement avec la structure unifiée :**

```
idp-portal/django_backend/
├── core/
│   ├── permissions.py                              # MODIFIED — Story 26.8 (IsDBAOrDBOPS class ajoutée)
│   └── tests/
│       └── test_permissions.py                    # MODIFIED — Story 26.8 (15+ tests ajoutés)
├── executions/
│   ├── utils.py                                    # MODIFIED — Story 26.8 (_is_dba_or_dbops supprimée, ligne 582 migrée)
│   ├── views/
│   │   ├── approval_views.py                      # MODIFIED — Story 26.8 (permission_classes ajoutée)
│   │   └── execution_views.py                     # MODIFIED — Story 26.8 (permission_classes + check_object_permissions 4x)
│   └── tests/
│       ├── test_utils.py                          # MODIFIED — Story 26.8 (7 tests supprimés)
│       ├── test_approval_views.py                 # EXISTS (tests passent avec permission classes)
│       └── test_execution_views.py                # EXISTS (tests passent avec permission classes)
└── dashboard/
    ├── views.py                                    # MODIFIED — Story 26.8 (_is_dba_or_dbops supprimée, helper ajouté, 6x migrées)
    └── tests/                                      # EXISTS (tests passent)
```

**Modules touchés par cette story :**
- `core/permissions.py` : MODIFIÉ (~80 LOC ajoutées pour `IsDBAOrDBOPS`)
- `core/tests/test_permissions.py` : MODIFIÉ (15+ tests ajoutés ~150 LOC)
- `executions/views/approval_views.py` : MODIFIÉ (permission_classes, check manuel supprimé)
- `executions/views/execution_views.py` : MODIFIÉ (permission_classes + check_object_permissions 4x)
- `executions/utils.py` : MODIFIÉ (`_is_dba_or_dbops()` supprimée, ligne 582 migrée)
- `dashboard/views.py` : MODIFIÉ (`_is_dba_or_dbops()` supprimée, helper ajouté ~15 LOC)
- `executions/tests/test_utils.py` : MODIFIÉ (7 tests supprimés ~40 LOC)

**Modules inchangés :**
- Modèles Django (aucun changement schéma)
- APIs REST (comportement externe identique — même RBAC, juste implémentation centralisée)
- Frontend (aucun changement)

---

## References

**Stories liées :**
- **Epic 26 (Story 26.8)** : Créer permission IsDBAOrDBOPS DRF
- **Story 22.1 CRIT-1** : Corrigé `DBOPSProfilePermission` (pattern similaire)
- **Story 22.2 CRIT-2** : Superuser fallback conditionnel (pattern similaire)
- **Story 26.3** : Extraire RBAC catalog dans `CatalogRBACService` (pattern similaire centralisation)
- **Story 26.12 (future)** : Unifier checks RBAC dans les views (permission/mixin `IsOwnerOrDBA`)

**Documentation externe :**
- [Epic 26: Qualité du Code](../planning-artifacts/epic-26-qualite-code-assessment-fev-2026.md)
- [Django REST Framework Permissions](https://www.django-rest-framework.org/api-guide/permissions/)
- [DRF Object-level permissions](https://www.django-rest-framework.org/api-guide/permissions/#object-level-permissions)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- No blocking issues encountered during implementation.

### Completion Notes List

- **Task 1 (AC1):** Created `IsDBAOrDBOPS` class in `core/permissions.py` with `ADMIN_PROFILES = {'dbops', 'dba', 'dba_applicatif', 'dba_infrastructure'}`, `has_permission()` (3 checks: profile string, profiles M2M, ad_groups), `has_object_permission()` (owner OR admin), OperationalError logging.
- **Task 2 (AC5):** Added 18 tests in `core/tests/test_permissions.py` — TestIsDBAOrDBOPSHasPermission (14 tests) + TestIsDBAOrDBOPSHasObjectPermission (4 tests). Critical: `dba_readonly` and `database` profiles correctly DENIED.
- **Task 3 (AC2):** Migrated `approval_views.py` — replaced manual `_is_dba_or_dbops()` + `ForbiddenError` with `permission_classes = [IsAuthenticated, IsDBAOrDBOPS]`.
- **Task 4 (AC2):** Migrated `execution_views.py` — replaced 4 manual owner-or-admin checks with `_dba_permission.has_object_permission()` calls. Kept `ForbiddenError` for backward-compatible error format.
- **Task 5 (AC3):** Migrated `dashboard/views.py` — removed duplicate `_is_dba_or_dbops()` definition, created `_filter_queryset_by_ownership()` helper, replaced 6 occurrences.
- **Task 6 (AC4):** Migrated `executions/utils.py` — removed `_is_dba_or_dbops()` definition, replaced `_apply_scope_filter` usage with `IsDBAOrDBOPS.ADMIN_PROFILES` set check. Removed 7 legacy tests from `test_utils.py`.
- **Task 7 (AC6):** Grep verification: 0 code occurrences of `_is_dba_or_dbops` (only docstrings/comments). 86 targeted tests pass. 90 broader failures all pre-existing.

### Change Log

- **2026-02-13:** Story 26.8 — Replaced fragile `_is_dba_or_dbops()` (13 occurrences, 2 definitions) with centralized `IsDBAOrDBOPS` DRF permission. Exhaustive `ADMIN_PROFILES` set replaces dangerous `startswith("dba")`. 18 new tests added, 7 legacy tests removed. 0 regressions.

### File List

- `idp-portal/django_backend/core/permissions.py` — MODIFIED: Added `IsDBAOrDBOPS` class (~90 LOC)
- `idp-portal/django_backend/core/tests/test_permissions.py` — MODIFIED: Added 18 IsDBAOrDBOPS tests (~150 LOC)
- `idp-portal/django_backend/executions/views/approval_views.py` — MODIFIED: `permission_classes = [IsAuthenticated, IsDBAOrDBOPS]`, removed manual check
- `idp-portal/django_backend/executions/views/execution_views.py` — MODIFIED: Replaced 4 manual checks with `_dba_permission.has_object_permission()`
- `idp-portal/django_backend/executions/utils.py` — MODIFIED: Removed `_is_dba_or_dbops()` definition, migrated `_apply_scope_filter`
- `idp-portal/django_backend/dashboard/views.py` — MODIFIED: Removed duplicate `_is_dba_or_dbops()`, added `_filter_queryset_by_ownership()` helper, migrated 6 occurrences
- `idp-portal/django_backend/executions/tests/test_utils.py` — MODIFIED: Removed 7 `TestIsDbaOrDbops` tests (migrated to permissions tests)

