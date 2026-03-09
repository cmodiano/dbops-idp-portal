"""
Story 67.6: Management command to migrate parallel_group steps to fan-out multi-connection.

Un step parallel_group legacy est converti en connexions directes fan-out :
- Le(s) parent(s) qui pointaient vers le parallel_group voient leur on_success_step_ids
  remplacé par la liste parallel_steps du groupe.
- Chaque step membre reçoit on_success_step_ids/on_error_step_ids depuis le groupe.
- Le step parallel_group est supprimé.

Usage:
    python manage.py migrate_parallel_group --dry-run   # Prévisualisation
    python manage.py migrate_parallel_group              # Migration réelle
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Action, ActionItemType
from catalog.validation import validate_workflow_steps

logger = logging.getLogger(__name__)


def _get_ids(step: dict, plural_key: str, singular_key: str) -> list[str]:
    """Retourne la liste des IDs depuis la clé plurielle ou singulière (rétrocompat)."""
    if plural_key in step:
        return list(step[plural_key] or [])
    if singular_key in step:
        val = step[singular_key]
        return [val] if val else []
    return []


def migrate_workflow_steps(steps: list[Any]) -> tuple[list[Any], list[str]]:
    """
    Convertit les steps parallel_group en fan-out multi-connexion.

    Returns:
        Tuple (migrated_steps, warnings) où warnings est la liste des avertissements.
    """
    warnings: list[str] = []

    # 1. Indexer les parallel_groups (step_id → step dict)
    pg_map: dict[str, dict] = {
        step['step_id']: step
        for step in steps
        if isinstance(step, dict)
        and step.get('step_type') == 'parallel_group'
        and 'step_id' in step
    }

    if not pg_map:
        return steps, warnings

    # Suivre quels parallel_groups sont référencés par un parent
    referenced_pgs: set[str] = set()

    # 2. Pour chaque step non-parallel_group, remplacer les références aux PG
    result: list[Any] = []
    for step in steps:
        if not isinstance(step, dict):
            result.append(step)
            continue

        if step.get('step_type') == 'parallel_group':
            continue  # Supprimé de la liste résultat

        # Remplacer on_success_step_ids qui pointent vers un parallel_group
        success_ids = _get_ids(step, 'on_success_step_ids', 'on_success_step_id')
        new_success_ids: list[str] = []
        for sid in success_ids:
            if sid in pg_map:
                referenced_pgs.add(sid)
                new_success_ids.extend(pg_map[sid].get('parallel_steps') or [])
            else:
                new_success_ids.append(sid)
        if new_success_ids != success_ids:
            step = {**step, 'on_success_step_ids': new_success_ids}
            step.pop('on_success_step_id', None)  # supprimer la clé singulière legacy (référence obsolète)

        # Remplacer on_error_step_ids qui pointent vers un parallel_group
        error_ids = _get_ids(step, 'on_error_step_ids', 'on_error_step_id')
        new_error_ids: list[str] = []
        for sid in error_ids:
            if sid in pg_map:
                referenced_pgs.add(sid)
                new_error_ids.extend(pg_map[sid].get('parallel_steps') or [])
            else:
                new_error_ids.append(sid)
        if new_error_ids != error_ids:
            step = {**step, 'on_error_step_ids': new_error_ids}
            step.pop('on_error_step_id', None)  # supprimer la clé singulière legacy (référence obsolète)

        result.append(step)

    # Détecter les parallel_groups orphelins (aucun parent ne les référençait)
    orphan_pgs = set(pg_map.keys()) - referenced_pgs
    for orphan_id in sorted(orphan_pgs):
        warnings.append(
            f"Step orphelin détecté : '{orphan_id}' (aucun parent ne le référençait). Supprimé."
        )

    # 3. Pour les steps membres du parallel_group, ajouter les connexions de sortie
    for pg in pg_map.values():
        all_success = pg.get('on_all_success_step_id')
        any_error = pg.get('on_any_error_step_id')
        for member_id in (pg.get('parallel_steps') or []):
            for idx, step in enumerate(result):
                if not isinstance(step, dict):
                    continue
                if step.get('step_id') == member_id:
                    # Avertir si on_success_step_ids déjà défini et non vide
                    existing_success = step.get('on_success_step_ids')
                    if existing_success and all_success:
                        warnings.append(
                            f"Step membre '{member_id}' a déjà on_success_step_ids={existing_success}. "
                            f"Remplacement par [{all_success}]."
                        )
                    # Avertir si on_error_step_ids déjà défini et non vide
                    existing_error = step.get('on_error_step_ids')
                    if existing_error and any_error:
                        warnings.append(
                            f"Step membre '{member_id}' a déjà on_error_step_ids={existing_error}. "
                            f"Remplacement par [{any_error}]."
                        )
                    # Créer un nouveau dict (cohérent avec l'étape 2)
                    updated: dict = {**step}
                    if all_success:
                        updated['on_success_step_ids'] = [all_success]
                    else:
                        updated.setdefault('on_success_step_ids', [])
                    if any_error:
                        updated['on_error_step_ids'] = [any_error]
                    result[idx] = updated
                    break

    return result, warnings


class Command(BaseCommand):
    help = 'Migre les steps parallel_group vers le fan-out multi-connexion (Story 67.6).'

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Prévisualise les transformations sans modifier la base de données.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run = options['dry_run']

        # Requête : toutes les actions WORKFLOW avec execution_steps
        candidates = Action.objects.filter(
            item_type=ActionItemType.WORKFLOW,
            execution_steps__isnull=False,
        )

        # Filtrer en mémoire : conserver uniquement celles avec au moins un parallel_group
        to_migrate: list[Action] = []
        ignored = 0
        for action in candidates:
            steps = action.execution_steps
            if not isinstance(steps, list):
                ignored += 1
                continue
            has_pg = any(
                isinstance(step, dict) and step.get('step_type') == 'parallel_group'
                for step in steps
            )
            if has_pg:
                to_migrate.append(action)
            else:
                ignored += 1

        if not to_migrate:
            self.stdout.write(self.style.SUCCESS('Aucun workflow à migrer.'))
            return

        self.stdout.write(
            f'Trouvé {len(to_migrate)} workflow(s) avec des steps parallel_group.'
        )

        migrated = 0
        errors = 0

        for action in to_migrate:
            steps = action.execution_steps
            pg_count = sum(
                1
                for s in steps
                if isinstance(s, dict) and s.get('step_type') == 'parallel_group'
            )

            if dry_run:
                self._report_dry_run(action, steps, pg_count)
                # Simuler la migration pour détecter les échecs de validation potentiels
                try:
                    sim_steps, _ = migrate_workflow_steps(copy.deepcopy(steps))
                    validate_workflow_steps(sim_steps)
                    migrated += 1
                except Exception as exc:
                    errors += 1
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠ Validation échouerait: {exc}')
                    )
                continue

            # Migration réelle
            try:
                with transaction.atomic():
                    new_steps, warnings = migrate_workflow_steps(steps)
                    for w in warnings:
                        self.stdout.write(self.style.WARNING(f'  ⚠ {w}'))

                    validate_workflow_steps(new_steps)

                    action.execution_steps = new_steps
                    action.save(update_fields=['execution_steps'])

                    self.stdout.write(
                        f'  Migré: "{action.name}" (id={action.id})'
                        f' — {pg_count} parallel_group(s) converti(s).'
                    )
                    migrated += 1
            except Exception as exc:
                errors += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'  Erreur: "{action.name}" (id={action.id}) — {exc}. Action ignorée.'
                    )
                )

        if dry_run:
            summary = f'\n[DRY-RUN] {migrated} action(s) seraient migrées'
            if errors:
                summary += f', {errors} échoueraient (validation)'
            summary += '. Relancez sans --dry-run pour exécuter.'
            self.stdout.write(self.style.WARNING(summary))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nMigration terminée : {migrated} action(s) migrée(s), '
                    f'{errors} erreur(s), {ignored} ignorée(s).'
                )
            )

    def _report_dry_run(self, action: Action, steps: list[dict], pg_count: int) -> None:
        """Affiche le rapport dry-run pour une action."""
        self.stdout.write(
            f'\n[DRY-RUN] Action "{action.name}" (id={action.id})'
            f' — {pg_count} parallel_group(s) :'
        )

        pg_map = {
            step['step_id']: step
            for step in steps
            if isinstance(step, dict)
            and step.get('step_type') == 'parallel_group'
            and 'step_id' in step
        }

        for pg_id, pg in pg_map.items():
            parallel_steps = pg.get('parallel_steps') or []
            all_success = pg.get('on_all_success_step_id')
            any_error = pg.get('on_any_error_step_id')

            # Identifier les parents qui pointent vers ce PG
            for step in steps:
                if not isinstance(step, dict) or step.get('step_type') == 'parallel_group':
                    continue
                success_ids = _get_ids(step, 'on_success_step_ids', 'on_success_step_id')
                if pg_id in success_ids:
                    self.stdout.write(
                        f'  Step parent "{step.get("step_id")}" :'
                        f' on_success_step_ids {success_ids} → {parallel_steps}'
                    )

            # Connexions de sortie pour chaque membre
            for member_id in parallel_steps:
                new_success = [all_success] if all_success else []
                line = f'  Step membre "{member_id}" : on_success_step_ids → {new_success}'
                if any_error:
                    line += f', on_error_step_ids → [{any_error}]'
                self.stdout.write(line)

            self.stdout.write(f'  Step "{pg_id}" (parallel_group) → supprimé')
