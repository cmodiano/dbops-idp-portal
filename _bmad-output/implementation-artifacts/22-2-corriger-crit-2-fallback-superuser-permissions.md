# Story 22.2 : Corriger CRIT-2 — Fallback superuser fail-open dans permissions

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que **développeur**,
Je veux revoir l'architecture de `DBOPSProfilePermission` pour supprimer ou documenter explicitement le fallback superuser,
Afin de respecter le principe du moindre privilège et éviter l'escalade de privilèges.

## Acceptance Criteria

1. **Given** un superuser Django sans profil DBOPS configuré
   **When** `DBOPSProfilePermission.has_permission()` est appelé
   **Then** l'accès est refusé sauf si explicitement autorisé pour le développement (documenté)

2. **And** le check superuser est déplacé avant les checks AD (pour dev) ou supprimé

3. **And** un profil DBOPS explicite est requis même pour les superusers en production

4. **And** la logique est documentée dans le code avec commentaires explicites

5. **And** un test unitaire vérifie qu'un superuser sans profil DBOPS est refusé en mode production

6. **And** un test d'intégration vérifie que le logging `superuser_fallback_used` n'est plus déclenché en production (ou uniquement en dev)

## Tasks / Subtasks

- [x] Task 1 : Analyser l'usage actuel du fallback superuser (AC: #1, #2)
  - [x] Subtask 1.1 : Identifier tous les endpoints protégés par `DBOPSProfilePermission` via grep sur le codebase
  - [x] Subtask 1.2 : Vérifier si des tests existants dépendent du fallback superuser (rechercher `is_superuser=True` dans les tests)
  - [x] Subtask 1.3 : Documenter les cas d'usage légitimes du fallback (ex: fixtures de développement, tests, bootstrapping initial)

- [x] Task 2 : Implémenter le contrôle par variable d'environnement (AC: #1, #3)
  - [x] Subtask 2.1 : Ajouter variable d'environnement `ALLOW_SUPERUSER_FALLBACK` dans `settings.py` avec valeur par défaut `False`
  - [x] Subtask 2.2 : Ajouter documentation dans `.env.production.template` expliquant que cette variable ne doit être `True` qu'en développement local
  - [x] Subtask 2.3 : Modifier le fallback superuser pour vérifier `settings.ALLOW_SUPERUSER_FALLBACK` avant d'accorder l'accès
  - [x] Subtask 2.4 : Ajouter logging WARNING si le fallback est utilisé (quand `ALLOW_SUPERUSER_FALLBACK=True`)

- [x] Task 3 : Réorganiser l'ordre des checks (AC: #2, #4)
  - [x] Subtask 3.1 : Fallback superuser maintenu APRÈS tous les checks de profils DBOPS (Option B recommandée)
  - [x] Subtask 3.2 : Ajouter commentaire explicite documentant pourquoi le fallback existe (bootstrapping, dev, tests)
  - [x] Subtask 3.3 : Ajouter commentaire WARNING indiquant que le fallback doit être désactivé en production
  - [x] Subtask 3.4 : Ajouter référence à Story 22.2 CRIT-2 dans le commentaire

- [x] Task 4 : Créer tests unitaires pour le fallback superuser (AC: #5)
  - [x] Subtask 4.1 : Test `test_superuser_without_profile_denied_in_production()` — superuser sans profil DBOPS refusé quand `ALLOW_SUPERUSER_FALLBACK=False`
  - [x] Subtask 4.2 : Test `test_superuser_without_profile_allowed_in_dev()` — superuser sans profil DBOPS accepté quand `ALLOW_SUPERUSER_FALLBACK=True`
  - [x] Subtask 4.3 : Test `test_superuser_with_profile_always_allowed()` — superuser avec profil DBOPS toujours accepté (indépendamment de la variable)
  - [x] Subtask 4.4 : Test `test_superuser_fallback_logs_warning()` — logging WARNING déclenché quand le fallback est utilisé

- [x] Task 5 : Créer tests d'intégration RBAC (AC: #6)
  - [x] Subtask 5.1 : Test `test_superuser_fallback_not_triggered_with_profile()` — `superuser_fallback_used` n'est PAS déclenché quand superuser a profil DBOPS
  - [x] Subtask 5.2 : Test `test_superuser_fallback_denied_in_production()` — superuser sans profil reçoit 403 quand `ALLOW_SUPERUSER_FALLBACK=False`
  - [x] Subtask 5.3 : Test `test_superuser_fallback_allowed_in_dev()` — superuser sans profil reçoit 200 quand `ALLOW_SUPERUSER_FALLBACK=True` + log `superuser_fallback_used`

- [x] Task 6 : Documenter la décision architecturale (AC: #4)
  - [x] Subtask 6.1 : Créé `docs/security-architecture.md` avec section 5.3 Politique de Fallback Superuser
  - [x] Subtask 6.2 : Documenté pourquoi le fallback est désactivé par défaut (moindre privilège, SOC1)
  - [x] Subtask 6.3 : Documenté comment activer le fallback en développement local
  - [x] Subtask 6.4 : Ajouté avertissement sur les risques d'activation en production

- [x] Task 7 : Valider l'impact sur les tests existants (AC: #1)
  - [x] Subtask 7.1 : Exécuté tous les tests avec `ALLOW_SUPERUSER_FALLBACK=False` (valeur par défaut)
  - [x] Subtask 7.2 : 2 tests identifiés dépendant du fallback — remplacés par les nouveaux tests
  - [x] Subtask 7.3 : Tests corrigés — `test_superuser_fallback_when_no_profile_match` remplacé par 4 tests spécialisés, `test_superuser_fallback_logs_when_used` remplacé par 3 tests intégration
  - [x] Subtask 7.4 : 38/38 tests permissions+RBAC passent, 490/534 tests totaux passent (44 échecs pré-existants non liés)

## Dev Notes

### Architecture & Patterns

**Principe du moindre privilège (SOC1/NFR Compliance):**
- Le système RBAC doit exiger des permissions explicites même pour les comptes privilégiés
- Un superuser compromis ne doit PAS contourner automatiquement tout le RBAC
- Les accès doivent être traçables et auditables (audit trail conforme SOC1)
- Le fallback superuser actuel viole ces principes en créant une porte dérobée non documentée

**Architecture fail-secure vs fail-open:**
- **Fail-open (actuel)** : Si les vérifications de profil échouent, accorder l'accès aux superusers → **DANGEREUX**
- **Fail-secure (cible)** : Si les vérifications de profil échouent, refuser l'accès à TOUS les utilisateurs (y compris superusers) → **SÉCURISÉ**
- Exception : Environnement de développement local où le fallback peut être toléré pour la commodité

**Contexte Story 22.1 (CRIT-1 corrigé) :**
- Story 22.1 a corrigé le bug où l'`AttributeError` masquait les échecs de résolution de profils
- Résultat : Le fallback superuser était déclenché **systématiquement** pour tous les utilisateurs avec groupes AD (bug masqué)
- Maintenant que CRIT-1 est corrigé, le fallback superuser n'est déclenché QUE pour les vrais superusers sans profil
- Cette story (22.2) traite le risque de sécurité résiduel du fallback lui-même

**Pattern : Variable d'environnement pour contrôle de sécurité :**
```python
# settings.py
ALLOW_SUPERUSER_FALLBACK = os.environ.get('ALLOW_SUPERUSER_FALLBACK', 'false').lower() == 'true'

# Logging warning si utilisé en production
if settings.ALLOW_SUPERUSER_FALLBACK and not settings.DEBUG:
    logger.warning(
        "superuser_fallback_enabled_in_production",
        message="SECURITY RISK: Superuser fallback is enabled in production. "
                "This bypasses RBAC for superusers without DBOPS profile. "
                "Set ALLOW_SUPERUSER_FALLBACK=false in production."
    )
```

### Technical Requirements

**Bug/Défaut de conception CRIT-2 :**
- `core/permissions.py:69-77` — Fallback superuser après échec de toutes les vérifications
- **Problème** : Un superuser sans profil DBOPS contourne TOUT le RBAC
- **Impact** : Escalade de privilèges, non-conformité au principe du moindre privilège
- **Risque** : Compte superuser compromis = accès complet sans trace dans l'audit trail des profils

**Flow actuel (problématique) :**
```
1. Check request.user.profile (attribut direct) → Échec
2. Check request.user.profiles (M2M) → Échec
3. Check request.user.ad_groups → Échec (pas de profil DBOPS associé)
4. Fallback: is_superuser → Succès (CONTOURNEMENT RBAC) ❌
```

**Flow cible (sécurisé) :**
```
1. Check ALLOW_SUPERUSER_FALLBACK setting
2. Si False (production) : check request.user.profile → Échec → REFUS ✅
3. Si True (dev) : check request.user.profile → Échec → Fallback superuser avec logging WARNING
```

**Ordre des checks recommandé :**
```python
# Option A : Déplacer le fallback superuser AVANT les checks AD (pour dev/bootstrap)
if settings.ALLOW_SUPERUSER_FALLBACK and request.user.is_superuser:
    logger.warning("superuser_fallback_bypass", ...)
    return True

# Check via profile attribute
if hasattr(request.user, 'profile'):
    ...

# Check via ad_groups
if hasattr(request.user, 'ad_groups'):
    ...

# Pas de fallback à la fin → Fail-secure
return False
```

**Option B : Garder le fallback à la fin mais conditionnel :**
```python
# Check via profile attribute
if hasattr(request.user, 'profile'):
    ...

# Check via ad_groups
if hasattr(request.user, 'ad_groups'):
    ...

# Fallback superuser conditionnel (dev only)
if settings.ALLOW_SUPERUSER_FALLBACK and request.user.is_superuser:
    logger.warning("superuser_fallback_bypass", ...)
    return True

return False
```

**Recommandation : Option B** (fallback à la fin) pour minimiser l'usage du fallback et préserver la logique normale.

### File Structure Requirements

**Fichiers à modifier :**
- `idp-portal/django_backend/core/permissions.py:69-79` — Ajout condition `settings.ALLOW_SUPERUSER_FALLBACK`
- `idp-portal/django_backend/idp_backend/settings.py` — Ajout variable `ALLOW_SUPERUSER_FALLBACK`
- `idp-portal/django_backend/.env.template` — Documentation de la variable
- `idp-portal/django_backend/docs/security-architecture.md` — Documentation de la décision

**Fichiers de tests à créer/modifier :**
- `idp-portal/django_backend/core/tests/test_permissions.py` — Tests unitaires superuser fallback (4 nouveaux tests)
- `idp-portal/django_backend/tests/integration/test_rbac_security.py` — Tests d'intégration (3 nouveaux tests)

**Fichiers à vérifier (impact potentiel) :**
- Tous les fichiers de tests utilisant `UserFactory(is_superuser=True)` sans profil DBOPS explicite
- Fixtures de tests qui dépendent du fallback superuser (rechercher `is_superuser=True` dans `conftest.py`)

### Testing Requirements

**Test Coverage Target : 100% du code modifié + régression 0%**

**Test Structure (pytest markers):**
```python
@pytest.mark.unit
@override_settings(ALLOW_SUPERUSER_FALLBACK=False)
def test_superuser_without_profile_denied_in_production():
    """Test superuser denied in production when fallback is disabled."""

@pytest.mark.unit
@override_settings(ALLOW_SUPERUSER_FALLBACK=True, DEBUG=False)
def test_superuser_fallback_logs_warning_in_production():
    """Test that superuser fallback logs warning when used in production mode."""

@pytest.mark.integration
@override_settings(ALLOW_SUPERUSER_FALLBACK=False)
def test_superuser_fallback_denied_in_production_integration():
    """Integration test: superuser without DBOPS profile receives 403."""
```

**Fixtures to Use (from conftest.py):**
- `db` — Database access
- `UserFactory` — Factory for creating test users
- `ProfileFactory` — Factory for creating test profiles
- `client` — DRF APIClient pour tests d'intégration

**Test Data Setup (cas nominal production) :**
```python
from django.test import override_settings

# Superuser SANS profil DBOPS (doit être refusé en production)
superuser_no_profile = UserFactory(
    username='admin',
    is_superuser=True,
    ad_groups=[]  # Pas de groupes AD
)
# Note : Pas de profile.name='DBOPS' associé

# Vérification attendue
with override_settings(ALLOW_SUPERUSER_FALLBACK=False):
    response = client.get('/api/v1/catalog/actions/')
    assert response.status_code == 403  # Refusé
```

**Test Data Setup (cas dev autorisé) :**
```python
# Superuser SANS profil DBOPS (autorisé en dev avec fallback)
with override_settings(ALLOW_SUPERUSER_FALLBACK=True):
    response = client.get('/api/v1/catalog/actions/')
    assert response.status_code == 200  # Autorisé via fallback
    # Vérifier logging
    assert 'superuser_fallback_used' in captured_logs
```

### Previous Story Intelligence

**Story 22.1 (commit précédent) — Correction CRIT-1 :**
- Correction du bug `AttributeError` qui masquait les échecs de résolution de profils
- Ajout logging `superuser_fallback_used` pour tracer les utilisations du fallback
- 18 tests (14 unitaires + 4 intégration) avec code review adversarial
- **Leçon** : Le fallback superuser est maintenant tracé avec `logger.info("superuser_fallback_used")` → Utiliser ce log pour validation

**Story 21.6 — Validation environnements profil :**
- Utilisation de `override_settings()` pour tester différentes configurations
- Pattern : Tests avec et sans validation activée via settings
- **Leçon** : Utiliser `@override_settings(ALLOW_SUPERUSER_FALLBACK=True/False)` pour tester les deux modes

**Story 17.5 — Sécuriser gestion secrets :**
- Ajout de startup checks pour détecter secrets par défaut en production
- Pattern : `settings.DEBUG` + variable d'environnement pour contrôle comportement dev/prod
- **Leçon** : Réutiliser le pattern de validation au démarrage si `ALLOW_SUPERUSER_FALLBACK=True` et `DEBUG=False` → Log WARNING

**Story 15.2 — Tests sécurité fonctionnels :**
- 154 tests de sécurité (auth JWT, RBAC, granular access, sensitive endpoints)
- Pattern : Tests d'intégration avec assertions sur status HTTP ET logs
- **Leçon** : Utiliser `self.assertLogs()` pour vérifier que les logging WARNING/INFO sont bien déclenchés

### Git Intelligence Summary

**Dernier commit (Story 22.1) :**
```
71e442f fix(22-1): resolve AttributeError in DBOPS permission check by using Profile.objects.find_by_ad_groups
```

**Patterns observés (permissions.py) :**
- Logging structuré avec `structlog.get_logger(__name__)`
- Safe access aux attributs user : `getattr(request.user, 'id', None)`
- Commentaires explicites avec références aux stories (ex: "Story 22.1 CRIT-1")
- Exception handling restrictif : `except OperationalError` (Story 17.6)

**Conventions de tests détectées (Story 22.1) :**
- Tests unitaires avec mocking : `@patch('profiles.models.ProfileManager.find_by_ad_groups')`
- Tests d'intégration avec fixtures réelles : `Profile.objects.create(...)`
- Assertions multiples : status HTTP + logs + effets de bord DB
- Utilisation de `self.assertLogs()` pour vérifier les messages de log

**Logging pattern (Story 22.1) :**
```python
logger.info(
    "superuser_fallback_used",
    user_id=getattr(request.user, 'id', None),
    username=getattr(request.user, 'username', None),
)
```
→ Réutiliser ce log pour les tests AC#6

### Latest Technical Specifics (Web Research Context)

**Django Settings Best Practices (2026):**
- Variables d'environnement booléennes : `os.environ.get('VAR', 'false').lower() == 'true'`
- Valeurs par défaut sécurisées : `ALLOW_SUPERUSER_FALLBACK` doit être `False` par défaut
- Documentation dans `.env.template` avec avertissement explicite sur les risques en production

**Django REST Framework Security (DRF 3.16):**
- `BasePermission.has_permission()` doit retourner `False` (refus) pour fail-secure
- Les permissions doivent être testables indépendamment des views (unit tests avec mocking)
- Les logs de sécurité doivent inclure `user_id`, `username`, `permission_class` pour audit trail

**Django Test Override Settings:**
```python
from django.test import override_settings

@override_settings(ALLOW_SUPERUSER_FALLBACK=False)
def test_production_mode():
    """Test with production-like settings."""

# Alternative : context manager
with override_settings(ALLOW_SUPERUSER_FALLBACK=True):
    # Test dev mode
```

**structlog Best Practices (Security Logging):**
```python
# Security events should use WARNING or higher
logger.warning(
    "security_control_bypassed",  # event name
    control="superuser_fallback",
    user_id=user.id,
    username=user.username,
    setting_value=settings.ALLOW_SUPERUSER_FALLBACK,
    debug_mode=settings.DEBUG,
)
```

**SOC1 Compliance (Audit Trail):**
- Tous les contournements de contrôles de sécurité doivent être loggés
- Les logs doivent inclure : qui (user_id), quoi (action), quand (timestamp auto), pourquoi (contexte)
- Le fallback superuser est un contournement → Log WARNING obligatoire

### Project Structure Notes

**Security Architecture (docs/security-architecture.md):**
- Section existante : "5. Permissions and Authorization"
- Ajouter sous-section : "5.3 Superuser Fallback Policy"
- Documenter : Pourquoi désactivé, comment activer en dev, risques en production

**RBAC Multi-Niveaux (rappel Story 22.1) :**
- Niveau 1 : Profil DBOPS (is_admin=1) — Accès au portail ← **Cette story corrige le Niveau 1**
- Niveau 2 : Permissions par action (`ProfileActionPermission`)
- Niveau 3 : Permissions par target/environnement (`ProfileTargetPermission`)

**Impact sur les endpoints protégés :**
- TOUS les endpoints utilisant `permission_classes = [DBOPSProfilePermission]` sont impactés
- Endpoints concernés : `/api/v1/catalog/*`, `/api/v1/executions/*`, `/api/v1/profiles/*`, `/api/v1/admin/*`
- Les superusers devront avoir un profil DBOPS explicite pour accéder aux endpoints en production

**Configuration recommandée pour les environnements :**

| Environnement | `DEBUG` | `ALLOW_SUPERUSER_FALLBACK` | Comportement |
|---|:---:|:---:|---|
| Dev local | `True` | `True` | Fallback autorisé, log INFO |
| Test/Staging | `False` | `False` | Fallback refusé, fail-secure |
| Production | `False` | `False` | Fallback refusé, fail-secure |

### References

**Source principale du défaut (CRIT-2) :**
- [Source: idp-portal/code-quality-assessment-2026-02-08.md#Section 9.1 CRIT-2]
  - Architecture fail-open : superuser compromis contourne tout le RBAC
  - Recommandation : Déplacer check superuser AVANT checks AD ou le supprimer
  - Impact : Escalade de privilèges, non-conformité principe du moindre privilège

**Architecture RBAC :**
- [Source: idp-portal/django_backend/docs/security-architecture.md#Section 5]
- [Source: _bmad-output/planning-artifacts/architecture.md#Section RBAC Multi-Niveaux]

**Story 22.1 (CRIT-1) — Context :**
- [Source: _bmad-output/implementation-artifacts/22-1-corriger-crit-1-methode-get-profiles-by-ad-groups.md]
  - Correction du bug AttributeError masqué par broad catch
  - Ajout logging `superuser_fallback_used` pour traçabilité
  - Commentaire ligne 70 : "Story 22.2 CRIT-2: This fallback should be removed or restricted in production"

**SOC1 Compliance Requirements :**
- [Source: idp-portal/django_backend/docs/soc1-compliance.md]
  - Principe du moindre privilège (section 3.2)
  - Audit trail complet pour tous les accès (section 4.1)

**Django Settings Pattern (Story 17.5) :**
- [Source: idp-portal/django_backend/idp_backend/settings.py:45-60]
  - Pattern de validation startup checks pour secrets
  - Utilisation de `os.environ.get()` avec valeurs par défaut sécurisées

**Tests RBAC existants :**
- [Source: idp-portal/django_backend/tests/integration/test_rbac_security.py]
  - 20+ tests de sécurité RBAC (permissions, AD groups, superuser)
  - Pattern : Utilisation de `override_settings()` pour tester différentes configurations

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Analyse : 12 endpoints protégés par `DBOPSProfilePermission`, 2 tests dépendant du fallback inconditionnel
- Implémentation : Option B retenue (fallback conditionnel en fin de chaîne) — minimise l'usage du fallback
- Tests : 19/19 unit tests, 6/6 integration tests, 40/40 permissions+RBAC tests pass
- **Code review adversarial 2026-02-09** : 10 issues trouvés (5 HIGH + 3 MEDIUM + 2 LOW), tous auto-fixés

### Completion Notes List

- `ALLOW_SUPERUSER_FALLBACK` ajouté dans `settings.py` avec valeur par défaut `False` (fail-secure)
- Fallback superuser conditionnel : `getattr(settings, 'ALLOW_SUPERUSER_FALLBACK', False)` vérifié AVANT `is_superuser`
- Log level changé de `INFO` à `WARNING` pour conformité SOC1 (contournement de contrôle de sécurité)
- Log enrichi avec `allow_superuser_fallback=True` et `debug_mode` pour audit trail complet
- Test existant `test_superuser_fallback_when_no_profile_match` remplacé par 4 tests spécialisés
- Test existant `test_superuser_fallback_logs_when_used` remplacé par 3 tests d'intégration
- `test_settings.py` : `ALLOW_SUPERUSER_FALLBACK = False` explicite pour fail-secure en tests
- `.env.production.template` : section RBAC Security ajoutée avec documentation variable + exemple activation dev
- `docs/security-architecture.md` : créé avec politique complète de fallback superuser + exemple log JSON
- Aucun test existant cassé par le changement (les 2 tests dépendants ont été remplacés)

**Code Review Adversarial Fixes (2026-02-09):**
- HIGH-2 : Event log renommé `superuser_fallback_used` → `security_rbac_bypass_superuser_fallback` (SIEM/SOC détection)
- HIGH-3 : Test `test_default_superuser_fallback_disabled_in_test_settings()` ajouté (vérification valeur par défaut)
- HIGH-5 : Test `test_superuser_fallback_logs_debug_mode()` ajouté (validation `debug_mode=True/False` dans logs)
- MEDIUM-1 : Exemple log JSON structuré ajouté dans `docs/security-architecture.md`
- MEDIUM-2 : Section RBAC Security déplacée dans "SECURITY SETTINGS" dans `.env.production.template`
- MEDIUM-3 : Commentaire `permissions.py:73` clarifié ("executed ONLY if all profile checks above returned False")
- LOW-2 : `assertNoLogs` fallback Django < 5.1 supprimé (projet utilise Django 5.2.11)

### File List

- `idp-portal/django_backend/core/permissions.py` — Modifié : fallback conditionnel + import settings + commentaires Story 22.2
- `idp-portal/django_backend/idp_backend/settings.py` — Modifié : ajout `ALLOW_SUPERUSER_FALLBACK`
- `idp-portal/django_backend/idp_backend/test_settings.py` — Modifié : ajout `ALLOW_SUPERUSER_FALLBACK = False`
- `idp-portal/django_backend/.env.production.template` — Modifié : section RBAC Security ajoutée
- `idp-portal/django_backend/core/tests/test_permissions.py` — Modifié : 6 nouveaux tests unitaires (remplacement 1 ancien + 2 tests code review)
- `idp-portal/django_backend/tests/integration/test_rbac_security.py` — Modifié : 3 nouveaux tests intégration (event renommé, assertNoLogs simplifié)
- `idp-portal/django_backend/docs/security-architecture.md` — Créé : documentation politique fallback superuser

## Change Log

- 2026-02-09 : Story 22.2 CRIT-2 — Fallback superuser rendu conditionnel via `ALLOW_SUPERUSER_FALLBACK` (default False). Fail-secure par défaut en production. 9 tests ajoutés (6 unit + 3 integration), documentation sécurité créée. **Code review adversarial** : 10 issues trouvés, 10 auto-fixés. Event log renommé `security_rbac_bypass_superuser_fallback`. 40/40 tests passent.
