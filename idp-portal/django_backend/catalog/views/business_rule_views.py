"""
ViewSet admin des politiques de règles métier.

Responsabilité unique : CRUD admin des BusinessRulePolicy prédéfinies.
Permissions : [IsAuthenticated, AdminProfilePermission] (admin users only). Aucun accès au cache.
"""
from __future__ import annotations

from typing import Any

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import Serializer
from rest_framework.request import Request
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from django.db.models import QuerySet

from catalog.models import BusinessRulePolicy
from catalog.serializers import BusinessRulePolicySerializer, BusinessRulePolicyListSerializer
from platforms.registry import platform_registry
from core.pagination import CustomPageNumberPagination
from core.permissions import AdminProfilePermission
from core.middleware import get_correlation_id


@extend_schema_view(
    list=extend_schema(
        tags=['catalog'],
        summary='Lister les règles métier',
        parameters=[
            OpenApiParameter('is_active', bool, description='Filtrage par statut actif'),
            OpenApiParameter('step_type', str, description='Filtrage par type d\'étape'),
            OpenApiParameter('platform', str, description='Filtrage par plateforme (alias step_type)'),
        ],
    ),
    create=extend_schema(tags=['catalog'], summary='Créer une règle métier'),
    retrieve=extend_schema(tags=['catalog'], summary='Détail d\'une règle métier'),
    partial_update=extend_schema(tags=['catalog'], summary='Modifier une règle métier'),
    destroy=extend_schema(tags=['catalog'], summary='Supprimer une règle métier'),
)
class BusinessRulePolicyViewSet(viewsets.ModelViewSet):
    """
    Story 28.4: CRUD ViewSet for BusinessRulePolicy (AC#4).
    GET/POST/PATCH/DELETE /api/v1/admin/business-rule-policies/
    """
    queryset = BusinessRulePolicy.objects.all()
    serializer_class = BusinessRulePolicySerializer
    permission_classes = [IsAuthenticated, AdminProfilePermission]
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self) -> type[Serializer[Any]]:
        if self.action == 'list':
            return BusinessRulePolicyListSerializer
        return BusinessRulePolicySerializer

    def get_queryset(self) -> QuerySet[BusinessRulePolicy]:
        queryset = BusinessRulePolicy.objects.all()

        # Filter by is_active
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        # Filter by step_type (extracted from policy_json) or by platform (mapped to step_type)
        step_type_filter = self.request.query_params.get('step_type')
        platform_param = self.request.query_params.get('platform')
        if platform_param and not step_type_filter:
            normalized = platform_param.lower().replace(' ', '_')
            step_type_filter = platform_registry.resolve_alias(normalized)
        if step_type_filter:
            # Filter in Python since step_type is computed from JSON
            # HIGH-1: Potential N+1 queries — load all policies before filtering
            all_policies = list(queryset)
            ids = [
                p.id for p in all_policies
                if p.step_type == step_type_filter
            ]
            queryset = queryset.filter(id__in=ids) if ids else queryset.none()

        return queryset

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = BusinessRulePolicyListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = BusinessRulePolicyListSerializer(queryset, many=True)
        return Response({"data": serializer.data})

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = BusinessRulePolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        policy = serializer.save(created_by=request.user)

        # Audit trail
        from core.models import AuditLog, AuditActionType, AuditEntityType
        AuditLog.objects.create_entry(
            user_id=str(request.user.id),
            action_type=AuditActionType.POLICY_CREATED,
            entity_type=AuditEntityType.BUSINESS_RULE_POLICY,
            entity_id=policy.id,
            details={'name': policy.name},
            correlation_id=get_correlation_id(),
        )
        response_serializer = BusinessRulePolicySerializer(policy)
        return Response({"data": response_serializer.data}, status=status.HTTP_201_CREATED)

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        serializer = BusinessRulePolicySerializer(instance)
        return Response({"data": serializer.data})

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        partial = kwargs.get('partial', False)
        serializer = BusinessRulePolicySerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        policy = serializer.save()

        # Audit trail
        from core.models import AuditLog, AuditActionType, AuditEntityType
        AuditLog.objects.create_entry(
            user_id=str(request.user.id),
            action_type=AuditActionType.POLICY_UPDATED,
            entity_type=AuditEntityType.BUSINESS_RULE_POLICY,
            entity_id=policy.id,
            details={'name': policy.name},
            correlation_id=get_correlation_id(),
        )
        response_serializer = BusinessRulePolicySerializer(policy)
        return Response({"data": response_serializer.data})

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()

        # Audit trail
        from core.models import AuditLog, AuditActionType, AuditEntityType
        AuditLog.objects.create_entry(
            user_id=str(request.user.id),
            action_type=AuditActionType.POLICY_DELETED,
            entity_type=AuditEntityType.BUSINESS_RULE_POLICY,
            entity_id=instance.id,
            details={'name': instance.name},
            correlation_id=get_correlation_id(),
        )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
