"""
Story 24.4 (AC1): Management command to analyze all integrations against the type catalogue.
Read-only analysis — does NOT modify any data.
Usage: python manage.py analyze_integrations
"""

import json
from pathlib import Path

import structlog
from django.core.management.base import BaseCommand
from django.utils import timezone

from integrations.models import Integration, IntegrationTypeCatalogue
from integrations.validation_service import IntegrationValidationService

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = 'Analyse toutes les intégrations existantes par rapport au catalogue des types'

    def handle(self, *args, **options):
        correlation_id = f"analyze-{timezone.now().strftime('%Y%m%d-%H%M%S')}"

        logger.info(
            "integration_analysis_started",
            correlation_id=correlation_id,
            command="analyze_integrations",
        )

        # Load catalogue info
        active_types = list(
            IntegrationTypeCatalogue.objects.filter(is_active=True).values_list('code', flat=True)
        )
        all_types_count = IntegrationTypeCatalogue.objects.filter(is_active=True).count()

        integrations = Integration.objects.all().order_by('id')

        valid_list = []
        deprecated_list = []
        invalid_list = []

        for integration in integrations:
            status = IntegrationValidationService.validate_integration(integration)

            entry = {
                'id': integration.id,
                'name': integration.name,
                'type': integration.type,
                'status': str(status),
            }

            if status == 'valid':
                valid_list.append(entry)
            elif status == 'deprecated':
                entry['reason'] = 'type_inactive'
                deprecated_list.append(entry)
            else:
                entry['reason'] = 'type_not_found'
                invalid_list.append(entry)

        total = len(valid_list) + len(deprecated_list) + len(invalid_list)

        # Console report
        self.stdout.write('\n=== ANALYSE DES INTÉGRATIONS EXISTANTES ===')
        self.stdout.write(f'Catalogue chargé : {all_types_count} types actifs ({", ".join(active_types)})')
        self.stdout.write(f'\nIntégrations trouvées : {total} total')

        self.stdout.write(self.style.SUCCESS(f'\n  ✓ Valides (type dans catalogue actif) : {len(valid_list)}'))
        for e in valid_list:
            self.stdout.write(f'    - ID {e["id"]}: {e["name"]} (type: {e["type"]}) ✓')

        self.stdout.write(self.style.WARNING(f'\n  ⚠ Dépréciées (type dans catalogue mais is_active=False) : {len(deprecated_list)}'))
        for e in deprecated_list:
            self.stdout.write(f'    - ID {e["id"]}: {e["name"]} (type: {e["type"]}) — type déprécié')

        self.stdout.write(self.style.ERROR(f'\n  ✗ Invalides (type inexistant dans catalogue) : {len(invalid_list)}'))
        for e in invalid_list:
            self.stdout.write(f'    - ID {e["id"]}: {e["name"]} (type: {e["type"]}) — type inconnu')

        # Recommendations
        self.stdout.write('\n=== RECOMMANDATIONS ===')
        self.stdout.write(f'1. Valides ({len(valid_list)}) : Aucune action nécessaire')
        self.stdout.write(f'2. Dépréciées ({len(deprecated_list)}) : Vérifier les workflows utilisant ces intégrations, prévoir migration vers types supportés')
        if invalid_list:
            self.stdout.write(f'3. Invalides ({len(invalid_list)}) : ATTENTION — Ces intégrations bloquent l\'exécution :')
            self.stdout.write('   - Soit créer les types manquants dans le catalogue (IntegrationTypeCatalogue)')
            self.stdout.write('   - Soit migrer vers des types existants')
            self.stdout.write('   - Soit marquer comme \'legacy\' (lecture seule, aucune nouvelle utilisation)')
        else:
            self.stdout.write(f'3. Invalides (0) : Aucune intégration invalide')

        self.stdout.write('\nPour migrer automatiquement les intégrations :')
        self.stdout.write('  python manage.py migrate_integrations --auto')
        self.stdout.write('\nPour marquer les invalides comme \'legacy\' :')
        self.stdout.write('  python manage.py migrate_integrations --mark-legacy')

        # Save JSON report
        now = timezone.now()
        report = {
            'analysis_date': now.isoformat(),
            'correlation_id': correlation_id,
            'catalogue_types_count': all_types_count,
            'catalogue_types_active': active_types,
            'integrations_total': total,
            'integrations_valid': len(valid_list),
            'integrations_deprecated': len(deprecated_list),
            'integrations_invalid': len(invalid_list),
            'details': {
                'valid': valid_list,
                'deprecated': deprecated_list,
                'invalid': invalid_list,
            },
            'recommendations': [
                f'{len(valid_list)} intégrations valides - aucune action',
                f'{len(deprecated_list)} intégrations dépréciées - vérifier workflows et planifier migration',
                f'{len(invalid_list)} intégrations invalides - {"BLOCKER pour exécution, action requise" if invalid_list else "aucune"}',
            ],
        }

        # MEDIUM-1 FIX: Write to logs/integrations/ directory
        logs_dir = Path('logs/integrations')
        logs_dir.mkdir(parents=True, exist_ok=True)
        filename = logs_dir / f'integration_analysis_{now.strftime("%Y%m%d_%H%M%S")}.json'

        # Atomic write: write to temp file then rename (prevents corruption)
        temp_filename = filename.with_suffix('.json.tmp')
        with open(temp_filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        temp_filename.replace(filename)

        self.stdout.write(self.style.SUCCESS(f'\nRapport sauvegardé : {filename}'))

        logger.info(
            "integration_analysis_completed",
            correlation_id=correlation_id,
            integrations_total=total,
            valid_count=len(valid_list),
            deprecated_count=len(deprecated_list),
            invalid_count=len(invalid_list),
        )
