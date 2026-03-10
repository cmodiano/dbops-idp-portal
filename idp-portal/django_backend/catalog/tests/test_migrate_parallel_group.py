"""
Story 67.6: Tests de la commande migrate_parallel_group (AC#8).

Cas couverts :
- 2.2 : Aucune action concernée → message "Aucun workflow à migrer"
- 2.3 : Migration simple — 1 parallel_group (2 steps), 1 successeur → steps corrects en DB
- 2.4 : --dry-run — DB inchangée, output décrit les transformations
- 2.5 : 2 parallel_groups dans le même workflow → les 2 sont traités
- 2.6 : parallel_group sans on_all_success_step_id → on_success_step_ids: [] pour les membres
- 2.7 : parallel_group avec on_any_error_step_id → on_error_step_ids ajouté aux membres
- 2.8 : validation post-migration échoue → action ignorée, autres migrées
- 2.9 : step parallel_group orphelin (aucun parent) → warning, step supprimé, autres steps intacts
"""

import pytest
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from catalog.models import Action, ActionStatus, ActionItemType, ActionEngine, ActionPlatform
from tests.factories import UserFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_platform_step(step_id: str, ref_action_id: int, **kwargs) -> dict:
    """Crée un step de type platform avec les champs requis par la validation."""
    return {
        'step_id': step_id,
        'step_type': 'platform',
        'referenced_action_id': ref_action_id,
        **kwargs,
    }


def _make_pg_step(step_id: str, parallel_steps: list[str], **kwargs) -> dict:
    """Crée un step de type parallel_group."""
    return {
        'step_id': step_id,
        'step_type': 'parallel_group',
        'parallel_steps': parallel_steps,
        **kwargs,
    }


@pytest.mark.django_db
class TestMigrateParallelGroupCommand(TestCase):
    """Tests de la commande migrate_parallel_group (Story 67.6, AC#8)."""

    def setUp(self):
        self.user = UserFactory(username='migrator67', profile='dbops')

    def _create_workflow_action(self, name: str, execution_steps: list) -> Action:
        """Crée une action WORKFLOW avec les steps donnés."""
        return Action.objects.create(
            name=name,
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            created_by=self.user,
            execution_steps=execution_steps,
        )

    # -----------------------------------------------------------------------
    # 2.2 — Aucune action concernée → message "Aucun workflow à migrer"
    # -----------------------------------------------------------------------

    def test_no_eligible_actions(self):
        """2.2: Aucune action avec parallel_group → message 'Aucun workflow à migrer'."""
        # Action WORKFLOW sans parallel_group
        self._create_workflow_action(
            name='Workflow sans PG',
            execution_steps=[
                _make_platform_step('step1', 1, on_success_step_ids=[]),
            ],
        )
        out = StringIO()
        call_command('migrate_parallel_group', stdout=out)
        self.assertIn('Aucun workflow à migrer', out.getvalue())

    # -----------------------------------------------------------------------
    # 2.3 — Migration simple : 1 parallel_group (2 steps), 1 successeur
    # -----------------------------------------------------------------------

    def test_simple_migration(self):
        """2.3: Migration d'un workflow avec 1 parallel_group et 2 steps membres."""
        steps = [
            _make_platform_step('start', 1, on_success_step_ids=['pg1']),
            _make_pg_step('pg1', ['branch1', 'branch2'], on_all_success_step_id='end'),
            _make_platform_step('branch1', 2),
            _make_platform_step('branch2', 3),
            _make_platform_step('end', 4, on_success_step_ids=[]),
        ]
        action = self._create_workflow_action(name='Workflow simple', execution_steps=steps)

        out = StringIO()
        call_command('migrate_parallel_group', stdout=out)

        action.refresh_from_db()
        result_steps = action.execution_steps

        # Le parallel_group est supprimé
        step_types = [s.get('step_type') for s in result_steps]
        self.assertNotIn('parallel_group', step_types)

        # step_ids présents
        step_ids = {s['step_id'] for s in result_steps}
        self.assertEqual(step_ids, {'start', 'branch1', 'branch2', 'end'})

        # start pointe vers branch1 et branch2
        start_step = next(s for s in result_steps if s['step_id'] == 'start')
        self.assertEqual(sorted(start_step['on_success_step_ids']), ['branch1', 'branch2'])

        # branch1 et branch2 pointent vers end
        for step_id in ('branch1', 'branch2'):
            member = next(s for s in result_steps if s['step_id'] == step_id)
            self.assertEqual(member['on_success_step_ids'], ['end'])

        # Message de succès
        self.assertIn('Migration terminée', out.getvalue())

    # -----------------------------------------------------------------------
    # 2.4 — --dry-run : DB inchangée, output décrit les transformations
    # -----------------------------------------------------------------------

    def test_dry_run_does_not_modify_db(self):
        """2.4: --dry-run n'affecte pas la DB mais décrit les transformations."""
        steps = [
            _make_platform_step('start', 1, on_success_step_ids=['pg1']),
            _make_pg_step('pg1', ['branch1', 'branch2'], on_all_success_step_id='end'),
            _make_platform_step('branch1', 2),
            _make_platform_step('branch2', 3),
            _make_platform_step('end', 4, on_success_step_ids=[]),
        ]
        action = self._create_workflow_action(name='Workflow dry-run', execution_steps=steps)
        original_steps = list(steps)  # copie

        out = StringIO()
        call_command('migrate_parallel_group', '--dry-run', stdout=out)
        output = out.getvalue()

        # DB inchangée
        action.refresh_from_db()
        self.assertEqual(action.execution_steps, original_steps)

        # Output mentionne DRY-RUN et des transformations
        self.assertIn('DRY-RUN', output)
        self.assertIn('pg1', output)
        self.assertIn('seraient migrées', output)

    # -----------------------------------------------------------------------
    # 2.5 — 2 parallel_groups dans le même workflow → les 2 sont traités
    # -----------------------------------------------------------------------

    def test_two_parallel_groups_same_workflow(self):
        """2.5: Workflow avec 2 parallel_groups → les deux sont convertis."""
        steps = [
            _make_platform_step('start', 1, on_success_step_ids=['pg1']),
            _make_pg_step('pg1', ['branch1', 'branch2'], on_all_success_step_id='mid'),
            _make_platform_step('branch1', 2),
            _make_platform_step('branch2', 3),
            _make_platform_step('mid', 5, on_success_step_ids=['pg2']),
            _make_pg_step('pg2', ['branch3', 'branch4'], on_all_success_step_id='end'),
            _make_platform_step('branch3', 6),
            _make_platform_step('branch4', 7),
            _make_platform_step('end', 8, on_success_step_ids=[]),
        ]
        action = self._create_workflow_action(name='Workflow 2 PG', execution_steps=steps)

        call_command('migrate_parallel_group', stdout=StringIO())

        action.refresh_from_db()
        result_steps = action.execution_steps

        # Aucun parallel_group restant
        self.assertFalse(
            any(s.get('step_type') == 'parallel_group' for s in result_steps)
        )

        # start → branch1, branch2
        start = next(s for s in result_steps if s['step_id'] == 'start')
        self.assertEqual(sorted(start['on_success_step_ids']), ['branch1', 'branch2'])

        # mid → branch3, branch4
        mid = next(s for s in result_steps if s['step_id'] == 'mid')
        self.assertEqual(sorted(mid['on_success_step_ids']), ['branch3', 'branch4'])

        # branch1/branch2 → mid
        for sid in ('branch1', 'branch2'):
            member = next(s for s in result_steps if s['step_id'] == sid)
            self.assertEqual(member['on_success_step_ids'], ['mid'])

        # branch3/branch4 → end
        for sid in ('branch3', 'branch4'):
            member = next(s for s in result_steps if s['step_id'] == sid)
            self.assertEqual(member['on_success_step_ids'], ['end'])

    # -----------------------------------------------------------------------
    # 2.6 — parallel_group sans on_all_success_step_id → on_success_step_ids: []
    # -----------------------------------------------------------------------

    def test_parallel_group_without_success_step(self):
        """2.6: parallel_group sans on_all_success_step_id → membres ont on_success_step_ids: []."""
        steps = [
            _make_platform_step('start', 1, on_success_step_ids=['pg1']),
            # Pas de on_all_success_step_id → fin de workflow pour les membres
            _make_pg_step('pg1', ['branch1', 'branch2']),
            _make_platform_step('branch1', 2),
            _make_platform_step('branch2', 3),
        ]
        action = self._create_workflow_action(name='Workflow sans successeur', execution_steps=steps)

        call_command('migrate_parallel_group', stdout=StringIO())

        action.refresh_from_db()
        result_steps = action.execution_steps

        for step_id in ('branch1', 'branch2'):
            member = next(s for s in result_steps if s['step_id'] == step_id)
            self.assertEqual(member.get('on_success_step_ids'), [])

    # -----------------------------------------------------------------------
    # 2.7 — parallel_group avec on_any_error_step_id → on_error_step_ids ajouté
    # -----------------------------------------------------------------------

    def test_parallel_group_with_error_step(self):
        """2.7: parallel_group avec on_any_error_step_id → membres reçoivent on_error_step_ids."""
        steps = [
            _make_platform_step('start', 1, on_success_step_ids=['pg1']),
            _make_pg_step(
                'pg1',
                ['branch1', 'branch2'],
                on_all_success_step_id='end',
                on_any_error_step_id='rollback',
            ),
            _make_platform_step('branch1', 2),
            _make_platform_step('branch2', 3),
            _make_platform_step('end', 4, on_success_step_ids=[]),
            _make_platform_step('rollback', 5, on_success_step_ids=[]),
        ]
        action = self._create_workflow_action(name='Workflow avec erreur', execution_steps=steps)

        call_command('migrate_parallel_group', stdout=StringIO())

        action.refresh_from_db()
        result_steps = action.execution_steps

        for step_id in ('branch1', 'branch2'):
            member = next(s for s in result_steps if s['step_id'] == step_id)
            self.assertEqual(member['on_success_step_ids'], ['end'])
            self.assertEqual(member['on_error_step_ids'], ['rollback'])

    # -----------------------------------------------------------------------
    # 2.8 — validation post-migration échoue → action ignorée, autres migrées
    # -----------------------------------------------------------------------

    def test_validation_failure_skips_action_others_migrated(self):
        """2.8: Si la validation échoue pour une action, elle est ignorée mais les autres sont migrées."""
        # Action valide
        valid_steps = [
            _make_platform_step('start', 1, on_success_step_ids=['pg1']),
            _make_pg_step('pg1', ['branch1', 'branch2'], on_all_success_step_id='end'),
            _make_platform_step('branch1', 2),
            _make_platform_step('branch2', 3),
            _make_platform_step('end', 4, on_success_step_ids=[]),
        ]
        valid_action = self._create_workflow_action(
            name='Workflow valide', execution_steps=valid_steps
        )

        # Action invalide : pg avec on_all_success_step_id qui n'existe pas → validation KO
        invalid_steps = [
            _make_platform_step('start2', 10, on_success_step_ids=['pg2']),
            _make_pg_step('pg2', ['branch5'], on_all_success_step_id='NONEXISTENT'),
            _make_platform_step('branch5', 11),
        ]
        invalid_action = self._create_workflow_action(
            name='Workflow invalide', execution_steps=invalid_steps
        )

        out = StringIO()
        call_command('migrate_parallel_group', stdout=out)
        output = out.getvalue()

        # L'action valide doit être migrée
        valid_action.refresh_from_db()
        result_steps = valid_action.execution_steps
        self.assertFalse(
            any(s.get('step_type') == 'parallel_group' for s in result_steps)
        )

        # L'action invalide doit être inchangée (rollback)
        invalid_action.refresh_from_db()
        self.assertTrue(
            any(s.get('step_type') == 'parallel_group' for s in invalid_action.execution_steps)
        )

        # Message d'erreur dans l'output
        self.assertIn('Erreur', output)
        # La migration rapporte succès partiel
        self.assertIn('Migration terminée', output)

    # -----------------------------------------------------------------------
    # 2.9 — step parallel_group orphelin (aucun parent) → warning, step supprimé
    # -----------------------------------------------------------------------

    def test_orphan_parallel_group_warning_and_removed(self):
        """2.9: parallel_group orphelin (aucun parent) → warning affiché, step supprimé."""
        # pg1 est orphelin : aucun autre step ne pointe vers lui
        steps = [
            _make_platform_step('start', 1, on_success_step_ids=['end']),
            _make_pg_step('pg1', ['branch1', 'branch2']),  # orphelin !
            _make_platform_step('branch1', 2),
            _make_platform_step('branch2', 3),
            _make_platform_step('end', 4, on_success_step_ids=[]),
        ]
        action = self._create_workflow_action(name='Workflow orphelin', execution_steps=steps)

        out = StringIO()
        call_command('migrate_parallel_group', stdout=out)
        output = out.getvalue()

        # Warning affiché
        self.assertIn('orphelin', output)
        self.assertIn("'pg1'", output)

        # Step parallel_group supprimé de la DB
        action.refresh_from_db()
        result_steps = action.execution_steps
        self.assertFalse(
            any(s.get('step_type') == 'parallel_group' for s in result_steps)
        )

        # Les autres steps sont intacts (start → end)
        start = next(s for s in result_steps if s['step_id'] == 'start')
        self.assertEqual(start['on_success_step_ids'], ['end'])
