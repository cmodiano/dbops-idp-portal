# Rapport : Clarification bases de données, moteurs, technologies et intégrations

**Date :** 2026-02-14  
**Constat :** Confusion entre les notions de « base de données », « moteur », « technologie », « plateforme » et « intégration » ; besoin de clarifier comment sont déterminées les technologies/moteurs disponibles.

---

## 1. Synthèse des concepts (état actuel)

Le codebase distingue **quatre notions** qui se recoupent partiellement et ne sont pas nommées de façon uniforme :

| Concept | Table / source | Rôle | Exposé au frontend |
|--------|-----------------|------|---------------------|
| **Engine (moteur / technologie)** | `REF_ENGINES` | Type de **technologie de base de données** (Oracle, SQL Server, Workflow, etc.) associé à une **action catalogue** | `GET /api/v1/reference/engines` → formulaire Action (champ « Technologie ») |
| **Platform (plateforme)** | `REF_PLATFORMS` | **Plateforme d’exécution** (AAP, GitHub Actions, Azure DevOps, Terraform) associée à une **action catalogue** | `GET /api/v1/reference/platforms` → formulaire Action (champ « Plateforme ») |
| **Type d’intégration** | `INTEGRATION_TYPE_CATALOGUE` | Type d’**instance d’intégration** configurable (aap, azure_devops, github_actions, etc.) | `GET /api/v1/integrations/types/` → formulaire Intégration (type d’intégration) |
| **engine_type (inventaire)** | Pas de table de référence | Attribut des **cibles** (serveurs / bases) dans l’inventaire pour filtrer les targets | Filtre optionnel sur API inventaire / permissions par attribut |

---

## 2. Détail par notion

### 2.1 Engine (REF_ENGINES) — « Moteur » / « Technologie »

- **Définition métier :** Technologie de base de données (ou « Workflow » pour les workflows) à laquelle une action catalogue est rattachée.
- **Table :** `REF_ENGINES` (V049). Colonnes : `CODE`, `LABEL`, `DISPLAY_ORDER`, `IS_ACTIVE`.
- **Valeurs initiales (migrations SQL) :** Oracle, SQL Server, DB2, PostgreSQL, MySQL, Workflow.
- **Utilisation :**
  - **Action (catalogue) :** `Action.engine` doit être un `CODE` présent dans `REF_ENGINES` (validé en création/édition par le serializer).
  - **Filtres :** catalogue (`?engine=Oracle`), exécutions, planification, dashboard (stats par engine).
  - **UI :** colonne « Technologie » dans les exécutions ; filtre « Technologie » ; formulaire Action (liste déroulante).
- **Détermination des valeurs disponibles :**  
  **`GET /api/v1/reference/engines?active_only=true`** → retourne les engines actifs, ordonnés par `display_order`, `code`.  
  Pas de fixture Django : données en base (migration V049 + éventuelles modifications admin).

**Vocabulaire dans le code :**  
- Backend : `engine`, `RefEngine`, « database engines/technologies ».  
- Frontend : « Technologie » (libellé colonne), `engine` (donnée).  
- Doc DB : « Moteur DB », « Database engine ».

---

### 2.2 Platform (REF_PLATFORMS) — « Plateforme »

- **Définition métier :** Plateforme d’exécution sur laquelle l’action est censée s’exécuter (AAP, GitHub Actions, Azure DevOps, Terraform).
- **Table :** `REF_PLATFORMS` (V051). Structure identique à REF_ENGINES.
- **Valeurs initiales :** AAP (Ansible Automation Platform), GitHub Actions, Azure DevOps, Terraform.
- **Utilisation :**
  - **Action (catalogue) :** `Action.platform` doit être un `CODE` de `REF_PLATFORMS` (validé par le serializer).
  - **Workflow runtime :** le payload d’étape contient `platform: referenced_action.platform` (couche adapter encore en TODO dans le workflow_runtime).
  - **UI :** formulaire Action (liste déroulante « Plateforme »).
- **Détermination des valeurs disponibles :**  
  **`GET /api/v1/reference/platforms?active_only=true`** → même principe que engines.

**Recoupement avec les intégrations (Story 29.4 — lien explicite) :**
Les **codes** REF_PLATFORMS (ex. « AAP », « GitHub Actions ») sont proches des **types** d'intégration (ex. `aap`, `github_actions`) :
- **REF_PLATFORMS** = libellé/catégorie pour **décrire** l'action (catalogue).
- **Integration.type** = type de l'**instance** d'intégration (config URL, credentials).

**Lien explicite (Story 29.4) :** La cohérence `action.platform` ↔ `integration.type` est maintenant **validée par le backend** quand les deux champs sont renseignés sur une action. La normalisation suit la convention `.lower().replace(' ', '_')` (ex. « GitHub Actions » → `github_actions`). Voir [platform-integration-mapping.md](../backend/platform-integration-mapping.md) pour le mapping complet et les règles de validation.

**Valeurs ajoutées (V073) :** Tower (Ansible Tower) et Terraform Cloud, pour couvrir tous les types plateforme du catalogue d'intégration (`IntegrationTypeCatalogue` où `integration_role='platform'`).

---

### 2.3 Type d’intégration (INTEGRATION_TYPE_CATALOGUE)

- **Définition métier :** Type d’une **instance** d’intégration (quelle plateforme technique : AAP, Azure DevOps, GitHub Actions, Terraform Cloud, Tower, Vault, ServiceNow, etc.).
- **Tables :** `INTEGRATION_TYPE_CATALOGUE` (code, name, description, is_active), `INTEGRATION_ACTIONS` (actions supportées par type, ex. start_job, run_pipeline).
- **Source des données :** Fixtures Django `integration_type_catalogue` (+ fixtures séparées pour les nouveaux types). Pas d’API d’écriture ; lecture seule.
- **Utilisation :**
  - **Integration :** chaque enregistrement `Integration` a un `type` (ex. `aap`, `azure_devops`) qui doit exister et être actif dans le catalogue.
  - **Exécution :** l’adapter est choisi via **integration.type** (ex. `get_platform_adapter(platform_type=integration.type, ...)` dans les chemins qui appellent les adapters ; aujourd’hui surtout dans les tâches de monitoring et les tests).
  - **UI :** formulaire « Nouvelle intégration » → liste déroulante des types issue de **`GET /api/v1/integrations/types/`**.
- **Détermination des valeurs disponibles :**  
  **`GET /api/v1/integrations/types/`** → tous les types avec `is_active=True` + leurs actions.  
  Les valeurs sont **chargées en base via fixtures** (`loaddata integration_type_catalogue` ou les 5 fixtures des nouveaux types).

**Vocabulaire :**  
- Backend : `integration.type`, `IntegrationTypeCatalogue`, « type d’intégration ».  
- Adapters : `platform_type` (ex. `aap`, `terraform_cloud`) = même sémantique que le `code` du catalogue d’intégration.

---

### 2.4 engine_type (inventaire / cibles)

- **Définition métier :** Type de moteur/technologie de la **cible** (serveur ou base) dans l’inventaire (ex. oracle, sqlserver pour filtrer les serveurs).
- **Source :** Pas de table de référence dédiée. Provient de la **configuration de la source d’inventaire** (API ou schéma BD) via `InventoryMapper` (ex. colonne `ENGINE` mappée en `engine_type`).
- **Utilisation :**
  - **Inventaire :** filtres `engine_type` sur serveurs/bases (ex. `GET /inventory/servers/?engine_type=oracle`).
  - **Profils :** `ProfileTargetPermission.filter_by_attribute_json` peut contenir `{"engine_type": ["oracle", "sqlserver"]}` pour restreindre les cibles accessibles.
- **Détermination des valeurs disponibles :**  
  **Non centralisée.** Les valeurs possibles dépendent des données exposées par la source d’inventaire (et du mapping). Il n’existe pas d’endpoint du type « liste des engine_type disponibles » ; on filtre avec des valeurs connues (souvent alignées sur les noms de technologies, en minuscules).

**Vocabulaire :**  
- Backend : `engine_type` (paramètre de filtre, clé dans `filter_by_attribute_json`).  
- Doc : « Database engine type », « type de moteur » (côté cible).

---

## 3. Où la confusion apparaît

### 3.1 Double vocabulaire « moteur » / « technologie »

- **REF_ENGINES** est décrit comme « database engines/technologies » (référentiel **catalogue**).
- **engine_type** dans l’inventaire désigne le **type de technologie de la cible** (serveur/base).
- Dans l’UI, la colonne des exécutions s’appelle « Technologie » et affiche `action.engine` (donc REF_ENGINES).  
→ Même idée (technologie de base de données) mais deux contextes : **action** vs **cible**. Une même valeur (ex. « Oracle ») peut apparaître côté action (REF_ENGINES) et côté inventaire (engine_type), sans lien explicite en base entre les deux.

### 3.2 Engine vs Platform vs Type d’intégration

- **Action** a à la fois :
  - **engine** (REF_ENGINES) : « sur quelle techno DB porte l’action » ;
  - **platform** (REF_PLATFORMS) : « sur quelle plateforme d’exécution » ;
  - **integration_id** (FK vers Integration) : « quelle instance utiliser pour exécuter ».
- **Integration** a **type** (catalogue d’intégration) : aap, azure_devops, github_actions, terraform_cloud, tower, vault, servicenow...
- Les **codes** REF_PLATFORMS (AAP, GitHub Actions, Azure DevOps, Terraform) et les **codes** du catalogue d’intégration (aap, github_actions, azure_devops, terraform_cloud) sont proches mais **pas identiques** (casse, tirets bas, « Terraform » vs « Terraform Cloud »). Aucune table ou règle ne les relie formellement.

### 3.3 Détermination des « moteurs / technologies » disponibles

- **Pour le catalogue (champ Technologie des actions) :**  
  Liste = **REF_ENGINES** actifs → **`GET /api/v1/reference/engines?active_only=true`**.  
  Géré en base (migrations + éventuelle admin) ; pas de fixture Django pour REF_ENGINES.

- **Pour les plateformes (champ Plateforme des actions) :**  
  Liste = **REF_PLATFORMS** actifs → **`GET /api/v1/reference/platforms?active_only=true`**.

- **Pour les types d’intégration (menu Admin Intégrations) :**  
  Liste = **IntegrationTypeCatalogue** actifs → **`GET /api/v1/integrations/types/`**.  
  Géré par **fixtures** (pas d’interface CRUD dédiée pour ajouter un type).

- **Pour l’inventaire (engine_type des cibles) :**  
  Pas de liste de référence unique ; dépend de la source d’inventaire et du mapping.

---

## 4. Schéma récapitulatif (flux de données)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ CATALOGUE D’ACTIONS (ACTIONS_CATALOG)                                        │
│   Action.engine     → REF_ENGINES.CODE   (technologie DB / Workflow)         │
│   Action.platform   → REF_PLATFORMS.CODE (plateforme d’exécution)             │
│   Action.integration_id → INTEGRATIONS.ID                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ INTÉGRATIONS (INTEGRATIONS)                                                  │
│   Integration.type → INTEGRATION_TYPE_CATALOGUE.CODE (aap, azure_devops…)   │
│   → Détermine l’adapter utilisé à l’exécution (get_platform_adapter(type))  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ RÉFÉRENTIELS (admin / migrations)                                           │
│   REF_ENGINES   → GET /reference/engines   → formulaire Action (Technologie)│
│   REF_PLATFORMS → GET /reference/platforms → formulaire Action (Plateforme)│
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ CATALOGUE D’INTÉGRATIONS (fixtures)                                          │
│   INTEGRATION_TYPE_CATALOGUE + INTEGRATION_ACTIONS                            │
│   → GET /integrations/types/ → formulaire Intégration (Type)                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ INVENTAIRE (cibles)                                                          │
│   engine_type = attribut des serveurs/bases (mapping source)                │
│   → Filtres API inventaire, filter_by_attribute_json (profils)               │
│   → Pas de liste de référence dédiée                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Recommandations (sans modification de code)

1. **Documenter un glossaire** (moteur, technologie, plateforme, type d’intégration, engine_type) et l’usage de chaque terme (catalogue vs inventaire vs exécution).
2. ~~**Clarifier la relation REF_PLATFORMS ↔ IntegrationTypeCatalogue**~~ → **FAIT (Story 29.4)** : Convention documentée dans [platform-integration-mapping.md](../backend/platform-integration-mapping.md), validation backend implémentée, REF_PLATFORMS complété (V073: Tower, Terraform Cloud).
3. **Centraliser « comment sont déterminées les listes disponibles »** dans un seul doc (comme ce rapport) avec les endpoints et sources (tables, fixtures).
4. **engine_type (inventaire) :** soit documenter les valeurs attendues par source (ex. oracle, sqlserver), soit introduire plus tard une table ou un endpoint de référence si on veut des listes déroulantes homogènes.

Ce rapport se limite à l'examen de l'existant ; aucune modification de code n'a été effectuée.

---

## 6. Références

- **Glossaire IDP Portal :** [glossary.md](../reference/glossary.md) — Définitions formelles des termes Moteur (Engine), Plateforme, Service, engine_type, avec tableau récapitulatif et exemples concrets.
- **Guide de mapping inventaire :** [docs/inventory-mapping-guide.md](../reference/inventory-mapping-guide.md) — Convention de normalisation engine_type, tableau de mapping REF_ENGINES → engine_type, configuration InventoryMapper.
- **Mapping REF_PLATFORMS ↔ IntegrationTypeCatalogue :** [platform-integration-mapping.md](../backend/platform-integration-mapping.md) — Convention de normalisation, tableau de mapping, règles de validation backend (Story 29.4).
