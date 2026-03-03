"""
Tests unitaires pour validate_schedule_config() — Story 57.15 AC #9.

Couvre : source valide/invalide, schedule_parameter_name manquant,
fixed_offset invalide, pattern_type manquant, schedule_config non-dict.
"""
import pytest
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from catalog.validators import validate_schedule_config


class TestValidateScheduleConfigValid(SimpleTestCase):
    """Tests de validation réussie."""

    def test_valid_parameter_source(self):
        """schedule_source=parameter avec schedule_parameter_name valide."""
        validate_schedule_config({
            'schedule_source': 'parameter',
            'schedule_parameter_name': 'scheduled_at',
        })  # No exception

    def test_valid_fixed_offset_days(self):
        """schedule_source=fixed_offset avec offset +3d valide."""
        validate_schedule_config({
            'schedule_source': 'fixed_offset',
            'fixed_offset': '+3d',
        })

    def test_valid_fixed_offset_hours(self):
        """schedule_source=fixed_offset avec offset +12h valide."""
        validate_schedule_config({
            'schedule_source': 'fixed_offset',
            'fixed_offset': '+12h',
        })

    def test_valid_fixed_offset_weeks(self):
        """schedule_source=fixed_offset avec offset +2w valide."""
        validate_schedule_config({
            'schedule_source': 'fixed_offset',
            'fixed_offset': '+2w',
        })

    def test_valid_fixed_offset_minutes(self):
        """schedule_source=fixed_offset avec offset +30m valide."""
        validate_schedule_config({
            'schedule_source': 'fixed_offset',
            'fixed_offset': '+30m',
        })

    def test_valid_recurring_source(self):
        """schedule_source=recurring avec pattern_type valide."""
        validate_schedule_config({
            'schedule_source': 'recurring',
            'recurring_pattern': {
                'pattern_type': 'daily',
                'pattern_config': {'hour': 9, 'minute': 0},
            },
        })


class TestValidateScheduleConfigInvalid(SimpleTestCase):
    """Tests de validation échouée."""

    def test_not_dict_raises(self):
        """schedule_config non-dict lève ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_schedule_config("not-a-dict")
        assert 'objet' in str(exc_info.value.detail).lower() or 'dict' in str(exc_info.value.detail).lower()

    def test_invalid_schedule_source_raises(self):
        """schedule_source inconnu lève ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_schedule_config({'schedule_source': 'invalid_source'})
        assert 'invalid_source' in str(exc_info.value.detail)

    def test_missing_schedule_source_raises(self):
        """schedule_source absent (None) lève ValidationError."""
        with pytest.raises(ValidationError):
            validate_schedule_config({'fixed_offset': '+1d'})  # pas de schedule_source

    def test_parameter_source_missing_parameter_name_raises(self):
        """schedule_source=parameter sans schedule_parameter_name lève ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_schedule_config({'schedule_source': 'parameter'})
        assert 'schedule_parameter_name' in str(exc_info.value.detail)

    def test_parameter_source_empty_parameter_name_raises(self):
        """schedule_source=parameter avec schedule_parameter_name vide lève ValidationError."""
        with pytest.raises(ValidationError):
            validate_schedule_config({
                'schedule_source': 'parameter',
                'schedule_parameter_name': '',
            })

    def test_fixed_offset_missing_offset_raises(self):
        """schedule_source=fixed_offset sans fixed_offset lève ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_schedule_config({'schedule_source': 'fixed_offset'})
        assert 'fixed_offset' in str(exc_info.value.detail)

    def test_fixed_offset_invalid_format_no_plus_raises(self):
        """schedule_source=fixed_offset sans + lève ValidationError."""
        with pytest.raises(ValidationError):
            validate_schedule_config({'schedule_source': 'fixed_offset', 'fixed_offset': '1d'})

    def test_fixed_offset_invalid_format_bad_unit_raises(self):
        """schedule_source=fixed_offset avec unité invalide (x) lève ValidationError."""
        with pytest.raises(ValidationError):
            validate_schedule_config({'schedule_source': 'fixed_offset', 'fixed_offset': '+1x'})

    def test_fixed_offset_invalid_format_uppercase_unit_raises(self):
        """schedule_source=fixed_offset avec unité majuscule (+1D) lève ValidationError."""
        with pytest.raises(ValidationError):
            validate_schedule_config({'schedule_source': 'fixed_offset', 'fixed_offset': '+1D'})

    def test_fixed_offset_invalid_format_no_value_raises(self):
        """schedule_source=fixed_offset sans valeur numérique lève ValidationError."""
        with pytest.raises(ValidationError):
            validate_schedule_config({'schedule_source': 'fixed_offset', 'fixed_offset': '+d'})

    def test_recurring_missing_pattern_type_raises(self):
        """schedule_source=recurring sans pattern_type lève ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_schedule_config({
                'schedule_source': 'recurring',
                'recurring_pattern': {'pattern_config': {}},  # pas de pattern_type
            })
        assert 'pattern_type' in str(exc_info.value.detail)

    def test_recurring_missing_recurring_pattern_key_raises(self):
        """schedule_source=recurring sans recurring_pattern lève ValidationError."""
        with pytest.raises(ValidationError):
            validate_schedule_config({'schedule_source': 'recurring'})

    def test_empty_dict_schedule_source_raises(self):
        """schedule_config vide (sans schedule_source) lève ValidationError."""
        with pytest.raises(ValidationError):
            validate_schedule_config({})
