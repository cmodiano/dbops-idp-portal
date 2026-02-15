"""
TerraformPlanInterpreter — Parses Terraform Cloud plan output.

Extracts resource_changes from JSON plan (or text fallback) and produces
a NormalizedArtifact with changes containing resource_type, actions,
changed_attributes, and resource_address.
"""
from __future__ import annotations

import re

import structlog

from core.middleware import get_correlation_id
from executions.interpreters.base import NormalizedArtifact, OutputInterpreter
from executions.policy_evaluator import PolicyEvaluationError

logger = structlog.get_logger(__name__)


class TerraformPlanInterpreter(OutputInterpreter):
    """Interprets Terraform Cloud plan output (JSON or text)."""

    def interpret(self, step_type: str, step_output: dict | str) -> NormalizedArtifact:
        """
        Parse Terraform plan and extract resource_changes.

        Supports JSON (Terraform Cloud API) and text (CLI output) formats.
        """
        correlation_id = get_correlation_id()

        if isinstance(step_output, dict):
            changes = self._parse_json_plan(step_output)
            metadata = {
                "format_version": step_output.get("format_version"),
                "terraform_version": step_output.get("terraform_version"),
            }
        elif isinstance(step_output, str):
            logger.warning(
                "terraform_plan_text_fallback_used",
                correlation_id=correlation_id,
            )
            changes = self._parse_text_plan(step_output)
            metadata = {}
        else:
            raise PolicyEvaluationError(
                message=f"Invalid Terraform plan format: expected dict or str, got {type(step_output).__name__}",
            )

        logger.info(
            "terraform_plan_parsed",
            num_resource_changes=len(changes),
            correlation_id=correlation_id,
        )

        return NormalizedArtifact(changes=changes, metadata=metadata)

    def _parse_json_plan(self, plan: dict) -> list[dict]:
        """Parse Terraform Cloud JSON plan format."""
        try:
            if "resource_changes" not in plan:
                raise PolicyEvaluationError(
                    message="Invalid Terraform plan format: missing 'resource_changes'",
                )

            raw_changes = plan["resource_changes"]
            if not isinstance(raw_changes, list):
                raise PolicyEvaluationError(
                    message="Invalid Terraform plan format: 'resource_changes' is not a list",
                )

            changes: list[dict] = []
            for rc in raw_changes:
                if not isinstance(rc, dict):
                    continue

                actions = rc.get("change", {}).get("actions", [])
                if actions == ["no-op"]:
                    continue

                resource_type = rc.get("type", "")
                address = rc.get("address", "")

                before = rc.get("change", {}).get("before") or {}
                after = rc.get("change", {}).get("after") or {}

                changed_attrs: list[str] = []
                for key in set(before.keys()) | set(after.keys()):
                    if before.get(key) != after.get(key):
                        changed_attrs.append(key)

                changes.append({
                    "resource_type": resource_type,
                    "actions": actions,
                    "changed_attributes": changed_attrs,
                    "resource_address": address,
                })

            return changes

        except PolicyEvaluationError:
            raise
        except (KeyError, TypeError) as exc:
            raise PolicyEvaluationError(
                message=f"Invalid Terraform plan format: {exc}",
            ) from exc

    def _parse_text_plan(self, plan_text: str) -> list[dict]:
        """Parse Terraform plan text format (fallback / best-effort)."""
        changes: list[dict] = []

        resource_pattern = re.compile(r'#\s+([\w.]+)\s+will be\s+(\w+)')
        attr_pattern = re.compile(r'^\s+[~+-]\s+(\w+)\s+', re.MULTILINE)

        blocks = re.split(r'(?=\s*#\s+\S+\s+will be)', plan_text)

        for block in blocks:
            resource_match = resource_pattern.search(block)
            if not resource_match:
                continue

            full_address = resource_match.group(1)
            action_text = resource_match.group(2).lower()

            parts = full_address.rsplit('.', 1)
            if len(parts) > 1:
                resource_type = parts[0]
                if 'module.' in resource_type:
                    type_parts = resource_type.split('.')
                    for i in range(len(type_parts) - 1, -1, -1):
                        if not type_parts[i].startswith('module'):
                            resource_type = type_parts[i]
                            break
            else:
                resource_type = full_address

            action_map = {
                'created': ['create'],
                'updated': ['update'],
                'destroyed': ['delete'],
                'replaced': ['create', 'delete'],
            }
            actions = action_map.get(action_text, [action_text])

            changed_attrs: list[str] = []
            for attr_match in attr_pattern.finditer(block):
                changed_attrs.append(attr_match.group(1))

            changes.append({
                "resource_type": resource_type,
                "actions": actions,
                "changed_attributes": changed_attrs,
                "resource_address": full_address,
            })

        return changes
