#!/usr/bin/env python3
"""
Script pour appliquer la configuration IDP via API.

Usage:
  python scripts/apply_idp_config.py --dir idp-config/ [--validate-only] [--dry-run] [--mode additive|full]

Variables d'environnement requises (sauf --validate-only):
  IDP_API_URL   : URL de base de l'API IDP (sans trailing slash)
  IDP_API_TOKEN : Token Bearer pour l'authentification

Exemples:
  python scripts/apply_idp_config.py --env staging --dir idp-config/
  python scripts/apply_idp_config.py --validate-only --dir idp-config/
  python scripts/apply_idp_config.py --dry-run --dir idp-config/ --env staging
"""
import argparse
import os
import sys
from pathlib import Path
from typing import NamedTuple

import requests
import yaml

# ---------------------------------------------------------------------------
# Ordre canonique de synchronisation CaC
# Tuple: (path_pattern, entity_label, endpoint_path, per_file)
# per_file=True  → répertoire : itère tous les *.yaml/*.yml
# per_file=False → fichier unique
# ---------------------------------------------------------------------------
SYNC_ORDER = [
    ("reference/engines.yaml",    "engines",       "/api/v1/admin/reference/engines/sync/",    False),
    ("reference/categories.yaml", "categories",    "/api/v1/admin/reference/categories/sync/", False),
    ("tags.yaml",                 "tags",          "/api/v1/admin/tags/sync/",                 False),
    ("feature-flags.yaml",        "feature-flags", "/api/v1/admin/feature-flags/sync/",        False),
    ("integration-types/",        "int-types",     "/api/v1/admin/integration-types/sync/",    True),
    ("integrations/",             "integrations",  "/api/v1/admin/integrations/sync/",         True),
    ("policies/",                 "policies",      "/api/v1/admin/policies/sync/",             True),
    ("actions/",                  "actions",       "/api/v1/admin/actions/sync/",              True),
    ("profiles/",                 "profiles",      "/api/v1/admin/profiles/sync/",             True),
]

REQUIRED_ENVELOPE_KEYS = ("apiVersion", "kind", "metadata", "spec")
EXPECTED_API_VERSION = "idp/v1"


class SyncError(Exception):
    """Levée quand un appel API retourne un status non-200."""

    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {body}")


class SyncResult(NamedTuple):
    created: int
    updated: int
    unchanged: int


# ---------------------------------------------------------------------------
# Validation locale (sans Django) — AC #3, #4
# ---------------------------------------------------------------------------

def validate_envelope(file_path: Path) -> None:
    """Valide le YAML et la structure envelope idp/v1.

    Lève ValueError si le fichier est invalide.
    """
    try:
        with file_path.open("rb") as f:
            content = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML invalide : {exc}") from exc

    if not isinstance(content, dict):
        raise ValueError("Le fichier YAML doit être un objet (dict)")

    for key in REQUIRED_ENVELOPE_KEYS:
        if key not in content:
            raise ValueError(f"Clé manquante dans l'envelope : '{key}'")

    if content.get("apiVersion") != EXPECTED_API_VERSION:
        raise ValueError(
            f"apiVersion invalide : {content.get('apiVersion')!r} (attendu: {EXPECTED_API_VERSION!r})"
        )


def collect_files(config_dir: Path, path_pattern: str, per_file: bool) -> list[Path]:
    """Retourne la liste des fichiers à traiter pour une entrée SYNC_ORDER."""
    target = config_dir / path_pattern
    if per_file:
        if not target.is_dir():
            return []
        return sorted(
            p for p in target.iterdir()
            if p.suffix in (".yaml", ".yml") and p.is_file()
        )
    else:
        if target.is_file():
            return [target]
        return []


def validate_local(config_dir: Path) -> list[str]:
    """Valide tous les fichiers de config localement.

    Retourne une liste de messages d'erreur (vide si tout est valide).
    """
    errors: list[str] = []
    for path_pattern, entity_label, _, per_file in SYNC_ORDER:
        files = collect_files(config_dir, path_pattern, per_file)
        for f in files:
            try:
                validate_envelope(f)
            except ValueError as exc:
                errors.append(f"[{entity_label}] {f}: {exc}")
    return errors


# ---------------------------------------------------------------------------
# Appel HTTP — AC #8, #9
# ---------------------------------------------------------------------------

def sync_entity(
    api_url: str,
    token: str,
    endpoint_path: str,
    content: bytes,
    mode: str,
) -> SyncResult:
    """POST le contenu YAML vers l'endpoint sync.

    Retourne (created, updated, unchanged) ou lève SyncError si non-200.
    """
    url = f"{api_url}{endpoint_path}?mode={mode}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-yaml",
    }
    response = requests.post(url, data=content, headers=headers, timeout=60)
    if response.status_code != 200:
        raise SyncError(response.status_code, response.text)

    data = response.json().get("data", {})
    return SyncResult(
        created=data.get("created", 0),
        updated=data.get("updated", 0),
        unchanged=data.get("unchanged", 0),
    )


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Applique la configuration IDP via les endpoints sync."
    )
    parser.add_argument(
        "--dir",
        dest="config_dir",
        required=True,
        help="Répertoire racine contenant les fichiers de config IDP (ex: idp-config/)",
    )
    parser.add_argument(
        "--env",
        default=None,
        help="Nom de l'environnement cible (informatif, non utilisé dans les appels API)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Valide les fichiers localement sans appel API. Exit 0 si valide, 1 sinon.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valide localement et affiche les requêtes sans les exécuter.",
    )
    parser.add_argument(
        "--mode",
        choices=["additive", "full"],
        default="additive",
        help="Mode de synchronisation passé à chaque endpoint (défaut: additive)",
    )
    return parser.parse_args(argv)


def get_env_vars() -> tuple[str, str]:
    """Lit IDP_API_URL et IDP_API_TOKEN depuis l'environnement.

    Exit 1 avec message explicite si absents.
    """
    api_url = os.environ.get("IDP_API_URL", "").rstrip("/")
    token = os.environ.get("IDP_API_TOKEN", "")

    missing = []
    if not api_url:
        missing.append("IDP_API_URL")
    if not token:
        missing.append("IDP_API_TOKEN")

    if missing:
        print(
            f"ERREUR : variable(s) d'environnement manquante(s) : {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    return api_url, token


def print_summary(totals: dict[str, SyncResult]) -> None:
    """Affiche le résumé final par type."""
    print("\n--- Résumé de synchronisation ---")
    header = f"{'Type':<20} {'Fichiers':>8} {'Créés':>8} {'MàJ':>6} {'Inchangés':>10}"
    print(header)
    print("-" * len(header))
    grand_created = grand_updated = grand_unchanged = grand_files = 0
    for label, (files_count, result) in totals.items():
        print(
            f"{label:<20} {files_count:>8} {result.created:>8} {result.updated:>6} {result.unchanged:>10}"
        )
        grand_files += files_count
        grand_created += result.created
        grand_updated += result.updated
        grand_unchanged += result.unchanged
    print("-" * len(header))
    print(
        f"{'TOTAL':<20} {grand_files:>8} {grand_created:>8} {grand_updated:>6} {grand_unchanged:>10}"
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_dir = Path(args.config_dir)

    if not config_dir.is_dir():
        print(f"ERREUR : répertoire introuvable : {config_dir}", file=sys.stderr)
        return 1

    # --validate-only : validation locale uniquement
    if args.validate_only:
        errors = validate_local(config_dir)
        if errors:
            print("Erreurs de validation :", file=sys.stderr)
            for err in errors:
                print(f"  {err}", file=sys.stderr)
            return 1
        print(f"Validation OK — {config_dir} est valide.")
        return 0

    # Récupération des variables d'environnement (exit 1 si absentes)
    api_url, token = get_env_vars()

    env_label = args.env or "cible"
    dry_run = args.dry_run

    if dry_run:
        print(f"[DRY-RUN] Simulation de synchronisation vers {env_label}")
    else:
        print(f"Synchronisation vers {env_label} ({api_url})")

    # Validation locale systématique avant tout appel
    errors = validate_local(config_dir)
    if errors:
        print("Erreurs de validation :", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    # Boucle principale
    # totals: label → (files_count, SyncResult)
    totals: dict[str, tuple[int, SyncResult]] = {}

    for path_pattern, entity_label, endpoint_path, per_file in SYNC_ORDER:
        files = collect_files(config_dir, path_pattern, per_file)
        if not files:
            # Fichier/répertoire optionnel absent : ignorer
            continue

        entity_created = entity_updated = entity_unchanged = 0

        for file_path in files:
            content = file_path.read_bytes()
            url = f"{api_url}{endpoint_path}?mode={args.mode}"

            if dry_run:
                # AC #4 : afficher la requête sans l'exécuter
                print(f"[DRY-RUN] POST {url} ({len(content)} bytes)  ← {file_path.name}")
            else:
                try:
                    result = sync_entity(api_url, token, endpoint_path, content, args.mode)
                    entity_created += result.created
                    entity_updated += result.updated
                    entity_unchanged += result.unchanged
                    print(
                        f"  [{entity_label}] {file_path.name} — "
                        f"créés: {result.created}, màj: {result.updated}, inchangés: {result.unchanged}"
                    )
                except SyncError as exc:
                    # AC #9 : afficher code HTTP + body, exit 1
                    print(
                        f"ERREUR [{entity_label}] {file_path.name} — HTTP {exc.status_code}",
                        file=sys.stderr,
                    )
                    print(exc.body, file=sys.stderr)
                    return 1

        totals[entity_label] = (
            len(files),
            SyncResult(entity_created, entity_updated, entity_unchanged),
        )

    if dry_run:
        print("\n[DRY-RUN] Aucun appel HTTP effectué. Validation et affichage uniquement.")
        return 0

    # Résumé final
    print_summary(totals)
    return 0


if __name__ == "__main__":
    sys.exit(main())
