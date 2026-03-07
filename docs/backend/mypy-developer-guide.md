# Guide Mypy pour Développeurs

## Pourquoi mypy ?

- **Détection de bugs** : erreurs de type détectées avant l'exécution (None inattendu, mauvais types)
- **Auto-completion IDE** : meilleure suggestion de méthodes et attributs
- **Refactoring sûr** : les changements de signature sont vérifiés partout
- **Documentation vivante** : les annotations de type documentent les contrats d'API

## Mode strict activé (Story 26.16)

Le projet est en **mode strict** depuis février 2026 :
- `disallow_untyped_defs = true` sur les modules principaux (core, idp_auth, executions, catalog, inventory, profiles, reference)
- **Toute erreur mypy bloque** le commit (pre-commit hook) et la CI
- **0 erreur tolérée** — le mécanisme baseline a été supprimé

## Exécuter mypy localement

```bash
cd django_backend
source .venv/bin/activate

# Vérifier les types (utilise pyproject.toml)
mypy .

# Doit retourner 0 erreur — sinon le commit sera bloqué
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
| `error: Function is missing a type annotation` | Fonction sans annotations | Ajouter types sur paramètres et retour |

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

### Vues DRF

```python
from rest_framework.request import Request
from rest_framework.response import Response

class ActionViewSet(viewsets.ModelViewSet):
    def list(self, request: Request) -> Response:
        ...

    def create(self, request: Request) -> Response:
        ...
```

## Bonnes pratiques

1. **Annoter toutes les nouvelles fonctions** : paramètres ET retour obligatoires sur les modules principaux
2. **Utiliser la syntaxe moderne** : `str | None` au lieu de `Optional[str]` (Python 3.10+)
3. **Éviter `Any`** : utiliser des types concrets quand possible
4. **Annoter les variables ambiguës** : `items: list[str] = []` au lieu de `items = []`
5. **Utiliser les génériques Django** : `QuerySet["Model"]`, `Manager["Model"]`
6. **Utiliser `from __future__ import annotations`** : pour les références circulaires

Voir : [docs/mypy-improvement-roadmap.md](mypy-improvement-roadmap.md) pour l'historique des phases.
