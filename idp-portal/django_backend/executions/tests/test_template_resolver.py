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
        """AC#3 : filtre length autorisé."""
        resolver = StepTemplateResolver({"discovery": {"items": [1, 2, 3]}})
        result = resolver.resolve({"count": "{{ steps.discovery.items | length }}"})
        assert result == {"count": "3"}

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
        assert "val" in result

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
        import pytest as pt
        proxy = _StepOutputProxy({})
        with pt.raises(AttributeError):
            _ = proxy.__custom_private

    def test_steps_proxy_private_attr_raises(self):
        """_StepsProxy.__getattr__ lève AttributeError pour les attributs privés."""
        from executions.template_resolver import _StepsProxy
        import pytest as pt
        proxy = _StepsProxy({})
        with pt.raises(AttributeError):
            _ = proxy.__custom_private
