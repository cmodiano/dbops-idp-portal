# Configuration du mapping inventaire multi-tables

## Vue d'ensemble

Le système d'inventaire supporte deux modes de configuration :

1. **Multi-tables** : tables distinctes pour serveurs, instances et bases de données avec relations
2. **Table plate (fallback)** : une seule table avec colonnes NAME, ENVIRONMENT, TYPE

La configuration est stockée dans le champ `config` (JSON) de l'intégration de type `inventory_db`.

## Format multi-tables

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
        "server_ref": "SERVER_NAME",
        "db_ref": "DB_NAME"
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

### Champs de chaque entité

| Champ | Obligatoire | Description |
|-------|------------|-------------|
| `table` | Oui | Nom de la table/vue Oracle source |
| `id_column` | Non | Colonne identifiant unique |
| `columns` | Oui | Mapping concept métier → colonne réelle |

### Concepts métier disponibles

| Concept | Description | Utilisé par |
|---------|------------|-------------|
| `name` | Nom de l'entité | Toutes les entités |
| `environment` | Environnement (dev, staging, prod...) | Toutes les entités |
| `engine_type` | Type de moteur (Oracle, SQL Server...) | servers |
| `server_ref` | Référence au serveur parent | instances |
| `db_ref` | Référence à la base de données | instances |

## Format table plate (fallback)

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

En mode table plate :
- `_read_servers_from_config` filtre sur `TYPE=server`
- `_read_instances_from_config` retourne une liste vide
- `_read_databases_from_config` retourne une liste vide

## Sécurité

Tous les noms de tables et colonnes sont validés par des patterns regex stricts :

- **Tables** : `^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$` (supporte `SCHEMA.TABLE`)
- **Colonnes** : `^[A-Za-z_][A-Za-z0-9_]*$`

Toute valeur non conforme est rejetée avec un `MapperValidationError` et loggée avec `correlation_id`.

## Responsabilités RBAC

Les méthodes `list_instances` et `list_databases` sont des **helpers techniques** qui ne filtrent PAS par RBAC. La responsabilité du contrôle d'accès incombe à la couche API.

### Pattern d'utilisation sécurisé

```python
# CORRECT : la couche API valide d'abord les serveurs autorisés
# Étape 1 : Obtenir les serveurs autorisés pour cet utilisateur
allowed_servers, total, truncated = inventory.list_targets_for_user(
    user_id=user.id,
    ad_groups=user.ad_groups,
    environment='prod'
)

# Étape 2 : Vérifier que le server_name demandé est dans la liste autorisée
allowed_server_names = {s['name'] for s in allowed_servers}
if server_name not in allowed_server_names:
    raise PermissionDenied(f"User not allowed to access server {server_name}")

# Étape 3 : Maintenant on peut charger les instances/databases en sécurité
instances = inventory.list_instances(environment='prod', server_name=server_name)
databases = inventory.list_databases(environment='prod', server_name=server_name)

# INCORRECT : pas de validation RBAC préalable
instances = inventory.list_instances(environment, user_input_server)  # UNSAFE!
# ⚠️ Risque : n'importe quel utilisateur peut accéder aux instances de n'importe quel serveur
```

### Répartition des responsabilités

| Couche | Responsabilité |
|--------|---------------|
| `list_targets_for_user` | Filtre RBAC complet (LIST, PATTERN, ALL) sur les **serveurs** |
| `list_servers` | Lecture brute des serveurs par environnement |
| `list_instances` / `list_databases` | Lecture brute — **aucun filtre RBAC** |
| API layer (views) | Valider que `server_name` est dans la liste des serveurs autorisés avant d'appeler `list_instances`/`list_databases` |

### Détection multi-tables

`list_targets_for_user` détecte automatiquement la config multi-tables (via `InventoryMapper.is_multi_table`) et utilise `list_servers` au lieu de `list_targets` quand elle est active. La logique RBAC (LIST, PATTERN, ALL) est appliquée de la même manière dans les deux cas.

## Architecture

```
Integration.config (JSON)
    │
    ▼
InventoryMapper (inventory/mapper.py)
    ├── validate_config()      → Validation complète
    ├── build_select_clause()  → SELECT avec alias
    ├── build_where_clause()   → WHERE avec colonnes mappées
    └── get_column()           → Résolution concept → colonne
    │
    ▼
InventoryService (inventory/services.py)
    ├── list_servers()              → Méthode publique (AC1)
    ├── list_instances()            → Méthode publique, pas de RBAC (AC2)
    ├── list_databases()            → Méthode publique, pas de RBAC (AC3)
    ├── list_targets_for_user()     → RBAC, utilise list_servers si multi-tables (AC4)
    ├── _read_servers_from_config()
    ├── _read_instances_from_config()
    └── _read_databases_from_config()
```
