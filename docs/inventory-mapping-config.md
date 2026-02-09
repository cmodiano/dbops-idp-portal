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
    ├── _read_servers_from_config()
    ├── _read_instances_from_config()
    └── _read_databases_from_config()
```
