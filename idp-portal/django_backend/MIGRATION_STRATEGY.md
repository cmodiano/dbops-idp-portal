# Stratégie de Migration Flyway → Django

> **📦 Document d'archivage — Migration terminée**  
> Ce document est conservé pour référence historique. La migration FastAPI→Django est complète (février 2026).  
> Voir [MIGRATION_ARCHIVE.md](../docs/MIGRATION_ARCHIVE.md) pour accéder au code FastAPI archivé.

## Contexte

Cette documentation décrit la stratégie de migration des migrations Flyway vers Django migrations pour le projet IDP Portal.

**Date:** 2026-02-03  
**Story:** m-2-modeles-django-et-migrations-schema-oracle
**Status:** Migration terminée — Document historique conservé

## État Actuel

- **Schéma Oracle:** Créé et géré via Flyway migrations (V001-V041+)
- **Tables existantes:** Toutes les tables Oracle existent déjà en production
- **Django:** Nouveau projet Django 5.2.11 avec modèles ORM mappés sur le schéma Oracle existant

## Décision: Cohabitation Temporaire puis Bascule

### Phase 1: Cohabitation (Actuelle)

**Durée:** Jusqu'à la fin de la migration FastAPI → Django (Epic M)

**Stratégie:**
- Flyway continue de gérer le schéma Oracle existant
- Django migrations sont créées mais marquées comme appliquées avec `--fake initial`
- Les modèles Django mappent le schéma Oracle existant sans le modifier
- Aucun changement de schéma via Django migrations pendant cette phase

**Avantages:**
- Pas de risque de conflit entre Flyway et Django
- Migration progressive sans interruption
- Rollback facile si nécessaire

**Inconvénients:**
- Deux systèmes de migration en parallèle (complexité temporaire)
- Nécessite coordination pour éviter les conflits

### Phase 2: Bascule vers Django Migrations

**Déclencheur:** Fin de l'Epic M (migration FastAPI → Django complète)

**Stratégie:**
1. Arrêter toutes les nouvelles migrations Flyway
2. Marquer la dernière migration Flyway comme référence (ex: V041)
3. Tous les futurs changements de schéma via Django migrations uniquement
4. Documenter la version Flyway de référence dans `settings.py` ou un fichier de configuration

**Processus de bascule:**
1. Créer une migration Django initiale qui référence la dernière version Flyway
2. Exécuter `python manage.py migrate --fake-initial` sur tous les environnements
3. Vérifier que tous les modèles Django peuvent lire/écrire les données existantes
4. Mettre à jour la documentation pour indiquer que Django migrations prend le relais

## Création des Migrations Django Initiales

### Étape 1: Générer les migrations

```bash
cd idp-portal/django_backend
source venv/bin/activate  # ou venv\Scripts\activate sur Windows
python manage.py makemigrations
```

Cette commande génère les migrations initiales pour toutes les apps:
- `idp_auth/migrations/0001_initial.py` (User model)
- `catalog/migrations/0001_initial.py` (Action, Tag, ActionTag, UserFavorite models)
- `profiles/migrations/0001_initial.py` (Profile, ProfileActionPermission, ProfileTargetPermission models)
- `integrations/migrations/0001_initial.py` (Integration model)
- `executions/migrations/0001_initial.py` (Execution, ExecutionStep, ScheduledExecution, RecurringPattern models)
- `core/migrations/0001_initial.py` (AuditLog model)

### Étape 2: Vérifier les migrations générées

Vérifier que les migrations générées correspondent au schéma Oracle existant:
- Noms de tables en UPPERCASE (`Meta.db_table`)
- Noms de colonnes en UPPERCASE (`db_column`)
- Types de données compatibles (CharField → VARCHAR2, TextField → CLOB, etc.)
- Relations ForeignKey correctes avec `on_delete` approprié
- Contraintes CHECK représentées par `choices` dans les modèles

### Étape 3: Appliquer les migrations avec --fake-initial

**IMPORTANT:** Les tables Oracle existent déjà. Ne pas créer les tables, seulement marquer les migrations comme appliquées.

```bash
# Sur un schéma Oracle de dev/test
python manage.py migrate --fake-initial

# Ou pour une app spécifique
python manage.py migrate idp_auth --fake-initial
python manage.py migrate catalog --fake-initial
python manage.py migrate profiles --fake-initial
python manage.py migrate integrations --fake-initial
python manage.py migrate executions --fake-initial
python manage.py migrate core --fake-initial
```

**Vérification après --fake-initial:**
```bash
python manage.py showmigrations
```

Toutes les migrations doivent être marquées `[X]` (appliquées).

### Étape 4: Valider la compatibilité

1. **Lecture des données existantes:**
   ```python
   from idp_auth.models import User
   from catalog.models import Action
   
   # Vérifier que les modèles peuvent lire les données Oracle
   users = User.objects.all()
   actions = Action.objects.all()
   ```

2. **Écriture de nouvelles données:**
   ```python
   # Créer un nouvel utilisateur
   user = User.objects.create(
       username='testuser',
       profile='DBA'
   )
   ```

3. **Relations ForeignKey:**
   ```python
   # Vérifier que les relations fonctionnent
   action = Action.objects.first()
   if action.created_by:
       print(action.created_by.username)
   ```

4. **Champs JSON (CLOB):**
   ```python
   # Vérifier que les helpers JSON fonctionnent
   action = Action.objects.first()
   schema = action.get_parameters_schema()
   action.set_parameters_schema({'type': 'object'})
   action.save()
   ```

## Gestion des Champs CLOB/JSON

### Choix Technique: TextField + Helpers

**Décision:** Utiliser `TextField` avec méthodes helper pour sérialiser/désérialiser JSON plutôt que `JSONField` natif.

**Raison:**
- Django 5.2+ supporte `JSONField` avec Oracle backend, mais nécessite `oracledb` en mode Thick (client Oracle requis)
- Le projet utilise `oracledb` en mode Thin (pas de client Oracle)
- `TextField` + helpers JSON offre plus de contrôle et compatibilité

**Implémentation:**
Chaque modèle avec champs CLOB JSON a des méthodes helper:
- `get_field_name()`: Désérialise JSON depuis CLOB
- `set_field_name(value)`: Sérialise JSON vers CLOB

**Exemple:**
```python
action = Action.objects.get(id=1)
schema = action.get_parameters_schema()  # Retourne dict Python
action.set_parameters_schema({'type': 'object'})  # Sérialise vers CLOB
action.save()
```

## Contraintes et Index Oracle

### Contraintes CHECK

Les contraintes CHECK Oracle sont représentées par:
- `models.TextChoices` ou `models.IntegerChoices` pour les enums
- `choices` dans les champs `CharField` ou `IntegerField`

**Note:** Les contraintes CHECK Oracle restent actives côté base de données. Django valide également côté application pour une meilleure UX.

### Index

Les index Oracle existants sont préservés. Django ne crée pas d'index supplémentaires sauf si explicitement définis dans `Meta.indexes`.

**Index critiques préservés:**
- Index sur colonnes ForeignKey (créés automatiquement par Oracle)
- Index sur colonnes fréquemment utilisées en WHERE (STATUS, CREATED_AT, etc.)
- Index composites pour requêtes complexes

## Colonnes IDENTITY (Auto-increment)

Oracle utilise `GENERATED ALWAYS AS IDENTITY` pour les colonnes auto-increment.

**Mapping Django:**
- `models.BigAutoField()` pour les clés primaires
- `db_column='ID'` pour mapper vers la colonne Oracle

**Note:** Django gère automatiquement les valeurs IDENTITY lors de l'insertion.

## Relations ForeignKey

### Mapping Oracle → Django

- **Oracle:** `FOREIGN KEY (CREATED_BY) REFERENCES USERS(ID)`
- **Django:** `models.ForeignKey(User, on_delete=models.SET_NULL, db_column='CREATED_BY')`

### on_delete Strategies

- `CASCADE`: Supprime les enregistrements enfants (ex: ExecutionStep → Execution)
- `SET_NULL`: Met à NULL si parent supprimé (ex: Action → User.created_by)
- `PROTECT`: Empêche la suppression si enfants existent (non utilisé dans ce schéma)

## Version de Référence Flyway

**Dernière migration Flyway avant bascule:** V041

**Date de bascule prévue:** Après complétion de l'Epic M (migration FastAPI → Django)

## Checklist de Validation

Avant de marquer cette story comme complète:

- [x] Tous les modèles Django créés pour toutes les tables Oracle
- [x] Migrations Django initiales générées (`makemigrations`)
- [x] Migrations appliquées avec `--fake-initial` sur schéma de dev
- [x] Tests unitaires créés pour tous les modèles
- [x] Tests de lecture/écriture des données Oracle existantes passent
- [x] Tests de sérialisation JSON (CLOB) passent
- [x] Tests de relations ForeignKey passent
- [x] Documentation de stratégie de migration créée
- [ ] Validation sur schéma Oracle de production (staging d'abord)

## Prochaines Étapes

1. **Story M.3:** Couche données repositories vers ORM Django
2. **Story M.4:** API REST catalogue et admin actions/tags
3. **Story M.5:** API REST profils et permissions
4. **...** (autres stories de l'Epic M)

Une fois l'Epic M complété, procéder à la bascule définitive vers Django migrations uniquement.

## Références

- [Django Oracle Backend Documentation](https://docs.djangoproject.com/en/5.2/ref/databases/#oracle-notes)
- [Django Migrations Documentation](https://docs.djangoproject.com/en/5.2/topics/migrations/)
- [Flyway Migrations](../database/migrations/)
- Story M.1: Bootstrap projet Django et DRF
- Story M.2: Modèles Django et migrations (schéma Oracle existant)
