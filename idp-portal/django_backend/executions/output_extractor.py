"""
Output Extractor — Story 57.2 (ADR-007 §3c)

Extrait des valeurs de l'output brut d'un step via dot-notation JSONPath simple
(ex : ``$.data.databases``). Stocke les résultats dans ``_step_outputs[step_id]``
du ContainerWorkflowRuntime pour permettre le chaînage de données entre steps.
"""

from typing import Any


class OutputExtractor:
    """
    Extrait des valeurs de l'output brut d'un step via dot-notation JSONPath simple.

    Expressions supportées : ``$.key``, ``$.key.subkey``, ``$.key.subkey.subsubkey``
    Préfixe ``$.`` optionnel (également accepté : ``$key``, ``key.subkey``).

    AC#2 : extraction via dot-notation, résultat stocké dans ``_step_outputs[step_id]``.
    AC#6 : si ``output_mapping`` vide → retourne ``{}``.
    AC#7 : si ``raw_output`` vide → retourne ``{}``.
    """

    def extract(self, raw_output: dict, output_mapping: dict | None) -> dict:
        """
        Extrait les valeurs de ``raw_output`` selon ``output_mapping``.

        Args:
            raw_output:     Dict brut retourné par le step (ex : ``{"data": {"databases": [...]}}``).
            output_mapping: Dict ``{alias: expression}`` (ex : ``{"databases": "$.data.databases"}``).

        Returns:
            Dict ``{alias: valeur_extraite}`` ; valeur = ``None`` si chemin introuvable.
            Retourne ``{}`` si ``output_mapping`` ou ``raw_output`` est vide/None.
        """
        if not raw_output:
            return {}
        if not isinstance(output_mapping, dict):
            return {}
        if not output_mapping:
            return {}
        result: dict = {}
        for key, path in output_mapping.items():
            if not isinstance(path, str):
                result[key] = None
            else:
                result[key] = self._resolve_path(raw_output, path)
        return result

    def _resolve_path(self, data: dict, path: str) -> Any:
        """
        Résout un chemin dot-notation dans ``data``.

        Args:
            data: Dict source.
            path: Expression JSONPath simple (ex : ``$.data.databases``).

        Returns:
            Valeur extraite, ou ``None`` si un segment du chemin est introuvable.
            Note: l'appelant (extract) valide que path est str avant d'appeler.
        """
        # Supprimer le préfixe "$." ou "$" si présent
        clean = path.lstrip("$").lstrip(".")
        if not clean:
            return None
        keys = clean.split(".")
        current: Any = data
        for k in keys:
            if isinstance(current, dict):
                current = current.get(k)
            else:
                return None
        return current
