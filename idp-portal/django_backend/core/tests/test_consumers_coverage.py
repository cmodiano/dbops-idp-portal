"""
Tests de couverture pour core/consumers.py (Story 55).
Couvre les lignes manquantes :
  - 33-34 : text_data is None → close(4002) + return
  - 72    : handle_authenticated_message() appelé après auth réussie
  - 76    : pass dans handle_authenticated_message (méthode de base)
"""
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock


class TestAuthenticatedWebSocketConsumerCoverage:
    """Tests async pour core.consumers.AuthenticatedWebSocketConsumer."""

    def _make_consumer(self):
        """Instancie le consumer avec les méthodes WS mockées."""
        from core.consumers import AuthenticatedWebSocketConsumer

        consumer = AuthenticatedWebSocketConsumer()
        consumer.accept = AsyncMock()
        consumer.close = AsyncMock()
        consumer.send = AsyncMock()
        consumer.authenticated = False
        consumer.user_id = None
        consumer.ad_groups = []
        return consumer

    def _make_valid_payload(self, user_id="user-1", ad_groups=None):
        payload = MagicMock()
        payload.sub = user_id
        payload.ad_groups = ad_groups or ["group1"]
        return payload

    @pytest.mark.asyncio
    async def test_receive_none_text_data_closes_4002(self):
        """Lignes 33-34 : text_data=None → close(4002) + return immédiat."""
        consumer = self._make_consumer()

        await consumer.receive(text_data=None)

        consumer.close.assert_awaited_once_with(code=4002)

    @pytest.mark.asyncio
    async def test_receive_none_text_does_not_process_further(self):
        """Lignes 33-34 : text_data=None → send() jamais appelé."""
        consumer = self._make_consumer()

        await consumer.receive(text_data=None)

        consumer.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_authenticated_message_dispatched_after_auth(self):
        """Ligne 72 : après auth, les messages métier sont dispatché à handle_authenticated_message."""
        consumer = self._make_consumer()

        # Simuler une session déjà authentifiée
        consumer.authenticated = True
        consumer.user_id = "user-42"

        # Patcher handle_authenticated_message pour capturer l'appel
        consumer.handle_authenticated_message = AsyncMock()

        business_message = {"type": "subscribe", "channel": "executions"}
        await consumer.receive(text_data=json.dumps(business_message))

        consumer.handle_authenticated_message.assert_awaited_once_with(business_message)

    @pytest.mark.asyncio
    async def test_handle_authenticated_message_base_is_noop(self):
        """Ligne 76 : handle_authenticated_message de base → pass (aucune action)."""
        consumer = self._make_consumer()

        # Appeler directement la méthode de base (pas de subclass override)
        await consumer.handle_authenticated_message({"type": "any"})
        # Aucune exception et aucun appel supplémentaire
        consumer.send.assert_not_awaited()
        consumer.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_receive_invalid_json_closes_4002(self):
        """Ligne 40 : JSON invalide → close(4002)."""
        consumer = self._make_consumer()

        await consumer.receive(text_data="not_json{{{")

        consumer.close.assert_awaited_once_with(code=4002)

    @pytest.mark.asyncio
    async def test_receive_first_message_not_auth_closes_4001(self):
        """Ligne 46 : premier message pas de type 'auth' → close(4001)."""
        consumer = self._make_consumer()

        await consumer.receive(text_data=json.dumps({"type": "subscribe"}))

        consumer.close.assert_awaited_once_with(code=4001)

    @pytest.mark.asyncio
    async def test_receive_missing_token_closes_4001(self):
        """Ligne 50-52 : token manquant → close(4001)."""
        consumer = self._make_consumer()

        await consumer.receive(text_data=json.dumps({"type": "auth"}))

        consumer.close.assert_awaited_once_with(code=4001)

    @pytest.mark.asyncio
    async def test_receive_invalid_token_closes_4001(self):
        """Lignes 55-59 : token invalide (verify_token=None) → close(4001)."""
        consumer = self._make_consumer()

        with patch('core.consumers.verify_token', return_value=None):
            await consumer.receive(text_data=json.dumps({"type": "auth", "token": "bad_token"}))

        consumer.close.assert_awaited_once_with(code=4001)

    @pytest.mark.asyncio
    async def test_receive_valid_auth_sends_auth_success(self):
        """Lignes 61-69 : auth valide → send auth_success avec user_id."""
        consumer = self._make_consumer()
        payload = self._make_valid_payload(user_id="user-99")

        with patch('core.consumers.verify_token', return_value=payload):
            await consumer.receive(text_data=json.dumps({"type": "auth", "token": "good_token"}))

        consumer.send.assert_awaited_once()
        call_args = consumer.send.call_args
        sent_data = json.loads(call_args[1]["text_data"])
        assert sent_data["type"] == "auth_success"
        assert sent_data["user_id"] == "user-99"
        assert consumer.authenticated is True

    @pytest.mark.asyncio
    async def test_connect_initializes_state(self):
        """Lignes 26-29 : connect() → accept() + state initialisé."""
        consumer = self._make_consumer()

        await consumer.connect()

        consumer.accept.assert_awaited_once()
        assert consumer.authenticated is False
        assert consumer.user_id is None
        assert consumer.ad_groups == []

    @pytest.mark.asyncio
    async def test_disconnect_is_noop(self):
        """Ligne 79 : disconnect() → pass, aucune exception."""
        consumer = self._make_consumer()
        await consumer.disconnect(code=1000)  # Ne doit pas lever
