"""
Story 39.3: Tests for migrate_inline_policies management command (AC#3).

Branches couvertes :
- total == 0 → message "Aucune action" + return
- dry_run=True + existing absent → affiche '[DRY-RUN] Créerait'
- dry_run=True + existing trouvé → affiche 'réutiliserait'
- dry_run=False + existing absent → crée BusinessRulePolicy, met à jour action
- dry_run=False + existing trouvé → réutilise la policy existante
- policy_json non-dict → continue (action ignorée)
- nom > 200 chars → tronqué à 197 + '...'
- conflit de nom → suffixe ' (1)' ajouté
"""

import pytest
from django.test import TestCase
from io import StringIO

from django.core.management import call_command

from catalog.models import Action, BusinessRulePolicy, ActionStatus, ActionItemType, ActionEngine, ActionPlatform
from tests.factories import UserFactory


VALID_POLICY_JSON = {
    "on_step_output": [
        {
            "when": {"step_type": "terraform_cloud"},
            "policy": {
                "type": "review_if_modified",
                "require_review_if_modified": [
                    {"resource_type": "azurerm_sql_database"}
                ]
            }
        }
    ]
}

# Différent du VALID_POLICY_JSON pour éviter la réutilisation
OTHER_POLICY_JSON = {
    "on_step_output": [
        {
            "when": {"step_type": "aap"},
            "policy": {
                "type": "review_if_modified",
                "require_review_if_modified": [
                    {"resource_type": "some_resource"}
                ]
            }
        }
    ]
}


@pytest.mark.django_db
class TestMigrateInlinePoliciesCommand(TestCase):
    """Tests de la commande migrate_inline_policies (Story 39.3, AC#3)."""

    def setUp(self):
        self.user = UserFactory(username='migrator', profile='dbops')

    def _create_action_with_inline_policy(self, name='Test Action', policy=None):
        """Helper : action publiée avec business_rule_policies inline et sans FK."""
        return Action.objects.create(
            name=name,
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
            business_rule_policies=policy if policy is not None else VALID_POLICY_JSON,
            business_rule_policy=None,
        )

    # -----------------------------------------------------------------------
    # 3.1 — total == 0 → message "Aucune action"
    # -----------------------------------------------------------------------

    def test_no_eligible_actions(self):
        """3.1: Aucune action inline → message succès, pas de création."""
        out = StringIO()
        call_command('migrate_inline_policies', stdout=out)
        self.assertIn('Aucune action', out.getvalue())

    # -----------------------------------------------------------------------
    # 3.2 — dry-run sans existing → affiche '[DRY-RUN] Créerait'
    # -----------------------------------------------------------------------

    def test_dry_run_creates_message_not_db(self):
        """3.2: --dry-run affiche 'Créerait' sans toucher la DB."""
        self._create_action_with_inline_policy()
        out = StringIO()
        call_command('migrate_inline_policies', '--dry-run', stdout=out)
        output = out.getvalue()
        self.assertIn('DRY-RUN', output)
        self.assertIn('Créerait', output)
        self.assertEqual(BusinessRulePolicy.objects.count(), 0)

    # -----------------------------------------------------------------------
    # 3.3 — dry-run avec existing → affiche 'réutiliserait'
    # -----------------------------------------------------------------------

    def test_dry_run_reuse_existing(self):
        """3.3: --dry-run affiche 'réutiliserait' si une policy identique existe déjà."""
        BusinessRulePolicy.objects.create(
            name='Existing Policy',
            policy_json=VALID_POLICY_JSON,
            is_active=True,
            created_by=self.user,
        )
        self._create_action_with_inline_policy()
        out = StringIO()
        call_command('migrate_inline_policies', '--dry-run', stdout=out)
        self.assertIn('réutiliserait', out.getvalue())

    # -----------------------------------------------------------------------
    # 3.4 — normal run crée BusinessRulePolicy et met à jour l'action
    # -----------------------------------------------------------------------

    def test_normal_run_creates_policy(self):
        """3.4: Sans --dry-run, crée une BusinessRulePolicy et met à jour l'action."""
        action = self._create_action_with_inline_policy()
        out = StringIO()
        call_command('migrate_inline_policies', stdout=out)
        self.assertEqual(BusinessRulePolicy.objects.count(), 1)
        action.refresh_from_db()
        self.assertIsNotNone(action.business_rule_policy_id)
        self.assertIsNone(action.business_rule_policies)

    # -----------------------------------------------------------------------
    # 3.5 — normal run réutilise une policy existante identique
    # -----------------------------------------------------------------------

    def test_normal_run_reuses_existing_policy(self):
        """3.5: Sans --dry-run, réutilise une policy existante identique."""
        existing = BusinessRulePolicy.objects.create(
            name='Existing',
            policy_json=VALID_POLICY_JSON,
            is_active=True,
            created_by=self.user,
        )
        action = self._create_action_with_inline_policy()
        call_command('migrate_inline_policies', stdout=StringIO())
        action.refresh_from_db()
        self.assertEqual(action.business_rule_policy_id, existing.id)
        self.assertEqual(BusinessRulePolicy.objects.count(), 1)

    # -----------------------------------------------------------------------
    # 3.6 — policy_json non-dict → continue (action ignorée)
    # -----------------------------------------------------------------------

    def test_policy_json_non_dict_skipped(self):
        """3.6: policy_json non-dict → action ignorée (continue), pas de création."""
        # Créer une action avec policy_json liste (non-dict)
        Action.objects.create(
            name='Action With List Policy',
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
            business_rule_policies=[{"on_step_output": []}],  # list, not dict
            business_rule_policy=None,
        )
        out = StringIO()
        call_command('migrate_inline_policies', stdout=out)
        output = out.getvalue()
        # Aucune BusinessRulePolicy créée car policy_json non-dict est ignorée
        self.assertEqual(BusinessRulePolicy.objects.count(), 0)
        # La commande détecte bien l'action (total == 1) mais le résumé indique 0 migré
        self.assertIn('Trouvé 1', output)
        self.assertIn('0 action(s) migrées', output)

    # -----------------------------------------------------------------------
    # 3.7 — nom > 200 chars → tronqué à 197 + '...'
    # -----------------------------------------------------------------------

    def test_name_truncation_for_long_action_names(self):
        """3.7: Action avec nom > 200 chars → nom de policy tronqué à 197 + '...'."""
        # Préfixe : 'Migré depuis action "' = 22 chars, suffixe = 1 char → 23 fixed
        # Pour dépasser 200 : nom > 177 chars
        long_name = 'A' * 185
        self._create_action_with_inline_policy(name=long_name)
        call_command('migrate_inline_policies', stdout=StringIO())
        policy = BusinessRulePolicy.objects.first()
        self.assertIsNotNone(policy)
        self.assertLessEqual(len(policy.name), 200)
        self.assertTrue(policy.name.endswith('...'))

    # -----------------------------------------------------------------------
    # 3.8 — conflit de nom → suffixe ' (1)' ajouté
    # -----------------------------------------------------------------------

    def test_duplicate_name_gets_suffix(self):
        """3.8: Conflit de nom → suffixe ' (1)'."""
        action = self._create_action_with_inline_policy(name='MyAction')
        expected_name = 'Migré depuis action "MyAction"'
        # Pré-créer une policy avec le même nom mais un JSON différent (évite réutilisation)
        BusinessRulePolicy.objects.create(
            name=expected_name,
            policy_json=OTHER_POLICY_JSON,
            is_active=True,
            created_by=self.user,
        )
        call_command('migrate_inline_policies', stdout=StringIO())
        policies = BusinessRulePolicy.objects.filter(
            name__startswith='Migré depuis action "MyAction"'
        )
        names = list(policies.values_list('name', flat=True))
        self.assertTrue(any('(1)' in n for n in names))
