# Stratégie de cache — IDP Portal

## Vue d'ensemble

Le portail IDP utilise des caches in-memory au niveau module via `cachetools.TTLCache`.
Ces caches sont **per-worker** : chaque processus Gunicorn possède sa propre instance.

## Caches actuels

| Cache | Fichier | TTL | maxsize | Données |
|-------|---------|-----|---------|---------|
| `_catalog_cache` | `catalog/views.py` | 300s (5 min) | 1000 | Réponses catalogue paginées |
| `_tags_cache` | `catalog/views.py` | 300s (5 min) | 200 | Liste des tags catalogue |
| `_environments_cache` | `inventory/services.py` | 300s (5 min) | 1 | Liste des environnements |

## Comportement per-worker

### Pourquoi per-worker (et non Redis partagé)

- **Simplicité opérationnelle** : pas de dépendance Redis pour le cache applicatif
- **Performance** : accès mémoire locale (~0ms) vs réseau Redis (~2-5ms)
- **Résilience** : pas de SPOF sur le cache
- **Données non-critiques** : catalogue, tags et environnements sont des données de référence
  qui changent rarement

### Limites acceptées

- **Incohérence temporaire entre workers** : après une mise à jour du catalogue, un worker
  peut servir des données stale pendant ≤5 minutes. Acceptable car :
  - Les modifications catalogue sont rares (<10/heure en moyenne)
  - L'invalidation est déjà gérée : chaque mutation (create/update/delete) appelle
    `_catalog_cache.clear()` et `_tags_cache.clear()` sur le worker local
  - Les autres workers voient la mise à jour après expiration du TTL (5 min max)

- **Warm-up progressif** : au redémarrage d'un worker, le cache est vide. Les premières
  requêtes touchent la base de données, puis le cache se remplit progressivement.

- **Mémoire** : chaque worker consomme de la mémoire pour son cache.
  Impact estimé : ~10-50 Mo par worker selon la taille du catalogue.

## Invalidation

Les caches sont invalidés **localement** (sur le worker qui traite la requête de mutation) :
- `catalog/views.py` : `_catalog_cache.clear()` et `_tags_cache.clear()` appelés dans
  chaque méthode de mutation (create, update, delete, publish, disable, etc.)
- `inventory/services.py` : `_environments_cache` expire par TTL

## Évolution future (Phase 2)

Si l'incohérence inter-workers devient problématique (ex. : haute fréquence de modifications
catalogue, exigence de cohérence immédiate), migrer vers Redis :

1. Installer `django-redis` et configurer `CACHES` dans `settings.py`
2. Remplacer `cachetools.TTLCache` par `django.core.cache.cache` (get/set)
3. L'invalidation sera automatiquement partagée entre tous les workers

Cette migration est prévue mais non prioritaire pour le MVP.
