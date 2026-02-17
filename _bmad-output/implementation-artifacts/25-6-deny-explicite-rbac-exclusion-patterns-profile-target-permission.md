# Story 25.6 : Deny explicite RBAC (exclusion_patterns sur ProfileTargetPermission)

Status: done

## Story

As a DBOPS,  
I want pouvoir exclure explicitement des cibles des permissions d'un profil (ex. tout sauf PROD-CRITICAL-*),  
so that l'accès soit "allow then exclude" sans avoir à lister toutes les cibles autorisées.

## Acceptance Criteria

### AC1: Champ `exclusion_patterns_json` ajouté au modèle

**Given** un profil avec des permissions sur les targets (liste ou pattern)  
**When** le profil possède un nouveau champ `exclusion_patterns_json` (JSON array de patterns, ex. `["PROD-CRITICAL-*", "DR-*"]`)  
**Then** la résolution RBAC des cibles autorisées pour l'utilisateur applique d'abord les règles d'inclusion (`LIST`, `PATTERN`, `ALL`), puis retire toute cible dont le nom (ou identifiant) matche au moins un pattern d'exclusion  
**And** une cible qui matche un pattern d'exclusion n'est jamais retournée comme autorisée, même si elle matche un pattern d'inclusion

### AC2: Interface Admin pour saisir les patterns d'exclusion

**Given** l'interface admin des profils / permissions targets  
**When** on édite les permissions cibles d'un profil  
**Then** un champ (liste ou texte) permet de saisir les patterns d'exclusion (ex. un par ligne ou tags)  
**And** la validation backend accepte un tableau de chaînes (patterns) et le persiste dans `exclusion_patterns_json` (ou nom de colonne équivalent)

### AC3: Migration DB ajoute le champ

**And** une migration ajoute le champ `exclusion_patterns_json` (TextField/JSON) à la table `PROFILE_TARGET_PERMISSIONS` (ou équivalent)

### AC4: Logique de résolution RBAC étendue

**And** la logique existante `list_targets_for_user` (ou équivalent) est étendue pour appliquer l'exclusion après l'inclusion ; les appels API qui renvoient les cibles autorisées reflètent ce comportement

### AC5: Documentation sémantique "allow first, then exclude"

**And** la documentation décrit la sémantique "allow first, then exclude" et les exemples de patterns

## Tasks / Subtasks

- [x] **Task 1: Migration DB + modèle Django (AC: 1, 3)**
  - [x] 1.1 Ajouter une migration Flyway `idp-portal/database/migrations/V071__add_exclusion_patterns_to_profile_target_permissions.sql` (numéro à confirmer) qui ajoute la colonne `EXCLUSION_PATTERNS_JSON` (CLOB ou équivalent Oracle) à `PROFILE_TARGET_PERMISSIONS`
    - Colonne: `EXCLUSION_PATTERNS_JSON CLOB`
    - Valeur par défaut: `NULL` (pas de restriction)
    - Contrainte: aucune contrainte spécifique (validation applicative)
  - [x] 1.2 Ajouter le champ au modèle Django `ProfileTargetPermission` dans `idp-portal/django_backend/profiles/models.py`:
    - `exclusion_patterns_json = models.TextField(null=True, blank=True, db_column='EXCLUSION_PATTERNS_JSON', help_text='JSON array filtering out targets matching any pattern. Format: ["PROD-CRITICAL-*", "DR-*"]')`
    - Méthodes helpers: `get_exclusion_patterns()` et `set_exclusion_patterns(value)` (pattern existant sur le modèle)
  - [x] 1.3 Ajouter la migration Django correspondante dans `profiles/migrations/` (pour tests)

- [x] **Task 2: Service de résolution RBAC étendu (AC: 1, 4)**
  - [x] 2.1 Identifier et étendre la méthode de résolution des cibles autorisées:
    - Emplacement actuel: `idp-portal/django_backend/inventory/services.py` → `InventoryService.list_targets_for_user(...)` (ou équivalent dans `profiles/services.py`)
    - Cette méthode applique déjà les règles d'inclusion (LIST, PATTERN, ALL) et le filtre `filter_by_attribute` (Story 23.4)
  - [x] 2.2 Ajouter l'étape d'exclusion **après** l'inclusion:
    - Pour chaque profil de l'utilisateur, charger `exclusion_patterns` via `ProfileTargetPermission.get_exclusion_patterns()`
    - Accumuler tous les patterns d'exclusion de tous les profils (union)
    - Filtrer la liste des cibles autorisées: retirer toute cible dont `target_name` matche au moins un pattern d'exclusion
    - Matching: utiliser la fonction existante de pattern matching (ex. `fnmatch`, `re.match`, ou équivalent utilisé pour `target_patterns`)
  - [x] 2.3 Ordre d'application des règles (important pour éviter les bugs):
    - **Étape 1**: Résolution d'inclusion (LIST, PATTERN, ALL)
    - **Étape 2**: Filtrage par attributs (`filter_by_attribute` si présent)
    - **Étape 3**: **Exclusion** (patterns d'exclusion)
    - Résultat final: ensemble des cibles autorisées après toutes les étapes
  - [x] 2.4 Cas limites à gérer:
    - Profil sans exclusion: `exclusion_patterns_json = NULL` ou `[]` → aucun impact
    - Profil avec exclusion mais aucune inclusion: exclusion n'a pas d'effet (pas de cibles de base)
    - Plusieurs profils avec exclusions différentes: union des exclusions (le plus restrictif gagne)
    - Pattern d'exclusion vide ou invalide: ignorer silencieusement avec log warning

- [x] **Task 3: API Profils - sérializers et validation (AC: 2)**
  - [x] 3.1 Étendre `ProfileTargetPermissionSerializer` dans `idp-portal/django_backend/profiles/serializers.py`:
    - Ajouter un champ `exclusion_patterns: list[str]` au serializer
    - Validation: chaque pattern doit être une chaîne non-vide (pas de validation stricte du format glob, car flexible)
    - Mapping: `exclusion_patterns` (serializer) ↔ `exclusion_patterns_json` (modèle) via helpers `get_` / `set_`
  - [x] 3.2 Tester que l'API `GET/POST/PATCH /api/v1/admin/profiles/{id}/permissions/targets/` expose et persiste correctement le nouveau champ
  - [x] 3.3 Ajouter des tests de validation:
    - Patterns valides: `["PROD-CRITICAL-*", "DR-*"]`, `["SERVER-123"]`
    - Patterns invalides: `[None]`, `[""]`, `123` (type incorrect) → erreur de validation

- [x] **Task 4: UI Admin - formulaire profil (AC: 2)**
  - [x] 4.1 Identifier le composant d'édition des permissions target:
    - Emplacement probable: `idp-portal/frontend/src/components/admin/ProfileForm.tsx` ou `ProfileWizard.tsx`
    - Section: Permissions Targets (déjà présente avec `permission_type`, `target_names`, `target_patterns`, `filter_by_attribute`)
  - [x] 4.2 Ajouter un champ UI pour `exclusion_patterns`:
    - Composant recommandé: `Select` Ant Design en mode `tags` (permet de saisir plusieurs patterns)
    - Label: "Patterns d'exclusion" (FR)
    - Placeholder: "ex: PROD-CRITICAL-*, DR-*"
    - Help text: "Cibles à exclure même si elles matchent les règles d'inclusion (sémantique: allow first, then exclude)"
  - [x] 4.3 Intégration dans le formulaire:
    - Valeur par défaut: `[]` (pas d'exclusion)
    - Validation frontend: chaque tag doit être non-vide
    - Sauvegarde: envoyer `exclusion_patterns: string[]` au backend via l'API profils
  - [x] 4.4 Affichage en lecture seule (liste profils):
    - Si un profil a des exclusions, les afficher dans la vue liste ou le drawer de détail (optionnel pour cette story, mais recommandé)

- [x] **Task 5: Tests backend (AC: 1, 4)**
  - [x] 5.1 Tests unitaires `profiles/tests/test_models.py`:
    - Helpers `get_exclusion_patterns()` / `set_exclusion_patterns()` fonctionnent correctement
    - JSON sérialisé/désérialisé sans perte
    - Cas limite: `None`, `[]`, patterns avec caractères spéciaux
  - [x] 5.2 Tests d'intégration `inventory/tests/test_rbac_exclusion.py` (nouveau fichier):
    - **Test 1**: Profil avec inclusion `ALL` + exclusion `["PROD-CRITICAL-*"]` → cibles PROD-CRITICAL-* exclues
    - **Test 2**: Profil avec inclusion `PATTERN: ["PROD-*"]` + exclusion `["PROD-CRITICAL-*"]` → PROD-* inclus sauf PROD-CRITICAL-*
    - **Test 3**: Profil avec inclusion `LIST: ["SERVER-1", "SERVER-2"]` + exclusion `["SERVER-1"]` → seul SERVER-2 autorisé
    - **Test 4**: Plusieurs profils avec exclusions différentes → union des exclusions (le plus restrictif)
    - **Test 5**: Exclusion sans inclusion → aucune cible (pas d'erreur)
  - [x] 5.3 Tests API `profiles/tests/test_api_target_permissions.py`:
    - Création/modification d'un profil avec `exclusion_patterns` via API
    - GET retourne les exclusions
    - Validation: patterns invalides refusés

- [x] **Task 6: Tests frontend (AC: 2)**
  - [x] 6.1 Tests `ProfileForm.test.tsx`:
    - Champ exclusion_patterns s'affiche correctement
    - Saisie de tags fonctionne
    - Validation: tags vides refusés
    - Sauvegarde envoie `exclusion_patterns` au backend
  - [x] 6.2 Tests d'intégration (optionnel):
    - Mock API retourne un profil avec exclusions
    - Formulaire affiche les exclusions existantes
    - Modification des exclusions persiste côté backend

- [x] **Task 7: Documentation (AC: 5)**
  - [x] 7.1 Documenter la sémantique "allow first, then exclude" dans:
    - `idp-portal/docs/backend/rbac.md` (ou équivalent)
    - Section: "Exclusion explicite de cibles (Deny patterns)"
    - Ordre d'application: Inclusion → Attributs → **Exclusion**
    - Exemples concrets: "Tous les serveurs Oracle sauf PROD-CRITICAL-*"
  - [x] 7.2 Ajouter un exemple de configuration dans la doc:
    ```json
    {
      "permission_type": "PATTERN",
      "target_patterns": ["PROD-*"],
      "exclusion_patterns": ["PROD-CRITICAL-*", "PROD-DR-*"],
      "filter_by_attribute": {"engine_type": ["oracle"]}
    }
    ```
    Résultat: "Tous les serveurs Oracle en PROD-* sauf PROD-CRITICAL-* et PROD-DR-*"
  - [x] 7.3 Mettre à jour le README ou la doc admin UI avec des captures d'écran (optionnel)

## Dev Notes

### Contexte Epic 25 — Convergence DBOps → IDP Portal

Cette story implémente le **deny explicite RBAC** décrit dans:
- `_bmad-output/implementation-artifacts/convergence-dbops-idp-portal.md` (section "Deny explicite RBAC (exclusion_patterns)")  
- `_bmad-output/planning-artifacts/epics.md` (Epic 25, Story 25.6)

**Dépendances déjà en place (stories précédentes) :**
- Story 23.4 ✅: `filter_by_attribute_json` sur `ProfileTargetPermission` — filtrage par attributs d'inventaire
- Story 25.1 ✅: `ExecutionTarget` (`EXECUTION_TARGETS`) — modèle de cible explicite
- Story 25.5 ✅: Mutex inter-actions — validation à la soumission (patterns de développement réutilisables)

### Intelligence story précédente (25.5) à réutiliser

- **Pattern de migration DB**: Story 25.5 a créé `V070__create_action_mutex.sql` pour ajouter une nouvelle table. Pour 25.6, on ajoute simplement une colonne à une table existante (plus simple).
- **Pattern de modèle Django**: Story 25.5 a utilisé des helpers `get_`/`set_` pour sérialiser/désérialiser le JSON. Même pattern ici pour `exclusion_patterns`.
- **Pattern de service**: Story 25.5 a implémenté `validate_action_mutex()` dans `executions/utils.py`. Pour 25.6, on étend `InventoryService.list_targets_for_user()` (existant).
- **Pattern de tests**: Story 25.5 a créé 23 tests (11 admin API + 12 validation). Pour 25.6, viser ~15-20 tests (5-10 backend RBAC + 5-10 API + 3-5 frontend).

### Où brancher (important)

- **Point d'entrée RBAC**: `idp-portal/django_backend/inventory/services.py` → `InventoryService.list_targets_for_user(...)`
  - C'est la méthode centrale qui résout les cibles autorisées pour un utilisateur donné
  - Elle applique déjà les règles d'inclusion (`LIST`, `PATTERN`, `ALL`) et le filtre `filter_by_attribute` (Story 23.4)
  - On ajoute l'étape d'exclusion **à la fin** de cette méthode
- **Alternative**: Si la logique RBAC est dans `profiles/services.py`, brancher là. Vérifier le code existant pour confirmer.
- **Important**: Ne pas créer une nouvelle méthode pour l'exclusion — étendre la méthode existante pour maintenir une seule source de vérité.

### Developer Guardrails (anti-bugs / anti-regressions)

- **Ordre d'application strict**: Inclusion → Attributs → **Exclusion**. Ne jamais inverser cet ordre, sinon un pattern d'inclusion pourrait "réactiver" une cible exclue.
- **Union des exclusions**: Si l'utilisateur a plusieurs profils avec des exclusions différentes, l'union des exclusions s'applique (le plus restrictif). Ne pas faire l'intersection.
- **Patterns vides ou invalides**: Ignorer silencieusement avec un log warning. Ne pas faire échouer toute la résolution RBAC à cause d'un pattern mal formé.
- **Tests de régression**: Vérifier que les tests existants de `list_targets_for_user` passent toujours (pas de régression sur le comportement d'inclusion).
- **Performance**: Si l'inventaire contient 10 000+ cibles, le filtrage d'exclusion doit être efficace. Utiliser des sets Python pour le matching (`target_name in excluded_set`) plutôt que des boucles imbriquées.

### Fonction de matching de patterns

- **Existing pattern matching**: Vérifier comment `target_patterns` est actuellement matché dans `InventoryService`. Réutiliser la même fonction.
- **Options courantes**:
  - `fnmatch.fnmatch(target_name, pattern)` — glob-style matching (`*`, `?`, `[abc]`)
  - `re.match(pattern, target_name)` — regex (plus puissant mais plus complexe)
- **Recommandation**: Utiliser `fnmatch` pour la simplicité et la cohérence avec `target_patterns`.
- **Cas sensibilité**: Matching case-insensitive recommandé (les noms de serveurs Oracle sont souvent en majuscules, mais les patterns peuvent être saisis en minuscules).

### Sémantique "allow first, then exclude"

- **Principe**: Les exclusions ne créent pas d'accès. Elles **retirent** des accès déjà accordés par les règles d'inclusion.
- **Exemple 1**: Profil avec `ALL` + exclusion `["PROD-CRITICAL-*"]`
  - Inclusion: toutes les cibles
  - Exclusion: retire PROD-CRITICAL-*
  - Résultat: toutes les cibles sauf PROD-CRITICAL-*
- **Exemple 2**: Profil avec `LIST: ["SERVER-1"]` + exclusion `["SERVER-2"]`
  - Inclusion: SERVER-1 uniquement
  - Exclusion: retire SERVER-2 (mais SERVER-2 n'était pas inclus)
  - Résultat: SERVER-1 (pas de changement, car l'exclusion ne s'applique qu'aux cibles déjà incluses)
- **Exemple 3**: Profil avec `PATTERN: ["PROD-*"]` + exclusion `["PROD-CRITICAL-*", "PROD-DR-*"]`
  - Inclusion: PROD-APP-01, PROD-CRITICAL-DB-01, PROD-DR-02
  - Exclusion: retire PROD-CRITICAL-DB-01 et PROD-DR-02
  - Résultat: PROD-APP-01 uniquement

### Cas d'usage réels (motivations métier)

- **Cas 1**: Donner accès à tous les serveurs Oracle en prod, sauf les serveurs critiques (PROD-CRITICAL-*)
  - `permission_type: ALL` + `filter_by_attribute: {"engine_type": ["oracle"], "environment": ["prod"]}` + `exclusion_patterns: ["PROD-CRITICAL-*"]`
- **Cas 2**: Donner accès à tous les serveurs SQL, sauf les DR (disaster recovery)
  - `permission_type: ALL` + `filter_by_attribute: {"engine_type": ["sqlserver"]}` + `exclusion_patterns: ["*-DR-*"]`
- **Cas 3**: Donner accès à un pattern large, sauf quelques serveurs spécifiques
  - `permission_type: PATTERN` + `target_patterns: ["APP-*"]` + `exclusion_patterns: ["APP-PROD-01", "APP-PROD-02"]`

### Sécurité / audit / observabilité

- **Log d'exclusion**: Quand une cible est exclue, logger un événement structlog (niveau debug ou info) avec `target_name`, `exclusion_pattern`, `profile_id`, `user_id`.
- **Audit trail**: Pas besoin d'un audit trail spécifique pour chaque exclusion (trop verbeux). L'audit de modification du profil (via `AuditActionType.PROFILE_UPDATED`) suffit.
- **Observabilité**: En cas de problème ("pourquoi je n'ai pas accès à cette cible ?"), les logs structlog permettront de tracer l'exclusion.

### Git intelligence (patterns récents)

Commits récents (conventions à suivre):
- `feat(25-5): implement ActionMutex model and API...`
- `fix(25-5): code review fixes...`
- `feat(25-4): enrichir change_type_config par environnement`
- `feat(25-1): implement ExecutionTarget model and API...`

Le style courant est donc `feat(25-6): ...` / `fix(25-6): ...` avec mention des fixes de revue si nécessaire.

### Architecture (référence)

D'après `_bmad-output/planning-artifacts/architecture.md`:
- **Pattern de données**: SQL brut + Repository Pattern (pas d'ORM complexe)
- **Naming DB**: `UPPER_SNAKE_CASE` (tables/colonnes Oracle)
- **Naming Python**: `snake_case` (variables/fonctions), `PascalCase` (classes)
- **Naming Frontend**: `camelCase` (variables), `PascalCase` (composants)
- **JSON fields**: Colonnes `CLOB` en Oracle, sérialisées via `json.dumps()` / `json.loads()`

### Recommandations pour le dev agent

- **Commencer par la migration DB**: V071 (ajouter colonne) → migration Django → modèle Django (helpers)
- **Puis le service RBAC**: Étendre `list_targets_for_user()` avec l'étape d'exclusion
- **Puis l'API**: Serializers + validation
- **Puis les tests backend**: Vérifier que l'exclusion fonctionne correctement dans différents scénarios
- **Puis l'UI**: Formulaire admin avec champ exclusion_patterns
- **Puis les tests frontend**: Vérifier que le formulaire fonctionne
- **Enfin la doc**: Documenter la sémantique et les exemples

### Known Issues / Limitations (à documenter)

- **Performance**: Si un profil a 1000+ patterns d'exclusion, le matching peut être lent. Recommandation: limiter à ~100 patterns max (validation frontend + warning backend).
- **Ordre des patterns**: Les patterns d'exclusion sont évalués dans l'ordre où ils sont stockés (array JSON). Pas de priorité entre patterns.
- **Wildcard complexes**: `fnmatch` supporte `*`, `?`, `[abc]`, mais pas les regex complexes. Si besoin de regex, documenter et implémenter `re.match()` à la place.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (via Cursor)

### Completion Notes List

✅ **Task 1 (Migration DB + modèle):**
- Created Flyway migration V071__add_exclusion_patterns_to_profile_target_permissions.sql
- Added exclusion_patterns_json field to ProfileTargetPermission model with get_/set_ helpers
- Created Django migration 0003_add_exclusion_patterns.py

✅ **Task 2 (Service RBAC):**
- Extended InventoryService.list_targets_for_user() to collect exclusion_patterns from all profiles (union)
- Implemented _apply_exclusion_patterns() helper with case-insensitive fnmatch matching
- Applied exclusions after attribute filtering (Inclusion → Attributes → Exclusion order)
- Enhanced RBAC traceability logs with exclusion metrics

✅ **Task 3 (API & Serializers):**
- Extended ProfileTargetPermissionsSerializer with exclusion_patterns field
- Added validate_exclusion_patterns() with validation (non-empty strings)
- Updated ProfileService.set_target_permissions() to persist exclusion_patterns
- Updated to_representation() to return exclusion_patterns

✅ **Task 4 (UI Admin):**
- Added exclusion_patterns to ProfileFormValues interface
- Added UI field (Select mode="tags") with tooltip explaining "allow first, then exclude"
- Updated API types (ProfileTargetPermissionsUpdate/Response)
- Form loads/saves exclusion_patterns correctly

✅ **Task 5 (Tests backend):**
- Created test_exclusion_patterns_model.py: 13 unit tests for get_/set_ helpers
- Created test_rbac_exclusion.py: 7 integration tests for RBAC resolution logic
- Created test_api_exclusion_patterns.py: 10 API tests for GET/PUT endpoints

✅ **Task 6 (Tests frontend):**
- Created ProfileForm.exclusion.test.tsx: 9 tests for UI field behavior

✅ **Task 7 (Documentation):**
- Extended docs/backend/rbac.md with comprehensive section on exclusion patterns
- Documented "allow first, then exclude" semantics
- Added 3 concrete examples with expected results
- Documented multi-profile union behavior and edge cases

🔥 **Code Review Fixes Applied:**
- **HIGH-2 (Performance limit):** Added max 100 patterns validation in serializer + warning log at 50+ patterns
- **HIGH-3 (API behavior):** Documented null/omitted/[] behavior in PUT requests (rbac.md)
- **MEDIUM-1 (Frontend validation):** Added pattern validation in ProfileForm.tsx (max 100, glob syntax check, regex detection)
- **MEDIUM-2 (Traceability):** Added warning log for patterns that never match any target (potential typos)
- **MEDIUM-3 (Error handling):** Changed WARNING to ERROR for "not a list" corruption (consistency with filter_by_attribute)
- **LOW-2 (Documentation):** Clarified multi-profile union behavior with concrete example
- **Documentation:** Added performance limit section (max 100 patterns) with technical rationale

### File List

**Database Migrations:**
- idp-portal/database/migrations/V071__add_exclusion_patterns_to_profile_target_permissions.sql

**Backend - Models:**
- idp-portal/django_backend/profiles/models.py (modified: added exclusion_patterns_json field + helpers)
- idp-portal/django_backend/profiles/migrations/0003_add_exclusion_patterns.py

**Backend - Services:**
- idp-portal/django_backend/inventory/services.py (modified: extended list_targets_for_user, added _apply_exclusion_patterns)
- idp-portal/django_backend/profiles/services.py (modified: set_target_permissions persists exclusion_patterns)

**Backend - Serializers:**
- idp-portal/django_backend/profiles/serializers.py (modified: added exclusion_patterns field + validation + max 100 limit)

**Backend - Tests:**
- idp-portal/django_backend/profiles/tests/test_exclusion_patterns_model.py
- idp-portal/django_backend/inventory/tests/test_rbac_exclusion.py
- idp-portal/django_backend/profiles/tests/test_api_exclusion_patterns.py

**Frontend - Components:**
- idp-portal/frontend/src/components/admin/ProfileForm.tsx (modified: added exclusion_patterns UI field)

**Frontend - Types:**
- idp-portal/frontend/src/types/api/profiles.ts (modified: added exclusion_patterns to interfaces)

**Frontend - Tests:**
- idp-portal/frontend/src/components/admin/ProfileForm.exclusion.test.tsx

**Documentation:**
- idp-portal/docs/backend/rbac.md (modified: added section on exclusion patterns)

## References

### Epic & Planning

- **Epic 25**: Convergence DBOps → IDP Portal (epics.md lignes 4246-4378)
- **Story 25.6**: Deny explicite RBAC (epics.md lignes 4357-4378)
- **Convergence doc**: `_bmad-output/implementation-artifacts/convergence-dbops-idp-portal.md`

### Architecture & Modèle

- **Architecture**: `_bmad-output/planning-artifacts/architecture.md`
  - Data architecture (lignes 253-265): SQL brut + Repository Pattern
  - Naming patterns (lignes 436-484): Conventions UPPER_SNAKE_CASE (DB), snake_case (Python), camelCase (TS)
  - RBAC (lignes 309-319): Middleware FastAPI + RBAC service

### Modèles & Services existants

- **ProfileTargetPermission model**: `idp-portal/django_backend/profiles/models.py` (lignes 205-316)
  - Champs actuels: `permission_type`, `target_names_json`, `target_patterns_json`, `filter_by_attribute_json`
  - Pattern existant: helpers `get_`/`set_` pour JSON CLOB
- **InventoryService**: `idp-portal/django_backend/inventory/services.py`
  - Méthode clé: `list_targets_for_user(...)` (résolution RBAC)
- **ProfileService**: `idp-portal/django_backend/profiles/services.py`
  - CRUD profils + cumul permissions multi-profils

### Stories précédentes (dépendances)

- **Story 23.4**: `filter_by_attribute_json` sur ProfileTargetPermission (`_bmad-output/implementation-artifacts/23-4-backend-rbac-profils-filtres-par-attribut.md`)
- **Story 25.1**: ExecutionTarget model (`_bmad-output/implementation-artifacts/25-1-modele-execution-target-table-execution-targets-api.md`)
- **Story 25.5**: ActionMutex validation (`_bmad-output/implementation-artifacts/25-5-mutex-inter-actions-table-action-mutex-validation-soumission.md`)

### Tests & Patterns

- **Tests RBAC existants**:
  - `idp-portal/django_backend/profiles/tests/test_filter_by_attribute.py`
  - `idp-portal/django_backend/inventory/tests/test_rbac_filter_by_attribute.py`
- **Tests API profils**:
  - `idp-portal/django_backend/profiles/tests/test_api_filter_by_attribute.py`

### Frontend

- **ProfileForm**: `idp-portal/frontend/src/components/admin/ProfileForm.tsx`
- **ProfileWizard**: `idp-portal/frontend/src/components/admin/ProfileWizard.tsx`
- **Types API**: `idp-portal/frontend/src/types/api/profiles.ts`

### Documentation

- **RBAC**: `idp-portal/docs/backend/rbac.md`
- **Database schema**: `idp-portal/docs/backend/database-schema.md`
