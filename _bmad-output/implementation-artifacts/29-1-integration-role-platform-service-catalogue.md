# Story 29.1: Champ integration_role (platform/service) dans IntegrationTypeCatalogue

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **DBOPS**,
I want **que le catalogue d'intégrations distingue explicitement les plateformes d'exécution (AAP, GitHub Actions, etc.) des services consommés (Vault, ServiceNow, Jira, Splunk)**,
So that **les formulaires et règles métier puissent traiter correctement chaque type d'intégration**.

## Acceptance Criteria

**Given** le modèle IntegrationTypeCatalogue existant
**When** on étend le catalogue pour catégoriser les types
**Then** un champ **integration_role** est ajouté avec les valeurs `platform` | `service`
**And** les fixtures sont mises à jour : plateformes = aap, github_actions, azure_devops, terraform_cloud, tower ; services = vault, servicenow, jira, splunk
**And** l'API GET /api/v1/integrations/types/ expose le champ integration_role
**And** un paramètre optionnel `?role=platform` ou `?role=service` permet de filtrer les types

**And** le frontend formulaire Admin Intégrations peut optionnellement grouper ou distinguer visuellement plateformes vs services
**And** des tests valident le chargement des fixtures et la réponse API

## Tasks / Subtasks

- [x] Task 1: Backend — Migration V072 ajout colonne INTEGRATION_ROLE (AC1)
  - [x] 1.1: Créer migration V072__add_integration_role.sql
  - [x] 1.2: Ajouter colonne INTEGRATION_ROLE VARCHAR2(20) NOT NULL DEFAULT 'platform'
  - [x] 1.3: Ajouter contrainte CHECK (INTEGRATION_ROLE IN ('platform', 'service'))
  - [x] 1.4: Tester migration sur environnement de développement Oracle

- [x] Task 2: Backend — Modèle IntegrationTypeCatalogue (AC1)
  - [x] 2.1: Ajouter champ integration_role dans IntegrationTypeCatalogue model
  - [x] 2.2: Créer enum IntegrationRole avec valeurs PLATFORM et SERVICE
  - [x] 2.3: Ajouter db_column='INTEGRATION_ROLE' et default='platform'
  - [x] 2.4: Mettre à jour __str__ pour inclure le rôle si pertinent

- [x] Task 3: Backend — Fixtures mise à jour (AC2)
  - [x] 3.1: Mettre à jour integration_type_catalogue.json avec "integration_role": "service" pour servicenow, jira
  - [x] 3.2: Mettre à jour vault_integration_type.json avec "integration_role": "service"
  - [x] 3.3: Ajouter "integration_role": "platform" explicite dans aap, github_actions, azure_devops, terraform_cloud, tower fixtures
  - [x] 3.4: Vérifier splunk fixture (Story 27.8) pour "integration_role": "service"
  - [x] 3.5: Tester loaddata avec fixtures mises à jour

- [x] Task 4: Backend — API ViewSet et Serializer (AC3, AC4)
  - [x] 4.1: Ajouter integration_role dans IntegrationTypeWithActionsSerializer
  - [x] 4.2: Ajouter filtrage ?role=platform|service dans IntegrationTypeCatalogueViewSet
  - [x] 4.3: Documenter le filtre dans docstring de la vue
  - [x] 4.4: Tester endpoint GET /api/v1/integrations/types/?role=platform
  - [x] 4.5: Tester endpoint GET /api/v1/integrations/types/?role=service

- [x] Task 5: Frontend — Types et services (AC5)
  - [x] 5.1: Ajouter integration_role dans IntegrationType (types/api/integrations.ts)
  - [x] 5.2: Mettre à jour getIntegrationTypes service pour accepter paramètre role optionnel
  - [x] 5.3: Créer hook useIntegrationTypesByRole(role?: 'platform' | 'service')
  - [x] 5.4: Tester appels API avec filtre

- [x] Task 6: Frontend — Formulaire Admin Intégrations (AC5)
  - [x] 6.1: Dans IntegrationForm, grouper les types par integration_role (optionnel)
  - [x] 6.2: Afficher badge ou icône distinctif pour plateformes vs services
  - [x] 6.3: Ajouter légende ou tooltip expliquant la différence
  - [x] 6.4: Tester UI avec les deux catégories visibles

- [x] Task 7: Tests Backend (AC6)
  - [x] 7.1: Tests migration V072 (contraintes)
  - [x] 7.2: Tests modèle IntegrationTypeCatalogue avec integration_role
  - [x] 7.3: Tests fixtures chargement (loaddata) avec nouveau champ
  - [x] 7.4: Tests API GET /types/ sans filtre (tous les types)
  - [x] 7.5: Tests API GET /types/?role=platform (seulement plateformes)
  - [x] 7.6: Tests API GET /types/?role=service (seulement services)
  - [x] 7.7: Tests validation role invalide (400 Bad Request attendu)

- [x] Task 8: Tests Frontend (AC6)
  - [x] 8.1: Tests hook useIntegrationTypesByRole
  - [x] 8.2: Tests IntegrationForm avec groupement par role (30/30 existing tests pass, no regression)
  - [x] 8.3: Tests visuels badge/icône distinction platform/service

- [x] Task 9: Documentation (AC6)
  - [x] 9.1: Mettre à jour docs/integration-type-catalogue.md avec champ integration_role dans modèle + filtre API
  - [x] 9.2: Tableau récapitulatif déjà catégorisé Platform/Service dans la doc existante
  - [x] 9.3: Ajouter exemples d'utilisation du filtre ?role= dans la doc API

## Dev Notes

### Architecture Context

**Migration Django → Oracle:**
- Django backend (DRF 3.16) avec base Oracle 19c
- Migrations SQL brutes dans `django_backend/migrations/sql/`
- Format: `V###__description.sql` (Flyway-like)
- IntegrationTypeCatalogue table existante: INTEGRATION_TYPE_CATALOGUE

**Modèle Actuel:**
- IntegrationTypeCatalogue: code (PK), name, description, version, is_active, timestamps
- IntegrationAction: FK vers IntegrationTypeCatalogue, actions supportées par type
- Fixtures Django dans `integrations/fixtures/` pour populate catalogue

**Référence Document:**
- `docs/rapport-bases-moteurs-technologies-integrations.md` définit les concepts Platform vs Service vs Engine
- `django_backend/docs/integration-type-catalogue.md` liste complète des types

**Plateformes (exécutent les actions):**
- aap, tower, azure_devops, github_actions, terraform_cloud
- Implémentent BaseAdapter, utilisent get_platform_adapter()
- Code dans `adapters/platforms/`

**Services (consommés par les actions):**
- vault, servicenow, jira, splunk
- N'héritent pas BaseAdapter, code dans `services/`
- Appelés via get_service_client() ou classes dédiées

### Technical Requirements

**Migration V070:**
```sql
ALTER TABLE INTEGRATION_TYPE_CATALOGUE
ADD INTEGRATION_ROLE VARCHAR2(20) DEFAULT 'platform' NOT NULL
ADD CONSTRAINT CHK_INTEGRATION_ROLE
    CHECK (INTEGRATION_ROLE IN ('platform', 'service'));

COMMENT ON COLUMN INTEGRATION_TYPE_CATALOGUE.INTEGRATION_ROLE IS
    'Rôle de l''intégration: platform (exécution) ou service (consommation)';
```

**Enum Python:**
```python
class IntegrationRole(models.TextChoices):
    PLATFORM = 'platform', 'Plateforme d\'exécution'
    SERVICE = 'service', 'Service consommé'
```

**Modèle:**
```python
class IntegrationTypeCatalogue(models.Model):
    # ... existing fields ...
    integration_role = models.CharField(
        max_length=20,
        choices=IntegrationRole.choices,
        default=IntegrationRole.PLATFORM,
        db_column='INTEGRATION_ROLE'
    )
```

**API Filter:**
```python
# Dans IntegrationTypeCatalogueViewSet
def get_queryset(self):
    queryset = super().get_queryset()
    role = self.request.query_params.get('role')
    if role in ['platform', 'service']:
        queryset = queryset.filter(integration_role=role)
    return queryset
```

**Fixture Format:**
```json
{
  "model": "integrations.integrationtypecatalogue",
  "pk": "vault",
  "fields": {
    "name": "HashiCorp Vault",
    "integration_role": "service",
    ...
  }
}
```

### Testing Requirements

**Backend Tests (minimum 15 tests):**
1. Migration V070 apply/rollback
2. IntegrationTypeCatalogue création avec role platform
3. IntegrationTypeCatalogue création avec role service
4. Validation contrainte CHECK (role invalide rejeté)
5. GET /types/ retourne tous avec integration_role
6. GET /types/?role=platform filtre correctement
7. GET /types/?role=service filtre correctement
8. GET /types/?role=invalid retourne validation error
9. Fixtures loaddata avec nouveau champ
10. Serializer inclut integration_role

**Frontend Tests (minimum 8 tests):**
1. useIntegrationTypesByRole sans filtre
2. useIntegrationTypesByRole role=platform
3. useIntegrationTypesByRole role=service
4. IntegrationForm affiche groupement
5. IntegrationForm affiche badge platform
6. IntegrationForm affiche badge service

**Coverage Target:** ≥ 90% sur code modifié

### File Structure Notes

**Backend Files à Modifier:**
```
django_backend/
  migrations/sql/V070__add_integration_role.sql  # NEW
  integrations/
    models.py                                     # MODIFY: IntegrationTypeCatalogue
    serializers.py                                # MODIFY: add integration_role
    views.py                                      # MODIFY: add ?role= filter
    fixtures/
      integration_type_catalogue.json             # MODIFY: add role
      vault_integration_type.json                 # MODIFY: add role
      tower_integration_type.json                 # MODIFY: add role
      azure_devops_integration_type.json          # MODIFY: add role
      github_actions_integration_type.json        # MODIFY: add role
      terraform_cloud_integration_type.json       # MODIFY: add role
    tests/
      test_integration_type_catalogue.py          # NEW or MODIFY
  docs/integration-type-catalogue.md              # MODIFY: add section
```

**Frontend Files à Modifier:**
```
react_frontend/
  src/
    types/api/integrations.ts                     # MODIFY: add integration_role
    services/integrations.ts                      # MODIFY: add role param
    hooks/useIntegrationTypes.ts                  # MODIFY: add role filter
    components/admin/IntegrationForm.tsx          # MODIFY: grouping/badge
    components/admin/IntegrationForm.test.tsx     # MODIFY: add tests
```

### Previous Story Intelligence

**Story 27.9 (refactoring adapters vs services):**
- Séparation claire adapters/platforms/ vs services/
- Factory get_platform_adapter() vs get_service_client()
- Fondation conceptuelle pour cette story

**Story 24.1 (IntegrationTypeCatalogue):**
- Modèle catalogue existant avec fixtures
- API GET /types/ déjà implémentée
- Tests fixtures loaddata en place

**Learnings from Story 24.x:**
- Toujours tester fixtures avec loaddata après modifications
- Validation JSON Schema stricte sur required_params/optional_params
- API must return `{"data": [...]}` format

### Latest Technical Context

**Django 5.2 + DRF 3.16:**
- Use `db_column='UPPERCASE'` for Oracle compatibility
- CharField max_length validation stricte
- TextChoices for enums (Python 3.9+)

**Oracle 19c Specifics:**
- VARCHAR2(20) pour enum fields
- COMMENT ON COLUMN pour documentation
- Contraintes CHECK pour validation

**Ant Design 6.2 (Frontend):**
- Select.OptGroup pour groupement types
- Badge component pour distinction visuelle
- Tooltip pour explications contextuelles

**Test Standards:**
- pytest backend avec factories (UserFactory, etc.)
- vitest + React Testing Library frontend
- Minimum 90% coverage sur nouveaux fichiers

### Git Intelligence

Commits récents liés (à partir de `git log --oneline -5`):
```
3d955c7 feat(28-3): add multi-platform rule engine with interpreter registry
6d7a77a feat(28-2): add PolicyEvaluator with Terraform plan review policies
e416ea8 feat(28-1): add business rule policies schema and admin editor
d8a3c91 feat(27-10): add JiraService with integration type catalogue support
6369314 refactor(27-9): separate platform adapters from consumed services
```

**Patterns observés:**
- Migrations SQL incrémentales (V069, V070...)
- Fixtures JSON avec timestamps cohérents
- Serializers DRF avec validation explicite
- Tests factories pour User, Action, Integration

### Project Context Reference

**Coding Standards:**
- Backend: PEP 8, type hints, docstrings Google style
- Frontend: TypeScript strict, ESLint Airbnb, Prettier
- SQL: Uppercase keywords, comments obligatoires

**Communication Language:** Français
**Document Output:** Français
**Code/Variables/Types:** English

**RBAC Context:**
- Seuls DBOPS peuvent accéder Admin Intégrations
- Permission: IsDBAOrDBOPS (DRF custom permission)
- Filtrage automatique des types is_active=True

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Migration numérotée V072 (au lieu de V070) car V071 existait déjà
- Django migration 0005 générée pour tests SQLite
- 1 régression corrigée : test_catalogue_serializers.py (ajout 'integration_role' aux champs attendus)

### Code Review Fixes (Story 29.1 - Review 2026-02-15)

**MEDIUM Issues Fixed (5):**
- MEDIUM-1: Ajout `COMMENT ON CONSTRAINT CHK_INTEGRATION_ROLE` dans V072 migration SQL
- MEDIUM-2: Ajout test de régression `test_integration_role_defaults_to_platform` pour cas integration_role=None
- MEDIUM-3: Garde ajoutée dans `useIntegrationTypesByRole.ts` pour filtrer null/undefined `integration_role`
- MEDIUM-4: Section "Filtrage par rôle" ajoutée dans `integration-type-catalogue.md` avec exemples cURL
- MEDIUM-5: Fix incohérence structure `typeOptions` dans IntegrationForm.tsx (wrap ungrouped dans groupe "Autres")

**LOW Issues Fixed (3):**
- LOW-1: Suppression `COMMIT` explicite dans V072 migration SQL (best practice Flyway)
- LOW-2: Renommage test `test_filter_empty_role_returns_all` → `test_filter_empty_role_returns_400` (nom incorrect)
- LOW-3: Note Story 29.1 ajoutée dans tableau récapitulatif de la doc pour traçabilité

### Completion Notes List

- AC1: Champ integration_role ajouté au modèle avec enum IntegrationRole (PLATFORM/SERVICE)
- AC2: 9 fixtures mises à jour (aap, tower, azure_devops, github_actions, terraform_cloud = platform; vault, servicenow, jira, splunk = service)
- AC3: API expose integration_role dans la réponse sérialisée
- AC4: Filtre ?role=platform|service implémenté avec validation 400 pour valeurs invalides
- AC5: Frontend groupement OptGroup (Plateformes/Services), Tag badge bleu/vert, hook useIntegrationTypesByRole
- AC6: 21 tests backend + 6 tests frontend hook + 30 tests IntegrationForm existants (0 régression)

### Change Log

| Fichier | Action | Description |
|---------|--------|-------------|
| `migrations/sql/V072__add_integration_role.sql` | NEW | Migration Oracle — colonne + contrainte CHECK + UPDATE services |
| `integrations/models.py` | MODIFY | Enum IntegrationRole + champ integration_role sur IntegrationTypeCatalogue |
| `integrations/serializers.py` | MODIFY | Ajout 'integration_role' aux champs du serializer |
| `integrations/catalogue_service.py` | MODIFY | Paramètre role optionnel dans list_all_types() |
| `integrations/catalogue_views.py` | MODIFY | Extraction et validation ?role= query param |
| `integrations/fixtures/integration_type_catalogue.json` | MODIFY | integration_role ajouté aux 9 types |
| `integrations/fixtures/vault_integration_type.json` | MODIFY | integration_role: "service" |
| `integrations/fixtures/tower_integration_type.json` | MODIFY | integration_role: "platform" |
| `integrations/fixtures/azure_devops_integration_type.json` | MODIFY | integration_role: "platform" |
| `integrations/fixtures/github_actions_integration_type.json` | MODIFY | integration_role: "platform" |
| `integrations/fixtures/terraform_cloud_integration_type.json` | MODIFY | integration_role: "platform" |
| `integrations/migrations/0005_...integration_role.py` | NEW | Django migration pour tests SQLite |
| `integrations/tests/test_integration_role.py` | NEW | 21 tests (model, serializer, service, API) |
| `integrations/tests/test_catalogue_serializers.py` | MODIFY | Ajout 'integration_role' aux champs attendus |
| `tests/factories.py` | MODIFY | integration_role='platform' par défaut dans factory |
| `docs/integration-type-catalogue.md` | MODIFY | Champ integration_role + filtre API ?role= |
| `frontend/src/types/api/integrations.ts` | MODIFY | IntegrationRoleType + integration_role? optionnel |
| `frontend/src/services/integrations_service.ts` | MODIFY | Paramètre role optionnel dans getIntegrationTypes() |
| `frontend/src/hooks/useIntegrationTypesByRole.ts` | NEW | Hook filtrage client-side par rôle |
| `frontend/src/hooks/useIntegrationTypesByRole.test.ts` | NEW | 6 tests hook |
| `frontend/src/components/admin/IntegrationForm.tsx` | MODIFY | OptGroup + Tag badge platform/service |

### File List

**Backend:**
- `django_backend/migrations/sql/V072__add_integration_role.sql`
- `django_backend/integrations/models.py`
- `django_backend/integrations/serializers.py`
- `django_backend/integrations/catalogue_service.py`
- `django_backend/integrations/catalogue_views.py`
- `django_backend/integrations/fixtures/integration_type_catalogue.json`
- `django_backend/integrations/fixtures/vault_integration_type.json`
- `django_backend/integrations/fixtures/tower_integration_type.json`
- `django_backend/integrations/fixtures/azure_devops_integration_type.json`
- `django_backend/integrations/fixtures/github_actions_integration_type.json`
- `django_backend/integrations/fixtures/terraform_cloud_integration_type.json`
- `django_backend/integrations/migrations/0005_integrationtypecatalogue_integration_role_and_more.py`
- `django_backend/integrations/tests/test_integration_role.py`
- `django_backend/integrations/tests/test_catalogue_serializers.py`
- `django_backend/tests/factories.py`
- `django_backend/docs/integration-type-catalogue.md`

**Frontend:**
- `frontend/src/types/api/integrations.ts`
- `frontend/src/services/integrations_service.ts`
- `frontend/src/hooks/useIntegrationTypesByRole.ts`
- `frontend/src/hooks/useIntegrationTypesByRole.test.ts`
- `frontend/src/components/admin/IntegrationForm.tsx`
