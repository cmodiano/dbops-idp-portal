"""
Story 28.4, AC#8: Management command to migrate inline business_rule_policies to predefined BusinessRulePolicy entries.

Usage:
    python manage.py migrate_inline_policies --dry-run   # Preview only
    python manage.py migrate_inline_policies              # Execute migration
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.core.management.base import BaseCommand

from catalog.models import Action, BusinessRulePolicy

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate inline business_rule_policies JSON to predefined BusinessRulePolicy entries (Story 28.4, AC#8).'

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be migrated without making changes.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run = options['dry_run']
        actions_with_inline = Action.objects.filter(
            business_rule_policies__isnull=False,
            business_rule_policy__isnull=True,
        ).exclude(business_rule_policies={})

        total = actions_with_inline.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('Aucune action avec des règles inline à migrer.'))
            return

        self.stdout.write(f'Trouvé {total} action(s) avec des règles métier inline.')

        migrated = 0
        reused = 0
        created = 0

        for action in actions_with_inline.select_related('created_by'):
            policy_json = action.business_rule_policies
            if not policy_json or not isinstance(policy_json, dict):
                continue

            policy_json_str = json.dumps(policy_json, sort_keys=True)

            # Check if an identical policy already exists
            # MEDIUM-1: Optimize — use .only() to load minimal fields
            existing = None
            for candidate in BusinessRulePolicy.objects.only('id', 'policy_json', 'name'):
                if json.dumps(candidate.policy_json, sort_keys=True) == policy_json_str:
                    existing = candidate
                    break

            if existing:
                policy = existing
                if not dry_run:
                    reused += 1
            else:
                name = f'Migré depuis action "{action.name}"'
                # Truncate to 200 chars
                if len(name) > 200:
                    name = name[:197] + '...'
                # Ensure unique name
                base_name = name
                counter = 1
                while BusinessRulePolicy.objects.filter(name=name).exists():
                    suffix = f' ({counter})'
                    name = base_name[:200 - len(suffix)] + suffix
                    counter += 1

                if dry_run:
                    policy = None
                    self.stdout.write(f'  [DRY-RUN] Créerait: "{name}"')
                else:
                    if action.created_by is None:
                        self.stdout.write(self.style.WARNING(
                            f'  Avertissement: action "{action.name}" (id={action.id}) '
                            f'sans created_by — ignorée.'
                        ))
                        continue
                    policy = BusinessRulePolicy.objects.create(
                        name=name,
                        description=f'Migré automatiquement depuis l\'action "{action.name}"',
                        policy_json=policy_json,
                        is_active=True,
                        created_by=action.created_by,
                    )
                    created += 1

            if dry_run:
                self.stdout.write(
                    f'  [DRY-RUN] Action "{action.name}" (id={action.id}) → '
                    f'{"réutiliserait" if existing else "créerait nouvelle"} règle'
                )
            elif policy is not None:
                action.business_rule_policy = policy
                action.business_rule_policies = None
                action.save(update_fields=['business_rule_policy', 'business_rule_policies'])
                migrated += 1
                self.stdout.write(f'  Migré: action "{action.name}" → règle "{policy.name}"')

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\n[DRY-RUN] {total} action(s) seraient migrées. '
                f'Relancez sans --dry-run pour exécuter.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nMigration terminée: {migrated} action(s) migrées, '
                f'{created} règle(s) créée(s), {reused} règle(s) réutilisée(s).'
            ))
