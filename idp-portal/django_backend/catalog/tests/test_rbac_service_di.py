"""
Tests d'injection de dépendances pour CatalogRBACService — Story 33.4 (DIP)

Vérifient :
- L'injection directe d'un ProfileService mock (AC3)
- L'injection directe d'un InventoryService mock (AC3)
- Le fallback sur les services par défaut (AC4 — rétrocompatibilité)
"""
from unittest.mock import MagicMock



def test_catalog_rbac_service_uses_injected_profile_service():
    """AC3 : CatalogRBACService accepte un ProfileService injecté."""
    mock_profile_svc = MagicMock()
    from catalog.rbac_service import CatalogRBACService
    rbac = CatalogRBACService(profile_service=mock_profile_svc)
    assert rbac._profile_service is mock_profile_svc


def test_catalog_rbac_service_uses_injected_inventory_service():
    """AC3 : CatalogRBACService accepte un InventoryService injecté."""
    mock_inv_svc = MagicMock()
    from catalog.rbac_service import CatalogRBACService
    rbac = CatalogRBACService(inventory_service=mock_inv_svc)
    assert rbac._inventory_service is mock_inv_svc


def test_catalog_rbac_service_default_services():
    """AC4 : Sans injection, CatalogRBACService utilise les services par défaut."""
    from catalog.rbac_service import CatalogRBACService
    rbac = CatalogRBACService()
    assert rbac._profile_service is None
    assert rbac._inventory_service is None


def test_catalog_rbac_service_get_permissions_uses_injected_profile_service():
    """AC3 : get_permissions() utilise le ProfileService injecté."""
    mock_profile_svc = MagicMock()
    mock_profile_svc.get_cumulative_permissions.return_value = {
        'action_permissions': [
            {
                'actions_type': 'all',
                'action_ids': [],
                'tag_patterns': [],
                'environments': ['prod'],
            }
        ]
    }
    mock_user = MagicMock()
    mock_user.is_authenticated = True
    mock_user.id = 1

    from catalog.rbac_service import CatalogRBACService
    from unittest.mock import patch
    with patch('catalog.rbac_service.get_user_ad_groups', return_value=['group1']):
        rbac = CatalogRBACService(profile_service=mock_profile_svc)
        result = rbac.get_permissions(mock_user)

    mock_profile_svc.get_cumulative_permissions.assert_called_once()
    assert result is not None
