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

    def test_schema_has_api_key_auth_security_scheme(self):
        """Story 44.9 AC1/AC5: Le schéma contient le security scheme apiKeyAuth avec description."""
        client = APIClient()
        schema = _get_schema(client)
        components = schema.get('components', {})
        security_schemes = components.get('securitySchemes', {})
        assert 'apiKeyAuth' in security_schemes
        api_key = security_schemes['apiKeyAuth']
        assert api_key['type'] == 'apiKey'
        assert api_key['in'] == 'header'
        assert api_key['name'] == 'X-API-Key'
        # M1: description doit être présente (AC1 spécifie le format complet)
        assert 'description' in api_key, "apiKeyAuth doit inclure une description"
        assert len(api_key['description']) > 0

    def test_auth_token_endpoint_documents_x_api_key(self):
        """Story 44.9 AC5: POST /auth/token documente le header X-API-Key requis."""
        client = APIClient()
        schema = _get_schema(client)
        paths = schema.get('paths', {})
        # Path may be /auth/token/ or /api/v1/auth/token/ depending on SCHEMA_PATH_PREFIX
        token_path = paths.get('/auth/token/') or paths.get('/api/v1/auth/token/')
        assert token_path is not None, "POST /auth/token doit être documenté dans le schéma"
        post_op = token_path.get('post')
        assert post_op is not None, "POST /auth/token doit avoir une opération post"
        parameters = post_op.get('parameters', [])
        header_params = [p for p in parameters if p.get('in') == 'header' and p.get('name') == 'X-API-Key']
        assert len(header_params) >= 1, "POST /auth/token doit documenter le paramètre X-API-Key (header)"
        # H2: le paramètre doit être required=True (un header manquant → 401)
        assert header_params[0].get('required') is True, "X-API-Key doit être marqué required=True"

    def test_auth_token_endpoint_has_api_key_security(self):
        """Story 44.9 AC2: POST /auth/token est associé au scheme apiKeyAuth."""
        client = APIClient()
        schema = _get_schema(client)
        paths = schema.get('paths', {})
        token_path = paths.get('/auth/token/') or paths.get('/api/v1/auth/token/')
        assert token_path is not None, "POST /auth/token doit être documenté dans le schéma"
        post_op = token_path.get('post')
        assert post_op is not None
        security = post_op.get('security', [])
        api_key_schemes = [s for s in security if 'apiKeyAuth' in s]
        assert len(api_key_schemes) >= 1, "POST /auth/token doit référencer le scheme apiKeyAuth"

    def test_schema_description_contains_api_key_workflow(self):
        """Story 44.9 AC3: La description globale décrit le workflow API key en 3 étapes."""
        client = APIClient()
        schema = _get_schema(client)
        description = schema.get('info', {}).get('description', '')
        # Vérifier que le workflow en 3 étapes est documenté
        assert 'X-API-Key' in description, "La description doit mentionner X-API-Key"
        assert 'auth/token' in description, "La description doit mentionner POST /auth/token"
        # Vérifier la mention du rate limiting
        assert '10' in description, "La description doit mentionner le rate limit (10 req/min)"
        # Vérifier la présence d'un exemple curl exploitable directement depuis Swagger UI
        # (pas de lien vers fichier .md non accessible via navigateur)
        assert 'curl' in description, "La description doit inclure un exemple curl utilisable"

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
