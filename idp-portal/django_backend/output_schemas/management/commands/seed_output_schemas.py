"""
Story 63.5: Commande de management pour charger les schémas d'output par défaut.
Usage: python manage.py seed_output_schemas [--force] [--mode=additive|full]
"""

import logging
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand
from django.db import transaction

from output_schemas.services_export_import import import_output_schemas_yaml

logger = logging.getLogger(__name__)

# Répertoire contenant les fichiers YAML seed, relatif à ce fichier
SEED_DIR = Path(__file__).resolve().parent.parent.parent / 'fixtures' / 'seed_schemas'

# Ordre de chargement : conventions plateforme AVANT les intégrations (parents avant enfants)
SEED_FILES_ORDERED = [
    SEED_DIR / 'platform-conventions' / 'aap-standard.yaml',
    SEED_DIR / 'integrations' / 'servicenow' / 'create_change.yaml',
    SEED_DIR / 'integrations' / 'servicenow' / 'update_change.yaml',
    SEED_DIR / 'integrations' / 'servicenow' / 'close_change.yaml',
    SEED_DIR / 'integrations' / 'servicenow' / 'get_change_status.yaml',
    SEED_DIR / 'integrations' / 'vault' / 'get_secret.yaml',
    SEED_DIR / 'integrations' / 'notification' / 'send_email.yaml',
    SEED_DIR / 'integrations' / 'notification' / 'send_teams.yaml',
]


class Command(BaseCommand):
    help = "Charge les schémas d'output par défaut (idempotent)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force le rechargement même si des schémas existent déjà',
        )
        parser.add_argument(
            '--mode',
            default='additive',
            choices=['additive', 'full'],
            help="Mode d'import : additive (upsert uniquement) ou full (supprime les absents)",
        )

    def handle(self, *args, **options):
        force = options['force']
        mode = options['mode']

        from output_schemas.models import OutputSchema

        existing_count = OutputSchema.objects.count()
        create_only = existing_count > 0 and not force
        if create_only:
            self.stdout.write(
                self.style.NOTICE(
                    f'{existing_count} schéma(s) existent déjà. '
                    'Ajout des schémas manquants uniquement (--force pour recharger).'
                )
            )

        if force and existing_count > 0:
            self.stdout.write(f'Mode --force : rechargement de {existing_count} schéma(s) existant(s)...')

        total_created = 0
        total_updated = 0
        total_unchanged = 0
        total_deleted = 0
        all_seed_names: list[str] = []

        with transaction.atomic():
            for yaml_path in SEED_FILES_ORDERED:
                if not yaml_path.exists():
                    self.stdout.write(
                        self.style.WARNING(f'Fichier manquant (ignoré) : {yaml_path}')
                    )
                    continue

                content = yaml_path.read_text(encoding='utf-8')

                # Collecter les noms de schémas seed pour la suppression post-étape (mode=full)
                try:
                    parsed = yaml.safe_load(content)
                    for item in (parsed or {}).get('items', []):
                        name = (item.get('metadata') or {}).get('name', '')
                        if name:
                            all_seed_names.append(name)
                except yaml.YAMLError:
                    pass  # import_output_schemas_yaml lèvera ValueError pour le même fichier

                # Toujours charger en mode additive par fichier : mode=full est traité en post-étape
                stats = import_output_schemas_yaml(
                    content, mode='additive', create_only=create_only
                )

                total_created += stats.get('created', 0)
                total_updated += stats.get('updated', 0)
                total_unchanged += stats.get('unchanged', 0)

                logger.debug(
                    'seed_output_schemas: file processed',
                    extra={
                        'seed_file': str(yaml_path.name),
                        'stats_created': stats.get('created', 0),
                        'stats_updated': stats.get('updated', 0),
                        'stats_unchanged': stats.get('unchanged', 0),
                    },
                )

            if mode == 'full' and all_seed_names:
                deleted_qs = OutputSchema.objects.exclude(name__in=all_seed_names)
                total_deleted = deleted_qs.count()
                deleted_qs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'Seed terminé : {total_created} créé(s), {total_updated} mis à jour, '
                f'{total_unchanged} inchangé(s), {total_deleted} supprimé(s). '
                f'[mode={mode}]'
            )
        )
        logger.info(
            'seed_output_schemas: complete',
            extra={
                'stats_created': total_created,
                'stats_updated': total_updated,
                'stats_unchanged': total_unchanged,
                'stats_deleted': total_deleted,
                'seed_mode': mode,
            },
        )
