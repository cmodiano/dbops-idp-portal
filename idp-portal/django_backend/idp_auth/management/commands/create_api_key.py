from argparse import ArgumentParser
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from idp_auth.models import APIKey, APIKeyScope, User


class Command(BaseCommand):
    help = 'Crée une API key pour un utilisateur existant.'

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--user', required=True, help='Username du propriétaire')
        parser.add_argument('--name', required=True, help='Nom lisible de la clé (ex: CI-CD Prod)')
        parser.add_argument(
            '--scope',
            choices=APIKeyScope.values,
            default=None,
            help='Scope de la clé (executions, catalog, full)',
        )
        parser.add_argument(
            '--expires-in-days',
            type=int,
            default=None,
            help='Durée de validité en jours (optionnel)',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        user = User.objects.find_by_username(options['user'])
        if user is None:
            raise CommandError(f"Utilisateur '{options['user']}' introuvable.")

        try:
            instance, raw_key = APIKey.objects.create_key(
                user=user,
                name=options['name'],
                scope=options['scope'],
            )
        except ValueError as e:
            raise CommandError(str(e))

        expires_days = options['expires_in_days']
        if expires_days is not None:
            if expires_days < 1:
                raise CommandError("--expires-in-days doit être un entier positif (>= 1).")
            instance.expires_at = timezone.now() + timedelta(days=expires_days)
            instance.save(update_fields=['expires_at', 'updated_at'])

        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('API key créée avec succès'))
        self.stdout.write(f'  ID    : {instance.id}')
        self.stdout.write(f'  Nom   : {instance.name}')
        self.stdout.write(f'  User  : {user.username}')
        self.stdout.write(f'  Scope : {instance.scope or "full (non restreint)"}')
        if instance.expires_at:
            self.stdout.write(f'  Expire: {instance.expires_at.strftime("%Y-%m-%d")}')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('⚠️  Copiez cette clé MAINTENANT — elle ne sera plus affichée :'))
        self.stdout.write(self.style.SUCCESS(f'  {raw_key}'))
        self.stdout.write('=' * 60)
