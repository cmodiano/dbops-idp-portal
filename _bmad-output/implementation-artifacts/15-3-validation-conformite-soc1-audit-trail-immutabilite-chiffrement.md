# Story 15.3: Validation conformité SOC1 (audit trail, immutabilité, chiffrement)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a spécialiste sécurité / auditeur SOC1,
I want valider que le portail respecte les exigences SOC1 pour l'audit trail, l'immutabilité des logs, et le chiffrement des communications,
So que je puisse certifier la conformité avant la release et documenter les contrôles de sécurité.

## Acceptance Criteria

**AC1: Immutabilité des logs d'audit**
**Given** le système d'audit du portail (table AUDIT_LOG),
**When** on valide l'immutabilité des logs d'audit,
**Then** aucune opération UPDATE ou DELETE n'est possible sur la table AUDIT_LOG (contraintes DB ou permissions)
**And** les logs d'audit sont écrits une seule fois et ne peuvent être modifiés après écriture
**And** NFR8 est vérifiée : les logs d'audit sont immutables
**And** un test démontre qu'une tentative de modification d'un log d'audit échoue avec une erreur appropriée

**AC2: Traçabilité complète des exécutions**
**Given** chaque exécution d'action dans le portail,
**When** on valide la traçabilité complète,
**Then** une entrée dans AUDIT_LOG est créée avec : utilisateur (qui), action exécutée (quoi), timestamp précis (quand), paramètres de l'exécution, résultat (succès/échec), autorisation RBAC appliquée
**And** FR30 est vérifiée : trace d'audit immutable pour chaque exécution
**And** les logs d'audit incluent un correlation_id pour tracer une exécution complète de bout en bout
**And** les logs d'audit sont consultables via l'API /api/v1/audit avec filtres par environnement, période, type d'action (FR33)

**AC3: Chiffrement en transit (TLS 1.2+)**
**Given** les communications entre le portail et les systèmes intégrés (Vault, ServiceNow, plateformes d'exécution),
**When** on valide le chiffrement en transit,
**Then** toutes les communications utilisent TLS 1.2 ou supérieur
**And** les certificats SSL/TLS sont valides et non expirés
**And** NFR6 est vérifiée : toutes les communications sont chiffrées en transit
**And** un test démontre qu'une connexion non chiffrée est rejetée

**AC4: Gestion des secrets via Vault**
**Given** les secrets et credentials utilisés par le portail,
**When** on valide la gestion des secrets,
**Then** aucun secret n'est stocké dans le code source, les fichiers de configuration, ou la base de données
**And** tous les secrets sont récupérés depuis HashiCorp Vault au moment de l'exécution
**And** NFR7 est vérifiée : aucun secret stocké dans le portail
**And** FR29 est vérifiée : tous les secrets sont récupérés depuis Vault à l'exécution
**And** un test démontre qu'une exécution échoue avec un message explicite si Vault est indisponible (NFR21)

**AC5: Protection des données sensibles**
**Given** les données sensibles stockées dans le portail,
**When** on valide la protection des données,
**Then** le portail ne stocke que les métadonnées de l'inventaire (noms de bases, environnements, technologies)
**And** aucune donnée sensible des bases de données gérées n'est stockée (pas de mots de passe, données utilisateurs, etc.)
**And** NFR11 est vérifiée : le portail ne conserve aucune donnée sensible
**And** un audit de la base de données confirme qu'aucune donnée sensible n'est présente

**AC6: Document de conformité SOC1**
**Given** les exigences SOC1,
**When** on consolide la validation,
**Then** un document de conformité SOC1 est généré avec la liste des contrôles validés et les preuves associées
**And** chaque contrôle SOC1 est documenté avec son implémentation, sa validation, et les tests associés
**And** les écarts identifiés sont documentés avec un plan de correction et une date cible

## Tasks / Subtasks

- [x] Task 1: Enforcement immutabilité AUDIT_LOG au niveau base de données (AC: 1)
  - [x] Subtask 1.1: Créer migration Flyway `V054__audit_log_immutable_trigger.sql` avec trigger Oracle rejetant UPDATE/DELETE
  - [x] Subtask 1.2: Implémenter trigger `TRG_AUDIT_LOG_IMMUTABLE` qui lève `RAISE_APPLICATION_ERROR(-20001, 'AUDIT_LOG is immutable')` sur UPDATE ou DELETE
  - [x] Subtask 1.3: Overrider `save()` sur le modèle Django AuditLog pour lever `IntegrityError` si `self.pk` existe déjà (empêcher update via ORM)
  - [x] Subtask 1.4: Overrider `delete()` sur le modèle Django AuditLog pour lever `IntegrityError` (empêcher suppression via ORM)
  - [x] Subtask 1.5: Overrider `QuerySet.update()` et `QuerySet.delete()` via custom Manager pour AuditLog

- [x] Task 2: Tests d'immutabilité audit log (AC: 1)
  - [x] Subtask 2.1: Créer `tests/security/test_soc1_compliance.py`
  - [x] Subtask 2.2: Test `test_audit_log_update_raises_error` — vérifier que `AuditLog.objects.filter(...).update(...)` lève une erreur
  - [x] Subtask 2.3: Test `test_audit_log_delete_raises_error` — vérifier que `AuditLog.objects.filter(...).delete()` lève une erreur
  - [x] Subtask 2.4: Test `test_audit_log_save_existing_raises_error` — vérifier que `.save()` sur un objet existant lève une erreur
  - [x] Subtask 2.5: Test `test_audit_log_create_succeeds` — vérifier que la création fonctionne toujours normalement
  - [x] Subtask 2.6: Test `test_audit_log_bulk_delete_raises_error` — vérifier que `QuerySet.delete()` lève une erreur

- [x] Task 3: Validation traçabilité complète et correlation_id (AC: 2)
  - [x] Subtask 3.1: Test `test_execution_creates_audit_entry_with_all_fields` — vérifier que chaque exécution crée une entrée AUDIT_LOG avec user_id, action_type, entity_type, entity_id, details JSON, ip_address, correlation_id
  - [x] Subtask 3.2: Test `test_correlation_id_propagated_from_request_to_audit` — vérifier que le correlation_id du header HTTP se retrouve dans AUDIT_LOG
  - [x] Subtask 3.3: Test `test_audit_filter_by_environment` — vérifier que l'API /api/v1/audit supporte le filtre par environnement
  - [x] Subtask 3.4: Test `test_audit_filter_by_date_range` — vérifier le filtre par période
  - [x] Subtask 3.5: Test `test_audit_filter_by_action_type` — vérifier le filtre par type d'action
  - [x] Subtask 3.6: Test `test_audit_lifecycle_complete` — vérifier la traçabilité bout-en-bout : EXECUTION_SUBMITTED → EXECUTION_RUNNING → EXECUTION_COMPLETED avec même correlation_id

- [x] Task 4: Configuration sécurité Django pour production (AC: 3)
  - [x] Subtask 4.1: Ajouter les settings de sécurité production dans `settings.py` (conditionnés par `not DEBUG`) : `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_PROXY_SSL_HEADER`
  - [x] Subtask 4.2: Activer le header HSTS dans la configuration Nginx (décommenter la ligne dans `deployment/nginx-django.conf`)
  - [x] Subtask 4.3: Test `test_production_security_settings_enabled` — vérifier que les settings de sécurité sont activés quand `DEBUG=False`
  - [x] Subtask 4.4: Test `test_ssl_redirect_when_not_debug` — vérifier que `SECURE_SSL_REDIRECT=True` en production

- [x] Task 5: Validation gestion des secrets (AC: 4)
  - [x] Subtask 5.1: Vérifier que `credential_ref` dans le modèle Integration est bien une référence Vault (pas un secret en clair)
  - [x] Subtask 5.2: Test `test_no_secrets_in_integration_config` — scanner les champs `config` et `credential_ref` des intégrations pour vérifier l'absence de secrets en clair
  - [x] Subtask 5.3: Test `test_vault_unavailable_returns_explicit_error` — vérifier que l'absence de Vault produit un message d'erreur explicite (NFR21)
  - [x] Subtask 5.4: Test `test_no_secrets_in_settings_file` — scanner `settings.py` pour vérifier que `SECRET_KEY` vient d'une variable d'environnement
  - [x] Subtask 5.5: Re-exécuter detect-secrets pour confirmer la conformité NFR7

- [x] Task 6: Audit protection des données sensibles (AC: 5)
  - [x] Subtask 6.1: Test `test_no_passwords_in_database_models` — scanner tous les modèles Django pour vérifier l'absence de champs mot de passe
  - [x] Subtask 6.2: Test `test_execution_parameters_no_credentials` — vérifier que les paramètres d'exécution ne contiennent pas de credentials en clair
  - [x] Subtask 6.3: Test `test_error_messages_no_sensitive_info` — vérifier que les messages d'erreur n'exposent pas d'informations sensibles (stack traces, chemins internes)
  - [x] Subtask 6.4: Documenter la classification des données pour tous les champs CLOB (Integration.config, Execution.parameters, ExecutionStep.output, AuditLog.details)

- [x] Task 7: Document de conformité SOC1 (AC: 6)
  - [x] Subtask 7.1: Créer `docs/soc1-compliance-report.md` avec résumé exécutif
  - [x] Subtask 7.2: Documenter chaque contrôle SOC1 : audit trail (FR30), immutabilité (NFR8), chiffrement (NFR6), zéro credentials (NFR7), sessions (NFR9), journalisation accès (NFR10), données sensibles (NFR11)
  - [x] Subtask 7.3: Pour chaque contrôle, documenter : implémentation technique, preuves (tests, scans, configurations), statut (conforme/partiel/non-conforme)
  - [x] Subtask 7.4: Documenter les écarts identifiés avec plan de correction et date cible
  - [x] Subtask 7.5: Inclure la matrice de traçabilité NFR ↔ tests ↔ contrôles SOC1
  - [x] Subtask 7.6: Inclure les résultats des audits Story 15.1 (SAST, dépendances, secrets) et Story 15.2 (tests fonctionnels sécurité) comme preuves

## Dev Notes

### État actuel de l'immutabilité AUDIT_LOG — GAP CRITIQUE

**Situation actuelle :**
- L'immutabilité est documentée dans la migration V004 (`COMMENT ON TABLE AUDIT_LOG IS 'Append-only audit log. No UPDATE or DELETE allowed.'`) mais **NON ENFORCÉE**
- Le code applicatif n'expose que `create_entry()` et des méthodes de lecture dans `AuditLogManager`
- **AUCUN trigger Oracle** ne bloque UPDATE/DELETE
- **AUCUN REVOKE** UPDATE/DELETE sur le user `idp_app`
- **AUCUN override** de `save()` ou `delete()` dans le modèle Django
- Le modèle Django **PERMET techniquement** `AuditLog.objects.filter(...).delete()` ou `.update(...)`
- La migration V028 note explicitement : *"Optional: add trigger or policy to reject UPDATE/DELETE for defense in depth (Task 5.1)."* — **ce Task 5.1 n'a jamais été implémenté**

**Solution requise (défense en profondeur) :**
1. **Trigger Oracle** (protection base de données) :
```sql
CREATE OR REPLACE TRIGGER TRG_AUDIT_LOG_IMMUTABLE
BEFORE UPDATE OR DELETE ON AUDIT_LOG
FOR EACH ROW
BEGIN
    RAISE_APPLICATION_ERROR(-20001, 'AUDIT_LOG is immutable - UPDATE and DELETE operations are forbidden (SOC1/NFR8)');
END;
/
```

2. **Django model override** (protection applicative) :
```python
class AuditLog(models.Model):
    def save(self, *args, **kwargs):
        if self.pk:
            raise IntegrityError("AUDIT_LOG is immutable - updates are forbidden (SOC1/NFR8)")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise IntegrityError("AUDIT_LOG is immutable - deletions are forbidden (SOC1/NFR8)")
```

3. **Custom QuerySet** (protection ORM) :
```python
class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise IntegrityError("AUDIT_LOG is immutable - bulk updates are forbidden (SOC1/NFR8)")

    def delete(self):
        raise IntegrityError("AUDIT_LOG is immutable - bulk deletions are forbidden (SOC1/NFR8)")
```

### Architecture de sécurité existante

**Authentification :**
- JWT tokens signés HS256 (access: 30 min, refresh: 8 heures)
- SAML 2.0 avec python3-saml (SP-initiated flow)
- Refresh token en cookie httpOnly, secure, samesite=lax
- Dev bypass mode avec `AUTH_DEV_BYPASS`

**Autorisation RBAC :**
- Profils: dbops, dba, dba_applicatif, dba_infrastructure, client_business
- Permissions par action: ALL, LIST (action_ids), PATTERN (tags)
- Restrictions par environnement: dev, staging, prod
- Workflow d'approbation requis pour prod

**Middleware de sécurité (ordre d'exécution dans settings.py:60-73) :**
1. `SecurityMiddleware` (Django built-in)
2. `CorrelationIdMiddleware` — UUID par requête, thread-local + structlog contextvars
3. `RequestResponseLoggingMiddleware` — Logging structuré JSON
4. `SecurityHeadersMiddleware` — X-Frame-Options, X-Content-Type-Options, Cache-Control
5. [...autres middleware Django...]
6. `AuditAuthMiddleware` — Journalisation des 401 sur /api/v1/auth

**Correlation ID — Implémentation complète :**
- Middleware génère/propage UUID (`core/middleware.py:44-86`)
- Thread-local storage (`core/middleware.py:13-27`)
- Stocké dans AUDIT_LOG.CORRELATION_ID (migration V028)
- Stocké dans SCHEDULED_EXECUTIONS.CORRELATION_ID
- Bind automatique à structlog pour TOUS les logs
- Retourné dans header HTTP `X-Idp-Request-Id`
- Supporte header client `X-Idp-Request-Id`

### TLS/HTTPS — État et gaps

**Nginx (configuré) :**
- TLS 1.2+ configuré dans `deployment/nginx-django.conf:17-27`
- Cipher suites modernes (ECDHE-ECDSA-AES128-GCM-SHA256, etc.)
- Redirect HTTP→HTTPS (port 80 → 443)
- HSTS **commenté** (ligne 30 : `# add_header Strict-Transport-Security`)

**Django settings (MANQUANTS pour production) :**
- `SECURE_SSL_REDIRECT` — absent
- `SECURE_HSTS_SECONDS` — absent
- `SESSION_COOKIE_SECURE` — absent
- `CSRF_COOKIE_SECURE` — absent
- `SECURE_PROXY_SSL_HEADER` — absent

### Vault — État actuel

- `VAULT_ADDR` configuré dans settings.py (`os.getenv('VAULT_ADDR', 'http://localhost:8200')`)
- Le modèle Integration a un champ `credential_ref` (référence Vault, pas le secret)
- **VaultService NON implémenté** — placeholder dans `inventory/services.py:133-150`
- Mock fixture `mock_vault_service` dans `tests/conftest.py:395-397`
- **Note importante** : L'implémentation complète de VaultService n'est PAS dans le scope de cette story. La story 15.3 VALIDE que la gestion des secrets est conforme (credential_ref = référence, pas de secret en clair, erreur explicite si Vault indisponible). L'implémentation complète est un sujet séparé.

### Données sensibles — Analyse des modèles

**Champs CLOB potentiellement sensibles :**
- `Integration.config` (CLOB) — configuration de plateforme, peut contenir des URLs internes
- `Integration.credential_ref` (VARCHAR2) — **référence Vault**, pas le secret lui-même ✅
- `Execution.parameters` (CLOB) — paramètres d'exécution (noms de serveurs, bases)
- `ExecutionStep.output` (CLOB) — sortie de commande, peut contenir des infos sensibles
- `ExecutionStep.error_message` (CLOB) — messages d'erreur, ne doit pas exposer de stack traces
- `AuditLog.details` (CLOB) — contexte JSON de l'audit

**Pas de données critiques :**
- ✅ Aucun mot de passe stocké (SAML auth, pas de password)
- ✅ Aucune clé API stockée (credential_ref = référence Vault)
- ✅ Pas de PII au-delà de username/display_name
- ✅ Pas de données des bases gérées (NFR11)

### Résultats des stories précédentes (15.1, 15.2) — Preuves SOC1

**Story 15.1 — Audit sécurité statique :**
- Bandit SAST : 8 issues (0 CRITICAL, 0 HIGH, 3 MEDIUM faux positifs, 5 LOW)
- pip-audit : 19 vulnérabilités HIGH dans dépendances (azure-core, requests, urllib3, etc.)
- npm audit : 0 vulnérabilités ✅
- detect-secrets : 0 secrets réels ✅ (NFR7 CONFORME)
- Rapports : `docs/security-audit-report.md`, `docs/security-remediation-plan.md`

**Story 15.2 — Tests sécurité fonctionnels :**
- 154 tests sécurité (52 auth + 34 RBAC + 27 granulaire + 24 endpoints + 17 headers)
- 100% passing
- NFR9 validée (expiration session 30min)
- NFR10 validée (journalisation accès non autorisé)
- CI/CD intégré (job `security-functional-tests`)

### Patterns de test à suivre

```python
# Utiliser les fixtures de tests/security/conftest.py
@pytest.fixture
def authenticated_client(api_client, test_user):
    """Client avec JWT valide."""
    token = create_access_token(test_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client

# Utiliser les factories de tests/factories.py
from tests.factories import ProfileFactory, UserFactory, ActionFactory

# Structure des tests SOC1
class TestAuditLogImmutability:
    """SOC1 Control: NFR8 - Audit logs are immutable."""

    def test_audit_log_update_raises_error(self, db):
        entry = AuditLog.objects.create_entry(...)
        with pytest.raises(IntegrityError):
            AuditLog.objects.filter(id=entry.id).update(action_type='MODIFIED')

    def test_audit_log_delete_raises_error(self, db):
        entry = AuditLog.objects.create_entry(...)
        with pytest.raises(IntegrityError):
            entry.delete()
```

### Project Structure Notes

**Nouveaux fichiers à créer :**
```
idp-portal/
├── database/migrations/
│   └── V054__audit_log_immutable_trigger.sql        # Trigger Oracle immutabilité
├── django_backend/
│   └── tests/security/
│       └── test_soc1_compliance.py                  # Tests SOC1 (AC1-AC5)
└── docs/
    └── soc1-compliance-report.md                     # Document conformité SOC1
```

**Fichiers à modifier :**
- `idp-portal/django_backend/core/models.py` — Override save()/delete() sur AuditLog, custom ImmutableQuerySet
- `idp-portal/django_backend/idp_backend/settings.py` — Ajouter settings sécurité production
- `idp-portal/django_backend/deployment/nginx-django.conf` — Décommenter HSTS
- `idp-portal/.github/workflows/ci.yml` — Ajouter job `soc1-compliance-tests` (optionnel, peut être intégré dans security-functional-tests existant)

### Références

- [Source: idp-portal/database/migrations/V004__create_audit_log.sql] — Création table AUDIT_LOG
- [Source: idp-portal/database/migrations/V028__audit_log_execution_traces.sql] — CORRELATION_ID + note Task 5.1
- [Source: idp-portal/django_backend/core/models.py] — Modèle AuditLog (lignes 71-200)
- [Source: idp-portal/django_backend/core/middleware.py:44-86] — CorrelationIdMiddleware
- [Source: idp-portal/django_backend/core/middleware.py:178-210] — SecurityHeadersMiddleware
- [Source: idp-portal/django_backend/idp_backend/settings.py:60-73] — Middleware stack
- [Source: idp-portal/django_backend/idp_backend/settings.py:284-285] — VAULT_ADDR config
- [Source: idp-portal/django_backend/integrations/models.py:73] — credential_ref field
- [Source: idp-portal/django_backend/deployment/nginx-django.conf:17-30] — TLS config + HSTS commenté
- [Source: idp-portal/django_backend/tests/security/] — Tests sécurité existants (154 tests)
- [Source: idp-portal/docs/security-audit-report.md] — Rapport audit Story 15.1
- [Source: idp-portal/docs/security-remediation-plan.md] — Plan remédiation
- [Source: idp-portal/database/init/01-create-idp-app-user.sql] — Grants user DB

### Intelligence des stories précédentes (15.1 & 15.2)

**Outils configurés dans 15.1 :**
- Bandit (SAST Python) — via pyproject.toml, CI/CD intégré
- pip-audit (dépendances Python) — rapports JSON/MD
- detect-secrets — baseline `.secrets.baseline`, pre-commit hook
- ESLint security — plugins eslint-plugin-security + eslint-plugin-react
- Rapports consolidés : script `scripts/consolidate-security-reports.py`

**Tests implémentés dans 15.2 :**
- 52 tests authentification (JWT, refresh, expiration, bypass)
- 34 tests autorisation RBAC (profils, accès admin, 403/401)
- 27 tests contrôle granulaire (action/target/env, multi-profils)
- 24 tests endpoints sensibles (exécution RBAC, audit isolation)
- 17 tests headers sécurité (nosniff, DENY, correlation_id)
- CI/CD : job `security-functional-tests`, 100% pass requis

**Insights critiques :**
- Les tests SQLite (test_settings.py) fonctionnent bien pour les tests de sécurité — pas besoin d'Oracle
- Les factories (`tests/factories.py`) couvrent tous les modèles
- Le conftest security (`tests/security/conftest.py`) fournit des fixtures JWT réelles

### Git Intelligence

**Commits récents pertinents :**
- `117fbe0` Push everything (dernier état)
- Story 15.2 : 154 tests sécurité créés et intégrés CI/CD
- Story 15.1 : outils SAST, pip-audit, detect-secrets configurés
- Epic M (m-8) : middleware logging structuré, health check étendu, CORS

**Patterns établis :**
- Tests Django : `pytest-django` avec `test_settings.py` (SQLite in-memory)
- Fixtures : factory_boy dans `tests/factories.py`
- Structure tests : `tests/security/test_*.py` avec conftest spécialisé
- CI/CD : jobs séparés par domaine dans `ci.yml`

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- 23/23 SOC1 compliance tests pass (test_soc1_compliance.py, incl. filtre env + masquage erreurs 500)
- Tests SOC1 inclus dans CI (marqueur @pytest.mark.security)
- 175+ security tests pass (no regression)
- detect-secrets scan: 0 secrets detected

### Completion Notes List

- **Task 1**: Défense en profondeur pour immutabilité AUDIT_LOG — trigger Oracle V054 + Django model save()/delete() override + ImmutableQuerySet
- **Task 2**: 6 tests d'immutabilité couvrant update, delete, save existant, create, bulk delete, all delete
- **Task 3**: 6 tests traçabilité — champs complets, correlation_id, filtres par environnement/type/date, lifecycle complet
- **Task 4**: Settings production Django (SECURE_SSL_REDIRECT, HSTS, cookies secure) + HSTS Nginx décommenté
- **Task 5**: 4 tests gestion secrets + detect-secrets scan confirmant NFR7
- **Task 6**: 4 tests protection données sensibles (dont erreurs 500 sans infos sensibles) + classification CLOB documentée
- **Task 7**: Rapport SOC1 complet avec 7 contrôles, matrice traçabilité, preuves 15.1/15.2, écarts documentés

### File List

_Note : cette liste est limitée aux fichiers modifiés ou créés pour la story 15.3 ; d’autres changements du dépôt (ex. autres stories, CI) ne sont pas listés ici._

**Nouveaux fichiers :**
- `idp-portal/database/migrations/V054__audit_log_immutable_trigger.sql` — Trigger Oracle immutabilité AUDIT_LOG
- `idp-portal/django_backend/tests/security/test_soc1_compliance.py` — 23 tests SOC1 (AC1-AC5), marqueur security pour CI
- `idp-portal/docs/soc1-compliance-report.md` — Document conformité SOC1 (AC6)

**Fichiers modifiés :**
- `idp-portal/django_backend/core/models.py` — ImmutableQuerySet + save()/delete() overrides sur AuditLog
- `idp-portal/django_backend/idp_backend/settings.py` — Settings sécurité production (if not DEBUG)
- `idp-portal/django_backend/deployment/nginx-django.conf` — HSTS activé

### Change Log

- 2026-02-06: Story 15.3 implémentée — Validation conformité SOC1 complète (7 tâches, 21 tests, rapport SOC1)
- 2026-02-06: Code review (adversarial) — 8 findings traités : test_audit_filter_by_environment (Task 3.3), pytest.mark.security (CI), test Vault NFR21 renforcé, test production settings durci, AuditLog.save() simplifié, rapport SOC1 et File List mis à jour. LOW : test_unhandled_exception_masks_internal_details (500), note File List limitée (23 tests)
