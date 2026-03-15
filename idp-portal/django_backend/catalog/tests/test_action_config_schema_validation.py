"""Tests pour la validation action_config via action_config_schema (Story 82.8, AC3)."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from rest_framework import serializers as drf_serializers

from catalog.serializers.action import _validate_action_config_schema


class TestValidateActionConfigSchema:
    """Tests unitaires pour _validate_action_config_schema."""

    def test_empty_platform_code_is_noop(self):
        """Pas de plateforme → pas de validation."""
        # Should not raise
        _validate_action_config_schema('', {'some': 'config'})

    def test_none_platform_code_is_noop(self):
        """Platform None → pas de validation."""
        _validate_action_config_schema(None, {'some': 'config'})  # type: ignore[arg-type]

    def test_unknown_platform_is_noop(self):
        """Plateforme inconnue dans le registry → pas de validation (silencieux)."""
        from platforms.registry import platform_registry
        with patch.object(platform_registry, 'get', side_effect=KeyError('unknown')):
            # Should not raise
            _validate_action_config_schema('unknown_platform', {'some': 'config'})

    def test_empty_schema_is_noop(self):
        """Schéma vide {} → pas de validation (aucune contrainte)."""
        defn_mock = MagicMock()
        defn_mock.action_config_schema = {}
        from platforms.registry import platform_registry
        with patch.object(platform_registry, 'get', return_value=defn_mock):
            # Should not raise even with invalid data
            _validate_action_config_schema('aap', {'invalid': 'anything'})

    def test_none_schema_is_noop(self):
        """Schéma None → pas de validation."""
        defn_mock = MagicMock()
        defn_mock.action_config_schema = None
        from platforms.registry import platform_registry
        with patch.object(platform_registry, 'get', return_value=defn_mock):
            _validate_action_config_schema('aap', {'invalid': 'anything'})

    def test_nonempty_schema_valid_config_passes(self):
        """Schéma non vide + config valide → pas d'erreur."""
        defn_mock = MagicMock()
        defn_mock.action_config_schema = {
            'type': 'object',
            'properties': {'target_host': {'type': 'string'}},
            'required': ['target_host'],
        }
        from platforms.registry import platform_registry
        with patch.object(platform_registry, 'get', return_value=defn_mock):
            # Should not raise
            _validate_action_config_schema('aap', {'target_host': 'server01'})

    def test_nonempty_schema_invalid_config_raises(self):
        """Schéma non vide + config invalide → ValidationError."""
        defn_mock = MagicMock()
        defn_mock.action_config_schema = {
            'type': 'object',
            'properties': {'target_host': {'type': 'string'}},
            'required': ['target_host'],
        }
        from platforms.registry import platform_registry
        with patch.object(platform_registry, 'get', return_value=defn_mock):
            with pytest.raises(drf_serializers.ValidationError) as exc_info:
                _validate_action_config_schema('aap', {})  # manque target_host
            assert 'action_config' in exc_info.value.detail

    def test_none_action_config_treated_as_empty_dict(self):
        """action_config None traité comme {} pour la validation."""
        defn_mock = MagicMock()
        defn_mock.action_config_schema = {
            'type': 'object',
            'properties': {'target_host': {'type': 'string'}},
            'required': ['target_host'],
        }
        from platforms.registry import platform_registry
        with patch.object(platform_registry, 'get', return_value=defn_mock):
            with pytest.raises(drf_serializers.ValidationError):
                _validate_action_config_schema('aap', None)

    def test_schema_with_wrong_type_raises(self):
        """Schéma non vide + config avec mauvais type → ValidationError."""
        defn_mock = MagicMock()
        defn_mock.action_config_schema = {
            'type': 'object',
            'properties': {'timeout': {'type': 'integer'}},
            'required': ['timeout'],
        }
        from platforms.registry import platform_registry
        with patch.object(platform_registry, 'get', return_value=defn_mock):
            with pytest.raises(drf_serializers.ValidationError) as exc_info:
                _validate_action_config_schema('aap', {'timeout': 'not_an_int'})
            assert 'action_config' in exc_info.value.detail

    def test_malformed_schema_raises_validation_error(self):
        """Schéma malformé (SchemaError) → ValidationError avec message clair (M1 code review)."""
        defn_mock = MagicMock()
        defn_mock.action_config_schema = {
            'type': 'object',
            'properties': {'x': {'type': 'invalid_type'}},  # type invalide → SchemaError
        }
        from platforms.registry import platform_registry
        with patch.object(platform_registry, 'get', return_value=defn_mock):
            with pytest.raises(drf_serializers.ValidationError) as exc_info:
                _validate_action_config_schema('aap', {'x': 'value'})
            assert 'action_config' in exc_info.value.detail


class TestValidateActionConfigSchemaNormalization:
    """Story 83-13 AC5 : normalisation du platform_code avant lookup dans le registry."""

    def test_uppercase_aap_normalized_and_validated_valid(self):
        """'AAP' normalisé → 'aap' → schema AAP validé avec config valide."""
        # Utilise le vrai registry (pas de mock)
        # Config valide pour AAP (template_id requis)
        _validate_action_config_schema('AAP', {'template_id': 42})

    def test_uppercase_aap_normalized_and_validated_invalid(self):
        """'AAP' normalisé → 'aap' → schema AAP validé avec config invalide → ValidationError."""
        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            _validate_action_config_schema('AAP', {'template_id': 'not_an_int'})
        assert 'action_config' in exc_info.value.detail

    def test_azure_devops_spaces_normalized(self):
        """'Azure DevOps' normalisé → 'azure_devops' → schema vide → no-op."""
        # azure_devops a un action_config_schema vide → pas de ValidationError
        _validate_action_config_schema('Azure DevOps', {'anything': 'goes'})

    def test_tower_uppercase_normalized(self):
        """'Tower' normalisé → 'tower' → schema Tower validé avec config valide."""
        _validate_action_config_schema('Tower', {'template_id': 1})

    def test_tower_normalized_invalid_config(self):
        """'Tower' normalisé → 'tower' → schema Tower validé avec config invalide → ValidationError."""
        with pytest.raises(drf_serializers.ValidationError):
            _validate_action_config_schema('Tower', {'template_id': -5})  # minimum: 1


class TestActionSerializerIntegration:
    """Tests d'intégration : _validate_action_config_schema est appelée depuis ActionSerializer (M2 code review).

    Story 83-13: schema validation uniquement si action_config est explicitement fourni (pas None).
    """

    def test_action_serializer_validate_calls_schema_validation_when_platform_and_action_config_set(self):
        """ActionSerializer.validate() appelle _validate_action_config_schema si platform ET action_config présents."""
        import catalog.serializers.action as action_module

        with patch.object(action_module, '_validate_action_config_schema') as mock_validate:
            from catalog.serializers.action import ActionSerializer
            s = ActionSerializer()
            data = {'platform': 'aap', 'action_config': {'template_id': 42}}
            try:
                s.validate(data)
            except Exception:
                pass  # D'autres validations peuvent échouer — on vérifie juste l'appel
            mock_validate.assert_called_once_with('aap', {'template_id': 42})

    def test_action_serializer_validate_skips_schema_validation_when_no_action_config(self):
        """ActionSerializer.validate() ne valide pas le schema si action_config est absent (None)."""
        import catalog.serializers.action as action_module

        with patch.object(action_module, '_validate_action_config_schema') as mock_validate:
            from catalog.serializers.action import ActionSerializer
            s = ActionSerializer()
            data = {'platform': 'aap'}  # action_config absent → pas de validation
            try:
                s.validate(data)
            except Exception:
                pass
            mock_validate.assert_not_called()

    def test_action_serializer_validate_skips_schema_validation_when_no_platform(self):
        """ActionSerializer.validate() ne doit pas appeler _validate_action_config_schema si pas de platform."""
        import catalog.serializers.action as action_module

        with patch.object(action_module, '_validate_action_config_schema') as mock_validate:
            from catalog.serializers.action import ActionSerializer
            s = ActionSerializer()
            data = {}
            try:
                s.validate(data)
            except Exception:
                pass
            mock_validate.assert_not_called()
