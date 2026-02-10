"""
Story 24.3: Management command to validate all integrations against the type catalogue.
Usage: python manage.py validate_integrations [--dry-run]
"""

import sys

from django.core.management.base import BaseCommand

from integrations.validation_service import IntegrationValidationService


class Command(BaseCommand):
    help = 'Valide toutes les intégrations contre le catalogue des types'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche le rapport sans mettre à jour la base de données',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write('Mode DRY-RUN : aucune modification ne sera sauvegardée\n')

        stats = IntegrationValidationService.validate_all_integrations(dry_run=dry_run)

        self.stdout.write('\n' + '=' * 40)
        self.stdout.write('Integration Validation Report')
        self.stdout.write('=' * 40)
        self.stdout.write(self.style.SUCCESS(f'Valid: {stats["valid"]}'))
        self.stdout.write(self.style.ERROR(f'Invalid: {stats["invalid"]}'))
        self.stdout.write(self.style.WARNING(f'Deprecated: {stats["deprecated"]}'))
        self.stdout.write(f'Updated: {stats["updated"]} integrations status changed')
        self.stdout.write('=' * 40 + '\n')

        if stats['invalid'] > 0:
            self.stdout.write(self.style.ERROR('Some integrations are invalid!'))
            sys.exit(1)

        self.stdout.write(self.style.SUCCESS('All integrations validated successfully'))
