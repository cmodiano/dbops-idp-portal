# Glossaire — IDP Portal

## Vue d'ensemble

Ce glossaire définit les concepts clés du portail IDP pour éviter les ambiguïtés entre termes similaires. Il distingue notamment **quatre notions** qui se recoupent partiellement : Moteur (Engine), Plateforme (Platform), Service, et engine_type (inventaire).

> Pour une analyse technique complète, voir le [rapport bases, moteurs, technologies et intégrations](../integrations/rapport-bases-moteurs-technologies-integrations.md).

---

## Concepts fondamentaux

### Moteur (Engine)

**Définition :** Technologie de base de données ou type de workflow ciblé par une action catalogue.

**Table de référence :** `REF_ENGINES` (migration V049). Colonnes : `CODE`, `LABEL`, `DISPLAY_ORDER`, `IS_ACTIVE`.

**Valeurs :** Oracle, SQL Server, DB2, PostgreSQL, MySQL, Workflow.

**API :** `GET /api/v1/reference/engines?active_only=true`

**Utilisation :**
- Champ `Action.engine` dans le catalogue d'actions (validé par le serializer)
- Filtre UI « Technologie » dans exécutions / catalogue / planification / dashboard
- Colonne « Technologie » dans le tableau des exécutions

**⚠️ Distinguer de `engine_type` (inventaire)** — voir section [engine_type](#engine_type-inventaire) ci-dessous.

### Plateforme (Platform)

**Définition :** Système externe sur lequel le portail IDP **exécute** des jobs (orchestration distante).

**Table de référence :** `REF_PLATFORMS` (migration V051). Structure identique à `REF_ENGINES`.

**Valeurs :** AAP (Ansible Automation Platform), GitHub Actions, Azure DevOps, Terraform.

**API :** `GET /api/v1/reference/platforms?active_only=true`

**Utilisation :**
- Champ `Action.platform` dans le catalogue d'actions (validé par le serializer)
- Détermine quel **adapter** est utilisé à l'exécution (via `get_platform_adapter()`)
- Chaque plateforme hérite de `BaseAdapter` (package `adapters/platforms/`)
- UI : formulaire Action (liste déroulante « Plateforme »)

**Relation avec IntegrationTypeCatalogue :**
Les codes `REF_PLATFORMS` (ex. « AAP ») sont proches mais distincts des types d'intégration (ex. `aap`). La cohérence (ex. action « AAP » → intégration type `aap`) est implicite, sans liaison formelle en base. Depuis Story 29.1, les types d'intégration ont `integration_role='platform'`.

### Service

**Définition :** Système externe **consommé** par le portail pour une fonction transversale (secrets, logs, ITSM, gestion de tickets).

**Catalogue :** `INTEGRATION_TYPE_CATALOGUE` avec `integration_role='service'` (Story 29.1).

**Valeurs :** Vault, ServiceNow, Jira, Splunk.

**API :** `GET /api/v1/integrations/types/?role=service`

**Utilisation :**
- Services **ne sont pas** des plateformes d'exécution
- Accédés via factory `get_service_client()` (package `services/`)
- N'héritent **pas** de `BaseAdapter` (classes spécialisées : `VaultService`, `SplunkService`, `ServiceNowService`, `JiraService`)

### engine_type (inventaire)

**Définition :** Type de moteur/technologie de la **cible** (serveur ou base) dans l'inventaire.

**Source :** Pas de table de référence dédiée. Provient du mapping inventaire (`InventoryMapper`, configuration source externe).

**Valeurs courantes :** `oracle`, `sqlserver` (minuscules, souvent alignées sur `REF_ENGINES` mais pas formellement liées).

**Utilisation :**
- Filtre API inventaire : `GET /api/v1/inventory/servers/?engine_type=oracle`
- Filtrage RBAC : `ProfileTargetPermission.filter_by_attribute_json` avec `{"engine_type": ["oracle"]}`
- **Contexte :** Attribut d'une **cible** (inventaire), pas d'une action (catalogue)

**⚠️ engine (catalogue) vs engine_type (inventaire) :**
- `Action.engine` (`REF_ENGINES`) = « Sur quelle techno DB **porte** cette action »
- `engine_type` (inventaire) = « Quelle techno DB **est** cette cible »
- Même sémantique (ex. « oracle ») mais deux contextes distincts

**Alignement recommandé (Story 29.3) :**

Les valeurs `engine_type` **DOIVENT** être alignées sur les codes `REF_ENGINES` normalisés (minuscules + underscores) pour assurer la cohérence. Le système ne valide pas formellement mais la convention est **fortement recommandée** :

| REF_ENGINES.CODE | engine_type recommandé |
|------------------|----------------------|
| `Oracle` | `oracle` |
| `SQL Server` | `sql_server` |
| `DB2` | `db2` |
| `PostgreSQL` | `postgresql` |
| `MySQL` | `mysql` |
| `Workflow` | `workflow` |

**Pourquoi pas de validation stricte :** Les sources d'inventaire externes sont multiples et utilisent des conventions variées. Imposer une contrainte référentielle empêcherait l'intégration de sources avec des conventions non standard. Le matching case-insensitive (`UPPER()`) absorbe les différences de casse, mais **la normalisation lors de la configuration InventoryMapper est la responsabilité de l'administrateur d'intégration**.

**Recommandation :** Lors de la configuration d'un `InventoryMapper`, normaliser les valeurs `engine_type` selon la convention ci-dessus. Voir le [guide de mapping inventaire](inventory-mapping-guide.md) pour les détails de configuration.

---

## Différence Plateforme vs Service

| Aspect | Plateforme | Service |
|--------|-----------|---------|
| **Rôle** | Le portail y **exécute** des jobs (action distante) | Le portail le **consomme** (fonction support) |
| **Référentiel** | `REF_PLATFORMS` + `IntegrationTypeCatalogue` (`role=platform`) | `IntegrationTypeCatalogue` (`role=service`) |
| **Exemples** | AAP, GitHub Actions, Azure DevOps, Terraform | Vault, ServiceNow, Jira, Splunk |
| **Code backend** | Package `adapters/platforms/`, hérite de `BaseAdapter` | Package `services/`, classes spécialisées |
| **Factory** | `get_platform_adapter()` | `get_service_client()` |
| **Champ action** | `Action.platform` + `Action.integration_id` | Pas de champ sur l'action |
| **API types** | `GET /api/v1/integrations/types/?role=platform` | `GET /api/v1/integrations/types/?role=service` |

---

## Tableau récapitulatif : Plateforme vs Moteur vs Service

| Concept | Table / Source | Rôle | Exemples | API endpoint | Contexte |
|---------|---------------|------|----------|--------------|----------|
| **Moteur (Engine)** | `REF_ENGINES` | Technologie DB ciblée par action | Oracle, SQL Server, DB2, PostgreSQL, MySQL, Workflow | `GET /api/v1/reference/engines` | Catalogue actions |
| **Plateforme** | `REF_PLATFORMS` + `IntegrationTypeCatalogue` (`role=platform`) | Système où s'**exécute** l'action | AAP, GitHub Actions, Azure DevOps, Terraform | `GET /api/v1/reference/platforms`<br>`GET /api/v1/integrations/types/?role=platform` | Exécution distante |
| **Service** | `IntegrationTypeCatalogue` (`role=service`) | Système **consommé** par le portail | Vault, ServiceNow, Jira, Splunk | `GET /api/v1/integrations/types/?role=service` | Consommation |
| **engine_type (inventaire)** | Mapping inventaire (pas de table) | Technologie DB de la **cible** | oracle, sqlserver | `GET /api/v1/inventory/servers/?engine_type=oracle` | Inventaire cibles |

**Note :** `engine` (catalogue, `REF_ENGINES`) et `engine_type` (inventaire) partagent une sémantique similaire (type de technologie DB) mais opèrent dans des contextes distincts : l'un décrit l'action, l'autre décrit la cible.

---

## Exemples concrets d'utilisation

### Action catalogue complète

```json
{
  "id": 123,
  "name": "Backup Oracle Production",
  "engine": "Oracle",
  "platform": "AAP",
  "integration_id": 5,
  "requires_target": true
}
```

**Explications :**
- `engine`: "Oracle" → REF_ENGINES, technologie DB ciblée
- `platform`: "AAP" → REF_PLATFORMS, plateforme d'exécution
- `integration_id`: 5 → Integration type='aap', role='platform'

### Cible inventaire

```json
{
  "name": "ORADB-PROD-01",
  "engine_type": "oracle",
  "environment": "production",
  "server_name": "srv-ora-01.bank.local"
}
```

**Explications :**
- `engine_type`: "oracle" → attribut inventaire (mapping source externe, pas REF_ENGINES)

### Workflow d'exécution avec services

Une action Terraform Cloud (`platform=Terraform`, `engine=Workflow`) qui :
1. Récupère credentials depuis **Vault** (service)
2. S'exécute sur **Terraform Cloud** (plateforme)
3. Ouvre un changement dans **ServiceNow** (service)
4. Envoie les logs à **Splunk** (service)

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

---

## Références techniques

- **Architecture adapters :** [architecture.md](../backend/architecture-django.md)
- **Catalogue d'intégrations :** [integration-type-catalogue.md](../backend/integration-type-catalogue.md)
- **Analyse complète :** [rapport-bases-moteurs-technologies-integrations.md](../integrations/rapport-bases-moteurs-technologies-integrations.md)
- **Story 29.1 :** Ajout champ `integration_role` (platform/service) dans `IntegrationTypeCatalogue`

---

## Termes techniques additionnels

| Terme | Définition |
|-------|-----------|
| **Adapter (adaptateur de plateforme)** | Classe héritant de `BaseAdapter` dans le package `adapters/platforms/`. Responsable de l'exécution de jobs sur une plateforme distante (lancement, monitoring, annulation). Obtenu via la factory `get_platform_adapter()`. |
| **Service client** | Classe dans le package `services/` qui encapsule l'accès à un service externe (ex. `VaultService`, `SplunkService`, `ServiceNowService`, `JiraService`). N'hérite **pas** de `BaseAdapter`. Obtenu via la factory `get_service_client()`. |
| **BaseAdapter** | Classe abstraite (`adapters/base_adapter.py`) définissant le contrat commun des adapters de plateforme : `start_job()`, `get_job_status()`, `cancel_job()`, etc. |
| **Factory** | Fonction qui instancie le bon adapter ou service client selon le type d'intégration. `get_platform_adapter()` pour les plateformes, `get_service_client()` pour les services. |
| **REF_ENGINES** | Table de référence (V049) contenant les moteurs/technologies de base de données supportés. Colonnes : `CODE`, `LABEL`, `DISPLAY_ORDER`, `IS_ACTIVE`. |
| **REF_PLATFORMS** | Table de référence (V051) contenant les plateformes d'exécution supportées. Structure identique à `REF_ENGINES`. |
| **IntegrationTypeCatalogue** | Modèle Django qui référence tous les types d'intégration supportés (plateformes et services) avec leurs actions disponibles. Champ `integration_role` (platform/service) depuis Story 29.1. |
| **credential_ref** | Référence à un secret stocké dans Vault, au format `vault:mount/data/path#key`. Résolu au runtime par `VaultService`. Aucun secret n'est stocké en base. |
| **Service de secrets** | Service externe (ex. HashiCorp Vault) qui stocke et résout les credentials de manière sécurisée au moment de l'exécution. Le portail IDP utilise Vault comme service de secrets principal. |
| **Secret 0** | Credential initial permettant au portail de s'authentifier au service de secrets (bootstrap problem). Fourni par les variables d'environnement (VAULT_TOKEN ou VAULT_ROLE_ID + VAULT_SECRET_ID), jamais stocké en base. Voir [../backend/vault-bootstrap-guide.md](../backend/vault-bootstrap-guide.md). |
| **secret_service_id** | Champ optionnel sur le modèle `Integration` (Story 27.11). FK vers une intégration de type `vault` spécifiant quelle instance Vault utiliser pour résoudre les secrets. NULL = Vault par défaut. |
| **Circuit breaker** | Mécanisme de résilience qui coupe les appels vers un service indisponible après N échecs consécutifs. Utilisé par `VaultService` et `SplunkService`. |
| **correlation_id** | Identifiant UUID unique qui relie tous les événements d'une même exécution, de bout en bout (logs, audit, Splunk). |
