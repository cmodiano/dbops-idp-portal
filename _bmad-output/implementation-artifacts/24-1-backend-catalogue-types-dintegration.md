# Story 24.1: Backend — Catalogue des types d'intégration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur backend,
Je veux définir un modèle `IntegrationType` avec catalogue d'actions supportées et exposer une API de lecture,
Afin que le frontend puisse récupérer le catalogue complet des types d'intégration valides et leurs actions, éliminant les intégrations "libres" et réduisant les erreurs de configuration.

## Contexte Epic 24

**Objectif Epic :** Encadrer la configuration des intégrations dans l'interface Admin pour n'autoriser que des types et des actions d'intégration explicitement supportés par le backend (AAP, ServiceNow, etc.), via un modèle "type d'intégration" + "instance d'intégration" et un catalogue d'actions contractuel.

**Problème résolu :**
- Actuellement, le modèle `Integration` utilise un enum `IntegrationType` (AAP, ServiceNow, Terraform, etc.) MAIS aucun catalogue formel d'actions supportées par type
- Les intégrations "libres" (type libre, config JSON libre) permettent des configurations non supportées → erreurs d'exécution
- Pas de validation contractuelle des actions disponibles par type d'intégration
- Frontend ne peut pas découvrir dynamiquement quelles actions sont valides pour un type donné

**Approche Epic :**
1. **Story 24.1 (cette story)** : Backend — Définir modèle `IntegrationType` catalogue + API lecture
2. **Story 24.2** : Frontend Admin — Restriction types actions basée sur catalogue backend
3. **Story 24.3** : Backend & Frontend — Validation état intégrations (valid/invalid/deprecated)
4. **Story 24.4** : Migration intégrations existantes + garde-fous exécution

## Acceptance Criteria

**AC1 — Modèle IntegrationType catalogue avec actions supportées**

**Given** le besoin de formaliser les types d'intégration et leurs actions
**When** le développeur crée le modèle de données
**Then** un nouveau modèle Django `IntegrationTypeCatalogue` est créé avec les champs :
- `code` (CharField, clé primaire, ex: 'aap', 'servicenow')
- `name` (CharField, ex: 'Ansible Automation Platform', 'ServiceNow ITSM')
- `description` (TextField, description du type d'intégration)
- `version` (CharField, versionnement minimal ex: '1.0', '1.1')
- `is_active` (BooleanField, permet de déprécier un type sans le supprimer)
- `created_at`, `updated_at` (DateTimeField)

**And** un modèle Django `IntegrationAction` est créé avec les champs :
- `id` (AutoField, clé primaire)
- `integration_type` (ForeignKey vers `IntegrationTypeCatalogue`, relation many-to-one)
- `action_code` (CharField, nom technique ex: 'start_job', 'create_change')
- `action_label` (CharField, label UI ex: 'Démarrer un job', 'Créer un changement')
- `description` (TextField, description de l'action)
- `required_params` (JSONField, schéma des paramètres obligatoires)
- `optional_params` (JSONField, schéma des paramètres optionnels)
- `response_format` (JSONField, description du format de réponse attendu)
- `is_active` (BooleanField)
- `created_at`, `updated_at` (DateTimeField)

**And** une migration Django `V0XX` est créée pour ces nouvelles tables `INTEGRATION_TYPE_CATALOGUE` et `INTEGRATION_ACTIONS`

**AC2 — Données initiales (fixtures) pour types AAP et ServiceNow**

**Given** les types d'intégration AAP et ServiceNow sont les plus utilisés
**When** le développeur crée les fixtures
**Then** des fixtures Django (ou script de seed) sont créées pour :

**Type AAP (code='aap') :**
- Actions supportées :
  - `start_job` : Démarrer un job template (params: `job_template_id`, `extra_vars`)
  - `start_workflow` : Démarrer un workflow job (params: `workflow_job_template_id`, `extra_vars`)
  - `get_job_status` : Récupérer le statut d'un job (params: `job_id`)
  - `cancel_job` : Annuler un job en cours (params: `job_id`)

**Type ServiceNow (code='servicenow') :**
- Actions supportées :
  - `create_change` : Créer un change request (params: `short_description`, `description`, `category`, `priority`)
  - `update_change` : Mettre à jour un change request (params: `change_id`, `state`, `work_notes`)
  - `get_change_status` : Récupérer le statut d'un change (params: `change_id`)

**And** chaque action définit son schéma `required_params` et `optional_params` en JSON Schema format

**AC3 — Repository IntegrationCatalogueRepository avec méthodes de lecture**

**Given** le besoin d'accéder aux données du catalogue
**When** le développeur crée le repository
**Then** une classe `IntegrationCatalogueRepository` est créée dans `integrations/repositories.py` avec les méthodes :
- `list_all_types()` : Liste tous les types d'intégration actifs
- `get_type_by_code(code: str)` : Récupère un type par son code
- `list_actions_by_type(type_code: str)` : Liste les actions d'un type donné
- `get_action(type_code: str, action_code: str)` : Récupère une action spécifique

**And** chaque méthode retourne des dictionnaires sérialisés ou None si non trouvé
**And** les requêtes utilisent `select_related()` / `prefetch_related()` pour optimiser les performances

**AC4 — Serializers DRF pour IntegrationTypeCatalogue et IntegrationAction**

**Given** le besoin d'exposer le catalogue via API REST
**When** le développeur crée les serializers DRF
**Then** un `IntegrationTypeCatalogueSerializer` est créé avec tous les champs du modèle
**And** un `IntegrationActionSerializer` est créé avec tous les champs du modèle
**And** un `IntegrationTypeWithActionsSerializer` est créé (nested) qui inclut :
- Tous les champs de `IntegrationTypeCatalogue`
- Un champ `actions` (liste de `IntegrationActionSerializer`)

**AC5 — API endpoint GET /api/v1/integrations/types**

**Given** le frontend a besoin de récupérer le catalogue complet
**When** un utilisateur authentifié appelle `GET /api/v1/integrations/types`
**Then** l'API retourne HTTP 200 avec un tableau JSON contenant tous les types actifs avec leurs actions
**And** la réponse utilise `IntegrationTypeWithActionsSerializer`
**And** un exemple de réponse :

```json
{
  "data": [
    {
      "code": "aap",
      "name": "Ansible Automation Platform",
      "description": "Exécution de jobs et workflows Ansible via AAP Controller",
      "version": "1.0",
      "is_active": true,
      "created_at": "2026-02-10T10:00:00Z",
      "updated_at": "2026-02-10T10:00:00Z",
      "actions": [
        {
          "id": 1,
          "action_code": "start_job",
          "action_label": "Démarrer un job",
          "description": "Lance un job template AAP avec paramètres extra_vars",
          "required_params": {"job_template_id": "integer"},
          "optional_params": {"extra_vars": "object"},
          "response_format": {"job_id": "integer", "status": "string"},
          "is_active": true
        }
      ]
    },
    {
      "code": "servicenow",
      "name": "ServiceNow ITSM",
      "description": "Gestion des change requests ServiceNow",
      "version": "1.0",
      "is_active": true,
      "actions": [...]
    }
  ]
}
```

**And** l'endpoint est documenté avec drf-spectacular (`@extend_schema`)
**And** aucune permission spéciale requise (utilisateur authentifié suffit)

**AC6 — API endpoint GET /api/v1/integrations/types/{code}**

**Given** le frontend a besoin de récupérer un type spécifique
**When** un utilisateur authentifié appelle `GET /api/v1/integrations/types/aap`
**Then** l'API retourne HTTP 200 avec les détails du type AAP et ses actions
**And** si le code n'existe pas → HTTP 404 avec message explicite
**And** l'endpoint est documenté avec drf-spectacular

**AC7 — API endpoint GET /api/v1/integrations/types/{code}/actions**

**Given** le frontend a besoin de lister uniquement les actions d'un type
**When** un utilisateur authentifié appelle `GET /api/v1/integrations/types/aap/actions`
**Then** l'API retourne HTTP 200 avec un tableau des actions de ce type
**And** utilise `IntegrationActionSerializer`
**And** si le type n'existe pas → HTTP 404

**AC8 — Tests unitaires et d'intégration**

**Given** le besoin de garantir la fiabilité du catalogue
**When** le développeur écrit les tests
**Then** au minimum 40 tests sont créés couvrant :
- **Modèles** : Création, relations ForeignKey, champs JSON, `is_active`
- **Repository** : Toutes les méthodes (list_all_types, get_type_by_code, list_actions_by_type, get_action)
- **Serializers** : Sérialisation complète, nested actions
- **API endpoints** : HTTP 200/404, structure réponse, permissions, pagination (si applicable)
- **Fixtures/seed** : Vérifier que AAP et ServiceNow sont bien créés avec actions

**And** tous les tests passent (`pytest`)
**And** couverture > 90% sur les nouveaux fichiers (models, repositories, serializers, views)

**AC9 — Documentation API et modèles**

**Given** le besoin de documenter l'architecture
**When** le développeur documente le catalogue
**Then** un fichier `docs/integration-type-catalogue.md` est créé contenant :
- Architecture du catalogue (schéma ER : IntegrationTypeCatalogue → IntegrationAction)
- Liste des types supportés (AAP, ServiceNow) et leurs actions
- Format des schémas `required_params` / `optional_params` (JSON Schema)
- Exemples d'appels API avec curl
- Guide pour ajouter un nouveau type d'intégration

**And** le README principal référence ce document

**AC10 — Audit trail création/modification types et actions**

**Given** le besoin de tracer les modifications du catalogue
**When** un type ou une action est créé/modifié (via admin Django ou fixtures)
**Then** un log d'audit est créé avec :
- `action_type` : `INTEGRATION_TYPE_CREATED`, `INTEGRATION_TYPE_UPDATED`, `INTEGRATION_ACTION_CREATED`, `INTEGRATION_ACTION_UPDATED`
- `entity_type` : `INTEGRATION_TYPE_CATALOGUE` ou `INTEGRATION_ACTION`
- `entity_id` : ID du type ou de l'action
- `user_id` : utilisateur ayant effectué la modification (si applicable)
- `correlation_id` : ID de corrélation de la requête

**And** utilise `AuditService.log()` pour créer les enregistrements
**And** les nouveaux `AuditActionType` et `AuditEntityType` sont ajoutés aux enums existants

## Tasks / Subtasks

- [x] Task 1: Créer modèles IntegrationTypeCatalogue et IntegrationAction (AC: #1, #10)
  - [x] 1.1: Définir modèle `IntegrationTypeCatalogue` avec champs (code, name, description, version, is_active, timestamps)
  - [x] 1.2: Définir modèle `IntegrationAction` avec ForeignKey et champs JSON (required_params, optional_params, response_format)
  - [x] 1.3: Créer migration Django 0003 pour tables `INTEGRATION_TYPE_CATALOGUE` et `INTEGRATION_ACTIONS`
  - [x] 1.4: Ajouter enums `AuditActionType` (INTEGRATION_TYPE_CREATED, etc.) et `AuditEntityType` (INTEGRATION_TYPE_CATALOGUE, INTEGRATION_ACTION)
  - [x] 1.5: Valider migration et modèles avec `python manage.py makemigrations` et `python manage.py migrate`

- [x] Task 2: Créer fixtures/seed pour types AAP et ServiceNow (AC: #2)
  - [x] 2.1: Créer fixture JSON pour type AAP avec 4 actions (start_job, start_workflow, get_job_status, cancel_job)
  - [x] 2.2: Créer fixture JSON pour type ServiceNow avec 3 actions (create_change, update_change, get_change_status)
  - [x] 2.3: Définir schémas JSON Schema pour `required_params` et `optional_params` de chaque action
  - [x] 2.4: Tester le chargement des fixtures (`python manage.py loaddata`) — 7 tests fixtures passent

- [x] Task 3: Implémenter IntegrationCatalogueService (AC: #3) — Note: Service pattern (ADR-003) au lieu de Repository
  - [x] 3.1: Créer classe `IntegrationCatalogueService` dans `integrations/catalogue_service.py`
  - [x] 3.2: Méthode `list_all_types()` avec filtre `is_active=True` et `prefetch_related('actions')`
  - [x] 3.3: Méthode `get_type_by_code(code)` avec `prefetch_related()` pour actions
  - [x] 3.4: Méthode `list_actions_by_type(type_code)` avec filtre `is_active=True`
  - [x] 3.5: Méthode `get_action(type_code, action_code)` retournant action ou None
  - [x] 3.6: Tests unitaires pour chaque méthode du service (14 tests)

- [x] Task 4: Créer serializers DRF (AC: #4)
  - [x] 4.1: `IntegrationTypeCatalogueSerializer` avec tous les champs
  - [x] 4.2: `IntegrationActionSerializer` avec tous les champs et JSONTextField custom
  - [x] 4.3: `IntegrationTypeWithActionsSerializer` avec nested `actions` field
  - [x] 4.4: Tests serializers (sérialisation/désérialisation, nested actions) — 10 tests

- [x] Task 5: Implémenter API endpoints (AC: #5, #6, #7)
  - [x] 5.1: ViewSet `IntegrationTypeCatalogueViewSet` dans `integrations/catalogue_views.py`
  - [x] 5.2: Endpoint `GET /api/v1/integrations/types` → list action, retourne tous types actifs avec actions
  - [x] 5.3: Endpoint `GET /api/v1/integrations/types/{code}` → retrieve action, retourne type spécifique ou 404
  - [x] 5.4: Action custom `@action(detail=True, methods=['get'])` pour `/types/{code}/actions`
  - [x] 5.5: Documentation drf-spectacular avec `@extend_schema` pour chaque endpoint
  - [x] 5.6: Enregistrer routes dans `integrations/urls.py`
  - [x] 5.7: Tests API endpoints (HTTP 200, 404, structure réponse, permissions) — 17 tests

- [x] Task 6: Audit trail pour catalogue (AC: #10)
  - [x] 6.1: Ajouter signal `post_save` pour `IntegrationTypeCatalogue` → appel `AuditService.create_entry()` avec action_type CREATED/UPDATED
  - [x] 6.2: Ajouter signal `post_save` pour `IntegrationAction` → appel `AuditService.create_entry()` avec action_type CREATED/UPDATED
  - [x] 6.3: Tests audit trail (vérifier création logs après save de type/action) — 6 tests

- [x] Task 7: Documentation (AC: #9)
  - [x] 7.1: Créer `docs/integration-type-catalogue.md` avec architecture, types supportés, exemples API
  - [x] 7.2: Documenter format JSON Schema pour paramètres actions
  - [x] 7.3: Guide pour ajouter nouveau type d'intégration
  - [x] 7.4: Mettre à jour README principal avec référence au document

- [x] Task 8: Tests complets et couverture (AC: #8)
  - [x] 8.1: Couverture complète sur nouveaux fichiers (models, service, serializers, views, signals)
  - [x] 8.2: Tests edge cases (type inactif, action inexistante, paramètres invalides, JSON mal formé)
  - [x] 8.3: Tests d'intégration end-to-end (seed fixtures → API call → validation réponse)
  - [x] 8.4: `pytest` confirme 76/76 tests passent (objectif 40 dépassé)

## Dev Notes

### Contexte Architectural

**Modèle actuel des intégrations :**
- Table `INTEGRATIONS` (V020) avec champs : `id`, `type`, `name`, `base_url`, `credential_ref`, `icon`, `auth_flow`, `token_url`, `config` (CLOB JSON)
- Enum `IntegrationType` dans `integrations/models.py` : AAP, SERVICENOW, TERRAFORM, AZUREDEVOPS, JIRA, GITHUB_ACTIONS, INVENTORY, INVENTORY_DB
- **Problème actuel** : Aucun catalogue formel des actions supportées par type, validation config JSON très permissive

**Nouvelle architecture (cette story) :**
- **Séparation conceptuelle** :
  - `IntegrationTypeCatalogue` : Définition formelle d'un TYPE d'intégration (ex: AAP, ServiceNow) avec métadonnées
  - `IntegrationAction` : Actions supportées par chaque type (ex: start_job pour AAP, create_change pour ServiceNow)
  - `Integration` (table existante) : **Instances** d'intégration (ex: "AAP Dev", "ServiceNow Prod") — reste inchangé dans cette story, sera relié au catalogue dans Story 24.3

**Flux de validation futur (Stories 24.2-24.4) :**
1. Frontend récupère catalogue types via `GET /api/v1/integrations/types`
2. UI Admin restreint la sélection aux types actifs et leurs actions valides
3. Backend valide que l'action utilisée existe dans le catalogue (Story 24.3)
4. Exécutions rejettent les intégrations avec actions non cataloguées (Story 24.4)

### Contraintes Techniques

**Base de données :**
- Oracle 19c avec schéma DBOPS (uppercase table/column names)
- JSONField Django → `TextField` avec sérialisation JSON manuelle (voir `integrations/models.py` méthodes `get_config()` / `set_config()`)
- Migrations doivent utiliser `db_column='UPPERCASE'` pour tous les champs

**Pattern Repository :**
- Utiliser le pattern repository existant (voir `profiles/repositories.py`, `integrations/repositories.py`)
- Méthodes retournent des dictionnaires sérialisés ou objets Django, JAMAIS des QuerySets bruts
- Logging avec `structlog` pour toutes les opérations

**DRF & drf-spectacular :**
- Tous les endpoints doivent être documentés avec `@extend_schema` (voir `profiles/views.py` exemples)
- Utiliser `Response({'data': ...})` pour cohérence avec API existante
- Permissions : `IsAuthenticated` par défaut (pas besoin de RBAC pour lecture catalogue)

**Tests :**
- Framework : `pytest` avec `pytest-django`
- Fixtures : Utiliser `UserFactory`, `ProfileFactory` existants (voir `core/tests/factories.py`)
- Créer `IntegrationTypeCatalogueFactory` et `IntegrationActionFactory` pour tests
- Tests d'API : utiliser `APIClient` de DRF
- Vérifier que tous les tests passent SANS fixtures DB existantes (isolation complète)

### Référencement Code Existant

**Fichiers à modifier/créer :**
- `integrations/models.py` : Ajouter `IntegrationTypeCatalogue`, `IntegrationAction`
- `integrations/repositories.py` : Ajouter `IntegrationCatalogueRepository`
- `integrations/serializers.py` : Ajouter serializers pour catalogue
- `integrations/views.py` : Ajouter `IntegrationTypeCatalogueViewSet`
- `integrations/urls.py` : Enregistrer routes
- `core/models.py` : Ajouter enums audit `INTEGRATION_TYPE_CREATED`, `INTEGRATION_ACTION_CREATED`, etc.
- `integrations/migrations/V0XX_integration_type_catalogue.py` : Migration Django

**Fichiers de référence (patterns à suivre) :**
- Modèle avec JSONField : `integrations/models.py` (classe `Integration`, méthodes `get_config()` / `set_config()`)
- Repository pattern : `profiles/repositories.py` (classe `ProfileRepository`)
- ViewSet DRF documenté : `profiles/views.py` (classe `ProfileViewSet` avec `@extend_schema`)
- Tests API : `profiles/tests/test_views.py`
- Audit trail avec signals : `profiles/models.py` (signal `post_save`)

### Schéma JSON pour Paramètres Actions

**Format JSON Schema pour `required_params` et `optional_params` :**

Exemple AAP `start_job` :
```json
{
  "required_params": {
    "type": "object",
    "properties": {
      "job_template_id": {"type": "integer", "description": "ID du job template AAP"}
    },
    "required": ["job_template_id"]
  },
  "optional_params": {
    "type": "object",
    "properties": {
      "extra_vars": {"type": "object", "description": "Variables supplémentaires JSON"}
    }
  }
}
```

Exemple ServiceNow `create_change` :
```json
{
  "required_params": {
    "type": "object",
    "properties": {
      "short_description": {"type": "string"},
      "category": {"type": "string"},
      "priority": {"type": "integer"}
    },
    "required": ["short_description", "category"]
  },
  "optional_params": {
    "type": "object",
    "properties": {
      "description": {"type": "string"},
      "work_notes": {"type": "string"}
    }
  }
}
```

### Gestion des Versions Catalogue

**Versionnement minimal (champ `version`) :**
- Format : `"1.0"`, `"1.1"`, `"2.0"` (semantic versioning simplifié)
- Incrémentation :
  - Minor (`1.0` → `1.1`) : Ajout d'actions non-breaking
  - Major (`1.0` → `2.0`) : Modification/suppression actions existantes (breaking change)
- **Note** : Dans cette story, versionnement est informatif uniquement (pas de logique de migration automatique)
- Stories futures pourront valider compatibilité version entre `Integration.type` et `IntegrationTypeCatalogue.version`

### Exemples d'Appels API (pour documentation)

**GET /api/v1/integrations/types**
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/integrations/types
```

**GET /api/v1/integrations/types/aap**
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/integrations/types/aap
```

**GET /api/v1/integrations/types/aap/actions**
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/integrations/types/aap/actions
```

### Checklist Implémentation

- [ ] Modèles créés avec champs corrects (uppercase DB columns)
- [ ] Migration Django appliquée sans erreur
- [ ] Fixtures/seed AAP + ServiceNow chargées avec succès
- [ ] Repository methods optimisées (select_related/prefetch_related)
- [ ] Serializers testés avec données réelles
- [ ] API endpoints documentés drf-spectacular
- [ ] Audit trail fonctionnel (logs créés lors save)
- [ ] Tests >= 40, couverture >= 90%
- [ ] Documentation `docs/integration-type-catalogue.md` complète
- [ ] `pytest` passe à 100% (aucune régression)

### Project Structure Notes

**Alignement avec structure Django existante :**
- App `integrations` : Contient modèles, repositories, serializers, views, tests
- App `core` : Contient `AuditService`, enums `AuditActionType` / `AuditEntityType`
- Migrations : Préfixe `V0XX` (convention Oracle migrations)
- Tests : Organisation par module (`test_models.py`, `test_repositories.py`, `test_views.py`, `test_serializers.py`)

**Pas de conflits détectés avec structure existante**

### References

**Source principale :**
- [Source: _bmad-output/planning-artifacts/epics.md — Epic 24, Story 24.1] (lines 4226-4227)
- [Source: _bmad-output/planning-artifacts/epics.md — Epic 24 Overview] (lines 4212-4236)

**Architecture :**
- [Source: idp-portal/django_backend/integrations/models.py] — Modèle `Integration` existant, enum `IntegrationType`, pattern JSONField
- [Source: idp-portal/django_backend/integrations/services.py] — Pattern service avec validation JSON Schema

**Patterns de référence :**
- [Source: idp-portal/django_backend/profiles/repositories.py] — Pattern repository
- [Source: idp-portal/django_backend/profiles/views.py] — ViewSet DRF avec drf-spectacular
- [Source: idp-portal/django_backend/core/models.py] — Enums `AuditActionType`, `AuditEntityType`

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- Fixture loading fix: `auto_now_add` fields require explicit timestamps in JSON fixtures
- ADR-003 adaptation: Story specified Repository pattern but project uses Service pattern — created `IntegrationCatalogueService` instead of `IntegrationCatalogueRepository`
- ViewSet placed in separate file `catalogue_views.py` to avoid conflicts with existing `IntegrationViewSet`

### Completion Notes List

- ✅ Task 1: Modèles `IntegrationTypeCatalogue` (PK=code) et `IntegrationAction` (FK + unique_together) créés avec uppercase DB columns, JSON helpers, migrations générées (integrations 0003, core 0004)
- ✅ Task 2: Fixture JSON avec AAP (4 actions) et ServiceNow (3 actions) — schémas JSON Schema complets pour required/optional params
- ✅ Task 3: `IntegrationCatalogueService` (Service pattern ADR-003) — 4 méthodes statiques avec prefetch_related/select_related
- ✅ Task 4: 3 serializers DRF + `JSONTextField` custom pour désérialiser les champs JSON TextFields
- ✅ Task 5: `IntegrationTypeCatalogueViewSet` avec list/retrieve/actions_list — drf-spectacular annotations — routes `/api/v1/integrations/types/`
- ✅ Task 6: Signals `post_save` pour audit trail — `INTEGRATION_TYPE_CREATED/UPDATED`, `INTEGRATION_ACTION_CREATED/UPDATED`
- ✅ Task 7: Documentation `docs/integration-type-catalogue.md` + README mis à jour
- ✅ Task 8: 76/76 tests passent (22 models, 14 service, 10 serializers, 17 views, 6 signals, 7 fixtures)

### Implementation Notes

- Service pattern utilisé au lieu du Repository pattern (conformément à ADR-003 — migration repositories vers services)
- `AuditService.create_entry()` utilisé dans les signals (pas `AuditService.log()` qui n'existe pas)
- `IntegrationTypeCatalogueFactory` et `IntegrationActionFactory` ajoutés dans `tests/factories.py`

### File List

**Fichiers créés :**
- `idp-portal/django_backend/integrations/catalogue_service.py` — Service de lecture du catalogue
- `idp-portal/django_backend/integrations/catalogue_views.py` — ViewSet API endpoints
- `idp-portal/django_backend/integrations/signals.py` — Signals audit trail post_save
- `idp-portal/django_backend/integrations/fixtures/integration_type_catalogue.json` — Données initiales AAP + ServiceNow
- `idp-portal/django_backend/integrations/migrations/0003_integrationtypecatalogue_integrationaction.py` — Migration modèles
- `idp-portal/django_backend/core/migrations/0004_alter_auditlog_action_type_and_more.py` — Migration enums audit
- `idp-portal/django_backend/integrations/tests/test_catalogue_models.py` — 22 tests modèles
- `idp-portal/django_backend/integrations/tests/test_catalogue_service.py` — 14 tests service
- `idp-portal/django_backend/integrations/tests/test_catalogue_serializers.py` — 10 tests serializers
- `idp-portal/django_backend/integrations/tests/test_catalogue_views.py` — 17 tests API
- `idp-portal/django_backend/integrations/tests/test_catalogue_signals.py` — 6 tests audit
- `idp-portal/django_backend/integrations/tests/test_catalogue_fixtures.py` — 7 tests fixtures
- `idp-portal/django_backend/docs/integration-type-catalogue.md` — Documentation catalogue

**Fichiers modifiés :**
- `idp-portal/django_backend/integrations/models.py` — Ajout modèles IntegrationTypeCatalogue, IntegrationAction
- `idp-portal/django_backend/integrations/serializers.py` — Ajout serializers catalogue + JSONTextField
- `idp-portal/django_backend/integrations/urls.py` — Ajout routes catalogue
- `idp-portal/django_backend/integrations/apps.py` — Import signals dans ready()
- `idp-portal/django_backend/core/models.py` — Ajout enums audit INTEGRATION_TYPE_*, INTEGRATION_ACTION_*
- `idp-portal/django_backend/tests/factories.py` — Ajout IntegrationTypeCatalogueFactory, IntegrationActionFactory
- `idp-portal/django_backend/README.md` — Référence documentation catalogue

## Change Log

- 2026-02-10: Story 24.1 complète — Catalogue des types d'intégration backend (modèles, fixtures AAP/ServiceNow, service, serializers, API endpoints, audit trail, documentation, 76 tests)
- 2026-02-10: Code Review — 11 issues trouvés et corrigés (8 HIGH: audit trail user_id/entity_id/correlation_id, validation JSON Schema, docs versionnement; 2 MEDIUM: logging structlog, 404 doc; 1 LOW: __str__() readability) — Tous les tests passent (76/76)
