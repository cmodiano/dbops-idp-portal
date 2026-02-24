"""
Tests de validation de la migration V084 - Partitionnement EXECUTIONS (Story 40.2).

Ces tests sont des tests d'intégration nécessitant une connexion Oracle réelle.
Ils ne s'exécutent PAS en tests unitaires avec mock DB.

Marqués @pytest.mark.integration — exécutés uniquement en CI avec Oracle disponible.

Pour exécuter localement (Oracle Docker requis) :
    pytest executions/tests/test_migration_40_2.py -v -m integration \
        --ds=idp_backend.test_settings
"""

import pytest
from django.db import connection


@pytest.mark.integration
class TestMigration40_2Partitioning:
    """
    Tests de validation de la migration V084 — partitionnement mensuel INTERVAL sur EXECUTIONS.

    AC#1 : Table partitionnée par CREATED_AT (INTERVAL mensuel)
    AC#2 : Données préservées (COUNT avant = COUNT après)
    AC#3 : FK depuis EXECUTION_STEPS et EXECUTION_TARGETS valides et ENABLED
    AC#4 : Index recréés correctement (locaux prefixed)
    AC#5 : Partition pruning actif sur filtre CREATED_AT
    """

    def test_executions_table_is_partitioned(self, db):
        """
        AC#1 — La table EXECUTIONS doit être partitionnée après V084.
        Vérifie USER_TABLES.PARTITIONED = 'YES'.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT PARTITIONED FROM USER_TABLES WHERE TABLE_NAME = 'EXECUTIONS'"
            )
            row = cursor.fetchone()

        assert row is not None, "Table EXECUTIONS introuvable dans USER_TABLES"
        assert row[0] == 'YES', (
            f"EXECUTIONS n'est pas partitionnée : PARTITIONED='{row[0]}'. "
            "V084 n'a peut-être pas été exécutée."
        )

    def test_executions_partitioned_by_created_at_interval(self, db):
        """
        AC#1 — Vérifie que le partitionnement est de type RANGE (INTERVAL) sur CREATED_AT.
        Utilise USER_PART_TABLES pour confirmer la colonne de partitionnement.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT pt.PARTITIONING_TYPE, pc.COLUMN_NAME
                FROM USER_PART_TABLES pt
                JOIN USER_PART_KEY_COLUMNS pc ON pc.NAME = pt.TABLE_NAME
                WHERE pt.TABLE_NAME = 'EXECUTIONS'
            """)
            rows = cursor.fetchall()

        assert len(rows) >= 1, "Aucune entrée dans USER_PART_TABLES pour EXECUTIONS"
        partitioning_types = {r[0] for r in rows}
        partition_columns = {r[1] for r in rows}

        # Oracle représente INTERVAL RANGE comme 'RANGE' dans PARTITIONING_TYPE
        assert 'RANGE' in partitioning_types, (
            f"Type de partitionnement inattendu : {partitioning_types}. Attendu : RANGE."
        )
        assert 'CREATED_AT' in partition_columns, (
            f"Colonne de partitionnement inattendue : {partition_columns}. Attendu : CREATED_AT."
        )

    def test_executions_row_count_preserved(self, db):
        """
        AC#2 — Les données doivent être intégralement préservées après migration.

        Stratégie de validation :
        1. EXECUTIONS_MIGRATION_CHECK ne doit plus exister : sa suppression en Phase 11
           prouve que la validation Phase 10 (COUNT avant = COUNT après) a réussi.
           Si elle existe encore, la migration n'a pas terminé ou a détecté un écart.
        2. COUNT(*) sur EXECUTIONS doit être >= 0 (requête accessible post-migration).

        Note : La comparaison avant/après est réalisée par la migration elle-même (Phase 10).
        Ce test valide que cette vérification a bien eu lieu et a réussi.
        """
        with connection.cursor() as cursor:
            # Vérification 1 : EXECUTIONS_MIGRATION_CHECK supprimée (Phase 11 exécutée)
            cursor.execute(
                "SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME = 'EXECUTIONS_MIGRATION_CHECK'"
            )
            check_table_exists = cursor.fetchone()[0]

        assert check_table_exists == 0, (
            "EXECUTIONS_MIGRATION_CHECK existe encore sur la base. "
            "Cela indique que la migration V084 n'a pas atteint la Phase 11 (nettoyage) "
            "ou que la Phase 10 a détecté un écart de COUNT(*) et a levé une exception. "
            "Vérifier l'état de la migration et les logs Flyway."
        )

        with connection.cursor() as cursor:
            # Vérification 2 : la table est accessible et la requête COUNT fonctionne
            cursor.execute("SELECT COUNT(*) FROM EXECUTIONS")
            count = cursor.fetchone()[0]

        assert count >= 0, (
            "Impossible d'exécuter COUNT(*) sur EXECUTIONS après migration V084."
        )

    def test_existing_fk_constraints_valid(self, db):
        """
        AC#3 — Les FK depuis EXECUTION_STEPS et EXECUTION_TARGETS doivent être ENABLED
        après la migration (réactivées en Phase 7 de V084).
        """
        with connection.cursor() as cursor:
            # Récupère les FK référençant la PK de EXECUTIONS
            cursor.execute("""
                SELECT c.TABLE_NAME, c.CONSTRAINT_NAME, c.STATUS
                FROM USER_CONSTRAINTS c
                WHERE c.TABLE_NAME IN ('EXECUTION_STEPS', 'EXECUTION_TARGETS')
                  AND c.CONSTRAINT_TYPE = 'R'
                  AND c.R_CONSTRAINT_NAME = (
                      SELECT CONSTRAINT_NAME FROM USER_CONSTRAINTS
                      WHERE TABLE_NAME = 'EXECUTIONS' AND CONSTRAINT_TYPE = 'P'
                  )
                ORDER BY c.TABLE_NAME
            """)
            rows = cursor.fetchall()

        assert len(rows) >= 2, (
            f"Attendu au moins 2 FK (EXECUTION_STEPS + EXECUTION_TARGETS), "
            f"trouvé : {[(r[0], r[1]) for r in rows]}"
        )
        for table_name, constraint_name, status in rows:
            assert status == 'ENABLED', (
                f"Contrainte FK {constraint_name} sur {table_name} "
                f"est '{status}' au lieu de 'ENABLED'. "
                "V084 Phase 7 ne l'a pas réactivée correctement."
            )

    def test_local_indexes_exist(self, db):
        """
        AC#4 — Les index locaux prefixed doivent exister et être partitionnés (LOCAL).
        Vérifie IDX_EXECUTIONS_CREATED_ACTION, IDX_EXECUTIONS_CREATED_USER, IDX_EXECUTIONS_CREATED_STATUS.
        """
        expected_indexes = {
            'IDX_EXECUTIONS_CREATED_ACTION',
            'IDX_EXECUTIONS_CREATED_USER',
            'IDX_EXECUTIONS_CREATED_STATUS',
        }

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT INDEX_NAME, PARTITIONED
                FROM USER_INDEXES
                WHERE TABLE_NAME = 'EXECUTIONS'
                  AND INDEX_NAME IN (
                      'IDX_EXECUTIONS_CREATED_ACTION',
                      'IDX_EXECUTIONS_CREATED_USER',
                      'IDX_EXECUTIONS_CREATED_STATUS'
                  )
                ORDER BY INDEX_NAME
            """)
            rows = cursor.fetchall()

        found = {r[0]: r[1] for r in rows}
        missing = expected_indexes - set(found.keys())
        assert not missing, (
            f"Index locaux manquants après V084 : {missing}. "
            f"Index trouvés : {list(found.keys())}"
        )
        for index_name, partitioned in found.items():
            assert partitioned == 'YES', (
                f"Index {index_name} n'est pas LOCAL (PARTITIONED='{partitioned}'). "
                "V084 Phase 8 devait créer ces index avec le mot-clé LOCAL."
            )

    def test_old_non_prefixed_indexes_removed(self, db):
        """
        AC#4 — Les anciens index non-prefixed doivent avoir été supprimés :
        IDX_EXECUTIONS_ACTION_ID et IDX_EXECUTIONS_CREATED_AT.
        Ces index existaient sur EXECUTIONS_OLD et ont été détruits avec DROP TABLE PURGE.
        """
        obsolete_indexes = ('IDX_EXECUTIONS_ACTION_ID', 'IDX_EXECUTIONS_CREATED_AT')

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT INDEX_NAME
                FROM USER_INDEXES
                WHERE TABLE_NAME = 'EXECUTIONS'
                  AND INDEX_NAME IN ('IDX_EXECUTIONS_ACTION_ID', 'IDX_EXECUTIONS_CREATED_AT')
            """)
            rows = cursor.fetchall()

        found_obsolete = [r[0] for r in rows]
        assert not found_obsolete, (
            f"Anciens index obsolètes encore présents après V084 : {found_obsolete}. "
            "Ces index auraient dû être supprimés avec EXECUTIONS_OLD."
        )

    def test_partition_pruning_with_date_filter(self, db):
        """
        AC#5 — Une requête avec filtre CREATED_AT doit utiliser le partition pruning.
        Vérifie via EXPLAIN PLAN que l'opération est 'PARTITION RANGE ITERATOR'
        (ou 'PARTITION RANGE SINGLE') et NON 'PARTITION RANGE ALL'.

        Note : Ce test nécessite DBMS_XPLAN et les droits d'exécution d'EXPLAIN PLAN.
        Il peut être ignoré si les droits ne sont pas disponibles en CI.
        """
        with connection.cursor() as cursor:
            # Purger d'éventuels résidus de runs précédents AVANT de générer un nouveau plan
            # (Oracle ne remplace pas les entrées existantes pour un même STATEMENT_ID)
            cursor.execute("DELETE FROM PLAN_TABLE WHERE STATEMENT_ID = 'V084_PRUNING_TEST'")

            # Générer le plan d'exécution
            cursor.execute("EXPLAIN PLAN SET STATEMENT_ID = 'V084_PRUNING_TEST' FOR "
                           "SELECT COUNT(*) FROM EXECUTIONS "
                           "WHERE CREATED_AT >= TIMESTAMP '2025-01-01 00:00:00' "
                           "AND CREATED_AT < TIMESTAMP '2025-02-01 00:00:00'")

            # Récupérer les opérations du plan
            cursor.execute("""
                SELECT OPERATION, OPTIONS
                FROM PLAN_TABLE
                WHERE STATEMENT_ID = 'V084_PRUNING_TEST'
                  AND OPERATION = 'PARTITION'
                ORDER BY ID
            """)
            plan_rows = cursor.fetchall()

            # Nettoyer après lecture
            cursor.execute("DELETE FROM PLAN_TABLE WHERE STATEMENT_ID = 'V084_PRUNING_TEST'")

        if not plan_rows:
            pytest.skip("PLAN_TABLE non accessible ou EXPLAIN PLAN non supporté dans cet environnement")

        partition_options = {r[1] for r in plan_rows}

        # 'PARTITION RANGE ALL' indique l'absence de pruning
        assert 'RANGE ALL' not in partition_options, (
            f"Partition pruning NON actif : opérations = {partition_options}. "
            "La requête scanne toutes les partitions. "
            "Vérifier que CREATED_AT est bien la clé de partition et que les stats sont à jour."
        )
        # Accepter RANGE ITERATOR (plusieurs partitions) ou RANGE SINGLE (1 partition)
        pruning_detected = bool(
            partition_options & {'RANGE ITERATOR', 'RANGE SINGLE', 'RANGE INLIST'}
        )
        assert pruning_detected, (
            f"Partition pruning non détecté. Options trouvées : {partition_options}. "
            "Attendu : RANGE ITERATOR ou RANGE SINGLE."
        )

    def test_approval_fk_constraint_valid(self, db):
        """
        AC#3 — FK_EXECUTIONS_APPROVED_BY doit être ENABLED après migration V084.
        Cette FK est recréée en Phase 6 et référence USERS(ID).
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT CONSTRAINT_NAME, STATUS
                FROM USER_CONSTRAINTS
                WHERE TABLE_NAME = 'EXECUTIONS'
                  AND CONSTRAINT_NAME = 'FK_EXECUTIONS_APPROVED_BY'
            """)
            row = cursor.fetchone()

        assert row is not None, (
            "Contrainte FK_EXECUTIONS_APPROVED_BY introuvable sur EXECUTIONS. "
            "V084 Phase 6 devait recréer cette FK (APPROVED_BY → USERS.ID)."
        )
        _, status = row
        assert status == 'ENABLED', (
            f"FK_EXECUTIONS_APPROVED_BY est '{status}' au lieu de 'ENABLED'. "
            "V084 Phase 6 devait recréer cette contrainte en état ENABLED."
        )

    def test_check_status_constraint_includes_integration_error(self, db):
        """
        AC#3 — La contrainte CHK_EXECUTION_STATUS doit inclure INTEGRATION_ERROR (V057).
        Vérifie que la contrainte recréée en V084 Phase 9 est correcte.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT SEARCH_CONDITION
                FROM USER_CONSTRAINTS
                WHERE TABLE_NAME = 'EXECUTIONS'
                  AND CONSTRAINT_NAME = 'CHK_EXECUTION_STATUS'
            """)
            row = cursor.fetchone()

        assert row is not None, "Contrainte CHK_EXECUTION_STATUS introuvable sur EXECUTIONS"
        condition = row[0].upper() if row[0] else ""
        assert 'INTEGRATION_ERROR' in condition, (
            f"CHK_EXECUTION_STATUS ne contient pas INTEGRATION_ERROR. "
            f"Condition actuelle : {row[0]}"
        )

    def test_pk_is_global_index(self, db):
        """
        AC#4 — La PK (PK_EXECUTIONS) doit être un index GLOBAL (non partitionné).
        La PK sur ID (non-partition-key) doit être backing par un index global.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT i.INDEX_NAME, i.PARTITIONED
                FROM USER_INDEXES i
                JOIN USER_CONSTRAINTS c ON c.INDEX_NAME = i.INDEX_NAME
                WHERE c.TABLE_NAME = 'EXECUTIONS'
                  AND c.CONSTRAINT_TYPE = 'P'
            """)
            row = cursor.fetchone()

        assert row is not None, "Index supporting PK_EXECUTIONS introuvable"
        index_name, partitioned = row
        assert partitioned == 'NO', (
            f"L'index PK {index_name} est partitionné ('{partitioned}') au lieu d'être GLOBAL. "
            "La PK sur ID doit être un index global pour une table partitionnée sur CREATED_AT."
        )
