# Story 29.3: Alignement REF_ENGINES ↔ engine_type inventaire

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **système**,
I want **un référentiel unique pour les moteurs de base de données (REF_ENGINES) utilisé à la fois par le catalogue d'actions et l'inventaire des cibles**,
So that **les filtres et les profils RBAC par engine_type soient cohérents et alignés**.

## Acceptance Criteria

**Given** REF_ENGINES contient les moteurs (Oracle, SQL Server, Azure SQL, DB2, CosmosDB, etc.)
**When** l'inventaire expose des cibles avec attribut engine_type
**Then** engine_type doit être aligné sur les codes REF_ENGINES (convention : minuscules/snake_case, ex. oracle, sql_server)
**And** la documentation du mapping inventaire (InventoryMapper) décrit comment mapper les colonnes sources vers les valeurs REF_ENGINES
**And** GET /api/v1/reference/engines retourne la liste des valeurs valides pour engine_type
**And** les profils (filter_by_attribute_json avec engine_type) et filtres API inventaire utilisent les mêmes valeurs

**And** des tests valident la cohérence des valeurs engine_type avec REF_ENGINES

## Tasks / Subtasks

- [x] Task 1: Documenter la relation actuelle REF_ENGINES ↔ engine_type (AC: documentation)
  - [x] 1.1: Analyser les valeurs actuelles dans REF_ENGINES (migration V049)
  - [x] 1.2: Analyser comment engine_type est utilisé dans l'inventaire (InventoryMapper)
  - [x] 1.3: Identifier les différences de format (casse, espaces, underscores)
  - [x] 1.4: Documenter le mapping recommandé dans glossary.md ou rapport technique

- [x] Task 2: Créer documentation du mapping engine_type (AC: documentation InventoryMapper)
  - [x] 2.1: Créer ou enrichir docs/inventory-mapping-guide.md
  - [x] 2.2: Documenter convention de normalisation (minuscules, underscores pour espaces)
  - [x] 2.3: Fournir tableau de mapping REF_ENGINES.CODE → engine_type recommandé
  - [x] 2.4: Expliquer que engine_type provient de sources externes et doit être normalisé
  - [x] 2.5: Ajouter exemples de configuration InventoryMapper avec colonne engine_type

- [x] Task 3: Valider que GET /api/v1/reference/engines retourne bien les valeurs (AC: API)
  - [x] 3.1: Vérifier endpoint existant /api/v1/reference/engines
  - [x] 3.2: Confirmer que le serializer RefEngineSerializer retourne CODE, LABEL, IS_ACTIVE
  - [x] 3.3: Ajouter note dans la documentation API que ces codes sont la référence pour engine_type
  - [x] 3.4: Ajouter champ normalized_code (minuscules) dans le serializer pour faciliter usage frontend

- [x] Task 4: Documenter usage cohérent dans filtres RBAC et API inventaire (AC: profils et filtres)
  - [x] 4.1: Enrichir docs/rbac-filter-by-attribute.md avec recommandations engine_type
  - [x] 4.2: Documenter que les valeurs filter_by_attribute_json doivent suivre convention normalisée
  - [x] 4.3: Expliquer que le matching est case-insensitive (déjà implémenté)
  - [x] 4.4: Ajouter exemples: {"engine_type": ["oracle", "sql_server"]} aligne avec REF_ENGINES
  - [x] 4.5: Documenter endpoint GET /api/v1/inventory/servers/?engine_type=oracle utilise mêmes valeurs

- [x] Task 5: Tests de cohérence engine_type ↔ REF_ENGINES (AC: tests)
  - [x] 5.1: Créer test_engine_type_alignment.py dans reference/tests/
  - [x] 5.2: Test: Charger REF_ENGINES actifs et générer normalized_codes attendus
  - [x] 5.3: Test: Valider que exemples engine_type dans tests inventaire correspondent
  - [x] 5.4: Test: Valider que exemples filter_by_attribute_json dans tests RBAC correspondent
  - [x] 5.5: Test: Documenter valeurs engine_type non-conformes comme WARNINGS (pas erreurs bloquantes)

- [x] Task 6: Enrichir glossaire avec clarification explicite (AC: documentation)
  - [x] 6.1: Mettre à jour section engine_type dans django_backend/docs/glossary.md
  - [x] 6.2: Clarifier que engine_type DEVRAIT être aligné sur REF_ENGINES mais n'est pas validé
  - [x] 6.3: Expliquer pourquoi pas de validation stricte (sources externes multiples, flexibilité)
  - [x] 6.4: Ajouter recommandation: normaliser engine_type selon convention lors configuration InventoryMapper

## Dev Notes

### Architecture Context

**Contexte actuel (d'après analyse exploration):**

Le codebase définit **DEUX concepts similaires mais distincts**:

1. **`engine` (contexte catalogue/action)**
   - Source: Table `REF_ENGINES` (migration V049)
   - Utilisation: Champ `Action.engine` — "Sur quelle technologie DB **porte** cette action"
   - Valeurs: "Oracle", "SQL Server", "DB2", "PostgreSQL", "MySQL", "Workflow"
   - Format: Title case, espaces autorisés
   - API: `GET /api/v1/reference/engines`
   - Validation: Stricte lors création/édition action (serializer vérifie vs REF_ENGINES)

2. **`engine_type` (contexte inventaire/cible)**
   - Source: Configuration `InventoryMapper` (mapping colonnes sources externes)
   - Utilisation: Attribut des cibles — "Quelle technologie DB **est** cette cible"
   - Valeurs: Proviennent de sources externes (ex: "oracle", "sqlserver", "mysql")
   - Format: Généralement minuscules, underscores (mais pas garanti)
   - API: `GET /api/v1/inventory/servers/?engine_type=oracle`
   - Validation: **AUCUNE** — valeurs passthrough depuis source externe
   - Filtrage RBAC: Case-insensitive matching déjà implémenté

**État actuel de l'alignement:**

✓ **Ce qui fonctionne:**
- REF_ENGINES table créée avec 6 moteurs (V049)
- API `/api/v1/reference/engines` retourne liste référence
- InventoryMapper permet mapping flexible colonnes → engine_type
- RBAC filter_by_attribute_json supporte {"engine_type": ["oracle"]}
- Matching case-insensitive évite problèmes "Oracle" vs "oracle"
- Documentation distingue clairement engine vs engine_type (glossary.md)

⚠️ **Gaps identifiés:**
- Pas de lien formel entre valeurs REF_ENGINES et engine_type
- Pas de normalisation recommandée lors configuration mapping
- Pas de validation des valeurs engine_type dans filter_by_attribute_json
- Risque incohérences si sources externes utilisent codes différents (ex: "MSSQL" vs "SQL Server" vs "sqlserver")

**Décision de design actuelle:**
Le système est **volontairement découplé** pour flexibilité:
- REF_ENGINES = référentiel géré en base pour le catalogue
- engine_type = attribut flexible provenant de sources externes variées
- Pas de contrainte référentielle stricte (permet sources multiples avec conventions différentes)

**Objectif Story 29.3:**
Pas de modification de code, uniquement **documentation et tests** pour:
1. Clarifier la relation (découplage intentionnel)
2. Recommander convention de normalisation
3. Tester cohérence dans les exemples du codebase
4. Guider configuration InventoryMapper

### Technical Requirements

**Documentation à créer/enrichir:**

1. **Guide de mapping inventaire** (`docs/inventory-mapping-guide.md` — NOUVEAU)
   - Convention de normalisation engine_type
   - Tableau mapping REF_ENGINES.CODE → engine_type recommandé
   - Exemple configuration InventoryMapper avec engine_type
   - Explication pourquoi pas de validation stricte
   - Recommandations pour transformation lors import initial

2. **Enrichissement glossaire** (`django_backend/docs/glossary.md` — MODIFICATION)
   - Clarifier relation engine_type ↔ REF_ENGINES
   - Documenter recommandation d'alignement
   - Expliquer flexibilité vs cohérence
   - Lien vers inventory-mapping-guide.md

3. **Enrichissement RBAC doc** (`django_backend/docs/rbac-filter-by-attribute.md` — MODIFICATION)
   - Bonnes pratiques pour valeurs engine_type dans filter_by_attribute_json
   - Exemples recommandés vs à éviter
   - Note sur matching case-insensitive
   - Lien vers inventory-mapping-guide.md

**Tests de cohérence:**

Créer `reference/tests/test_engine_type_alignment.py`:
- Test normalisation REF_ENGINES → engine_type
- Test valeurs dans tests inventaire utilisent convention
- Test exemples filter_by_attribute_json alignés
- Test endpoint /api/v1/reference/engines disponible
- **Important:** Tests informatifs (WARNINGS ok), pas bloquants

**Pas de modifications code backend/frontend:**
- Pas de validation stricte à ajouter (design volontaire)
- Pas de normalisation automatique (sources externes variées)
- Pas de contrainte DB (trop rigide)

### Testing Requirements

**Tests de documentation:**
1. Liens markdown valides entre fichiers
2. Tableau mapping REF_ENGINES → engine_type complet
3. Exemples JSON syntax valid
4. Cohérence terminologie

**Tests de code (informatifs, non-bloquants):**
```
reference/tests/test_engine_type_alignment.py
├─ test_ref_engines_normalization_mapping()      # Documente mapping attendu
├─ test_inventory_test_fixtures_use_normalized() # Valide exemples tests inventaire
├─ test_rbac_filter_examples_alignment()         # Valide exemples filter RBAC
└─ test_api_reference_engines_endpoint_exists()  # Confirme API disponible
```

**Tests existants à valider (non-régression):**
- `inventory/tests/test_rbac_filter_by_attribute.py` — Matching case-insensitive fonctionne
- `reference/tests/test_models.py` — RefEngine.objects.active() retourne engines
- `reference/tests/test_views.py` — GET /api/v1/reference/engines endpoint fonctionne

**Couverture attendue:**
- Documentation: 100% (3 fichiers créés/modifiés)
- Tests informatifs: 4 tests passent avec éventuels WARNINGS documentés
- Pas de régression sur tests existants

### File Structure Notes

**Fichiers à créer:**
```
idp-portal/
  docs/
    inventory-mapping-guide.md                 # CREATE: guide normalisation engine_type
  django_backend/
    reference/tests/
      test_engine_type_alignment.py            # CREATE: tests cohérence informatifs
```

**Fichiers à modifier:**
```
idp-portal/
  django_backend/docs/
    glossary.md                                # MODIFY: enrichir section engine_type avec recommandation alignement
    rbac-filter-by-attribute.md                # MODIFY: ajouter bonnes pratiques engine_type
  docs/
    rapport-bases-moteurs-technologies-integrations.md  # MODIFY: ajouter lien vers inventory-mapping-guide.md
```

**Fichiers à lire (contexte):**
```
idp-portal/
  database/migrations/
    V049__create_ref_engines.sql               # READ: valeurs REF_ENGINES actuelles
  django_backend/
    reference/models.py                        # READ: RefEngine model
    inventory/mapper.py                        # READ: InventoryMapper.get_column('servers', 'engine_type')
    inventory/tests/test_rbac_filter_by_attribute.py  # READ: exemples engine_type actuels
```

### Previous Story Intelligence

**Story 29.2 (glossaire platform/engine/service) — 2026-02-15:**
- Glossaire enrichi avec distinctions Moteur (catalogue) vs engine_type (inventaire)
- Tableau récapitulatif clarifie contextes distincts
- Section engine_type déjà créée avec note "⚠️ Distinguer de engine (catalogue)"
- **Learning:** Vocabulaire "moteur" ambigu → préférer "engine" technique, "technologie" UI
- **Application:** Utiliser même terminologie précise dans inventory-mapping-guide.md
- **Fichier:** `django_backend/docs/glossary.md` — base solide à enrichir

**Story 13.7 (REF_ENGINES et REF_PLATFORMS tables) — 2026-02-05:**
- Migration V049 crée REF_ENGINES avec 6 valeurs (Oracle, SQL Server, DB2, PostgreSQL, MySQL, Workflow)
- API endpoint `/api/v1/reference/engines` implémenté avec RefEngineSerializer
- RefEngine Django model avec managers active()/ordered()
- Tests dans `reference/tests/test_models.py` et `test_views.py`
- **Learning:** Table de référence facile à étendre (INSERT nouveaux moteurs)
- **Application:** Documenter comment ajouter nouveau moteur si besoin

**Story 23.1 (config mapping colonnes inventaire) — 2026-02-09:**
- InventoryMapper permet config flexible colonnes source → concepts business
- Méthode `get_available_concepts('servers')` retourne concepts supportés dont engine_type
- Validation des clés concepts lors sauvegarde RBAC filter
- Fichier: `inventory/mapper.py` — ligne 45-67 build_select_clause()
- **Learning:** Config JSON mapping critique pour cohérence données
- **Application:** Guide mapping doit montrer exemples config concrets

**Story 23.4 (RBAC profils filtres par attribut) — 2026-02-09:**
- ProfileTargetPermission.filter_by_attribute_json stocke filtres {"engine_type": ["oracle"]}
- Filtrage case-insensitive implémenté dans InventoryRBACFilter._apply_attribute_filter()
- Tests dans `inventory/tests/test_rbac_filter_by_attribute.py`
- Utilise valeurs: "oracle", "sqlserver", "mysql" (note: "sqlserver" 1 mot)
- **Learning:** Matching case-insensitive fonctionne mais valeurs incohérentes ("sqlserver" vs "sql_server")
- **Application:** Tests alignment doivent documenter cette incohérence comme WARNING

**Epic 29 contexte (clarification Platform/Engine/Service):**
- Rapport technique 2026-02-14 (`docs/rapport-bases-moteurs-technologies-integrations.md`) identifie confusion
- Section 2.4 engine_type: "Pas de table de référence dédiée. Provient de la configuration source."
- Section 3.1: "Double vocabulaire moteur/technologie"
- Recommandation §5.4: "engine_type: soit documenter valeurs attendues [...] soit introduire table référence"
- **Décision Story 29.3:** Documenter valeurs recommandées (pas nouvelle table, trop rigide)

### Git Intelligence

**Commits récents Epic 29:**
```
2c6f1df docs(29-2): add comprehensive glossary for Platform/Engine/Service concepts
2ac1fb7 feat(29-1): add integration_role field to distinguish platforms from services
```

**Pattern commit Epic 29:**
- `feat(29-X):` pour modifications code/fixtures/migrations
- `docs(29-X):` pour modifications documentation uniquement

**Commit attendu Story 29.3:**
```
docs(29-3): align REF_ENGINES ↔ inventory engine_type documentation

- Create docs/inventory-mapping-guide.md with normalization convention
- Enrich django_backend/docs/glossary.md engine_type section (alignment recommendation)
- Enrich django_backend/docs/rbac-filter-by-attribute.md (best practices engine_type)
- Add reference/tests/test_engine_type_alignment.py (informative coherence tests)
- Update rapport-bases-moteurs-technologies-integrations.md cross-references

Story 29.3: Alignement REF_ENGINES ↔ engine_type inventaire
```

**Fichiers attendus dans commit:**
```
modified:   idp-portal/django_backend/docs/glossary.md
modified:   idp-portal/django_backend/docs/rbac-filter-by-attribute.md
modified:   idp-portal/docs/rapport-bases-moteurs-technologies-integrations.md
new file:   idp-portal/docs/inventory-mapping-guide.md
new file:   idp-portal/django_backend/reference/tests/test_engine_type_alignment.py
```

### Latest Technical Context

**État actuel REF_ENGINES (migration V049):**
```sql
CREATE TABLE REF_ENGINES (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    CODE            VARCHAR2(50) NOT NULL,
    LABEL           VARCHAR2(100) NOT NULL,
    DISPLAY_ORDER   NUMBER DEFAULT 0 NOT NULL,
    IS_ACTIVE       NUMBER(1) DEFAULT 1 NOT NULL
);

INSERT INTO REF_ENGINES (CODE, LABEL, DISPLAY_ORDER) VALUES
  ('Oracle', 'Oracle Database', 1),
  ('SQL Server', 'Microsoft SQL Server', 2),
  ('DB2', 'IBM DB2', 3),
  ('PostgreSQL', 'PostgreSQL', 4),
  ('MySQL', 'MySQL', 5),
  ('Workflow', 'Workflow Orchestration', 6);
```

**Normalisation recommandée:**
```python
def normalize_engine_code(ref_engine_code: str) -> str:
    """Convertit REF_ENGINES.CODE → engine_type normalisé."""
    return ref_engine_code.lower().replace(' ', '_')

# Examples:
# "Oracle" → "oracle"
# "SQL Server" → "sql_server"
# "DB2" → "db2"
# "PostgreSQL" → "postgresql"
# "MySQL" → "mysql"
# "Workflow" → "workflow"
```

**Utilisation actuelle engine_type dans tests:**
- Fichier: `inventory/tests/test_rbac_filter_by_attribute.py` (ligne 15-22)
- Valeurs utilisées: "oracle", "sqlserver", "mysql"
- ⚠️ Note: "sqlserver" (1 mot) vs recommandé "sql_server" (avec underscore)
- Fonctionne grâce au matching case-insensitive mais incohérent avec convention
- **Action:** Test alignment doit documenter cet écart comme WARNING acceptable

**API existantes (vérifiées):**
- `GET /api/v1/reference/engines` ✓ existe (Story 13.7)
  - File: `reference/views.py` ligne 19-32
  - Retourne: `[{"code": "Oracle", "label": "Oracle Database", "is_active": true}, ...]`
- `GET /api/v1/inventory/servers/?engine_type=oracle` ✓ existe (Story 23.3)
  - File: `inventory/views.py` ligne 98-127
  - Filtre: passé à `inventory_service.list_servers(environment, engine_type)`
- `ProfileTargetPermission.filter_by_attribute_json` ✓ supporte engine_type (Story 23.4)
  - File: `profiles/models.py` ligne 163-185
  - Format: `{"engine_type": ["oracle", "sql_server"]}`

**InventoryMapper engine_type:**
- File: `inventory/mapper.py` ligne 117-139
- Méthode: `build_select_clause('servers')` génère `SELECT ENGINE AS engine_type, ...`
- Config exemple (hypothétique):
```json
{
  "entities": {
    "servers": {
      "table": "DBOPS_SERVERS",
      "columns": {
        "name": "HOSTNAME",
        "environment": "ENV",
        "engine_type": "ENGINE"
      }
    }
  }
}
```
- Note: La colonne source `ENGINE` doit contenir valeurs normalisées (responsabilité admin intégration)

**Communication:**
- **Language:** Français (documentation utilisateur/produit)
- **Code/Variables:** English (exemples JSON, noms fonctions, code Python)
- **Terminologie:** "moteur" (métier/UI) vs "engine" (technique/code) — préférer "engine" dans doc technique

**Vocabulaire cohérent Epic 29:**
- **Moteur (Engine):** Technologie DB (REF_ENGINES, catalogue actions)
- **engine_type:** Attribut inventaire (sources externes, mapping)
- **Plateforme (Platform):** Où s'exécute (AAP, GitHub Actions, etc.)
- **Service:** Consommé (Vault, ServiceNow, Jira, Splunk)

### Project Context Reference

**Coding Standards:**
- Documentation: Markdown, headers ##/###, tableaux formatés, exemples code avec backticks
- Français pour texte narratif, English pour termes techniques/code
- Liens relatifs entre docs (../docs/file.md, ./autre-doc.md)
- Exemples JSON: syntax valid, pas de commentaires inline (utiliser paragraphes avant/après)

**Documentation Structure:**
- `django_backend/docs/` = documentation technique backend (architecture, modèles, services)
- `docs/` (root idp-portal) = documentation projet transverse (rapports, analyses, migration, guides)
- `frontend/docs/` = documentation frontend (conventions, logging)

**Tests Standards:**
- Tests informatifs (documentent état, WARNINGS acceptables): `pytest.skip()` avec message explicatif
- Tests bloquants (régressions): `assert` strict
- Couverture: viser 90%+ sur nouveaux fichiers, baseline existant acceptable
- Fichiers: `*/tests/test_*.py`, pytest discover automatique

**RBAC Context:**
- Documentation publique (pas de restriction accès)
- Glossaire accessible à tous: PM, Analyst, Dev, DBOPS, Auditeurs
- Guides techniques: Dev, Architect, Admin Intégrations

**Audience Documentation:**
1. **Équipe produit** (PM, Analyst, UX) — vocabulaire métier clair, exemples concrets
2. **Développeurs** (Backend, Frontend) — termes techniques précis, références code
3. **DBOPS** (utilisateurs finaux) — clarification concepts, impacts RBAC
4. **Admin Intégrations** — guides configuration, conventions de mapping
5. **Auditeurs/Conformité** — traçabilité concepts SOC1

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- 5/5 tests de cohérence passent (reference/tests/test_engine_type_alignment.py)
- 2/2 tests e2e RBAC+API passent (reference/tests/test_engine_type_e2e.py)
- 3/3 tests validation JSON doc passent (reference/tests/test_documentation_json_examples.py)
- 12 WARNINGS informatifs attendus (base de test sans données V049 — comportement normal)
- 18/18 reference tests passent (0 régression, +1 assertion normalized_code)
- 18/18 inventory RBAC filter tests passent (0 régression)

### Completion Notes List

- **Task 1:** Analyse complète des valeurs REF_ENGINES (V049) et engine_type (InventoryMapper). Identification des différences de format : casse (Oracle→oracle) et espaces (SQL Server→sqlserver vs sql_server recommandé).
- **Task 2:** Création de `docs/inventory-mapping-guide.md` — guide complet avec convention de normalisation, tableau de mapping, exemples InventoryMapper, vue SQL de normalisation, instructions pour ajouter un nouveau moteur. **[CODE REVIEW]** Ajout section "Exemples de valeurs problématiques" avec tableau comparatif.
- **Task 3:** Validation de l'endpoint `GET /api/v1/reference/engines` — existe (reference/views.py:29). **[CODE REVIEW]** Ajout champ `normalized_code` dans RefEngineSerializer et RefPlatformSerializer pour faciliter usage frontend (retourne valeur directement utilisable pour engine_type).
- **Task 4:** Enrichissement de `rbac-filter-by-attribute.md` avec section "Bonnes pratiques pour engine_type" — convention recommandée, exemples recommandés vs à éviter, matching case-insensitive, cohérence avec API inventaire, lien vers guide mapping.
- **Task 5:** Création de `reference/tests/test_engine_type_alignment.py` — 5 tests informatifs (normalisation mapping, fonction normalize, fixtures inventaire, exemples RBAC, endpoint API). Tests non-bloquants avec WARNINGS pour écarts documentés. **[CODE REVIEW]** Ajout logging structlog dans normalize_engine_code(), correction fixtures pour utiliser "sql_server" au lieu de "sqlserver", réduction verbosité WARNINGS. Création `test_engine_type_e2e.py` pour test end-to-end RBAC + API. Création `test_documentation_json_examples.py` pour valider syntaxe JSON de la doc.
- **Task 6:** Enrichissement de `glossary.md` section engine_type — tableau d'alignement REF_ENGINES→engine_type, explication du découplage intentionnel, lien vers guide de mapping. **[CODE REVIEW]** Clarification de "devraient" → "DOIVENT" pour renforcer la recommandation, ajout responsabilité explicite de l'admin intégration. Ajout référence croisée dans rapport technique.

### Change Log

- **2026-02-15:** Story 29.3 implémentée — documentation alignement REF_ENGINES ↔ engine_type, convention normalisation, tests informatifs cohérence, enrichissement glossaire et doc RBAC.
- **2026-02-15 (Code Review):** Corrections suite revue adversariale :
  - Ajout champ `normalized_code` dans serializers RefEngine/RefPlatform (AC: faciliter usage frontend)
  - Ajout tests e2e (RBAC + API cohérence) et validation JSON exemples documentation
  - Correction fixtures tests : "sqlserver" → "sql_server" (alignement convention)
  - Ajout section "Exemples valeurs problématiques" dans guide mapping
  - Clarification glossaire : "devraient" → "DOIVENT" (renforcement recommandation)
  - Ajout logging dans normalize_engine_code() pour débogage
  - Réduction verbosité WARNINGS tests (CI logs moins pollués)

### File List

**Fichiers créés :**
- `idp-portal/docs/inventory-mapping-guide.md` — Guide de mapping inventaire avec convention normalisation engine_type
- `idp-portal/django_backend/reference/tests/test_engine_type_alignment.py` — Tests informatifs cohérence engine_type ↔ REF_ENGINES (5 tests)
- `idp-portal/django_backend/reference/tests/test_engine_type_e2e.py` — **[CODE REVIEW]** Test end-to-end RBAC + API inventaire (2 tests)
- `idp-portal/django_backend/reference/tests/test_documentation_json_examples.py` — **[CODE REVIEW]** Validation syntaxe JSON exemples docs (3 tests)

**Fichiers modifiés :**
- `idp-portal/django_backend/docs/glossary.md` — Section engine_type enrichie avec tableau alignement et recommandation **[CODE REVIEW: clarification responsabilité admin]**
- `idp-portal/django_backend/docs/rbac-filter-by-attribute.md` — Section "Bonnes pratiques pour engine_type" ajoutée
- `idp-portal/docs/rapport-bases-moteurs-technologies-integrations.md` — Lien vers inventory-mapping-guide.md ajouté
- `idp-portal/django_backend/reference/serializers.py` — **[CODE REVIEW]** Ajout champ `normalized_code` dans RefEngineSerializer et RefPlatformSerializer
