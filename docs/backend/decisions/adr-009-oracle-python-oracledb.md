# ADR-009 : Oracle Database — python-oracledb en Mode Thin

**Date :** 2024-06-01
**Statut :** Accepté
**Décideurs :** Équipe IDP Portal, DBA Desjardins

## Contexte

Le portail IDP est déployé dans le contexte d'entreprise Desjardins. Oracle Database est
le SGBD imposé par les équipes DBA — aucun autre moteur de base de données n'est disponible
dans l'environnement de production. Les contraintes incluent Oracle 19c, des règles de
nommage UPPER_SNAKE_CASE pour les colonnes, et l'absence de `JSONField` natif supporté par
Django pour Oracle 19c.

Ce document complète **ADR-001** (ORM Django vs SQL brut) et **ADR-004** (gestion des
champs JSON Oracle) en documentant les décisions spécifiques à la couche pilote et aux
conventions Oracle.

## Décision

### 1. Driver : python-oracledb 3.4.1 en mode Thin

`python-oracledb` (successeur officiel de `cx_Oracle`) est utilisé en **mode Thin** — sans
client Oracle Instant Client sur les machines de développement ou de déploiement. La
configuration dans `settings.py` utilise `django.db.backends.oracle` avec les variables
d'environnement :

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.oracle',
        'NAME': ORACLE_DSN,   # os.getenv('ORACLE_DSN', 'localhost:1521/FREEPDB1')
        'USER': ORACLE_USER,
        'PASSWORD': ORACLE_PASSWORD,
        'CONN_MAX_AGE': DB_CONN_MAX_AGE,
        'CONN_HEALTH_CHECKS': DB_CONN_HEALTH_CHECKS,
    }
}
```

Le mode Thick (avec client Oracle) est disponible via la variable
`ORACLE_CLIENT_LIB` pour les cas nécessitant `TIMESTAMP WITH TIME ZONE` (DPY-3022).

### 2. OracleJSONField pour les données JSON (`core/fields.py`)

Oracle 19c ne supporte pas `JSONField` natif de Django. Les données JSON sont stockées
dans des colonnes `CLOB`. `OracleJSONField` (héritant de `models.TextField`) gère la
sérialisation/désérialisation transparente :

- **`from_db_value`** : désérialise le CLOB JSON en `dict`/`list` Python après `SELECT`
- **`get_prep_value`** : sérialise `dict`/`list` en chaîne JSON avant `INSERT`/`UPDATE`
- Mode permissif pour les données corrompues (retourne `None` avec log `WARNING`)

*Voir ADR-004 pour le détail de ce champ.*

### 3. Conventions booléens : `NUMBER(1)` et comparaison explicite

Oracle ne possède pas de type booléen natif. Les champs booléens sont stockés en
`NUMBER(1)` (0 ou 1). **Règle critique** : toujours comparer avec `== 1`, jamais en
truthiness, car Oracle peut retourner des entiers ou des décimaux selon le contexte.

```python
# Correct
return any(getattr(p, 'is_auditor', 0) == 1 for p in profiles)

# Incorrect (risque de faux-négatif avec des types Oracle)
return any(p.is_auditor for p in profiles)
```

Les modèles exposent des propriétés `_bool` pour une utilisation sûre en Python :
```python
@property
def is_admin_bool(self) -> bool:
    return self.is_admin == 1
```

### 4. Nommage : UPPER_SNAKE_CASE en base, snake_case en Python

Les colonnes Oracle suivent la convention UPPER_SNAKE_CASE imposée par les DBA.
Django utilise `db_column` pour le mapping explicite :

```python
class User(AbstractBaseUser):
    username   = models.CharField(max_length=255, db_column='USERNAME')
    is_active  = models.BooleanField(default=True, db_column='IS_ACTIVE')
    created_at = models.DateTimeField(db_column='CREATED_AT')
```

Toutes les colonnes de toutes les tables mappent explicitement via `db_column` dans
les `Meta` des modèles.

### 5. Pool de connexions

Django `CONN_MAX_AGE` gère la persistance des connexions par worker. Les variables
d'environnement :

- `ORACLE_DB_HOST` / `ORACLE_DB_PORT` / `ORACLE_DB_SERVICE_NAME` : composants du DSN
- `ORACLE_DSN` : DSN complet (format `host:port/service`)
- `DB_CONN_MAX_AGE` : durée de persistance (par défaut : 0 en dev, 60s en production)
- `DB_CONN_HEALTH_CHECKS` : validation des connexions avant réutilisation

### 6. Migrations

Les migrations Django standard sont utilisées pour les modifications de schéma post-initialisation.
L'état initial du schéma (`V001-V035`) provient de scripts SQL legacy exécutés lors du
premier déploiement. `OracleJSONField` fonctionne comme un `TextField` standard pour les
migrations — aucune migration custom n'est requise pour ce champ.

## Conséquences

### Positives
- Mode Thin : pas d'Oracle Instant Client à installer (simplification déploiement CI/CD et dev)
- `OracleJSONField` transparent pour le code applicatif — même interface que `JSONField` Django
- Convention `db_column` UPPER_SNAKE_CASE : compatibilité avec le schéma Oracle existant
- Django ORM complet disponible (requêtes, relations, migrations)

### Négatives
- Mode Thin : certaines fonctionnalités Oracle avancées requièrent le mode Thick
  (`TIMESTAMP WITH TIME ZONE` → DPY-3022 en mode Thin)
- `OracleJSONField` ne supporte pas les requêtes JSON natives Oracle (pas de `JSONQuery`)
- Comparaisons booléens `== 1` : convention non-standard, source de bugs si non respectée

### Neutres
- Les migrations Oracle génèrent parfois des noms de contraintes longs (Oracle 30-char limit) —
  géré par Django depuis la version 4.2

## Alternatives Considérées

### Alternative 1 : PostgreSQL

- **Description :** SGBD open source avec support natif `JSONField`, booléens, etc.
- **Raison du rejet :** Non disponible dans l'environnement d'entreprise Desjardins.

### Alternative 2 : cx_Oracle

- **Description :** Pilote Oracle précédent, nécessitant Oracle Instant Client
- **Raison du rejet :** Déprécié officiellement en faveur de `python-oracledb`. Mode Thin
  de `python-oracledb` élimine la dépendance au client Oracle.

### Alternative 3 : SQLite pour le développement local

- **Description :** SQLite comme base de dev, Oracle uniquement en production
- **Raison du rejet :** Différences de comportement trop importantes (types, contraintes,
  booléens). Risque de bugs masqués. Tous les environnements utilisent Oracle.

## Références

- `core/fields.py` — `OracleJSONField`
- `core/permissions.py:100` — Commentaire sur `NUMBER(1)` et `== 1`
- `idp_auth/models.py` — Mapping `db_column` UPPER_SNAKE_CASE
- `idp_backend/settings.py:215-246` — Configuration DATABASES Oracle
- ADR-001 — Django ORM vs SQL brut
- ADR-004 — Gestion champs JSON Oracle (détail `OracleJSONField`)
- Story 17.4 — Introduction `OracleJSONField`
- [python-oracledb documentation](https://python-oracledb.readthedocs.io/)
