"""
Tests for BUG-BE-3: structlog bind user_id BEFORE get_response().
Story 30.3 — AC2.

Verifies that user_id is bound in structlog contextvars BEFORE get_response()
so that all logs generated during request processing contain user_id.
"""

from unittest.mock import MagicMock, patch

import pytest
import structlog
from django.test import TestCase, RequestFactory
from django.http import HttpResponse

from core.middleware import CorrelationIdMiddleware, set_correlation_id
from tests.factories import UserFactory


@pytest.mark.django_db
class TestUserIdBindingBeforeGetResponse(TestCase):
    """Tests that user_id is bound before get_response in CorrelationIdMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory(profile='dbops')

    def tearDown(self):
        set_correlation_id(None)
        structlog.contextvars.unbind_contextvars('correlation_id', 'user_id')

    def test_authenticated_request_binds_user_id_before_get_response(self):
        """user_id should be in structlog contextvars DURING get_response processing."""
        captured_contextvars = {}

        def mock_get_response(request):
            # Capture structlog contextvars at the moment get_response is called
            ctx = structlog.contextvars.get_contextvars()
            captured_contextvars.update(ctx)
            return HttpResponse("OK")

        middleware = CorrelationIdMiddleware(mock_get_response)
        request = self.factory.get('/api/v1/test')
        request.user = self.user

        middleware(request)

        # user_id should have been bound BEFORE get_response
        assert 'user_id' in captured_contextvars
        assert captured_contextvars['user_id'] == str(self.user.pk)

    def test_authenticated_request_binds_correlation_id_and_user_id(self):
        """Both correlation_id and user_id should be present during request processing."""
        captured_contextvars = {}

        def mock_get_response(request):
            ctx = structlog.contextvars.get_contextvars()
            captured_contextvars.update(ctx)
            return HttpResponse("OK")

        middleware = CorrelationIdMiddleware(mock_get_response)
        request = self.factory.get('/api/v1/test')
        request.user = self.user

        middleware(request)

        assert 'correlation_id' in captured_contextvars
        assert 'user_id' in captured_contextvars

    def test_unauthenticated_request_no_user_id_in_context(self):
        """Unauthenticated request should not have user_id in structlog contextvars."""
        captured_contextvars = {}

        def mock_get_response(request):
            ctx = structlog.contextvars.get_contextvars()
            captured_contextvars.update(ctx)
            return HttpResponse("OK")

        middleware = CorrelationIdMiddleware(mock_get_response)
        request = self.factory.get('/api/v1/test')
        # Anonymous user mock
        request.user = MagicMock()
        request.user.is_authenticated = False

        middleware(request)

        assert 'correlation_id' in captured_contextvars
        assert 'user_id' not in captured_contextvars

    def test_contextvars_cleared_after_response(self):
        """After response, user_id and correlation_id should be unbound."""
        def mock_get_response(request):
            return HttpResponse("OK")

        middleware = CorrelationIdMiddleware(mock_get_response)
        request = self.factory.get('/api/v1/test')
        request.user = self.user

        middleware(request)

        # After the middleware completes, contextvars should be cleared
        ctx = structlog.contextvars.get_contextvars()
        assert 'user_id' not in ctx
        assert 'correlation_id' not in ctx
