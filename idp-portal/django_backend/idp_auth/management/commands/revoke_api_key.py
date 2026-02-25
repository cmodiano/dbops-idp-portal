from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from idp_auth.models import APIKey


class Command(BaseCommand):
    help = 'Révoque une API key (soft delete : is_active=False).'

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--id', type=int, default=None, help='ID de la clé')
        parser.add_argument('--name', default=None, help='Nom de la clé')
        parser.add_argument('--user', default=None, help='Username du propriétaire (avec --name)')

    def handle(self, *args: Any, **options: Any) -> None:
        key_id = options['id']
        name = options['name']
        username = options['user']

        if key_id is None and name is None:
            raise CommandError("Fournir --id OU --name (avec optionnellement --user).")

        try:
            if key_id is not None:
                instance = APIKey.objects.get(pk=key_id)
            else:
                qs = APIKey.objects.filter(name=name)
                if username:
                    qs = qs.filter(user__username=username)
                instance = qs.get()  # DoesNotExist ou MultipleObjectsReturned
        except APIKey.DoesNotExist:
            raise CommandError("Clé introuvable.")
        except APIKey.MultipleObjectsReturned:
            raise CommandError("Plusieurs clés correspondent. Précisez --user ou utilisez --id.")

        if not instance.is_active:
            self.stdout.write(
                self.style.WARNING(f"Clé '{instance.name}' (ID={instance.id}) est déjà révoquée.")
            )
            return

        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])
        self.stdout.write(
            self.style.SUCCESS(
                f"Clé '{instance.name}' (ID={instance.id}, user={instance.user.username}) révoquée."
            )
        )
