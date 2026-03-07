#!/usr/bin/env python
"""
Audit script : vérifie la couverture de schémas d'output pour les workflows.

Usage:
    python scripts/audit_workflow_schemas.py [--output json]

Options:
    --output json    Écrire le rapport en JSON structuré sur stdout.
                     Par défaut : affichage console lisible.

Ce script est READ-ONLY : aucune modification de données.
"""
import argparse
import json
import os
import sys

# Initialisation Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'idp_backend.settings')

import django  # noqa: E402
django.setup()

from catalog.models import Action, ActionItemType  # noqa: E402
from output_schemas.registry import schema_registry  # noqa: E402


# Step types that can carry an output schema (others are not applicable by design)
_SCHEMA_BEARING_STEP_TYPES = {'platform', 'service_call'}


def _get_schema_for_step(step: dict, action_names_by_id: dict):
    """Retourne le schéma résolu pour un step, ou None si absent."""
    step_type = step.get('step_type', 'platform')

    if step_type == 'platform':
        ref_action_id = step.get('referenced_action_id')
        if not ref_action_id:
            return None
        action_name = action_names_by_id.get(ref_action_id)
        if not action_name:
            return None
        return schema_registry.get_action_schema(action_name)

    if step_type == 'service_call':
        integration_type = step.get('integration_type', '')
        operation = step.get('operation', '')
        if integration_type and operation:
            return schema_registry.get_integration_schema(integration_type, operation)
        return None

    return None


def audit() -> dict:
    """
    Parcourt tous les workflows et leurs steps.
    Retourne un dict avec les statistiques et les steps sans couverture.
    """
    workflows = list(Action.objects.filter(item_type=ActionItemType.WORKFLOW).order_by('id'))

    # Pre-load all referenced Action names in a single query to avoid N+1
    all_ref_ids = set()
    for workflow in workflows:
        for step in (workflow.execution_steps or []):
            if step.get('step_type') == 'platform':
                ref_id = step.get('referenced_action_id')
                if ref_id:
                    all_ref_ids.add(ref_id)
    action_names_by_id = (
        dict(Action.objects.filter(id__in=all_ref_ids).values_list('id', 'name'))
        if all_ref_ids else {}
    )

    total_steps = 0
    steps_with_schema = 0
    steps_without_schema = []

    for workflow in workflows:
        execution_steps = workflow.execution_steps or []
        for step in execution_steps:
            step_type = step.get('step_type', 'platform')
            if step_type not in _SCHEMA_BEARING_STEP_TYPES:
                # Gates, approvals, etc. don't carry output schemas by design — skip
                continue

            total_steps += 1
            step_id = step.get('step_id', '')
            step_name = step.get('name', step_id)

            schema = _get_schema_for_step(step, action_names_by_id)

            if schema:
                steps_with_schema += 1
            else:
                steps_without_schema.append({
                    'workflow_id': workflow.id,
                    'workflow_name': workflow.name,
                    'step_id': step_id,
                    'step_name': step_name,
                    'step_type': step_type,
                })

    return {
        'total_workflows': len(workflows),
        'total_steps': total_steps,
        'steps_with_schema': steps_with_schema,
        'steps_without_schema_count': len(steps_without_schema),
        'coverage_percent': (
            round(steps_with_schema / total_steps * 100, 1) if total_steps > 0 else 100.0
        ),
        'steps_without_schema': steps_without_schema,
    }


def print_console_report(report: dict) -> None:
    """Affiche le rapport en mode console lisible."""
    print("=" * 60)
    print("Audit des schémas d'output — Workflows IDP")
    print("=" * 60)
    print(f"Workflows analysés  : {report['total_workflows']}")
    print(f"Steps total         : {report['total_steps']}")
    print(f"Steps avec schéma   : {report['steps_with_schema']}")
    print(f"Steps sans schéma   : {report['steps_without_schema_count']}")
    print(f"Couverture          : {report['coverage_percent']}%")
    print()

    if report['steps_without_schema']:
        print("Steps sans couverture :")
        print("-" * 60)
        for item in report['steps_without_schema']:
            print(
                f"  Workflow #{item['workflow_id']} ({item['workflow_name']}) "
                f"| step={item['step_id']!r} | type={item['step_type']}"
            )
    else:
        print("Tous les steps ont un schéma d'output. ✓")

    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit de couverture des schémas d'output pour les workflows."
    )
    parser.add_argument(
        '--output',
        choices=['json'],
        default=None,
        help="Format de sortie. Par défaut : affichage console.",
    )
    args = parser.parse_args()

    report = audit()

    if args.output == 'json':
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_console_report(report)


if __name__ == '__main__':
    main()
