"""
Story 78.10: WorkflowDefinitionRepository — dual-read service for workflow definitions.

Provides a single API to read workflow steps from either the JSON CLOB
(ACTIONS_CATALOG.EXECUTION_STEPS) or the normalized tables (WORKFLOW_DEFINITIONS,
WORKFLOW_STEPS, WORKFLOW_STEP_EDGES), controlled by the feature flag
WORKFLOW_NORMALIZED_DEFINITIONS_ENABLED.
"""
from __future__ import annotations

import structlog
from django.conf import settings

from catalog.models import Action
from catalog.models_workflow_definition import (
    WorkflowDefinition,
    WorkflowStep,
    WorkflowStepEdge,
)

logger = structlog.get_logger(__name__)


def get_steps_from_json(action: Action) -> list[dict]:
    """Return execution_steps from the JSON CLOB field (existing behavior)."""
    steps = action.execution_steps
    if not steps or not isinstance(steps, list):
        return []
    return steps


def get_steps_from_normalized(action_id: int) -> list[dict]:
    """
    Reconstruct execution_steps dict list from normalized tables.

    Produces output identical to the JSON CLOB format so callers
    see no difference regardless of backend.
    """
    try:
        wf_def = WorkflowDefinition.objects.get(action_id=action_id)
    except WorkflowDefinition.DoesNotExist:
        return []

    steps = (
        WorkflowStep.objects
        .filter(workflow_definition=wf_def)
        .select_related('referenced_action')
        .order_by('step_order')
    )

    # Prefetch all edges for this workflow in one query
    all_edges = (
        WorkflowStepEdge.objects
        .filter(from_step__workflow_definition=wf_def)
        .select_related('to_step')
    )
    edges_by_from: dict[int, list[WorkflowStepEdge]] = {}
    for edge in all_edges:
        edges_by_from.setdefault(edge.from_step_id, []).append(edge)

    result = []
    for step in steps:
        step_dict: dict = {
            'order': step.step_order,
            'step_id': step.step_id,
            'name': step.step_name,
            'step_type': step.step_type,
        }

        # referenced_action_id
        if step.referenced_action_id is not None:
            step_dict['referenced_action_id'] = step.referenced_action_id

        # Optional fields — only include if not None/empty
        if step.integration_type:
            step_dict['integration_type'] = step.integration_type
        if step.operation:
            step_dict['operation'] = step.operation
        if step.input_mapping is not None:
            step_dict['input_mapping'] = step.input_mapping
        if step.output_mapping is not None:
            step_dict['output_mapping'] = step.output_mapping
        if step.condition:
            step_dict['condition'] = step.condition
        if step.join_policy:
            step_dict['join_policy'] = step.join_policy

        # Retry fields
        step_dict['retry_enabled'] = step.retry_enabled
        if step.retry_max_attempts is not None:
            step_dict['retry_max_attempts'] = step.retry_max_attempts
        if step.retry_interval_seconds is not None:
            step_dict['retry_interval_seconds'] = step.retry_interval_seconds
        if step.retry_backoff_multiplier is not None:
            step_dict['retry_backoff_multiplier'] = float(step.retry_backoff_multiplier)

        # Reconstruct edges
        step_edges = edges_by_from.get(step.id, [])
        success_ids = [e.to_step.step_id for e in step_edges if e.edge_type == 'success']
        error_ids = [e.to_step.step_id for e in step_edges if e.edge_type == 'error']
        if success_ids:
            step_dict['on_success_step_ids'] = success_ids
        if error_ids:
            step_dict['on_error_step_ids'] = error_ids

        result.append(step_dict)

    return result


def get_steps(action: Action) -> list[dict]:
    """
    Public API: return workflow steps, dispatching based on feature flag.

    When WORKFLOW_NORMALIZED_DEFINITIONS_ENABLED is True, reads from
    normalized tables. Otherwise, reads from JSON CLOB.
    """
    if getattr(settings, 'WORKFLOW_NORMALIZED_DEFINITIONS_ENABLED', False):
        return get_steps_from_normalized(action.id)
    return get_steps_from_json(action)


def sync_from_json(action: Action) -> None:
    """
    Synchronize normalized tables from the JSON CLOB field.

    Idempotent: deletes existing rows for this action and re-inserts.
    Must be called within a transaction.atomic() block.
    """
    steps_json = action.execution_steps
    if not steps_json or not isinstance(steps_json, list):
        # No steps — clean up any existing normalized data
        WorkflowDefinition.objects.filter(action_id=action.id).delete()
        return

    # Upsert WorkflowDefinition
    wf_def, created = WorkflowDefinition.objects.update_or_create(
        action_id=action.id,
        defaults={'version': 1},
    )
    if not created:
        # Increment version on update
        wf_def.version = (wf_def.version or 0) + 1
        wf_def.save(update_fields=['version', 'updated_at'])

    # Clear existing steps (cascade deletes edges)
    WorkflowStep.objects.filter(workflow_definition=wf_def).delete()

    # Insert steps
    step_objects: dict[str, WorkflowStep] = {}
    for step_data in steps_json:
        if not isinstance(step_data, dict):
            continue

        step_id = step_data.get('step_id', '')
        if not step_id:
            continue

        retry_backoff = step_data.get('retry_backoff_multiplier')

        step_obj = WorkflowStep.objects.create(
            workflow_definition=wf_def,
            step_id=step_id,
            step_order=step_data.get('order', 0),
            step_name=step_data.get('name', f"Step {step_data.get('order', 0)}"),
            step_type=step_data.get('step_type', 'platform'),
            referenced_action_id=step_data.get('referenced_action_id'),
            integration_type=step_data.get('integration_type'),
            operation=step_data.get('operation'),
            input_mapping=step_data.get('input_mapping'),
            output_mapping=step_data.get('output_mapping'),
            condition=step_data.get('condition'),
            retry_enabled=bool(step_data.get('retry_enabled', False)),
            retry_max_attempts=step_data.get('retry_max_attempts'),
            retry_interval_seconds=step_data.get('retry_interval_seconds'),
            retry_backoff_multiplier=retry_backoff,
            join_policy=step_data.get('join_policy'),
        )
        step_objects[step_id] = step_obj

    # Insert edges
    for step_data in steps_json:
        if not isinstance(step_data, dict):
            continue
        from_step_id = step_data.get('step_id', '')
        from_step = step_objects.get(from_step_id)
        if not from_step:
            continue

        for edge_type, key in [('success', 'on_success_step_ids'), ('error', 'on_error_step_ids')]:
            target_ids = step_data.get(key, [])
            if not isinstance(target_ids, list):
                continue
            for target_step_id in target_ids:
                to_step = step_objects.get(target_step_id)
                if to_step:
                    WorkflowStepEdge.objects.create(
                        from_step=from_step,
                        to_step=to_step,
                        edge_type=edge_type,
                    )

    logger.info(
        "workflow_definition_synced",
        action_id=action.id,
        step_count=len(step_objects),
        version=wf_def.version,
    )
