"""
Tests unitaires pour OutputExtractor — Story 57.2 (AC#2, #6, #7)

Tests :
- Extraction dot-notation simple
- Clé inexistante → None
- Mapping vide → {}
- raw_output vide → {}
- Expressions imbriquées multi-niveaux
- Préfixes JSONPath variés ($., $, aucun)
"""

from executions.output_extractor import OutputExtractor


class TestOutputExtractor:
    """Tests unitaires pour OutputExtractor (pas de DB requise)."""

    def test_extract_simple_path(self):
        """AC#2 : extraction simple via dot-notation $.key."""
        extractor = OutputExtractor()
        raw = {"databases": ["DB1", "DB2"]}
        result = extractor.extract(raw, {"databases": "$.databases"})
        assert result == {"databases": ["DB1", "DB2"]}

    def test_extract_nested_path(self):
        """AC#2 : extraction via dot-notation $.key.subkey."""
        extractor = OutputExtractor()
        raw = {"data": {"databases": ["DB1", "DB2"]}}
        result = extractor.extract(raw, {"databases": "$.data.databases"})
        assert result == {"databases": ["DB1", "DB2"]}

    def test_extract_deeply_nested_path(self):
        """AC#2 : extraction via dot-notation $.key.subkey.subsubkey."""
        extractor = OutputExtractor()
        raw = {"response": {"data": {"items": [1, 2, 3]}}}
        result = extractor.extract(raw, {"items": "$.response.data.items"})
        assert result == {"items": [1, 2, 3]}

    def test_extract_missing_key_returns_none(self):
        """AC#2 : clé inexistante → None (pas d'exception)."""
        extractor = OutputExtractor()
        result = extractor.extract({"a": 1}, {"missing": "$.missing_key"})
        assert result == {"missing": None}

    def test_extract_missing_nested_key_returns_none(self):
        """AC#2 : clé intermédiaire inexistante → None."""
        extractor = OutputExtractor()
        raw = {"data": {"name": "test"}}
        result = extractor.extract(raw, {"val": "$.data.missing.subkey"})
        assert result == {"val": None}

    def test_extract_empty_mapping_returns_empty(self):
        """AC#7 : output_mapping vide → {} (pas d'erreur)."""
        extractor = OutputExtractor()
        assert extractor.extract({"a": 1}, {}) == {}

    def test_extract_empty_raw_output_returns_empty(self):
        """AC#7 : raw_output vide → {} (pas d'erreur)."""
        extractor = OutputExtractor()
        assert extractor.extract({}, {"key": "$.key"}) == {}

    def test_extract_none_raw_output_returns_empty(self):
        """AC#7 : raw_output None → {} (pas d'erreur)."""
        extractor = OutputExtractor()
        assert extractor.extract(None, {"key": "$.key"}) == {}

    def test_extract_none_mapping_returns_empty(self):
        """AC#7 : output_mapping None → {} (pas d'erreur)."""
        extractor = OutputExtractor()
        assert extractor.extract({"a": 1}, None) == {}

    def test_extract_multiple_keys(self):
        """AC#2 : extraction de plusieurs clés depuis le même raw_output."""
        extractor = OutputExtractor()
        raw = {"data": {"db_name": "PROD", "count": 42}}
        result = extractor.extract(raw, {
            "db_name": "$.data.db_name",
            "count": "$.data.count",
        })
        assert result == {"db_name": "PROD", "count": 42}

    def test_extract_path_without_dollar_prefix(self):
        """Chemin sans préfixe '$.' — également supporté."""
        extractor = OutputExtractor()
        raw = {"key": "value"}
        result = extractor.extract(raw, {"k": "key"})
        assert result == {"k": "value"}

    def test_extract_path_with_dollar_no_dot(self):
        """Chemin avec '$' seul sans '.' — strip correct."""
        extractor = OutputExtractor()
        raw = {"key": "value"}
        result = extractor.extract(raw, {"k": "$key"})
        assert result == {"k": "value"}

    def test_extract_non_dict_intermediate_returns_none(self):
        """Si un segment intermédiaire n'est pas un dict → None."""
        extractor = OutputExtractor()
        raw = {"data": "not_a_dict"}
        result = extractor.extract(raw, {"val": "$.data.subkey"})
        assert result == {"val": None}

    def test_extract_scalar_value(self):
        """Extraction d'une valeur scalaire (int, str, bool)."""
        extractor = OutputExtractor()
        raw = {"change_number": "CHG001234"}
        result = extractor.extract(raw, {"change": "$.change_number"})
        assert result == {"change": "CHG001234"}

    def test_extract_none_value_in_output(self):
        """La valeur présente dans raw_output peut être None."""
        extractor = OutputExtractor()
        raw = {"data": {"value": None}}
        result = extractor.extract(raw, {"val": "$.data.value"})
        assert result == {"val": None}

    def test_extract_empty_path_string_returns_none(self):
        """Chemin vide (après strip '$' et '.') → None sans erreur."""
        extractor = OutputExtractor()
        raw = {"key": "value"}
        # Chemin qui devient vide après strip : "$.." → clean="" → None
        result = extractor.extract(raw, {"val": "$."})
        assert result == {"val": None}
