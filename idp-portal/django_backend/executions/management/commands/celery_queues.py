"""
Management command: celery_queues

Story 47.4: Output the list of Celery queues derived from the AdapterRegistry,
for use in worker startup scripts.

Usage:
    python manage.py celery_queues
    python manage.py celery_queues --format=list

Worker startup example:
    celery -A idp_backend worker -Q $(python manage.py celery_queues)
"""
from __future__ import annotations

from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand

from adapters.registry import adapter_registry


class Command(BaseCommand):
    help = "Output Celery queues derived from the AdapterRegistry (Story 47.4)"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--format",
            choices=["comma", "list"],
            default="comma",
            help=(
                "Output format: 'comma' (default, for -Q flag) prints a "
                "comma-separated string; 'list' prints one queue per line."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        queues = adapter_registry.list_queues()
        if options["format"] == "comma":
            self.stdout.write(",".join(queues))
        else:
            for q in queues:
                self.stdout.write(q)
