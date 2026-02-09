"""
Tests de validation du schéma OpenAPI (Story 22.20).
Vérifie que drf-spectacular génère un schéma valide et complet.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from django.urls import reverse
from rest_framework.test import APIClient


def _get_schema(client):
    """Fetch the OpenAPI schema and parse as JSON."""
    response = client.get(reverse('schema'), HTTP_ACCEPT='application/json')
    assert response.status_code == 200
    return json.loads(response.content)


@pytest.mark.django_db
class TestAPISchemaGeneration:
    """Tests de génération du schéma OpenAPI."""

    def test_schema_endpoint_returns_200(self):
        """AC8: Le schéma OpenAPI est accessible via /api/schema/."""
        client = APIClient()
        response = client.get(reverse('schema'))
        assert response.status_code == 200

    def test_schema_is_openapi_3(self):
        """AC8: Le schéma généré est OpenAPI 3.0+."""
        client = APIClient()
        schema = _get_schema(client)
        assert 'openapi' in schema
        assert schema['openapi'].startswith('3.')

    def test_schema_has_info_metadata(self):
        """AC3: Les métadonnées du projet sont configurées."""
        client = APIClient()
        schema = _get_schema(client)
        info = schema.get('info', {})
        assert info.get('title') == 'DBOps Portal API'
        assert info.get('version') == '1.0.0'
        assert 'description' in info

    def test_schema_has_security_schemes(self):
        """AC3: Les schémas d'authentification Bearer JWT sont configurés."""
        client = APIClient()
        schema = _get_schema(client)
        components = schema.get('components', {})
        security_schemes = components.get('securitySchemes', {})
        assert 'bearerAuth' in security_schemes
        bearer = security_schemes['bearerAuth']
        assert bearer['type'] == 'http'
        assert bearer['scheme'] == 'bearer'
        assert bearer['bearerFormat'] == 'JWT'

    def test_schema_has_paths(self):
        """Le schéma contient des endpoints documentés."""
        client = APIClient()
        schema = _get_schema(client)
        paths = schema.get('paths', {})
        assert len(paths) > 0, "Le schéma doit contenir au moins un endpoint"

    def test_critical_catalog_endpoints_documented(self):
        """AC5: Les endpoints catalog sont documentés."""
        client = APIClient()
        schema = _get_schema(client)
        paths = schema.get('paths', {})
        catalog_paths = [p for p in paths if 'catalog' in p or 'actions' in p or 'tags' in p]
        assert len(catalog_paths) > 0, "Catalog endpoints doivent être documentés"

    def test_critical_executions_endpoints_documented(self):
        """AC5: Les endpoints executions sont documentés."""
        client = APIClient()
        schema = _get_schema(client)
        paths = schema.get('paths', {})
        execution_paths = [p for p in paths if 'execution' in p]
        assert len(execution_paths) > 0, "Execution endpoints doivent être documentés"

    def test_critical_profiles_endpoints_documented(self):
        """AC5: Les endpoints profiles sont documentés."""
        client = APIClient()
        schema = _get_schema(client)
        paths = schema.get('paths', {})
        profile_paths = [p for p in paths if 'profile' in p]
        assert len(profile_paths) > 0, "Profile endpoints doivent être documentés"

    def test_schema_has_tags(self):
        """AC3: Les tags sont configurés pour organiser les endpoints."""
        client = APIClient()
        schema = _get_schema(client)
        tags = schema.get('tags', [])
        tag_names = {t['name'] for t in tags}
        assert 'catalog' in tag_names
        assert 'executions' in tag_names
        assert 'profiles' in tag_names


@pytest.mark.django_db
class TestSwaggerUIAccessible:
    """Tests d'accessibilité des interfaces de documentation."""

    def test_swagger_ui_returns_200(self):
        """AC6: Swagger UI est accessible."""
        client = APIClient()
        response = client.get(reverse('swagger-ui'))
        assert response.status_code == 200

    def test_redoc_returns_200(self):
        """AC7: ReDoc est accessible."""
        client = APIClient()
        response = client.get(reverse('redoc'))
        assert response.status_code == 200


class TestSchemaValidationCLI:
    """Tests de validation CLI du schéma."""

    def test_schema_validate_command(self):
        """AC9: `python manage.py spectacular --validate` passe sans erreur fatale."""
        manage_py = Path(__file__).resolve().parent.parent / 'manage.py'
        result = subprocess.run(
            [sys.executable, str(manage_py), 'spectacular', '--validate', '--skip-checks'],
            capture_output=True,
            text=True,
            cwd=str(manage_py.parent),
            env={
                **__import__('os').environ,
                'DJANGO_SETTINGS_MODULE': 'idp_backend.test_settings',
            },
        )
        assert result.returncode == 0, f"Schema validation failed:\n{result.stderr}"

    def test_schema_file_generation(self):
        """AC8: Le fichier de schéma peut être généré."""
        manage_py = Path(__file__).resolve().parent.parent / 'manage.py'
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.yml', delete=True) as f:
            result = subprocess.run(
                [sys.executable, str(manage_py), 'spectacular', '--file', f.name, '--skip-checks'],
                capture_output=True,
                text=True,
                cwd=str(manage_py.parent),
                env={
                    **__import__('os').environ,
                    'DJANGO_SETTINGS_MODULE': 'idp_backend.test_settings',
                },
            )
            assert result.returncode == 0, f"Schema file generation failed:\n{result.stderr}"


@pytest.mark.django_db
class TestSchemaAuthenticationConfig:
    """Tests de configuration d'authentification dans le schéma."""

    def test_security_requirement_on_schema(self):
        """AC3: La sécurité Bearer JWT est définie (globalement ou via securitySchemes)."""
        client = APIClient()
        schema = _get_schema(client)
        # Check global security OR securitySchemes
        security = schema.get('security', [])
        security_schemes = schema.get('components', {}).get('securitySchemes', {})
        has_global_security = any('bearerAuth' in s for s in security)
        has_security_scheme = 'bearerAuth' in security_schemes
        assert has_global_security or has_security_scheme, \
            "Le schéma doit avoir bearerAuth configuré"

    def test_schema_endpoint_count_minimum(self):
        """AC5: Au moins 15 endpoints documentés."""
        client = APIClient()
        schema = _get_schema(client)
        paths = schema.get('paths', {})
        operation_count = sum(
            len([m for m in path_item if m in ('get', 'post', 'put', 'patch', 'delete')])
            for path_item in paths.values()
        )
        assert operation_count >= 15, \
            f"Au moins 15 opérations attendues, trouvées: {operation_count}"
