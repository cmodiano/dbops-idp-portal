# RBAC — Filtres par attribut d'inventaire

**Story 23.4** — Backend RBAC profils filtrés par attribut

## Concept

Les filtres par attribut permettent de restreindre l'accès d'un profil à un sous-ensemble de serveurs basé sur les **attributs mappés de l'inventaire** (ex. `engine_type`, `zone`), sans lister manuellement chaque serveur.

Cela permet de créer des profils dynamiques comme :
- "Tous les serveurs Oracle" → `{"engine_type": ["oracle"]}`
- "Tous les serveurs SQL en production" → `{"engine_type": ["sqlserver"], "zone": ["prod"]}`

Le filtre est stocké dans le champ `FILTER_BY_ATTRIBUTE_JSON` (CLOB) de la table `PROFILE_TARGET_PERMISSIONS`.

## Format JSON

```json
{
  "engine_type": ["oracle", "sqlserver"],
  "zone": ["prod"]
}
```

- **Clés** : concepts métier définis dans la config InventoryMapper (`entities.servers.columns`), stables et indépendants des colonnes Oracle réelles.
- **Valeurs** : listes non vides de strings (comparaison case-insensitive).

## Exemples de profils

### Tous les serveurs Oracle

```json
{
  "targets_type": "all",
  "filter_by_attribute": {
    "engine_type": ["oracle"]
  }
}
```

Résultat : l'utilisateur ne voit que les serveurs où `engine_type = "oracle"`.

### Tous les serveurs SQL en production

```json
{
  "targets_type": "all",
  "filter_by_attribute": {
    "engine_type": ["sqlserver"],
    "zone": ["prod"]
  }
}
```

Résultat : serveurs SQL Server **ET** zone prod (AND entre attributs).

### Liste restreinte + filtre

```json
{
  "targets_type": "list",
  "target_names": ["srv01", "srv02", "srv03", "srv04"],
  "filter_by_attribute": {
    "engine_type": ["oracle"]
  }
}
```

Résultat : parmi srv01-04, seuls ceux qui sont Oracle.

## Comportement cumulatif

### Au sein d'un profil (AND)

Tous les critères d'un filtre doivent être satisfaits simultanément :

```json
{"engine_type": ["oracle"], "zone": ["prod"]}
```

→ Oracle **ET** prod uniquement.

### Entre profils (OR)

Les résultats de chaque profil sont combinés par union :

- Profil A : `{"engine_type": ["oracle"]}`
- Profil B : `{"engine_type": ["sqlserver"]}`

→ L'utilisateur voit Oracle **OU** SQL Server.

Si **un seul profil** n'a aucun filtre attribut, ses cibles passent sans restriction (ce profil ne filtre rien).

## Ordre d'application

```
1. permission_type (LIST / PATTERN / ALL)
       ↓
2. Restriction par environnement (action_permissions.environments)
       ↓
3. Restriction par cibles (target_names / target_patterns)
       ↓
4. filter_by_attribute (filtre additionnel sur les attributs mappés)
       ↓
5. Union entre profils (OR)
```

Le filtre attribut **affine** le résultat de l'étape précédente, il ne le remplace pas.

## Validation des clés (API)

Lors de la sauvegarde via l'API (`PUT /admin/profiles/{id}/targets`), les clés du filtre sont validées contre `InventoryMapper.get_available_concepts('servers')`.

- Clé valide → sauvegarde OK
- Clé invalide → `400 Bad Request` avec message :

```
Invalid filter attributes: bad_key. Valid attributes: name, environment, engine_type, zone
```

Les concepts valides dépendent de la configuration multi-tables de l'inventaire. En mode fallback (table plate), les concepts par défaut sont : `name`, `environment`, `type`.

## Edge cases

| Cas | Comportement |
|-----|-------------|
| `filter_by_attribute = null` | Pas de filtrage (standard LIST/PATTERN/ALL) |
| `filter_by_attribute = {}` | Pas de filtrage |
| JSON malformé en DB | Log ERROR, filtre ignoré, pas de crash |
| Attribut absent des données serveur | Log WARNING, critère ignoré (pas tout le filtre) |
| Tous serveurs exclus par filtre | Retourne liste vide `[]` |
| LIST + filter | Applique d'abord LIST, puis filtre attribut |
| ALL + filter | Récupère tous serveurs, puis filtre attribut |
| Erreur d'application du filtre | Log ERROR, filtre ignoré, dégradation gracieuse |

## Principe de dégradation gracieuse

Les erreurs liées aux filtres attribut ne bloquent **jamais** l'authentification ni l'accès aux cibles. En cas d'erreur :

1. L'erreur est loguée (ERROR ou WARNING selon gravité)
2. Le filtre défaillant est ignoré
3. Les cibles sont retournées comme si le filtre n'existait pas

## Fichiers concernés

| Fichier | Modification |
|---------|-------------|
| `profiles/models.py` | Champ `filter_by_attribute_json` + helpers `get/set_filter_by_attribute()` |
| `profiles/serializers.py` | Champ `filter_by_attribute` + validation `validate_filter_by_attribute()` |
| `profiles/services.py` | Gestion du champ dans `set_target_permissions()` |
| `inventory/mapper.py` | `get_available_concepts()` statique |
| `inventory/services.py` | `_apply_attribute_filter()` + `_apply_attribute_filters_across_profiles()` |
| `profiles/migrations/0002_add_filter_by_attribute.py` | Migration Django |

## Logging structlog

| Event | Niveau | Description |
|-------|--------|-------------|
| `rbac_filter_by_attribute_applied` | INFO | Filtre appliqué avec nb_servers_before/after |
| `rbac_filter_attribute_not_found` | WARNING | Attribut absent des données serveur |
| `rbac_filter_by_attribute_error` | ERROR | Erreur lors de l'application du filtre |
| `profile_filter_by_attribute_validated` | INFO | Validation API réussie |
