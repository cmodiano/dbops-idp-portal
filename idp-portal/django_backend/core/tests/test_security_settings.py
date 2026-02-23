"""Tests de sécurité fail-fast pour SECRET_KEY et JWT_SECRET_KEY (Story 30.1, AC7).

These tests validate that settings.py raises ImproperlyConfigured when critical
secrets are missing. Since settings.py is executed at module import time, we use
subprocess to test in an isolated Python process with controlled env vars.

Mocking strategy for CI:
    - Tests use subprocess with a clean environment (no inherited secrets)
    - The subprocess runs a minimal Python script that imports settings.py
    - If ImproperlyConfigured is raised, the subprocess exits with code 0 (test passes)
    - If no error is raised, the subprocess exits with code 1 (test fails)
"""
import os
import subprocess
import sys


# Path to manage.py parent directory (django_backend/)
DJANGO_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run_settings_check(env_overrides: dict, expect_error: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess that imports settings.py with specific env vars.

    Args:
        env_overrides: Dict of env vars to set. Missing keys => not set.
        expect_error: Whether we expect ImproperlyConfigured to be raised.

    Returns:
        CompletedProcess with stdout/stderr.
    """
    # Build a clean env with only what we need
    env = {
        'PATH': os.environ.get('PATH', ''),
        'HOME': os.environ.get('HOME', ''),
        'PYTHONPATH': DJANGO_BACKEND_DIR,
        'DJANGO_SETTINGS_MODULE': 'idp_backend.settings',
    }
    env.update(env_overrides)

    script = """
import sys
try:
    import django
    from django.conf import settings
    # Force settings evaluation
    _ = settings.SECRET_KEY
    _ = settings.JWT_SECRET_KEY
    print("OK: settings loaded successfully")
    sys.exit(0)
except Exception as e:
    etype = type(e).__name__
    print(f"ERROR: {etype}: {e}")
    if "ImproperlyConfigured" in etype:
        sys.exit(42)  # Expected error code
    sys.exit(1)  # Unexpected error
"""
    result = subprocess.run(
        [sys.executable, '-c', script],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        cwd=DJANGO_BACKEND_DIR,
    )
    return result


class TestSecretKeyFailFast:
    """SECRET_KEY must raise ImproperlyConfigured when absent or empty (AC5)."""

    def test_missing_secret_key_raises_improperly_configured(self):
        """Import settings.py without SECRET_KEY → ImproperlyConfigured."""
        result = _run_settings_check({
            # Provide JWT_SECRET_KEY so it doesn't fail on that first
            'JWT_SECRET_KEY': 'test-jwt-secret',
        })
        assert result.returncode == 42, (
            f"Expected ImproperlyConfigured (exit 42), got exit {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert 'SECRET_KEY' in result.stdout or 'SECRET_KEY' in result.stderr

    def test_empty_secret_key_raises_improperly_configured(self):
        """Import settings.py with SECRET_KEY='' → ImproperlyConfigured."""
        result = _run_settings_check({
            'SECRET_KEY': '',
            'JWT_SECRET_KEY': 'test-jwt-secret',
        })
        assert result.returncode == 42, (
            f"Expected ImproperlyConfigured (exit 42), got exit {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_valid_secret_key_loads_successfully(self):
        """Import settings.py with valid secrets → no error."""
        result = _run_settings_check({
            'SECRET_KEY': 'test-secret-key-valid',
            'JWT_SECRET_KEY': 'test-jwt-secret-valid',
        })
        assert result.returncode == 0, (
            f"Expected success (exit 0), got exit {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


class TestJwtSecretKeyFailFast:
    """JWT_SECRET_KEY must raise ImproperlyConfigured when absent or empty (AC6)."""

    def test_missing_jwt_secret_key_raises_improperly_configured(self):
        """Import settings.py without JWT_SECRET_KEY → ImproperlyConfigured."""
        result = _run_settings_check({
            'SECRET_KEY': 'test-secret-key',
            # JWT_SECRET_KEY intentionally not set
        })
        assert result.returncode == 42, (
            f"Expected ImproperlyConfigured (exit 42), got exit {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert 'JWT_SECRET_KEY' in result.stdout or 'JWT_SECRET_KEY' in result.stderr

    def test_empty_jwt_secret_key_raises_improperly_configured(self):
        """Import settings.py with JWT_SECRET_KEY='' → ImproperlyConfigured."""
        result = _run_settings_check({
            'SECRET_KEY': 'test-secret-key',
            'JWT_SECRET_KEY': '',
        })
        assert result.returncode == 42, (
            f"Expected ImproperlyConfigured (exit 42), got exit {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


class TestBothSecretsRequired:
    """Integration test: Django refuses to start without both secrets."""

    def test_django_startup_fails_without_secrets(self):
        """Django management command fails gracefully without secrets."""
        env = {
            'PATH': os.environ.get('PATH', ''),
            'HOME': os.environ.get('HOME', ''),
            'PYTHONPATH': DJANGO_BACKEND_DIR,
            'DJANGO_SETTINGS_MODULE': 'idp_backend.settings',
        }
        result = subprocess.run(
            [sys.executable, '-m', 'django', 'check', '--deploy'],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=DJANGO_BACKEND_DIR,
        )
        # Should fail because SECRET_KEY is missing
        assert result.returncode != 0
        assert 'ImproperlyConfigured' in result.stderr or 'SECRET_KEY' in result.stderr
