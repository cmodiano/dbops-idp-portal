"""
Tests unitaires pour StepTemplateResolver — Story 57.2 (AC#3, #4)

Tests :
- Résolution simple d'une référence steps.X.Y
- Filtre join
- Filtre length
- Filtre first
- Filtre default
- Step absent → null (AC#4)
- input_mapping vide → {}
- Dict imbriqué (résolution récursive)
- Liste (résolution récursive)
- Valeur non-string laissée intacte
- Filtres non autorisés indisponibles
"""

import pytest

from executions.template_resolver import StepTemplateResolver


class TestStepTemplateResolver:
    """Tests unitaires pour StepTemplateResolver (pas de DB requise)."""

    def test_resolve_simple_step_reference(self):
        """AC#3 : résolution simple {{ steps.discovery.databases }}."""
        resolver = StepTemplateResolver({"discovery": {"databases": "PROD"}})
        result = resolver.resolve({"db": "{{ steps.discovery.databases }}"})
        assert result == {"db": "PROD"}

    def test_resolve_filter_join(self):
        """AC#3 : filtre join autorisé."""
        resolver = StepTemplateResolver({"discovery": {"databases": ["DB1", "DB2"]}})
        result = resolver.resolve({"dbs": "{{ steps.discovery.databases | join(', ') }}"})
        assert result == {"dbs": "DB1, DB2"}

    def test_resolve_filter_length(self):
        """AC#3 : filtre length autorisé — retourne int (type natif, Story 77.2)."""
        resolver = StepTemplateResolver({"discovery": {"items": [1, 2, 3]}})
        result = resolver.resolve({"count": "{{ steps.discovery.items | length }}"})
        # Story 77.2 : expression pure → type natif ; length retourne int
        assert result == {"count": 3}

    def test_resolve_filter_first(self):
        """AC#3 : filtre first autorisé."""
        resolver = StepTemplateResolver({"discovery": {"databases": ["DB1", "DB2"]}})
        result = resolver.resolve({"first_db": "{{ steps.discovery.databases | first }}"})
        assert result == {"first_db": "DB1"}

    def test_resolve_filter_default(self):
        """AC#3 : filtre default autorisé avec boolean=True (None est falsy en Python).

        Note : en Jinja2, `| default('x')` ne s'applique qu'à Undefined.
        Pour Python None (retourné par le proxy), utiliser `| default('x', true)`
        qui traite également les valeurs falsy (None, '', 0, etc.).
        """
        resolver = StepTemplateResolver({"discovery": {}})
        result = resolver.resolve({"val": "{{ steps.discovery.missing | default('fallback', true) }}"})
        assert result == {"val": "fallback"}

    def test_resolve_missing_step_renders_as_empty_string(self):
        """AC#4 : step absent → proxy retourne Python None → finalize convertit en ''.

        Le proxy _StepOutputProxy retourne None Python pour les champs absents.
        Le SandboxedEnvironment utilise finalize=lambda x: '' if x is None else x
        pour convertir None en chaîne vide (au lieu de 'None').
        """
        resolver = StepTemplateResolver({})
        result = resolver.resolve({"val": "{{ steps.create_change.number }}"})
        # Python None → finalize → '' (AC#4 : step absent → valeur vide/null)
        assert result["val"] == ""

    def test_resolve_missing_step_field_with_default_boolean(self):
        """AC#4 : champ absent dans step existant → None → default(boolean=True) s'applique."""
        resolver = StepTemplateResolver({"discovery": {"databases": ["DB1"]}})
        result = resolver.resolve({"val": "{{ steps.discovery.missing_field | default('', true) }}"})
        assert result == {"val": ""}

    def test_resolve_empty_input_mapping_returns_empty(self):
        """input_mapping vide → {} (pas d'erreur)."""
        resolver = StepTemplateResolver({"discovery": {"databases": ["DB1"]}})
        assert resolver.resolve({}) == {}

    def test_resolve_none_input_mapping_returns_empty(self):
        """input_mapping None → {} (pas d'erreur)."""
        resolver = StepTemplateResolver({})
        assert resolver.resolve(None) == {}

    def test_resolve_nested_dict(self):
        """Résolution récursive dans un dict imbriqué."""
        resolver = StepTemplateResolver({"discovery": {"db": "PROD"}})
        result = resolver.resolve({
            "extra_vars": {
                "target_db": "{{ steps.discovery.db }}",
                "static_value": "unchanged",
            }
        })
        assert result == {
            "extra_vars": {
                "target_db": "PROD",
                "static_value": "unchanged",
            }
        }

    def test_resolve_list_of_strings(self):
        """Résolution récursive dans une liste."""
        resolver = StepTemplateResolver({"step1": {"name": "mydb"}})
        result = resolver.resolve({"items": ["{{ steps.step1.name }}", "static"]})
        assert result == {"items": ["mydb", "static"]}

    def test_resolve_non_string_value_unchanged(self):
        """Valeurs non-string (int, bool, None) laissées intactes."""
        resolver = StepTemplateResolver({})
        result = resolver.resolve({
            "num": 42,
            "flag": True,
            "nothing": None,
        })
        assert result == {"num": 42, "flag": True, "nothing": None}

    def test_resolve_no_template_syntax_unchanged(self):
        """Chaîne sans template Jinja2 retournée telle quelle."""
        resolver = StepTemplateResolver({})
        result = resolver.resolve({"val": "plain string"})
        assert result == {"val": "plain string"}

    def test_resolve_step_outputs_initialized_empty(self):
        """StepTemplateResolver avec dict vide — pas d'erreur."""
        resolver = StepTemplateResolver({})
        result = resolver.resolve({"val": "{{ steps.nonexistent.field }}"})
        assert result["val"] == ""

    def test_resolve_multiple_steps(self):
        """Résolution depuis plusieurs steps dans le même input_mapping."""
        resolver = StepTemplateResolver({
            "discovery": {"db": "PROD"},
            "create_change": {"change_number": "CHG001"},
        })
        result = resolver.resolve({
            "db": "{{ steps.discovery.db }}",
            "change": "{{ steps.create_change.change_number }}",
        })
        assert result == {"db": "PROD", "change": "CHG001"}

    def test_resolve_disallowed_filter_not_available(self):
        """Filtres non listés dans ALLOWED_FILTERS ne sont pas disponibles."""
        resolver = StepTemplateResolver({"discovery": {"data": "hello world"}})
        # Le filtre 'upper' n'est pas dans ALLOWED_FILTERS → TemplateError → retourne la valeur brute
        result = resolver.resolve({"val": "{{ steps.discovery.data | upper }}"})
        # En cas d'erreur de filtre → valeur brute retournée (non modifiée)
        assert result["val"] == "{{ steps.discovery.data | upper }}"

    def test_steps_proxy_allows_hyphenated_step_id_via_item_access(self):
        """Accès via steps['step-with-hyphen'] pour les step_id avec tirets."""
        resolver = StepTemplateResolver({"create-change": {"number": "CHG999"}})
        # Via accès dict : {{ steps['create-change'].number }}
        result = resolver.resolve({"change": "{{ steps['create-change'].number }}"})
        assert result == {"change": "CHG999"}

    def test_step_output_proxy_item_access(self):
        """_StepOutputProxy.__getitem__ accessible directement."""
        from executions.template_resolver import _StepOutputProxy
        proxy = _StepOutputProxy({"key": "value", "other": 42})
        assert proxy["key"] == "value"
        assert proxy["other"] == 42
        assert proxy["missing"] is None

    def test_step_output_proxy_iter(self):
        """_StepOutputProxy.__iter__ itère sur les valeurs."""
        from executions.template_resolver import _StepOutputProxy
        proxy = _StepOutputProxy({"a": 1, "b": 2})
        values = list(proxy)
        assert 1 in values
        assert 2 in values

    def test_step_output_proxy_len(self):
        """_StepOutputProxy.__len__ retourne le nombre d'entrées."""
        from executions.template_resolver import _StepOutputProxy
        proxy = _StepOutputProxy({"a": 1, "b": 2, "c": 3})
        assert len(proxy) == 3

    def test_step_output_proxy_private_attr_raises(self):
        """_StepOutputProxy.__getattr__ lève AttributeError pour les attributs privés."""
        from executions.template_resolver import _StepOutputProxy

        proxy = _StepOutputProxy({})
        with pytest.raises(AttributeError):
            _ = proxy._private

    def test_steps_proxy_private_attr_raises(self):
        """_StepsProxy.__getattr__ lève AttributeError pour les attributs privés."""
        from executions.template_resolver import _StepsProxy

        proxy = _StepsProxy({})
        with pytest.raises(AttributeError):
            _ = proxy._private

    # --- Story 63.4 : truncate + execution_context ---

    def test_resolve_filter_truncate(self):
        """AC#2 : filtre truncate disponible — tronque à N caractères."""
        long_text = "A" * 600
        resolver = StepTemplateResolver({"step1": {"platform_logs": long_text}})
        result = resolver.resolve({"logs": "{{ steps.step1.platform_logs | truncate(500) }}"})
        # truncate(500) produit une chaîne ≤ 500 chars (ajoute '...' à la fin)
        assert len(result["logs"]) <= 500
        assert result["logs"].endswith("...")

    def test_resolve_execution_context_variables(self):
        """AC#1 : action_name, environment, execution_id résolus depuis execution_context."""
        resolver = StepTemplateResolver(
            {},
            execution_context={
                'action_name': 'Oracle Patching PROD',
                'environment': 'prod',
                'execution_id': 42,
            },
        )
        result = resolver.resolve({
            "subject": "✅ {{ action_name }} terminé dans {{ environment }}",
            "body": "Exécution {{ execution_id }} : {{ action_name }} terminé.",
        })
        assert result["subject"] == "✅ Oracle Patching PROD terminé dans prod"
        assert result["body"] == "Exécution 42 : Oracle Patching PROD terminé."

    def test_resolve_missing_execution_context_variable_renders_empty(self):
        """AC#1 : variable de contexte absente → chaîne vide (finalize)."""
        resolver = StepTemplateResolver(
            {},
            execution_context={'action_name': 'Test Action'},
        )
        # 'environment' non fourni → Jinja2 Undefined → finalize → ''
        result = resolver.resolve({"val": "{{ environment }}"})
        assert result["val"] == ""

    def test_resolve_backward_compatible_without_execution_context(self):
        """AC#1/AC#5 : StepTemplateResolver({}) sans execution_context fonctionne."""
        resolver = StepTemplateResolver({"step1": {"field": "value"}})
        result = resolver.resolve({"out": "{{ steps.step1.field }}"})
        assert result == {"out": "value"}


# ---------------------------------------------------------------------------
# Story 77.2 — Préservation des types natifs pour expressions pures
# ---------------------------------------------------------------------------

class TestStory772NativeTypePreservation:
    """
    Story 77.2 : expressions pures {{ expr }} → type Python natif préservé.
    Templates mixtes → string (comportement actuel).
    """

    # AC1 — Expression pure → type natif

    def test_pure_expression_list_returns_list(self):
        """AC1 : expression pure avec valeur liste → retourne list, pas string."""
        resolver = StepTemplateResolver({"discovery": {"databases": ["DB1", "DB2"]}})
        result = resolver.resolve({"dbs": "{{ steps.discovery.databases }}"})
        assert result["dbs"] == ["DB1", "DB2"]
        assert isinstance(result["dbs"], list), f"Attendu list, reçu {type(result['dbs'])}"

    def test_pure_expression_dict_returns_dict(self):
        """AC1 : expression pure avec valeur dict → retourne dict, pas string."""
        resolver = StepTemplateResolver({"discovery": {"config": {"key": "val", "count": 3}}})
        result = resolver.resolve({"cfg": "{{ steps.discovery.config }}"})
        assert result["cfg"] == {"key": "val", "count": 3}
        assert isinstance(result["cfg"], dict), f"Attendu dict, reçu {type(result['cfg'])}"

    def test_pure_expression_int_returns_int(self):
        """AC1 : expression pure avec valeur int → retourne int, pas string."""
        resolver = StepTemplateResolver({"step1": {"count": 42}})
        result = resolver.resolve({"n": "{{ steps.step1.count }}"})
        assert result["n"] == 42
        assert isinstance(result["n"], int), f"Attendu int, reçu {type(result['n'])}"

    def test_pure_expression_float_returns_float(self):
        """AC1 : expression pure avec valeur float → retourne float, pas string."""
        resolver = StepTemplateResolver({"step1": {"ratio": 3.14}})
        result = resolver.resolve({"r": "{{ steps.step1.ratio }}"})
        assert result["r"] == 3.14
        assert isinstance(result["r"], float), f"Attendu float, reçu {type(result['r'])}"

    def test_pure_expression_bool_true_returns_bool(self):
        """AC1 : expression pure avec valeur bool True → retourne bool, pas string."""
        resolver = StepTemplateResolver({"step1": {"success": True}})
        result = resolver.resolve({"ok": "{{ steps.step1.success }}"})
        assert result["ok"] is True
        assert isinstance(result["ok"], bool), f"Attendu bool, reçu {type(result['ok'])}"

    def test_pure_expression_bool_false_returns_bool(self):
        """AC1 : expression pure avec valeur bool False → retourne bool, pas string."""
        resolver = StepTemplateResolver({"step1": {"success": False}})
        result = resolver.resolve({"ok": "{{ steps.step1.success }}"})
        assert result["ok"] is False
        assert isinstance(result["ok"], bool), f"Attendu bool, reçu {type(result['ok'])}"

    def test_pure_expression_string_returns_string(self):
        """AC1 : expression pure avec valeur string → retourne string (inchangé)."""
        resolver = StepTemplateResolver({"step1": {"name": "PROD"}})
        result = resolver.resolve({"n": "{{ steps.step1.name }}"})
        assert result["n"] == "PROD"
        assert isinstance(result["n"], str)

    def test_pure_expression_absent_field_returns_empty_string(self):
        """AC1/AC#4 compat : expression pure avec champ absent → '' (compatibilité AC#4)."""
        resolver = StepTemplateResolver({"step1": {}})
        result = resolver.resolve({"val": "{{ steps.step1.missing }}"})
        assert result["val"] == ""

    def test_pure_expression_absent_step_returns_empty_string(self):
        """AC1/AC#4 compat : expression pure avec step absent → ''."""
        resolver = StepTemplateResolver({})
        result = resolver.resolve({"val": "{{ steps.nonexistent.field }}"})
        assert result["val"] == ""

    # AC2 — Template mixte → string

    def test_mixed_template_returns_string(self):
        """AC2 : template mixte (texte + expression) → string, pas type natif."""
        resolver = StepTemplateResolver({"step1": {"patch_number": 42}})
        result = resolver.resolve({"label": "Patch {{ steps.step1.patch_number }}"})
        assert result["label"] == "Patch 42"
        assert isinstance(result["label"], str)

    def test_mixed_template_with_list_returns_string(self):
        """AC2 : template mixte avec liste → string (repr de la liste)."""
        resolver = StepTemplateResolver({"step1": {"databases": ["DB1", "DB2"]}})
        result = resolver.resolve({"msg": "Bases: {{ steps.step1.databases }}"})
        assert isinstance(result["msg"], str)
        assert "DB1" in result["msg"]

    def test_two_expressions_in_one_string_returns_string(self):
        """AC2 : deux blocs {{ }} dans une même string → template mixte → string."""
        resolver = StepTemplateResolver({
            "step1": {"a": "FOO", "b": "BAR"},
        })
        result = resolver.resolve({"val": "{{ steps.step1.a }} et {{ steps.step1.b }}"})
        assert result["val"] == "FOO et BAR"
        assert isinstance(result["val"], str)

    def test_filter_join_on_list_returns_string(self):
        """AC2 : expression pure avec filtre join sur liste → string (filtre produit une string)."""
        resolver = StepTemplateResolver({"discovery": {"databases": ["DB1", "DB2"]}})
        result = resolver.resolve({"dbs": "{{ steps.discovery.databases | join(', ') }}"})
        assert result["dbs"] == "DB1, DB2"
        assert isinstance(result["dbs"], str)

    # AC3 — Test end-to-end (sans DB) du resolver avec extra_vars.databases

    def test_ac3_extra_vars_databases_as_list(self):
        """AC3 : extra_vars.databases via expression pure → liste Python, pas string."""
        resolver = StepTemplateResolver({"discovery": {"databases": ["DB1", "DB2"]}})
        result = resolver.resolve({
            "extra_vars": {
                "databases": "{{ steps.discovery.databases }}",
            }
        })
        assert result["extra_vars"]["databases"] == ["DB1", "DB2"]
        assert isinstance(result["extra_vars"]["databases"], list)
        assert result["extra_vars"]["databases"][0] == "DB1"

    def test_ac3_extra_vars_dict_preserved(self):
        """AC3 : extra_vars avec dict → dict Python préservé."""
        resolver = StepTemplateResolver({"step1": {"config": {"key": "val"}}})
        result = resolver.resolve({
            "extra_vars": {
                "config": "{{ steps.step1.config }}",
            }
        })
        assert result["extra_vars"]["config"] == {"key": "val"}
        assert isinstance(result["extra_vars"]["config"], dict)

    def test_pure_expression_with_whitespace_around_brackets(self):
        """AC1 : espaces autour des accolades → toujours détecté comme expression pure."""
        resolver = StepTemplateResolver({"step1": {"items": [1, 2, 3]}})
        result = resolver.resolve({"items": "  {{ steps.step1.items }}  "})
        assert result["items"] == [1, 2, 3]
        assert isinstance(result["items"], list)
