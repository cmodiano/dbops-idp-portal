"""
Story 27.7: Idempotent seed command for integration type catalogue.
Loads all integration types and their actions from the consolidated fixture.
Usage: python manage.py seed_integration_types [--force]
"""

import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand

from integrations.models import IntegrationAction, IntegrationTypeCatalogue

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Charge les types d\'intégration depuis les fixtures (idempotent)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force le rechargement même si les types existent déjà',
        )

    def handle(self, *args, **options):
        force = options['force']

        existing_types = set(
            IntegrationTypeCatalogue.objects.values_list('code', flat=True)
        )
        expected_types = {'aap', 'servicenow', 'tower', 'azure_devops',
                          'github_actions', 'terraform_cloud', 'vault', 'splunk',
                          'jira'}

        missing = expected_types - existing_types

        if not missing and not force:
            type_count = IntegrationTypeCatalogue.objects.filter(
                code__in=expected_types
            ).count()
            action_count = IntegrationAction.objects.filter(
                integration_type__code__in=expected_types
            ).count()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Tous les types existent déjà ({type_count} types, '
                    f'{action_count} actions). Utilisez --force pour recharger.'
                )
            )
            logger.info(
                'seed_integration_types: skip (all types exist)',
                extra={'type_count': type_count, 'action_count': action_count},
            )
            return

        if force and not missing:
            # Force reload: delete actions first to avoid unique constraint
            # violations (actions have auto-PK, not fixture-defined PK)
            IntegrationAction.objects.filter(
                integration_type__code__in=expected_types
            ).delete()
            self.stdout.write('Mode --force : actions supprimées, rechargement...')

        if missing:
            self.stdout.write(
                f'Types manquants : {", ".join(sorted(missing))}'
            )

        call_command('loaddata', 'integration_type_catalogue', verbosity=0)

        type_count = IntegrationTypeCatalogue.objects.filter(
            code__in=expected_types
        ).count()
        action_count = IntegrationAction.objects.filter(
            integration_type__code__in=expected_types
        ).count()

        self.stdout.write(
            self.style.SUCCESS(
                f'Seed terminé : {type_count} types, {action_count} actions chargés.'
            )
        )
        logger.info(
            'seed_integration_types: complete',
            extra={'type_count': type_count, 'action_count': action_count},
        )
