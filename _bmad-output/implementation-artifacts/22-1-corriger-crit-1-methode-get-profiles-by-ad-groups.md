# Story 22.1 : Corriger CRIT-1 — Méthode manquante `get_profiles_by_ad_groups` dans RBAC

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que **développeur**,
Je veux corriger le bug où `DBOPSProfilePermission` appelle une méthode inexistante `get_profiles_by_ad_groups()`,
Afin de restaurer l'authentification par groupes AD et éviter le fallback superuser non sécurisé.

## Acceptance Criteria

1. **Given** un utilisateur avec groupes AD configurés
   **When** `DBOPSProfilePermission.has_permission()` est appelé
   **Then** la méthode appelle correctement `Profile.objects.find_by_ad_groups()` au lieu de `service.get_profiles_by_ad_groups()`

2. **And** l'`AttributeError` n'est plus masqué par le broad catch — le bug devient visible si une autre erreur survient

3. **And** les utilisateurs avec groupes AD peuvent accéder aux fonctionnalités protégées sans déclencher le fallback superuser

4. **And** un test unitaire vérifie que l'authentification par groupes AD fonctionne correctement avec les profils résolus

5. **And** un test d'intégration vérifie qu'un utilisateur non-superuser avec groupe AD 'GRP-IDP-DBOPS' peut accéder aux endpoints protégés

6. **And** la logique d'exception est documentée avec commentaire expliquant pourquoi le catch est justifié (fallback DB)

## Tasks / Subtasks

- [x] Task 1 : Corriger l'appel de méthode dans `core/permissions.py` (AC: #1, #2)
  - [x] Subtask 1.1 : Remplacer `service.get_profiles_by_ad_groups(ad_groups)` par `Profile.objects.find_by_ad_groups(ad_groups)`
  - [x] Subtask 1.2 : Supprimer l'instanciation inutile de `ProfileService()`
  - [x] Subtask 1.3 : Ajouter l'import `from profiles.models import Profile` en haut du fichier

- [x] Task 2 : Restreindre le catch d'exception (AC: #2, #6)
  - [x] Subtask 2.1 : Identifier les exceptions spécifiques que `Profile.objects.find_by_ad_groups()` peut lever (ex: `OperationalError` pour erreur DB)
  - [x] Subtask 2.2 : Remplacer `except Exception as e` par des exceptions spécifiques appropriées
  - [x] Subtask 2.3 : Ajouter un commentaire documentant pourquoi le catch est justifié (ex: "Fallback si la DB est indisponible — préfère refuser l'accès")
  - [x] Subtask 2.4 : S'assurer que le catch ne masque pas les `AttributeError` ou autres bugs logiques

- [x] Task 3 : Créer tests unitaires de permissions (AC: #4)
  - [x] Subtask 3.1 : Créer `core/tests/test_permissions.py` si inexistant
  - [x] Subtask 3.2 : Test `test_dbops_permission_with_ad_groups()` — vérifie qu'un utilisateur avec groupe AD 'GRP-IDP-DBOPS' obtient l'accès
  - [x] Subtask 3.3 : Test `test_dbops_permission_no_matching_profile()` — vérifie qu'un utilisateur avec groupe AD non-DBOPS est refusé
  - [x] Subtask 3.4 : Test `test_dbops_permission_empty_ad_groups()` — vérifie qu'un utilisateur sans groupes AD est refusé
  - [x] Subtask 3.5 : Mocker `Profile.objects.find_by_ad_groups()` pour isoler la logique de permission

- [x] Task 4 : Créer test d'intégration RBAC (AC: #5)
  - [x] Subtask 4.1 : Ajouter test dans `tests/integration/test_rbac_security.py`
  - [x] Subtask 4.2 : Test `test_non_superuser_dbops_access_via_ad_group()` — créer profil 'DBOPS', utilisateur avec `ad_groups=['GRP-IDP-DBOPS']`, vérifier accès endpoint protégé
  - [x] Subtask 4.3 : Vérifier que le statut HTTP est 200 (pas 403) et que le superuser flag n'est pas nécessaire

- [x] Task 5 : Valider que le fallback superuser n'est plus déclenché (AC: #3)
  - [x] Subtask 5.1 : Ajouter logging temporaire dans le fallback superuser pour tracking
  - [x] Subtask 5.2 : Exécuter tests d'intégration et vérifier que le log "superuser fallback" n'apparaît pas pour les utilisateurs AD valides
  - [x] Subtask 5.3 : Retirer le logging temporaire après validation

## Dev Notes

### Architecture & Patterns

**RBAC Architecture (SOC1/NFR Compliance):**
- Le système RBAC repose sur la résolution de profils via groupes AD
- Flux d'authentification : JWT avec claims AD → `Profile.objects.find_by_ad_groups()` → Permissions cumulatives
- La classe `DBOPSProfilePermission` est utilisée comme guard pour les endpoints DRF nécessitant un profil DBOPS
- Le fallback superuser à la ligne 61-63 est documenté comme un point d'amélioration dans Story 22.2 (CRIT-2)

**ProfileManager (`profiles/models.py:9-69`):**
- Méthode `find_by_ad_groups(ad_groups: list[str])` — résout les profils par correspondance case-insensitive sur `Profile.ad_group` ou `Profile.name`
- Supporte les DN complets (ex: `CN=GRP-IDP-DBOPS,OU=...`) et les codes courts (ex: `DBOPS`)
- Retourne un QuerySet ordonné par nom

**Exception Handling Best Practices (Story 17.6):**
- Éviter les `except Exception` trop larges qui masquent les bugs
- Privilégier des catches spécifiques : `OperationalError` (DB), `ValidationError`, `IntegrityError`
- Toujours logger avec `structlog` incluant `correlation_id`, `user_id`, `error_type`

### Technical Requirements

**Bug Root Cause:**
- `core/permissions.py:48` appelle `service.get_profiles_by_ad_groups(ad_groups)`
- Cette méthode n'existe PAS dans `ProfileService` (vérifié dans `profiles/services.py`)
- Le catch `except Exception` ligne 51 masque l'`AttributeError`, causant un fallback silencieux vers le superuser

**Correct Implementation:**
```python
# profiles/models.py:15
def find_by_ad_groups(self, ad_groups: list[str]):
    """Find profiles matching AD groups - CETTE méthode existe et fonctionne"""
```

**Required Change:**
```python
# AVANT (INCORRECT)
from profiles.services import ProfileService
service = ProfileService()
for profile in service.get_profiles_by_ad_groups(ad_groups):  # AttributeError!

# APRÈS (CORRECT)
from profiles.models import Profile
for profile in Profile.objects.find_by_ad_groups(ad_groups):
```

### File Structure Requirements

**Fichiers à modifier :**
- `idp-portal/django_backend/core/permissions.py:42-59` — Correction du bug + exception handling

**Fichiers de tests à créer/modifier :**
- `idp-portal/django_backend/core/tests/test_permissions.py` — Tests unitaires (nouveau fichier)
- `idp-portal/django_backend/tests/integration/test_rbac_security.py` — Test d'intégration (fichier existant avec 20+ tests RBAC)

**Fichiers de référence (ne pas modifier) :**
- `idp-portal/django_backend/profiles/models.py:9-69` — ProfileManager avec `find_by_ad_groups()`
- `idp-portal/django_backend/profiles/services.py` — ProfileService (vérifier qu'aucune méthode `get_profiles_by_ad_groups` n'existe)

### Testing Requirements

**Test Coverage Target : 100% du code modifié**

**Test Structure (pytest markers):**
```python
@pytest.mark.unit
def test_dbops_permission_with_ad_groups():
    """Test permission granted for user with DBOPS AD group."""

@pytest.mark.integration
def test_non_superuser_dbops_access_via_ad_group():
    """Integration test: non-superuser with AD group accesses protected endpoint."""
```

**Fixtures to Use (from conftest.py):**
- `db` — Database access (Django TestCase)
- `UserFactory` — Factory for creating test users
- `ProfileFactory` — Factory for creating test profiles (if exists, sinon créer Profile manuellement)
- `client` — DRF APIClient pour tests d'intégration

**Test Data Setup:**
```python
# Profil DBOPS
profile = Profile.objects.create(
    name='DBOPS',
    ad_group='GRP-IDP-DBOPS',
    is_admin=1
)

# Utilisateur avec groupe AD
user = User.objects.create(
    username='dbops_user',
    ad_groups=['GRP-IDP-DBOPS']  # Sera résolu vers profile DBOPS
)
```

### Previous Story Intelligence

**Story 21.6 (dernier commit) — Validation environnements profil :**
- Tests backend/frontend pour validation des environnements dynamiques
- Pattern : Tests adversarial avec 37 tests (29 backend + 8 frontend)
- Leçon : Bien tester les cas limites (empty input, missing data, edge cases)

**Story 20.1 — Correction fixtures User :**
- Problème récurrent : `UserFactory` mal configurée causait des échecs de tests
- Solution : Utiliser `UserFactory.create()` avec fixtures explicites pour `ad_groups`
- Impacte les tests RBAC qui dépendent de la résolution AD → Profil

**Story 17.6 — Restreindre exception catches :**
- Epic 17 a déjà abordé la réduction des `except Exception` trop larges
- Résultat : De 21 occurrences → <15 (avec exceptions spécifiques documentées)
- Cette story continue cette initiative pour `core/permissions.py:51`

### Git Intelligence Summary

**Derniers commits pertinents :**
```
7d7f2e0 feat(21-6): add profile environment validation on save
7046edc test(21-3): add comprehensive backend tests for inventory, executions, and profiles
```

**Patterns observés (last 5 commits) :**
- Tests exhaustifs : 50+ tests par story pour valider les cas limites
- Fixtures : Utilisation de `UserFactory`, `ProfileFactory` dans `conftest.py`
- Logging : `structlog.get_logger(__name__)` avec `correlation_id` systématique
- Django ORM : Préférer les QuerySet methods (`Profile.objects.find_by_ad_groups()`) plutôt que des Service methods custom

**Conventions de tests détectées :**
- Marqueurs pytest : `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.security`
- Nomenclature : `test_<feature>_<scenario>_<expected_result>()`
- Assertions multiples : Valider status HTTP, corps de réponse, effets de bord (DB, logs)

### Latest Technical Specifics (Web Research Context)

**Django REST Framework 3.16 (stable):**
- `BasePermission.has_permission(request, view)` — Méthode à implémenter pour permissions custom
- Pattern recommandé : Retourner `False` (refus) plutôt que lever une exception
- Le catch d'exception dans une permission devrait refuser l'accès (`return False`) plutôt que laisser passer

**Django ORM Best Practices (2026):**
- `Model.objects.method()` — Manager methods are preferred over Service layer methods for queries
- `QuerySet.none()` — Return empty queryset instead of `None` or `[]` for consistency
- `prefetch_related()` — Use for reverse OneToOne/ForeignKey to avoid N+1

**Python 3.12 Type Hints:**
- `list[str]` — Modern syntax (vs `List[str]` from typing module)
- `QuerySet` type hints — Use `from django.db.models import QuerySet` for return types

**structlog Best Practices:**
```python
logger.warning(
    "profile_service_unavailable_dbops_check",  # event name
    user_id=request.user.id,
    error=str(e),
    error_type=type(e).__name__,  # Important for debugging
    exc_info=True,  # Include full traceback
)
```

### Project Structure Notes

**Unified Django Backend (Epic M complete):**
- Tous les endpoints RBAC utilisent `DBOPSProfilePermission` dans les ViewSets DRF
- Architecture : Models → Manager → Service → Serializers → Views
- Le ProfileService existe pour la logique métier (CRUD, permissions cumulatives), PAS pour les queries simples

**RBAC Multi-Niveaux :**
- Niveau 1 : Profil DBOPS (is_admin=1) — Accès au portail
- Niveau 2 : Permissions par action (`ProfileActionPermission`)
- Niveau 3 : Permissions par target/environnement (`ProfileTargetPermission`)
- Cette story corrige le **Niveau 1** (check profil DBOPS)

**Alignment avec unified structure :**
- Le bug impacte TOUS les endpoints protégés par `DBOPSProfilePermission`
- Endpoints concernés : `/api/v1/catalog/*`, `/api/v1/executions/*`, `/api/v1/profiles/*`, etc.
- Pas de conflit détecté — le fix est isolé dans `core/permissions.py`

### References

**Source principale du bug :**
- [Source: idp-portal/code-quality-assessment-2026-02-08.md#Section 9.1 CRIT-1]
  - Ligne 48 de core/permissions.py appelle une méthode inexistante
  - Le broad catch masque l'AttributeError
  - Recommendation : Utiliser Profile.objects.find_by_ad_groups() directement

**Architecture RBAC :**
- [Source: _bmad-output/planning-artifacts/architecture.md#Section RBAC Multi-Niveaux]
- [Source: idp-portal/django_backend/docs/sso-architecture.md:212]

**ProfileManager Implementation :**
- [Source: idp-portal/django_backend/profiles/models.py:9-69]
  - Méthode find_by_ad_groups() avec logique de matching DN/short name
  - Case-insensitive matching sur ad_group et name

**Tests RBAC existants :**
- [Source: idp-portal/django_backend/tests/integration/test_rbac_security.py]
  - 20+ tests de sécurité RBAC (permissions, AD groups, superuser)
  - Pattern de tests à réutiliser pour Story 22.1

**Exception Handling Guidelines :**
- [Source: _bmad-output/implementation-artifacts/17-6-restreindre-exception-catches.md]
  - Story Epic 17 : Réduction des broad catches de 21 → <10
  - Exceptions spécifiques recommandées : OperationalError, ValidationError

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- Early return bug: `return profile.lower() == 'dbops'` empêchait le fallthrough vers la vérification AD groups quand `profile` est une string vide. Corrigé en `if isinstance(profile, str) and profile.lower() == 'dbops': return True`.
- Patching dans tests unitaires : `profiles.models.ProfileManager.find_by_ad_groups` (pas `core.permissions.Profile` car import lazy).

### Completion Notes List

- ✅ Task 1: Remplacé `service.get_profiles_by_ad_groups()` → `Profile.objects.find_by_ad_groups()`, supprimé `ProfileService()` instanciation, `profile.code` → `profile.name` (le modèle Profile n'a pas de champ `code`)
- ✅ Task 2: `except Exception` → `except DatabaseError` (couvre OperationalError, InterfaceError, etc.), commentaire justificatif ajouté, `AttributeError` propagé correctement
- ✅ Task 2 bonus: Corrigé le flow logique — `return profile.lower() == 'dbops'` → `if ... and ... == 'dbops': return True` pour permettre le fallthrough vers AD groups
- ✅ Task 3: 13 tests unitaires dans `core/tests/test_permissions.py` — 8 tests AD groups + 5 tests basiques, tous mocked
- ✅ Task 4: 3 tests d'intégration dans `tests/integration/test_rbac_security.py` — accès admin via AD group, refus sans AD group, superuser non nécessaire
- ✅ Task 5: Logging temporaire vérifié (superuser_fallback non déclenché pour users AD valides), logging retiré
- 🔧 Code Review Fixes (2026-02-09):
  - HIGH-1: Supprimé vérifications `profile.code` et `p.code` inexistants (le modèle Profile n'a pas de champ `code`)
  - HIGH-2: Ajouté commentaire détaillé AC#6 expliquant pourquoi `OperationalError` est catchée (DB temporairement indisponible)
  - HIGH-3: Ajouté logging `superuser_fallback_used` pour tracer l'usage du fallback superuser (Story 22.2 CRIT-2)
  - HIGH-6: Test d'intégration vérifie maintenant que le superuser fallback n'est PAS déclenché via `assertLogs()`
  - HIGH-8: `DatabaseError` → `OperationalError` (catch plus restrictif, Story 17.6 guidelines)
  - MEDIUM-1: Ajouté `sprint-status.yaml` dans la File List
  - MEDIUM-2: Supprimé commentaire "MEDIUM-5 fix" trompeur, ajouté référence Story 22.1 CRIT-1
  - MEDIUM-3: Import `Profile` déplacé en haut du fichier (performance)
  - MEDIUM-4: Ajouté test `test_ad_groups_none_treated_as_empty()` pour edge case ad_groups=None
  - MEDIUM-5: Logging `user_id` utilise maintenant `getattr(request.user, 'id', None)` safe access

### Change Log

- 2026-02-09: Story 22.1 CRIT-1 — Correction méthode manquante `get_profiles_by_ad_groups` + flow logique early return + exception handling restrictif + 16 tests (13 unit + 3 integration)
- 2026-02-09: Code Review Pass — 9 HIGH + 5 MEDIUM issues fixed, ajouté 1 test unitaire (ad_groups=None), ajouté 1 test d'intégration (superuser fallback logging), total 18 tests (14 unit + 4 integration)

### File List

- `idp-portal/django_backend/core/permissions.py` (modifié) — Bug fix CRIT-1 + flow logique + exception handling + code review fixes (9 HIGH + 5 MEDIUM)
- `idp-portal/django_backend/core/tests/test_permissions.py` (nouveau) — 14 tests unitaires permissions
- `idp-portal/django_backend/tests/integration/test_rbac_security.py` (modifié) — 4 tests d'intégration AD group DBOPS + superuser fallback logging
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modifié) — Sync sprint tracking status
