"""
ASGI config for idp_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

Story 22.13: Added WebSocket routing via Django Channels ProtocolTypeRouter.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'idp_backend.settings')

django_asgi_app = get_asgi_application()

from idp_backend.routing import websocket_urlpatterns  # noqa: E402 — after Django setup

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter(websocket_urlpatterns),
})
