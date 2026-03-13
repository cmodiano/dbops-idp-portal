"""
Tests Story 78.3 — Alignement modèle/schéma ExecutionStep.config_step_id

AC1 : Le champ config_step_id est un CharField(max_length=255)
AC3 : Round-trip persistance (None, valeur courte, 255 chars, rejet 256+)
"""
import uuid

import pytest
from django.core.exceptions import ValidationError

from executions.models import ExecutionStep
from tests.factories import ExecutionStepFactory


pytestmark = pytest.mark.django_db


class TestAC1FieldIntrospection:
    """AC1 : config_step_id est CharField(max_length=255)."""

    def test_field_is_charfield(self):
        field = ExecutionStep._meta.get_field("config_step_id")
        assert field.__class__.__name__ == "CharField"

    def test_field_max_length_255(self):
        field = ExecutionStep._meta.get_field("config_step_id")
        assert field.max_length == 255

    def test_field_nullable(self):
        field = ExecutionStep._meta.get_field("config_step_id")
        assert field.null is True
        assert field.blank is True

    def test_field_db_column(self):
        field = ExecutionStep._meta.get_field("config_step_id")
        assert field.db_column == "CONFIG_STEP_ID"


class TestAC3Persistence:
    """AC3 : round-trip persistance avec différentes longueurs."""

    def test_round_trip_none(self):
        """AC3a : persistance avec config_step_id=None."""
        step = ExecutionStepFactory(config_step_id=None)
        step.refresh_from_db()
        assert step.config_step_id is None

    def test_round_trip_empty_string(self):
        """AC3a-bis : persistance avec valeur vide (chaîne vide)."""
        step = ExecutionStepFactory(config_step_id="")
        step.refresh_from_db()
        assert step.config_step_id == ""

    def test_round_trip_short_value(self):
        """AC3b : persistance avec valeur courte (UUID 36 chars)."""
        value = str(uuid.uuid4())
        step = ExecutionStepFactory(config_step_id=value)
        step.refresh_from_db()
        assert step.config_step_id == value

    def test_round_trip_max_length(self):
        """AC3c : persistance avec valeur exactement 255 caractères."""
        value = "x" * 255
        step = ExecutionStepFactory(config_step_id=value)
        step.refresh_from_db()
        assert step.config_step_id == value
        assert len(step.config_step_id) == 255

    def test_validation_rejects_over_max_length(self):
        """AC3d : Django rejette une valeur de 256+ caractères via full_clean()."""
        step = ExecutionStepFactory.build(config_step_id="y" * 256)
        with pytest.raises(ValidationError) as exc_info:
            step.full_clean()
        assert "config_step_id" in exc_info.value.message_dict
