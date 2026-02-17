# Story 29.2: Glossaire produit Plateforme / Moteur / Service

Status: in-progress

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **équipe produit et utilisateur**,
I want **un glossaire documentant les trois concepts (Plateforme, Moteur, Service) avec des exemples concrets**,
So that **tout le monde parle le même langage et évite les confusions**.

## Acceptance Criteria

**Given** un document de référence
**When** on consulte le glossaire
**Then** les trois termes sont définis clairement : Plateforme (où s'exécute), Moteur (techno DB ciblée), Service (consommé)
**And** des exemples sont fournis pour chaque catégorie (liste Plateformes, Moteurs, Services)
**And** le document explique la différence entre plateforme et service (exécution vs consommation)
**And** le glossaire est intégré ou référencé dans la doc technique (docs/ ou implementation-artifacts/)

## Tasks / Subtasks

- [x] Task 1: Enrichir le glossaire existant avec les trois concepts clés (AC1, AC2, AC3)
  - [x] 1.1: Lire le glossaire actuel `django_backend/docs/glossary.md`
  - [x] 1.2: Ajouter définition **Moteur (Engine)** avec exemples (Oracle, SQL Server, DB2, PostgreSQL, MySQL)
  - [x] 1.3: Enrichir définition **Plateforme** avec référence REF_PLATFORMS et IntegrationTypeCatalogue
  - [x] 1.4: Enrichir définition **Service** avec liste exhaustive (Vault, ServiceNow, Jira, Splunk)
  - [x] 1.5: Ajouter section "Différence Plateforme vs Service" avec tableau comparatif
  - [x] 1.6: Ajouter terme **REF_ENGINES** avec lien vers modèle Django
  - [x] 1.7: Ajouter terme **REF_PLATFORMS** avec lien vers modèle Django
  - [x] 1.8: Ajouter terme **engine_type (inventaire)** pour distinguer moteur catalogue vs moteur cible

- [x] Task 2: Créer section "Clarification des concepts" dans le glossaire (AC3)
  - [x] 2.1: Ajouter tableau récapitulatif "Plateforme vs Moteur vs Service"
  - [x] 2.2: Colonnes: Concept, Table/Source, Rôle, Exemples, API endpoint
  - [x] 2.3: Ligne Moteur (Engine): REF_ENGINES, technologie DB ciblée, Oracle/SQL Server, GET /reference/engines
  - [x] 2.4: Ligne Plateforme: REF_PLATFORMS + IntegrationTypeCatalogue (role=platform), exécution distante, AAP/GitHub Actions, GET /reference/platforms + GET /integrations/types/?role=platform
  - [x] 2.5: Ligne Service: IntegrationTypeCatalogue (role=service), consommé par actions, Vault/ServiceNow/Jira/Splunk, GET /integrations/types/?role=service
  - [x] 2.6: Ajouter note sur engine_type (inventaire) vs engine (catalogue)

- [x] Task 3: Ajouter exemples concrets d'utilisation (AC2)
  - [x] 3.1: Exemple Action catalogue: engine=Oracle, platform=AAP, integration_id → type aap
  - [x] 3.2: Exemple cible inventaire: serveur avec engine_type=oracle, environment=production
  - [x] 3.3: Exemple workflow exécution: action Terraform (platform=Terraform, engine=Workflow) consomme Vault (service)
  - [x] 3.4: Ajouter diagramme ASCII simple flux action → plateforme + services

- [x] Task 4: Référencer rapport technique existant (AC4)
  - [x] 4.1: Ajouter lien vers `docs/rapport-bases-moteurs-technologies-integrations.md`
  - [x] 4.2: Ajouter note "Pour détails techniques complets, voir [rapport-bases-moteurs-technologies-integrations.md]"
  - [x] 4.3: Cross-référencer glossaire dans le rapport technique (lien inverse)

- [x] Task 5: Intégrer glossaire dans documentation navigable (AC4)
  - [x] 5.1: Créer ou mettre à jour `docs/README.md` ou `django_backend/docs/README.md` avec lien vers glossary.md
  - [x] 5.2: Optionnel: ajouter glossaire dans documentation Sphinx/MkDocs si existe — N/A (pas de Sphinx/MkDocs configuré)
  - [x] 5.3: S'assurer que glossary.md est dans table des matières principale

- [x] Task 6: Validation et tests (AC4)
  - [ ] 6.1: Reviewer avec équipe produit (PM/Analyst) pour validation vocabulaire — PENDING validation formelle
  - [x] 6.2: Vérifier que tous les termes du rapport technique sont couverts
  - [x] 6.3: Vérifier cohérence avec Story 29.1 (integration_role platform/service)
  - [x] 6.4: Tester navigation glossaire ↔ rapport technique ↔ docs API — FIXED: liens relatifs corrigés

## Dev Notes

### Architecture Context

**Contexte du Glossaire:**
- **Glossaire existant:** `django_backend/docs/glossary.md` (déjà 17 lignes avec Plateforme, Service, Adapter, BaseAdapter, etc.)
- **Rapport technique détaillé:** `idp-portal/docs/rapport-bases-moteurs-technologies-integrations.md` (181 lignes, analyse exhaustive)
- **Story précédente 29.1:** Ajout champ `integration_role` (platform/service) dans IntegrationTypeCatalogue

**Problème à résoudre:**
Le rapport technique du 2026-02-14 identifie **confusion entre 4 concepts** qui se recoupent:
1. **Engine (moteur)** — Table REF_ENGINES, technologie DB (Oracle, SQL Server, etc.)
2. **Platform (plateforme)** — Table REF_PLATFORMS, où s'exécute (AAP, GitHub Actions, etc.)
3. **Type d'intégration** — Table INTEGRATION_TYPE_CATALOGUE, types instances (aap, azure_devops, vault, servicenow, etc.)
4. **engine_type (inventaire)** — Attribut des cibles, pas de table référence, mapping dynamique

**Double vocabulaire:**
- "Moteur" = à la fois REF_ENGINES (catalogue actions) et engine_type (inventaire cibles)
- "Technologie" = utilisé UI pour afficher action.engine (REF_ENGINES)
- Pas de lien explicite REF_PLATFORMS ↔ IntegrationTypeCatalogue (codes proches mais pas identiques)

### Technical Requirements

**Structure du Glossaire enrichi:**

```markdown
# Glossaire — IDP Portal

## Vue d'ensemble

Ce glossaire définit les concepts clés du portail IDP pour éviter les ambiguïtés entre termes similaires.

## Concepts Fondamentaux

### Moteur (Engine)
**Définition:** Technologie de base de données ou type de workflow ciblé par une action catalogue.
**Table de référence:** `REF_ENGINES` (V049)
**Valeurs:** Oracle, SQL Server, DB2, PostgreSQL, MySQL, Workflow
**API:** `GET /api/v1/reference/engines?active_only=true`
**Utilisation:**
- Champ `Action.engine` dans le catalogue d'actions
- Filtre UI "Technologie" dans exécutions/catalogue
- Colonne "Technologie" dans tableau exécutions

**⚠️ Distinguer de `engine_type` (inventaire)** — voir section ci-dessous.

### Plateforme (Platform)
**Définition:** Système externe sur lequel le portail IDP **exécute** des jobs (orchestration distante).
**Table de référence:** `REF_PLATFORMS` (V051)
**Valeurs:** AAP, GitHub Actions, Azure DevOps, Terraform
**API:** `GET /api/v1/reference/platforms?active_only=true`
**Utilisation:**
- Champ `Action.platform` dans le catalogue d'actions
- Détermine quel **adapter** est utilisé à l'exécution (get_platform_adapter)
- Chaque plateforme hérite de `BaseAdapter` (package `adapters/platforms/`)

**Relation avec IntegrationTypeCatalogue:**
Les codes REF_PLATFORMS (ex. "AAP") sont proches mais distincts des types d'intégration (ex. "aap").
Depuis Story 29.1, les types d'intégration ont `integration_role='platform'`.

### Service
**Définition:** Système externe **consommé** par le portail pour une fonction transversale (secrets, logs, ITSM).
**Catalogue:** `INTEGRATION_TYPE_CATALOGUE` avec `integration_role='service'` (Story 29.1)
**Valeurs:** Vault, ServiceNow, Jira, Splunk
**API:** `GET /api/v1/integrations/types/?role=service`
**Utilisation:**
- Services **ne sont pas** des plateformes d'exécution
- Accédés via factory `get_service_client()` (package `services/`)
- N'héritent **pas** de BaseAdapter (classes spécialisées: VaultService, SplunkService, etc.)

**Différence clé Plateforme vs Service:**
- **Plateforme:** Le portail y **exécute** des jobs (action distante)
- **Service:** Le portail le **consomme** (fonction support)

### engine_type (inventaire)
**Définition:** Type de moteur/technologie de la **cible** (serveur ou base) dans l'inventaire.
**Source:** Pas de table référence dédiée. Provient du mapping inventaire (InventoryMapper, config source externe).
**Valeurs courantes:** oracle, sqlserver (minuscules, souvent alignées sur REF_ENGINES mais pas formellement liées)
**Utilisation:**
- Filtre API inventaire: `GET /inventory/servers/?engine_type=oracle`
- Filtrage RBAC: `ProfileTargetPermission.filter_by_attribute_json` avec `{"engine_type": ["oracle"]}`
- **Contexte:** Attribut d'une **cible** (inventaire), pas d'une action (catalogue)

**⚠️ engine (catalogue) vs engine_type (inventaire):**
- `Action.engine` (REF_ENGINES) = "Sur quelle techno DB **porte** cette action"
- `engine_type` (inventaire) = "Quelle techno DB **est** cette cible"
- Même sémantique (ex. "oracle") mais deux contextes distincts

## Tableau récapitulatif

| Concept | Table/Source | Rôle | Exemples | API endpoint | Contexte |
|---------|--------------|------|----------|--------------|----------|
| **Moteur (Engine)** | REF_ENGINES | Technologie DB ciblée par action | Oracle, SQL Server, DB2, PostgreSQL, MySQL, Workflow | GET /api/v1/reference/engines | Catalogue actions |
| **Plateforme** | REF_PLATFORMS + IntegrationTypeCatalogue (role=platform) | Système où s'**exécute** l'action | AAP, Tower, GitHub Actions, Azure DevOps, Terraform Cloud | GET /api/v1/reference/platforms<br>GET /api/v1/integrations/types/?role=platform | Exécution distante |
| **Service** | IntegrationTypeCatalogue (role=service) | Système **consommé** par le portail | Vault, ServiceNow, Jira, Splunk | GET /api/v1/integrations/types/?role=service | Consommation |
| **engine_type (inventaire)** | Mapping inventaire (pas de table) | Technologie DB de la **cible** | oracle, sqlserver | GET /api/v1/inventory/servers/?engine_type=oracle | Inventaire cibles |

## Exemples concrets

### Action catalogue complète
```json
{
  "id": 123,
  "name": "Backup Oracle Production",
  "engine": "Oracle",           // REF_ENGINES → Technologie DB ciblée
  "platform": "AAP",            // REF_PLATFORMS → Plateforme d'exécution
  "integration_id": 5,          // → Integration type='aap', role='platform'
  "requires_target": true
}
```

### Cible inventaire
```json
{
  "name": "ORADB-PROD-01",
  "engine_type": "oracle",      // Attribut inventaire (mapping source)
  "environment": "production",
  "server_name": "srv-ora-01.bank.local"
}
```

### Workflow d'exécution avec services
Une action Terraform Cloud (platform=Terraform, engine=Workflow) qui:
1. Récupère credentials depuis **Vault** (service)
2. S'exécute sur **Terraform Cloud** (plateforme)
3. Ouvre changement dans **ServiceNow** (service)
4. Envoie logs à **Splunk** (service)

```
┌─────────────────────────────────────────────────────┐
│ ACTION CATALOGUE                                     │
│   engine: Workflow                                   │
│   platform: Terraform                                │
│   integration_id → type='terraform_cloud' (platform) │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│ EXÉCUTION                                                 │
│  1. get_service_client('vault') → VaultService           │
│  2. get_platform_adapter('terraform_cloud') → TerraformAdapter │
│  3. get_service_client('servicenow') → ServiceNowService │
│  4. get_service_client('splunk') → SplunkService         │
└──────────────────────────────────────────────────────────┘
```

## Références techniques

- **Analyse complète:** [docs/rapport-bases-moteurs-technologies-integrations.md](../../docs/rapport-bases-moteurs-technologies-integrations.md)
- **Catalogue d'intégrations:** [django_backend/docs/integration-type-catalogue.md](./integration-type-catalogue.md)
- **Story 29.1:** Ajout champ integration_role (platform/service)
- **Architecture adapters:** [django_backend/docs/architecture.md](./architecture.md)

## Termes techniques additionnels

| Terme | Définition |
|-------|-----------|
| **Adapter (adaptateur de plateforme)** | Classe héritant de `BaseAdapter` dans le package `adapters/`. Responsable de l'exécution de jobs sur une plateforme distante (lancement, monitoring, annulation). Obtenu via la factory `get_platform_adapter()`. |
| **Service client** | Classe dans le package `services/` qui encapsule l'accès à un service externe (ex. `VaultService`, `SplunkService`, `ServiceNowService`). N'hérite **pas** de `BaseAdapter`. Obtenu via la factory `get_service_client()`. |
| **BaseAdapter** | Classe abstraite (`adapters/base_adapter.py`) définissant le contrat commun des adapters de plateforme : `start_job()`, `get_job_status()`, `cancel_job()`, etc. |
| **Factory** | Fonction qui instancie le bon adapter ou service client selon le type d'intégration. `get_platform_adapter()` pour les plateformes, `get_service_client()` pour les services. |
| **REF_ENGINES** | Table de référence (V049) contenant les moteurs/technologies de base de données supportés. Colonnes: CODE, LABEL, DISPLAY_ORDER, IS_ACTIVE. |
| **REF_PLATFORMS** | Table de référence (V051) contenant les plateformes d'exécution supportées. Structure identique à REF_ENGINES. |
| **IntegrationTypeCatalogue** | Modèle Django qui référence tous les types d'intégration supportés (plateformes et services) avec leurs actions disponibles. Champ `integration_role` depuis Story 29.1. |
| **credential_ref** | Référence à un secret stocké dans Vault, au format `vault:mount/data/path#key`. Résolu au runtime par `VaultService`. |
| **Circuit breaker** | Mécanisme de résilience qui coupe les appels vers un service indisponible après N échecs consécutifs. Utilisé par `VaultService` et `SplunkService`. |
| **correlation_id** | Identifiant UUID unique qui relie tous les événements d'une même exécution, de bout en bout (logs, audit, Splunk). |
```

**Localisation finale:** `idp-portal/django_backend/docs/glossary.md` (enrichissement du fichier existant)

### Testing Requirements

**Documentation Validation:**
1. Tous les termes du rapport technique sont couverts
2. Définitions claires et non-ambiguës
3. Exemples concrets pour chaque concept
4. Tableau récapitulatif facilement scannable
5. Liens cross-référencés fonctionnels

**Cohérence avec Story 29.1:**
1. Termes "platform" et "service" alignés sur integration_role
2. Exemples API utilisent `?role=platform|service`
3. Liste plateformes = aap, tower, azure_devops, github_actions, terraform_cloud
4. Liste services = vault, servicenow, jira, splunk

**Pas de tests automatisés** pour cette story (documentation uniquement), mais:
- Validation par code review (PM/Analyst/Architect)
- Vérification liens markdown valides
- Scan typos/orthographe

### File Structure Notes

**Fichiers modifiés:**
```
idp-portal/
  django_backend/docs/
    glossary.md                                    # MODIFY: enrichir avec 3 concepts
  docs/
    rapport-bases-moteurs-technologies-integrations.md  # MODIFY: ajouter lien vers glossaire
    README.md                                      # CREATE ou MODIFY: index documentation
```

**Optionnel (si doc navigable existe):**
```
idp-portal/
  docs/
    mkdocs.yml                                     # MODIFY: ajouter glossary dans nav
  ou
  django_backend/docs/
    conf.py (Sphinx)                               # MODIFY: ajouter glossary dans toctree
```

### Previous Story Intelligence

**Story 29.1 (integration_role platform/service):**
- Champ `integration_role` ajouté à IntegrationTypeCatalogue
- Fixtures mises à jour: 5 platforms (aap, tower, azure_devops, github_actions, terraform_cloud), 4 services (vault, servicenow, jira, splunk)
- API filter `?role=platform|service` implémenté
- Frontend UI groupement OptGroup + Badge bleu (platform) / vert (service)
- **Learnings:** Liste exhaustive des types validée, documentation alignée, tests fixtures loaddata critiques

**Story 27.9 (refactoring adapters vs services):**
- Séparation claire `adapters/platforms/` vs `services/`
- Factory `get_platform_adapter()` vs `get_service_client()`
- BaseAdapter héritage uniquement pour plateformes
- **Learnings:** Vocabulaire technique "adapter" vs "service client" déjà établi, à reprendre dans glossaire

**Rapport technique 2026-02-14:**
- Analyse exhaustive des 4 concepts (Engine, Platform, Type intégration, engine_type)
- Constat de confusion double vocabulaire moteur/technologie
- Recommandation: "Documenter un glossaire" (§5.1 du rapport)
- **Learnings:** Tableau récapitulatif du rapport (§4 Schéma) est excellent base pour glossaire

### Latest Technical Context

**Glossaire existant (django_backend/docs/glossary.md):**
- 17 lignes actuelles
- Déjà définit: Plateforme, Service, Adapter, Service client, BaseAdapter, Factory, credential_ref, Circuit breaker, IntegrationTypeCatalogue, correlation_id
- **Action:** Enrichir (pas réécrire), ajouter Moteur, REF_ENGINES, REF_PLATFORMS, engine_type, tableau récapitulatif, exemples

**Rapport technique (docs/rapport-bases-moteurs-technologies-integrations.md):**
- 181 lignes, 5 sections, exhaustif
- §1 Synthèse: tableau 4 concepts
- §2 Détail par notion (4 sous-sections)
- §3 Où la confusion apparaît
- §4 Schéma récapitulatif (ASCII)
- §5 Recommandations
- **Action:** Cross-référencer depuis glossaire (lien "Pour détails techniques complets")

**Vocabulaire établi:**
- Backend: engine, platform, integration.type, engine_type
- Frontend: "Technologie" (UI colonne), "Plateforme" (UI formulaire)
- Doc DB: "Moteur DB", "Database engine"
- **Action:** Unifier dans glossaire avec priorité vocabulaire backend (plus précis)

**Communication:**
- **Language:** Français (glossaire audience produit + équipe)
- **Code/Variables:** English (exemples JSON/code dans glossaire)

### Git Intelligence

Commits récents Epic 29:
```
2ac1fb7 feat(29-1): add integration_role field to distinguish platforms from services
```

Pattern commit Epic 29:
```
feat(29-X): [description courte]
```

Commit attendu Story 29.2:
```
docs(29-2): add comprehensive glossary for Platform/Engine/Service concepts

- Enrich django_backend/docs/glossary.md with 3 core concepts
- Add Moteur (Engine) definition with REF_ENGINES reference
- Add Platform vs Service comparison table
- Add concrete examples (action catalog, inventory target, workflow execution)
- Cross-reference rapport-bases-moteurs-technologies-integrations.md
- Distinguish engine (catalog) vs engine_type (inventory)
```

### Project Context Reference

**Coding Standards:**
- Documentation: Markdown, headers ##/###, tableaux formatés, exemples code avec backticks
- Français pour texte narratif, English pour termes techniques/code
- Liens relatifs entre docs (../docs/file.md)

**Documentation Structure:**
- `django_backend/docs/` = documentation technique backend (architecture, modèles, services)
- `docs/` (root idp-portal) = documentation projet transverse (rapports, analyses, migration)
- `frontend/docs/` = documentation frontend (conventions, logging)

**RBAC Context:**
- Documentation publique (pas de restriction accès)
- Glossaire accessible à tous: PM, Analyst, Dev, DBOPS, Auditeurs

**Audience Glossaire:**
1. **Équipe produit** (PM, Analyst, UX) — vocabulaire métier clair
2. **Développeurs** (Backend, Frontend) — termes techniques précis
3. **DBOPS** (utilisateurs finaux) — clarification "moteur" action vs cible
4. **Auditeurs/Conformité** — traçabilité concepts SOC1

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

Aucun debug nécessaire — story documentation uniquement.

### Completion Notes List

- Glossaire enrichi de 17 lignes → ~190 lignes avec 4 concepts fondamentaux détaillés (Moteur, Plateforme, Service, engine_type)
- Tableau comparatif "Différence Plateforme vs Service" (7 critères : rôle, référentiel, exemples, code backend, factory, champ action, API)
- Tableau récapitulatif "Plateforme vs Moteur vs Service" (6 colonnes : Concept, Table/Source, Rôle, Exemples, API endpoint, Contexte)
- 3 exemples concrets JSON (action catalogue, cible inventaire, workflow avec services) + diagramme ASCII flux exécution
- Cross-référencement bidirectionnel glossaire ↔ rapport technique
- README.md créé pour `django_backend/docs/` avec table des matières et glossaire en première position
- Termes techniques additionnels préservés et enrichis (13 termes dont REF_ENGINES, REF_PLATFORMS, IntegrationTypeCatalogue avec integration_role)
- Validation automatisée : 13/13 termes couverts, 4/4 endpoints API référencés, cohérence Story 29.1 confirmée
- Pas de tests automatisés (story documentation uniquement, conformément aux Dev Notes)
- **Code Review 2026-02-15:** 14 issues détectées et corrigées automatiquement (4 CRITICAL, 7 MEDIUM, 3 LOW)
  - FIXED: Lien relatif cassé rapport → glossaire
  - FIXED: Liens morts README.md (sso-architecture.md)
  - FIXED: Commentaires JSON invalides (déplacés hors blocs code)
  - FIXED: Inconsistance "Terraform" vs "Terraform Cloud" (uniformisé)
  - FIXED: Ordre références techniques (Architecture → Catalogue → Analyse → Stories)
  - FIXED: Retrait marqueurs "(si existant)" inutiles
  - FIXED: Retrait "Tower (legacy)" des exemples principaux
  - PENDING: Task 6.1 validation équipe produit (démarquée pour refléter réalité)

### Change Log

- 2026-02-15 10:00: Glossaire enrichi avec concepts Moteur/Plateforme/Service/engine_type, tableau récapitulatif, exemples concrets, cross-références
- 2026-02-15 14:30: Code review — corrections qualité (14 issues): liens relatifs, JSON syntax, cohérence terminologie, ordre sections

### File List

- `idp-portal/django_backend/docs/glossary.md` — MODIFIED: enrichi avec 4 concepts fondamentaux, tableaux comparatifs, exemples, références; code review fixes (JSON syntax, terminologie, ordre sections)
- `idp-portal/docs/rapport-bases-moteurs-technologies-integrations.md` — MODIFIED: ajout section 6 Références avec lien vers glossaire (lien relatif corrigé)
- `idp-portal/django_backend/docs/README.md` — CREATED: table des matières documentation backend avec glossaire en première position (liens morts corrigés)
- `_bmad-output/implementation-artifacts/29-2-glossaire-plateforme-moteur-service.md` — MODIFIED: story file avec notes code review
