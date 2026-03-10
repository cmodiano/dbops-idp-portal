"""Pipeline unifié de validation pour la création d'exécutions.

Story 71.5 (MAINT-BE-9): Orchestre les validateurs existants dans un ordre
déterministe et retourne un ExecutionValidationResult structuré.
"""
from __future__ import annotations

from typing import Any

from rest_framework.request import Request

from core.auth_utils import get_user_ad_groups
from executions.validators.payload_validator import ExecutionPayloadValidator
from executions.validators.target_validator import TargetValidator
from executions.validators.env_config_resolver import EnvironmentConfigResolver
from executions.validators.workflow_validator import WorkflowValidator
from executions.validators.mutex_validator import MutexValidator
from executions.validators.result import ExecutionValidationResult

import structlog

logger = structlog.get_logger(__name__)


class ExecutionValidationPipeline:
    """Orchestre les validateurs existants dans un ordre déterministe.

    Séquence : payload -> targets -> env_config -> workflow -> mutex
    Chaque étape délègue au validateur existant (pas de duplication de logique).
    Fail-fast : les validateurs lèvent des exceptions immédiatement.
    """

    @staticmethod
    def validate(
        request_data: dict[str, Any],
        request: Request,
        user: Any,
        ip_address: str,
    ) -> ExecutionValidationResult:
        """Exécute le pipeline de validation complet.

        Args:
            request_data: Payload de la requête.
            request: Objet Request DRF (pour headers, META).
            user: Utilisateur authentifié.
            ip_address: Adresse IP du client.

        Returns:
            ExecutionValidationResult avec tous les champs validés.

        Raises:
            BadRequestError: Si la validation échoue.
            NotFoundError: Si l'action n'existe pas.
            ForbiddenError: Si la cible n'est pas autorisée.
        """
        # Step 1: Validate payload
        validated = ExecutionPayloadValidator.validate(request_data, request)
        action = validated['action']
        action_id = validated['action_id']
        environment = validated['environment']
        target_names = validated['target_names']
        parameters = validated['parameters']
        workflow_step_parameters = validated['workflow_step_parameters']
        parent_execution_id = validated['parent_execution_id']
        correlation_id = validated['correlation_id']
        page_me = validated.get('page_me', False)
        requires_target = validated['requires_target']

        # Step 2: Validate targets (if applicable)
        validated_targets: list[dict[str, Any]] | None = None
        if target_names:
            ad_groups = get_user_ad_groups(user)
            validated_targets, environment = TargetValidator.validate_targets(
                target_names=target_names,
                action_id=action_id,
                user=user,
                ad_groups=ad_groups,
                correlation_id=correlation_id,
            )
            parameters = (parameters.copy() if parameters else {})
            parameters['_targets'] = target_names

            logger.info(
                "execution_with_targets",
                user_id=user.id,
                action_id=action_id,
                target_count=len(target_names),
                derived_environment=environment,
                correlation_id=correlation_id,
            )

        # Step 3: Resolve environment config
        env_config = EnvironmentConfigResolver.resolve(
            action=action,
            environment=environment,
            correlation_id=correlation_id,
        )

        # Store environment config in parameters
        parameters = (parameters.copy() if parameters else {})
        parameters['_env_config'] = {
            'change_required': env_config['change_required'],
            'change_model_code': env_config['change_model_code'],
            'impact_level': env_config['impact_level'],
            'requires_maintenance_window': env_config['requires_maintenance_window'],
            'requires_approval': env_config['requires_approval'],
        }

        # Step 4: Validate workflow (if applicable)
        delegated_referenced_action_ids: list[int] | None = None
        if action.item_type == "workflow":
            delegated_referenced_action_ids = WorkflowValidator.validate_referenced_actions(
                workflow_action=action,
                correlation_id=correlation_id,
                user_id=user.id,
                ip_address=ip_address,
            )
        else:
            WorkflowValidator.reject_step_parameters_for_non_workflow(action, workflow_step_parameters)

        if action.item_type == "workflow" and workflow_step_parameters is not None:
            normalized_wsp = WorkflowValidator.validate_step_parameters(
                workflow_action=action,
                workflow_step_parameters=workflow_step_parameters,
            )
            parameters = (parameters.copy() if parameters else {})
            parameters["workflow_step_parameters"] = normalized_wsp

        # Step 5: Validate mutex
        target_ids_for_mutex = [t['name'] for t in validated_targets] if validated_targets else []
        MutexValidator.validate(
            action=action,
            target_ids=target_ids_for_mutex,
            correlation_id=correlation_id,
            user_id=str(user.id),
        )

        return ExecutionValidationResult(
            action=action,
            action_id=action_id,
            environment=env_config['env_str'],
            correlation_id=correlation_id,
            requires_target=requires_target,
            page_me=page_me,
            target_names=target_names,
            parameters=parameters if parameters else None,
            workflow_step_parameters=workflow_step_parameters,
            parent_execution_id=parent_execution_id,
            validated_targets=validated_targets,
            env_config=env_config,
            delegated_referenced_action_ids=delegated_referenced_action_ids,
        )
