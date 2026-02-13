"""
WebSocket consumer for real-time execution updates.

Story 22.13: Inherits message-based JWT auth from AuthenticatedWebSocketConsumer.
"""

from core.consumers import AuthenticatedWebSocketConsumer


class ExecutionConsumer(AuthenticatedWebSocketConsumer):
    """WebSocket endpoint: /ws/executions/{execution_id}

    After authentication, forwards real-time step_update,
    execution_complete, and execution_failed messages.
    """

    async def connect(self):
        self.execution_id = self.scope["url_route"]["kwargs"].get("execution_id")
        await super().connect()

    async def handle_authenticated_message(self, message: dict):
        pass


class DashboardConsumer(AuthenticatedWebSocketConsumer):
    """WebSocket endpoint: /ws/dashboard

    After authentication, forwards real-time execution_update messages
    for the dashboard.
    """

    async def handle_authenticated_message(self, message: dict):
        pass
