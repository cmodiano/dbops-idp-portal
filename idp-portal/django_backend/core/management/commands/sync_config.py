"""
Story 64.9 : Commande management sync_config.
Applique un répertoire de configuration IDP complet vers la base de données.

Usage: python manage.py sync_config --config-dir ./idp-config/ [--dry-run] [--validate-only] [--mode additive|full]
"""

import argparse
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from catalog.services_export_import import import_action_yaml
from catalog.services_export_import_policies import import_policy_yaml
from catalog.services_export_import_tags import import_tags_yaml
from core.exceptions import InvalidStateError
from core.services_export_import import import_feature_flags_yaml
from core.services_cac_utils import parse_yaml, validate_envelope
from integrations.services_export_import import import_integration_yaml
from integrations.services_export_import_types import import_integration_types_yaml
from profiles.services_export_import import import_profiles_yaml
from reference.services_export_import import import_reference_yaml


# SYNC_ORDER : (path_pattern, label, call_fn(content, mode, user) -> tuple[int, int, int])
# Ordre des dépendances : engines → categories → tags → flags → int-types → integrations → policies → actions → profiles
SYNC_ORDER = [
    (
        "reference/engines.yaml",
        "engines",
        lambda c, m, u: import_reference_yaml(c, "engines", mode=m, user=u),
    ),
    (
        "reference/categories.yaml",
        "categories",
        lambda c, m, u: import_reference_yaml(c, "categories", mode=m, user=u),
    ),
    (
        "tags.yaml",
        "tags",
        lambda c, m, u: import_tags_yaml(c, mode=m, user=u),
    ),
    (
        "feature-flags.yaml",
        "flags",
        lambda c, m, u: import_feature_flags_yaml(c, user=u),
    ),
    (
        "integration-types/",
        "int-types",
        lambda c, m, u: import_integration_types_yaml(c, mode=m, user=u),
    ),
    (
        "integrations/",
        "integrations",
        lambda c, m, u: import_integration_yaml(c, mode=m, user=u),
    ),
    (
        "policies/",
        "policies",
        lambda c, m, u: import_policy_yaml(c, mode=m, user=u),
    ),
    (
        "actions/",
        "actions",
        lambda c, m, u: import_action_yaml(c, mode=m, user=u),
    ),
    (
        "profiles/",
        "profiles",
        lambda c, m, u: import_profiles_yaml(c, user=u, mode=m),  # user avant mode
    ),
]


class Command(BaseCommand):
    help = (
        "Applique un répertoire de configuration IDP complet vers la base de données."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--config-dir",
            required=True,
            help="Chemin vers le répertoire idp-config/",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Valide les fichiers YAML sans écrire en DB",
        )
        parser.add_argument(
            "--validate-only",
            action="store_true",
            help="Validation schéma uniquement, sans écriture en DB",
        )
        parser.add_argument(
            "--mode",
            choices=["additive", "full"],
            default="additive",
            help="Mode de synchronisation (défaut : additive)",
        )

    def _validate_yaml_file(self, file_path: Path, label: str) -> None:
        """Parse + validate_envelope en mode dry-run. Lève CommandError si invalide."""
        content = file_path.read_bytes()
        try:
            parsed = parse_yaml(content)
            validate_envelope(parsed)
            self.stdout.write(f"  \u2713 {label} \u2014 valide")
        except InvalidStateError as exc:
            raise CommandError(f"Fichier invalide {label}: {exc.message}") from exc

    def handle(self, *args: Any, **options: Any) -> None:
        config_dir = Path(options["config_dir"])
        dry_run = options["dry_run"] or options["validate_only"]
        mode = options["mode"]
        total_results: dict[str, tuple[int, int, int]] = {}
        dry_run_count = 0

        for path_pattern, label, call_fn in SYNC_ORDER:
            full_path = config_dir / path_pattern

            if full_path.is_dir():
                files = sorted(
                    list(full_path.glob("*.yaml")) + list(full_path.glob("*.yml"))
                )
                label_created = label_updated = label_unchanged = 0

                for f in files:
                    if dry_run:
                        self._validate_yaml_file(f, f.name)
                        dry_run_count += 1
                    else:
                        content = f.read_bytes()
                        try:
                            created, updated, unchanged = call_fn(content, mode, None)
                        except InvalidStateError as exc:
                            raise CommandError(
                                f"Erreur dans {f}: {exc.message}"
                            ) from exc
                        label_created += created
                        label_updated += updated
                        label_unchanged += unchanged
                        self.stdout.write(
                            f"  {f.name}: created={created} updated={updated} unchanged={unchanged}"
                        )

                if not dry_run and files:
                    total_results[label] = (
                        label_created,
                        label_updated,
                        label_unchanged,
                    )

            elif full_path.is_file():
                if dry_run:
                    self._validate_yaml_file(full_path, path_pattern)
                    dry_run_count += 1
                else:
                    content = full_path.read_bytes()
                    try:
                        created, updated, unchanged = call_fn(content, mode, None)
                    except InvalidStateError as exc:
                        raise CommandError(
                            f"Erreur dans {path_pattern}: {exc.message}"
                        ) from exc
                    total_results[label] = (created, updated, unchanged)
                    self.stdout.write(
                        f"  {label}: created={created} updated={updated} unchanged={unchanged}"
                    )
            else:
                self.stdout.write(
                    f"  \u26a0 {path_pattern} \u2014 introuvable, ignor\u00e9"
                )

        # Récapitulatif final
        if dry_run:
            self.stdout.write(
                f"\n--- Dry-run termin\u00e9 \u2014 {dry_run_count} fichier(s) valid\u00e9(s) ---"
            )
        else:
            self.stdout.write("\n--- Sync termin\u00e9 ---")
            for lbl, (c, u, uc) in total_results.items():
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {lbl}: created={c} updated={u} unchanged={uc}"
                    )
                )
