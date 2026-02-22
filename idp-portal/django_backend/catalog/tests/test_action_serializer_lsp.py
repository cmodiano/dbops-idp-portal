"""Tests for ActionSerializer LSP compliance (Story 34.3 - SOLID-BE-6).

Verifies that ActionSerializer does NOT override create() and update() with
NotImplementedError — LSP violation removed.
"""
import inspect

import pytest
from rest_framework import serializers

from catalog.serializers import ActionSerializer


class TestActionSerializerLSP:
    """Story 34.3 - SOLID-BE-6: ActionSerializer must not raise NotImplementedError."""

    def test_action_serializer_no_notimplementederror(self) -> None:
        """AC6: create() and update() are inherited from ModelSerializer, not overridden."""
        source = inspect.getsource(ActionSerializer)
        assert 'raise NotImplementedError' not in source, (
            "ActionSerializer must not raise NotImplementedError in create() or update()"
        )

    def test_action_serializer_create_is_inherited(self) -> None:
        """create() method is inherited from ModelSerializer (not overridden in ActionSerializer)."""
        assert 'create' not in ActionSerializer.__dict__, (
            "ActionSerializer.create should be inherited from ModelSerializer, not overridden"
        )

    def test_action_serializer_update_is_inherited(self) -> None:
        """update() method is inherited from ModelSerializer (not overridden in ActionSerializer)."""
        assert 'update' not in ActionSerializer.__dict__, (
            "ActionSerializer.update should be inherited from ModelSerializer, not overridden"
        )

    def test_action_serializer_inherits_from_model_serializer(self) -> None:
        """ActionSerializer inherits from serializers.ModelSerializer."""
        assert issubclass(ActionSerializer, serializers.ModelSerializer)
