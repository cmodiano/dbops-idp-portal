"""
Package catalog/views — DRF ViewSets for catalog app.

Ce package regroupe les ViewSets par domaine :
- action_views        : CRUD admin des actions
- business_rule_views : CRUD admin des règles métier
- catalog_views       : lecture publique du catalogue (RBAC)
- tags_views          : lecture publique des tags
- _shared             : cache TTL + helpers partagés (module interne)

Note : _catalog_cache, _tags_cache et _get_cache_key sont re-exportés depuis ce package
pour maintenir la rétrocompatibilité avec les imports existants (from catalog.views import _catalog_cache).
Ces symboles ne font pas partie de l'API publique (__all__) mais restent accessibles via import direct.
"""
from catalog.views.action_views import ActionViewSet
from catalog.views.business_rule_views import BusinessRulePolicyViewSet
from catalog.views.catalog_views import CatalogActionViewSet
from catalog.views.tags_views import TagViewSet

# Rétrocompatibilité : ces symboles privés sont re-exportés pour les tests existants
# qui utilisent `from catalog.views import _catalog_cache` (voir test_performance.py, test_bug_be5_cache_pagination.py)
from catalog.views._shared import _catalog_cache, _tags_cache, _get_cache_key

__all__ = [
    "ActionViewSet",
    "BusinessRulePolicyViewSet",
    "CatalogActionViewSet",
    "TagViewSet",
]
