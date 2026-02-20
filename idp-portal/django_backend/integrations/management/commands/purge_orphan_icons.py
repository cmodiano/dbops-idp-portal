"""
Management command: purge_orphan_icons

Deletes uploaded icon files from static/icons/ that are no longer referenced
by any Integration record in the database.

Usage:
    python manage.py purge_orphan_icons           # dry-run (shows what would be deleted)
    python manage.py purge_orphan_icons --delete  # actually delete the files
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from integrations.models import Integration


class Command(BaseCommand):
    help = "Delete uploaded icon files not referenced by any integration (orphans)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            default=False,
            help='Actually delete the orphan files (default: dry-run only).',
        )

    def handle(self, *args, **options):
        do_delete = options['delete']
        static_root = Path(getattr(settings, 'STATIC_ROOT', None) or (Path(settings.BASE_DIR) / 'static'))
        icons_dir = static_root / 'icons'

        if not icons_dir.exists():
            self.stdout.write(self.style.WARNING(f"Icons directory does not exist: {icons_dir}"))
            return

        # Collect all filenames currently referenced in the DB
        referenced = set()
        for icon_path in Integration.objects.exclude(icon__isnull=True).exclude(icon='').values_list('icon', flat=True):
            if icon_path and icon_path.startswith('/static/icons/'):
                filename = icon_path.removeprefix('/static/icons/').lstrip('/')
                if filename:
                    referenced.add(filename)

        self.stdout.write(f"Integrations referencing uploaded icons: {len(referenced)}")

        # Scan all files in icons_dir
        all_files = list(icons_dir.iterdir())
        orphans = [f for f in all_files if f.is_file() and f.name not in referenced]

        if not orphans:
            self.stdout.write(self.style.SUCCESS("No orphan icon files found."))
            return

        total_size = sum(f.stat().st_size for f in orphans)
        self.stdout.write(
            f"Found {len(orphans)} orphan file(s) "
            f"({total_size / 1024:.1f} KB total):"
        )
        for f in sorted(orphans):
            self.stdout.write(f"  {f.name}  ({f.stat().st_size} bytes)")

        if not do_delete:
            self.stdout.write(
                self.style.WARNING("\nDry-run mode — no files deleted. Re-run with --delete to remove them.")
            )
            return

        deleted = 0
        errors = 0
        for f in orphans:
            try:
                f.unlink()
                deleted += 1
            except OSError as exc:
                self.stderr.write(self.style.ERROR(f"  Failed to delete {f.name}: {exc}"))
                errors += 1

        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} orphan file(s)."))
        if errors:
            self.stderr.write(self.style.ERROR(f"{errors} file(s) could not be deleted."))
