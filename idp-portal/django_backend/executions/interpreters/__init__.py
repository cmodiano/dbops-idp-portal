"""
Output interpreters for the RuleEngine.

Each interpreter transforms platform-specific step output (Terraform plan, AAP job, etc.)
into a NormalizedArtifact that the RuleEngine can evaluate against business rule policies.

To add a new interpreter:
1. Create a class inheriting from OutputInterpreter
2. Implement interpret(step_type, step_output) -> NormalizedArtifact
3. Register it: OutputInterpreterRegistry.register("step_type", MyInterpreter())
"""
from executions.interpreters.base import NormalizedArtifact, OutputInterpreter
from executions.interpreters.registry import OutputInterpreterRegistry
from executions.interpreters.terraform_plan_interpreter import TerraformPlanInterpreter
from executions.interpreters.aap_output_interpreter import AAPOutputInterpreter

__all__ = [
    "NormalizedArtifact",
    "OutputInterpreter",
    "OutputInterpreterRegistry",
    "TerraformPlanInterpreter",
    "AAPOutputInterpreter",
]


def register_default_interpreters() -> None:
    """Register built-in interpreters in the global registry."""
    registry = OutputInterpreterRegistry.get_instance()
    registry.register("terraform_cloud", TerraformPlanInterpreter())
    registry.register("aap", AAPOutputInterpreter())


register_default_interpreters()
