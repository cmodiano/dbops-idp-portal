# Guide Mypy pour Développeurs

## Pourquoi mypy ?

- **Détection de bugs** : erreurs de type détectées avant l'exécution (None inattendu, mauvais types)
- **Auto-completion IDE** : meilleure suggestion de méthodes et attributs
- **Refactoring sûr** : les changements de signature sont vérifiés partout
- **Documentation vivante** : les annotations de type documentent les contrats d'API

## Exécuter mypy localement

```bash
cd django_backend

# Vérifier les types (utilise pyproject.toml)
source .venv/bin/activate
mypy .

# Vérifier par rapport au baseline (comme en CI)
scripts/check_mypy_baseline.sh

# Mettre à jour le baseline après corrections
scripts/generate_mypy_baseline.sh
```

## Interpréter les erreurs mypy

### Erreurs courantes

| Erreur | Cause | Solution |
|--------|-------|----------|
| `error: Returning Any` | Fonction retourne un type non typé | Ajouter annotation de retour ou cast |
| `error: Need type annotation` | Variable sans type explicite | Ajouter annotation : `x: list[str] = []` |
| `error: has no attribute` | Accès à un attribut inexistant | Vérifier le type de l'objet |
| `error: Incompatible types` | Mauvais type passé | Corriger le type ou ajouter un cast |
| `error: arg-type` | Argument de mauvais type | Vérifier la signature de la fonction |

### Ignorer une erreur spécifique

Si une erreur est un faux positif, vous pouvez l'ignorer avec un commentaire :

```python
result = some_dynamic_call()  # type: ignore[no-any-return]
```

Utilisez toujours le code d'erreur spécifique (pas juste `# type: ignore`).

## Ajouter des annotations de type

### Fonctions

```python
def get_user(user_id: int) -> User | None:
    ...

def process_items(items: list[str], *, verbose: bool = False) -> dict[str, int]:
    ...
```

### Patterns Django courants

```python
from django.db import models
from django.db.models import QuerySet

class ActionManager(models.Manager["Action"]):
    def active(self) -> QuerySet["Action"]:
        return self.filter(is_active=True)

class Action(models.Model):
    name: str = models.CharField(max_length=255)
    objects: ActionManager = ActionManager()
```

### DRF Serializers

```python
from rest_framework import serializers

class ActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Action
        fields = ["id", "name"]

    def validate_name(self, value: str) -> str:
        if len(value) < 3:
            raise serializers.ValidationError("Nom trop court")
        return value
```

## Bonnes pratiques

1. **Annoter les nouvelles fonctions** : toute nouvelle fonction doit avoir des annotations de type
2. **Utiliser `Optional` correctement** : `str | None` au lieu de `Optional[str]` (Python 3.10+)
3. **Éviter `Any`** : utiliser des types concrets quand possible
4. **Annoter les variables ambiguës** : `items: list[str] = []` au lieu de `items = []`
5. **Utiliser les génériques Django** : `QuerySet["Model"]`, `Manager["Model"]`

## Contribuer à réduire le baseline

Le baseline actuel est de 89 erreurs. Chaque correction réduit ce nombre :

1. Choisir un fichier dans `mypy-report.txt`
2. Corriger les erreurs de type
3. Exécuter `scripts/generate_mypy_baseline.sh`
4. Commiter le baseline mis à jour

### Exemples de corrections réelles

**Exemple 1 : Erreur `error: Returning Any from function`**

```python
# AVANT (erreur mypy)
def get_user_permissions(user):
    return user.permissions.all()

# APRÈS (corrigé)
from django.db.models import QuerySet
from profiles.models import Permission

def get_user_permissions(user) -> QuerySet[Permission]:
    return user.permissions.all()
```

**Exemple 2 : Erreur `error: Need type annotation for 'items'`**

```python
# AVANT (erreur mypy)
items = []
for action in actions:
    items.append(action.name)

# APRÈS (corrigé)
items: list[str] = []
for action in actions:
    items.append(action.name)
```

**Exemple 3 : Erreur `error: "None" has no attribute "id"`**

```python
# AVANT (erreur mypy)
def process_action(action_id: int):
    action = Action.objects.filter(id=action_id).first()
    return action.name  # mypy: error si action est None

# APRÈS (corrigé)
def process_action(action_id: int) -> str | None:
    action = Action.objects.filter(id=action_id).first()
    if action is None:
        return None
    return action.name
```

Voir : [docs/mypy-improvement-roadmap.md](mypy-improvement-roadmap.md)
