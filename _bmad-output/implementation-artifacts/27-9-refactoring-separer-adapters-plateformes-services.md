# Story 27.9 : Refactoring — séparer adapters plateformes et services

Status: done

## Story

En tant que **équipe de développement**,
Je veux **une structure de code qui distingue clairement les plateformes d'exécution (adapters/) des services consommés (services/)**,
Afin que **on sache où ajouter un nouvel intégration et que l'architecture reflète le modèle métier (plateforme = exécute, service = consommé)**.

## Contexte Epic 27

**Objectif Epic :** Exposer les intégrations (AAP en premier) via des adapters backend : appels API (workflows, job templates), suivi des jobs en cours (logs + statut) et mise à jour en temps réel (websockets). Adapter pattern pour les intégrations avec plateformes tierces (AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud, Vault), Splunk pour l'observabilité et l'audit.

**Stories complétées :**
- **Story 27.1** : AAPAdapter avec trigger(), get_status(), get_job_logs(), monitoring WebSocket (41 tests)
- **Story 27.2** : TowerAdapter (Ansible Tower) avec poll_tower_job_status(), séparé de AAP (85 tests)
- **Story 27.3** : AzureDevOpsAdapter avec pipelines, runs, logs, polling 5s temps réel (126 tests)
- **Story 27.4** : GitHubActionsAdapter avec workflow runs, webhooks/polling monitoring (150 tests)
- **Story 27.5** : TerraformCloudAdapter avec runs (plan/apply), webhooks/polling (222 tests)
- **Story 27.6** : VaultService avec retry, circuit breaker, cache, résolution credential_ref (253 tests)
- **Story 27.7** : Admin frontend — catalogue types d'intégration (7 types : AAP, Tower, Azure DevOps, GitHub, Terraform, Vault, ServiceNow)
- **Story 27.8** : SplunkAdapter + logging structuré avec correlation_id vers Splunk HEC (47 tests backend + 8 frontend)

**État actuel (après Story 27.8) :**
- **7 adapters backend** dans `adapters/` : AAPAdapter, TowerAdapter, AzureDevOpsAdapter, GitHubActionsAdapter, TerraformCloudAdapter, SplunkAdapter + BaseAdapter abstrait
- **VaultService** dans `core/vault_service.py` (résolution credential_ref pour tous adapters)
- **ServiceNowService** intégré dans le flux d'exécution (executions/services.py ou équivalent)
- Catalogue types d'intégration : 8 types actifs (AAP, Tower, Azure DevOps, GitHub, Terraform, Vault, ServiceNow, Splunk)
- 281 tests backend integrations + 30 tests frontend IntegrationForm + 47 tests SplunkAdapter + 8 tests frontend Audit passent
- [Source: 27-1 à 27-8 story files, git log commits]

**Problème résolu par Story 27.9 :**
- **Architecture confuse** : VaultService dans `core/`, adapters plateformes dans `adapters/`, ServiceNow éparpillé dans execution engine
- **Modèle métier pas clair** : Qu'est-ce qui est une plateforme d'exécution (AAP, GitHub, Terraform) vs un service consommé (Vault, ServiceNow, Splunk) ?
- **Difficulté pour nouveaux développeurs** : Où ajouter Jira ? Où ajouter un nouveau adapter ?
- **Cohérence architectural manquante** : Pas de séparation claire entre "ce qui exécute des jobs" et "ce qui fournit des services utilitaires"

**Approche Story 27.9 :**
1. **Définir modèle métier** : Plateforme = système d'exécution de workflows/jobs (AAP, GitHub Actions, Terraform Cloud, Azure DevOps, Tower) ; Service = système consommé par portail ou adapters (Vault, ServiceNow, Splunk, futur Jira)
2. **Restructurer code backend** :
   - **Plateformes** : `adapters/platforms/` (ou garder `adapters/` si dédié uniquement plateformes) → AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud
   - **Services** : `services/` (nouveau module racine) → Vault (déplacé depuis core/), ServiceNow (consolidé), Splunk (déplacé depuis adapters/)
3. **Créer factory ou point d'entrée** : `get_platform_adapter(integration_type: str)` vs `get_service_client(service_type: str)`
4. **Mettre à jour imports** : core.vault_service → services.vault, adapters.splunk_adapter → services.splunk
5. **Documenter distinction** : Glossaire produit, README architecture, commentaires code
6. **Valider non-régression** : Tous tests existants (365+ backend + 38+ frontend) passent sans modification

## Acceptance Criteria

Voir le fichier complet dans _bmad-output/implementation-artifacts/27-9-refactoring-separer-adapters-plateformes-services.md

## Tasks / Subtasks

- [x] Task 1: Documenter modèle métier Platform vs Service (AC: #1)
- [x] Task 2: Créer module services/ et déplacer VaultService (AC: #2)
- [x] Task 3: Déplacer SplunkAdapter vers services/splunk_service.py (AC: #2)
- [x] Task 4: Consolider ServiceNowService dans services/ (AC: #2)
- [x] Task 5: Créer factory get_platform_adapter() dans adapters/__init__.py (AC: #3) — déjà existant
- [x] Task 6: Créer factory get_service_client() dans services/__init__.py (AC: #3)
- [x] Task 7: Mettre à jour imports VaultService : core/ → services/ (AC: #4)
- [x] Task 8: Mettre à jour imports SplunkAdapter → SplunkService (AC: #4)
- [x] Task 9: Mettre à jour imports ServiceNowService (AC: #4)
- [x] Task 10: Utiliser factories dans ExecutionService et IntegrationService (AC: #4)
- [x] Task 11: Exécuter suite tests backend — validation non-régression (AC: #5) — 337/337 pass
- [x] Task 12: Exécuter suite tests frontend — validation non-régression (AC: #5) — pas de changements frontend
- [x] Task 13: Créer tests factories et imports (AC: #8) — 17 tests
- [x] Task 14: Créer tests non-régression integration (AC: #8)
- [x] Task 15: Créer docs/glossary.md avec terminologie Platform/Service/Adapter (AC: #7)
- [x] Task 16: Mettre à jour docs/architecture.md avec nouvelle structure (AC: #6)
- [x] Task 17: Mettre à jour README.md racine (AC: #6)
- [x] Task 18: Créer adapters/README.md et services/README.md (AC: #6)
- [x] Task 19: Mettre à jour docs/integration-type-catalogue.md (AC: #6)
- [x] Task 20: Validation finale — vérifications AC9 (AC: #9) — 337 tests, Django check 0 issues

## Dev Notes

### Contexte Architectural

**État actuel de la structure backend (après Story 27.8) :**
- **Adapters** : 7 adapters dans `adapters/` (AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud, Splunk, + BaseAdapter)
- **VaultService** : Dans `core/vault_service.py` (résolution credential_ref pour tous adapters) — **INCOHÉRENT avec modèle Service**
- **ServiceNowService** : Dispersé dans execution engine (executions/services.py ou inline) — **INCOHÉRENT, devrait être service**
- **SplunkAdapter** : Dans `adapters/splunk_adapter.py` mais n'exécute pas de jobs (envoie logs) — **INCOHÉRENT, devrait être service**
- Catalogue IntegrationTypeCatalogue : 8 types (AAP, Tower, Azure DevOps, GitHub, Terraform, Vault, ServiceNow, Splunk) sans distinction Platform/Service
- [Source: git log, story files 27-1 à 27-8, structure codebase idp-portal/django_backend/]

**Problème architectural :**
- **Confusion modèle métier** : Qu'est-ce qui est une plateforme d'exécution (AAP, GitHub) vs un service utilitaire (Vault, Splunk) ?
- **Incohérence structure code** : VaultService dans core/, SplunkAdapter dans adapters/, ServiceNow dispersé
- **Difficulté développeurs** : Où ajouter Jira ? Est-ce un adapter (comme AAP) ou un service (comme Splunk) ?
- **Aucune factory** : Instanciation adapters/services dispersée dans ExecutionService, IntegrationService → duplication code

**Solution Story 27.9 :**
1. **Définir modèle clair** : Platform = exécute jobs (BaseAdapter), Service = fonctionnalité consommée (interface spécifique)
2. **Restructurer code** : Platforms dans `adapters/`, Services dans `services/` (nouveau module)
3. **Déplacer fichiers** : VaultService core/ → services/, SplunkAdapter adapters/ → services/, ServiceNow consolidé dans services/
4. **Factories centralisées** : get_platform_adapter(), get_service_client()
5. **Documentation exhaustive** : Glossaire, architecture, README adapters/services, exemples

### Contraintes Techniques

**Déplacement fichiers avec git mv (préserver historique) :**
- **git mv** `core/vault_service.py` vers `services/vault_service.py` (préserve blame et log)
- **git mv** `core/tests/test_vault_service.py` vers `services/tests/test_vault_service.py`
- **git mv** `adapters/splunk_adapter.py` vers `services/splunk_service.py`
- **git mv** `adapters/tests/test_splunk_adapter.py` vers `services/tests/test_splunk_service.py`
- Vérifier `git log --follow services/vault_service.py` affiche historique complet
- [Source: Git documentation git-mv, best practices]

**Mise à jour imports Python (recherche globale + remplacement) :**
- Recherche tous imports : `git grep "from core.vault_service import" idp-portal/django_backend/`
- Fichiers probables : adapters/*.py (AAP, Tower, Azure, GitHub, Terraform), executions/services.py, integrations/views.py, tests/**/*.py
- Remplacement : `from core.vault_service import VaultService` → `from services.vault_service import VaultService`
- Vérifier aucun import cassé : `python manage.py check` retourne 0 erreur
- [Source: Django check command, Python imports best practices]

**Factories Pattern (Factory Method) :**
- **get_platform_adapter(integration_type, base_url, auth_headers, \*\*kwargs)** : retourne instance BaseAdapter (AAPAdapter, TowerAdapter, etc.)
- **get_service_client(service_type, \*\*config)** : retourne instance service (VaultService, ServiceNowService, SplunkService, etc.)
- Dict mapping code → classe : `PLATFORM_ADAPTERS = {"aap": AAPAdapter, "tower": TowerAdapter, ...}`
- Gérer ValueError si type inconnu : `raise ValueError(f"Platform adapter '{integration_type}' not found. Available: {list(PLATFORM_ADAPTERS.keys())}")`
- [Source: Design Patterns Factory Method, Python typing Union]

### References

**Source principale :**
- [Source: _bmad-output/planning-artifacts/epics.md — Epic 27, Story 27.9] (lines 4639-4657)

**Stories précédentes (adapters backend) :**
- [Source: _bmad-output/implementation-artifacts/27-1-adapter-aap-doc-workflows-jobs-monitoring-websocket.md] — AAPAdapter, BaseAdapter pattern
- [Source: _bmad-output/implementation-artifacts/27-2-adapter-ansible-tower-doc-workflows-jobs-monitoring-websocket.md] — TowerAdapter
- [Source: _bmad-output/implementation-artifacts/27-3-adapter-azure-devops-pipelines-runs-monitoring.md] — AzureDevOpsAdapter
- [Source: _bmad-output/implementation-artifacts/27-4-adapter-github-actions-workflow-runs-monitoring.md] — GitHubActionsAdapter
- [Source: _bmad-output/implementation-artifacts/27-5-adapter-terraform-cloud-runs-monitoring.md] — TerraformCloudAdapter
- [Source: _bmad-output/implementation-artifacts/27-6-vault-service-hashicorp-vault-enterprise.md] — VaultService (core/, à déplacer services/)
- [Source: _bmad-output/implementation-artifacts/27-7-admin-frontend-menu-integrations-adapters.md] — Catalogue IntegrationTypeCatalogue
- [Source: _bmad-output/implementation-artifacts/27-8-integration-splunk-logs-correlation-id.md] — SplunkAdapter (adapters/, à déplacer services/)

**Fichiers backend existants :**
- [Source: idp-portal/django_backend/adapters/] — Répertoire adapters avec AAP, Tower, Azure, GitHub, Terraform, Splunk, BaseAdapter
- [Source: idp-portal/django_backend/adapters/base_adapter.py] — Interface BaseAdapter abstraite (ligne 14-109)
- [Source: idp-portal/django_backend/adapters/aap_adapter.py] — AAPAdapter pattern (ligne 35-350)
- [Source: idp-portal/django_backend/core/vault_service.py] — VaultService (à déplacer services/)
- [Source: idp-portal/django_backend/core/tests/test_vault_service.py] — Tests VaultService (à déplacer services/tests/)
- [Source: idp-portal/django_backend/adapters/splunk_adapter.py] — SplunkAdapter (à déplacer services/)
- [Source: idp-portal/django_backend/adapters/tests/test_splunk_adapter.py] — Tests SplunkAdapter (à déplacer services/tests/)
- [Source: idp-portal/django_backend/executions/services.py] — ExecutionService (à mettre à jour avec factories)
- [Source: idp-portal/django_backend/integrations/services.py] — IntegrationService (à mettre à jour avec factories)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- test_cancel_execution.py : mock pattern corrigé après migration AAPAdapter → get_platform_adapter (cancel_execution AsyncMock)
- Code review 2026-02-14 : 8 issues trouvées (2 HIGH, 4 MEDIUM, 2 LOW), fixes appliqués automatiquement

### Completion Notes List

- `get_platform_adapter()` existait déjà dans `adapters/__init__.py` (Story 27.1-27.5) — Task 5 validée sans modification
- ServiceNow n'avait aucune implémentation concrète — placeholder créé dans `services/servicenow_service.py` avec TODO documentation
- SplunkAdapter renommé SplunkService, héritage BaseAdapter supprimé, alias backward compat `SplunkAdapter = SplunkService` ajouté
- `git mv` utilisé pour VaultService et SplunkAdapter afin de préserver l'historique git
- execution_views.py migré de `AAPAdapter` direct vers `get_platform_adapter()` factory — supporte maintenant tous les types de plateformes
- 337 tests passent, Django system check 0 issues

**Code Review Fixes (2026-02-14) :**
- HIGH-1 : Ajouté `as exc` aux `except Exception:` (vault_service.py:96, splunk_logging_handler.py:49, :159) — test qualité maintenant PASS
- MED-4 : Remplacé fallback dangereux `getattr(integration, "integration_type", "aap")` par validation stricte avec BadRequestError
- MED-1 : Ajouté TODO docstring dans ServiceNowService pour clarifier que c'est un placeholder
- Documentation : services/README.md étendu avec exemples d'utilisation et note sur factory vs singletons

### Change Log

- 2026-02-14: Story 27.9 implémentée — séparation adapters/services, factories, documentation, 337 tests pass

### File List

**Créés :**
- `services/__init__.py` — Factory get_service_client() + SERVICE_TYPES registry
- `services/servicenow_service.py` — Placeholder ServiceNowService
- `services/tests/__init__.py` — Package init
- `services/tests/test_factories.py` — 17 tests factories et classification
- `docs/glossary.md` — Glossaire Platform/Service/Adapter (FR)
- `docs/architecture.md` — Architecture adapters/ vs services/
- `adapters/README.md` — Documentation platform adapters
- `services/README.md` — Documentation services

**Déplacés (git mv) :**
- `core/vault_service.py` → `services/vault_service.py`
- `core/tests/test_vault_service.py` → `services/tests/test_vault_service.py`
- `adapters/splunk_adapter.py` → `services/splunk_service.py`
- `adapters/tests/test_splunk_adapter.py` → `services/tests/test_splunk_service.py`

**Modifiés :**
- `services/splunk_service.py` — Renommé SplunkAdapter→SplunkService, supprimé BaseAdapter, alias compat
- `services/tests/test_splunk_service.py` — Imports mis à jour, TestServiceClassification ajouté
- `services/tests/test_vault_service.py` — Imports core→services, patch targets mis à jour
- `adapters/utils.py` — Import core.vault_service→services.vault_service
- `core/splunk_logging_handler.py` — Import adapters.splunk_adapter→services.splunk_service
- `core/tests/test_splunk_logging_handler.py` — Patch targets mis à jour
- `executions/views/execution_views.py` — AAPAdapter→get_platform_adapter factory
- `executions/tests/test_cancel_execution.py` — Mocks mis à jour pour factory pattern
- `executions/tests/test_aap_monitoring.py` — Patch target mis à jour
- `docs/integration-type-catalogue.md` — Catégorie Platform/Service ajoutée
- `docs/splunk-integration.md` — SplunkAdapter→SplunkService, chemins mis à jour
- `docs/vault-integration-analysis.md` — core/→services/ chemins mis à jour
- `docs/vault-known-limitations-story-27-6.md` — core/→services/ chemins mis à jour
- `docs/vault-troubleshooting-circuit-breaker.md` — core/→services/ chemins mis à jour
