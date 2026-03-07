# Analyse de couverture — Épic 55 : Objectif 90 % backend et frontend

**Date :** 2026-02-28
**Auteur :** Agent de développement (story 55.1)
**Statut :** Document de référence pour les stories 55.2 – 55.7
**Baseline :** Voir [coverage-analysis-epic-39.md](../reference/coverage-analysis-epic-39.md)

---

## 1. Résumé exécutif

| Métrique | Baseline Epic 39 (24 fév) | Post-Epic 54 (28 fév) | Progression |
|----------|--------------------------|----------------------|-------------|
| Couverture backend (stmts) | 84,65 % combinée¹ | **88,84 %** | +4,19 pts |
| Stmts backend totales | 13 431 | 14 991 (+1 560 nouveaux stmts) | +11,6 % de code |
| Stmts backend manquantes | 1 785 | 1 441 | -344 |
| Fichiers backend < 80 % | 24 | **13** | -11 fichiers |
| Fichiers backend 80–90 % | ~30 (estimé) | **43** | à traiter |
| Couverture frontend stmts (périmètre hooks+comps) | 77,57 % | **84,88 %** (global) | +7,3 pts |
| Fichiers hooks < 80 % | estimé ~10 (24 fév pre-39.7) | **1** | -9+ fichiers |
| Fichiers composants < 80 % | 36 (24 fév pre-39.7) | **34** | -2 fichiers |
| Fichiers frontend (hooks) 80–90 % | N/A | **16** | à traiter |
| Fichiers frontend (comps) 80–90 % | N/A | **24** | à traiter |

> ¹ La métrique Epic 39 incluait branches dans le calcul ; la valeur post-Epic 54 est la couverture statements pure.

**Commandes exécutées :**
- Backend : `python -m pytest --cov=. --cov-report=term-missing --cov-report=json -m "not slow and not benchmark and not integration"` (4 279 tests passés, 5 échecs pré-existants dans `audit/tests/`)
- Frontend : `npm run test:coverage` (vitest --coverage v8)

---

## 2. Backend — Fichiers < 80 %

13 fichiers identifiés, triés par couverture croissante.

| Couverture | Fichier | Stmts | Manquantes | Domaine | Priorité |
|------------|---------|-------|------------|---------|----------|
| **0,0 %** | `idp_backend/routing.py` | 3 | 3 | Config ASGI | Basse (config) |
| **35,7 %** | `idp_backend/celery.py` | 80 | 50 | Config Celery | Basse (config)² |
| **39,7 %** | `dashboard/views.py` | 226 | 129 | ViewSet dashboard | **Haute** |
| **41,9 %** | `inventory/mapping_validator.py` | 21 | 10 | Validation mapping (Epic 54-14) | **Haute** |
| **44,4 %** | `admin_analytics/views.py` | 34 | 18 | ViewSet analytics admin | Moyenne |
| **72,9 %** | `integrations/tasks.py` | 133 | 35 | Tâches Celery intégrations | **Haute** |
| **73,1 %** | `idp_auth/views/favorites.py` | 26 | 7 | Vues favoris (Epic 54-7) | Moyenne |
| **74,2 %** | `audit/views.py` | 222 | 45 | ViewSet audit | Moyenne |
| **75,8 %** | `utils/json_helpers.py` | 59 | 13 | Utilitaire JSON | Basse |
| **76,4 %** | `inventory/services.py` | 228 | 54 | Service inventory | **Haute** |
| **76,4 %** | `inventory/query_builder.py` | 276 | 59 | Query builder (Epic 54-14) | **Haute** |
| **76,6 %** | `inventory/query_executor.py` | 173 | 38 | Orchestrateur query (Epic 54-14) | **Haute** |
| **78,8 %** | `executions/workflow_step_executor.py` | 169 | 28 | Exécuteur étapes workflow | **Haute** |

> ² `idp_backend/celery.py` : fichier de configuration Celery. La couverture a diminué par rapport à Epic 39 (63,6 %) car le fichier a été étendu (80 stmts contre ~18 lignes estimées). Les blocs de workers, beat, et routing Celery sont structurellement difficiles à tester unitairement. Maintenu comme priorité basse.

### Comparaison avec la baseline Epic 39

Fichiers qui **étaient** < 80 % en Epic 39 et sont maintenant **≥ 90 %** (améliorés par les stories 39.x) :

| Fichier | Était (Epic 39) | Maintenant | Amélioré par |
|---------|----------------|------------|--------------|
| `catalog/management/commands/migrate_inline_policies.py` | 0,0 % | **95,7 %** | Story 39.x |
| `integrations/management/commands/purge_orphan_icons.py` | 0,0 % | **100 %** | Story 39.x |
| `executions/scheduling_service.py` | 38,6 % | **100 %** | Story 39.x |
| `executions/utils/rbac_helpers.py` | 42,9 % | **100 %** | Story 39.x |
| `executions/consumers.py` | 43,4 % | **100 %** | Story 39.x |
| `core/services.py` | 48,9 % | **97,9 %** | Story 39.x |
| `executions/views/list_views.py` | 56,3 % | **100 %** | Story 39.x |
| `core/auth_utils.py` | 59,5 % | **95,2 %** | Story 39.x |
| `executions/services.py` | 61,3 % | **97,4 %** | Story 39.x |
| `executions/views/terraform_webhooks.py` | 72,7 % | **99,2 %** | Story 39.x |
| `catalog/views/tags_views.py` | 73,8 % | **98,5 %** | Story 39.x |
| `executions/views/approval_views.py` | 75,0 % | **100 %** | Story 39.x |
| `executions/utils/workflow_parsing.py` | 75,1 % | **94,7 %** | Story 39.x |
| `executions/views/github_webhooks.py` | 76,5 % | **100 %** | Story 39.x |
| `idp_auth/services.py` | 77,2 % | **100 %** | Story 39.x |
| `core/logging.py` | 78,9 % | **100 %** | Story 39.x |
| `catalog/validators.py` | 79,4 % | **96,3 %** | Story 39.x |

Fichiers qui **étaient** < 80 % en Epic 39 et **restent** problématiques :

| Fichier | Était (Epic 39) | Maintenant | Notes |
|---------|----------------|------------|-------|
| `idp_backend/routing.py` | 0,0 % | 0,0 % | Config — pas de tests unitaires possibles |
| `idp_backend/celery.py` | 63,6 % | 35,7 % | Fichier étendu, config Celery difficile à tester |
| `dashboard/views.py` | 39,7 % | 39,7 % | Inchangé — priorité story 55.2 |
| `admin_analytics/views.py` | 44,4 % | 44,4 % | Inchangé — priorité story 55.2 |
| `audit/views.py` | 69,6 % | 74,2 % | Légère amélioration (+4,6 pts) |
| `utils/json_helpers.py` | 75,8 % | 75,8 % | Inchangé |

---

## 3. Backend — Fichiers 80–90 % (à compléter pour atteindre 90 %)

43 fichiers entre 80 % et 90 %, triés par couverture croissante.

| Couverture | Fichier | Stmts | Manquantes | Domaine |
|------------|---------|-------|------------|---------|
| **80,4 %** | `executions/runtime_registry.py` | 40 | 8 | Registre runtimes |
| **80,5 %** | `profiles/serializers.py` | 180 | 25 | Sérialiseurs profils |
| **80,5 %** | `core/startup_checks.py` | 137 | 27 | Checks démarrage |
| **80,6 %** | `executions/container_workflow_runtime.py` | 231 | 43 | Runtime container |
| **81,1 %** | `idp_auth/views/jwt.py` | 89 | 15 | Vues JWT (Epic 54-7) |
| **81,6 %** | `catalog/serializers.py` | 334 | 49 | Sérialiseurs catalogue |
| **81,8 %** | `profiles/cache.py` | 11 | 2 | Cache profils |
| **82,2 %** | `services/splunk_service.py` | 166 | 26 | Service Splunk |
| **82,5 %** | `catalog/views/action_views.py` | 307 | 40 | Vues actions |
| **82,8 %** | `catalog/services.py` | 338 | 53 | Services catalogue |
| **82,8 %** | `executions/views/execution_views.py` | 306 | 50 | Vues exécutions |
| **83,1 %** | `catalog/views/catalog_views.py` | 126 | 16 | Vues catalogue |
| **83,5 %** | `executions/utils/filters.py` | 89 | 12 | Filtres exécutions |
| **83,8 %** | `executions/gate_evaluator.py` | 102 | 14 | Évaluateur gates |
| **83,9 %** | `executions/utils/scheduling.py` | 46 | 7 | Utilitaire scheduling |
| **84,2 %** | `executions/gate_context.py` | 15 | 2 | Contexte gates |
| **84,3 %** | `executions/rule_engine.py` | 172 | 24 | Moteur de règles |
| **84,9 %** | `adapters/terraform_cloud_adapter.py` | 212 | 28 | Adapter Terraform Cloud³ |
| **85,0 %** | `adapters/utils.py` | 103 | 15 | Utilitaires adapters |
| **85,2 %** | `executions/interpreters/terraform_plan_interpreter.py` | 76 | 9 | Interpréteur plans TF |
| **85,2 %** | `executions/tasks/cleanup.py` | 53 | 8 | Tâches nettoyage |
| **85,6 %** | `inventory/mapper.py` | 185 | 25 | Mappeur inventory |
| **85,6 %** | `executions/views/remediation_views.py` | 79 | 11 | Vues remédiation |
| **85,7 %** | `executions/builders/response_builder.py` | 12 | 1 | Constructeur réponse |
| **85,8 %** | `adapters/aap_adapter.py` | 156 | 21 | Adapter AAP |
| **86,9 %** | `adapters/azure_devops_adapter.py` | 172 | 16 | Adapter Azure DevOps |
| **87,1 %** | `executions/views/scheduled_views.py` | 294 | 32 | Vues scheduled |
| **87,6 %** | `integrations/models.py` | 153 | 15 | Modèles intégrations |
| **87,9 %** | `executions/simulation_service.py` | 104 | 10 | Service simulation |
| **88,0 %** | `core/splunk_logging_handler.py` | 124 | 13 | Handler logging Splunk |
| **88,0 %** | `services/jira_service.py` | 118 | 11 | Service Jira |
| **88,4 %** | `profiles/models.py` | 176 | 22 | Modèles profils |
| **88,5 %** | `inventory/permission_aggregator.py` | 100 | 10 | Agrégateur permissions |
| **88,6 %** | `executions/models.py` | 216 | 22 | Modèles exécutions |
| **88,6 %** | `executions/tasks/scheduled.py` | 72 | 6 | Tâches scheduled |
| **88,7 %** | `integrations/validation.py` | 44 | 4 | Validation intégrations |
| **88,7 %** | `executions/tasks/polling.py` | 131 | 16 | Tâches polling |
| **89,4 %** | `executions/validators/target_validator.py` | 37 | 4 | Validateur cibles |
| **89,4 %** | `core/feature_flags.py` | 146 | 12 | Feature flags |
| **89,4 %** | `core/views.py` | 58 | 4 | Vues core |
| **89,4 %** | `core/permissions.py` | 75 | 5 | Permissions core |
| **89,5 %** | `core/consumers.py` | 47 | 4 | Consumers WebSocket |
| **89,8 %** | `integrations/services.py` | 173 | 12 | Services intégrations |

> ³ `adapters/terraform_cloud_adapter.py` : Fichier **modifié localement** (git status `M`) mais non commité. Sa couverture post-modification est 84,9 % (28 stmts manquantes sur 212). À traiter en priority story 55.4.

---

## 4. Backend — Fichiers nouveaux ou refactorisés (Epic 54) sans tests suffisants

| Story | Fichier | Couverture | Stmts miss. | Action requise |
|-------|---------|------------|-------------|----------------|
| 54-14 | `inventory/mapping_validator.py` | **41,9 %** ⚠️ | 10/21 | Tests unitaires — story 55.2 |
| 54-14 | `inventory/query_builder.py` | **76,4 %** ⚠️ | 59/276 | Tests SQL builder — story 55.2 |
| 54-14 | `inventory/query_executor.py` | **76,6 %** ⚠️ | 38/173 | Tests orchestration — story 55.2 |
| 54-7 | `idp_auth/views/favorites.py` | **73,1 %** ⚠️ | 7/26 | Tests vues favoris — story 55.2 |
| 54-7 | `idp_auth/views/jwt.py` | **81,1 %** | 15/89 | Tests JWT — story 55.4 |
| 54-11 | `adapters/status_mappers.py` | **100 %** ✅ | 0/27 | Aucune action requise |
| 54-14 | `inventory/result_paginator.py` | **100 %** ✅ | 0/22 | Aucune action requise |
| 54-6 | `executions/services.py` | **97,4 %** ✅ | 6/247 | Aucune action requise |
| 54-7 | `idp_auth/views/saml.py` | **100 %** ✅ | 0/86 | Aucune action requise |
| 54-7 | `idp_auth/views/api_keys.py` | **98,7 %** ✅ | 0/68 | Aucune action requise |
| 54-7 | `idp_auth/views/service_login.py` | **100 %** ✅ | 0/57 | Aucune action requise |

**Note :** `terraform_cloud_adapter.py` (git status `M`, non commité) est actuellement à **84,9 %**. Son état final dépend du commit de la modification en cours.

---

## 5. Frontend — Fichiers < 80 % (hooks — périmètre `src/hooks/**/*.ts`)

1 seul hook sous 80 % :

| Couverture stmts | Couverture branches | Fichier | Stmts | Manquantes | Notes |
|-----------------|---------------------|---------|-------|------------|-------|
| **73,4 %** | **38 %** | `src/hooks/useActionsAdminPanel.ts` | 124 | 33 | Epic 54-15 — nouveau hook extrait |

---

## 6. Frontend — Fichiers 80–90 % (hooks — à compléter pour 90 %)

16 hooks entre 80 % et 90 % :

| Couverture stmts | Couverture branches | Fichier | Stmts | Manquantes |
|-----------------|---------------------|---------|-------|------------|
| **80,0 %** | 41 % | `src/hooks/useAuditFilters.ts` | 130 | 26 |
| **80,0 %** | 74 % | `src/hooks/useExecutionWizardState.ts` | 265 | 53 |
| **81,6 %** | 70 % | `src/hooks/useWorkflowGraph.ts` | 136 | 25 |
| **82,4 %** | 75 % | `src/hooks/useRemediationContext.ts` | 34 | 6 |
| **83,3 %** | 25 % | `src/hooks/useIntegrations.ts` | 18 | 3 |
| **86,5 %** | 25 % | `src/hooks/useApiKeys.ts` | 37 | 5 |
| **86,6 %** | 36 % | `src/hooks/useExecutionsData.ts` | 149 | 20 |
| **86,9 %** | 67 % | `src/hooks/useEnvironments.ts` | 61 | 8 |
| **87,5 %** | 67 % | `src/hooks/useEngines.ts` | 48 | 6 |
| **87,8 %** | 82 % | `src/hooks/useCalendarFilters.ts` | 49 | 6 |
| **87,9 %** | 65 % | `src/hooks/useWorkflowStepActions.ts` | 33 | 4 |
| **89,3 %** | 74 % | `src/hooks/useExecutionSubmit.ts` | 56 | 6 |
| **89,4 %** | 73 % | `src/hooks/useCatalogState.ts` | 151 | 16 |
| **89,5 %** | 60 % | `src/hooks/useExecutionSteps.ts` | 19 | 2 |
| **89,5 %** | 74 % | `src/hooks/useIntegrationTypes.ts` | 57 | 6 |
| **89,8 %** | 70 % | `src/hooks/useProfileFormState.ts` | 59 | 6 |

---

## 7. Frontend — Fichiers < 80 % (composants — périmètre `src/components/**/*.tsx`)

34 composants sous 80 %, triés par couverture croissante :

| Couverture stmts | Couverture branches | Fichier | Stmts | Manquantes | Domaine |
|-----------------|---------------------|---------|-------|------------|---------|
| **0,0 %** | 0 % | `src/components/admin/CategoryForm.tsx` | 20 | 20 | Admin |
| **0,0 %** | 0 % | `src/components/admin/FeatureFlagsPanel.tsx` | 57 | 57 | Admin |
| **0,0 %** | 0 % | `src/components/dashboard/ExecutionsChart.tsx` | 10 | 10 | Dashboard |
| **16,7 %** | 0 % | `src/components/dashboard/reporting/PeriodComparisonChart.tsx` | 12 | 10 | Dashboard |
| **50,0 %** | 63 % | `src/components/admin/WizardStep3ImpactChangement.tsx` | 2 | 1 | Admin |
| **53,8 %** | 31 % | `src/components/dashboard/reporting/ComparisonPanel.tsx` | 26 | 12 | Dashboard |
| **56,2 %** | 65 % | `src/components/admin/ActionPalette.tsx` | 16 | 7 | Admin |
| **57,1 %** | 60 % | `src/components/calendar/EditExecutionModal.tsx` | 7 | 3 | Calendrier |
| **57,9 %** | 50 % | `src/components/admin/ProfilesTable.tsx` | 19 | 8 | Admin |
| **58,1 %** | 64 % | `src/components/admin/BusinessRulesPolicyPanel.tsx` | 62 | 26 | Admin |
| **58,1 %** | 91 % | `src/components/catalog/SchedulingPanel.tsx` | 31 | 13 | Catalogue |
| **59,4 %** | 79 % | `src/components/admin/BusinessRulePolicySelector.tsx` | 32 | 13 | Admin |
| **60,8 %** | 71 % | `src/components/admin/IntegrationForm.tsx` | 97 | 38 | Admin |
| **61,4 %** | 68 % | `src/components/admin/IntegrationsTable.tsx` | 57 | 22 | Admin |
| **61,7 %** | 68 % | `src/components/admin/ParametersEditor.tsx` | 60 | 23 | Admin |
| **66,2 %** | 69 % | `src/components/admin/StepsEditor.tsx` | 68 | 23 | Admin |
| **66,7 %** | 94 % | `src/components/catalog/ActionDrawerPreview.tsx` | 45 | 15 | Catalogue |
| **66,7 %** | 100 % | `src/components/admin/CustomEdge.tsx` | 9 | 3 | Admin |
| **69,2 %** | 45 % | `src/components/dashboard/reporting/ComparisonChart.tsx` | 13 | 4 | Dashboard |
| **69,2 %** | 100 % | `src/components/admin/WorkflowBuilderCanvas.tsx` | 13 | 4 | Admin |
| **70,9 %** | 60 % | `src/components/admin/ActionWizard.tsx` | 189 | 55 | Admin |
| **71,4 %** | 46 % | `src/components/dashboard/reporting/EnvironmentBarChart.tsx` | 14 | 4 | Dashboard |
| **71,4 %** | 46 % | `src/components/dashboard/reporting/TechnologyBarChart.tsx` | 14 | 4 | Dashboard |
| **71,8 %** | 60 % | `src/components/dashboard/RecentExecutions.tsx` | 71 | 20 | Dashboard |
| **75,0 %** | 52 % | `src/components/execution/ExecutionTimeline/RemediationPanel.tsx` | 4 | 1 | Exécutions |
| **75,0 %** | 71 % | `src/components/dashboard/reporting/AdvancedFiltersPanel.tsx` | 28 | 7 | Dashboard |
| **75,8 %** | 62 % | `src/components/dashboard/reporting/ReportingDashboard.tsx` | 66 | 16 | Dashboard |
| **76,3 %** | 76 % | `src/components/admin/NotificationConfigSection.tsx` | 38 | 9 | Admin |
| **76,9 %** | 61 % | `src/components/admin/ActionForm.tsx` | 65 | 15 | Admin |
| **76,9 %** | 63 % | `src/components/admin/WorkflowStepsEditor.tsx` | 78 | 18 | Admin |
| **76,9 %** | 76 % | `src/components/admin/WizardStep2Automatisme.tsx` | 13 | 3 | Admin |
| **78,6 %** | 38 % | `src/components/audit/AuditFiltersPanel.tsx` | 14 | 3 | Audit |
| **78,8 %** | 92 % | `src/components/execution/ExecutionView.tsx` | 33 | 7 | Exécutions |
| **78,9 %** | 75 % | `src/components/catalog/TargetSelectionStep.tsx` | 19 | 4 | Catalogue |

---

## 8. Frontend — Fichiers 80–90 % (composants — à compléter pour 90 %)

24 composants entre 80 % et 90 % :

| Couverture stmts | Couverture branches | Fichier | Stmts | Manquantes |
|-----------------|---------------------|---------|-------|------------|
| **80,0 %** | 38 % | `src/components/execution/ExecutionTimeline/TimelineList.tsx` | 5 | 1 |
| **80,0 %** | 73 % | `src/components/catalog/ExecutionWizard.tsx` | 20 | 4 |
| **80,0 %** | 83 % | `src/components/admin/WizardStep1General.tsx` | 10 | 2 |
| **80,6 %** | 90 % | `src/components/admin/CategoriesAdminTable.tsx` | 36 | 7 |
| **81,1 %** | 74 % | `src/components/catalog/TargetSelector.tsx` | 53 | 10 |
| **82,9 %** | 68 % | `src/components/admin/SortableStepCard.tsx` | 41 | 7 |
| **83,0 %** | 66 % | `src/components/audit/AuditTable.tsx` | 47 | 8 |
| **83,3 %** | 77 % | `src/components/admin/ChangeTypeConfig.tsx` | 84 | 14 |
| **83,3 %** | 100 % | `src/components/ErrorBoundary.tsx` | 24 | 4 |
| **83,9 %** | 40 % | `src/components/admin/ProfileImportModal.tsx` | 31 | 5 |
| **84,2 %** | 93 % | `src/components/catalog/ActiveFiltersChips.tsx` | 19 | 3 |
| **84,6 %** | 64 % | `src/components/dashboard/reporting/TrendLineChart.tsx` | 13 | 2 |
| **85,7 %** | 76 % | `src/components/audit/AuditEntryDrawer.tsx` | 14 | 2 |
| **86,0 %** | 83 % | `src/components/layout/TopNav.tsx` | 43 | 6 |
| **86,1 %** | 82 % | `src/components/admin/StepConfigPanel.tsx` | 36 | 5 |
| **86,4 %** | 55 % | `src/components/executions/ExecutionsFiltersPanel.tsx` | 22 | 3 |
| **86,7 %** | 71 % | `src/components/admin/ProfileForm.tsx` | 113 | 15 |
| **87,0 %** | 67 % | `src/components/calendar/CalendarFiltersPanel.tsx` | 23 | 3 |
| **87,0 %** | 73 % | `src/components/catalog/WorkflowStepsRenderer.tsx` | 23 | 3 |
| **87,2 %** | 83 % | `src/components/admin/EnginesAdminTable.tsx` | 39 | 5 |
| **87,3 %** | 76 % | `src/components/admin/BusinessRulePolicyModal.tsx` | 55 | 7 |
| **87,8 %** | 89 % | `src/components/admin/RemediationRulesEditor.tsx` | 41 | 5 |
| **88,0 %** | 70 % | `src/components/admin/ProfileWizard.tsx` | 75 | 9 |
| **88,9 %** | 67 % | `src/components/dashboard/PendingApprovalsList.tsx` | 45 | 5 |

---

## 9. Frontend — Fichiers nouveaux (Epic 54) sans tests suffisants

| Story | Fichier | Couverture stmts | Couverture branches | Statut |
|-------|---------|-----------------|---------------------|--------|
| 54-8 | `src/hooks/useIntegrationFormState.ts` | **100 %** | 93 % | ✅ Bien couvert |
| 54-12 | `src/hooks/useWorkflowGraph.ts` | **81,6 %** | 70 % | ⚠️ 80–90 % — story 55.6 |
| 54-15 | `src/hooks/useActionsAdminPanel.ts` | **73,4 %** | 38 % | ❌ < 80 % — story 55.5 |
| 54-13 | `src/utils/executionStatusRenderer.tsx` | Hors périmètre | N/A | Hors scope hooks+comps |
| 54-16 | `src/utils/dateFormat.ts` | Hors périmètre | N/A | Hors scope hooks+comps |

> **Note :** `executionStatusRenderer.tsx` et `dateFormat.ts` sont dans `src/utils/`, hors du périmètre coverage défini (`src/hooks/**/*.ts` + `src/components/**/*.tsx`). Ils ont des tests mais leur couverture n'est pas mesurée dans ce rapport.

---

## 10. Comparaison avec baseline Epic 39

### Backend — Progression globale

| Métrique | Epic 39 (24 fév) | Post-Epic 54 (28 fév) | Gain |
|----------|-----------------|----------------------|------|
| Couverture globale | 84,65 % | **88,84 %** | **+4,19 pts** |
| Stmts totales | 13 431 | 14 991 | +1 560 (Epic 54) |
| Stmts manquantes | 1 785 | 1 441 | -344 |
| Fichiers < 80 % | 24 | **13** | -11 fichiers |

Les stories 39.2–39.6 ont résolu 17 des 24 fichiers sous 80 %. La suppression des 7 fichiers restants est le travail des stories 55.2–55.4.

### Frontend — Progression globale (périmètre hooks + composants)

| Métrique | Epic 39 (24 fév pre-39.7) | Post-Epic 54 (28 fév) | Gain |
|----------|--------------------------|----------------------|------|
| Couverture stmts hooks | ~estimée < 80 % | **90,54 %** | Significant |
| Couverture stmts composants | 77,57 % (global) | **85,71 %** (comps seuls) | +8 pts |
| Fichiers < 80 % (hooks) | ~10+ | **1** | -9+ fichiers |
| Fichiers < 80 % (composants) | 36 | **34** | -2 fichiers |

La story 39.7 a ajouté des tests pour 11 fichiers hooks (réduisant significativement les < 80 %). Les composants restent la priorité principale du frontend.

---

## 11. Recommandations pour les stories 55.2 – 55.7

### Story 55.2 — Backend fichiers 0–80 % (priorité critique)

**Fichiers cibles (5) :**
1. `dashboard/views.py` (39,7 %, 129/226 stmts manquantes) — ViewSet dashboard
2. `inventory/mapping_validator.py` (41,9 %, 10/21 stmts) — Epic 54-14
3. `admin_analytics/views.py` (44,4 %, 18/34 stmts) — Analytics admin
4. `inventory/query_builder.py` (76,4 % → < 60 % après ajout stmts manquantes, 59/276) — Epic 54-14
5. `idp_auth/views/favorites.py` (73,1 %, 7/26 stmts) — Epic 54-7

**Note :** `idp_backend/routing.py` (0 %) et `idp_backend/celery.py` (35,7 %) sont des fichiers de configuration — à exclure des objectifs tests.

### Story 55.3 — Backend fichiers 60–80 % (priorité haute)

**Fichiers cibles (6) :**
1. `integrations/tasks.py` (72,9 %, 35/133 stmts)
2. `audit/views.py` (74,2 %, 45/222 stmts)
3. `utils/json_helpers.py` (75,8 %, 13/59 stmts)
4. `inventory/services.py` (76,4 %, 54/228 stmts)
5. `inventory/query_executor.py` (76,6 %, 38/173 stmts)
6. `executions/workflow_step_executor.py` (78,8 %, 28/169 stmts)

### Story 55.4 — Backend fichiers 80–90 % (compléter vers 90 %)

**Priorité : fichiers à grand impact (gros stmts manquants) :**
- `executions/container_workflow_runtime.py` (80,6 %, 43 stmts)
- `catalog/serializers.py` (81,6 %, 49 stmts)
- `catalog/services.py` (82,8 %, 53 stmts)
- `executions/views/execution_views.py` (82,8 %, 50 stmts)
- `catalog/views/action_views.py` (82,5 %, 40 stmts)
- `adapters/terraform_cloud_adapter.py` (84,9 %, 28 stmts — **commit local en attente**)
- `executions/rule_engine.py` (84,3 %, 24 stmts)

### Story 55.5 — Frontend hooks 0–60 % et composants 0–60 %

**Hooks (1 fichier) :**
- `useActionsAdminPanel.ts` (73,4 % — Epic 54-15)

**Composants (priorité 0 % d'abord) :**
- `CategoryForm.tsx`, `FeatureFlagsPanel.tsx`, `ExecutionsChart.tsx` (0 %)
- `PeriodComparisonChart.tsx` (16,7 %)
- `ComparisonPanel.tsx` (53,8 %)
- `ActionPalette.tsx` (56,2 %), `EditExecutionModal.tsx` (57,1 %)
- Nombreux composants admin entre 58–70 %

### Story 55.6 — Frontend composants 60–80 %

Voir la liste section 7 — composants 60–80 % (environ 20 fichiers).

### Story 55.7 — Frontend hooks et composants 80–90 %

- 16 hooks entre 80–90 % (section 6)
- 24 composants entre 80–90 % (section 8)
- `useWorkflowGraph.ts` (81,6 % — Epic 54-12) : priorité dans cette story

---

## 12. Configuration coverage de référence

### Backend (`idp-portal/django_backend/.coveragerc`)
```
[run]
branch = True
[report]
fail_under = 80
```

### Frontend (`idp-portal/frontend/vite.config.ts`)
- Périmètre : `src/hooks/**/*.ts` + `src/components/**/*.tsx`
- **Pas de seuil `thresholds` configuré** — Vitest ne rejette pas si < 80 %
- Reporter : `v8`
- Coverage JSON : `coverage/coverage-final.json`

### Test runner backend
```bash
# Depuis idp-portal/django_backend/
.venv/bin/python -m pytest --cov=. --cov-report=term-missing --cov-report=json \
  -m "not slow and not benchmark and not integration"
# En cas d'erreurs de collecte (conflits tests.py vs tests/):
# Ajouter --ignore=*/tests.py ou cibler un module spécifique
```

### Résultats de la suite backend (28 fév 2026)
- 4 279 tests passés, 5 échecs (pré-existants dans `audit/tests/test_audit_execution_parameters.py`)
- 4 ignorés, 110 désélectionnés (markers slow/benchmark/integration)
- Durée : ~141 s

---

*Document généré automatiquement par la story 55.1 — Agent claude-sonnet-4-6*
