"""
Tests de validation de la migration V086 — Range INTERVAL Partitioning AUDIT_LOG (Story 40.4).

Ces tests sont des tests d'intégration nécessitant une connexion Oracle réelle.
Ils ne s'exécutent PAS en tests unitaires avec mock DB.

Marqués @pytest.mark.integration — exécutés uniquement en CI avec Oracle disponible.

Pour exécuter localement (Oracle Docker requis) :
    pytest core/tests/test_migration_40_4.py -v -m integration \\
        --ds=idp_backend.test_settings
"""

import pytest
from django.db import connection


@pytest.mark.integration
class TestMigration40_4RangeIntervalPartitioning:
    """
    Tests de validation de la migration V086 — Range INTERVAL Partitioning sur AUDIT_LOG.

    AC#1 : AUDIT_LOG est partitionnée par TIMESTAMP (Range INTERVAL mensuel)
    AC#2 : Données préservées intégralement (COUNT avant = COUNT après)
    AC#3 : Partition pruning actif sur les requêtes filtrées par TIMESTAMP
    AC#4 : Index et contraintes recréés conformément aux recommandations DBA
    AC#5 : Trigger TRG_AUDIT_LOG_IMMUTABLE recréé (SOC1/NFR8 compliance)
    """

    def test_audit_log_table_is_partitioned(self, db):
        """
        AC#1 — La table AUDIT_LOG doit être partitionnée après V086.
        Vérifie USER_TABLES.PARTITIONED = 'YES'.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT PARTITIONED FROM USER_TABLES WHERE TABLE_NAME = 'AUDIT_LOG'"
            )
            row = cursor.fetchone()

        assert row is not None, "Table AUDIT_LOG introuvable dans USER_TABLES"
        assert row[0] == 'YES', (
            f"AUDIT_LOG n'est pas partitionnée : PARTITIONED='{row[0]}'. "
            "V086 n'a peut-être pas été exécutée."
        )

    def test_audit_log_partitioned_by_range(self, db):
        """
        AC#1 — Vérifie que le partitionnement est de type RANGE avec INTERVAL.
        Utilise USER_PART_TABLES pour confirmer PARTITIONING_TYPE = 'RANGE' et INTERVAL != NULL.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT PARTITIONING_TYPE, INTERVAL
                FROM USER_PART_TABLES
                WHERE TABLE_NAME = 'AUDIT_LOG'
            """)
            row = cursor.fetchone()

        assert row is not None, "Aucune entrée dans USER_PART_TABLES pour AUDIT_LOG"
        partitioning_type, interval = row
        assert partitioning_type == 'RANGE', (
            f"Type de partitionnement inattendu : '{partitioning_type}'. Attendu : RANGE. "
            "V086 devait créer AUDIT_LOG avec PARTITION BY RANGE (TIMESTAMP) INTERVAL."
        )
        assert interval is not None, (
            "L'expression INTERVAL est NULL dans USER_PART_TABLES. "
            "AUDIT_LOG doit utiliser INTERVAL (NUMTOYMINTERVAL(1, 'MONTH'))."
        )

    def test_audit_log_row_count_preserved(self, db):
        """
        AC#2 — Les données doivent être intégralement préservées après migration.

        Stratégie de validation :
        AUDIT_LOG_MIGRATION_CHECK ne doit plus exister : sa suppression en Phase 11
        prouve que la validation Phase 10 (COUNT avant = COUNT après) a réussi.
        Si elle existe encore, la migration n'a pas terminé ou a détecté un écart.

        Note : La comparaison avant/après est réalisée par la migration elle-même (Phase 10).
        Ce test valide que cette vérification a bien eu lieu et a réussi.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME = 'AUDIT_LOG_MIGRATION_CHECK'"
            )
            check_table_exists = cursor.fetchone()[0]

        assert check_table_exists == 0, (
            "AUDIT_LOG_MIGRATION_CHECK existe encore sur la base. "
            "Cela indique que la migration V086 n'a pas atteint la Phase 11 (nettoyage) "
            "ou que la Phase 10 a détecté un écart de COUNT(*) et a levé une exception. "
            "Vérifier l'état de la migration et les logs Flyway."
        )
        # L'absence de AUDIT_LOG_MIGRATION_CHECK est la preuve que la Phase 10 (COUNT validation)
        # a réussi. Pas d'assertion tautologique count >= 0 — la vérification ci-dessus suffit.

    def test_local_index_timestamp_exists(self, db):
        """
        AC#4 — L'index IDX_AUDIT_LOG_TIMESTAMP doit exister et être LOCAL (PARTITIONED='YES').
        Recréé en V086 Phase 6 comme index local sur (TIMESTAMP) — la clé de partition.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT INDEX_NAME, PARTITIONED
                FROM USER_INDEXES
                WHERE TABLE_NAME = 'AUDIT_LOG'
                  AND INDEX_NAME = 'IDX_AUDIT_LOG_TIMESTAMP'
            """)
            row = cursor.fetchone()

        assert row is not None, (
            "Index IDX_AUDIT_LOG_TIMESTAMP introuvable sur AUDIT_LOG. "
            "V086 Phase 6 devait créer cet index local sur TIMESTAMP."
        )
        index_name, partitioned = row
        assert partitioned == 'YES', (
            f"IDX_AUDIT_LOG_TIMESTAMP n'est pas LOCAL (PARTITIONED='{partitioned}'). "
            "L'index doit être local car TIMESTAMP est la clé de partition."
        )

    def test_local_index_created_entity_exists(self, db):
        """
        AC#4 — L'index IDX_AUDITLOG_CREATED_ENTITY doit exister et être LOCAL.
        Recréé en V086 Phase 6 sur (TIMESTAMP, ENTITY_TYPE, ENTITY_ID).
        Remplace IDX_AUDIT_LOG_ENTITY et IDX_AUDIT_LOG_ENTITY_TYPE_TIMESTAMP (V029).
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT INDEX_NAME, PARTITIONED
                FROM USER_INDEXES
                WHERE TABLE_NAME = 'AUDIT_LOG'
                  AND INDEX_NAME = 'IDX_AUDITLOG_CREATED_ENTITY'
            """)
            row = cursor.fetchone()

        assert row is not None, (
            "Index IDX_AUDITLOG_CREATED_ENTITY introuvable sur AUDIT_LOG. "
            "V086 Phase 6 devait créer cet index local prefixed sur (TIMESTAMP, ENTITY_TYPE, ENTITY_ID)."
        )
        index_name, partitioned = row
        assert partitioned == 'YES', (
            f"IDX_AUDITLOG_CREATED_ENTITY n'est pas LOCAL (PARTITIONED='{partitioned}'). "
            "L'index doit être local (prefixed par TIMESTAMP) pour bénéficier du partition pruning."
        )

    def test_local_index_created_user_exists(self, db):
        """
        AC#4 — L'index IDX_AUDITLOG_CREATED_USER doit exister et être LOCAL.
        Recréé en V086 Phase 6 sur (TIMESTAMP, USER_ID).
        Remplace IDX_AUDIT_LOG_USER.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT INDEX_NAME, PARTITIONED
                FROM USER_INDEXES
                WHERE TABLE_NAME = 'AUDIT_LOG'
                  AND INDEX_NAME = 'IDX_AUDITLOG_CREATED_USER'
            """)
            row = cursor.fetchone()

        assert row is not None, (
            "Index IDX_AUDITLOG_CREATED_USER introuvable sur AUDIT_LOG. "
            "V086 Phase 6 devait créer cet index local prefixed sur (TIMESTAMP, USER_ID)."
        )
        index_name, partitioned = row
        assert partitioned == 'YES', (
            f"IDX_AUDITLOG_CREATED_USER n'est pas LOCAL (PARTITIONED='{partitioned}'). "
            "L'index doit être local (prefixed par TIMESTAMP) pour bénéficier du partition pruning."
        )

    def test_global_index_correlation_exists(self, db):
        """
        AC#4 — L'index IDX_AUDIT_LOG_CORRELATION doit exister et être GLOBAL (PARTITIONED='NO').
        Recréé en V086 Phase 7 sur CORRELATION_ID — GLOBAL car les requêtes de corrélation
        n'ont pas de filtre TIMESTAMP.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT INDEX_NAME, PARTITIONED
                FROM USER_INDEXES
                WHERE TABLE_NAME = 'AUDIT_LOG'
                  AND INDEX_NAME = 'IDX_AUDIT_LOG_CORRELATION'
            """)
            row = cursor.fetchone()

        assert row is not None, (
            "Index IDX_AUDIT_LOG_CORRELATION introuvable sur AUDIT_LOG. "
            "V086 Phase 7 devait créer cet index global sur CORRELATION_ID."
        )
        index_name, partitioned = row
        assert partitioned == 'NO', (
            f"IDX_AUDIT_LOG_CORRELATION est LOCAL (PARTITIONED='{partitioned}') au lieu d'être GLOBAL. "
            "Cet index doit être GLOBAL pour supporter les requêtes sans filtre TIMESTAMP."
        )

    def test_pk_is_global_index(self, db):
        """
        AC#4 — La PK (PK_AUDIT_LOG) doit être un index GLOBAL (non partitionné).
        La PK sur ID (non partition-key) doit être backed par un index global
        pour garantir l'unicité inter-partitions.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT i.INDEX_NAME, i.PARTITIONED
                FROM USER_INDEXES i
                JOIN USER_CONSTRAINTS c ON c.INDEX_NAME = i.INDEX_NAME
                WHERE c.TABLE_NAME = 'AUDIT_LOG'
                  AND c.CONSTRAINT_TYPE = 'P'
            """)
            row = cursor.fetchone()

        assert row is not None, (
            "Index backing la PK de AUDIT_LOG introuvable. "
            "V086 Phase 4 devait renommer PK_AUDIT_LOG_NEW → PK_AUDIT_LOG."
        )
        index_name, partitioned = row
        assert partitioned == 'NO', (
            f"L'index PK {index_name} est partitionné ('{partitioned}') au lieu d'être GLOBAL. "
            "La PK sur ID doit être un index global pour garantir l'unicité inter-partitions."
        )

    def test_immutability_trigger_exists(self, db):
        """
        AC#5 — Le trigger TRG_AUDIT_LOG_IMMUTABLE doit exister sur la nouvelle table AUDIT_LOG.
        Recréé en V086 Phase 9 — CRITIQUE pour la compliance SOC1/NFR8.
        Sans ce trigger, AUDIT_LOG perd sa protection UPDATE/DELETE.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT TRIGGER_NAME, STATUS, TRIGGER_TYPE, TRIGGERING_EVENT
                FROM USER_TRIGGERS
                WHERE TABLE_NAME = 'AUDIT_LOG'
                  AND TRIGGER_NAME = 'TRG_AUDIT_LOG_IMMUTABLE'
            """)
            row = cursor.fetchone()

        assert row is not None, (
            "Trigger TRG_AUDIT_LOG_IMMUTABLE introuvable sur AUDIT_LOG. "
            "V086 Phase 9 devait recréer ce trigger sur la nouvelle table. "
            "ATTENTION : Sans ce trigger, AUDIT_LOG n'est plus immutable (violation SOC1/NFR8)."
        )
        trigger_name, status, trigger_type, triggering_event = row
        assert status == 'ENABLED', (
            f"TRG_AUDIT_LOG_IMMUTABLE est {status} au lieu d'être ENABLED. "
            "Le trigger d'immutabilité doit être actif pour garantir la compliance SOC1/NFR8."
        )

    def test_local_index_created_action_exists(self, db):
        """
        AC#4 — L'index IDX_AUDIT_LOG_CREATED_ACTION doit exister et être LOCAL.
        Recréé en V086 Phase 6 sur (TIMESTAMP, ACTION_TYPE).
        Remplace IDX_AUDIT_LOG_ACTION_TYPE.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT INDEX_NAME, PARTITIONED
                FROM USER_INDEXES
                WHERE TABLE_NAME = 'AUDIT_LOG'
                  AND INDEX_NAME = 'IDX_AUDIT_LOG_CREATED_ACTION'
            """)
            row = cursor.fetchone()

        assert row is not None, (
            "Index IDX_AUDIT_LOG_CREATED_ACTION introuvable sur AUDIT_LOG. "
            "V086 Phase 6 devait créer cet index local prefixed sur (TIMESTAMP, ACTION_TYPE)."
        )
        index_name, partitioned = row
        assert partitioned == 'YES', (
            f"IDX_AUDIT_LOG_CREATED_ACTION n'est pas LOCAL (PARTITIONED='{partitioned}'). "
            "L'index doit être local (prefixed par TIMESTAMP) pour bénéficier du partition pruning."
        )

    def test_check_constraints_recreated(self, db):
        """
        AC#4 — Les CHECK constraints CK_AUDIT_LOG_ACTION_TYPE et CK_AUDIT_LOG_ENTITY_TYPE
        doivent exister sur la nouvelle table AUDIT_LOG après migration V086.
        Recréées en Phase 5 (state V068/V045).
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT CONSTRAINT_NAME
                FROM USER_CONSTRAINTS
                WHERE TABLE_NAME = 'AUDIT_LOG'
                  AND CONSTRAINT_TYPE = 'C'
                  AND CONSTRAINT_NAME IN (
                      'CK_AUDIT_LOG_ACTION_TYPE',
                      'CK_AUDIT_LOG_ENTITY_TYPE'
                  )
                ORDER BY CONSTRAINT_NAME
            """)
            rows = cursor.fetchall()

        found_names = {row[0] for row in rows}
        assert 'CK_AUDIT_LOG_ACTION_TYPE' in found_names, (
            "CHECK constraint CK_AUDIT_LOG_ACTION_TYPE introuvable sur AUDIT_LOG. "
            "V086 Phase 5 devait la recréer (valeurs V068)."
        )
        assert 'CK_AUDIT_LOG_ENTITY_TYPE' in found_names, (
            "CHECK constraint CK_AUDIT_LOG_ENTITY_TYPE introuvable sur AUDIT_LOG. "
            "V086 Phase 5 devait la recréer (valeurs V045)."
        )

    def test_audit_log_interval_is_monthly(self, db):
        """
        AC#1 — L'expression INTERVAL de partitionnement doit être mensuelle
        (NUMTOYMINTERVAL(1, 'MONTH') ≈ '0-1' en format Oracle YM).
        Vérifie que l'intervalle est bien d'un mois et non d'un autre pas de temps.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT INTERVAL
                FROM USER_PART_TABLES
                WHERE TABLE_NAME = 'AUDIT_LOG'
            """)
            row = cursor.fetchone()

        assert row is not None, "Aucune entrée dans USER_PART_TABLES pour AUDIT_LOG"
        interval_value = row[0]
        assert interval_value is not None, (
            "L'expression INTERVAL est NULL — AUDIT_LOG n'est pas une Range INTERVAL table."
        )
        # Oracle stocke NUMTOYMINTERVAL(1,'MONTH') comme '0-1' (year-month format)
        assert '0-1' in str(interval_value), (
            f"Expression INTERVAL inattendue : '{interval_value}'. "
            "Attendu : '0-1' (= NUMTOYMINTERVAL(1,'MONTH'), partitionnement mensuel). "
            "V086 devait créer AUDIT_LOG avec INTERVAL (NUMTOYMINTERVAL(1,'MONTH'))."
        )

    def test_old_entity_type_timestamp_index_absent(self, db):
        """
        AC#4 — L'ancien index IDX_AUDIT_LOG_ENTITY_TYPE_TIMESTAMP (V029) doit avoir été supprimé.
        Il était sur AUDIT_LOG_OLD et a été détruit avec DROP TABLE AUDIT_LOG_OLD PURGE (Phase 11).
        Remplacé par IDX_AUDITLOG_CREATED_ENTITY sur (TIMESTAMP, ENTITY_TYPE, ENTITY_ID).
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT INDEX_NAME
                FROM USER_INDEXES
                WHERE TABLE_NAME = 'AUDIT_LOG'
                  AND INDEX_NAME = 'IDX_AUDIT_LOG_ENTITY_TYPE_TIMESTAMP'
            """)
            rows = cursor.fetchall()

        assert not rows, (
            "L'ancien index IDX_AUDIT_LOG_ENTITY_TYPE_TIMESTAMP (V029) est encore présent. "
            "Il aurait dû être supprimé avec AUDIT_LOG_OLD en Phase 11 de V086. "
            "Il est remplacé par IDX_AUDITLOG_CREATED_ENTITY (TIMESTAMP, ENTITY_TYPE, ENTITY_ID)."
        )

    def test_partition_pruning_by_timestamp(self, db):
        """
        AC#3 — Les requêtes avec filtre TIMESTAMP doivent bénéficier du partition pruning.
        Vérifie via EXPLAIN PLAN que le plan contient 'PARTITION RANGE ITERATOR' ou
        'PARTITION RANGE SINGLE' pour une requête avec WHERE TIMESTAMP BETWEEN :d1 AND :d2.

        IMPORTANT : Les valeurs de date sont des LITTÉRAUX (pas SYSTIMESTAMP).
        EXPLAIN PLAN étant statique (parse-time), l'optimiseur ne peut pas évaluer
        SYSTIMESTAMP et produirait toujours PARTITION RANGE ALL, rendant le test sans valeur.
        Avec des dates littérales, Oracle calcule statiquement les partitions cibles et
        génère PARTITION RANGE SINGLE ou ITERATOR — preuve effective du partition pruning.

        Note : Ce test nécessite les droits EXPLAIN PLAN et PLAN_TABLE.
        Il peut être ignoré si les droits ne sont pas disponibles en CI.
        """
        statement_id = 'TEST_40_4_PRUNING'
        partition_rows: list[tuple[str, str | None]] = []

        try:
            with connection.cursor() as cursor:
                # Purger d'éventuels résidus AVANT de générer un nouveau plan
                # (Oracle ne remplace pas les entrées existantes pour un même STATEMENT_ID)
                cursor.execute(
                    f"DELETE FROM PLAN_TABLE WHERE STATEMENT_ID = '{statement_id}'"
                )

                # Générer le plan d'exécution pour une requête filtrée par TIMESTAMP
                # Dates LITTÉRALES (pas SYSTIMESTAMP) : l'optimiseur peut calculer statiquement
                # les partitions concernées et générer PARTITION RANGE SINGLE ou ITERATOR.
                cursor.execute(f"""
                    EXPLAIN PLAN SET STATEMENT_ID = '{statement_id}' FOR
                    SELECT ID, ACTION_TYPE, USER_ID
                    FROM AUDIT_LOG
                    WHERE TIMESTAMP BETWEEN TIMESTAMP '2024-01-01 00:00:00'
                      AND TIMESTAMP '2024-02-01 00:00:00'
                """)

                # Récupérer les opérations de partition du plan
                # Accept both OPERATION='PARTITION' (OPTIONS='RANGE ITERATOR'/'RANGE SINGLE')
                # and OPERATION='PARTITION RANGE' (OPTIONS='ITERATOR'/'SINGLE') — Oracle version variance
                cursor.execute(f"""
                    SELECT OPERATION, OPTIONS
                    FROM PLAN_TABLE
                    WHERE STATEMENT_ID = '{statement_id}'
                      AND (OPERATION = 'PARTITION' OR OPERATION = 'PARTITION RANGE')
                    ORDER BY ID
                """)
                partition_rows = cursor.fetchall()

                # Nettoyer après lecture
                cursor.execute(
                    f"DELETE FROM PLAN_TABLE WHERE STATEMENT_ID = '{statement_id}'"
                )
        except Exception as db_exc:
            if 'ORA-00942' in str(db_exc):
                partition_rows = []
            else:
                raise

        if not partition_rows:
            # Vérifier si PLAN_TABLE est accessible (fallback quand plan vide ou ORA-00942)
            check_id = 'TEST_40_4_CHECK'
            plan_accessible = False
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"DELETE FROM PLAN_TABLE WHERE STATEMENT_ID = '{check_id}'"
                    )
                    cursor.execute(
                        f"EXPLAIN PLAN SET STATEMENT_ID = '{check_id}' FOR SELECT 1 FROM DUAL"
                    )
                    cursor.execute(
                        f"SELECT COUNT(*) FROM PLAN_TABLE WHERE STATEMENT_ID = '{check_id}'"
                    )
                    plan_accessible = cursor.fetchone()[0] > 0
                    cursor.execute(
                        f"DELETE FROM PLAN_TABLE WHERE STATEMENT_ID = '{check_id}'"
                    )
            except Exception as check_exc:
                if 'ORA-00942' in str(check_exc):
                    plan_accessible = False
                else:
                    raise

            if not plan_accessible:
                pytest.skip(
                    "PLAN_TABLE non accessible ou EXPLAIN PLAN non supporté dans cet environnement"
                )
            else:
                pytest.fail(
                    "Aucune opération PARTITION RANGE dans le plan d'exécution. "
                    "Le partition pruning n'est pas actif pour la requête filtrée par TIMESTAMP. "
                    "Vérifier que AUDIT_LOG est bien partitionnée par RANGE INTERVAL sur TIMESTAMP."
                )

        # Vérifier PARTITION RANGE ITERATOR ou SINGLE — preuve du partition pruning actif.
        # OPTIONS peut être 'ITERATOR'/'SINGLE' (OPERATION='PARTITION RANGE') ou
        # 'RANGE ITERATOR'/'RANGE SINGLE' (OPERATION='PARTITION') selon version Oracle.
        # PARTITION RANGE ALL = pas de pruning = ÉCHEC AC#3.
        pruning_found = any(
            opt and ('ITERATOR' in opt or 'SINGLE' in opt) and 'ALL' not in (opt or '')
            for _, opt in partition_rows
        )

        assert pruning_found, (
            f"Opérations PARTITION RANGE trouvées : {partition_rows}. "
            "Aucune n'est ITERATOR ou SINGLE — le partition pruning n'est pas actif. "
            "AC#3 exige que les requêtes filtrées par TIMESTAMP scannent uniquement "
            "les partitions concernées. PARTITION RANGE ALL indique que toutes les "
            "partitions sont scannées malgré le filtre date."
        )
