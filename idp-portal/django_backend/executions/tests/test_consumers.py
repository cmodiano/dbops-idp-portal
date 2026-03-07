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
# Tâche 3.3 — connect(): avec channel_layer mock → group_add N'EST PAS appelé
# (SEC-2 FIX: group_add déplacé dans receive() après auth+authz)
# ============================================================================

@pytest.mark.asyncio
async def test_connect_with_channel_layer_does_not_call_group_add():
    """3.3 (SEC-2): With channel_layer mock → group_add NOT called in connect() anymore."""
    consumer = ExecutionConsumer()
    consumer.scope = {"url_route": {"kwargs": {"execution_id": "99"}}}
    consumer.channel_name = "test_channel_name"

    mock_channel_layer = AsyncMock()
    consumer.channel_layer = mock_channel_layer

    with patch.object(AuthenticatedWebSocketConsumer, 'connect', new_callable=AsyncMock):
        await consumer.connect()

    mock_channel_layer.group_add.assert_not_called()


# ============================================================================
# Tâche 3.4 — disconnect(): avec channel_layer → group_discard appelé
# ============================================================================

@pytest.mark.asyncio
async def test_disconnect_with_channel_layer_calls_group_discard():
    """3.4: With channel_layer and _group_joined=True → group_discard called."""
    consumer = ExecutionConsumer()
    consumer.execution_id = "42"
    consumer.group_name = "execution_42"
    consumer._group_joined = True
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
    consumer._group_joined = True
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


@pytest.mark.asyncio
async def test_disconnect_no_attribute_error_when_group_name_unset():
    """Regression: disconnect() when connect() returned early (no group_name) → no AttributeError."""
    consumer = ExecutionConsumer()
    consumer.scope = {"url_route": {"kwargs": {}}}
    consumer.channel_name = "channel_abc"
    consumer.channel_layer = AsyncMock()
    # Simulate connect() returned early: group_name and _group_joined never set

    with patch.object(AuthenticatedWebSocketConsumer, 'disconnect', new_callable=AsyncMock):
        await consumer.disconnect(1000)

    consumer.channel_layer.group_discard.assert_not_called()


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


# ============================================================================
# Story 59-2 — SEC-2 : vérification d'accès après auth JWT
# ============================================================================

def _make_consumer(execution_id: str = "42", user_id: str | None = None) -> ExecutionConsumer:
    """Helper : crée un ExecutionConsumer avec les attributs minimaux."""
    consumer = ExecutionConsumer()
    consumer.execution_id = execution_id
    consumer.group_name = f"execution_{execution_id}"
    consumer.channel_name = "test_channel"
    consumer.authenticated = False
    consumer.user_id = user_id
    return consumer


# ============================================================================
# Test 59-2-a : owner → group_add appelé, pas de close
# ============================================================================

@pytest.mark.asyncio
async def test_receive_authorized_owner_joins_group():
    """59-2-a: Authenticated owner → group_add called, close not called."""
    consumer = _make_consumer(execution_id="42", user_id=None)

    mock_channel_layer = AsyncMock()
    consumer.channel_layer = mock_channel_layer
    consumer.close = AsyncMock()

    async def mock_super_receive(self_inner, **kwargs):
        consumer.authenticated = True
        consumer.user_id = "10"

    with patch.object(consumer, '_check_execution_access', new=AsyncMock(return_value=True)):
        with patch.object(AuthenticatedWebSocketConsumer, 'receive', mock_super_receive):
            await consumer.receive(text_data='{"type":"auth","token":"tok"}')

    mock_channel_layer.group_add.assert_called_once_with("execution_42", "test_channel")
    consumer.close.assert_not_called()


# ============================================================================
# Test 59-2-b : non owner / non admin → close(4003), group_add non appelé
# ============================================================================

@pytest.mark.asyncio
async def test_receive_unauthorized_user_closes_4003():
    """59-2-b: Non-owner, non-admin user → close(4003) called, group_add not called."""
    consumer = _make_consumer(execution_id="42", user_id=None)

    mock_channel_layer = AsyncMock()
    consumer.channel_layer = mock_channel_layer
    consumer.close = AsyncMock()

    async def mock_super_receive(self_inner, **kwargs):
        consumer.authenticated = True
        consumer.user_id = "99"

    with patch.object(consumer, '_check_execution_access', new=AsyncMock(return_value=False)):
        with patch.object(AuthenticatedWebSocketConsumer, 'receive', mock_super_receive):
            await consumer.receive(text_data='{"type":"auth","token":"tok"}')

    consumer.close.assert_called_once_with(code=4003)
    mock_channel_layer.group_add.assert_not_called()


# ============================================================================
# Test 59-2-c : admin (is_admin=1) → group_add appelé, pas de close
# ============================================================================

@pytest.mark.asyncio
async def test_receive_admin_user_joins_group():
    """59-2-c: Admin user (is_admin=1) → group_add called, close not called."""
    consumer = _make_consumer(execution_id="42", user_id=None)

    mock_channel_layer = AsyncMock()
    consumer.channel_layer = mock_channel_layer
    consumer.close = AsyncMock()

    async def mock_super_receive(self_inner, **kwargs):
        consumer.authenticated = True
        consumer.user_id = "7"  # admin, not owner

    with patch.object(consumer, '_check_execution_access', new=AsyncMock(return_value=True)):
        with patch.object(AuthenticatedWebSocketConsumer, 'receive', mock_super_receive):
            await consumer.receive(text_data='{"type":"auth","token":"tok"}')

    mock_channel_layer.group_add.assert_called_once_with("execution_42", "test_channel")
    consumer.close.assert_not_called()


# ============================================================================
# Test 59-2-d : exécution inexistante → _check_execution_access retourne False → close(4003)
# ============================================================================

@pytest.mark.asyncio
async def test_receive_nonexistent_execution_closes_4003():
    """59-2-d: Execution not found → _check_execution_access returns False → close(4003)."""
    consumer = _make_consumer(execution_id="9999", user_id=None)

    mock_channel_layer = AsyncMock()
    consumer.channel_layer = mock_channel_layer
    consumer.close = AsyncMock()

    async def mock_super_receive(self_inner, **kwargs):
        consumer.authenticated = True
        consumer.user_id = "10"

    with patch.object(consumer, '_check_execution_access', new=AsyncMock(return_value=False)):
        with patch.object(AuthenticatedWebSocketConsumer, 'receive', mock_super_receive):
            await consumer.receive(text_data='{"type":"auth","token":"tok"}')

    consumer.close.assert_called_once_with(code=4003)
    mock_channel_layer.group_add.assert_not_called()


# ============================================================================
# Test 59-2-e : connect() initialise _group_joined à False (SEC-2 state tracking)
# ============================================================================

@pytest.mark.asyncio
async def test_connect_initializes_group_joined_false():
    """59-2-e: connect() sets _group_joined=False; group_add NOT called in connect()."""
    consumer = ExecutionConsumer()
    consumer.scope = {"url_route": {"kwargs": {"execution_id": "42"}}}
    consumer.channel_name = "ch"

    mock_channel_layer = AsyncMock()
    consumer.channel_layer = mock_channel_layer

    with patch.object(AuthenticatedWebSocketConsumer, 'connect', new_callable=AsyncMock):
        await consumer.connect()

    assert consumer._group_joined is False
    mock_channel_layer.group_add.assert_not_called()


# ============================================================================
# Test 59-2-f : auth échec (code 4001) → group_add jamais appelé
# ============================================================================

@pytest.mark.asyncio
async def test_receive_skips_group_add_when_super_receive_does_not_authenticate():
    """59-2-f: When super().receive() does not set authenticated=True, ExecutionConsumer.receive()
    skips access check and group_add entirely (auth guard: only join when authenticated)."""
    consumer = _make_consumer(execution_id="42", user_id=None)

    mock_channel_layer = AsyncMock()
    consumer.channel_layer = mock_channel_layer
    consumer.close = AsyncMock()

    # super().receive() does NOT set authenticated=True (simulates auth failure / no-op)
    async def mock_super_receive_no_auth(self_inner, **kwargs):
        pass  # authenticated stays False

    with patch.object(consumer, '_check_execution_access', new=AsyncMock(return_value=False)) as mock_check:
        with patch.object(AuthenticatedWebSocketConsumer, 'receive', mock_super_receive_no_auth):
            await consumer.receive(text_data='{"type":"auth","token":"invalid"}')

    mock_check.assert_not_called()
    mock_channel_layer.group_add.assert_not_called()
    consumer.close.assert_not_called()


# ============================================================================
# Test 59-2-g : receive() — exception dans _check_execution_access → close(4003)
# ============================================================================

@pytest.mark.asyncio
async def test_receive_access_check_exception_closes_4003():
    """59-2-g: _check_execution_access raises unexpected exception → close(4003), fail-secure."""
    consumer = _make_consumer(execution_id="42", user_id=None)

    mock_channel_layer = AsyncMock()
    consumer.channel_layer = mock_channel_layer
    consumer.close = AsyncMock()

    async def mock_super_receive(self_inner, **kwargs):
        consumer.authenticated = True
        consumer.user_id = "10"

    with patch.object(
        consumer, '_check_execution_access',
        new=AsyncMock(side_effect=Exception("DB connection failed"))
    ):
        with patch.object(AuthenticatedWebSocketConsumer, 'receive', mock_super_receive):
            await consumer.receive(text_data='{"type":"auth","token":"tok"}')

    consumer.close.assert_called_once_with(code=4003)
    mock_channel_layer.group_add.assert_not_called()


# ============================================================================
# Tests 59-2-h à 59-2-k : _check_execution_access — logique interne (mocks DB)
# Les imports dans _check_execution_access sont locaux → on patche les sources.
# ============================================================================

@pytest.mark.asyncio
async def test_check_execution_access_owner_returns_true():
    """59-2-h: Owner (str(execution.user_id) == str(self.user_id)) → True, no admin query."""
    from executions.models import Execution as RealExecution
    from unittest.mock import MagicMock

    consumer = _make_consumer(execution_id="42", user_id="10")

    mock_execution = MagicMock()
    mock_execution.user_id = 10  # int → str comparison: str(10) == "10" → True

    mock_exec_cls = MagicMock()
    mock_exec_cls.objects.aget = AsyncMock(return_value=mock_execution)
    mock_exec_cls.DoesNotExist = RealExecution.DoesNotExist

    mock_user_model = MagicMock()

    with patch('executions.models.Execution', mock_exec_cls):
        with patch('django.contrib.auth.get_user_model', return_value=mock_user_model):
            result = await consumer._check_execution_access()

    assert result is True
    # Admin query must NOT be executed (owner short-circuits)
    mock_user_model.objects.filter.assert_not_called()


@pytest.mark.asyncio
async def test_check_execution_access_admin_not_owner_returns_true():
    """59-2-i: Non-owner admin (profiles__is_admin=1 via aexists) → True."""
    from executions.models import Execution as RealExecution
    from unittest.mock import MagicMock

    consumer = _make_consumer(execution_id="42", user_id="7")

    mock_execution = MagicMock()
    mock_execution.user_id = 99  # not owner

    mock_exec_cls = MagicMock()
    mock_exec_cls.objects.aget = AsyncMock(return_value=mock_execution)
    mock_exec_cls.DoesNotExist = RealExecution.DoesNotExist

    mock_qs = MagicMock()
    mock_qs.aexists = AsyncMock(return_value=True)
    mock_user_model = MagicMock()
    mock_user_model.objects.filter = MagicMock(return_value=mock_qs)

    with patch('executions.models.Execution', mock_exec_cls):
        with patch('django.contrib.auth.get_user_model', return_value=mock_user_model):
            result = await consumer._check_execution_access()

    assert result is True
    mock_user_model.objects.filter.assert_called_once_with(id="7", profiles__is_admin=1)


@pytest.mark.asyncio
async def test_check_execution_access_nonexistent_execution_returns_false():
    """59-2-j: Execution.DoesNotExist → returns False, admin query never executed."""
    from executions.models import Execution as RealExecution
    from unittest.mock import MagicMock

    consumer = _make_consumer(execution_id="9999", user_id="10")

    mock_exec_cls = MagicMock()
    mock_exec_cls.objects.aget = AsyncMock(side_effect=RealExecution.DoesNotExist)
    mock_exec_cls.DoesNotExist = RealExecution.DoesNotExist

    mock_user_model = MagicMock()

    with patch('executions.models.Execution', mock_exec_cls):
        with patch('django.contrib.auth.get_user_model', return_value=mock_user_model):
            result = await consumer._check_execution_access()

    assert result is False
    mock_user_model.objects.filter.assert_not_called()


@pytest.mark.asyncio
async def test_check_execution_access_non_owner_non_admin_returns_false():
    """59-2-k: Non-owner, non-admin (aexists returns False) → False."""
    from executions.models import Execution as RealExecution
    from unittest.mock import MagicMock

    consumer = _make_consumer(execution_id="42", user_id="5")

    mock_execution = MagicMock()
    mock_execution.user_id = 99  # not owner

    mock_exec_cls = MagicMock()
    mock_exec_cls.objects.aget = AsyncMock(return_value=mock_execution)
    mock_exec_cls.DoesNotExist = RealExecution.DoesNotExist

    mock_qs = MagicMock()
    mock_qs.aexists = AsyncMock(return_value=False)
    mock_user_model = MagicMock()
    mock_user_model.objects.filter = MagicMock(return_value=mock_qs)

    with patch('executions.models.Execution', mock_exec_cls):
        with patch('django.contrib.auth.get_user_model', return_value=mock_user_model):
            result = await consumer._check_execution_access()

    assert result is False


# ============================================================================
# Tests 59-2-l / 59-2-m : disconnect() — log trompeur corrigé (_group_joined state)
# ============================================================================

@pytest.mark.asyncio
async def test_disconnect_group_discard_called_when_joined():
    """59-2-l: disconnect() with _group_joined=True → group_discard called (user had joined)."""
    consumer = _make_consumer(execution_id="42")
    consumer._group_joined = True

    mock_channel_layer = AsyncMock()
    consumer.channel_layer = mock_channel_layer

    with patch.object(AuthenticatedWebSocketConsumer, 'disconnect', new_callable=AsyncMock):
        await consumer.disconnect(1000)

    mock_channel_layer.group_discard.assert_called_once_with("execution_42", "test_channel")


@pytest.mark.asyncio
async def test_disconnect_skips_group_discard_when_never_joined():
    """59-2-m: disconnect() with _group_joined=False → group_discard NOT called
    (guard: only cleanup when we actually joined to avoid AttributeError)."""
    consumer = _make_consumer(execution_id="42")
    consumer._group_joined = False

    mock_channel_layer = AsyncMock()
    consumer.channel_layer = mock_channel_layer

    with patch.object(AuthenticatedWebSocketConsumer, 'disconnect', new_callable=AsyncMock):
        await consumer.disconnect(4003)

    mock_channel_layer.group_discard.assert_not_called()


# ============================================================================
# Tests 59-2-n / 59-2-o : intégration WebSocket via WebsocketCommunicator (AC-5)
# Vérifie que l'utilisateur A ne peut pas observer les exécutions de l'utilisateur B.
# ============================================================================

@pytest.mark.asyncio
async def test_ws_integration_unauthorized_user_receives_close_4003():
    """59-2-n (AC-5): Full WebSocket stack — unauthorized user is closed with code 4003.

    Tests the complete consumer lifecycle via WebsocketCommunicator:
    connect → send auth → auth_success → access denied → close(4003).
    JWT verification and DB access check are mocked.
    """
    from channels.testing import WebsocketCommunicator  # type: ignore[import-untyped]
    from channels.routing import URLRouter
    from django.urls import re_path
    from unittest.mock import MagicMock

    application = URLRouter([
        re_path(r"ws/executions/(?P<execution_id>[0-9]+)$", ExecutionConsumer.as_asgi()),
    ])

    communicator = WebsocketCommunicator(application, "ws/executions/42")

    mock_payload = MagicMock()
    mock_payload.sub = "99"  # user 99, not owner of execution 42
    mock_payload.ad_groups = []

    with patch('core.consumers.verify_token', return_value=mock_payload):
        with patch.object(ExecutionConsumer, '_check_execution_access', new=AsyncMock(return_value=False)):
            connected, _ = await communicator.connect()
            assert connected

            await communicator.send_json_to({"type": "auth", "token": "valid_token"})

            # Base class sends auth_success before ExecutionConsumer checks access
            response = await communicator.receive_json_from()
            assert response["type"] == "auth_success"

            # ExecutionConsumer then denies access → close(4003)
            close_msg = await communicator.receive_output()
            assert close_msg["type"] == "websocket.close"
            assert close_msg.get("code") == 4003

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_ws_integration_authorized_owner_connection_stays_open():
    """59-2-o (AC-5): Full WebSocket stack — authorized owner connection stays open after auth.

    Tests the complete consumer lifecycle via WebsocketCommunicator:
    connect → send auth → auth_success → access granted → connection remains open.
    """
    from channels.testing import WebsocketCommunicator
    from channels.routing import URLRouter
    from django.urls import re_path
    from unittest.mock import MagicMock

    application = URLRouter([
        re_path(r"ws/executions/(?P<execution_id>[0-9]+)$", ExecutionConsumer.as_asgi()),
    ])

    communicator = WebsocketCommunicator(application, "ws/executions/42")

    mock_payload = MagicMock()
    mock_payload.sub = "10"  # user 10 = owner of execution 42
    mock_payload.ad_groups = []

    with patch('core.consumers.verify_token', return_value=mock_payload):
        with patch.object(ExecutionConsumer, '_check_execution_access', new=AsyncMock(return_value=True)):
            connected, _ = await communicator.connect()
            assert connected

            await communicator.send_json_to({"type": "auth", "token": "valid_token"})

            # Should receive auth_success
            response = await communicator.receive_json_from()
            assert response["type"] == "auth_success"

            # Connection must remain open — no close(4003)
            assert await communicator.receive_nothing()

    await communicator.disconnect()
