"""
SimulationService for simulating execution progression in dev mode.
Story 19.0: Enables testing execution UX without real platform integrations.
"""

import random
import time
from threading import Thread

import structlog
from django.conf import settings
from django.db import DatabaseError, IntegrityError, close_old_connections
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.middleware import get_correlation_id

from executions.models import (
    Execution,
    ExecutionStep,
    ExecutionStatus,
    ExecutionStepStatus,
    ExecutionStepType,
)

logger = structlog.get_logger(__name__)

# Simulated step definitions for simple action executions
SIMULATED_STEPS_ACTION = [
    {
        "step_order": 1,
        "step_name": "Préparation",
        "step_type": ExecutionStepType.PREREQUISITE,
        "logs": [
            "[INFO] Initialisation de l'exécution...",
            "[INFO] Validation des paramètres OK",
        ],
    },
    {
        "step_order": 2,
        "step_name": "Récupération secrets Vault",
        "step_type": ExecutionStepType.VAULT,
        "logs": [
            "[INFO] Connexion à Vault...",
            "[INFO] 3 secrets récupérés avec succès",
        ],
    },
    {
        "step_order": 3,
        "step_name": "Déclenchement plateforme",
        "step_type": ExecutionStepType.PLATFORM,
        "logs": [
            "[INFO] Appel API plateforme...",
            "[INFO] Job ID: job-sim-{execution_id}",
        ],
    },
    {
        "step_order": 4,
        "step_name": "Exécution distante",
        "step_type": ExecutionStepType.PLATFORM,
        "logs": [
            "[INFO] Job en cours...",
            "[INFO] Étape 1/3 complétée",
            "[INFO] Étape 2/3 complétée",
            "[INFO] Étape 3/3 complétée",
            "[SUCCESS] Job terminé",
        ],
    },
    {
        "step_order": 5,
        "step_name": "Vérification résultat",
        "step_type": ExecutionStepType.VERIFICATION,
        "logs": [
            "[INFO] Analyse du résultat...",
            "[SUCCESS] Validation OK",
        ],
    },
]


class SimulationService:
    """Service pour simuler l'exécution d'actions en mode dev."""

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if simulation mode is active."""
        return getattr(settings, 'SIMULATE_EXECUTION_DEV', False)

    @classmethod
    def create_simulated_steps(cls, execution: Execution) -> list[ExecutionStep]:
        """Create simulated ExecutionSteps for an execution."""
        if execution.action and execution.action.item_type == 'workflow':
            return cls._create_workflow_steps(execution)
        return cls._create_action_steps(execution)

    @classmethod
    def _create_action_steps(cls, execution: Execution) -> list[ExecutionStep]:
        """Create steps for a simple action execution."""
        steps = []
        for step_config in SIMULATED_STEPS_ACTION:
            step = ExecutionStep.objects.create(
                execution=execution,
                step_order=step_config["step_order"],  # type: ignore[misc]
                step_name=str(step_config["step_name"]),
                step_type=str(step_config["step_type"]),
                status=ExecutionStepStatus.PENDING,
                output="",
            )
            steps.append(step)

        logger.info(
            "simulation_steps_created",
            execution_id=execution.id,
            step_count=len(steps),
        )
        return steps

    @classmethod
    def _create_workflow_steps(cls, execution: Execution) -> list[ExecutionStep]:
        """Create steps for a workflow execution (uses action steps for now)."""
        return cls._create_action_steps(execution)

    @classmethod
    def start_simulation(cls, execution: Execution) -> None:
        """Start background simulation thread for an execution."""
        if not cls.is_enabled():
            logger.warning("simulation_called_but_disabled", execution_id=execution.id)
            return

        # Set execution to RUNNING immediately
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = timezone.now()
        execution.save(update_fields=['status', 'started_at'])

        # Launch daemon thread
        thread = Thread(
            target=cls._run_simulation,
            args=(execution.id,),
            daemon=True,
        )
        thread.start()

        logger.info("simulation_started", execution_id=execution.id)

    @classmethod
    def _run_simulation(cls, execution_id: int) -> None:
        """Background simulation loop (runs in a thread)."""
        try:
            # Thread needs its own DB connection
            close_old_connections()

            execution = Execution.objects.get(id=execution_id)
            steps = list(
                ExecutionStep.objects.filter(execution_id=execution_id).order_by('step_order')
            )

            step_duration = getattr(settings, 'SIMULATE_EXECUTION_STEP_DURATION', 2)
            # MEDIUM-3 fix: Validate step_duration > 0
            if step_duration <= 0:
                logger.warning(
                    "simulation_invalid_step_duration",
                    execution_id=execution_id,
                    step_duration=step_duration,
                    message="SIMULATE_EXECUTION_STEP_DURATION must be > 0, using default 2s",
                )
                step_duration = 2

            failure_rate = getattr(settings, 'SIMULATE_EXECUTION_FAILURE_RATE', 0.1)

            for i, step in enumerate(steps):
                is_last_step = (i == len(steps) - 1)

                # PENDING -> RUNNING
                step.status = ExecutionStepStatus.RUNNING
                step.started_at = timezone.now()
                step.save(update_fields=['status', 'started_at'])

                # Generate logs progressively
                logs = cls._get_logs_for_step(step.step_name, execution_id)
                accumulated = []
                log_delay = step_duration / max(len(logs), 1)

                for log_line in logs:
                    time.sleep(log_delay)
                    accumulated.append(log_line)
                    step.output = "\n".join(accumulated)
                    step.save(update_fields=['output'])

                # Decide failure (only on last step for realism)
                should_fail = is_last_step and random.random() < failure_rate

                if should_fail:
                    step.status = ExecutionStepStatus.FAILED
                    step.output = (step.output or "") + "\n[ERROR] Échec de l'exécution (simulation)"
                    step.completed_at = timezone.now()
                    step.save(update_fields=['status', 'output', 'completed_at'])

                    execution.status = ExecutionStatus.FAILED
                    execution.completed_at = timezone.now()
                    execution.save(update_fields=['status', 'completed_at'])
                    logger.info(
                        "simulation_completed",
                        execution_id=execution_id,
                        status="FAILED",
                    )
                    return
                else:
                    step.status = ExecutionStepStatus.COMPLETED
                    step.completed_at = timezone.now()
                    step.save(update_fields=['status', 'completed_at'])

            # All steps completed successfully
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = timezone.now()
            execution.save(update_fields=['status', 'completed_at'])

            logger.info(
                "simulation_completed",
                execution_id=execution_id,
                status="COMPLETED",
            )

        except (DatabaseError, IntegrityError, ValidationError) as e:
            logger.error(
                "simulation_db_error",
                execution_id=execution_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
                correlation_id=get_correlation_id(),
            )
            raise  # Re-raise pour permettre Celery retry si appelé comme task
        except Exception as e:
            # Story 22.11: Justified broad catch - Simulation thread must handle any unexpected error gracefully
            logger.error(
                "simulation_unexpected_error",
                execution_id=execution_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
                correlation_id=get_correlation_id(),
            )
            raise  # Re-raise pour signaler l'échec au caller
        finally:
            close_old_connections()

    @classmethod
    def advance_simulation_sync(cls, execution_id: int) -> None:
        """
        Run simulation synchronously for tests only (no threading).

        This method bypasses the daemon thread and runs simulation directly
        in the calling thread. Used exclusively in unit/integration tests
        to avoid SQLite thread-locking and ensure deterministic execution.

        Do NOT use in production code - use start_simulation() instead.
        """
        cls._run_simulation(execution_id)

    @classmethod
    def _get_logs_for_step(cls, step_name: str, execution_id: int) -> list[str]:
        """Return simulated log lines for a step type."""
        for step_config in SIMULATED_STEPS_ACTION:
            if step_config["step_name"] == step_name:
                logs = step_config["logs"]
                return [
                    str(log).format(execution_id=execution_id)
                    for log in (logs if isinstance(logs, list) else [])
                ]
        return ["[INFO] Étape en cours...", "[SUCCESS] Étape complétée"]
