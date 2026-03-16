"""Action mutex serializers."""
from __future__ import annotations

from typing import Any

from django.db.models import Q
from rest_framework import serializers

from catalog import models
from catalog.models import Action, ActionStatus, ActionMutex


class ActionMutexSerializer(serializers.ModelSerializer):
    """
    Story 25.5: Serializer for ActionMutex model.
    Used for GET /api/v1/admin/actions/{id}/mutex/ responses.
    """
    action_id = serializers.IntegerField(source='action.id', read_only=True)
    action_name = serializers.CharField(source='action.name', read_only=True)
    incompatible_with_id = serializers.IntegerField(source='incompatible_with.id', read_only=True)
    incompatible_with_name = serializers.CharField(source='incompatible_with.name', read_only=True)

    class Meta:
        model = models.ActionMutex
        fields = [
            'id', 'action_id', 'action_name',
            'incompatible_with_id', 'incompatible_with_name',
            'same_target', 'description', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ActionMutexCreateSerializer(serializers.ModelSerializer):
    """
    Story 25.5: Serializer for creating ActionMutex rules.
    Used for POST /api/v1/admin/actions/{id}/mutex/ requests.
    """
    class Meta:
        model = models.ActionMutex
        fields = ['incompatible_with_id', 'same_target', 'description']

    incompatible_with_id = serializers.IntegerField(required=True)
    same_target = serializers.BooleanField(required=True)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500
    )

    def validate_incompatible_with_id(self, value: int) -> int:
        try:
            action = Action.objects.get(id=value)
            if action.status == ActionStatus.DISABLED:
                raise serializers.ValidationError(
                    f"Action {value} est désactivée et ne peut pas être utilisée dans une règle mutex"
                )
            return value
        except Action.DoesNotExist:
            raise serializers.ValidationError(f"Action {value} n'existe pas")

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        action_id = self.context.get('action_id')
        if not action_id:
            raise serializers.ValidationError("action_id required in context")
        incompatible_with_id = data.get('incompatible_with_id')

        if action_id == incompatible_with_id:
            raise serializers.ValidationError({
                'incompatible_with_id': "Une action ne peut pas être incompatible avec elle-même"
            })

        try:
            primary_action = Action.objects.get(id=action_id)
            if primary_action.status == ActionStatus.DISABLED:
                raise serializers.ValidationError(
                    f"L'action principale {action_id} est désactivée et ne peut pas avoir de règles mutex"
                )
        except Action.DoesNotExist:
            raise serializers.ValidationError(f"L'action principale {action_id} n'existe pas")

        existing = ActionMutex.objects.filter(
            Q(action_id=int(action_id), incompatible_with_id=incompatible_with_id)
            | Q(action_id=incompatible_with_id, incompatible_with_id=int(action_id))
        ).first()

        if existing:
            raise serializers.ValidationError({
                'incompatible_with_id': f"Une règle mutex existe déjà entre ces deux actions (ID: {existing.id})"
            })
        return data
