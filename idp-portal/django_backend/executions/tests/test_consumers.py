"""
Tests for executions/consumers.py — ExecutionConsumer, DashboardConsumer.
Story 39.4 — Tâche 3.

Stratégie : tests unitaires async avec AsyncMock pour éviter le routing ASGI complet.
"""
import json
import pytest
from unittest.mock import AsyncMock, patch

from channels.exceptions import StopConsumer  # type: ignore[import-untyped]

from core.consumers import AuthenticatedWebSocketConsumer
from executions.consumers import ExecutionConsumer, DashboardConsumer


# ============================================================================
# Tâche 3.1 — connect(): execution_id absent → fermeture immédiate
# ============================================================================

@pytest.mark.asyncio
async def test_connect_missing_execution_id_closes_immediately():
    """3.1: Missing execution_id in url_route → close() called immediately."""
    consumer = ExecutionConsumer()
    consumer.scope = {"url_route": {"kwargs": {}}}
    consumer.close = AsyncMock()

    await consumer.connect()

    consumer.close.assert_called_once()


# ============================================================================
# Tâche 3.2 — connect(): execution_id présent, sans channel_layer → pas d'exception
# ============================================================================

@pytest.mark.asyncio
async def test_connect_with_execution_id_no_channel_layer():
    """3.2: execution_id present, no channel_layer → no exception, group_add not called."""
    consumer = ExecutionConsumer()
    consumer.scope = {"url_route": {"kwargs": {"execution_id": "42"}}}

    # Remove channel_layer attribute if it exists
    if hasattr(consumer, 'channel_layer'):
        del consumer.channel_layer

    with patch.object(AuthenticatedWebSocketConsumer, 'connect', new_callable=AsyncMock):
        await consumer.connect()

    # No exception raised; group_add not applicable since no channel_layer
    assert consumer.execution_id == "42"
    assert consumer.group_name == "execution_42"


# ============================================================================
# Tâche 3.3 — connect(): avec channel_layer mock → group_add appelé
# ============================================================================

@pytest.mark.asyncio
async def test_connect_with_channel_layer_calls_group_add():
    """3.3: With channel_layer mock → group_add called with execution_{id}."""
    consumer = ExecutionConsumer()
    consumer.scope = {"url_route": {"kwargs": {"execution_id": "99"}}}
    consumer.channel_name = "test_channel_name"

    mock_channel_layer = AsyncMock()
    consumer.channel_layer = mock_channel_layer

    with patch.object(AuthenticatedWebSocketConsumer, 'connect', new_callable=AsyncMock):
        await consumer.connect()

    mock_channel_layer.group_add.assert_called_once_with("execution_99", "test_channel_name")


# ============================================================================
# Tâche 3.4 — disconnect(): avec channel_layer → group_discard appelé
# ============================================================================

@pytest.mark.asyncio
async def test_disconnect_with_channel_layer_calls_group_discard():
    """3.4: With channel_layer → group_discard called."""
    consumer = ExecutionConsumer()
    consumer.execution_id = "42"
    consumer.group_name = "execution_42"
    consumer.channel_name = "channel_abc"

    mock_channel_layer = AsyncMock()
    consumer.channel_layer = mock_channel_layer

    with patch.object(AuthenticatedWebSocketConsumer, 'disconnect', new_callable=AsyncMock):
        await consumer.disconnect(1000)

    mock_channel_layer.group_discard.assert_called_once_with("execution_42", "channel_abc")


# ============================================================================
# Tâche 3.5 — disconnect(): group_discard lève une exception → log warning, pas de propagation
# ============================================================================

@pytest.mark.asyncio
async def test_disconnect_group_discard_exception_does_not_propagate():
    """3.5: group_discard raises exception → warning logged, no propagation."""
    consumer = ExecutionConsumer()
    consumer.execution_id = "42"
    consumer.group_name = "execution_42"
    consumer.channel_name = "channel_abc"

    mock_channel_layer = AsyncMock()
    mock_channel_layer.group_discard = AsyncMock(side_effect=Exception("channel error"))
    consumer.channel_layer = mock_channel_layer

    with patch.object(AuthenticatedWebSocketConsumer, 'disconnect', new_callable=AsyncMock):
        # Should not raise
        await consumer.disconnect(1000)


# ============================================================================
# Tâche 3.6 — disconnect(): sans channel_layer → group_discard non appelé
# ============================================================================

@pytest.mark.asyncio
async def test_disconnect_without_channel_layer_no_group_discard():
    """3.6: Without channel_layer → group_discard not called."""
    consumer = ExecutionConsumer()
    consumer.execution_id = "42"
    consumer.group_name = "execution_42"
    consumer.channel_name = "channel_abc"

    # No channel_layer
    if hasattr(consumer, 'channel_layer'):
        del consumer.channel_layer

    with patch.object(AuthenticatedWebSocketConsumer, 'disconnect', new_callable=AsyncMock):
        # Should not raise
        await consumer.disconnect(1000)


# ============================================================================
# Tâche 3.7 — _safe_send(): succès normal → payload envoyé en JSON
# ============================================================================

@pytest.mark.asyncio
async def test_safe_send_success_sends_json_payload():
    """3.7: Normal success → payload sent as JSON."""
    consumer = ExecutionConsumer()
    consumer.send = AsyncMock()

    await consumer._safe_send({"type": "step_update", "data": {"step": 1}})

    consumer.send.assert_called_once()
    call_kwargs = consumer.send.call_args.kwargs
    payload = json.loads(call_kwargs["text_data"])
    assert payload["type"] == "step_update"
    assert payload["data"] == {"step": 1}


# ============================================================================
# Tâche 3.8 — _safe_send(): StopConsumer → retour silencieux
# ============================================================================

@pytest.mark.asyncio
async def test_safe_send_stop_consumer_returns_silently():
    """3.8: StopConsumer raised → silent return, no propagation."""
    consumer = ExecutionConsumer()
    consumer.send = AsyncMock(side_effect=StopConsumer())

    # Should not raise
    await consumer._safe_send({"type": "test"})


# ============================================================================
# Tâche 3.9 — _safe_send(): autre exception → log debug, pas de propagation
# ============================================================================

@pytest.mark.asyncio
async def test_safe_send_generic_exception_does_not_propagate():
    """3.9: Generic exception → debug log, no propagation."""
    consumer = ExecutionConsumer()
    consumer.send = AsyncMock(side_effect=RuntimeError("network error"))

    # Should not raise
    await consumer._safe_send({"type": "test"})


# ============================================================================
# Tâche 3.10 — step_update(): forward {"type": "step_update", "data": ...}
# ============================================================================

@pytest.mark.asyncio
async def test_step_update_forwards_correct_payload():
    """3.10: step_update → forwards {type: step_update, data: ...}."""
    consumer = ExecutionConsumer()
    consumer._safe_send = AsyncMock()

    await consumer.step_update({"data": {"step": 1, "status": "running"}})

    consumer._safe_send.assert_called_once_with({
        "type": "step_update",
        "data": {"step": 1, "status": "running"},
    })


# ============================================================================
# Tâche 3.11 — log_update(): forward {"type": "log_update", "data": ...}
# ============================================================================

@pytest.mark.asyncio
async def test_log_update_forwards_correct_payload():
    """3.11: log_update → forwards {type: log_update, data: ...}."""
    consumer = ExecutionConsumer()
    consumer._safe_send = AsyncMock()

    await consumer.log_update({"data": {"line": "log line 1"}})

    consumer._safe_send.assert_called_once_with({
        "type": "log_update",
        "data": {"line": "log line 1"},
    })


# ============================================================================
# Tâche 3.12 — execution_complete(): forward {"type": "execution_complete", "data": ...}
# ============================================================================

@pytest.mark.asyncio
async def test_execution_complete_forwards_correct_payload():
    """3.12: execution_complete → forwards {type: execution_complete, data: ...}."""
    consumer = ExecutionConsumer()
    consumer._safe_send = AsyncMock()

    await consumer.execution_complete({"data": {"result": "success"}})

    consumer._safe_send.assert_called_once_with({
        "type": "execution_complete",
        "data": {"result": "success"},
    })


# ============================================================================
# Tâche 3.13 — execution_failed(): forward {"type": "execution_failed", "data": ...}
# ============================================================================

@pytest.mark.asyncio
async def test_execution_failed_forwards_correct_payload():
    """3.13: execution_failed → forwards {type: execution_failed, data: ...}."""
    consumer = ExecutionConsumer()
    consumer._safe_send = AsyncMock()

    await consumer.execution_failed({"data": {"error": "timeout"}})

    consumer._safe_send.assert_called_once_with({
        "type": "execution_failed",
        "data": {"error": "timeout"},
    })


# ============================================================================
# Tâche 3.14 — status_update(): forward {"type": "status_update", "data": ...}
# ============================================================================

@pytest.mark.asyncio
async def test_status_update_forwards_correct_payload():
    """3.14: status_update → forwards {type: status_update, data: ...}."""
    consumer = ExecutionConsumer()
    consumer._safe_send = AsyncMock()

    await consumer.status_update({"data": {"status": "COMPLETED"}})

    consumer._safe_send.assert_called_once_with({
        "type": "status_update",
        "data": {"status": "COMPLETED"},
    })


# ============================================================================
# Tâche 3.15 — ExecutionConsumer.handle_authenticated_message(): log debug only
# ============================================================================

@pytest.mark.asyncio
async def test_execution_consumer_handle_authenticated_message_no_exception():
    """3.15: handle_authenticated_message → debug log only, no exception."""
    consumer = ExecutionConsumer()
    consumer.execution_id = "42"
    consumer.user_id = "user_1"

    # Should not raise
    await consumer.handle_authenticated_message({"type": "ping"})


# ============================================================================
# Tâche 3.16 — DashboardConsumer.handle_authenticated_message(): pass, no exception
# ============================================================================

@pytest.mark.asyncio
async def test_dashboard_consumer_handle_authenticated_message_no_exception():
    """3.16: DashboardConsumer.handle_authenticated_message → pass, no exception."""
    consumer = DashboardConsumer()

    # Should not raise
    await consumer.handle_authenticated_message({"type": "ping"})
