"""
Tests d'injection de dépendances pour les vues d'exécution — Story 33.4 (DIP)

Vérifient :
- Surcharge de _execution_service_class dans ExecutionsCreateView (AC3)
- Surcharge de _execution_service_class dans ApproveExecutionView (AC3)
- Surcharge de _execution_service_class dans ExecutionCancelView (AC3)
- Fallback sur ExecutionService par défaut (AC4 — rétrocompatibilité)
"""
from unittest.mock import MagicMock

import pytest


def test_executions_create_view_injected_service():
    """AC3 : ExecutionsCreateView accepte un service surchargé via _execution_service_class."""
    mock_svc_class = MagicMock(return_value=MagicMock())
    from executions.views.execution_views import ExecutionsCreateView
    view = ExecutionsCreateView()
    view._execution_service_class = mock_svc_class
    svc = view.get_execution_service()
    mock_svc_class.assert_called_once()


def test_executions_create_view_default_service():
    """AC4 : Sans surcharge, ExecutionsCreateView utilise ExecutionService par défaut."""
    from executions.services import ExecutionService
    from executions.views.execution_views import ExecutionsCreateView
    view = ExecutionsCreateView()
    svc = view.get_execution_service()
    assert isinstance(svc, ExecutionService)


def test_approve_execution_view_injected_service():
    """AC3 : ApproveExecutionView accepte un service surchargé via _execution_service_class."""
    mock_svc_class = MagicMock(return_value=MagicMock())
    from executions.views.approval_views import ApproveExecutionView
    view = ApproveExecutionView()
    view._execution_service_class = mock_svc_class
    svc = view.get_execution_service()
    mock_svc_class.assert_called_once()


def test_approve_execution_view_default_service():
    """AC4 : Sans surcharge, ApproveExecutionView utilise ExecutionService par défaut."""
    from executions.services import ExecutionService
    from executions.views.approval_views import ApproveExecutionView
    view = ApproveExecutionView()
    svc = view.get_execution_service()
    assert isinstance(svc, ExecutionService)


def test_execution_cancel_view_injected_service():
    """AC3 : ExecutionCancelView accepte un service surchargé via _execution_service_class."""
    mock_svc_class = MagicMock(return_value=MagicMock())
    from executions.views.execution_views import ExecutionCancelView
    view = ExecutionCancelView()
    view._execution_service_class = mock_svc_class
    svc = view.get_execution_service()
    mock_svc_class.assert_called_once()


def test_execution_cancel_view_default_service():
    """AC4 : Sans surcharge, ExecutionCancelView utilise ExecutionService par défaut."""
    from executions.services import ExecutionService
    from executions.views.execution_views import ExecutionCancelView
    view = ExecutionCancelView()
    svc = view.get_execution_service()
    assert isinstance(svc, ExecutionService)
