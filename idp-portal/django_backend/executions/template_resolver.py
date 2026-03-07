"""
Step Template Resolver — Story 57.2 (ADR-007 §3b)

Résout les références ``{{ steps.<step_id>.<field> }}`` dans les ``input_mapping``
d'un step en utilisant Jinja2 ``SandboxedEnvironment``.

Filtres autorisés : ``join``, ``length``, ``first``, ``default``, ``truncate``.
"""

from typing import Any, Iterator, cast

import jinja2
import jinja2.sandbox


# Ensemble des filtres Jinja2 autorisés dans les templates de workflow
_ALLOWED_FILTERS = frozenset({'join', 'length', 'first', 'default', 'truncate'})


class _StepOutputProxy:
    """
    Proxy exposant les outputs d'un step spécifique dans les templates Jinja2.

    Permet ``steps.discovery.databases`` → valeur extraite de ``_step_outputs["discovery"]``.
    Si la clé n'existe pas dans les outputs du step → retourne ``None`` (AC#4).
    """

    def __init__(self, outputs: dict):
        self._data = outputs if isinstance(outputs, dict) else {}

    def __getattr__(self, key: str) -> Any:
        # Éviter la récursion infinie sur les attributs privés
        if key.startswith('_'):
            raise AttributeError(key)
        return self._data.get(key)

    def __getitem__(self, key: str) -> Any:
        return self._data.get(key)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data.values())

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"_StepOutputProxy({self._data!r})"


class _StepsProxy:
    """
    Proxy exposant ``_step_outputs`` dans le contexte Jinja2 via ``steps.<step_id>``.

    Si ``step_id`` est absent de ``_step_outputs`` → retourne un proxy vide dont
    tous les accès retournent ``None`` (AC#4 : step SKIPPED → null).
    """

    def __init__(self, step_outputs: dict):
        self._data = step_outputs if isinstance(step_outputs, dict) else {}

    def __getattr__(self, step_id: str) -> _StepOutputProxy:
        if step_id.startswith('_'):
            raise AttributeError(step_id)
        outputs = self._data.get(step_id, {})
        return _StepOutputProxy(outputs)

    def __getitem__(self, step_id: str) -> _StepOutputProxy:
        return self.__getattr__(step_id)

    def __repr__(self) -> str:
        return f"_StepsProxy(keys={list(self._data.keys())!r})"


class StepTemplateResolver:
    """
    Résout les templates ``{{ steps.<step_id>.<field> }}`` dans les ``input_mapping``.

    Utilise ``jinja2.sandbox.SandboxedEnvironment`` pour la sécurité.
    Seuls les filtres ``join``, ``length``, ``first``, ``default``, ``truncate`` sont disponibles.

    AC#3 : résolution via Jinja2 SandboxedEnvironment avec filtres limités.
    AC#4 : step absent → accès retourne ``None`` (proxy vide).
    """

    def __init__(self, step_outputs: dict, execution_context: dict | None = None):
        """
        Initialise le resolver avec le contexte partagé des outputs de steps.

        Args:
            step_outputs: Dict ``{step_id: {alias: valeur}}`` issu de
                          ``ContainerWorkflowRuntime._step_outputs``.
            execution_context: Variables de contexte d'exécution (action_name,
                               environment, execution_id). Optionnel, défaut ``{}``.
        """
        self._step_outputs = step_outputs if isinstance(step_outputs, dict) else {}
        self._execution_context = execution_context or {}
        self._env = jinja2.sandbox.SandboxedEnvironment(
            undefined=jinja2.Undefined,
            # AC#4 : convertit None Python en chaîne vide pour éviter le rendu 'None'
            # (step absent ou champ absent → '' au lieu de 'None')
            finalize=lambda x: '' if x is None else x,
        )
        # Limiter les filtres aux seuls filtres autorisés (sécurité)
        self._env.filters = {
            k: v for k, v in self._env.filters.items()
            if k in _ALLOWED_FILTERS
        }
        # truncate(N) strict : pas de leeway (par défaut 5) pour garantir ≤ N caractères
        self._env.policies['truncate.leeway'] = 0

    def resolve(self, input_mapping: dict) -> dict:
        """
        Résout les templates dans ``input_mapping``.

        Args:
            input_mapping: Dict potentiellement imbriqué dont les valeurs string
                           peuvent contenir des références ``{{ steps.X.Y }}``.

        Returns:
            Nouveau dict avec toutes les références résolues.
            Retourne ``{}`` si ``input_mapping`` est vide/None.
        """
        if not input_mapping:
            return {}
        context = {**self._execution_context, 'steps': _StepsProxy(self._step_outputs)}
        return cast(dict, self._resolve_value(input_mapping, context))

    def _resolve_value(self, value: Any, context: dict) -> Any:
        """
        Résout récursivement une valeur (str, dict, list ou autre).

        Args:
            value:   Valeur à résoudre.
            context: Contexte Jinja2 (contient ``steps``).

        Returns:
            Valeur résolue du même type que ``value``.
        """
        if isinstance(value, str):
            try:
                rendered = self._env.from_string(value).render(context)
                # Jinja2 Undefined retourne une chaîne vide "" — conserver ce comportement
                return rendered
            except jinja2.exceptions.TemplateError:
                return value
        elif isinstance(value, dict):
            return {k: self._resolve_value(v, context) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_value(item, context) for item in value]
        return value
