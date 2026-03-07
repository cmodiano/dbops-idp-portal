# ADR-005 : Stratégie de Tests avec pytest-django

**Date :** 2026-02-08
**Statut :** Accepté
**Décideurs :** Équipe IDP — Migration Epic M

## Contexte

Le backend FastAPI utilisait `pytest` avec des tests utilisant `httpx.AsyncClient` et des fixtures manuelles. La migration vers Django nécessitait de choisir entre :
1. `unittest` Django natif (TestCase)
2. `pytest-django` avec fixtures pytest
3. Un mix des deux

Le projet a ~1200 tests couvrant 6 apps Django, avec des besoins variés : tests unitaires de services, tests d'intégration d'API, tests de sécurité, tests de performance.

## Décision

**Utiliser `pytest-django` comme framework de test principal**, avec les conventions suivantes :

### Factories (factory_boy)
```python
# tests/factories.py — Factories partagées
class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
    username = factory.Sequence(lambda n: f"user_{n}")
    ad_groups = factory.LazyAttribute(lambda o: ["DBOPS"])

class ActionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Action
    name = factory.Sequence(lambda n: f"action_{n}")
    parameters_schema = factory.LazyFunction(lambda: {"type": "object"})
```

### Conventions de nommage
- Fichiers : `test_<domaine>.py` (ex: `test_profile_views.py`, `test_services.py`)
- Classes : `Test<Feature>` (ex: `TestProfileCRUD`, `TestAuditTrail`)
- Méthodes : `test_<action>_<scenario>` (ex: `test_create_profile_missing_name`)
- Fixtures : `@pytest.fixture` dans `conftest.py` ou directement dans le fichier de test

### Organisation
```
app/tests/
├── __init__.py
├── conftest.py          # Fixtures partagées de l'app
├── test_views.py        # Tests d'API (integration)
├── test_services.py     # Tests de logique métier (unit)
├── test_models.py       # Tests de modèles (unit)
└── test_managers.py     # Tests de managers (unit)
```

### Patterns de test
- **Tests API :** `APIClient` + `force_authenticate()` + assertions sur status code et réponse JSON
- **Tests services :** Appel direct du service avec mock des dépendances externes
- **Tests modèles :** Validation des contraintes, méthodes custom, signals
- **Tests sécurité :** Tests 401/403 systématiques, RBAC, injection

## Conséquences

### Positives
- Compatibilité pytest existante — réutilisation des connaissances de l'équipe
- Fixtures pytest plus flexibles que `setUp()` / `tearDown()` de unittest
- Factories réutilisables — `UserFactory`, `ActionFactory` standardisent la création de données
- Tests paramétrés avec `@pytest.mark.parametrize` pour couvrir les variantes
- Base SQLite in-memory — tests rapides sans Oracle
- Découverte automatique des tests par pytest

### Négatives
- Mix de styles possible (TestCase Django vs fonctions pytest) — résolu par convention
- `TransactionTestCase` nécessaire pour certains tests de transactions (plus lent)
- Factories nécessitent maintenance quand les modèles changent

### Neutres
- Configuration via `pytest.ini` avec `DJANGO_SETTINGS_MODULE = idp_backend.test_settings`
- Migrations appliquées automatiquement par pytest-django
- Compatible avec `pytest-cov` pour le rapport de couverture

## Alternatives Considérées

### Alternative 1 : unittest Django pur (TestCase)
- **Description :** Utiliser uniquement `django.test.TestCase` et `django.test.Client`
- **Raison du rejet :** Moins flexible que pytest (pas de fixtures paramétrées, pas de `@pytest.mark.parametrize`), setup/teardown plus verbeux

### Alternative 2 : Fixtures JSON Django
- **Description :** Utiliser les fixtures JSON de Django (`loaddata`) pour les données de test
- **Raison du rejet :** Difficile à maintenir quand les modèles changent, pas de génération dynamique, fixtures binaires fragiles

## Références

- [Conventions de test détaillées](../../tests/README.md)
- [Issues connues](../../tests/KNOWN_ISSUES.md)
- [pytest-django documentation](https://pytest-django.readthedocs.io/)
- [factory_boy documentation](https://factoryboy.readthedocs.io/)
