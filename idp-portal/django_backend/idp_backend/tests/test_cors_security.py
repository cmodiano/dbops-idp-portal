"""
Story 30.5 — SEC-9: CORS correlation ID header standardization tests.
SEC-8: Celery credentials validation tests.
"""

import pytest
from django.conf import settings
from django.test import RequestFactory
from django.http import HttpResponse

from core.middleware import CorrelationIdMiddleware


class TestCORSCorrelationIDHeader:
    """SEC-9: CORS must include X-Correlation-ID."""

    def test_x_correlation_id_in_cors_allow_headers(self):
        """X-Correlation-ID must be in CORS_ALLOW_HEADERS."""
        assert 'x-correlation-id' in settings.CORS_ALLOW_HEADERS

    def test_x_correlation_id_in_cors_expose_headers(self):
        """X-Correlation-ID must be in CORS_EXPOSE_HEADERS."""
        assert 'X-Correlation-ID' in settings.CORS_EXPOSE_HEADERS

    def test_legacy_header_not_in_cors(self):
        """Legacy X-Idp-Request-Id should no longer be in CORS config."""
        assert 'x-idp-request-id' not in settings.CORS_ALLOW_HEADERS
        assert 'X-Idp-Request-Id' not in settings.CORS_EXPOSE_HEADERS


class TestCorrelationIDMiddlewareUnified:
    """SEC-9: Middleware reads X-Correlation-ID and responds with it."""

    def setup_method(self):
        self.factory = RequestFactory()
        self.middleware = CorrelationIdMiddleware(lambda req: HttpResponse("OK"))

    def test_reads_x_correlation_id_header(self):
        """Middleware should read X-Correlation-ID from request."""
        custom_id = 'test-sec9-correlation-123'
        request = self.factory.get('/api/v1/test', HTTP_X_CORRELATION_ID=custom_id)
        response = self.middleware(request)
        assert response['X-Correlation-ID'] == custom_id

    def test_reads_legacy_header_as_fallback(self):
        """Middleware should fallback to X-Idp-Request-Id for backward compat."""
        legacy_id = 'legacy-request-id-456'
        request = self.factory.get('/api/v1/test', HTTP_X_IDP_REQUEST_ID=legacy_id)
        response = self.middleware(request)
        assert response['X-Correlation-ID'] == legacy_id

    def test_prefers_x_correlation_id_over_legacy(self):
        """When both headers present, X-Correlation-ID takes priority."""
        request = self.factory.get(
            '/api/v1/test',
            HTTP_X_CORRELATION_ID='preferred-id',
            HTTP_X_IDP_REQUEST_ID='legacy-id',
        )
        response = self.middleware(request)
        assert response['X-Correlation-ID'] == 'preferred-id'

    def test_response_header_is_x_correlation_id(self):
        """Response must use X-Correlation-ID (not X-Idp-Request-Id)."""
        request = self.factory.get('/api/v1/test')
        response = self.middleware(request)
        assert 'X-Correlation-ID' in response


class TestCeleryCredentialsSecurity:
    """SEC-8: Celery tasks must not receive credentials as parameters."""

    def test_retry_workflow_step_no_credential_params(self):
        """retry_workflow_step task must not accept credential parameters."""
        import inspect
        from executions.tasks import retry_workflow_step
        # Get the wrapped function signature
        sig = inspect.signature(retry_workflow_step)
        param_names = set(sig.parameters.keys())
        credential_params = {'password', 'token', 'secret', 'credential', 'api_key'}
        assert param_names.isdisjoint(credential_params), (
            f"Celery task has credential params: {param_names & credential_params}"
        )

    def test_evaluate_waiting_gates_no_credential_params(self):
        """evaluate_waiting_gates task must not accept credential parameters."""
        import inspect
        from executions.tasks import evaluate_waiting_gates
        sig = inspect.signature(evaluate_waiting_gates)
        param_names = set(sig.parameters.keys())
        credential_params = {'password', 'token', 'secret', 'credential', 'api_key'}
        assert param_names.isdisjoint(credential_params)

    def test_poll_aap_job_status_no_credential_params(self):
        """poll_aap_job_status must not accept credential parameters."""
        import inspect
        from executions.tasks import poll_aap_job_status
        sig = inspect.signature(poll_aap_job_status)
        param_names = set(sig.parameters.keys())
        credential_params = {'password', 'token', 'secret', 'credential', 'api_key'}
        assert param_names.isdisjoint(credential_params)
