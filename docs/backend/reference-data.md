# Données de référence — Reproductibilité entre environnements

Ce document décrit comment répliquer la configuration des données de référence (moteurs, intégrations) entre les différents environnements (dev, staging, production).

## Tables concernées

| Table | Champs clés | API lecture | API écriture |
|---|---|---|---|
| `REF_ENGINES` | `code`, `label`, `display_order`, `is_active`, `icon_url` | `GET /api/v1/reference/engines?active_only=false` | `PATCH /api/v1/admin/engines/{id}/` |
| `INTEGRATIONS` | `name`, `type`, `icon`, `is_active` | `GET /api/v1/admin/integrations/` | `PATCH /api/v1/admin/integrations/{id}/` |

## Option 1 : Django fixtures (recommandé pour déploiement initial)

### Export depuis l'environnement source

```bash
# Exporter les moteurs
python manage.py dumpdata reference.RefEngine --format=json --indent=2 > fixtures/ref_engines.json

# Exporter les intégrations
python manage.py dumpdata integrations.Integration --format=json --indent=2 > fixtures/integrations.json
```

### Import dans l'environnement cible

```bash
# Importer les moteurs
python manage.py loaddata fixtures/ref_engines.json

# Importer les intégrations
python manage.py loaddata fixtures/integrations.json
```

### Limitations

- `loaddata` utilise les PKs du fichier source — attention aux conflits si les séquences diffèrent entre envs.
- Préférer `--natural-primary` si les modèles supportent les clés naturelles.

## Option 2 : Export/Import via API REST

### Export (GET)

```bash
# Exporter les moteurs (tous, y compris inactifs)
curl -s -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/api/v1/reference/engines?active_only=false" \
  | jq '.' > engines_export.json

# Exporter les intégrations
curl -s -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/api/v1/admin/integrations/" \
  | jq '.' > integrations_export.json
```

### Import (PATCH en boucle)

```bash
# Importer les moteurs
for engine in $(jq -c '.[]' engines_export.json); do
  id=$(echo $engine | jq '.id')
  curl -s -X PATCH \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$engine" \
    "$TARGET_URL/api/v1/admin/engines/$id/"
done

# Même approche pour les intégrations
for integration in $(jq -c '.[]' integrations_export.json); do
  id=$(echo $integration | jq '.id')
  curl -s -X PATCH \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$integration" \
    "$TARGET_URL/api/v1/admin/integrations/$id/"
done
```

### Avantages

- Utilise les mêmes endpoints que l'interface Admin.
- Authentification et RBAC appliqués (requiert profil DBOPS).

### Limitations

- Le script utilise les PKs (`id`) pour construire les URLs PATCH — les moteurs doivent exister avec les mêmes IDs dans l'environnement cible.
- Alternative : utiliser le `code` comme clé de correspondance et résoudre l'ID via un GET préalable.

## Option 3 : Commande de management seed (à créer si besoin)

Si un seeding reproductible est nécessaire (CI/CD, environnement de test), créer une commande de management Django :

```bash
# Exemple — commande à implémenter dans reference/management/commands/seed_reference_engines.py
python manage.py seed_reference_engines
```

Cette commande devrait créer ou mettre à jour les entrées `REF_ENGINES` avec les valeurs par défaut (code, label, icon_url, display_order). Voir la [documentation Django sur les management commands](https://docs.djangoproject.com/en/5.2/howto/custom-management-commands/).

## Bonnes pratiques

1. **Versionner les fixtures** : commiter `fixtures/ref_engines.json` dans le dépôt pour traçabilité.
2. **Icônes en chemin relatif** : utiliser des chemins relatifs (`/static/icons/oracle.svg`) plutôt que des URLs absolues pour la portabilité entre envs.
3. **Vérifier après import** : utiliser l'onglet Admin > Moteurs pour vérifier visuellement les icônes et libellés après import.
4. **Intégrations** : même approche pour les icônes d'intégrations via l'onglet Admin > Intégrations.
