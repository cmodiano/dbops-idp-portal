# ADR-001 : Choix Django ORM vs SQL brut pour la couche données

**Date :** 2026-02-08
**Statut :** Accepté
**Décideurs :** Équipe IDP — Migration Epic M

## Contexte

Le backend FastAPI original utilisait des requêtes SQL brutes via `python-oracledb` avec des repositories manuels. La migration vers Django nécessitait de choisir entre :
1. Conserver le SQL brut (avec `python-oracledb` sous Django)
2. Migrer vers Django ORM
3. Utiliser un ORM tiers (SQLAlchemy)

Le projet utilise Oracle Database comme SGBD, avec des colonnes CLOB pour les champs JSON et des fonctionnalités Oracle-specific (JSON_VALUE, séquences, etc.).

## Décision

**Utiliser Django ORM comme couche d'accès principale aux données.** SQL brut réservé uniquement aux requêtes Oracle-specific (JSON_VALUE dans les clauses WHERE, fonctions d'agrégation Oracle-specific).

Concrètement :
- Modèles Django pour toutes les tables (`Action`, `Profile`, `AuditLog`, etc.)
- QuerySets avec `filter()`, `select_related()`, `prefetch_related()` pour les CRUD
- `cursor.execute()` avec bind variables nommés (`:param`) uniquement pour les requêtes impossibles en ORM
- Migrations Django pour les évolutions de schéma (complétées par Flyway pour les migrations Oracle-specific)

## Conséquences

### Positives
- Réduction dette technique significative : querysets lisibles vs SQL brut multi-lignes
- Protection automatique contre l'injection SQL
- Gestion automatique des connexions et transactions (`@transaction.atomic`)
- `select_related()` / `prefetch_related()` pour prévenir N+1 queries
- Migrations automatiques avec `makemigrations` / `migrate`
- Testabilité améliorée (SQLite in-memory pour les tests unitaires)

### Négatives
- N+1 queries à surveiller (3/10 stories Epic M corrigées)
- Performances potentiellement moindres pour requêtes complexes sur Oracle
- Certaines fonctionnalités Oracle (JSON_VALUE, CONNECT BY) nécessitent SQL brut
- Courbe d'apprentissage pour les développeurs habitués au SQL brut

### Neutres
- Le backend Oracle reste le même — seule la couche d'accès change
- Les migrations Flyway coexistent avec les migrations Django pour les cas Oracle-specific

## Alternatives Considérées

### Alternative 1 : Conserver SQL brut sous Django
- **Description :** Garder les repositories avec `python-oracledb` et SQL brut, sans utiliser les modèles Django
- **Raison du rejet :** Perte des avantages Django (admin, migrations, ORM), dette technique maintenue, pas de protection injection SQL automatique

### Alternative 2 : SQLAlchemy comme ORM
- **Description :** Utiliser SQLAlchemy (déjà mature avec Oracle) au lieu de Django ORM
- **Raison du rejet :** Stack cible est Django — ajouter SQLAlchemy crée une complexité et une dépendance supplémentaire incompatible avec l'écosystème Django (admin, DRF, migrations)

## Références

- [Notes migration ORM](../django-orm-migration-notes.md)
- [Notes migration DRF](../drf-api-migration-notes.md)
- Rétrospective Epic M — Issues N+1 queries (3/10 stories)
