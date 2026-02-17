# Référentiels : environnements et technologies uniquement via tables (aucune valeur en dur)

**Contexte :** Aujourd’hui les environnements (dev, staging, prod) et les technologies/moteurs (Oracle, SQL Server, DB2) sont fixés par des contraintes CHECK en base et des enums/listes en dur dans le code. L’objectif est de **ne plus avoir aucune référence en dur** : tout est piloté par des **tables** (et pour les environnements, la **source de vérité est l’inventaire**).

---

## 1. Technologies (moteurs / engines) — table de référence dans le portail

**Principe :** Une table **REF_ENGINES** (ou REF_TECHNOLOGIES) dans le portail, gérée par DBOPS (admin). Plus de CHECK fixe sur `ACTIONS_CATALOG.ENGINE`.

### 1.1 Schéma proposé

- **Table `REF_ENGINES`**
  - `ID` (PK)
  - `CODE` (VARCHAR, unique) — ex. `Oracle`, `SQL Server`, `DB2`, `PostgreSQL`, `MySQL`, `Workflow`
  - `LABEL` (VARCHAR) — libellé affichage (peut être égal à CODE)
  - `DISPLAY_ORDER` (NUMBER) — ordre dans les listes
  - `IS_ACTIVE` (0/1) — désactiver sans supprimer

- **`ACTIONS_CATALOG.ENGINE`**  
  - Soit **FK vers REF_ENGINES(ID)** et on stocke l’id.  
  - Soit on garde **VARCHAR** et on stocke `REF_ENGINES.CODE` ; contrainte FK optionnelle (CODE référencé dans REF_ENGINES).  
  - Suppression de la contrainte CHECK actuelle (V002/V037).

### 1.2 API

- **GET /api/v1/reference/engines** (ou `/catalog/engines`)  
  - Retourne la liste des moteurs actifs (code, label, order).  
  - Utilisée par : formulaire action, filtres Exécutions, filtres Calendrier, catalogue.

### 1.3 Code

- **Backend :** plus d’enum `ActionEngine` en dur. Lecture des choix depuis la table (modèle Django `RefEngine`, ou service qui expose la liste).
- **Frontend :** plus de `ENGINE_OPTIONS` / `ENGINE_OPTIONS` en dur. Chargement des options via l’API reference/engines (au chargement de l’app ou des écrans concernés).
- **Validation :** à la création/mise à jour d’une action, vérifier que `engine` appartient à la liste retournée par reference/engines (ou FK si on utilise une FK).

### 1.4 Données initiales

- Migration SQL : création de la table + insertion des valeurs actuelles (Oracle, SQL Server, DB2, et éventuellement PostgreSQL, MySQL, Workflow si souhaité). Ensuite toute ajout/modification se fait via l’admin (écran de gestion des référentiels ou seed administrable).

---

## 2. Plateformes — même logique (optionnel mais cohérent)

- **Table `REF_PLATFORMS`** (ID, CODE, LABEL, DISPLAY_ORDER, IS_ACTIVE).
- **`ACTIONS_CATALOG.PLATFORM`** → référence par CODE ou FK.
- **GET /api/v1/reference/platforms** pour le frontend.
- Même principe : plus de liste en dur côté code.

---

## 3. Environnements — source de vérité = inventaire

**Principe :** Les **environnements valides** ne sont **pas** définis par une table fixe dans le portail : ils **proviennent de l’inventaire** (API externe ou schéma DBOPS_INVENTORY). Le portail ne fait que les **exposer** et les **utiliser** pour validation et listes.

### 3.1 Deux options de mise en œuvre

**Option A — Pas de table REF dans le portail (recommandé pour rester “inventaire = source”)**

- L’inventaire expose la liste des environnements qu’il connaît :
  - Soit l’**API externe** d’inventaire fournit un endpoint du type `GET .../environments`.
  - Soit le **portail** dérive la liste en interrogeant l’inventaire (ex. `GET /api/v1/inventory/targets` avec agrégation des `environment` distincts, ou un endpoint dédié **GET /api/v1/inventory/environments** qui demande à l’inventaire les environnements distincts).
- **Portail :**
  - **GET /api/v1/inventory/environments** (nouveau) : retourne la liste des environnements valides (provenant de l’inventaire). Le frontend et les filtres utilisent uniquement cette API.
  - **EXECUTIONS.ENVIRONMENT** et **SCHEDULED_EXECUTIONS.ENVIRONMENT** : on **supprime la contrainte CHECK fixe** ; la colonne reste VARCHAR. La **validation** se fait en applicatif : à la création d’une exécution ou planification, l’environnement doit appartenir à la liste retournée par `GET /api/v1/inventory/environments` (ou dérivée du target choisi, Epic 13).
- **Code :** suppression de toutes les listes en dur d’environnements (TargetEnvironment.VALUES, ENVIRONMENT_OPTIONS, etc.). Partout on utilise la liste renvoyée par l’API inventaire/environments (éventuellement mise en cache court en frontend pour les dropdowns).

**Option B — Table REF_ENVIRONMENTS alimentée par l’inventaire (cache/sync)**

- **Table `REF_ENVIRONMENTS`** dans le portail (ID, CODE, LABEL, DISPLAY_ORDER, SOURCE = 'inventory').
- Un **job périodique** (ou un sync à la demande) interroge l’inventaire (distinct des environnements des targets), puis met à jour `REF_ENVIRONMENTS` (insert/update des codes présents, désactivation des codes qui ne sont plus dans l’inventaire si besoin).
- **EXECUTIONS.ENVIRONMENT** : stocke le CODE ; contrainte **FK vers REF_ENVIRONMENTS(CODE)** ou colonne CODE avec vérification applicative.
- **GET /api/v1/reference/environments** (ou garder GET .../inventory/environments qui lit cette table) pour le frontend.
- Avantage : une seule source pour affichage et contraintes DB ; inconvénient : délai de sync et complexité du job.

### 3.2 Recommandation

- **Option A** si on veut que la source de vérité reste **directement** l’inventaire sans duplication (pas de table REF environnements dans le portail). La liste des environnements valides = ce que l’inventaire retourne.
- **Option B** si on veut une table de référence pour FK, audit, ou performance (éviter d’appeler l’inventaire à chaque chargement de formulaire).

### 3.3 Inventaire : exposition des environnements

- **Côté inventaire (API externe ou DBOPS_INVENTORY) :** idéalement exposer un endpoint ou une vue “liste des environnements” (distinct des environnements des targets). Si ce n’est pas possible, le portail peut dériver la liste à partir des targets (distinct(environment)).
- **Normalisation :** le portail peut conserver une couche de normalisation (alias certif → staging, etc.) soit dans l’inventaire, soit dans le service portail qui agrège les environnements, pour garder des codes cohérents (ex. toujours `staging` en base).

### 3.4 Profils (permissions) et environnements

- Aujourd’hui `PROFILE_ACTION_PERMISSIONS.ENVIRONMENTS_JSON` contient une liste d’environnements autorisés (ex. `["DEV","STAGING","PROD"]`).  
- Avec la source = inventaire : les valeurs autorisées dans ce JSON doivent être **restreintes aux environnements retournés par l’inventaire** (au moment de la configuration du profil). En affichage, les options du sélecteur d’environnements pour les profils viennent de **GET /api/v1/inventory/environments** (ou reference/environments si Option B), pas d’une liste en dur.

---

## 4. Résumé des changements

| Référentiel    | Aujourd’hui                    | Cible                                                                 |
|----------------|--------------------------------|-----------------------------------------------------------------------|
| **Technologies** | CHECK + enums/listes en dur    | Table **REF_ENGINES** + API reference/engines ; plus de liste en dur |
| **Plateformes**  | CHECK + enums/listes en dur    | Table **REF_PLATFORMS** + API reference/platforms (recommandé)         |
| **Environnements** | CHECK + listes en dur        | **Inventaire = source** ; API GET .../inventory/environments ; plus de liste en dur ; CHECK supprimé ou remplacé par table sync (Option B) |

---

## 5. Ordre de mise en œuvre suggéré

1. **REF_ENGINES** : migration table + API + alimentation initiale ; suppression CHECK ENGINE ; adapter catalog + executions + frontend pour utiliser l’API.
2. **REF_PLATFORMS** : idem si on souhaite tout piloter par tables.
3. **Environnements** : ajout GET /api/v1/inventory/environments (dérivation depuis l’inventaire ou appel à l’API externe) ; suppression des listes en dur et de la CHECK ENVIRONMENT ; validation applicative à la soumission ; adapter profils pour charger les options depuis l’API.

Ce document peut être rattaché à l’Epic 13 (inventaire) et éventuellement à une story dédiée “Référentiels pilotés par tables (environnements depuis inventaire, technologies/plateformes en tables)”.
