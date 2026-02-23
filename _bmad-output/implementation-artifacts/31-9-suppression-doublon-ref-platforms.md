# Story 31.9 : Suppression du doublon REF_PLATFORMS

Status: done

<!-- Réf: _bmad-output/implementation-artifacts/analyse-facilite-integrations-adapters.md §7. Prérequis : 31.1 done (formulaire action alimenté par les intégrations). -->

## Story

En tant que développeur,
je veux supprimer la table REF_PLATFORMS (RefPlatform),
afin d'avoir une seule source de vérité pour les types de plateforme (IntegrationTypeCatalogue + intégrations) et d'éviter la double maintenance.

## Acceptance Criteria

1. **Given** une action avec une intégration (integration_id) sélectionnée
   **When** on valide ou exécute l'action
   **Then** la validation et le runtime utilisent le type d'intégration (Integration.type / IntegrationTypeCatalogue), pas RefPlatform

2. **And** l'API `GET /api/v1/reference/platforms` est supprimée ou redirige vers les types d'intégration (filtrés par rôle plateforme) depuis IntegrationTypeCatalogue

3. **And** plus aucun code ne lit ni n'écrit la table REF_PLATFORMS / le modèle RefPlatform

4. **And** une migration Django supprime le modèle RefPlatform et une migration Flyway supprime la table REF_PLATFORMS

5. **And** le test `test_mapping_covers_all_platform_types` est retiré ou réécrit sans dépendance à RefPlatform

## Tasks / Subtasks

### Task 1 — Remplacer la validation `validate_platform` dans les serializers (AC: #1)

- [x] 1.1 — Dans `catalog/serializers.py`, remplacer les deux `validate_platform()` pour valider contre `IntegrationTypeCatalogue` (role=platform, is_active=True). Import `RefPlatform` supprimé. Ajout `_PLATFORM_ALIAS` pour résolution `terraform` → `terraform_cloud`.
- [x] 1.2 — `_validate_platform_integration_consistency()` : dict `expected_platforms` hardcodé supprimé, dérivation depuis `integration_type_cat.name`.
- [x] 1.3 — Bug latent fixé dans `workflow_runtime.py` : `platform_type = integration.type` au lieu de `referenced_action.platform.lower()`.

### Task 2 — Remplacer l'API reference/platforms (AC: #2)

- [x] 2.1 — `reference/views.py` : `list_platforms()` requête `IntegrationTypeCatalogue` filtré par `integration_role=PLATFORM`. Format compatible `{"data": [...]}`.
- [x] 2.2 — `RefPlatformSerializer` supprimé, `PlatformTypeCatalogueSerializer` créé avec `label=source('name')`, `normalized_code=source('code')`.
- [x] 2.3 — Import `RefPlatform` supprimé de `reference/views.py`.
- [x] 2.4 — Frontend : `usePlatforms.ts` supprimé, `fetchPlatforms()` + interface `RefPlatform` supprimés de `reference_service.ts`, `PLATFORM_OPTIONS_DEPRECATED` supprimé de `actionOptions.ts`.

### Task 3 — Supprimer les usages résiduels (AC: #3)

- [x] 3.1 — `business_rule_views.py` : `_PLATFORM_TO_STEP_TYPE` remplacé par `_PLATFORM_ALIAS` + normalisation.
- [x] 3.2 — `catalog/models.py` : `help_text` du champ `platform` mis à jour.
- [x] 3.3 — Grep exhaustif : aucun import `RefPlatform` restant (uniquement commentaires et migrations).
- [x] 3.4 — `RefPlatform`, `RefPlatformQuerySet`, `RefPlatformManager` supprimés de `reference/models.py`.
- [x] 3.5 — Docstring `reference/__init__.py` mis à jour.

### Task 4 — Migrations (AC: #4)

- [x] 4.1 — Migration Flyway `V083__drop_ref_platforms.sql` créée.
- [x] 4.2 — Migration Django `reference/migrations/0005_delete_refplatform.py` créée (dépend de `0004`, pas `0001`).

### Task 5 — Tests (AC: #5, #1, #2, #3)

- [x] 5.1 — `test_mapping_covers_all_platform_types` supprimé.
- [x] 5.2 — `RefPlatformModelTests` supprimé de `test_models.py`.
- [x] 5.3 — `RefPlatformsAPITests` remplacé par `PlatformTypeCatalogueAPITests` dans `test_views.py`.
- [x] 5.4 — 8 fichiers de test mis à jour (RefPlatform → IntegrationTypeCatalogue).
- [x] 5.5 — 3 tests ajoutés dans `test_validation.py` : codes normalisés, alias Terraform, rejet service.
- [x] 5.6 — Couvert par `PlatformTypeCatalogueAPITests` (6 tests : active_only, all, ordered, auth, fields, data wrapper).
- [x] 5.7 — Grep final : seuls commentaires et migrations restent.

## Dev Notes

### Bug latent corrigé par cette story

`workflow_runtime.py` ligne ~879 utilise `referenced_action.platform.lower()` pour résoudre l'adapter. Pour `"GitHub Actions"`, cela donne `"github actions"` au lieu de `"github_actions"` (clé du registry). Les execution_views font correctement `integration.type` (déjà normalisé). Cette story unifie le runtime pour utiliser `integration.type` partout.

### Modèle cible après cette story

```
Action.platform (CharField, conservé pour rétrocompat)
    ↕ cross-validé avec :
Integration.type (ex. "github_actions")
    → IntegrationTypeCatalogue.code (PK, ex. "github_actions", role=PLATFORM)
    → adapter_registry.get("github_actions")
```

`Action.platform` reste en base (pas de migration de suppression de colonne — une story future peut le déprécier entièrement). La validation s'appuie sur le catalogue au lieu de la table REF_PLATFORMS.

### Fichiers clés à modifier

| Fichier | Changement |
|---------|-----------|
| `catalog/serializers.py` | `validate_platform()` → IntegrationTypeCatalogue ; supprimer import RefPlatform ; mettre à jour `_validate_platform_integration_consistency()` |
| `catalog/views/business_rule_views.py` | `_PLATFORM_TO_STEP_TYPE` → dérivation catalogue |
| `catalog/models.py` | Mettre à jour help_text du champ platform |
| `executions/workflow_runtime.py` | `platform_type` depuis `integration.type` au lieu de `action.platform.lower()` |
| `reference/models.py` | Supprimer RefPlatform, RefPlatformQuerySet, RefPlatformManager |
| `reference/serializers.py` | Supprimer RefPlatformSerializer, ajouter PlatformTypeCatalogueSerializer |
| `reference/views.py` | Remplacer list_platforms() → IntegrationTypeCatalogue filtré |
| `reference/urls.py` | Garder le path inchangé (rétrocompat URL) |
| `frontend/src/hooks/usePlatforms.ts` | Supprimer |
| `frontend/src/services/reference_service.ts` | Supprimer RefPlatform interface + fetchPlatforms() |
| `frontend/src/utils/actionOptions.ts` | Supprimer PLATFORM_OPTIONS_DEPRECATED |

### Migrations

| Fichier | Contenu |
|---------|---------|
| `database/migrations/V083__drop_ref_platforms.sql` | `DROP TABLE REF_PLATFORMS` |
| `reference/migrations/0002_delete_refplatform.py` | `DeleteModel(name='RefPlatform')` |

**V082** = dernière migration Flyway (Story 31.8). **0001** = dernière migration Django reference.

### IntegrationTypeCatalogue — codes plateforme existants

Codes du catalogue avec `integration_role=platform` (source : fixtures + seed) :

| code | name |
|------|------|
| `aap` | AAP (Ansible Automation Platform) |
| `tower` | Ansible Tower |
| `github_actions` | GitHub Actions |
| `azure_devops` | Azure DevOps |
| `terraform_cloud` | Terraform Cloud |

Ces codes sont déjà les clés du registry d'adapters (`adapters/__init__.py`). La normalisation `Action.platform.lower().replace(' ', '_')` produit exactement ces codes.

### Correspondance REF_PLATFORMS ↔ IntegrationTypeCatalogue

| REF_PLATFORMS.code | IntegrationTypeCatalogue.code |
|---|---|
| `AAP` | `aap` |
| `Tower` | `tower` |
| `GitHub Actions` | `github_actions` |
| `Azure DevOps` | `azure_devops` |
| `Terraform` | *(pas d'équivalent direct — historique)* |
| `Terraform Cloud` | `terraform_cloud` |

**Note** : `Terraform` (V051, code original) est un alias historique pour `Terraform Cloud` (V073). Le catalogue n'a que `terraform_cloud`. Les actions avec `platform='Terraform'` devront être migrées ou la validation doit accepter `terraform` → `terraform_cloud`.

### Contraintes et risques

1. **Oracle DDL** : `DROP TABLE REF_PLATFORMS` est irréversible. S'assurer que toutes les actions utilisent `integration_id` avant la migration. En cas de doute, ajouter un check pré-migration.
2. **Rétrocompatibilité API** : L'URL `GET /api/v1/reference/platforms` est conservée mais retourne les types du catalogue. Les clients existants (s'il y en a) reçoivent un format compatible.
3. **Tests** : 10+ fichiers de test créent des `RefPlatform` en setUp. Chaque setUp doit être mis à jour. Utiliser une factory ou fixture `IntegrationTypeCatalogue` partagée.
4. **`Action.platform` conservé** : La colonne reste en base — la suppression complète du champ `platform` est hors scope (story future). On ne touche pas au schéma de `ACTIONS_CATALOG`.
5. **`Terraform` vs `Terraform Cloud`** : Si des actions existantes ont `platform='Terraform'`, la normalisation `.lower()` donne `"terraform"` ≠ `"terraform_cloud"`. Ajouter un mapping d'alias dans la validation : `{"terraform": "terraform_cloud"}`.

### Intelligence de la story précédente (31.8)

- Story 31.8 a ajouté V082 (migration Flyway) et migration Django 0011. V083 est le prochain numéro Flyway disponible.
- Pattern de factory services/ bien établi (`get_service_client()`, `SERVICE_TYPES`, registry).
- `OracleJSONField` utilisé pour les champs JSON (gate_config, notification_config).
- Tests structurés avec mocks : `@patch` pour les appels externes, `MagicMock` pour les objets.
- Code review adversarial a trouvé 6 issues (dont H1: httpx dans transaction.atomic) — attention aux patterns similaires.

### Contexte git récent

Les 5 derniers commits (Epic 33 — conformité SOLID) montrent :
- Pattern registry OCP bien en place (Story 33.1)
- Découpage en sous-modules (Stories 33.2, 33.3, 33.5)
- Injection de dépendances via constructeur (Story 33.4)
- Le codebase est en phase de nettoyage SOLID — cette story s'inscrit dans cette dynamique.

### Project Structure Notes

- Alignement avec la structure modulaire : les vues catalog sont dans `catalog/views/` (package), les vues exécution dans `executions/views/` (package)
- Le registry d'adapters est dans `adapters/registry.py`, factory dans `adapters/__init__.py`
- `IntegrationTypeCatalogue` est dans `integrations/models.py`
- `reference/` est un module Django dédié aux tables de référence (engines, platforms, categories)

### References

- [Source: _bmad-output/implementation-artifacts/analyse-facilite-integrations-adapters.md#7-REF_PLATFORMS-doublon-inutile]
- [Source: _bmad-output/planning-artifacts/epic-31-admin-catalogue-integrations-et-icones-moteurs.md#Story-31.9]
- [Source: django_backend/reference/models.py] — Modèle RefPlatform à supprimer (lignes 50–86)
- [Source: django_backend/catalog/serializers.py] — validate_platform() à remplacer (lignes 260, 499) + _validate_platform_integration_consistency() (lignes 23–75)
- [Source: django_backend/executions/workflow_runtime.py] — platform_type résolu depuis action.platform (ligne ~879)
- [Source: django_backend/executions/views/execution_views.py] — platform_type résolu depuis integration.type (lignes 372, 543)
- [Source: django_backend/reference/views.py] — list_platforms() endpoint (lignes 61–91)
- [Source: django_backend/integrations/models.py] — IntegrationTypeCatalogue, IntegrationRole
- [Source: django_backend/catalog/views/business_rule_views.py] — _PLATFORM_TO_STEP_TYPE mapping (lignes 25–32)
- [Source: django_backend/catalog/tests/test_action_platform_integration_validation.py] — test_mapping_covers_all_platform_types (lignes 274–291)
- [Source: _bmad-output/implementation-artifacts/31-8-service-notification-multi-destinations-email-teams-page.md] — Story précédente (patterns, migrations)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- Bug latent fixé : `workflow_runtime.py` utilisait `platform.lower()` → `"github actions"` ≠ `"github_actions"`. Corrigé en dérivant `platform_type` depuis `integration.type`.
- Alias `_PLATFORM_ALIAS` ajouté pour `terraform` → `terraform_cloud` (rétrocompat actions historiques).
- Migration Django numérotée `0005` (pas `0002` comme prévu dans la story) car des migrations `0002`–`0004` existent déjà.
- 158 tests passent (68 + 80 + 10 sur les fichiers de test concernés).

### File List

| Fichier | Changement |
|---------|-----------|
| `django_backend/catalog/serializers.py` | `validate_platform()` × 2 → IntegrationTypeCatalogue ; `_validate_platform_integration_consistency()` simplifié ; import RefPlatform supprimé |
| `django_backend/executions/workflow_runtime.py` | `platform_type = integration.type` (bug fix) |
| `django_backend/reference/views.py` | `list_platforms()` → IntegrationTypeCatalogue filtré |
| `django_backend/reference/serializers.py` | `RefPlatformSerializer` → `PlatformTypeCatalogueSerializer` |
| `django_backend/reference/models.py` | `RefPlatform`, `RefPlatformQuerySet`, `RefPlatformManager` supprimés |
| `django_backend/reference/__init__.py` | Docstring mis à jour |
| `django_backend/catalog/views/business_rule_views.py` | `_PLATFORM_TO_STEP_TYPE` → `_PLATFORM_ALIAS` + normalisation |
| `django_backend/catalog/models.py` | `help_text` champ `platform` mis à jour |
| `django_backend/reference/migrations/0005_delete_refplatform.py` | Migration Django suppression RefPlatform |
| `database/migrations/V083__drop_ref_platforms.sql` | Migration Flyway DROP TABLE REF_PLATFORMS |
| `frontend/src/hooks/usePlatforms.ts` | Supprimé |
| `frontend/src/services/reference_service.ts` | `RefPlatform` interface + `fetchPlatforms()` supprimés |
| `frontend/src/utils/actionOptions.ts` | `PLATFORM_OPTIONS_DEPRECATED` supprimé |
| `django_backend/catalog/tests/test_validation.py` | RefPlatform → IntegrationTypeCatalogue ; 3 tests ajoutés (5.5) |
| `django_backend/catalog/tests/test_action_platform_integration_validation.py` | RefPlatform supprimé ; `test_mapping_covers_all_platform_types` supprimé |
| `django_backend/reference/tests/test_views.py` | `RefPlatformsAPITests` → `PlatformTypeCatalogueAPITests` |
| `django_backend/reference/tests/test_models.py` | `RefPlatformModelTests` supprimé |
| `django_backend/catalog/tests/test_admin_views.py` | RefPlatform → IntegrationTypeCatalogue |
| `django_backend/catalog/tests/test_business_rule_policies_api.py` | RefPlatform → IntegrationTypeCatalogue |
| `django_backend/catalog/tests/test_story_25_4_validators.py` | RefPlatform → IntegrationTypeCatalogue |
| `django_backend/catalog/tests/test_workflow_steps_integration.py` | RefPlatform → IntegrationTypeCatalogue |
| `django_backend/reference/tests/test_categories.py` | RefPlatform → IntegrationTypeCatalogue |
| `django_backend/core/tests/test_api_response_format.py` | RefPlatform → IntegrationTypeCatalogue (doublon corrigé) |
| `django_backend/docs/standards/endpoint-checklist.md` | [Code Review] RefPlatform → IntegrationTypeCatalogue |
| `django_backend/tests/README.md` | [Code Review] PIÈGE 9 : RefPlatform → IntegrationTypeCatalogue |
| `django_backend/tests/KNOWN_ISSUES.md` | [Code Review] RefPlatform → IntegrationTypeCatalogue |

### Code Review — Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.6 — 2026-02-21
**Verdict:** APPROVED with fixes applied

**Findings corrigés :**
- **M1** (MEDIUM) — Documentation stale : 5 fichiers docs/tests référençaient encore RefPlatform/REF_PLATFORMS → corrigé (endpoint-checklist, README, KNOWN_ISSUES)
- **M2** (MEDIUM) — `_PLATFORM_ALIAS` dupliqué avec valeurs différentes entre serializers.py et business_rule_views.py → centralisé dans serializers.py, importé par business_rule_views.py. Alias `tower→aap` ajouté au dict canonical.
- **L1** (LOW) — Docstring stale test_validation.py → corrigé

**Findings non corrigés (by design) :**
- **M3→L** — `validate_platform` retourne la valeur non-normalisée : intentionnel (contrainte CHECK Oracle sur ACTIONS_CATALOG.PLATFORM)
- **L2** — `PlatformTypeCatalogueSerializer.normalized_code` redondant : acceptable pour rétrocompat format API
- **L3** — Migration Flyway sans CASCADE : pattern standard Flyway

**Change Log :**
- 2026-02-21 : Code review adversariale — 3 fixes appliqués (M1, M2, L1)
