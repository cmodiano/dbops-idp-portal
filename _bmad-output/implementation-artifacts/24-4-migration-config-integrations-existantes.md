# Story 24.4: Migration configuration intégrations existantes

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur backend,
Je veux migrer les intégrations existantes vers le nouveau modèle typé du catalogue et mettre en place des garde-fous d'exécution,
Afin d'assurer la cohérence du système et d'éviter les erreurs d'exécution liées à des intégrations invalides ou dépréciées.

## Contexte Epic 24

**Objectif Epic :** Encadrer la configuration des intégrations dans l'interface Admin pour n'autoriser que des types et des actions d'intégration explicitement supportés par le backend (AAP, ServiceNow, etc.), via un modèle "type d'intégration" + "instance d'intégration" et un catalogue d'actions contractuel.

**Position dans l'Epic :**
1. **Story 24.1** (✅ done) : Backend — Catalogue types intégration + API lecture
2. **Story 24.2** (✅ done) : Frontend Admin — Restriction types actions basée sur catalogue backend
3. **Story 24.3** (✅ done) : Backend & Frontend — Validation état intégrations (valid/invalid/deprecated)
4. **Story 24.4 (cette story)** : Migration intégrations existantes + garde-fous exécution

**Problème résolu :**
- Les intégrations créées avant Story 24.1 peuvent référencer des types non présents dans le catalogue
- Des intégrations peuvent avoir un statut `INVALID` ou `DEPRECATED` suite à la validation automatique (Story 24.3)
- Aucun garde-fou n'empêche actuellement l'exécution d'actions avec des intégrations invalides
- Les workflows existants peuvent référencer des intégrations obsolètes sans avertissement visible

**Approche :**
Cette story finalise l'Epic 24 en :
1. **Analysant** les intégrations existantes en base et leur correspondance avec le catalogue
2. **Migrant** automatiquement celles qui peuvent être rattachées à un type du catalogue
3. **Marquant** comme `legacy` celles qui ne correspondent à aucun type connu
4. **Bloquant** l'utilisation d'intégrations `INVALID` dans les nouvelles exécutions (moteur d'exécution)
5. **Avertissant** pour les intégrations `DEPRECATED` avec logging audit

## Acceptance Criteria

### AC1 — Script d'analyse des intégrations existantes (management command)

**Given** le besoin d'identifier l'état des intégrations existantes par rapport au catalogue
**When** l'administrateur exécute `python manage.py analyze_integrations`
**Then** le script analyse toutes les intégrations en base et produit un rapport console :

```
=== ANALYSE DES INTÉGRATIONS EXISTANTES ===
Catalogue chargé : 2 types actifs (aap, servicenow)

Intégrations trouvées : 15 total
  ✓ Valides (type dans catalogue actif) : 10
    - ID 1: AAP Dev (type: aap) ✓
    - ID 2: AAP Prod (type: aap) ✓
    - ID 5: ServiceNow ITSM (type: servicenow) ✓
    [...]

  ⚠ Dépréciées (type dans catalogue mais is_active=False) : 2
    - ID 8: Terraform Cloud (type: terraform) — type déprécié
    - ID 9: Azure DevOps Legacy (type: azuredevops) — type déprécié

  ✗ Invalides (type inexistant dans catalogue) : 3
    - ID 12: Custom Script Runner (type: custom_script) — type inconnu
    - ID 13: Legacy Jenkins (type: jenkins) — type inconnu
    - ID 14: Old AAP (type: aap_v1) — type inconnu

=== RECOMMANDATIONS ===
1. Valides (10) : Aucune action nécessaire
2. Dépréciées (2) : Vérifier les workflows utilisant ces intégrations, prévoir migration vers types supportés
3. Invalides (3) : ATTENTION — Ces intégrations bloquent l'exécution :
   - Soit créer les types manquants dans le catalogue (IntegrationTypeCatalogue)
   - Soit migrer vers des types existants
   - Soit marquer comme 'legacy' (lecture seule, aucune nouvelle utilisation)

Pour migrer automatiquement les intégrations valides/dépréciées :
  python manage.py migrate_integrations --auto

Pour marquer les invalides comme 'legacy' :
  python manage.py migrate_integrations --mark-legacy
```

**And** le script utilise `IntegrationValidationService.validate_integration()` pour déterminer le statut de chaque intégration

**And** le script ne modifie AUCUNE donnée (lecture seule, analyse uniquement)

**And** le rapport est également sauvegardé dans un fichier JSON : `integration_analysis_YYYYMMDD_HHMMSS.json` contenant :
```json
{
  "analysis_date": "2026-02-10T14:30:00Z",
  "catalogue_types_count": 2,
  "catalogue_types_active": ["aap", "servicenow"],
  "integrations_total": 15,
  "integrations_valid": 10,
  "integrations_deprecated": 2,
  "integrations_invalid": 3,
  "details": {
    "valid": [
      {"id": 1, "name": "AAP Dev", "type": "aap", "status": "valid"},
      ...
    ],
    "deprecated": [
      {"id": 8, "name": "Terraform Cloud", "type": "terraform", "status": "deprecated", "reason": "type_inactive"},
      ...
    ],
    "invalid": [
      {"id": 12, "name": "Custom Script Runner", "type": "custom_script", "status": "invalid", "reason": "type_not_found"},
      ...
    ]
  },
  "recommendations": [
    "10 intégrations valides - aucune action",
    "2 intégrations dépréciées - vérifier workflows et planifier migration",
    "3 intégrations invalides - BLOCKER pour exécution, action requise"
  ]
}
```

### AC2 — Script de migration automatique des intégrations (management command)

**Given** le besoin de mettre à jour automatiquement les intégrations existantes
**When** l'administrateur exécute `python manage.py migrate_integrations --auto`
**Then** le script exécute les actions suivantes :

**Pour chaque intégration :**
1. Appelle `IntegrationValidationService.validate_integration(integration)` pour obtenir le statut calculé
2. Compare avec le statut actuel en base (`integration.status`)
3. Si différent :
   - Met à jour `integration.status` avec la nouvelle valeur
   - Crée une entrée d'audit `INTEGRATION_STATUS_UPDATED` avec détails :
     ```json
     {
       "integration_id": 5,
       "integration_name": "AAP Dev",
       "old_status": "valid",
       "new_status": "deprecated",
       "reason": "type_inactive",
       "migrated_by": "migrate_integrations_command",
       "correlation_id": "migrate-20260210-143000"
     }
     ```

**And** affiche un rapport de migration :
```
=== MIGRATION DES INTÉGRATIONS ===
Date : 2026-02-10 14:30:00
Corrélation ID : migrate-20260210-143000

Intégrations analysées : 15
Mises à jour effectuées : 5
  - ID 3: AAP QA — valid → valid (aucun changement)
  - ID 8: Terraform Cloud — valid → deprecated ✓ MIGRÉ
  - ID 9: Azure DevOps Legacy — valid → deprecated ✓ MIGRÉ
  - ID 12: Custom Script Runner — valid → invalid ✓ MIGRÉ
  - ID 13: Legacy Jenkins — valid → invalid ✓ MIGRÉ
  - ID 14: Old AAP — valid → invalid ✓ MIGRÉ

Statut final :
  ✓ Valides : 10
  ⚠ Dépréciées : 2
  ✗ Invalides : 3

ATTENTION : 3 intégrations invalides bloquent l'exécution.
Recommandation : Exécuter avec --mark-legacy pour les désactiver proprement.
```

**And** le script est transactionnel (rollback complet en cas d'erreur)

**And** le script utilise `structlog` pour logger chaque mise à jour avec `correlation_id`

**And** si aucune mise à jour nécessaire, affiche : `"Aucune migration nécessaire. Toutes les intégrations sont à jour."`

### AC3 — Option --mark-legacy pour désactiver les intégrations invalides

**Given** le besoin de marquer les intégrations invalides comme "legacy" (désactivées)
**When** l'administrateur exécute `python manage.py migrate_integrations --mark-legacy`
**Then** le script identifie toutes les intégrations avec `status=INVALID`

**And** pour chaque intégration invalide :
- Ne modifie PAS le champ `status` (reste `INVALID`)
- Ajoute un champ `config` JSON avec clé `"_legacy": true` (ou modifie config existant)
- Crée une entrée d'audit `INTEGRATION_MARKED_LEGACY` avec détails

**And** affiche :
```
=== MARQUAGE LEGACY ===
Intégrations marquées comme legacy : 3
  - ID 12: Custom Script Runner (type: custom_script) ✓ LEGACY
  - ID 13: Legacy Jenkins (type: jenkins) ✓ LEGACY
  - ID 14: Old AAP (type: aap_v1) ✓ LEGACY

Ces intégrations ne peuvent plus être utilisées dans :
  - Nouvelles exécutions (bloquées par le moteur)
  - Nouveaux workflows (filtrées dans l'UI)

Workflows existants utilisant ces intégrations :
  - Workflow "Deploy to Azure" (ID 42) utilise ID 9 (Azure DevOps Legacy)
  → ACTION REQUISE : Mettre à jour le workflow pour utiliser une intégration valide

Pour restaurer une intégration legacy :
  1. Créer le type correspondant dans IntegrationTypeCatalogue
  2. Exécuter : python manage.py validate_integrations
  3. Retirer la clé "_legacy" du config
```

**And** le script détecte les workflows référençant les intégrations marquées legacy et affiche un avertissement

### AC4 — Garde-fou backend : bloquer exécutions avec intégrations invalides

**Given** le besoin d'empêcher les exécutions avec des intégrations invalides
**When** le moteur d'exécution tente de démarrer une exécution (action ou workflow step)
**Then** avant de déclencher l'exécution :

1. **Récupère l'intégration** via `integration_id` fourni par l'action/workflow
2. **Vérifie le statut** de l'intégration :
   - Si `status == IntegrationStatus.INVALID` → **BLOQUE** l'exécution
   - Si `status == IntegrationStatus.DEPRECATED` → **AVERTIT** mais autorise
   - Si `status == IntegrationStatus.VALID` → **AUTORISE** normalement

3. **En cas de blocage (INVALID) :**
   - Retourne erreur HTTP 400 avec code `INVALID_INTEGRATION`
   - Message : `"L'intégration '{integration.name}' (type: '{integration.type}') est invalide et ne peut pas être utilisée. Veuillez contacter un administrateur."`
   - Détails JSON :
     ```json
     {
       "error": {
         "code": "INVALID_INTEGRATION",
         "message": "L'intégration 'Custom Script Runner' (type: 'custom_script') est invalide...",
         "details": {
           "integration_id": 12,
           "integration_name": "Custom Script Runner",
           "integration_type": "custom_script",
           "integration_status": "invalid",
           "reason": "type_not_found_in_catalogue",
           "action": "contact_administrator"
         }
       }
     }
     ```
   - **Crée une entrée d'audit** `EXECUTION_BLOCKED_INVALID_INTEGRATION` avec tous les détails
   - **Ne crée PAS** d'enregistrement dans `EXECUTIONS` (exécution refusée avant création)

4. **En cas d'avertissement (DEPRECATED) :**
   - Autorise l'exécution normalement
   - Logue un WARNING `structlog` :
     ```python
     logger.warning(
         "execution_with_deprecated_integration",
         integration_id=integration.id,
         integration_name=integration.name,
         integration_type=integration.type,
         execution_id=execution.id,
         action_id=action.id,
         user_id=user.id
     )
     ```
   - Crée une entrée d'audit `EXECUTION_DEPRECATED_INTEGRATION_WARNING`
   - L'exécution se poursuit normalement

**And** ce garde-fou est implémenté dans `ExecutionService.trigger_execution()` AVANT l'appel aux adapters

**And** les tests couvrent les 3 cas : `VALID`, `DEPRECATED`, `INVALID`

### AC5 — Vérification intégration dans WorkflowRuntimeService

**Given** un workflow avec des steps utilisant des intégrations
**When** le `WorkflowRuntimeService` exécute un step de type intégration
**Then** avant de déclencher le step :

1. Récupère l'`integration_id` du step
2. Vérifie le statut de l'intégration (même logique que AC4)
3. Si `INVALID` → **STOPPE** le workflow avec statut `FAILED` et erreur explicite
4. Si `DEPRECATED` → **AVERTIT** (log + audit) mais continue
5. Si `VALID` → Continue normalement

**And** le message d'erreur en cas d'intégration invalide est clair :
```
Workflow step 'Deploy to AAP' failed: Integration 'Old AAP' (type: aap_v1) is invalid and cannot be used.
Please update the workflow to use a valid integration before retrying.
```

**And** le workflow entier est marqué `FAILED` (pas seulement le step)

**And** une notification est envoyée au créateur du workflow via `NotificationService`

### AC6 — Tests backend : migration et garde-fous

**Given** le besoin de valider la migration et les garde-fous
**When** les tests sont exécutés
**Then** les tests suivants passent :

**Tests migration (`tests/management/test_migrate_integrations.py`) :**
- `test_analyze_integrations_report` : Vérifie le rapport d'analyse complet
- `test_migrate_integrations_auto_updates_status` : Vérifie mise à jour statut avec audit
- `test_migrate_integrations_no_updates_needed` : Cas où tout est déjà à jour
- `test_mark_legacy_invalid_integrations` : Vérifie marquage legacy + config
- `test_mark_legacy_warns_about_workflows` : Détection workflows impactés

**Tests garde-fous (`tests/executions/test_execution_integration_validation.py`) :**
- `test_trigger_execution_blocks_invalid_integration` : HTTP 400 + audit
- `test_trigger_execution_warns_deprecated_integration` : Log + audit + exécution OK
- `test_trigger_execution_allows_valid_integration` : Pas de warning, exécution OK
- `test_workflow_step_fails_invalid_integration` : Workflow FAILED + notification
- `test_workflow_step_warns_deprecated_integration` : Log + continue

**And** tous les tests utilisent `IntegrationFactory` et `IntegrationTypeCatalogueFactory` pour créer des données de test

**And** les tests vérifient les entrées d'audit créées via `AuditService`

### AC7 — Documentation de la migration

**Given** le besoin de documenter la migration pour les équipes
**When** la documentation est rédigée
**Then** un fichier `docs/integration-migration-guide.md` est créé avec :

**Contenu :**
1. **Vue d'ensemble** : Pourquoi migrer les intégrations (Epic 24 context)
2. **Étapes de migration** :
   - Étape 1 : Analyse (`analyze_integrations`)
   - Étape 2 : Validation catalogue (ajouter types manquants si nécessaire)
   - Étape 3 : Migration auto (`migrate_integrations --auto`)
   - Étape 4 : Marquage legacy (`migrate_integrations --mark-legacy`)
   - Étape 5 : Mise à jour workflows impactés
3. **Scénarios de migration** :
   - Scénario A : Toutes les intégrations sont valides → Aucune action
   - Scénario B : Quelques intégrations dépréciées → Plan de migration vers types actifs
   - Scénario C : Intégrations invalides → Créer types manquants OU marquer legacy
4. **Dépannage** :
   - "Que faire si une intégration est marquée INVALID ?"
   - "Comment réactiver une intégration legacy ?"
   - "Comment savoir quels workflows sont impactés ?"
5. **Référence des commandes** : Liste complète des options CLI

**And** des exemples concrets de sorties de commandes sont inclus

**And** un lien vers `docs/integration-type-catalogue.md` (Story 24.1) pour comprendre le catalogue

### AC8 — Logging structuré et observabilité

**Given** le besoin de tracer toutes les opérations de migration et validation
**When** les scripts de migration et les garde-fous s'exécutent
**Then** tous les logs utilisent `structlog` avec les champs suivants :

**Migration logs :**
```python
logger.info(
    "integration_migration_started",
    correlation_id="migrate-20260210-143000",
    command="migrate_integrations",
    options={"auto": True, "mark_legacy": False},
    integrations_total=15
)

logger.info(
    "integration_status_updated",
    integration_id=8,
    integration_name="Terraform Cloud",
    old_status="valid",
    new_status="deprecated",
    reason="type_inactive",
    correlation_id="migrate-20260210-143000"
)

logger.info(
    "integration_migration_completed",
    correlation_id="migrate-20260210-143000",
    integrations_updated=5,
    valid_count=10,
    deprecated_count=2,
    invalid_count=3,
    duration_ms=1230
)
```

**Garde-fou logs :**
```python
logger.error(
    "execution_blocked_invalid_integration",
    execution_id=None,  # Not created yet
    integration_id=12,
    integration_name="Custom Script Runner",
    integration_status="invalid",
    action_id=42,
    user_id=5,
    correlation_id=request_correlation_id
)

logger.warning(
    "execution_with_deprecated_integration",
    execution_id=105,
    integration_id=8,
    integration_name="Terraform Cloud",
    integration_status="deprecated",
    action_id=15,
    user_id=5,
    correlation_id=execution_correlation_id
)
```

**And** tous les logs sont formatés JSON pour ingestion Splunk

**And** les `correlation_id` permettent de tracer toute la chaîne d'opérations

### AC9 — Entrées d'audit pour migration et blocages

**Given** le besoin de tracer les changements de statut et les blocages d'exécution
**When** les opérations de migration et les garde-fous s'exécutent
**Then** les entrées d'audit suivantes sont créées :

**Nouveaux types d'audit à ajouter dans `AuditActionType` :**
```python
INTEGRATION_STATUS_UPDATED = 'INTEGRATION_STATUS_UPDATED'  # Migration auto
INTEGRATION_MARKED_LEGACY = 'INTEGRATION_MARKED_LEGACY'    # --mark-legacy
EXECUTION_BLOCKED_INVALID_INTEGRATION = 'EXECUTION_BLOCKED_INVALID_INTEGRATION'
EXECUTION_DEPRECATED_INTEGRATION_WARNING = 'EXECUTION_DEPRECATED_INTEGRATION_WARNING'
WORKFLOW_STEP_BLOCKED_INVALID_INTEGRATION = 'WORKFLOW_STEP_BLOCKED_INVALID_INTEGRATION'
```

**And** chaque entrée d'audit contient :
- `user_id` : ID de l'utilisateur (ou "system" pour les commandes management)
- `action_type` : Un des types ci-dessus
- `entity_type` : `INTEGRATION` ou `EXECUTION`
- `entity_id` : ID de l'intégration ou exécution
- `details` : JSON avec contexte complet (avant/après, raison, correlation_id)
- `ip_address` : IP de l'utilisateur (ou "127.0.0.1" pour les commandes system)
- `correlation_id` : Pour tracer les opérations liées

**And** les entrées d'audit sont créées via `AuditService.create_entry()` pour cohérence

### AC10 — Option --dry-run pour migration

**Given** le besoin de prévisualiser les changements avant de les appliquer
**When** l'administrateur exécute `python manage.py migrate_integrations --auto --dry-run`
**Then** le script exécute toute la logique de validation et affiche le rapport

**And** aucune modification n'est effectuée en base de données (transaction rollback à la fin)

**And** le rapport affiche clairement : `"MODE DRY-RUN : Aucune modification effectuée en base"`

**And** le rapport montre exactement ce qui SERAIT changé :
```
=== MIGRATION DES INTÉGRATIONS (DRY-RUN) ===
⚠ MODE DRY-RUN : Aucune modification ne sera effectuée

Changements prévus :
  - ID 8: Terraform Cloud — valid → deprecated
  - ID 9: Azure DevOps Legacy — valid → deprecated
  - ID 12: Custom Script Runner — valid → invalid
  - ID 13: Legacy Jenkins — valid → invalid
  - ID 14: Old AAP — valid → invalid

Total : 5 intégrations seraient mises à jour

Pour appliquer ces changements, exécutez sans --dry-run :
  python manage.py migrate_integrations --auto
```

**And** aucune entrée d'audit n'est créée en mode `--dry-run`

**And** le code utilise une transaction Django avec rollback explicite : `transaction.set_rollback(True)`

## Dev Notes

### Contexte technique des stories précédentes

**Story 24.1 (done) :**
- Modèles créés : `IntegrationTypeCatalogue`, `IntegrationAction`
- Migration DB : `0003_integrationtypecatalogue_integrationaction.py`
- API endpoints : `GET /api/v1/integrations/types/`, `GET /api/v1/integrations/types/{code}/`
- Service : `IntegrationCatalogueService` (list types, get type by code, list actions)

**Story 24.2 (done) :**
- Frontend `IntegrationForm` : Restriction type via Select (catalogue backend)
- Hook `useIntegrationTypes()` : Fetch catalogue avec fallback
- Composant `AvailableActionsPanel` : Affichage actions par type

**Story 24.3 (done) :**
- Ajout champ `status` au modèle `Integration` (enum `IntegrationStatus`)
- Migration DB : `0004_add_integration_status.py`
- Service `IntegrationValidationService` : Validation status automatique
- API endpoint : `GET /api/v1/integrations/{id}/validate`
- Mise à jour auto status lors create/update dans `IntegrationService`
- UI Admin : Badges status + alerts formulaire

### Architecture et conventions à respecter

**Database :**
- Migrations Oracle avec nommage : `000X_descriptive_name.py`
- Tables : UPPER_SNAKE_CASE (ex: `INTEGRATIONS`, `INTEGRATION_TYPE_CATALOGUE`)
- Index : `IDX_{TABLE}_{COLUMN}` (ex: `IDX_INTEGRATION_STATUS`)

**Backend Python :**
- Services dans `integrations/services.py` et `integrations/validation_service.py`
- Management commands dans `integrations/management/commands/`
- Tests dans `tests/management/`, `tests/integrations/`, `tests/executions/`
- Logging : `structlog` avec `correlation_id` (voir `core/middleware.py`)
- Audit : `AuditService.create_entry()` pour toute mutation importante

**API REST :**
- Format erreur structuré : `{"error": {"code": "...", "message": "...", "details": {...}}}`
- Codes HTTP : 400 (validation), 404 (not found), 403 (forbidden)
- Documentation : `@extend_schema` pour drf-spectacular

**Frontend TypeScript :**
- Types API dans `types/api/integrations.ts`
- Service dans `services/integrations_service.ts`
- Composants Ant Design : `Tag`, `Alert`, `Badge`, `Select`

### Patterns d'exécution existants

**ExecutionService (`executions/services.py`) :**
- `trigger_execution(action_id, user_id, environment, parameters, target_names)` : Point d'entrée exécutions
- Vérifie RBAC, crée enregistrement `Execution`, appelle adapter plateforme
- **Point d'injection du garde-fou** : Avant appel adapter, vérifier `integration.status`

**WorkflowRuntimeService (`workflows/runtime_service.py`) :**
- `execute_workflow(workflow_id, user_id, parameters)` : Exécute workflow complet
- `_execute_step(workflow_execution, step)` : Exécute un step individuel
- Pour steps type `integration` : Récupère `integration_id`, appelle adapter
- **Point d'injection du garde-fou** : Dans `_execute_step()`, vérifier status avant appel

**Adapters (`integrations/adapters/`) :**
- `AAPAdapter`, `ServiceNowAdapter` : Implémentent `BaseAdapter`
- Ne sont appelés QUE si validation passe dans `ExecutionService`/`WorkflowRuntimeService`

### Fichiers clés à modifier

**Backend :**
1. `integrations/management/commands/analyze_integrations.py` (nouveau) — AC1
2. `integrations/management/commands/migrate_integrations.py` (nouveau) — AC2, AC3, AC10
3. `executions/services.py` : Ajouter validation intégration dans `trigger_execution()` — AC4
4. `workflows/runtime_service.py` : Ajouter validation dans `_execute_step()` — AC5
5. `core/models.py` : Ajouter nouveaux `AuditActionType` — AC9
6. `tests/management/test_migrate_integrations.py` (nouveau) — AC6
7. `tests/executions/test_execution_integration_validation.py` (nouveau) — AC6
8. `docs/integration-migration-guide.md` (nouveau) — AC7

**Pas de changement frontend nécessaire** : L'UI Admin affiche déjà les status (Story 24.3), les garde-fous backend bloquent automatiquement les exécutions invalides.

### Dépendances et migration data

**Seed data existant :**
- `scripts/seed_integration_catalogue.py` : Seed AAP + ServiceNow dans catalogue (Story 24.1)
- À exécuter AVANT migration : `python manage.py seed_integration_catalogue`

**Ordre d'exécution :**
1. Déployer code Story 24.4
2. Exécuter seed catalogue si pas déjà fait
3. Exécuter `analyze_integrations` pour comprendre l'état
4. Créer types manquants dans catalogue si nécessaire (manuel)
5. Exécuter `migrate_integrations --auto --dry-run` pour prévisualiser
6. Exécuter `migrate_integrations --auto` pour migrer
7. Si intégrations invalides : soit créer types, soit `--mark-legacy`

### Tests à créer

**Management commands :**
- Factories : `IntegrationFactory`, `IntegrationTypeCatalogueFactory`, `WorkflowFactory`
- Cas nominal : intégrations valides → aucun changement
- Cas migration : valid → deprecated, valid → invalid
- Cas --dry-run : aucun changement DB
- Cas --mark-legacy : config modifié, audit créé

**Garde-fous exécution :**
- Mock `IntegrationValidationService` pour forcer status
- Vérifier HTTP 400 + code erreur + audit
- Vérifier log WARNING pour deprecated
- Vérifier exécution autorisée pour valid

### Considérations SOC1 et sécurité

**Audit trail :**
- Toutes les migrations doivent être auditées (qui, quand, quoi, pourquoi)
- Blocages d'exécution doivent être auditables (détection tentative utilisation intégration invalide)

**Integrity :**
- Les intégrations invalides ne doivent JAMAIS pouvoir exécuter
- Les workflows existants doivent être identifiés s'ils utilisent des intégrations obsolètes

**Observability :**
- Les logs structurés permettent de détecter les tentatives d'utilisation d'intégrations invalides
- Les rapports de migration doivent être archivés pour conformité

### Limites et exclusions (hors scope)

**Hors scope Story 24.4 :**
- Migration automatique des workflows pour remplacer intégrations invalides (action manuelle)
- UI Admin pour gérer les types de catalogue (lecture seule via API, création manuelle en DB)
- Notification proactive aux créateurs de workflows impactés (seule notification = échec exécution)
- Désactivation automatique d'intégrations après X jours de dépréciation (manuel)

### Références

**Documentation associée :**
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 24] — Exigences complètes Epic 24
- [Source: _bmad-output/implementation-artifacts/24-1-backend-catalogue-types-dintegration.md] — Catalogue types (Story 24.1)
- [Source: _bmad-output/implementation-artifacts/24-2-frontend-admin-restriction-types-actions.md] — Restriction frontend (Story 24.2)
- [Source: _bmad-output/implementation-artifacts/24-3-backend-frontend-validation-etat-integrations.md] — Validation status (Story 24.3)
- [Source: idp-portal/django_backend/docs/integration-type-catalogue.md] — Documentation technique catalogue
- [Source: idp-portal/django_backend/docs/integration-status-validation.md] — Documentation validation

**Code existant :**
- [Source: idp-portal/django_backend/integrations/models.py:94-157] — Modèle `Integration` avec champ `status`
- [Source: idp-portal/django_backend/integrations/services.py:76-141] — `IntegrationService.create_integration()` avec validation auto
- [Source: idp-portal/django_backend/integrations/validation_service.py] — `IntegrationValidationService`
- [Source: idp-portal/django_backend/executions/services.py] — `ExecutionService.trigger_execution()`
- [Source: idp-portal/django_backend/workflows/runtime_service.py] — `WorkflowRuntimeService._execute_step()`

## Tasks / Subtasks

### Tâche 1 : Commande d'analyse des intégrations (AC1)
- [x] Créer fichier `integrations/management/commands/analyze_integrations.py`
- [x] Implémenter logique d'analyse utilisant `IntegrationValidationService`
- [x] Générer rapport console formaté (✓, ⚠, ✗ sections)
- [x] Sauvegarder rapport JSON avec timestamp
- [x] Ajouter section recommandations selon résultats
- [x] Tester avec fixtures (valides, deprecated, invalid)

### Tâche 2 : Commande de migration automatique (AC2)
- [x] Créer fichier `integrations/management/commands/migrate_integrations.py`
- [x] Implémenter option `--auto` avec transaction atomique
- [x] Appeler `validate_integration()` pour chaque intégration
- [x] Mettre à jour `status` si changement détecté
- [x] Créer entrées audit `INTEGRATION_STATUS_UPDATED` via `AuditService`
- [x] Générer rapport de migration avec statistiques
- [x] Logger avec `structlog` + `correlation_id`
- [x] Tester migration avec rollback en cas d'erreur

### Tâche 3 : Option --mark-legacy (AC3)
- [x] Ajouter argument `--mark-legacy` à la commande
- [x] Filtrer intégrations `status=INVALID`
- [x] Modifier `config` JSON : ajouter clé `"_legacy": true`
- [x] Créer entrées audit `INTEGRATION_MARKED_LEGACY`
- [x] Détecter workflows référençant intégrations legacy
- [x] Afficher avertissements pour workflows impactés
- [x] Tester avec workflow factory utilisant intégration invalide

### Tâche 4 : Option --dry-run (AC10)
- [x] Ajouter argument `--dry-run` à la commande
- [x] Wrapper logique dans transaction avec `set_rollback(True)`
- [x] Afficher banner "MODE DRY-RUN" dans rapport
- [x] Montrer changements prévus sans les appliquer
- [x] Désactiver création entrées audit en dry-run
- [x] Tester que DB reste inchangée après dry-run

### Tâche 5 : Garde-fou ExecutionService (AC4)
- [x] Modifier `executions/services.py:create_execution()`
- [x] Récupérer intégration via `action.integration` FK
- [x] Vérifier `integration.status` AVANT appel adapter
- [x] Si `INVALID` : retourner erreur HTTP 400 + code `INVALID_INTEGRATION`
- [x] Créer audit `EXECUTION_BLOCKED_INVALID_INTEGRATION`
- [x] Si `DEPRECATED` : logger WARNING + créer audit warning
- [x] Si `VALID` : continuer normalement
- [x] Formatter message erreur avec détails complets
- [x] Tester 3 cas (valid, deprecated, invalid)

### Tâche 6 : Garde-fou WorkflowRuntimeService (AC5)
- [x] Modifier `executions/workflow_runtime.py:_execute_step()`
- [x] Récupérer `integration` depuis referenced_action
- [x] Appliquer même validation que Tâche 5
- [x] Si `INVALID` : marquer workflow `FAILED` + erreur explicite
- [x] Créer audit `WORKFLOW_STEP_BLOCKED_INVALID_INTEGRATION`
- [x] Si `DEPRECATED` : logger WARNING + créer audit + continuer
- [x] Tester workflow avec step intégration invalide

### Tâche 7 : Nouveaux types d'audit (AC9)
- [x] Ajouter dans `core/models.py:AuditActionType` :
  - `INTEGRATION_MARKED_LEGACY`
  - `EXECUTION_BLOCKED_INVALID_INTEGRATION`
  - `EXECUTION_DEPRECATED_INTEGRATION_WARNING`
  - `WORKFLOW_STEP_BLOCKED_INVALID_INTEGRATION`
- [x] Note: `INTEGRATION_STATUS_UPDATED` existait déjà (Story 24.3)
- [x] Vérifier cohérence avec autres types audit existants

### Tâche 8 : Tests migration (AC6 - partie 1)
- [x] Créer `integrations/tests/test_analyze_command.py` (6 tests)
- [x] Créer `integrations/tests/test_migrate_command.py` (11 tests)
- [x] Utiliser factories existantes : IntegrationFactory, IntegrationTypeCatalogueFactory
- [x] Test `test_analyze_integrations_report` : vérifier output console + JSON
- [x] Test `test_migrate_integrations_auto_updates_status` : vérifier DB + audit
- [x] Test `test_migrate_integrations_no_updates_needed` : cas déjà à jour
- [x] Test `test_mark_legacy_invalid_integrations` : vérifier config modifié
- [x] Test `test_mark_legacy_warns_about_workflows` : détection workflows
- [x] Test `test_dry_run_no_changes` : vérifier rollback transaction

### Tâche 9 : Tests garde-fous (AC6 - partie 2)
- [x] Créer `executions/tests/test_execution_integration_validation.py` (6 tests)
- [x] Test `test_trigger_execution_blocks_invalid_integration` : BadRequestError + audit
- [x] Test `test_trigger_execution_warns_deprecated_integration` : log + audit + OK
- [x] Test `test_trigger_execution_allows_valid_integration` : aucun warning
- [x] Test `test_workflow_step_fails_invalid_integration` : workflow FAILED
- [x] Test `test_workflow_step_warns_deprecated_integration` : log + continue
- [x] Utiliser `pytest.raises` pour vérifier exceptions
- [x] Vérifier entrées audit créées avec `AuditService`

### Tâche 10 : Documentation migration (AC7)
- [x] Créer fichier `docs/integration-migration-guide.md`
- [x] Section 1 : Vue d'ensemble Epic 24
- [x] Section 2 : Étapes de migration (5 étapes détaillées)
- [x] Section 3 : Scénarios de migration (A, B, C)
- [x] Section 4 : Dépannage (FAQ)
- [x] Section 5 : Référence commandes (options CLI complètes)
- [x] Ajouter exemples de sorties de commandes réelles
- [x] Lien vers docs catalogue (Story 24.1)

### Tâche 11 : Logging structuré (AC8)
- [x] Ajouter logs `structlog` dans `migrate_integrations` :
  - `integration_migration_started`
  - `integration_status_updated` (par intégration)
  - `integration_migration_completed`
- [x] Ajouter logs dans garde-fous :
  - `execution_blocked_invalid_integration` (ERROR)
  - `execution_with_deprecated_integration` (WARNING)
- [x] Inclure `correlation_id` dans tous les logs
- [x] Format JSON via structlog (Splunk-compatible)

### Tâche 12 : Validation et nettoyage
- [x] Exécuter tous les tests story 24.4 : 23/23 passent
- [x] Régression integrations tests : 232/232 passent
- [x] Régression execution service tests : 3/3 passent
- [x] Régression workflow runtime tests : 42/42 passent
- [x] Documentation inline (docstrings) à jour
- [x] File List rempli avec fichiers créés/modifiés

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Transaction atomique `create_execution` : L'audit entry pour `EXECUTION_BLOCKED_INVALID_INTEGRATION` était rollback avec la transaction quand `BadRequestError` était levée. Fix : séparer `create_execution()` en wrapper non-atomique + `_create_execution_atomic()`.

### Completion Notes List

- 12/12 tâches complétées
- 23/23 tests story 24.4 passent (6 analyze + 11 migrate + 6 garde-fous)
- 232/232 tests integrations passent (0 régression)
- 3/3 tests execution service passent
- 42/42 tests workflow runtime passent
- 64 échecs pré-existants dans la suite globale (redirections 301, rate limiting 429, IntegrityError soft-delete) — non liés aux changements
- AC1-AC10 tous validés

**Code Review 2026-02-10** :
- 5 problèmes trouvés (3 MEDIUM + 2 LOW) — tous corrigés automatiquement
- MEDIUM-1: Rapports JSON maintenant dans `logs/integrations/` avec écriture atomique
- MEDIUM-2: Documentation corrigée (commande `validate_integrations` inexistante → `migrate_integrations --auto`)
- MEDIUM-3: Logging durée ajouté pour `_handle_auto` et `_handle_mark_legacy`
- LOW-1: Import `uuid` inutilisé retiré
- LOW-2: Tests mis à jour pour nouveau chemin JSON
- 23/23 tests passent après corrections ✅

### Change Log

- `core/models.py` : +4 `AuditActionType` (INTEGRATION_MARKED_LEGACY, EXECUTION_BLOCKED_*, WORKFLOW_STEP_BLOCKED_*)
- `executions/services.py` : `create_execution()` splitté en wrapper + `_create_execution_atomic()`, ajout `_check_integration_status()`
- `executions/workflow_runtime.py` : validation intégration dans `_execute_step()`, `select_related('integration')`

### File List

**Fichiers créés :**
- `integrations/management/commands/analyze_integrations.py` — AC1
- `integrations/management/commands/migrate_integrations.py` — AC2, AC3, AC10
- `integrations/tests/test_analyze_command.py` — AC6 (6 tests)
- `integrations/tests/test_migrate_command.py` — AC6 (11 tests)
- `executions/tests/test_execution_integration_validation.py` — AC6 (6 tests)
- `docs/integration-migration-guide.md` — AC7

**Fichiers modifiés :**
- `core/models.py` — AC9 : nouveaux `AuditActionType`
- `executions/services.py` — AC4 : garde-fou `create_execution`
- `executions/workflow_runtime.py` — AC5 : garde-fou `_execute_step`
