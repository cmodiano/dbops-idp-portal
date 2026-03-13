"""
Story 78.10, AC4: Parity check between JSON CLOB and normalized workflow definitions.

Compares get_steps_from_json() vs get_steps_from_normalized() for every workflow
and reports divergences. Zero divergences required before enabling the feature flag.

Usage:
    python manage.py check_workflow_definition_parity
    python manage.py check_workflow_definition_parity --verbose
"""
from __future__ import annotations

import sys
from typing import Any

from django.core.management.base import BaseCommand

from catalog.models import Action, ActionItemType
from catalog.workflow_definition_repository import (
    get_steps_from_json,
    get_steps_from_normalized,
)


def _normalize_step(step: dict) -> dict:
    """Normalize a step dict for comparison (sort keys, convert types, strip nulls/empties).

    Strips keys with None values and empty lists so both JSON and normalized
    outputs are comparable regardless of whether absent-vs-null or absent-vs-[]
    was used.
    """
    normalized: dict[str, Any] = {}
    for key in sorted(step.keys()):
        val = step[key]
        # Strip None values — absent key and explicit null are equivalent
        if val is None:
            continue
        # Strip empty lists — absent key and [] are equivalent for edge lists
        if isinstance(val, list) and len(val) == 0:
            continue
        if isinstance(val, float):
            val = round(val, 2)
        elif isinstance(val, list):
            val = sorted(val) if all(isinstance(v, str) for v in val) else val
        normalized[key] = val
    return normalized


def _compare_steps(json_steps: list[dict], normalized_steps: list[dict]) -> list[str]:
    """Deep-compare two step lists, return list of divergence descriptions."""
    divergences: list[str] = []

    if len(json_steps) != len(normalized_steps):
        divergences.append(
            f"Step count mismatch: JSON={len(json_steps)}, normalized={len(normalized_steps)}"
        )

    json_by_id = {s.get('step_id', f'idx-{i}'): s for i, s in enumerate(json_steps)}
    norm_by_id = {s.get('step_id', f'idx-{i}'): s for i, s in enumerate(normalized_steps)}

    all_ids = set(json_by_id.keys()) | set(norm_by_id.keys())

    for step_id in sorted(all_ids):
        if step_id not in json_by_id:
            divergences.append(f"Step '{step_id}' missing from JSON")
            continue
        if step_id not in norm_by_id:
            divergences.append(f"Step '{step_id}' missing from normalized")
            continue

        js = _normalize_step(json_by_id[step_id])
        ns = _normalize_step(norm_by_id[step_id])

        if js != ns:
            # Find specific field differences
            all_keys = set(js.keys()) | set(ns.keys())
            for key in sorted(all_keys):
                jv = js.get(key)
                nv = ns.get(key)
                if jv != nv:
                    divergences.append(
                        f"Step '{step_id}', field '{key}': JSON={jv!r}, normalized={nv!r}"
                    )

    return divergences


class Command(BaseCommand):
    help = 'Check parity between JSON CLOB and normalized workflow definitions (Story 78.10, AC4).'

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show details for each workflow, including OK ones.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        verbose = options['verbose']

        workflows = Action.objects.filter(
            item_type=ActionItemType.WORKFLOW,
        ).order_by('id')

        total = 0
        ok_count = 0
        divergent_count = 0
        skipped_count = 0

        for action in workflows:
            total += 1
            json_steps = get_steps_from_json(action)
            normalized_steps = get_steps_from_normalized(action.id)

            if not json_steps and not normalized_steps:
                skipped_count += 1
                if verbose:
                    self.stdout.write(f"  SKIP  action_id={action.id} name={action.name!r} (no steps)")
                continue

            divergences = _compare_steps(json_steps, normalized_steps)

            if not divergences:
                ok_count += 1
                if verbose:
                    self.stdout.write(self.style.SUCCESS(
                        f"  OK    action_id={action.id} name={action.name!r} ({len(json_steps)} steps)"
                    ))
            else:
                divergent_count += 1
                self.stdout.write(self.style.ERROR(
                    f"  DIFF  action_id={action.id} name={action.name!r}"
                ))
                for d in divergences:
                    self.stdout.write(f"        - {d}")

        self.stdout.write("")
        self.stdout.write(f"Total workflows: {total}")
        self.stdout.write(f"  OK:        {ok_count}")
        self.stdout.write(f"  Divergent: {divergent_count}")
        self.stdout.write(f"  Skipped:   {skipped_count}")

        if divergent_count > 0:
            self.stdout.write(self.style.ERROR(
                f"\nPARITY CHECK FAILED — {divergent_count} divergence(s) detected."
            ))
            sys.exit(1)
        else:
            self.stdout.write(self.style.SUCCESS(
                "\nPARITY CHECK PASSED — 100% parity between JSON and normalized tables."
            ))
