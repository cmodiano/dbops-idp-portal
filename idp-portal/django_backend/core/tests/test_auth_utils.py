"""
Tests for core/auth_utils.py — get_user_ad_groups() coverage.
Story 39.2 — Tâche 1
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1.1  user=None → []
# ---------------------------------------------------------------------------
def test_get_user_ad_groups_none_user():
    from core.auth_utils import get_user_ad_groups

    assert get_user_ad_groups(None) == []


# ---------------------------------------------------------------------------
# 1.2  user non authentifié → []
# ---------------------------------------------------------------------------
def test_get_user_ad_groups_unauthenticated():
    from core.auth_utils import get_user_ad_groups

    user = MagicMock()
    user.is_authenticated = False
    assert get_user_ad_groups(user) == []


# ---------------------------------------------------------------------------
# 1.3  get_ad_groups() callable → succès
# ---------------------------------------------------------------------------
def test_get_user_ad_groups_callable_success():
    from core.auth_utils import get_user_ad_groups

    user = MagicMock()
    user.is_authenticated = True
    user.get_ad_groups.return_value = ['group1', 'group2']
    # get_ad_groups callable → branche if prise, elif jamais évaluée

    result = get_user_ad_groups(user)
    assert result == ['group1', 'group2']


# ---------------------------------------------------------------------------
# 1.4  get_ad_groups() lève une exception → warning + retourne []
# ---------------------------------------------------------------------------
def test_get_user_ad_groups_callable_raises():
    from core.auth_utils import get_user_ad_groups

    user = MagicMock()
    user.is_authenticated = True
    user.get_ad_groups.side_effect = RuntimeError("LDAP error")
    user.profile = None  # désactiver le fallback profile

    with patch('core.auth_utils.logger') as mock_logger:
        result = get_user_ad_groups(user)

    assert result == []
    mock_logger.warning.assert_called_once()
    call_kwargs = mock_logger.warning.call_args
    assert call_kwargs[0][0] == 'get_ad_groups_failed'


# ---------------------------------------------------------------------------
# 1.5  ad_groups est une list directe
# ---------------------------------------------------------------------------
def test_get_user_ad_groups_list_attribute():
    from core.auth_utils import get_user_ad_groups

    user = MagicMock(spec=[])  # aucune méthode par défaut
    user.is_authenticated = True
    user.ad_groups = ['grp_a', 'grp_b']

    result = get_user_ad_groups(user)
    assert result == ['grp_a', 'grp_b']


# ---------------------------------------------------------------------------
# 1.6  ad_groups est une chaîne CSV "group1, group2"
# ---------------------------------------------------------------------------
def test_get_user_ad_groups_csv_string():
    from core.auth_utils import get_user_ad_groups

    user = MagicMock(spec=[])
    user.is_authenticated = True
    user.ad_groups = 'group1, group2, group3'

    result = get_user_ad_groups(user)
    assert result == ['group1', 'group2', 'group3']


# ---------------------------------------------------------------------------
# 1.7  ad_groups possède values_list (queryset simulé)
# ---------------------------------------------------------------------------
def test_get_user_ad_groups_queryset():
    from core.auth_utils import get_user_ad_groups

    user = MagicMock(spec=[])
    user.is_authenticated = True

    mock_qs = MagicMock()
    mock_qs.values_list.return_value = ['dn_group1', 'dn_group2']
    user.ad_groups = mock_qs

    result = get_user_ad_groups(user)
    assert result == ['dn_group1', 'dn_group2']
    mock_qs.values_list.assert_called_once_with('name', flat=True)


# ---------------------------------------------------------------------------
# 1.8  fallback profile str
# ---------------------------------------------------------------------------
def test_get_user_ad_groups_profile_str():
    from core.auth_utils import get_user_ad_groups

    user = MagicMock(spec=[])
    user.is_authenticated = True
    # Pas d'ad_groups → branch elif ne s'active pas
    user.profile = 'DBOPS'

    result = get_user_ad_groups(user)
    assert result == ['DBOPS']


# ---------------------------------------------------------------------------
# 1.9  fallback profile objet avec .name
# ---------------------------------------------------------------------------
def test_get_user_ad_groups_profile_object_with_name():
    from core.auth_utils import get_user_ad_groups

    user = MagicMock(spec=[])
    user.is_authenticated = True
    profile_obj = MagicMock()
    profile_obj.name = 'DBA'
    user.profile = profile_obj

    result = get_user_ad_groups(user)
    assert result == ['DBA']


# ---------------------------------------------------------------------------
# 1.10 ad_groups vide + profile None → []
# ---------------------------------------------------------------------------
def test_get_user_ad_groups_empty_ad_groups_no_profile():
    from core.auth_utils import get_user_ad_groups

    user = MagicMock(spec=[])
    user.is_authenticated = True
    user.ad_groups = []
    user.profile = None

    result = get_user_ad_groups(user)
    assert result == []
