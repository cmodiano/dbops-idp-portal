"""
Story 64.10 : Commande management detect_drift.
Compare la base de données avec un répertoire de configuration YAML
et identifie les entités synchronisées, divergées, absentes de la DB,
ou absentes du YAML.

Usage: python manage.py detect_drift --config-dir ./idp-config/ [--format text|json]
"""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand

from catalog.models import Action, BusinessRulePolicy, Tag
from core.exceptions import InvalidStateError
from catalog.services_export_import import export_action_yaml
from catalog.services_export_import_policies import export_policy_yaml
from catalog.services_export_import_tags import export_tags_yaml
from core.models import FeatureFlag
from core.services_export_import import export_feature_flags_yaml
from core.services_iac_utils import parse_yaml
from integrations.models import Integration, IntegrationTypeCatalogue
from integrations.services_export_import import export_integration_yaml
from integrations.services_export_import_types import export_integration_types_yaml
from profiles.models import Profile
from profiles.services_export_import import export_profile_yaml
from reference.models import RefCategory, RefEngine
from reference.services_export_import import export_reference_yaml


# DRIFT_ORDER : (path_pattern, label, key_field, entity_type, export_fn, db_keys_fn)
# entity_type:
#   "per_file"         → export_fn(key: str) -> bytes, un fichier par entité
#   "single_file"      → export_fn() -> bytes, spec = list[dict] avec key_field
#   "single_file_list" → export_fn() -> bytes, spec = list[str] (tags)
DRIFT_ORDER = [
    (
        "reference/engines.yaml",
        "engines",
        "code",
        "single_file",
        lambda: export_reference_yaml("engines"),
        lambda: set(RefEngine.objects.values_list("code", flat=True)),
    ),
    (
        "reference/categories.yaml",
        "categories",
        "code",
        "single_file",
        lambda: export_reference_yaml("categories"),
        lambda: set(RefCategory.objects.values_list("code", flat=True)),
    ),
    (
        "tags.yaml",
        "tags",
        None,
        "single_file_list",
        export_tags_yaml,
        lambda: set(Tag.objects.values_list("name", flat=True)),
    ),
    (
        "feature-flags.yaml",
        "flags",
        "flag_key",
        "single_file",
        export_feature_flags_yaml,
        lambda: set(FeatureFlag.objects.values_list("flag_key", flat=True)),
    ),
    (
        "integration-types/",
        "int-types",
        "code",
        "per_file",
        lambda key: export_integration_types_yaml(key),
        lambda: set(IntegrationTypeCatalogue.objects.values_list("code", flat=True)),
    ),
    (
        "integrations/",
        "integrations",
        "name",
        "per_file",
        lambda key: export_integration_yaml(key),
        lambda: set(Integration.objects.values_list("name", flat=True)),
    ),
    (
        "policies/",
        "policies",
        "name",
        "per_file",
        lambda key: export_policy_yaml(key),
        lambda: set(BusinessRulePolicy.objects.values_list("name", flat=True)),
    ),
    (
        "actions/",
        "actions",
        "name",
        "per_file",
        lambda key: export_action_yaml(key),
        lambda: set(Action.objects.values_list("name", flat=True)),
    ),
    (
        "profiles/",
        "profiles",
        "name",
        "per_file",
        lambda key: export_profile_yaml(key),
        lambda: set(Profile.objects.values_list("name", flat=True)),
    ),
]


def _canonical(spec: Any) -> str:
    """Sérialise en JSON canonique (sort_keys=True) pour comparaison fiable."""
    return json.dumps(spec, sort_keys=True, default=str)


def _specs_equal(spec_a: Any, spec_b: Any) -> bool:
    return _canonical(spec_a) == _canonical(spec_b)


def _empty_result() -> dict:
    return {"in_sync": [], "diverged": [], "missing_in_db": [], "missing_in_yaml": []}


class Command(BaseCommand):
    help = "Compare la base de données avec un répertoire de configuration YAML."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--config-dir",
            required=True,
            help="Chemin vers le répertoire idp-config/",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Format de sortie (défaut : text)",
        )

    def _process_per_file(
        self,
        config_dir: Path,
        path_pattern: str,
        label: str,
        key_field: str | None,
        export_fn: Any,
        db_keys_fn: Any,
    ) -> dict:
        """Traite les entités dont chaque fichier YAML correspond à une entité."""
        full_path = config_dir / path_pattern
        if not full_path.is_dir():
            self.stderr.write(f"  \u26a0 {path_pattern} \u2014 introuvable, ignor\u00e9")
            return _empty_result()

        yaml_map: dict[str, Any] = {}
        for f in sorted(list(full_path.glob("*.yaml")) + list(full_path.glob("*.yml"))):
            try:
                parsed = parse_yaml(f.read_bytes())
                key = parsed["metadata"][key_field]
            except (KeyError, TypeError) as exc:
                self.stderr.write(
                    f"  \u26a0 {f.name} \u2014 cl\u00e9 '{key_field}' introuvable dans metadata ({exc}), ignor\u00e9"
                )
                continue
            except InvalidStateError as exc:
                self.stderr.write(f"  \u26a0 {f.name} \u2014 YAML invalide ({exc}), ignor\u00e9")
                continue
            if key in yaml_map:
                self.stderr.write(
                    f"  \u26a0 cl\u00e9 dupliqu\u00e9e '{key}' dans {path_pattern} \u2014 {f.name} \u00e9crase le fichier pr\u00e9c\u00e9dent"
                )
            yaml_map[key] = parsed.get("spec", {})

        db_keys = db_keys_fn()
        result = _empty_result()

        for key in sorted(set(yaml_map.keys()) | db_keys):
            in_yaml = key in yaml_map
            in_db = key in db_keys

            if in_yaml and not in_db:
                result["missing_in_db"].append(key)
            elif in_db and not in_yaml:
                result["missing_in_yaml"].append(key)
            else:
                db_yaml_bytes = export_fn(key)
                db_parsed = parse_yaml(db_yaml_bytes)
                db_spec = db_parsed.get("spec", {})
                file_spec = yaml_map[key]
                if _specs_equal(file_spec, db_spec):
                    result["in_sync"].append(key)
                else:
                    result["diverged"].append({"name": key, "label": label})

        return result

    def _process_single_file(
        self,
        config_dir: Path,
        path_pattern: str,
        label: str,
        key_field: str | None,
        bulk_export_fn: Any,
        db_keys_fn: Any,  # noqa: ARG002 — non utilisé : les clés DB viennent de bulk_export_fn()
    ) -> dict:
        """Traite les entités dont toutes les entités sont dans un seul fichier YAML (spec = list[dict])."""
        full_path = config_dir / path_pattern
        if not full_path.is_file():
            self.stderr.write(f"  \u26a0 {path_pattern} \u2014 introuvable, ignor\u00e9")
            return _empty_result()

        file_parsed = parse_yaml(full_path.read_bytes())
        file_spec_items = file_parsed.get("spec", []) or []
        yaml_map = {item[key_field]: item for item in file_spec_items}

        db_yaml_bytes = bulk_export_fn()
        db_parsed = parse_yaml(db_yaml_bytes)
        db_spec_items = db_parsed.get("spec", []) or []
        db_map = {item[key_field]: item for item in db_spec_items}

        result = _empty_result()

        for key in sorted(set(yaml_map.keys()) | set(db_map.keys())):
            in_yaml = key in yaml_map
            in_db = key in db_map

            if in_yaml and not in_db:
                result["missing_in_db"].append(key)
            elif in_db and not in_yaml:
                result["missing_in_yaml"].append(key)
            else:
                if _specs_equal(yaml_map[key], db_map[key]):
                    result["in_sync"].append(key)
                else:
                    result["diverged"].append({"name": key, "label": label})

        return result

    def _process_single_file_list(
        self,
        config_dir: Path,
        path_pattern: str,
        db_keys_fn: Any,
    ) -> dict:
        """Traite les tags : spec = liste de strings.

        Pour ce type, la comparaison se fait clé-à-clé (présence/absence uniquement) —
        pas besoin d'exporter les données DB en YAML car il n'y a pas de spec à comparer.
        """
        full_path = config_dir / path_pattern
        if not full_path.is_file():
            self.stderr.write(f"  \u26a0 {path_pattern} \u2014 introuvable, ignor\u00e9")
            return _empty_result()

        file_parsed = parse_yaml(full_path.read_bytes())
        file_spec_items = file_parsed.get("spec", []) or []
        yaml_keys = set(file_spec_items)

        db_keys = db_keys_fn()
        result = _empty_result()

        for key in sorted(yaml_keys | db_keys):
            if key in yaml_keys and key not in db_keys:
                result["missing_in_db"].append(key)
            elif key in db_keys and key not in yaml_keys:
                result["missing_in_yaml"].append(key)
            else:
                result["in_sync"].append(key)

        return result

    def _print_text_report(self, report: dict) -> None:
        self.stdout.write("\n--- R\u00e9sultat detect_drift ---\n")
        totals = {"in_sync": 0, "diverged": 0, "missing_in_db": 0, "missing_in_yaml": 0}

        for label, res in report.items():
            s = res["in_sync"]
            d = res["diverged"]
            m_db = res["missing_in_db"]
            m_yaml = res["missing_in_yaml"]

            line = (
                f"{label:<12}: in_sync={len(s):<3} diverged={len(d):<3}"
                f" missing_in_db={len(m_db):<3} missing_in_yaml={len(m_yaml)}"
            )
            self.stdout.write(line)
            if m_db:
                self.stdout.write(f"  \u26a0 missing_in_db  : {m_db}")
            if d:
                self.stdout.write(f"  \u26a0 diverged       : {d}")
            if m_yaml:
                self.stdout.write(f"  \u26a0 missing_in_yaml: {m_yaml}")

            totals["in_sync"] += len(s)
            totals["diverged"] += len(d)
            totals["missing_in_db"] += len(m_db)
            totals["missing_in_yaml"] += len(m_yaml)

        self.stdout.write("\n--- R\u00e9sum\u00e9 global ---")
        self.stdout.write(f"  Total in_sync        : {totals['in_sync']}")
        self.stdout.write(f"  Total diverged       : {totals['diverged']}")
        self.stdout.write(f"  Total missing_in_db  : {totals['missing_in_db']}")
        self.stdout.write(f"  Total missing_in_yaml: {totals['missing_in_yaml']}")

    def handle(self, *args: Any, **options: Any) -> None:
        config_dir = Path(options["config_dir"])
        fmt = options["format"]
        report: dict[str, dict] = {}

        for path_pattern, label, key_field, entity_type, export_fn, db_keys_fn in DRIFT_ORDER:
            if entity_type == "per_file":
                result = self._process_per_file(
                    config_dir, path_pattern, label, key_field, export_fn, db_keys_fn
                )
            elif entity_type == "single_file":
                result = self._process_single_file(
                    config_dir, path_pattern, label, key_field, export_fn, db_keys_fn
                )
            elif entity_type == "single_file_list":
                result = self._process_single_file_list(
                    config_dir, path_pattern, db_keys_fn
                )
            else:
                continue
            report[label] = result

        if fmt == "json":
            self.stdout.write(json.dumps(report, indent=2, default=str))
        else:
            self._print_text_report(report)
