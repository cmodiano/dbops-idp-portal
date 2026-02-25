"""
Tests de validation de la migration V085 — Reference Partitioning EXECUTION_STEPS (Story 40.3).

Ces tests sont des tests d'intégration nécessitant une connexion Oracle réelle.
Ils ne s'exécutent PAS en tests unitaires avec mock DB.

Marqués @pytest.mark.integration — exécutés uniquement en CI avec Oracle disponible.

Pour exécuter localement (Oracle Docker requis) :
    pytest executions/tests/test_migration_40_3.py -v -m integration \\
        --ds=idp_backend.test_settings
"""

import pytest
from django.conf import settings
from django.db import connection

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        "oracle" not in settings.DATABASES["default"]["ENGINE"],
        reason="Oracle-specific tests (USER_TABLES, USER_PART_TABLES, etc.) require Oracle DB",
    ),
]


class TestMigration40_3ReferencePartitioning:
    """
    Tests de validation de la migration V085 — Reference Partitioning sur EXECUTION_STEPS.

    AC#1 : EXECUTION_STEPS est partitionnée par Oracle Reference Partitioning via FK → EXECUTIONS
    AC#2 : Données préservées intégralement (COUNT avant = COUNT après)
    AC#3 : FK ENABLED vers EXECUTIONS
    AC#4 : Index et contraintes recréés conformément aux recommandations DBA
    AC#5 : Partition-wise join actif (EXPLAIN PLAN produit PARTITION REFERENCE)
    """

    def test_execution_steps_table_is_partitioned(self, db):
        """
        AC#1 — La table EXECUTION_STEPS doit être partitionnée après V085.
        Vérifie USER_TABLES.PARTITIONED = 'YES'.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT PARTITIONED FROM USER_TABLES WHERE TABLE_NAME = 'EXECUTION_STEPS'"
            )
            row = cursor.fetchone()

        assert row is not None, "Table EXECUTION_STEPS introuvable dans USER_TABLES"
        assert row[0] == 'YES', (
            f"EXECUTION_STEPS n'est pas partitionnée : PARTITIONED='{row[0]}'. "
            "V085 n'a peut-être pas été exécutée."
        )

    def test_execution_steps_partitioned_by_reference(self, db):
        """
        AC#1 — Vérifie que le partitionnement est de type REFERENCE (Oracle Reference Partitioning).
        Utilise USER_PART_TABLES pour confirmer le type.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT PARTITIONING_TYPE
                FROM USER_PART_TABLES
                WHERE TABLE_NAME = 'EXECUTION_STEPS'
            """)
            row = cursor.fetchone()

        assert row is not None, "Aucune entrée dans USER_PART_TABLES pour EXECUTION_STEPS"
        assert row[0] == 'REFERENCE', (
            f"Type de partitionnement inattendu : '{row[0]}'. Attendu : REFERENCE. "
            "V085 devait créer EXECUTION_STEPS avec PARTITION BY REFERENCE."
        )

    def test_execution_steps_row_count_preserved(self, db):
        """
        AC#2 — Les données doivent être intégralement préservées après migration.

        Stratégie de validation :
        EXEC_STEPS_MIGRATION_CHECK ne doit plus exister : sa suppression en Phase 10
        prouve que la validation Phase 9 (COUNT avant = COUNT après) a réussi.
        Si elle existe encore, la migration n'a pas terminé ou a détecté un écart.

        Note : La comparaison avant/après est réalisée par la migration elle-même (Phase 9).
        Ce test valide que cette vérification a bien eu lieu et a réussi.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME = 'EXEC_STEPS_MIGRATION_CHECK'"
            )
            check_table_exists = cursor.fetchone()[0]

        assert check_table_exists == 0, (
            "EXEC_STEPS_MIGRATION_CHECK existe encore sur la base. "
            "Cela indique que la migration V085 n'a pas atteint la Phase 10 (nettoyage) "
            "ou que la Phase 9 a détecté un écart de COUNT(*) et a levé une exception. "
            "Vérifier l'état de la migration et les logs Flyway."
        )
        # L'absence de EXEC_STEPS_MIGRATION_CHECK est la preuve que la Phase 9 (COUNT validation)
        # a réussi. Pas d'assertion tautologique count >= 0 — le test de présence ci-dessus suffit.

    def test_fk_to_executions_enabled(self, db):
        """
        AC#3 — La FK EXECUTION_STEPS.EXECUTION_ID → EXECUTIONS doit être ENABLED.
        La FK (FK_EXEC_STEPS_NEW_EXEC) est déclarée inline dans CREATE TABLE EXECUTION_STEPS_NEW
        et doit rester ENABLED après le renommage V085 Phase 4.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT CONSTRAINT_NAME, STATUS
                FROM USER_CONSTRAINTS
                WHERE TABLE_NAME = 'EXECUTION_STEPS'
                  AND CONSTRAINT_TYPE = 'R'
                  AND R_CONSTRAINT_NAME = (
                      SELECT CONSTRAINT_NAME FROM USER_CONSTRAINTS
                      WHERE TABLE_NAME = 'EXECUTIONS' AND CONSTRAINT_TYPE = 'P'
                  )
                AND ROWNUM = 1
            """)
            row = cursor.fetchone()

        assert row is not None, (
            "FK EXECUTION_STEPS.EXECUTION_ID → EXECUTIONS introuvable dans USER_CONSTRAINTS. "
            "V085 Phase 2 devait créer la contrainte FK_EXEC_STEPS_NEW_EXEC inline."
        )
        constraint_name, status = row
        assert status == 'ENABLED', (
            f"FK {constraint_name} n'est pas ENABLED (status='{status}'). "
            "La FK est requise pour le Reference Partitioning et doit rester ENABLED."
        )

    def test_uk_exec_steps_local_prefixed(self, db):
        """
        AC#4 — Le UK UK_EXEC_STEPS_EXEC_ORDER doit exister, être UNIQUE et LOCAL (PARTITIONED='YES').
        Recréé en V085 Phase 5 comme index local prefixed sur (EXECUTION_ID, STEP_ORDER).
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT INDEX_NAME, UNIQUENESS, PARTITIONED
                FROM USER_INDEXES
                WHERE TABLE_NAME = 'EXECUTION_STEPS'
                  AND INDEX_NAME = 'UK_EXEC_STEPS_EXEC_ORDER'
            """)
            row = cursor.fetchone()

        assert row is not None, (
            "Index UK_EXEC_STEPS_EXEC_ORDER introuvable sur EXECUTION_STEPS. "
            "V085 Phase 5 devait créer ce UK local prefixed sur (EXECUTION_ID, STEP_ORDER)."
        )
        idx_name, uniqueness, partitioned = row
        assert uniqueness == 'UNIQUE', (
            f"UK_EXEC_STEPS_EXEC_ORDER n'est pas UNIQUE (uniqueness='{uniqueness}'). "
            "La contrainte doit garantir l'unicité de (EXECUTION_ID, STEP_ORDER)."
        )
        assert partitioned == 'YES', (
            f"UK_EXEC_STEPS_EXEC_ORDER n'est pas LOCAL (PARTITIONED='{partitioned}'). "
            "L'index doit être local (prefixed par EXECUTION_ID) pour une table partitionnée."
        )

    def test_local_indexes_exist(self, db):
        """
        AC#4 — Les index locaux IDX_EXEC_STEPS_EXECUTION_ID et IDX_EXEC_STEPS_EXEC_STATUS
        doivent exister et être partitionnés (LOCAL).
        Recréés en V085 Phase 7.
        """
        expected_indexes = {
            'IDX_EXEC_STEPS_EXECUTION_ID',
            'IDX_EXEC_STEPS_EXEC_STATUS',
        }

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT INDEX_NAME, PARTITIONED
                FROM USER_INDEXES
                WHERE TABLE_NAME = 'EXECUTION_STEPS'
                  AND INDEX_NAME IN ('IDX_EXEC_STEPS_EXECUTION_ID', 'IDX_EXEC_STEPS_EXEC_STATUS')
                ORDER BY INDEX_NAME
            """)
            rows = cursor.fetchall()

        found = {r[0]: r[1] for r in rows}
        missing = expected_indexes - set(found.keys())
        assert not missing, (
            f"Index locaux manquants après V085 : {missing}. "
            f"Index trouvés : {list(found.keys())}"
        )
        for index_name, partitioned in found.items():
            assert partitioned == 'YES', (
                f"Index {index_name} n'est pas LOCAL (PARTITIONED='{partitioned}'). "
                "V085 Phase 7 devait créer ces index avec le mot-clé LOCAL."
            )

    def test_old_status_only_index_removed(self, db):
        """
        AC#4 — L'ancien index IDX_EXEC_STEPS_STATUS (sur STATUS seul) doit avoir été supprimé.
        Il était sur EXECUTION_STEPS_OLD et a été détruit avec DROP TABLE EXECUTION_STEPS_OLD PURGE.
        Remplacé par IDX_EXEC_STEPS_EXEC_STATUS (EXECUTION_ID, STATUS) — prefixed.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT INDEX_NAME
                FROM USER_INDEXES
                WHERE TABLE_NAME = 'EXECUTION_STEPS'
                  AND INDEX_NAME = 'IDX_EXEC_STEPS_STATUS'
            """)
            rows = cursor.fetchall()

        assert not rows, (
            "L'ancien index IDX_EXEC_STEPS_STATUS (STATUS seul) est encore présent. "
            "Il aurait dû être supprimé avec EXECUTION_STEPS_OLD en Phase 10 de V085."
        )

    def test_pk_is_global_index(self, db):
        """
        AC#4 — La PK (PK_EXECUTION_STEPS) doit être un index GLOBAL (non partitionné).
        La PK sur ID (non partition-key) doit être backing par un index global
        pour garantir l'unicité inter-partitions.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT i.INDEX_NAME, i.PARTITIONED
                FROM USER_INDEXES i
                JOIN USER_CONSTRAINTS c ON c.INDEX_NAME = i.INDEX_NAME
                WHERE c.TABLE_NAME = 'EXECUTION_STEPS'
                  AND c.CONSTRAINT_TYPE = 'P'
            """)
            row = cursor.fetchone()

        assert row is not None, (
            "Index backing la PK de EXECUTION_STEPS introuvable. "
            "V085 Phase 4 devait renommer PK_EXECUTION_STEPS_NEW → PK_EXECUTION_STEPS."
        )
        index_name, partitioned = row
        assert partitioned == 'NO', (
            f"L'index PK {index_name} est partitionné ('{partitioned}') au lieu d'être GLOBAL. "
            "La PK sur ID doit être un index global pour garantir l'unicité inter-partitions."
        )

    def test_check_status_constraint_includes_waiting(self, db):
        """
        AC#4 — La contrainte CHK_STEP_STATUS doit inclure WAITING (ajouté en V067).
        Vérifier que la contrainte recréée en V085 Phase 6 est correcte.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT SEARCH_CONDITION
                FROM USER_CONSTRAINTS
                WHERE TABLE_NAME = 'EXECUTION_STEPS'
                  AND CONSTRAINT_NAME = 'CHK_STEP_STATUS'
            """)
            row = cursor.fetchone()

        assert row is not None, (
            "Contrainte CHK_STEP_STATUS introuvable sur EXECUTION_STEPS. "
            "V085 Phase 6 devait recréer cette contrainte."
        )
        condition = row[0].upper() if row[0] else ""
        assert 'WAITING' in condition, (
            f"CHK_STEP_STATUS ne contient pas WAITING. "
            f"Condition actuelle : {row[0]}. "
            "La contrainte doit inclure WAITING (V067)."
        )

    def test_check_step_type_constraint_exists(self, db):
        """
        AC#4 — La contrainte CHK_STEP_TYPE doit exister sur EXECUTION_STEPS avec les valeurs
        issues de V025 : vault, servicenow, platform, prerequisite, verification.
        Recréée en V085 Phase 6.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT SEARCH_CONDITION
                FROM USER_CONSTRAINTS
                WHERE TABLE_NAME = 'EXECUTION_STEPS'
                  AND CONSTRAINT_NAME = 'CHK_STEP_TYPE'
            """)
            row = cursor.fetchone()

        assert row is not None, (
            "Contrainte CHK_STEP_TYPE introuvable sur EXECUTION_STEPS. "
            "V085 Phase 6 devait recréer cette contrainte (STEP_TYPE IN ...)."
        )
        condition = row[0].upper() if row[0] else ""
        expected_values = ['VAULT', 'SERVICENOW', 'PLATFORM', 'PREREQUISITE', 'VERIFICATION']
        missing_values = [v for v in expected_values if v not in condition]
        assert not missing_values, (
            f"CHK_STEP_TYPE ne contient pas toutes les valeurs attendues (V025). "
            f"Valeurs manquantes : {missing_values}. "
            f"Condition actuelle : {row[0]}"
        )

    def test_partition_wise_join_executions_steps(self, db):
        """
        AC#5 — Une jointure EXECUTIONS ↔ EXECUTION_STEPS doit utiliser le partition-wise join.
        Vérifie via EXPLAIN PLAN que le plan contient une opération PARTITION REFERENCE.

        Avec Reference Partitioning, Oracle peut utiliser :
        - PARTITION REFERENCE ALL (scan de toutes les partitions de référence)
        - PARTITION REFERENCE ITERATOR (scan de partitions spécifiques)

        Note : Ce test nécessite les droits EXPLAIN PLAN et PLAN_TABLE.
        Il peut être ignoré si les droits ne sont pas disponibles en CI.
        """
        partition_rows: list[tuple[str, str | None]] = []
        try:
            with connection.cursor() as cursor:
                # Purger d'éventuels résidus AVANT de générer un nouveau plan
                # (Oracle ne remplace pas les entrées existantes pour un même STATEMENT_ID)
                cursor.execute("DELETE FROM PLAN_TABLE WHERE STATEMENT_ID = 'TEST_40_3_JOIN'")

                # Générer le plan d'exécution pour une jointure EXECUTIONS ↔ EXECUTION_STEPS
                # avec filtre sur CREATED_AT (partition pruning sur EXECUTIONS → cascade REFERENCE)
                cursor.execute("""
                    EXPLAIN PLAN SET STATEMENT_ID = 'TEST_40_3_JOIN' FOR
                    SELECT s.ID, s.STEP_NAME, s.STATUS
                    FROM EXECUTIONS e
                    JOIN EXECUTION_STEPS s ON s.EXECUTION_ID = e.ID
                    WHERE e.CREATED_AT BETWEEN SYSTIMESTAMP - INTERVAL '30' DAY AND SYSTIMESTAMP
                """)

                # Récupérer les opérations de partition du plan
                cursor.execute("""
                    SELECT OPERATION, OPTIONS
                    FROM PLAN_TABLE
                    WHERE STATEMENT_ID = 'TEST_40_3_JOIN'
                      AND (OPTIONS LIKE '%REFERENCE%' OR OPERATION LIKE '%PARTITION%')
                    ORDER BY ID
                """)
                partition_rows = cursor.fetchall()

                # Nettoyer après lecture
                cursor.execute("DELETE FROM PLAN_TABLE WHERE STATEMENT_ID = 'TEST_40_3_JOIN'")
        except Exception as db_exc:
            if 'ORA-00942' in str(db_exc):
                partition_rows = []
            else:
                raise

        if not partition_rows:
            # Vérifier si PLAN_TABLE est accessible (fallback quand plan vide ou ORA-00942)
            plan_accessible = False
            try:
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM PLAN_TABLE WHERE STATEMENT_ID = 'TEST_40_3_JOIN_CHECK'")
                    cursor.execute(
                        "EXPLAIN PLAN SET STATEMENT_ID = 'TEST_40_3_JOIN_CHECK' FOR SELECT 1 FROM DUAL"
                    )
                    cursor.execute(
                        "SELECT COUNT(*) FROM PLAN_TABLE WHERE STATEMENT_ID = 'TEST_40_3_JOIN_CHECK'"
                    )
                    plan_accessible = cursor.fetchone()[0] > 0
                    cursor.execute("DELETE FROM PLAN_TABLE WHERE STATEMENT_ID = 'TEST_40_3_JOIN_CHECK'")
            except Exception as check_exc:
                if 'ORA-00942' in str(check_exc):
                    plan_accessible = False
                else:
                    raise

            if not plan_accessible:
                pytest.skip("PLAN_TABLE non accessible ou EXPLAIN PLAN non supporté dans cet environnement")
            else:
                pytest.fail(
                    "Aucune opération PARTITION REFERENCE dans le plan d'exécution. "
                    "Le partition-wise join n'est pas actif pour la jointure EXECUTIONS ↔ EXECUTION_STEPS. "
                    "Vérifier que EXECUTION_STEPS est bien partitionnée par REFERENCE."
                )

        # Vérifier la présence de PARTITION REFERENCE dans le plan
        reference_found = any(
            'REFERENCE' in (row[1] or '')
            for row in partition_rows
        )
        assert reference_found, (
            f"Opérations de partition trouvées : {partition_rows}. "
            "Aucune ne contient REFERENCE — le partition-wise join via Reference Partitioning n'est pas actif."
        )
