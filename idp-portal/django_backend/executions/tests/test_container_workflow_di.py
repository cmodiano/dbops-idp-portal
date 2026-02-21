"""
Tests d'injection de dépendances pour ContainerWorkflowRuntime — Story 33.4 (DIP)

Vérifient :
- L'injection directe d'un ExecutionService mock (AC3)
- Le fallback sur ExecutionService() par défaut (AC4 — rétrocompatibilité)
"""
from unittest.mock import MagicMock

import pytest


@pytest.mark.django_db
def test_container_workflow_uses_injected_service():
    """AC3 : ContainerWorkflowRuntime accepte un ExecutionService injecté."""
    mock_execution = MagicMock()
    mock_execution.action.execution_steps = []
    mock_execution.action.name = "test-workflow"
    mock_execution.action.id = 1
    mock_execution.id = 42
    mock_svc = MagicMock()

    from executions.container_workflow_runtime import ContainerWorkflowRuntime
    runtime = ContainerWorkflowRuntime(mock_execution, execution_service=mock_svc)

    assert runtime.execution_service is mock_svc


@pytest.mark.django_db
def test_container_workflow_default_service():
    """AC4 : Sans injection, ContainerWorkflowRuntime instancie ExecutionService par défaut."""
    from executions.services import ExecutionService
    from executions.container_workflow_runtime import ContainerWorkflowRuntime

    mock_execution = MagicMock()
    mock_execution.action.execution_steps = []
    mock_execution.action.name = "test-workflow"
    mock_execution.action.id = 1
    mock_execution.id = 42

    runtime = ContainerWorkflowRuntime(mock_execution)
    assert isinstance(runtime.execution_service, ExecutionService)
