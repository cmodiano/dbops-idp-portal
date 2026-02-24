# Analyse de couverture — Épic 39 : Objectif 80 % backend et frontend

**Date :** 2026-02-24
**Auteur :** Agent de développement (story 39.1)
**Statut :** Document de référence pour les stories 39.2 – 39.7

---

## 1. Résumé exécutif

| Métrique | Valeur |
|----------|--------|
| Couverture globale backend | **84,65 %** (13 431 lignes, 1 785 manquantes) |
| Tests backend exécutés | 3 477 passés, 3 ignorés |
| Durée suite backend | ~134 s |
| Couverture globale frontend (lignes) | **79,14 %** |
| Couverture globale frontend (instructions) | **77,57 %** |
| Périmètre frontend ciblé | `src/hooks/**/*.ts` + `src/components/**/*.tsx` |

Le backend dépasse le seuil de 80 % globalement mais **24 fichiers** sont en dessous. Le frontend est sous le seuil global (77,57 % stmts) avec plusieurs fichiers à 0 % ou très bas.

---

## 2. Fichiers backend sous 80 % (données au 2026-02-24)

### 2.1 Tableau complet — classé par couverture croissante

| Couverture | Fichier | Lignes totales | Lignes manquantes | Type | Priorité |
|------------|---------|---------------|-------------------|------|----------|
| **0,0 %** | `catalog/management/commands/migrate_inline_policies.py` | 61 | 61 | Management Command | **Haute** |
| **0,0 %** | `idp_backend/routing.py` | 3 | 3 | Config ASGI/routing | Basse |
| **0,0 %** | `integrations/management/commands/purge_orphan_icons.py` | 46 | 46 | Management Command | **Haute** |
| **38,6 %** | `executions/scheduling_service.py` | 90 | 50 | Service scheduling | **Haute** |
| **39,7 %** | `dashboard/views.py` | 226 | 129 | ViewSet dashboard | Moyenne |
| **42,9 %** | `executions/utils/rbac_helpers.py` | 32 | 15 | Utilitaire RBAC | **Haute** |
| **43,4 %** | `executions/consumers.py` | 47 | 24 | WebSocket Consumer | **Haute** |
| **44,4 %** | `admin_analytics/views.py` | 34 | 18 | ViewSet analytics | Moyenne |
| **48,9 %** | `core/services.py` | 68 | 30 | Service audit (AuditService) | **Haute** |
| **56,3 %** | `executions/views/list_views.py` | 79 | 31 | ViewSet API | Moyenne |
| **56,7 %** | `executions/views/scheduled_views.py` | 294 | 116 | ViewSet scheduled | Moyenne |
| **59,5 %** | `core/auth_utils.py` | 26 | 9 | Utilitaire auth | **Haute** |
| **61,3 %** | `executions/services.py` | 247 | 89 | Service métier principal | **Haute** |
| **63,6 %** | `idp_backend/celery.py` | 18 | 5 | Config Celery | Basse |
| **69,6 %** | `audit/views.py` | 196 | 47 | ViewSet audit | Moyenne |
| **72,7 %** | `executions/views/terraform_webhooks.py` | 102 | 27 | Webhook Terraform | Moyenne |
| **73,8 %** | `catalog/views/tags_views.py` | 53 | 11 | ViewSet tags | Moyenne |
| **75,0 %** | `executions/views/approval_views.py` | 94 | 20 | ViewSet approvals | Moyenne |
| **75,1 %** | `executions/utils/workflow_parsing.py` | 133 | 30 | Utilitaire parsing | Moyenne |
| **75,8 %** | `utils/json_helpers.py` | 59 | 13 | Utilitaire JSON | Basse |
| **76,5 %** | `executions/views/github_webhooks.py` | 95 | 22 | Webhook GitHub | Moyenne |
| **77,2 %** | `idp_auth/services.py` | 53 | 11 | Service auth SAML/JWT | **Haute** |
| **78,9 %** | `core/logging.py` | 17 | 3 | Config logging | Basse |
| **79,4 %** | `catalog/validators.py` | 187 | 35 | Validateurs catalogue | Basse |

> **Note :** `idp_backend/routing.py` (3 lignes) et `idp_backend/celery.py` sont des fichiers de configuration ; leur couverture à 0/63 % est peu risquée mais mentionnée pour exhaustivité.

---

## 3. Analyse de la qualité des tests existants

### 3.1 Redondances et faible utilité

#### 3.1.1 Tests RBAC dupliqués (executions/utils/rbac_helpers.py — 42,9 %)
`rbac_helpers.py` est testé **indirectement** via :
- `catalog/tests/test_rbac_service.py`
- `executions/tests/test_execution_views_di.py`
- plusieurs tests d'intégration

**Problème :** Pas de tests unitaires isolés pour les fonctions `check_rbac_*`. Les mocks utilisés dans les tests d'intégration sont trop larges et ne valident pas les branches d'autorisation individuelle.
**Recommandation :** Créer `executions/tests/test_rbac_helpers.py` avec des tests unitaires ciblant chaque fonction d'aide RBAC.

#### 3.1.2 Mocks trop larges dans les tests scheduling (executions/scheduling_service.py — 38,6 %)
`scheduling_service.py` n'a **aucun test direct**. Les tests de `scheduled_views` couvrent le service en passant mais ne valident pas :
- Les transactions atomiques (`atomic()`)
- Le calcul cron (`croniter`)
- Les états de transition (enabled/disabled/erreur)

**Recommandation :** Créer `executions/tests/test_scheduling_service.py` avec injection de dépendances mockées.

#### 3.1.3 Audit trail éparpillé (core/services.py — 48,9 %)
Les assertions d'audit log sont dupliquées dans `core/tests/`, `executions/tests/` et `catalog/tests/`, mais `AuditService` lui-même (export CSV/PDF, règles de rétention) reste peu couvert.
**Recommandation :** Créer un helper partagé `tests/utils/audit_assertions.py` et écrire des tests unitaires directs sur `AuditService`.

#### 3.1.4 Management commands à 0 %
`migrate_inline_policies.py` et `purge_orphan_icons.py` ne sont jamais testés.
- `migrate_inline_policies.py` : risque élevé, migration de données en production
- `purge_orphan_icons.py` : nettoyage d'icônes orphelines, potentielle perte de données

**Recommandation :** Utiliser `django.test.utils.call_command()` avec des fixtures minimales Oracle/SQLite.

#### 3.1.5 WebSocket sans couverture async (executions/consumers.py — 43,4 %)
`consumers.py` n'a aucun test async malgré le fix CRITICAL-5 (race condition `join channel group`).
**Recommandation :** Utiliser `pytest-asyncio` + mock `channel_layer` (pattern disponible dans l'architecture).

### 3.2 Chemins critiques identifiés

| Chemin | Fichiers | Impact | Couverture actuelle |
|--------|----------|--------|---------------------|
| **Auth / RBAC** | `core/auth_utils.py`, `executions/utils/rbac_helpers.py`, `idp_auth/services.py` | Sécurité — accès non autorisé possible | 59,5 % / 42,9 % / 77,2 % |
| **Scheduling** | `executions/scheduling_service.py` | Transactions atomiques, perte d'état | 38,6 % |
| **Audit** | `core/services.py` | Conformité SOC1, export CSV/PDF | 48,9 % |
| **WebSocket** | `executions/consumers.py` | Temps réel, race condition non validée | 43,4 % |
| **Services métier** | `executions/services.py` | Logique d'exécution centrale | 61,3 % |

---

## 4. Couverture frontend (périmètre : hooks + components)

### 4.1 Résumé par dossier

| Dossier | % Stmts | % Branch | % Funcs | % Lignes | Statut |
|---------|---------|----------|---------|---------|--------|
| `components/admin` | 67,75 % | 68,02 % | 58,28 % | 68,69 % | ❌ Sous seuil |
| `components/audit` | 71,87 % | 52,83 % | 81,25 % | 76,66 % | ❌ Sous seuil |
| `components/auth` | 100 % | 100 % | 100 % | 100 % | ✅ |
| `components/calendar` | 81,48 % | 68,0 % | 60,0 % | 81,48 % | ⚠️ Branches |
| `components/catalog` | 85,29 % | 84,62 % | 72,97 % | 86,79 % | ✅ |
| `components/common` | 100 % | 92 % | 100 % | 100 % | ✅ |
| `components/dashboard` | 73,88 % | 59,18 % | 75,0 % | 78,22 % | ❌ Sous seuil |
| `components/dashboard/reporting` | 74,35 % | 56,7 % | 63,51 % | 75,22 % | ❌ Sous seuil |
| `components/execution` | 91,7 % | 87,45 % | 93,47 % | 94,5 % | ✅ |
| `components/executions` | 79,41 % | 74,28 % | 61,11 % | 79,41 % | ⚠️ Limite |
| `components/layout` | 88,46 % | 82,66 % | 70,58 % | 89,79 % | ✅ |
| `components/shared` | 58,33 % | 83,33 % | 28,57 % | 58,33 % | ❌ Sous seuil |
| `hooks` | 81,25 % | 64,02 % | 83,07 % | 83,4 % | ⚠️ Branches |

### 4.2 Fichiers hooks sous 80 % (ou critiques)

| Fichier | % Stmts | % Branch | % Lignes | Note |
|---------|---------|----------|---------|------|
| `useWebSocket.ts` | **3,7 %** | 5,19 % | 3,92 % | Critique — WebSocket non testé |
| `useMediaQuery.ts` | **0,0 %** | 0,0 % | 0,0 % | Non testé |
| `useExecutionFilters.ts` | **47,1 %** | 45,65 % | 62,16 % | Filtres exécutions |
| `useEnvironments.ts` | **68,3 %** | 57,69 % | 70,49 % | Gestion environnements |
| `useExecutionWizardState.ts` | **62,6 %** | 52,3 % | 63,68 % | État wizard exécution |
| `useScheduledExecutionValidation.ts` | **51,7 %** | 54,54 % | 51,72 % | Validation scheduling |
| `useCatalogState.ts` | **75,5 %** | 70,45 % | 75,34 % | État catalogue |
| `useExecutionView.ts` | **78,7 %** | 40,0 % | 82,5 % | Vue exécution — branches |
| `useScheduledExecutions.ts` | **77,5 %** | 50,0 % | 83,33 % | Exécutions planifiées |
| `useTargetIntegrations.ts` | **68,2 %** | 30,0 % | 73,68 % | Intégrations cibles |
| `useProfileIntegrations.ts` | **69,0 %** | 30,0 % | 76,0 % | Intégrations profil |
| `useAuditFilters.ts` | **80,2 %** | **31,8 %** | 80,39 % | Branches audit très basses |

### 4.3 Fichiers components sous 80 % (critiques)

| Fichier | % Stmts | Note |
|---------|---------|------|
| `components/admin/CategoriesAdminTable.tsx` | **0,0 %** | Non testé |
| `components/admin/CategoryForm.tsx` | **0,0 %** | Non testé |
| `components/admin/FeatureFlagsPanel.tsx` | **0,0 %** | Non testé |
| `components/admin/WorkflowBuilderCanvas.tsx` | **29,5 %** | Canvas workflow |
| `components/dashboard/ExecutionsChart.tsx` | **0,0 %** | Non testé |
| `components/calendar/CalendarCreationModal.tsx` | **14,3 %** | Très bas |
| `components/shared/ValidationHelper.tsx` | **44,4 %** | Sous seuil |
| `components/admin/IntegrationsTable.tsx` | **51,9 %** | Sous seuil |
| `components/admin/BusinessRulePolicyPanel.tsx` | **58,1 %** | Sous seuil |
| `components/admin/IntegrationForm.tsx` | **58,9 %** | Sous seuil |
| `components/admin/ParametersEditor.tsx` | **61,7 %** | Sous seuil |
| `components/admin/ActionPalette.tsx` | **65,4 %** | Sous seuil |

### 4.4 Périmètre à élargir ?

Le périmètre actuel (`src/hooks/**/*.ts` + `src/components/**/*.tsx`) est pertinent. Une extension à `src/utils/` et `src/api/` pourrait être envisagée dans une story ultérieure (epic 40) car ces fichiers contiennent de la logique métier utilisée par les hooks. **Recommandation : ne pas élargir dans l'épic 39** pour rester dans les limites de la configuration CI.

---

## 5. Les 18 fichiers backend de l'épic-39 — analyse de risque

| Fichier | Couverture actuelle | Niveau de risque | Observation |
|---------|--------------------|-----------------|----|
| `core/auth_utils.py` | 59,5 % | **ÉLEVÉ** | Impact sécurité direct |
| `core/services.py` | 48,9 % | **ÉLEVÉ** | Audit, conformité SOC1 |
| `core/logging.py` | 78,9 % | Faible | Config logging, peu de logique |
| `catalog/validators.py` | 79,4 % | Faible | Proches du seuil |
| `catalog/views/tags_views.py` | 73,8 % | Moyen | ViewSet tags |
| `catalog/management/commands/migrate_inline_policies.py` | 0,0 % | **ÉLEVÉ** | Migration données production |
| `executions/services.py` | 61,3 % | **ÉLEVÉ** | Service métier central |
| `executions/scheduling_service.py` | 38,6 % | **ÉLEVÉ** | Transactions atomiques |
| `executions/consumers.py` | 43,4 % | **ÉLEVÉ** | Race condition non validée |
| `executions/utils/rbac_helpers.py` | 42,9 % | **ÉLEVÉ** | Sécurité RBAC |
| `executions/utils/workflow_parsing.py` | 75,1 % | Moyen | Parsing workflows |
| `executions/views/list_views.py` | 56,3 % | Moyen | API REST |
| `executions/views/scheduled_views.py` | 56,7 % | Moyen | API planification |
| `executions/views/approval_views.py` | 75,0 % | Moyen | API approbations |
| `executions/views/terraform_webhooks.py` | 72,7 % | Moyen | Webhook Terraform |
| `executions/views/github_webhooks.py` | 76,5 % | Moyen | Webhook GitHub |
| `idp_auth/services.py` | 77,2 % | **ÉLEVÉ** | Auth SAML + JWT |
| `integrations/management/commands/purge_orphan_icons.py` | 0,0 % | **ÉLEVÉ** | Nettoyage données |

> **Note additionnelle :** `dashboard/views.py` (39,7 %) et `admin_analytics/views.py` (44,4 %) ne figurent pas dans la liste initiale de l'epic-39 mais sont des fichiers à faible couverture découverts lors de cette analyse. Ils peuvent être traités en story 39.5 (views).

---

## 6. Recommandations et ordre de traitement

### 6.1 Ordre recommandé pour les stories 39.2 – 39.7

| Ordre | Story | Périmètre | Justification |
|-------|-------|-----------|---------------|
| **1er** | **39.4** | `executions/` core (services, scheduling, consumers, rbac_helpers, workflow_parsing) | Déficit le plus élevé (38–61 %), chemins critiques métier + sécurité RBAC + race condition WebSocket |
| **2e** | **39.2** | `core/` (auth_utils, logging, services) + `idp_backend/` | Impact sécurité direct + audit SOC1 — base partagée par tous les modules |
| **3e** | **39.3** | `catalog/` (validators, tags_views, migrate_inline_policies) | 0 % sur migration données = risque production élevé ; validators proches du seuil |
| **4e** | **39.5** | `executions/views/` (5 ViewSets) + `dashboard/views.py` + `admin_analytics/views.py` | Tests API REST — dépendent logiquement des services couverts en 39.4 |
| **5e** | **39.6** | `idp_auth/services.py` + `integrations/purge_orphan_icons.py` | Proches du seuil (77 %) ou à 0 % mais périmètre limité |
| **6e** | **39.7** | Frontend : hooks + components (cibler fichiers à 0 % et sous 80 %) | Périmètre bien identifié ; peut commencer en parallèle après 39.4 |

### 6.2 Recommandations techniques transversales

1. **Helper d'assertions audit partagé** — Créer `tests/utils/audit_assertions.py` pour éviter la duplication dans core, executions et catalog.
2. **Pattern async pour consumers** — Utiliser `pytest-asyncio` + mock `channel_layer` (voir architecture patterns).
3. **Management commands** — Utiliser `django.test.utils.call_command()` avec fixtures en DB de test.
4. **Mocks RBAC isolés** — Ne plus tester `rbac_helpers.py` via les vues : créer des tests unitaires directs.
5. **Frontend — prioriser les fichiers à 0 %** — `useWebSocket.ts`, `useMediaQuery.ts`, `CategoriesAdminTable.tsx`, `CategoryForm.tsx`, `ExecutionsChart.tsx`, `FeatureFlagsPanel.tsx`.

---

## 7. Patterns de test de référence

| Pattern | Fichier source | Usage |
|---------|---------------|-------|
| Mock structuré + structlog + correlation_id | `catalog/tests/test_rbac_service.py` | Tests RBAC, permissions |
| Tests avec vraie DB (`@pytest.mark.django_db`) | `core/tests/test_services.py` | Services avec transactions |
| Management command | `integrations/tests/test_management.py` | `call_command()` + DB fixture |
| Async WebSocket | À créer | `pytest-asyncio` + mock `channel_layer` |
| Frontend hook | `src/hooks/usePendingApprovalsCount.test.tsx` | Hooks avec MSW |
| Frontend component | `src/components/admin/ActionForm.test.tsx` | Components complexes |

---

## 8. Structure de test existante (état au 2026-02-24)

```
django_backend/
├── core/tests/              # 23 fichiers, ~85 % moy.  — bien structuré
├── catalog/tests/           # 28 fichiers, ~82 % moy.  — excellent pattern RBAC
├── executions/tests/        # 60 fichiers, ~78 % moy.  — volume élevé, qualité inégale
├── idp_auth/tests/          # 11 fichiers, ~78 % moy.
├── integrations/tests/      # 25 fichiers, ~75 % moy.
└── utils/tests.py           # Test unique, pas de répertoire dédié

frontend/src/
├── hooks/*.test.tsx         # ~45 fichiers — couverture inégale
├── components/**/*.test.tsx # ~60 fichiers — bonne couverture sur execution/catalog
└── pages/**/*.test.tsx      # ~15 fichiers — hors périmètre coverage CI
```

---

## 9. Configuration coverage (référence)

### Backend
```ini
# .coveragerc
[run]
branch = True
omit = */migrations/*, */tests/*, */__init__.py
[report]
fail_under = 80
exclude_lines =
    pragma: no cover
    def __repr__
    @abstractmethod
    raise NotImplementedError
```

### Frontend
```typescript
// vite.config.ts (L28-34)
coverage: {
  provider: 'v8',
  include: ['src/hooks/**/*.ts', 'src/components/**/*.tsx'],
  reporter: ['text', 'json', 'lcov'],
  reportsDirectory: './coverage'
}
```

### CI
- Backend : `.github/workflows/django-tests.yml` — `--cov-fail-under=80`
- Frontend : threshold implicite via rapport Vitest

---

*Document généré par story 39.1 — à mettre à jour après chaque story 39.x*
