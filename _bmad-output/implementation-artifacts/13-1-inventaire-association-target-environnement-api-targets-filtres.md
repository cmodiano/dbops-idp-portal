# Story 13.1 : Inventaire — source via intégration (API ou DB), association target à un environnement, API targets filtrés

Status: done

## Story

As a système,
I want que la source des targets soit une intégration (type `inventory` ou `inventory_db`) et que chaque target soit associé à un environnement (dev, certif, prod),
So that l'environnement d'une exécution est dérivé du target choisi et qu'en dev sans API le fallback DBOPS_INVENTORY (synonyme) soit utilisé.

## Acceptance Criteria

### AC1 — Source inventaire via intégration
**Given** la source des targets est une **intégration** (table INTEGRATIONS) : type `inventory` (API externe, base_url + credential_ref) ou `inventory_db` (lecture depuis schéma BD, config ex. schema DBOPS_INVENTORY),
**When** le backend cherche des targets,
**Then** il utilise l'intégration active de type `inventory` ou `inventory_db` pour récupérer les données.

### AC2 — Fallback DBOPS_INVENTORY en dev
**Given** aucune intégration inventaire n'est configurée (ex. dev),
**When** le backend cherche des targets,
**Then** il utilise le **fallback** : lecture depuis le schéma DBOPS_INVENTORY (accès via synonyme Oracle).

### AC3 — Target avec environnement
**Given** un target (serveur, base, groupe) est enregistré (API, table inventaire, ou DBOPS_INVENTORY),
**When** on le consulte,
**Then** il possède un attribut `environment` (dev, certif, prod) et cet attribut est la source de vérité pour l'environnement.

### AC4 — API liste targets avec filtres
**Given** une API liste les targets (GET `/api/v1/inventory/targets`),
**When** elle est appelée avec des filtres (environnement, user/permissions),
**Then** elle retourne les targets avec leur environnement, filtrés par permissions utilisateur (pour usage dans le wizard).

### AC5 — Données inventaire exposent environnement
**And** les données inventaire alimentant les formulaires dynamiques (FR43) exposent l'environnement par target.

## Tasks / Subtasks

### Backend — Django App `inventory`

- [x] **Task 1** (AC: 1,2) — Créer l'app Django `inventory`
  - [x] Subtask 1.1 — Créer le module `idp-portal/django_backend/inventory/` avec __init__.py, apps.py, admin.py
  - [x] Subtask 1.2 — Ajouter `'inventory'` à INSTALLED_APPS dans settings.py

- [x] **Task 2** (AC: 3) — Créer les structures de données `Target` (dataclass, pas de table DB)
  - [x] Subtask 2.1 — ~~Migration créant table TARGETS~~ **SUPPRIMÉ** : pas de table locale, lecture directe depuis sources externes
  - [x] Subtask 2.2 — Dataclass Target avec attributs (name, environment, target_type, metadata)
  - [x] Subtask 2.3 — Classes TargetEnvironment et TargetType avec constantes

- [x] **Task 3** (AC: 1,2) — Service `InventoryService` pour résolution source
  - [x] Subtask 3.1 — Méthode `get_active_inventory_integration()` : cherche Integration type=inventory ou inventory_db
  - [x] Subtask 3.2 — Méthode `list_targets()` : si intégration API → placeholder, sinon lecture Oracle
  - [ ] Subtask 3.3 — ~~Client HTTP pour intégration type=inventory~~ **DEFERRED** : à implémenter quand API externe disponible (placeholder retourne [])
  - [x] Subtask 3.4 — Lecteur Oracle pour intégration type=inventory_db ou fallback synonyme DBOPS_INVENTORY
  - [x] Subtask 3.5 — *(Code Review)* Validation SQL injection sur noms de table/synonym
  - [x] Subtask 3.6 — *(Code Review)* Normalisation des environnements (certif → staging)

- [x] **Task 4** (AC: 4,5) — Endpoints API REST
  - [x] Subtask 4.1 — Créer `inventory/urls.py` et `inventory/views.py` avec fonctions
  - [x] Subtask 4.2 — `GET /api/v1/inventory/targets` : liste paginée avec filtres (environment, search, type)
  - [x] Subtask 4.3 — ~~`GET /api/v1/inventory/targets/{id}`~~ **SUPPRIMÉ** : pas d'ID local, lecture depuis source externe
  - [x] Subtask 4.4 — Serializers (TargetSerializer, TargetFilterParamsSerializer)
  - [x] Subtask 4.5 — Filtrage RBAC : cumul permissions profils pour environnements et restrictions target
  - [x] Subtask 4.6 — *(Code Review)* Permission `IsAdminOrIntegration` sur `/targets/all`
  - [x] Subtask 4.7 — *(Code Review)* Gestion erreur 503 pour `InventoryServiceError`

- [x] **Task 5** (AC: 1-5) — Tests unitaires et intégration
  - [x] Subtask 5.1 — Tests InventoryService (mock intégration, mock fallback Oracle)
  - [x] Subtask 5.2 — Tests API endpoints (authentification, filtrage, pagination)
  - [x] Subtask 5.3 — Tests permission RBAC (profil avec env limités, restrictions pattern/liste)
  - [x] Subtask 5.4 — *(Code Review)* Tests validation SQL injection
  - [x] Subtask 5.5 — *(Code Review)* Tests normalisation environnement (certif → staging)
  - [x] Subtask 5.6 — *(Code Review)* Tests permission admin sur `/targets/all`
  - [x] Subtask 5.7 — *(Code Review)* Tests gestion erreur 503

### Base de données

- ~~**Task 6** (AC: 3) — Migration Flyway pour table TARGETS~~
  - **SUPPRIMÉ** : Pas de table locale. Les données viennent des sources externes (API inventaire ou DBOPS_INVENTORY).
  - Décision prise pour simplifier l'architecture : pas de duplication des données d'inventaire.

- ~~**Task 7** (AC: 2) — Synonyme fallback DBOPS_INVENTORY~~
  - **SUPPRIMÉ** : Le synonyme DBOPS_INVENTORY doit être créé par le DBA.
  - Structure attendue documentée dans Dev Notes.

## Dev Notes

### Architecture simplifiée (décision 2026-02-05)

**Pas de table TARGETS locale** — Les données d'inventaire viennent directement des sources externes :
1. **Intégration type=inventory** : API externe (à implémenter)
2. **Intégration type=inventory_db** : Lecture depuis schéma Oracle configuré
3. **Fallback** : Lecture depuis synonyme DBOPS_INVENTORY

Cette approche évite la duplication des données et garantit que l'inventaire est toujours à jour.

### Structure attendue par le portail (contrat actuel)

Le portail lit une **seule** table ou vue avec exactement ces colonnes :
- `NAME` VARCHAR2(255) — Nom du target (serveur, base, groupe)
- `ENVIRONMENT` VARCHAR2(20) — Environnement: DEV, STAGING, PROD
- `TYPE` VARCHAR2(50) — Type: SERVER, DATABASE, GROUP, CLUSTER

### Schéma DBOPS_INVENTORY réel (normalisé)

En pratique le schéma inventaire est normalisé, par exemple :

- **SERVER** : ID, NAME, HOSTNAME, IP_ADDRESS, **ENVIRONMENT**, OS_TYPE, STATUS, ENABLED, LOCATION, …
- **INSTANCE** : ID, SERVER_ID, NAME, ORACLE_HOME, ORACLE_VERSION, SID, PORT, STATUS, …
- **DB** : ID, INSTANCE_ID, NAME, DB_UNIQUE_NAME, **DB_TYPE**, VERSION, STATUS, …
- **PDB** : ID, DB_ID, NAME, PDB_NAME, STATUS, …
- **SCHEMAS** : ID, PDB_ID, DB_ID, SCHEMA_NAME, APPLICATION_NAME, OWNER_TEAM, STATUS, …

Les environnements valides viennent de **SERVER.ENVIRONMENT** ; les technologies (moteur) peuvent être dérivées de **DB.DB_TYPE** ou **INSTANCE**. Pour que le portail continue à consommer le même contrat (NAME, ENVIRONMENT, TYPE), il faut exposer une **vue de compatibilité** qui aplatit ce schéma (voir ci‑dessous).

---

### Utilisation concrète du schéma local (inventory_db et fallback)

On peut « simuler » l’API inventaire en utilisant **soit** un schéma local configuré via une intégration **inventory_db**, **soit** le **fallback** sur le synonyme `DBOPS_INVENTORY`. Aucune API externe n’est nécessaire.

#### 1. Créer la table ou vue dans Oracle

Dans un schéma auquel l’utilisateur du portail a accès (ex. `MON_SCHEMA`), créer une table ou vue avec exactement ces colonnes :

```sql
-- Exemple : table dans un schéma dédié (dev / démo)
CREATE TABLE MON_SCHEMA.INVENTORY_TABLE (
  NAME      VARCHAR2(255) NOT NULL,
  ENVIRONMENT VARCHAR2(20) NOT NULL,
  TYPE      VARCHAR2(50)  NOT NULL
);

INSERT INTO MON_SCHEMA.INVENTORY_TABLE (NAME, ENVIRONMENT, TYPE) VALUES ('srv-dev-01', 'DEV', 'SERVER');
INSERT INTO MON_SCHEMA.INVENTORY_TABLE (NAME, ENVIRONMENT, TYPE) VALUES ('srv-dev-02', 'DEV', 'SERVER');
INSERT INTO MON_SCHEMA.INVENTORY_TABLE (NAME, ENVIRONMENT, TYPE) VALUES ('db-prod-01', 'PROD', 'DATABASE');
-- ...
```

**Si le schéma réel est DBOPS_INVENTORY (SERVER, DB, INSTANCE, PDB, SCHEMAS)** : créer une **vue de compatibilité** qui expose NAME, ENVIRONMENT, TYPE. Exemple (à adapter à la casse et aux noms exacts) :

```sql
CREATE OR REPLACE VIEW DBOPS_INVENTORY.INVENTORY_TARGETS AS
SELECT NAME, ENVIRONMENT, 'SERVER' AS TYPE FROM DBOPS_INVENTORY.SERVER WHERE ENABLED = 1
UNION ALL
SELECT d.NAME AS NAME, s.ENVIRONMENT AS ENVIRONMENT, 'DATABASE' AS TYPE
FROM DBOPS_INVENTORY.DB d
JOIN DBOPS_INVENTORY.INSTANCE i ON i.ID = d.INSTANCE_ID
JOIN DBOPS_INVENTORY.SERVER s ON s.ID = i.SERVER_ID
WHERE d.STATUS = 'OPEN' OR d.STATUS IS NULL;
```

Puis faire pointer le synonyme (dans le schéma du portail) vers cette vue : `CREATE OR REPLACE SYNONYM DBOPS_INVENTORY FOR DBOPS_INVENTORY.INVENTORY_TARGETS;`

Les valeurs d’environnement sont normalisées côté portail (ex. certif → staging, casse ignorée). Les types reconnus sont : SERVER, DATABASE, GROUP, CLUSTER (sinon SERVER par défaut).

#### 2. Option A — Fallback (sans intégration)

Si **aucune** intégration de type `inventory` ou `inventory_db` n’est configurée, le backend utilise automatiquement le **synonyme** `DBOPS_INVENTORY`.

- Le schéma du portail est **IDP_APP**. Le DBA crée dans IDP_APP un synonyme `DBOPS_INVENTORY` pointant vers une vue (colonnes NAME, ENVIRONMENT, TYPE) :
  ```sql
  CREATE OR REPLACE SYNONYM IDP_APP.DBOPS_INVENTORY FOR DBOPS_INVENTORY.INVENTORY_TARGETS;
  ```
- Aucune configuration dans l’admin du portail : dès que `GET /api/v1/inventory/targets` est appelé, les données viennent de `DBOPS_INVENTORY`.

**Résolution :** pas d’intégration → lecture directe depuis `DBOPS_INVENTORY`.

#### 3. Option B — Intégration type inventory_db (schéma explicite)

Pour utiliser un **schéma/table précis** (différent du synonyme `DBOPS_INVENTORY`), créer une **intégration** de type **inventory_db** avec un **config** JSON contenant `schema` et `table`.

- **Via l’API** (le formulaire Admin actuel n’expose pas encore le champ `config` pour inventory_db) :

  ```http
  POST /api/v1/admin/integrations
  Content-Type: application/json

  {
    "type": "inventory_db",
    "name": "Inventaire schéma local",
    "base_url": "https://placeholder.inventory.local",
    "config": {
      "schema": "MON_SCHEMA",
      "table": "INVENTORY_TABLE"
    }
  }
  ```

- Le backend lit alors **uniquement** `MON_SCHEMA.INVENTORY_TABLE` (pas le synonyme). Les noms `schema` et `table` sont validés (alphanum + underscore, format `schema.table`) pour éviter l’injection SQL.
- Valeurs par défaut si `config` est vide : `schema` = `DBOPS_INVENTORY`, `table` = `INVENTORY_TABLE` (voir `inventory/services.py`).

**Résolution :** une intégration `inventory_db` active → lecture depuis `config.schema` + `config.table`.

#### 4. Ordre de résolution (qui est utilisé ?)

1. S’il existe une intégration **inventory** (API) → elle est utilisée (pour l’instant placeholder, retourne []).
2. Sinon, s’il existe une intégration **inventory_db** → lecture depuis `config.schema` + `config.table` (ou défauts).
3. Sinon → **fallback** : lecture depuis le synonyme **DBOPS_INVENTORY**.

Une seule source est utilisée à la fois ; il n’y a pas de fusion de plusieurs sources.

#### 5. Vérification

- Appeler **GET /api/v1/inventory/targets** (avec un utilisateur authentifié ayant des permissions sur au moins un environnement). Les targets retournés doivent avoir `name`, `environment`, `target_type`.
- Filtrer par environnement : **GET /api/v1/inventory/targets?environment=dev**.
- En dev, si aucune intégration n’est créée et que le synonyme `DBOPS_INVENTORY` pointe vers une table de test, c’est bien le schéma local qui « simule » l’API.

#### 6. Résumé

| Mode | Configuration | Source lue |
|------|----------------|------------|
| **Fallback** | Aucune intégration inventory / inventory_db | Synonyme `DBOPS_INVENTORY` |
| **inventory_db** | Intégration avec `type=inventory_db` et `config: { "schema": "X", "table": "Y" }` | Table ou vue `X.Y` |

Les deux modes permettent de piloter l’inventaire **uniquement via la base** (table/vue + éventuellement synonyme), sans déployer d’API externe.

---

### Intégration types existants

Les types `INVENTORY` et `INVENTORY_DB` existent déjà dans `IntegrationType` (integrations/models.py:24-26).

### Filtrage RBAC des targets

Implémenté dans `InventoryService.list_targets_for_user()` :
- **RM2** : Cumul des environnements autorisés depuis tous les profils
- **RM3/RM4** : Application des restrictions (PATTERN, LIST, ALL)
- **RM6** : Union des permissions de tous les profils de l'utilisateur

### API Endpoints

- `GET /api/v1/inventory/targets` — Liste avec filtrage RBAC
- `GET /api/v1/inventory/targets/all` — Liste sans RBAC (admin/intégration)

### Tests existants à ne pas casser

- Tests `profiles/tests/` : les permissions existantes fonctionnent
- Tests `integrations/tests/` : les types d'intégration ne changent pas

### Dépendances avec autres stories Epic 13

- **Story 13.2** utilisera `GET /api/v1/inventory/targets` dans le wizard d'exécution
- **Story 13.3** implémentera le filtrage RBAC complet
- **Story 13.5** utilisera les targets pour l'API self-service

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- Task 1: App Django `inventory` créée avec structure complète
- Task 2: Dataclass Target + constantes TargetEnvironment/TargetType (pas de table DB)
- Task 3: InventoryService avec résolution source et filtrage RBAC + sécurité SQL injection
- Task 4: Endpoints API avec views function-based, serializers + permission admin sur /all
- Task 5: Tests unitaires pour models, services et views + tests sécurité/erreurs
- Tasks 6-7: **SUPPRIMÉS** — Architecture simplifiée sans table locale
- **Code Review 2026-02-05**: 9 issues corrigées (2 CRIT, 3 HIGH, 3 MED, 1 LOW)

### File List

**Créés :**
- idp-portal/django_backend/inventory/__init__.py
- idp-portal/django_backend/inventory/admin.py
- idp-portal/django_backend/inventory/apps.py
- idp-portal/django_backend/inventory/models.py
- idp-portal/django_backend/inventory/serializers.py
- idp-portal/django_backend/inventory/services.py
- idp-portal/django_backend/inventory/urls.py
- idp-portal/django_backend/inventory/views.py
- idp-portal/django_backend/inventory/tests/__init__.py
- idp-portal/django_backend/inventory/tests/test_models.py
- idp-portal/django_backend/inventory/tests/test_services.py
- idp-portal/django_backend/inventory/tests/test_views.py

**Modifiés :**
- idp-portal/django_backend/idp_backend/settings.py (ajout 'inventory' à INSTALLED_APPS)
- idp-portal/django_backend/idp_backend/urls.py (ajout route /api/v1/inventory/)

## Change Log

- 2026-02-05: Implémentation initiale — architecture simplifiée sans table TARGETS locale
- 2026-02-05: **Code Review** — Corrections sécurité et robustesse :
  - CRIT-1 FIX: Validation SQL injection sur noms de table/synonym (regex whitelist)
  - CRIT-2 FIX: Permission `IsAdminOrIntegration` sur endpoint `/targets/all`
  - HIGH-1 FIX: Normalisation environnement (certif/certification → staging)
  - HIGH-2 CLARIFIED: Subtask 3.3 marqué DEFERRED (pas [x]) — placeholder jusqu'à API disponible
  - HIGH-3 FIX: Limite MAX_TARGETS_FOR_RBAC_FILTER (5000) + warning si dépassé
  - MED-1 FIX: Erreurs Oracle lèvent `InventoryServiceError` au lieu de retourner silencieusement []
  - MED-2 FIX: Validation et normalisation des valeurs d'environnement
  - MED-3 FIX: Tests ajoutés pour SQL injection, normalisation, permissions, erreurs 503
  - LOW-2 FIX: Warning log si utilisateur n'a pas de groupes AD
