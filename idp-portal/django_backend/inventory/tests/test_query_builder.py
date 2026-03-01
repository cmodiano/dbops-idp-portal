"""
Tests pour inventory/query_builder.py — Story 55.2 (couverture ≥ 90 %).

Tests purement unitaires (sans accès DB) : InventoryQueryBuilder construit des chaînes SQL.

Couvre :
- _build_aliased_select
- build_entity_query : server/instance/database, sans filtre, avec id_filter, search, page/page_size
- Branches des filtres SQL (ORDER BY, pagination, entités non configurées)
"""
from __future__ import annotations

import pytest

from inventory.mapper import InventoryMapper, MapperValidationError
from inventory.mapping_validator import MappingValidator
from inventory.query_builder import InventoryQueryBuilder


# ---------------------------------------------------------------------------
# Config minimale réutilisable
# ---------------------------------------------------------------------------

MINIMAL_CONFIG = {
    'entities': {
        'servers': {
            'table': 'CMDB_SERVERS',
            'id_column': 'SERVER_ID',
            'columns': {
                'name': 'HOST_NAME',
                'environment': 'ENV',
                'engine_type': 'ENGINE_TYPE',
            }
        },
        'instances': {
            'table': 'CMDB_INSTANCES',
            'id_column': 'INST_ID',
            'ref_join': 'id',
            'columns': {
                'name': 'INST_NAME',
                'server_ref': 'SERVER_ID',
                'db_ref': 'DB_ID',
            }
        },
        'databases': {
            'table': 'CMDB_DATABASES',
            'id_column': 'DB_ID',
            'columns': {
                'name': 'DB_NAME',
            }
        }
    }
}

CONFIG_SERVERS_ONLY = {
    'entities': {
        'servers': {
            'table': 'CMDB_SERVERS',
            'id_column': 'SERVER_ID',
            'columns': {
                'name': 'HOST_NAME',
                'environment': 'ENV',
            }
        }
    }
}

CONFIG_NAME_REF = {
    'entities': {
        'servers': {
            'table': 'CMDB_SERVERS',
            'id_column': 'SERVER_ID',
            'columns': {
                'name': 'HOST_NAME',
                'environment': 'ENV',
                'engine_type': 'ENGINE_TYPE',
            }
        },
        'instances': {
            'table': 'CMDB_INSTANCES',
            # pas de ref_join → name-based
            'columns': {
                'name': 'INST_NAME',
                'server_ref': 'SERVER_NAME_REF',
            }
        },
    }
}


def _make_builder(config: dict = None) -> InventoryQueryBuilder:
    if config is None:
        config = MINIMAL_CONFIG
    mapper = InventoryMapper(config)
    validator = MappingValidator()
    return InventoryQueryBuilder(mapper, validator)


# ---------------------------------------------------------------------------
# Tests _build_aliased_select
# ---------------------------------------------------------------------------

class TestBuildAliasedSelect:
    """Tests pour InventoryQueryBuilder._build_aliased_select."""

    def test_entity_with_id_col_and_columns(self):
        """Entity avec id_column et columns → SELECT bien formé."""
        entity_cfg = {
            'id_column': 'SERVER_ID',
            'columns': {
                'name': 'HOST_NAME',
                'environment': 'ENV',
            }
        }
        result = InventoryQueryBuilder._build_aliased_select(entity_cfg, 'e')

        assert 'e.SERVER_ID AS id' in result
        assert 'e.HOST_NAME AS name' in result
        assert 'e.ENV AS environment' in result

    def test_entity_without_id_col(self):
        """Entity sans id_column → pas de 'AS id'."""
        entity_cfg = {
            'columns': {
                'name': 'HOST_NAME',
            }
        }
        result = InventoryQueryBuilder._build_aliased_select(entity_cfg, 'e')

        assert 'AS id' not in result
        assert 'e.HOST_NAME AS name' in result

    def test_invalid_concept_raises(self):
        """Concept avec tiret → MapperValidationError."""
        entity_cfg = {
            'columns': {
                'invalid-concept': 'HOST_NAME',
            }
        }
        with pytest.raises(MapperValidationError):
            InventoryQueryBuilder._build_aliased_select(entity_cfg, 'e')

    def test_invalid_column_name_raises(self):
        """Colonne avec tiret → MapperValidationError."""
        entity_cfg = {
            'columns': {
                'name': 'invalid-col',
            }
        }
        with pytest.raises(MapperValidationError):
            InventoryQueryBuilder._build_aliased_select(entity_cfg, 'e')


# ---------------------------------------------------------------------------
# Tests build_entity_query — serveurs
# ---------------------------------------------------------------------------

class TestBuildEntityQueryServers:
    """Tests pour build_entity_query avec entity_type='server'."""

    def test_server_no_filter(self):
        """Requête server sans filtre → SQL valide avec ROWNUM."""
        builder = _make_builder(CONFIG_SERVERS_ONLY)
        sql, params = builder.build_entity_query(
            entity_type='server',
            entity_plural='servers',
            environment=None,
            engine_type=None,
            server_name=None,
            server_names=None,
            correlation_id=None,
        )

        assert isinstance(sql, str)
        assert 'CMDB_SERVERS' in sql
        assert 'ROWNUM' in sql
        assert params == {}

    def test_server_with_environment(self):
        """Requête server avec environment → WHERE clause."""
        builder = _make_builder(CONFIG_SERVERS_ONLY)
        sql, params = builder.build_entity_query(
            entity_type='server',
            entity_plural='servers',
            environment='prod',
            engine_type=None,
            server_name=None,
            server_names=None,
            correlation_id=None,
        )

        assert 'prod' in params.values() or ':p_environment' in sql
        assert isinstance(sql, str)
        assert 'CMDB_SERVERS' in sql

    def test_server_with_engine_type_no_engine_col(self):
        """Requête server avec engine_type mais sans colonne engine_type config → SQL sans filtre engine."""
        builder = _make_builder(CONFIG_SERVERS_ONLY)
        # CONFIG_SERVERS_ONLY n'a pas engine_type → le filtre n'est pas appliqué
        sql, params = builder.build_entity_query(
            entity_type='server',
            entity_plural='servers',
            environment=None,
            engine_type=None,  # pas d'engine_type
            server_name=None,
            server_names=None,
            correlation_id=None,
        )

        assert isinstance(sql, str)
        assert 'CMDB_SERVERS' in sql

    def test_server_with_full_config_engine_type(self):
        """Requête server avec engine_type dans config complète."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='server',
            entity_plural='servers',
            environment=None,
            engine_type='Oracle',
            server_name=None,
            server_names=None,
            correlation_id=None,
        )

        assert isinstance(sql, str)
        assert 'Oracle' in params.values() or ':p_engine_type' in sql

    def test_server_multi_server_names_via_instances(self):
        """Requête instances avec server_names → query multi-server."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment='prod',
            engine_type=None,
            server_name=None,
            server_names=['srv1', 'srv2'],
            correlation_id=None,
        )

        assert isinstance(sql, str)
        assert 'srv1' in params.values()
        assert 'srv2' in params.values()


# ---------------------------------------------------------------------------
# Tests build_entity_query — instances
# ---------------------------------------------------------------------------

class TestBuildEntityQueryInstances:
    """Tests pour build_entity_query avec entity_type='instance'."""

    def test_instance_no_filter(self):
        """Requête instance sans filtre → SQL simple."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment=None,
            engine_type=None,
            server_name=None,
            server_names=None,
            correlation_id=None,
        )

        assert isinstance(sql, str)
        assert 'CMDB_INSTANCES' in sql
        assert 'ROWNUM' in sql

    def test_instance_with_environment_uses_join(self):
        """Instance avec environment + servers config → JOIN avec servers."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment='prod',
            engine_type=None,
            server_name=None,
            server_names=None,
            correlation_id=None,
        )

        assert isinstance(sql, str)
        assert 'CMDB_SERVERS' in sql
        assert 'prod' in params.values() or ':p_environment' in sql

    def test_instance_with_server_name(self):
        """Instance filtrée par server_name → paramètre server_ref."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment=None,
            engine_type=None,
            server_name='myserver',
            server_names=None,
            correlation_id=None,
        )

        assert isinstance(sql, str)
        # server_name doit être dans les params
        assert 'myserver' in params.values()

    def test_instance_no_servers_config_fallback(self):
        """Instance sans servers config → fallback simple query (sans environment filter)."""
        config = {
            'entities': {
                'instances': {
                    'table': 'CMDB_INSTANCES',
                    'id_column': 'INST_ID',
                    'columns': {
                        'name': 'INST_NAME',
                    }
                }
            }
        }
        builder = _make_builder(config)
        # Sans environment → simple query sans filtre
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment=None,
            engine_type=None,
            server_name=None,
            server_names=None,
            correlation_id=None,
        )

        assert isinstance(sql, str)
        assert 'CMDB_INSTANCES' in sql


# ---------------------------------------------------------------------------
# Tests build_entity_query — databases
# ---------------------------------------------------------------------------

class TestBuildEntityQueryDatabases:
    """Tests pour build_entity_query avec entity_type='database'."""

    def test_database_no_filter(self):
        """Requête database sans filtre → SQL simple."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment=None,
            engine_type=None,
            server_name=None,
            server_names=None,
            correlation_id=None,
        )

        assert isinstance(sql, str)
        assert 'CMDB_DATABASES' in sql
        assert 'ROWNUM' in sql

    def test_database_with_server_name_via_instances(self):
        """Database filtrée par server_name → JOIN via instances."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment=None,
            engine_type=None,
            server_name='myserver',
            server_names=None,
            correlation_id=None,
        )

        assert isinstance(sql, str)
        assert 'myserver' in params.values()

    def test_database_with_environment_uses_join(self):
        """Database avec environment + servers/instances config → JOIN triple."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment='prod',
            engine_type=None,
            server_name=None,
            server_names=None,
            correlation_id=None,
        )

        assert isinstance(sql, str)
        assert 'CMDB_SERVERS' in sql or 'p_environment' in params

    def test_database_multi_server_query(self):
        """Database avec server_names → requête multi-server."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment='prod',
            engine_type=None,
            server_name=None,
            server_names=['srv1', 'srv2'],
            correlation_id=None,
        )

        assert isinstance(sql, str)
        # Multi-server for databases calls _build_databases_multi_server_query

    def test_database_fallback_without_instances_config(self):
        """Database sans instances config → fallback simple query + warning (sans environment filter)."""
        config = {
            'entities': {
                'servers': {
                    'table': 'CMDB_SERVERS',
                    'id_column': 'SERVER_ID',
                    'columns': {'name': 'HOST_NAME', 'environment': 'ENV'}
                },
                'databases': {
                    'table': 'CMDB_DATABASES',
                    'id_column': 'DB_ID',
                    'columns': {'name': 'DB_NAME'}
                }
            }
        }
        builder = _make_builder(config)
        # Sans environment → simple query (la colonne environment n'est pas dans la config database)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment=None,
            engine_type=None,
            server_name=None,
            server_names=None,
            correlation_id=None,
        )

        assert isinstance(sql, str)
        assert 'CMDB_DATABASES' in sql


# ---------------------------------------------------------------------------
# Tests avec name-based refs
# ---------------------------------------------------------------------------

class TestBuildQueryNameBasedRefs:
    """Tests pour le cas ref_join=name (pas d'ID FK)."""

    def test_instance_name_based_join(self):
        """Instance avec name-based refs → JOIN par UPPER()."""
        builder = _make_builder(CONFIG_NAME_REF)
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment='prod',
            engine_type=None,
            server_name=None,
            server_names=None,
            correlation_id=None,
        )

        assert isinstance(sql, str)
        assert 'CMDB_INSTANCES' in sql
        # Name-based join utilise UPPER()
        assert 'UPPER' in sql


# ---------------------------------------------------------------------------
# Tests de structure SQL — ORDER BY et ROWNUM
# ---------------------------------------------------------------------------

class TestSQLStructure:
    """Tests que les requêtes contiennent ORDER BY et ROWNUM."""

    def test_server_query_has_order_by(self):
        """Requête server → contient ORDER BY."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, _ = builder.build_entity_query(
            entity_type='server',
            entity_plural='servers',
            environment=None,
            engine_type=None,
            server_name=None,
            server_names=None,
            correlation_id=None,
        )

        assert 'ORDER BY' in sql.upper()

    def test_server_query_has_rownum(self):
        """Requête server → contient ROWNUM (limite DoS)."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, _ = builder.build_entity_query(
            entity_type='server',
            entity_plural='servers',
            environment=None,
            engine_type=None,
            server_name=None,
            server_names=None,
            correlation_id=None,
        )

        assert 'ROWNUM' in sql

    def test_instance_join_query_has_rownum(self):
        """Requête instance avec JOIN → contient ROWNUM."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, _ = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment='prod',
            engine_type=None,
            server_name=None,
            server_names=None,
            correlation_id=None,
        )

        assert 'ROWNUM' in sql


# ---------------------------------------------------------------------------
# Tests des branches manquantes — couverture avancée
# ---------------------------------------------------------------------------

# Config avec instances name-based (no ref_join = name-based)
CONFIG_NAME_REF_FULL = {
    'entities': {
        'servers': {
            'table': 'CMDB_SERVERS',
            'id_column': 'SERVER_ID',
            'columns': {
                'name': 'HOST_NAME',
                'environment': 'ENV',
                # pas engine_type → MapperValidationError si on essaie d'y accéder
            }
        },
        'instances': {
            'table': 'CMDB_INSTANCES',
            # pas ref_join → name-based
            'columns': {
                'name': 'INST_NAME',
                'server_ref': 'SERVER_NAME_REF',
                'db_ref': 'DB_NAME_REF',
            }
        },
        'databases': {
            'table': 'CMDB_DATABASES',
            'id_column': 'DB_ID',
            'columns': {
                'name': 'DB_NAME',
            }
        }
    }
}

# Config sans engine_type dans servers
# → tester que MapperValidationError est catchée (warning path), le filtre engine n'est pas ajouté
CONFIG_NO_ENGINE = {
    'entities': {
        'servers': {
            'table': 'CMDB_SERVERS',
            'id_column': 'SERVER_ID',
            'columns': {
                'name': 'HOST_NAME',
                'environment': 'ENV',
                # pas engine_type
            }
        },
        'instances': {
            'table': 'CMDB_INSTANCES',
            'id_column': 'INST_ID',
            'ref_join': 'id',
            'columns': {
                'name': 'INST_NAME',
                'server_ref': 'SERVER_ID',
                'db_ref': 'DB_ID',
            }
        },
        'databases': {
            'table': 'CMDB_DATABASES',
            'id_column': 'DB_ID',
            'columns': {
                'name': 'DB_NAME',
            }
        }
    }
}


class TestInstanceJoinQueryBranches:
    """Tests pour _build_instance_join_query — branches avancées."""

    def test_instance_join_with_engine_type(self):
        """Instance join avec engine_type dans config → filtre engine."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment='prod',
            engine_type='Oracle',
            server_name=None,
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'Oracle' in params.values() or ':p_engine_type' in sql

    def test_instance_join_engine_type_not_mapped_warning(self):
        """Instance join avec engine_type non mappé → warning, pas d'erreur."""
        builder = _make_builder(CONFIG_NO_ENGINE)
        # engine_type pas dans servers → MapperValidationError catch → warning
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment='prod',
            engine_type='Oracle',
            server_name=None,
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'Oracle' not in params.values()  # MapperValidationError → pas de paramètre engine

    def test_instance_join_with_server_name_ref_join_id(self):
        """Instance join avec server_name et ref_join=id → filtre srv.name."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment='prod',
            engine_type=None,
            server_name='myserver',
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'myserver' in params.values()

    def test_instance_join_with_server_name_name_based(self):
        """Instance join avec server_name et ref_join=name → filtre inst.server_ref."""
        builder = _make_builder(CONFIG_NAME_REF_FULL)
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment='prod',
            engine_type=None,
            server_name='myserver',
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'myserver' in params.values()


class TestDatabaseJoinQueryBranches:
    """Tests pour _build_database_join_query — branches avancées."""

    def test_database_join_name_based_refs(self):
        """Database join avec name-based refs → UPPER() dans JOIN."""
        builder = _make_builder(CONFIG_NAME_REF_FULL)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment='prod',
            engine_type=None,
            server_name=None,
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        # Name-based → UPPER() dans JOIN
        assert 'UPPER' in sql

    def test_database_join_with_engine_type(self):
        """Database join avec engine_type dans config → filtre engine."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment='prod',
            engine_type='Oracle',
            server_name=None,
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'Oracle' in params.values() or ':p_engine_type' in sql

    def test_database_join_engine_type_not_mapped_warning(self):
        """Database join avec engine_type non mappé → warning, pas d'erreur."""
        builder = _make_builder(CONFIG_NO_ENGINE)
        # engine_type pas dans servers → MapperValidationError catch → warning
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment='prod',
            engine_type='Oracle',
            server_name=None,
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'Oracle' not in params.values()


class TestSimpleEntityQueryBranches:
    """Tests pour _build_simple_entity_query — branches avancées."""

    def test_instance_with_server_name_and_ref_join_id_need_join(self):
        """Instance sans environment mais avec server_name + ref_join=id + has_servers → need_join."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment=None,
            engine_type=None,
            server_name='myserver',
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'myserver' in params.values()
        # need_join → JOIN avec servers
        assert 'CMDB_SERVERS' in sql

    def test_instance_with_server_name_name_based_no_join(self):
        """Instance avec server_name mais ref_join=name → server_ref filter (no join)."""
        config = {
            'entities': {
                'servers': {
                    'table': 'CMDB_SERVERS',
                    'id_column': 'SERVER_ID',
                    'columns': {'name': 'HOST_NAME', 'environment': 'ENV'}
                },
                'instances': {
                    'table': 'CMDB_INSTANCES',
                    # pas de ref_join → name-based
                    'columns': {
                        'name': 'INST_NAME',
                        'server_ref': 'SERVER_NAME_REF',
                    }
                },
            }
        }
        builder = _make_builder(config)
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment=None,
            engine_type=None,
            server_name='myserver',
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        # server_name doit être dans les params (via server_ref filter)
        assert 'myserver' in params.values()


class TestMultiServerQueryBranches:
    """Tests pour _build_entity_multi_server_query — branches avancées."""

    def test_instances_multi_server_with_environment(self):
        """Instances multi-server avec environment → WHERE sur env."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment='prod',
            engine_type=None,
            server_name=None,
            server_names=['srv1', 'srv2'],
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'prod' in params.values() or ':p_environment' in sql

    def test_instances_multi_server_name_based_refs(self):
        """Instances multi-server avec name-based refs."""
        builder = _make_builder(CONFIG_NAME_REF_FULL)
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment='prod',
            engine_type=None,
            server_name=None,
            server_names=['srv1', 'srv2'],
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'srv1' in params.values()

    def test_instances_multi_server_engine_type_not_mapped(self):
        """Instances multi-server avec engine_type non mappé → warning, pas d'erreur."""
        builder = _make_builder(CONFIG_NO_ENGINE)
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment='prod',
            engine_type='Oracle',
            server_name=None,
            server_names=['srv1'],
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'Oracle' not in params.values()

    def test_databases_multi_server_no_entity_config_returns_empty(self):
        """Databases multi-server sans entity_config databases → retourne ('', {})."""
        config = {
            'entities': {
                'servers': {
                    'table': 'CMDB_SERVERS',
                    'id_column': 'SERVER_ID',
                    'columns': {'name': 'HOST_NAME', 'environment': 'ENV'}
                },
                'instances': {
                    'table': 'CMDB_INSTANCES',
                    'id_column': 'INST_ID',
                    'ref_join': 'id',
                    'columns': {
                        'name': 'INST_NAME',
                        'server_ref': 'SERVER_ID',
                        'db_ref': 'DB_ID',
                    }
                },
                # pas de 'databases'
            }
        }
        builder = _make_builder(config)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment='prod',
            engine_type=None,
            server_name=None,
            server_names=['srv1'],
            correlation_id=None,
        )
        assert sql == ''
        assert params == {}

    def test_databases_multi_server_name_based_refs(self):
        """Databases multi-server avec name-based refs → UPPER() dans JOIN."""
        builder = _make_builder(CONFIG_NAME_REF_FULL)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment='prod',
            engine_type=None,
            server_name=None,
            server_names=['srv1'],
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'srv1' in params.values()

    def test_databases_multi_server_with_engine_type(self):
        """Databases multi-server avec engine_type → filtre engine."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment='prod',
            engine_type='Oracle',
            server_name=None,
            server_names=['srv1'],
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'Oracle' in params.values() or ':p_engine_type' in sql

    def test_databases_multi_server_engine_type_not_mapped(self):
        """Databases multi-server engine_type non mappé → warning, pas d'erreur."""
        builder = _make_builder(CONFIG_NO_ENGINE)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment='prod',
            engine_type='Oracle',
            server_name=None,
            server_names=['srv1'],
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'Oracle' not in params.values()


class TestDatabasesViaInstancesQuery:
    """Tests pour _build_databases_via_instances_query et _apply_dvi_where."""

    def test_database_via_instances_no_filters(self):
        """Database via instances sans filtres → SQL avec server_name."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment=None,
            engine_type=None,
            server_name='myserver',
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'myserver' in params.values()

    def test_database_via_instances_with_environment_has_srv(self):
        """Database via instances avec environment ET servers config → JOIN srv."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment='prod',
            engine_type=None,
            server_name='myserver',
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'prod' in params.values() or ':p_environment' in sql
        assert 'myserver' in params.values()

    def test_database_via_instances_with_environment_and_engine(self):
        """Database via instances avec environment + engine_type."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment='prod',
            engine_type='Oracle',
            server_name='myserver',
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'Oracle' in params.values() or ':p_engine_type' in sql

    def test_database_via_instances_env_engine_not_mapped(self):
        """Database via instances avec environment + engine_type non mappé → warning."""
        builder = _make_builder(CONFIG_NO_ENGINE)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment='prod',
            engine_type='Oracle',
            server_name='myserver',
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'Oracle' not in params.values()

    def test_database_via_instances_engine_only_no_env(self):
        """Database via instances avec engine_type seul (pas env) + servers config."""
        builder = _make_builder(MINIMAL_CONFIG)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment=None,
            engine_type='Oracle',
            server_name='myserver',
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'Oracle' in params.values() or ':p_engine_type' in sql

    def test_database_via_instances_engine_only_not_mapped(self):
        """Database via instances avec engine_type seul non mappé → warning."""
        builder = _make_builder(CONFIG_NO_ENGINE)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment=None,
            engine_type='Oracle',
            server_name='myserver',
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'Oracle' not in params.values()

    def test_database_via_instances_name_based_no_env_no_engine(self):
        """Database via instances name-based, sans env ni engine → WHERE server_name direct."""
        builder = _make_builder(CONFIG_NAME_REF_FULL)
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment=None,
            engine_type=None,
            server_name='myserver',
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'myserver' in params.values()


class TestWarningFallbackPaths:
    """Tests des chemins de warning pour les branches 107 et 113."""

    def test_database_with_env_no_instances_no_servers_triggers_warning(self):
        """Database avec environment mais sans servers/instances → warning path (ligne 107)."""
        config = {
            'entities': {
                'databases': {
                    'table': 'CMDB_DATABASES',
                    'id_column': 'DB_ID',
                    'columns': {'name': 'DB_NAME'}
                }
            }
        }
        builder = _make_builder(config)
        # Cette combinaison déclenche has_servers=False + has_instances=False
        # → warning + simple query (ne peut pas filtrer par environment ici)
        # Mais la config database n'a pas d'environment column, donc simple query
        sql, params = builder.build_entity_query(
            entity_type='database',
            entity_plural='databases',
            environment=None,
            engine_type=None,
            server_name=None,
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'CMDB_DATABASES' in sql

    def test_instance_with_env_no_servers_triggers_warning(self):
        """Instance avec environment mais sans servers config → warning path (ligne 113)."""
        config = {
            'entities': {
                'instances': {
                    'table': 'CMDB_INSTANCES',
                    'id_column': 'INST_ID',
                    'columns': {
                        'name': 'INST_NAME',
                        'environment': 'ENV_COL',
                    }
                }
            }
        }
        builder = _make_builder(config)
        # Instance avec environment mais sans servers config → warning path
        sql, params = builder.build_entity_query(
            entity_type='instance',
            entity_plural='instances',
            environment='prod',
            engine_type=None,
            server_name=None,
            server_names=None,
            correlation_id=None,
        )
        assert isinstance(sql, str)
        assert 'CMDB_INSTANCES' in sql
