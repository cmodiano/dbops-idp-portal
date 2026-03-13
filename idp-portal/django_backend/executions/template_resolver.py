"""
Step Template Resolver — Story 57.2 (ADR-007 §3b)

Résout les références ``{{ steps.<step_id>.<field> }}`` dans les ``input_mapping``
d'un step en utilisant Jinja2 ``SandboxedEnvironment``.

Filtres autorisés : ``join``, ``length``, ``first``, ``default``, ``truncate``.

Story 77.2 — Préservation des types natifs :
- Expression pure ``{{ steps.X.Y }}`` (un seul bloc, sans texte autour) :
  si la valeur résolue est list/dict/int/float/bool, retourne le type natif.
- Template mixte ``"Patch {{ steps.X.Y }}"`` : render() → string (comportement actuel).
"""

import re
from typing import Any, Iterator, cast

import jinja2
import jinja2.sandbox
import structlog

logger = structlog.get_logger(__name__)


# Ensemble des filtres Jinja2 autorisés dans les templates de workflow
_ALLOWED_FILTERS = frozenset({'join', 'length', 'first', 'default', 'truncate'})

# Regex détectant une expression Jinja pure : exactement un bloc {{ ... }} sans texte autour.
# Exemples : "{{ steps.X.Y }}", "{{ steps.X.Y | default('v', true) }}"
# Non-match : "Patch {{ steps.X.N }}", "{{ a }} et {{ b }}"
_PURE_EXPRESSION_RE = re.compile(r'^\s*\{\{(.+)\}\}\s*$', re.DOTALL)


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

        # Environnement sans finalize pour évaluation d'expressions pures (Story 77.2).
        # Permet de retourner None natif (et donc list/dict/bool réels) au lieu de ''.
        self._env_native = jinja2.sandbox.SandboxedEnvironment(
            undefined=jinja2.Undefined,
        )
        self._env_native.filters = {
            k: v for k, v in self._env_native.filters.items()
            if k in _ALLOWED_FILTERS
        }
        self._env_native.policies['truncate.leeway'] = 0

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

        Story 77.2 — Expression pure vs template mixte :
        - Expression pure (``{{ expr }}``) : si la valeur résolue est un type natif
          (list, dict, int, float, bool), retourner ce type sans stringification.
          Si la valeur est None (step/champ absent), retourner '' (AC#4, compat).
        - Template mixte (``"Prefix {{ expr }}"``) : render() → string (comportement actuel).

        Args:
            value:   Valeur à résoudre.
            context: Contexte Jinja2 (contient ``steps``).

        Returns:
            Valeur résolue (type natif pour expressions pures, string pour templates mixtes).
        """
        if isinstance(value, str):
            if _PURE_EXPRESSION_RE.match(value):
                return self._resolve_pure_expression(value, context)
            try:
                rendered = self._env.from_string(value).render(context)
                return rendered
            except jinja2.exceptions.TemplateError:
                return value
        elif isinstance(value, dict):
            return {k: self._resolve_value(v, context) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_value(item, context) for item in value]
        return value

    def _resolve_pure_expression(self, value: str, context: dict) -> Any:
        """
        Évalue une expression Jinja pure (``{{ expr }}``) et retourne la valeur Python native.

        Technique : wrapper l'expression en ``{% set _result = expr %}`` puis exécuter
        le template via ``new_context`` + ``root_render_func`` pour obtenir la valeur
        Python native depuis ``ctx.vars['_result']`` (sans passer par render() → str).

        Si la valeur est None ou Undefined (step/champ absent), retourne '' (compat AC#4).
        En cas d'erreur, bascule sur render() classique avec finalize.

        Args:
            value:   String matchant ``_PURE_EXPRESSION_RE``.
            context: Contexte Jinja2.

        Returns:
            Valeur Python native (list, dict, int, float, bool, str ou '').
        """
        try:
            expr_inner = _PURE_EXPRESSION_RE.match(value).group(1).strip()  # type: ignore[union-attr]
            wrapper = f"{{% set _result = {expr_inner} %}}"
            template = self._env_native.from_string(wrapper)

            # Exécuter le template dans un Context et lire la variable _result
            ctx = template.new_context(context)
            list(template.root_render_func(ctx))  # exécuter le {% set %}
            native_value = ctx.vars.get('_result', jinja2.Undefined())

            # Jinja2 Undefined → step/champ absent → '' (compat AC#4)
            if isinstance(native_value, jinja2.Undefined):
                return ''

            # None Python → '' (compat AC#4, finalize habituel)
            if native_value is None:
                return ''

            # Type natif (list, dict, scalaires) : retourner tel quel
            return native_value

        except jinja2.exceptions.TemplateError as e:
            # Fallback : render() classique avec finalize (évite de masquer d'autres bugs)
            logger.warning(
                "template_resolver_pure_expression_fallback",
                expression=value[:200] if len(value) > 200 else value,
                error=str(e),
            )
            try:
                return self._env.from_string(value).render(context)
            except jinja2.exceptions.TemplateError:
                return value
