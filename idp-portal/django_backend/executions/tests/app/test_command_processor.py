"""Tests pour executions.app.command_processor — Story 85.3."""
import pytest
from executions.app.command_processor import WorkflowCommandService


def test_import_from_app_command_processor():
    """Vérifier que l'import depuis app.command_processor fonctionne."""
    assert WorkflowCommandService is not None


@pytest.mark.django_db
def test_write_command_creates_command():
    from tests.factories import ExecutionFactory
    from executions.models import WorkflowCommandStatus
    execution = ExecutionFactory(status="running")
    cmd = WorkflowCommandService.write_command(
        execution_id=execution.id,
        command_type="cancel",
    )
    assert cmd.id is not None
    assert cmd.status == WorkflowCommandStatus.PENDING
    assert cmd.command_type == "cancel"


def test_write_command_invalid_type_raises():
    with pytest.raises(ValueError, match="Invalid command_type"):
        WorkflowCommandService.write_command(
            execution_id=999,
            command_type="invalid_type",
        )
