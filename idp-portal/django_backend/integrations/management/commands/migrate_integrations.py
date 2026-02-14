"""
Story 24.4 (AC2, AC3, AC10): Management command to migrate integrations.
- --auto: Update status based on catalogue validation
- --mark-legacy: Mark INVALID integrations with _legacy flag in config
- --dry-run: Preview changes without applying them
"""

import time

import structlog
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from catalog.models import Action
from core.models import AuditActionType, AuditEntityType
from core.services import AuditService
from integrations.models import Integration, IntegrationStatus
from integrations.validation_service import IntegrationValidationService

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = 'Migre les intégrations existantes vers le nouveau modèle typé du catalogue'

    def add_arguments(self, parser):
        parser.add_argument(
            '--auto',
            action='store_true',
            help='Met à jour automatiquement le statut de chaque intégration selon le catalogue',
        )
        parser.add_argument(
            '--mark-legacy',
            action='store_true',
            help='Marque les intégrations INVALID comme legacy (_legacy: true dans config)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Prévisualise les changements sans les appliquer',
        )

    def handle(self, *args, **options):
        auto = options['auto']
        mark_legacy = options['mark_legacy']
        dry_run = options['dry_run']

        if not auto and not mark_legacy:
            self.stderr.write(self.style.ERROR(
                'Erreur : spécifiez --auto et/ou --mark-legacy.\n'
                'Utilisez analyze_integrations pour un rapport en lecture seule.'
            ))
            return

        correlation_id = f"migrate-{timezone.now().strftime('%Y%m%d-%H%M%S')}"
        start_time = time.monotonic()

        logger.info(
            "integration_migration_started",
            correlation_id=correlation_id,
            command="migrate_integrations",
            options={"auto": auto, "mark_legacy": mark_legacy, "dry_run": dry_run},
            integrations_total=Integration.objects.count(),
        )

        if auto:
            self._handle_auto(correlation_id, dry_run)

        if mark_legacy:
            self._handle_mark_legacy(correlation_id, dry_run)

        duration_ms = round((time.monotonic() - start_time) * 1000)
        logger.info(
            "integration_migration_completed",
            correlation_id=correlation_id,
            duration_ms=duration_ms,
        )

    def _handle_auto(self, correlation_id: str, dry_run: bool):
        """AC2 + AC10: Auto-migrate integration statuses."""
        start_time = time.monotonic()  # MEDIUM-3 FIX: Track duration
        integrations = Integration.objects.all().order_by('id')
        total = integrations.count()

        changes = []
        stats = {'valid': 0, 'deprecated': 0, 'invalid': 0}

        for integration in integrations:
            new_status = IntegrationValidationService.validate_integration(integration)
            stats[str(new_status)] += 1
            old_status = integration.status

            if old_status != new_status:
                changes.append({
                    'integration': integration,
                    'id': integration.id,
                    'name': integration.name,
                    'old_status': old_status,
                    'new_status': str(new_status),
                })

        # Header
        if dry_run:
            self.stdout.write('\n=== MIGRATION DES INTÉGRATIONS (DRY-RUN) ===')
            self.stdout.write(self.style.WARNING('⚠ MODE DRY-RUN : Aucune modification ne sera effectuée'))
        else:
            self.stdout.write('\n=== MIGRATION DES INTÉGRATIONS ===')

        self.stdout.write(f'Date : {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}')
        self.stdout.write(f'Corrélation ID : {correlation_id}')
        self.stdout.write(f'\nIntégrations analysées : {total}')

        if not changes:
            self.stdout.write(self.style.SUCCESS(
                '\nAucune migration nécessaire. Toutes les intégrations sont à jour.'
            ))
            return

        # Apply changes (or preview)
        if dry_run:
            self.stdout.write('\nChangements prévus :')
            for c in changes:
                self.stdout.write(f'  - ID {c["id"]}: {c["name"]} — {c["old_status"]} → {c["new_status"]}')

            self.stdout.write(f'\nTotal : {len(changes)} intégrations seraient mises à jour')
            self.stdout.write('\nPour appliquer ces changements, exécutez sans --dry-run :')
            self.stdout.write('  python manage.py migrate_integrations --auto')
        else:
            self.stdout.write(f'Mises à jour effectuées : {len(changes)}')
            with transaction.atomic():
                for c in changes:
                    integ: Integration = c['integration']  # type: ignore[assignment]
                    integ.status = c['new_status']  # type: ignore[assignment]
                    integ.save(update_fields=['status', 'updated_at'])

                    AuditService.create_entry(
                        user_id='system',
                        action_type=AuditActionType.INTEGRATION_STATUS_UPDATED,
                        entity_type=AuditEntityType.INTEGRATION,
                        entity_id=integ.id,
                        details={
                            'integration_id': integ.id,
                            'integration_name': integ.name,
                            'old_status': c['old_status'],
                            'new_status': c['new_status'],
                            'reason': 'catalogue_validation',
                            'migrated_by': 'migrate_integrations_command',
                            'correlation_id': correlation_id,
                        },
                        ip_address='127.0.0.1',
                        correlation_id=correlation_id,
                    )

                    logger.info(
                        "integration_status_updated",
                        integration_id=integration.id,
                        integration_name=integration.name,
                        old_status=c['old_status'],
                        new_status=c['new_status'],
                        reason='catalogue_validation',
                        correlation_id=correlation_id,
                    )

                    status_symbol = '✓ MIGRÉ'
                    self.stdout.write(f'  - ID {c["id"]}: {c["name"]} — {c["old_status"]} → {c["new_status"]} {status_symbol}')

        # Final stats
        self.stdout.write('\nStatut final :')
        self.stdout.write(self.style.SUCCESS(f'  ✓ Valides : {stats["valid"]}'))
        self.stdout.write(self.style.WARNING(f'  ⚠ Dépréciées : {stats["deprecated"]}'))
        self.stdout.write(self.style.ERROR(f'  ✗ Invalides : {stats["invalid"]}'))

        if stats['invalid'] > 0:
            self.stdout.write(self.style.ERROR(
                f'\nATTENTION : {stats["invalid"]} intégrations invalides bloquent l\'exécution.'
            ))
            self.stdout.write('Recommandation : Exécuter avec --mark-legacy pour les désactiver proprement.')

        # MEDIUM-3 FIX: Log duration for _handle_auto step
        duration_auto_ms = round((time.monotonic() - start_time) * 1000)
        logger.info(
            "integration_auto_migration_step_completed",
            correlation_id=correlation_id,
            duration_ms=duration_auto_ms,
            integrations_updated=len(changes),
        )

    def _handle_mark_legacy(self, correlation_id: str, dry_run: bool):
        """AC3: Mark INVALID integrations as legacy."""
        start_time = time.monotonic()  # MEDIUM-3 FIX: Track duration
        invalid_integrations = Integration.objects.filter(status=IntegrationStatus.INVALID).order_by('id')

        if not invalid_integrations.exists():
            self.stdout.write(self.style.SUCCESS('\nAucune intégration invalide à marquer comme legacy.'))
            return

        if dry_run:
            self.stdout.write('\n=== MARQUAGE LEGACY (DRY-RUN) ===')
            self.stdout.write(self.style.WARNING('⚠ MODE DRY-RUN : Aucune modification ne sera effectuée'))
        else:
            self.stdout.write('\n=== MARQUAGE LEGACY ===')

        marked = []
        with transaction.atomic():
            for integration in invalid_integrations:
                config = integration.get_config() or {}
                config['_legacy'] = True
                marked.append({
                    'integration': integration,
                    'id': integration.id,
                    'name': integration.name,
                    'type': integration.type,
                })

                if not dry_run:
                    integration.set_config(config)
                    integration.save(update_fields=['config', 'updated_at'])

                    AuditService.create_entry(
                        user_id='system',
                        action_type=AuditActionType.INTEGRATION_MARKED_LEGACY,
                        entity_type=AuditEntityType.INTEGRATION,
                        entity_id=integration.id,
                        details={
                            'integration_id': integration.id,
                            'integration_name': integration.name,
                            'integration_type': integration.type,
                            'marked_by': 'migrate_integrations_command',
                            'correlation_id': correlation_id,
                        },
                        ip_address='127.0.0.1',
                        correlation_id=correlation_id,
                    )

                    logger.info(
                        "integration_marked_legacy",
                        integration_id=integration.id,
                        integration_name=integration.name,
                        integration_type=integration.type,
                        correlation_id=correlation_id,
                    )

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(f'Intégrations marquées comme legacy : {len(marked)}')
        for m in marked:
            self.stdout.write(f'  - ID {m["id"]}: {m["name"]} (type: {m["type"]}) ✓ LEGACY')

        self.stdout.write('\nCes intégrations ne peuvent plus être utilisées dans :')
        self.stdout.write('  - Nouvelles exécutions (bloquées par le moteur)')
        self.stdout.write('  - Nouveaux workflows (filtrées dans l\'UI)')

        # Detect workflows using legacy integrations
        legacy_ids = [m['id'] for m in marked]
        impacted_actions = Action.objects.filter(integration_id__in=legacy_ids).order_by('id')
        if impacted_actions.exists():
            self.stdout.write(self.style.WARNING('\nWorkflows/Actions existants utilisant ces intégrations :'))
            for action in impacted_actions:
                legacy_name = next(
                    (m['name'] for m in marked if m['id'] == action.integration_id), 'Inconnu'
                )
                self.stdout.write(
                    f'  - Action "{action.name}" (ID {action.id}) utilise ID {action.integration_id} ({legacy_name})'
                )
                self.stdout.write(
                    '  → ACTION REQUISE : Mettre à jour l\'action pour utiliser une intégration valide'
                )

        self.stdout.write('\nPour restaurer une intégration legacy :')
        self.stdout.write('  1. Créer le type correspondant dans IntegrationTypeCatalogue')
        self.stdout.write('  2. Exécuter : python manage.py migrate_integrations --auto')  # MEDIUM-2 FIX: Corrected command
        self.stdout.write('  3. Retirer la clé "_legacy" du config')

        # MEDIUM-3 FIX: Log duration for _handle_mark_legacy step
        duration_legacy_ms = round((time.monotonic() - start_time) * 1000)
        logger.info(
            "integration_mark_legacy_step_completed",
            correlation_id=correlation_id,
            duration_ms=duration_legacy_ms,
            integrations_marked=len(marked),
        )
