"""
Base interface and data structures for output interpreters.

An OutputInterpreter transforms the raw output of an execution step
(Terraform plan, AAP job, etc.) into a NormalizedArtifact that the
RuleEngine can evaluate against business rule policies.

To create a new interpreter:
1. Subclass OutputInterpreter
2. Implement interpret(step_type, step_output) -> NormalizedArtifact
3. Register via OutputInterpreterRegistry.register("step_type", MyInterpreter())
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class NormalizedArtifact:
    """
    Normalized artifact produced by an interpreter.

    Common structure for all interpreters:
    - changes: list of change dicts (structure varies by platform)
    - metadata: platform-specific metadata
    """
    changes: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class OutputInterpreter(ABC):
    """
    Interface for execution step output interpreters.

    An interpreter transforms raw step output (Terraform plan, AAP job, etc.)
    into a NormalizedArtifact exploitable by the RuleEngine.
    """

    @abstractmethod
    def interpret(self, step_type: str, step_output: dict | str) -> NormalizedArtifact:
        """
        Parse step output and return a normalized artifact.

        Args:
            step_type: Step type (terraform_cloud, aap, etc.)
            step_output: Raw step output (JSON dict or text string)

        Returns:
            NormalizedArtifact with changes and metadata

        Raises:
            PolicyEvaluationError: if parsing fails
        """
