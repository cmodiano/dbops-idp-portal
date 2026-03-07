# Guide de mapping inventaire — Normalisation engine_type

**Story 29.3** — Alignement REF_ENGINES ↔ engine_type inventaire

---

## 1. Contexte

Le portail IDP distingue **deux concepts** liés aux technologies de base de données :

| Concept | Source | Contexte | Exemple |
|---------|--------|----------|---------|
| **engine** (catalogue) | Table `REF_ENGINES` (V049) | Champ `Action.engine` — technologie DB ciblée par une action | `Oracle`, `SQL Server` |
| **engine_type** (inventaire) | Configuration `InventoryMapper` (source externe) | Attribut des cibles (serveurs/bases) dans l'inventaire | `oracle`, `sqlserver` |

Ces deux concepts partagent une **sémantique similaire** (type de technologie DB) mais opèrent dans des **contextes distincts** et ne sont **pas liés formellement** en base de données.

### Pourquoi pas de validation stricte ?

Le système est **volontairement découplé** pour les raisons suivantes :

1. **Sources externes multiples** — Les valeurs `engine_type` proviennent de sources d'inventaire variées (outils CMDB, fichiers CSV, APIs tierces) qui peuvent utiliser des conventions différentes.
2. **Flexibilité d'intégration** — Imposer une contrainte référentielle empêcherait l'ajout de sources avec des conventions non standard.
3. **Matching case-insensitive** — Le filtrage RBAC compare déjà en `UPPER()`, ce qui absorbe les différences de casse.
4. **Pas de blocage métier** — Une valeur `engine_type` non standard n'empêche pas le fonctionnement (l'accès aux cibles reste opérationnel).

---

## 2. Convention de normalisation recommandée

Lors de la configuration d'une source d'inventaire via `InventoryMapper`, les valeurs `engine_type` **devraient** suivre cette convention :

- **Minuscules** (`oracle`, pas `Oracle`)
- **Underscores pour les espaces** (`sql_server`, pas `SQL Server` ou `sqlserver`)
- **Alignement sur REF_ENGINES.CODE** quand possible

### Tableau de mapping REF_ENGINES.CODE → engine_type recommandé

| REF_ENGINES.CODE | engine_type recommandé | Transformation |
|------------------|----------------------|----------------|
| `Oracle` | `oracle` | Minuscules |
| `SQL Server` | `sql_server` | Minuscules + espace → underscore |
| `DB2` | `db2` | Minuscules |
| `PostgreSQL` | `postgresql` | Minuscules |
| `MySQL` | `mysql` | Minuscules |
| `Workflow` | `workflow` | Minuscules |

### Fonction de normalisation (référence)

```python
def normalize_engine_code(ref_engine_code: str) -> str:
    """Convertit REF_ENGINES.CODE → engine_type normalisé."""
    return ref_engine_code.lower().replace(' ', '_')
```

---

## 3. Configuration InventoryMapper avec engine_type

### 3.1 Mode multi-table (recommandé)

La configuration `InventoryMapper` permet de mapper la colonne source contenant le type de moteur vers le concept `engine_type` :

```json
{
  "entities": {
    "servers": {
      "table": "DBOPS_SERVERS",
      "id_column": "SERVER_ID",
      "columns": {
        "name": "HOSTNAME",
        "environment": "ENV",
        "engine_type": "ENGINE"
      }
    },
    "instances": {
      "table": "DBOPS_INSTANCES",
      "id_column": "INSTANCE_ID",
      "columns": {
        "name": "INSTANCE_NAME",
        "environment": "ENV",
        "server_ref": "SERVER_ID",
        "db_ref": "DB_ID"
      }
    },
    "databases": {
      "table": "DBOPS_DATABASES",
      "id_column": "DB_ID",
      "columns": {
        "name": "DB_NAME",
        "environment": "ENV"
      }
    }
  }
}
```

La colonne mappée vers `engine_type` (ici `ENGINE` dans `DBOPS_SERVERS`) sera exposée dans l'API inventaire. **Note :** Le filtrage par `engine_type` est pris en charge uniquement en mode multi-table. En mode `flat_table`, `_read_servers_flat_fallback()` ne filtre pas par `engine_type` ; les valeurs proviennent de la colonne mappée (ex. `TYPE`) mais le filtrage RBAC par engine_type ne s'applique qu'en mode multi-table.

**Table de jointure `instances` :** la table des instances fait le lien entre serveurs et bases. Elle contient typiquement `SERVER_ID` et `DB_ID` (ou des colonnes de type nom). Les concepts `server_ref` et `db_ref` dans la config mappent vers ces colonnes ; le portail les utilise pour les jointures et pour filtrer (ex. toutes les instances d’un serveur donné).

### 3.2 Mode une seule table (flat_table)

Si votre inventaire est dans une seule table avec colonnes `NAME`, `ENVIRONMENT`, `TYPE` :

**Limitation :** Le filtrage par `engine_type` n'est pas supporté en mode `flat_table` ; il est uniquement disponible en mode multi-table (via `query_executor._read_entity_from_config` et `mapper.build_where_clause`).

```json
{
  "flat_table": {
    "table": "DBOPS_INVENTORY",
    "columns": {
      "name": "NAME",
      "environment": "ENVIRONMENT",
      "type": "TYPE"
    }
  }
}
```

Adaptez les noms de table et colonnes à votre schéma. Le formulaire « Nouvelle intégration » propose des boutons « Exemple multi-table » et « Exemple une table » pour insérer ces modèles.

### 3.3 Requête SQL générée

Avec la configuration multi-table ci-dessus (section 3.1), `InventoryMapper.build_select_clause('servers')` produit :

```sql
SELECT SERVER_ID AS id, HOSTNAME AS name, ENV AS environment, ENGINE AS engine_type
FROM DBOPS_SERVERS
```

### 3.4 Responsabilité de la normalisation

Les valeurs `engine_type` retournées dépendent **directement** du contenu de la colonne mappée vers `engine_type` (en mode multi-table, par ex. `ENGINE` ; en mode `flat_table`, souvent `TYPE`). La normalisation est la **responsabilité de l'administrateur d'intégration** lors de la configuration :

- **Option A (recommandée)** — S'assurer que la colonne source contient des valeurs normalisées (`oracle`, `sql_server`, etc.).
- **Option B** — Créer une vue SQL qui normalise les valeurs avant exposition.
- **Option C** — Accepter les valeurs telles quelles (le matching case-insensitive absorbe les différences de casse).

### 3.5 Exemple : vue SQL de normalisation

Si la source utilise des formats différents (ex. `MSSQL`, `ORA`, `MS SQL Server`), l'administrateur peut créer une vue :

```sql
CREATE VIEW V_INVENTORY_SERVERS AS
SELECT
    SERVER_ID,
    HOSTNAME,
    ENV,
    CASE UPPER(ENGINE)
        WHEN 'ORACLE' THEN 'oracle'
        WHEN 'ORA' THEN 'oracle'
        WHEN 'SQL SERVER' THEN 'sql_server'
        WHEN 'MSSQL' THEN 'sql_server'
        WHEN 'MS SQL SERVER' THEN 'sql_server'
        WHEN 'DB2' THEN 'db2'
        WHEN 'POSTGRESQL' THEN 'postgresql'
        WHEN 'POSTGRES' THEN 'postgresql'
        WHEN 'MYSQL' THEN 'mysql'
        ELSE LOWER(REPLACE(ENGINE, ' ', '_'))
    END AS ENGINE
FROM DBOPS_SERVERS;
```

Puis configurer `InventoryMapper` pour pointer vers la vue au lieu de la table directe.

---

## 4. Utilisation dans l'API

### 4.1 API inventaire

```
GET /api/v1/inventory/servers/?engine_type=oracle
```

Filtre les serveurs dont `engine_type` correspond (case-insensitive via `UPPER()`).

### 4.2 API référence engines

```
GET /api/v1/reference/engines?active_only=true
```

Retourne la liste des moteurs de référence (`REF_ENGINES`). Ces codes sont la **source de vérité** pour les valeurs `engine_type` recommandées.

Réponse :

```json
[
  {
    "code": "Oracle",
    "label": "Oracle",
    "is_active": true,
    "normalized_code": "oracle"
  },
  {
    "code": "SQL Server",
    "label": "SQL Server",
    "is_active": true,
    "normalized_code": "sql_server"
  },
  {
    "code": "DB2",
    "label": "DB2",
    "is_active": true,
    "normalized_code": "db2"
  },
  {
    "code": "PostgreSQL",
    "label": "PostgreSQL",
    "is_active": true,
    "normalized_code": "postgresql"
  },
  {
    "code": "MySQL",
    "label": "MySQL",
    "is_active": true,
    "normalized_code": "mysql"
  },
  {
    "code": "Workflow",
    "label": "Workflow",
    "is_active": true,
    "normalized_code": "workflow"
  }
]
```

Le champ `normalized_code` retourne directement la valeur recommandée pour `engine_type` (Story 29.3).

---

## 5. Utilisation dans les profils RBAC

Le champ `filter_by_attribute_json` des profils cibles (`ProfileTargetPermission`) peut filtrer par `engine_type` :

```json
{
  "engine_type": ["oracle", "sql_server"]
}
```

Le matching est **case-insensitive** : `"Oracle"`, `"oracle"`, `"ORACLE"` correspondent tous.

Pour plus de détails, voir [rbac-filter-by-attribute.md](../backend/rbac-filter-by-attribute.md).

---

## 6. Ajouter un nouveau moteur

Pour ajouter un nouveau moteur au système :

1. **REF_ENGINES** — Insérer via l'admin ou migration SQL :
   ```sql
   INSERT INTO REF_ENGINES (CODE, LABEL, DISPLAY_ORDER, IS_ACTIVE)
   VALUES ('CosmosDB', 'Azure Cosmos DB', 7, 1);
   ```

2. **Inventaire** — S'assurer que la source d'inventaire expose la valeur normalisée (`cosmosdb`) dans la colonne mappée à `engine_type`.

3. **Profils RBAC** — Mettre à jour les profils `filter_by_attribute_json` si nécessaire :
   ```json
   {"engine_type": ["oracle", "cosmosdb"]}
   ```

---

## 7. Références

- **Glossaire IDP Portal :** [glossary.md](../reference/glossary.md) — Définitions formelles engine vs engine_type
- **Filtres RBAC par attribut :** [rbac-filter-by-attribute.md](../backend/rbac-filter-by-attribute.md) — Détails filtrage engine_type dans profils
- **Rapport technique :** [rapport-bases-moteurs-technologies-integrations.md](../integrations/rapport-bases-moteurs-technologies-integrations.md) — Analyse complète des concepts
- **Migration V049 :** `idp-portal/database/migrations/V049__create_ref_engines.sql` (dépôt) — Création table REF_ENGINES avec valeurs initiales (Oracle, SQL Server, DB2, PostgreSQL, MySQL, Workflow)
- **InventoryMapper :** `django_backend/inventory/mapper.py` — Mapping colonnes source → concepts business

## 8. Exemples de valeurs problématiques

### ❌ Valeurs à éviter

| Valeur problématique | Pourquoi c'est mauvais | Valeur recommandée |
|---------------------|----------------------|-------------------|
| `ORACLE` | Majuscules — incohérent avec convention | `oracle` |
| `SQL Server` | Espaces — difficile à parser, casse mixte | `sql_server` |
| `sqlserver` | Pas d'underscore — incohérent avec "SQL Server" REF_ENGINES | `sql_server` |
| `MSSQL` | Acronyme non standard — pas dans REF_ENGINES | `sql_server` |
| `MS SQL Server` | Trop verbeux, espaces | `sql_server` |
| `db2-luw` | Tirets au lieu d'underscores | `db2` (ou `db2_luw` si distinction nécessaire) |

### ✅ Pourquoi la normalisation est importante

1. **Cohérence RBAC** — Les profils utilisent les mêmes valeurs que l'inventaire
2. **Documentation claire** — Les développeurs savent quelles valeurs utiliser
3. **Maintenance facile** — Pas de surprises avec "Oracle" vs "oracle" vs "ORACLE"
4. **Frontend prévisible** — Les listes déroulantes affichent des valeurs cohérentes
