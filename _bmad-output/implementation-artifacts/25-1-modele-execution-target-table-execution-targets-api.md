# Story 25.1 : Modèle ExecutionTarget (table EXECUTION_TARGETS et API)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a moteur d'exécution,
I want une liaison explicite entre une exécution et ses cibles (serveurs, bases),
So que les requêtes par cible, la validation RBAC, les mutex et les condition gates s'appuient sur un modèle relationnel fiable.

## Acceptance Criteria

**Given** une exécution est créée avec des cibles choisies par l'utilisateur
**When** le backend enregistre l'exécution
**Then** une entrée est créée dans la table EXECUTION_TARGETS pour chaque cible (execution_id, target_type, target_id, target_name, target_metadata)
**And** le couple (execution, target_type, target_id) est unique
**And** l'API d'exécution accepte et persiste les targets (target_type : SERVER, DATABASE, PDB, SCHEMA ; target_id opaque vers l'inventaire ; target_name en snapshot pour affichage)

**Given** une exécution existante
**When** on consulte ses cibles
**Then** l'API retourne la liste des ExecutionTarget avec target_type, target_id, target_name et métadonnées optionnelles

**And** une migration Flyway/SQL crée la table EXECUTION_TARGETS avec les contraintes et index appropriés
**And** le modèle Django ExecutionTarget est exposé via le repository et les serializers existants

## Tasks / Subtasks

- [x] Task 1: Créer le modèle Django ExecutionTarget (AC: 1, 2, 3, 4)
  - [x] 1.1: Créer executions/models.py::ExecutionTarget avec champs (execution, target_type, target_id, target_name, target_metadata, created_at)
  - [x] 1.2: Ajouter Meta: db_table='EXECUTION_TARGETS', unique_together=('execution', 'target_type', 'target_id')
  - [x] 1.3: Implémenter méthodes helper get_target_metadata()/set_target_metadata() pour JSON (pattern existant ProfileTargetPermission)
  - [x] 1.4: Ajouter related_name='targets' sur FK execution pour accès Execution.targets.all()

- [x] Task 2: Créer la migration SQL V066 (AC: 5)
  - [x] 2.1: Créer database/migrations/V066__create_execution_targets.sql
  - [x] 2.2: Table EXECUTION_TARGETS avec colonnes: ID NUMBER(19) PRIMARY KEY, EXECUTION_ID NUMBER(19) NOT NULL, TARGET_TYPE VARCHAR2(50), TARGET_ID VARCHAR2(200), TARGET_NAME VARCHAR2(255), TARGET_METADATA CLOB, CREATED_AT TIMESTAMP DEFAULT SYSTIMESTAMP
  - [x] 2.3: Ajouter contrainte FK: FOREIGN KEY (EXECUTION_ID) REFERENCES EXECUTIONS(ID) ON DELETE CASCADE
  - [x] 2.4: Ajouter contrainte unique: UNIQUE (EXECUTION_ID, TARGET_TYPE, TARGET_ID)
  - [x] 2.5: Créer index composite: CREATE INDEX IDX_EXEC_TARGETS_EXEC ON EXECUTION_TARGETS(EXECUTION_ID)
  - [x] 2.6: Créer index pour recherche inverse: CREATE INDEX IDX_EXEC_TARGETS_TARGET ON EXECUTION_TARGETS(TARGET_TYPE, TARGET_ID)

- [x] Task 3: Modifier le flow de création d'exécution pour peupler ExecutionTarget (AC: 1, 2)
  - [x] 3.1: Dans executions/views.py, après validation RBAC, passer validated_targets à ExecutionService
  - [x] 3.2: Pour chaque target, résoudre target_type depuis inventory metadata
  - [x] 3.3: Créer ExecutionTarget pour chaque cible avec target_type=inféré, target_id=name, target_name=name, target_metadata=JSON snapshot (env, technology)
  - [x] 3.4: Transaction atomique dans _create_execution_atomic: si création ExecutionTarget échoue, rollback Execution
  - [x] 3.5: Maintenir backward compatibility: target_names continue d'être stocké dans parameters._targets

- [x] Task 4: Ajouter serializer et exposer targets dans l'API (AC: 3, 4)
  - [x] 4.1: Créer executions/serializers.py::ExecutionTargetSerializer avec champs (target_type, target_id, target_name, target_metadata)
  - [x] 4.2: Ajouter champ targets dans ExecutionSerializer via to_representation
  - [x] 4.3: Ajouter prefetch_related('targets') dans les vues list et detail
  - [x] 4.4: Testé via GET /api/v1/executions/{id}/ que targets[] est retourné

- [x] Task 5: Ajouter tests unitaires et d'intégration (AC: tous)
  - [x] 5.1: Test modèle: créer ExecutionTarget, vérifier contrainte unique (execution, target_type, target_id)
  - [x] 5.2: Test API POST: créer exécution avec target_names, vérifier ExecutionTarget créés
  - [x] 5.3: Test API GET: vérifier que targets[] est retourné avec metadata
  - [x] 5.4: Test RBAC: vérifier que seules les cibles autorisées créent ExecutionTarget (pas de bypass)
  - [x] 5.5: Test cascade: supprimer Execution, vérifier ExecutionTarget supprimés automatiquement

- [x] Task 6: Documentation et migration de données existantes (optionnel) (AC: 5)
  - [x] 6.1: Documenté EXECUTION_TARGETS dans docs/backend/database-schema.md
  - [ ] 6.2: (Optionnel — non implémenté) Script de migration rétroactive
  - [ ] 6.3: (Optionnel — non implémenté) docs/api/executions.md n'existe pas, schema OpenAPI auto-généré par drf-spectacular

## Dev Notes

### Architecture Context - Pattern Convergence DBOps

Cette story implémente la **fondation** de la convergence DBOps → IDP Portal (Réf: `_bmad-output/implementation-artifacts/convergence-dbops-idp-portal.md`).

**Pourquoi cette story en premier ?**
- Les stories suivantes (Condition Gates, Mutex, Deny RBAC) dépendent TOUTES de ce modèle relationnel
- Les mutex inter-actions nécessitent de savoir quelles cibles sont impactées par une exécution en cours
- Les condition gates `maintenance_window` nécessitent de connaître les serveurs cibles pour interroger l'inventaire
- La validation RBAC devient plus performante avec une relation directe au lieu de parser du JSON

**Ordre d'implémentation de l'Epic 25 :**
```
1. ExecutionTarget (CETTE STORY) ← Fondation
2. Condition Gates + statut WAITING
3. Overrides par environnement
4. Mutex inter-actions (dépend de #1)
5. Deny explicite RBAC
```

### Existing Models and Patterns to Follow

**1. Current Execution Model** (`executions/models.py`):
```python
class Execution(models.Model):
    # Champs existants pertinents
    action = models.ForeignKey(Action, on_delete=models.PROTECT)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    environment = models.CharField(max_length=50)
    parameters = models.TextField()  # CLOB contenant JSON
    status = models.CharField(max_length=50, choices=ExecutionStatus.choices)

    # Helper methods à imiter
    def get_parameters(self) -> dict:
        return json.loads(self.parameters) if self.parameters else {}

    def set_parameters(self, params: dict):
        self.parameters = json.dumps(params, ensure_ascii=False)
```

**2. Pattern JSON Helper Methods** (à réutiliser pour target_metadata):
- Tous les modèles avec CLOB JSON suivent ce pattern
- Exemples: `ProfileTargetPermission.get_target_names()`, `Action.get_parameters_schema()`
- TOUJOURS utiliser `ensure_ascii=False` pour supporter les caractères Unicode

**3. Migration Pattern** (depuis V060__add_filter_by_attribute_to_profile_target_permissions.sql):
```sql
ALTER TABLE PROFILE_TARGET_PERMISSIONS
ADD FILTER_BY_ATTRIBUTE_JSON CLOB;

COMMENT ON COLUMN PROFILE_TARGET_PERMISSIONS.FILTER_BY_ATTRIBUTE_JSON IS
'JSON dict of attribute filters...';
```

**4. Related_name Convention**:
- Execution → ExecutionStep: `related_name='steps'` (existant)
- Execution → ExecutionTarget: `related_name='targets'` (à créer)

### Inventory Service Integration

**InventoryService Location:** `inventory/services.py`

**Méthode clé à utiliser:**
```python
def list_targets_for_user(
    user_id: int,
    environment: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> list[Target]:
    """Returns RBAC-filtered targets accessible by user."""
```

**Target Dataclass** (`inventory/models.py`):
```python
@dataclass
class Target:
    name: str
    environment: str  # dev, staging, prod
    target_type: str  # server, database, group, cluster, other
    metadata: dict[str, Any] | None  # { "engine_type": "oracle", "zone": "prod" }
```

**Story 23 Context (Multi-Table Inventory):**
- Depuis les stories 23.1-23.3, l'inventaire supporte 3 types d'entités: SERVER, DATABASE, INSTANCE
- InventoryMapper permet mapping config-driven (business concepts → Oracle columns)
- Cette story doit supporter target_type = SERVER | DATABASE | INSTANCE | SCHEMA (anticipation futurs besoins)

### Target Type Inference Logic

**Depuis Story 13.4** (`executions/utils.py`):
- Les actions avec `requires_target=True` EXIGENT target_names dans le payload
- L'environnement est dérivé du target (pas passé séparément)
- Tous les targets d'une exécution doivent être dans le MÊME environnement

**À implémenter dans Task 3:**
```python
# Pseudo-code pour inférence target_type
def infer_target_type(target: Target) -> str:
    """Infer target type from inventory metadata."""
    # Logic à adapter selon metadata retourné par InventoryService
    if target.target_type == "server":
        return "SERVER"
    elif target.target_type == "database":
        return "DATABASE"
    elif target.target_type == "cluster":
        return "CLUSTER"
    else:
        return "OTHER"
```

### RBAC Enforcement - Existing Flow

**Current Validation** (`executions/views.py::ExecutionViewSet.create()`):
1. Extract `target_names` from POST payload
2. Call `InventoryService.list_targets_for_user(user_id, environment)`
3. Validate que tous les target_names requis sont dans la liste autorisée
4. Si un target n'est pas autorisé → 403 Forbidden

**Avec ExecutionTarget:**
- MÊME validation RBAC (ne rien changer ici)
- APRÈS validation réussie: créer ExecutionTarget pour chaque cible autorisée
- Le modèle ExecutionTarget devient la "preuve" que RBAC a été validé au moment de la soumission

### Database Schema Context

**Existing Tables to Reference:**
- `EXECUTIONS` (V023) - Table parente
- `EXECUTION_STEPS` (V023) - Pattern similaire (FK vers Execution avec ON DELETE CASCADE)
- `PROFILE_TARGET_PERMISSIONS` (V002) - Pattern JSON CLOB avec helpers

**Oracle Constraints:**
- VARCHAR2 max 4000 bytes (target_id=200 safe, target_name=255 safe)
- CLOB pour JSON (target_metadata)
- INDEX composites pour performance (execution_id + target filtering)

**Index Strategy:**
```sql
-- Forward lookup: "Quelles cibles pour cette exécution ?"
CREATE INDEX IDX_EXEC_TARGETS_EXEC ON EXECUTION_TARGETS(EXECUTION_ID);

-- Reverse lookup: "Quelles exécutions sur ce serveur ?"
CREATE INDEX IDX_EXEC_TARGETS_TARGET ON EXECUTION_TARGETS(TARGET_TYPE, TARGET_ID);
```

### Testing Strategy

**Existants à étendre:**
- `executions/tests/test_models.py` - Ajouter test ExecutionTarget model
- `executions/tests/test_views.py` - Modifier tests POST execution pour vérifier targets créés
- `executions/tests/test_rbac.py` - Vérifier que RBAC bloque création ExecutionTarget pour cibles non autorisées

**Nouveaux tests:**
```python
# Test contrainte unique
def test_execution_target_unique_constraint():
    """Cannot create duplicate (execution, target_type, target_id)."""

# Test cascade delete
def test_execution_target_cascade_delete():
    """Deleting execution deletes all associated targets."""

# Test API serialization
def test_execution_detail_includes_targets():
    """GET /api/v1/executions/{id}/ includes targets array."""
```

### Backward Compatibility Strategy

**Phase de transition:**
1. **Story 25.1 (cette story):** Créer ExecutionTarget ET garder target_names dans parameters JSON
2. **Stories futures:** Les condition gates et mutex liront depuis ExecutionTarget relation
3. **Cleanup éventuel:** Supprimer target_names de parameters JSON (après validation migration réussie)

**Pourquoi maintenir parameters JSON temporairement ?**
- Évite casse des clients existants qui parsent parameters
- Permet rollback facile si bug détecté
- Tests existants continuent de passer

### Error Handling

**Cas à gérer:**
1. **Target non trouvé dans l'inventaire:** 400 Bad Request (existant RBAC)
2. **Échec création ExecutionTarget:** Rollback transaction complète (inclure Execution)
3. **Violation contrainte unique:** 500 Internal Error (ne devrait jamais arriver - bug logic)

**Pattern à suivre** (depuis `executions/views.py`):
```python
try:
    with transaction.atomic():
        execution = Execution.objects.create(...)
        # Créer ExecutionTarget ici
        for target in validated_targets:
            ExecutionTarget.objects.create(...)
except IntegrityError as e:
    logger.error(f"Failed to create execution targets: {e}", extra={...})
    raise
```

### Performance Considerations

**Index critiques:**
- `IDX_EXEC_TARGETS_EXEC` - Utilisé par `Execution.targets.all()` (lecture fréquente)
- `IDX_EXEC_TARGETS_TARGET` - Utilisé par mutex validation et condition gates (lookup inverse)

**Volume estimé:**
- PRD: 10 000+ exécutions/an
- Si moyenne 2 targets/exécution = 20 000 rows/an dans EXECUTION_TARGETS
- Pas de problème de volume à court terme

### Security Audit Notes

**SOC1 Compliance:**
- ExecutionTarget est un **audit trail secondaire** : prouve quelles cibles ont été visées
- Immutable après création (pas de UPDATE, seulement INSERT via création Execution)
- Suppression seulement via CASCADE quand Execution parent supprimée (rare)

**RBAC Enforcement:**
- CRITIQUE: La création d'ExecutionTarget DOIT suivre validation RBAC
- Test de sécurité requis: vérifier qu'un attaquant ne peut pas bypasser RBAC en manipulant payload
- Pattern existant `executions/tests/test_security.py` à étendre

### References

**Architecture:**
- [Source: _bmad-output/implementation-artifacts/convergence-dbops-idp-portal.md#4-modele-de-cible-generique-target-first]
- [Source: _bmad-output/planning-artifacts/architecture.md#data-architecture]

**Code Patterns:**
- Modèle JSON CLOB: `profiles/models.py::ProfileTargetPermission`
- Migration SQL: `database/migrations/V060__add_filter_by_attribute_to_profile_target_permissions.sql`
- Transaction atomique: `executions/views.py::ExecutionViewSet.create()`

**Related Stories:**
- Story 13.4: Refactoring action unique, validation backend (target_names REQUIRED)
- Story 23.1-23.3: Inventaire multi-tables (SERVER, DATABASE, INSTANCE)
- Story 25.2-25.6: Stories suivantes dépendant de ExecutionTarget

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

N/A

### Completion Notes List

- Story créée avec analyse exhaustive du contexte existant (Execution models, Inventory service, RBAC, migrations)
- Modèle ExecutionTarget aligné sur architecture DBOps convergence
- Backward compatibility maintenue (parameters JSON garde target_names temporairement)
- Pattern JSON helpers réutilisé (get/set_target_metadata) avec ensure_ascii=False
- Indexes optimisés pour forward lookup (execution→targets) et reverse lookup (target→executions)
- RBAC enforcement: ExecutionTarget créés APRÈS validation RBAC dans transaction atomique
- Migration SQL V066 avec contraintes FK, unique, et 2 index
- Fondation établie pour stories 25.2-25.6 (Condition Gates, Mutex, Deny RBAC)
- 19 tests créés: modèle, contraintes, cascade, API POST/GET, RBAC, serializer — tous passent
- Aucune régression introduite (40 tests core passent, 67 échecs pré-existants)

### Implementation Notes

- TargetType enum: SERVER, DATABASE, INSTANCE, SCHEMA, CLUSTER, OTHER
- target_type est inféré depuis inventory metadata (.target_type.upper()), fallback à OTHER
- metadata_snapshot inclut environment, engine_type, zone, technology si disponibles
- validated_targets transmis de views.py → services.py._create_execution_atomic()
- prefetch_related('targets') ajouté aux vues list et detail pour éviter N+1
- ExecutionTargetSerializer ajouté dans to_representation d'ExecutionSerializer

### File List

Files created:
- `idp-portal/database/migrations/V066__create_execution_targets.sql`
- `idp-portal/django_backend/executions/tests/test_execution_targets.py`
- `idp-portal/django_backend/executions/migrations/0005_add_execution_target.py`

Files modified:
- `idp-portal/django_backend/executions/models.py` (added TargetType enum, ExecutionTarget model)
- `idp-portal/django_backend/executions/serializers.py` (added ExecutionTargetSerializer, targets in ExecutionSerializer)
- `idp-portal/django_backend/executions/services.py` (added validated_targets param, ExecutionTarget creation in atomic block)
- `idp-portal/django_backend/executions/views.py` (pass validated_targets, prefetch_related('targets'))
- `idp-portal/docs/backend/database-schema.md` (documented EXECUTION_TARGETS table)

### Change Log

- 2026-02-10: Implémentation complète Story 25.1 — Modèle ExecutionTarget, migration V066, serializer, flow de création, 19 tests (AC1-AC5 validés)
