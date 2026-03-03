"""
WebSocket URL routing.

Story 22.13: WebSocket endpoints use message-based JWT authentication
(no token in URL query parameters).
"""

from django.urls import re_path

from executions.consumers import DashboardConsumer, ExecutionConsumer

websocket_urlpatterns = [
    re_path(r"ws/executions/(?P<execution_id>[0-9]+)$", ExecutionConsumer.as_asgi()),  # type: ignore[arg-type]
    re_path(r"ws/dashboard$", DashboardConsumer.as_asgi()),  # type: ignore[arg-type]
]
