"""
Tests de validation de la migration V087 — PKG_IDP_MAINTENANCE et politique de rétention (Story 40.5).

Ces tests sont des tests d'intégration nécessitant une connexion Oracle réelle.
Ils ne s'exécutent PAS en tests unitaires avec mock DB.

Marqués @pytest.mark.integration — exécutés uniquement en CI avec Oracle disponible.

Pour exécuter localement (Oracle Docker requis) :
    pytest core/tests/test_migration_40_5.py -v -m integration \\
        --ds=idp_backend.test_settings

Couverture AC#8 et AC#9 :
    AC#8 — Script V087 installe PKG_IDP_MAINTENANCE + IDP_MAINTENANCE_LOG
    AC#9 — Tests d'intégration de la procédure de purge :
        - La procédure/package existe dans USER_OBJECTS
        - L'appel en dry_run=1 ne drop aucune partition
        - Les partitions dans la fenêtre de rétention ne sont pas droppées
        - Les index globaux restent VALID après drop
"""

import pytest
from django.db import connection


@pytest.mark.integration
class TestMigration40_5PurgeProcedure:
    """
    Tests de validation de la migration V087 — PKG_IDP_MAINTENANCE.

    AC#8 : Script V087 installe le package et la table de log
    AC#9 : Tests fonctionnels de la procédure de purge
    """

    def test_purge_procedure_exists(self, db):
        """
        AC#8 / AC#9 — Le package PKG_IDP_MAINTENANCE doit exister dans USER_OBJECTS
        avec les deux composants : PACKAGE (spec) et PACKAGE BODY, tous deux VALID.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT OBJECT_TYPE, STATUS
                FROM USER_OBJECTS
                WHERE OBJECT_NAME = 'PKG_IDP_MAINTENANCE'
                  AND OBJECT_TYPE IN ('PACKAGE', 'PACKAGE BODY')
                ORDER BY OBJECT_TYPE
            """)
            rows = cursor.fetchall()

        object_map = {row[0]: row[1] for row in rows}

        assert 'PACKAGE' in object_map, (
            "PKG_IDP_MAINTENANCE PACKAGE spec introuvable dans USER_OBJECTS. "
            "V087 Phase 2 devait créer la spécification du package."
        )
        assert object_map['PACKAGE'] == 'VALID', (
            f"PKG_IDP_MAINTENANCE PACKAGE spec est '{object_map['PACKAGE']}' au lieu de 'VALID'. "
            "Vérifier les erreurs de compilation : SELECT * FROM USER_ERRORS WHERE NAME='PKG_IDP_MAINTENANCE'."
        )

        assert 'PACKAGE BODY' in object_map, (
            "PKG_IDP_MAINTENANCE PACKAGE BODY introuvable dans USER_OBJECTS. "
            "V087 Phase 3 devait créer le corps du package."
        )
        assert object_map['PACKAGE BODY'] == 'VALID', (
            f"PKG_IDP_MAINTENANCE PACKAGE BODY est '{object_map['PACKAGE BODY']}' au lieu de 'VALID'. "
            "Vérifier les erreurs de compilation : SELECT * FROM USER_ERRORS "
            "WHERE NAME='PKG_IDP_MAINTENANCE' AND TYPE='PACKAGE BODY'."
        )

    def test_maintenance_log_table_exists(self, db):
        """
        AC#8 — La table IDP_MAINTENANCE_LOG doit exister après V087.
        Vérifie la présence dans USER_TABLES et la structure minimale des colonnes.
        """
        with connection.cursor() as cursor:
            # Vérifier la table
            cursor.execute(
                "SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME = 'IDP_MAINTENANCE_LOG'"
            )
            table_exists = cursor.fetchone()[0]

        assert table_exists == 1, (
            "Table IDP_MAINTENANCE_LOG introuvable dans USER_TABLES. "
            "V087 Phase 1 devait créer cette table."
        )

        # Vérifier les colonnes obligatoires
        expected_columns = {
            'ID', 'EXECUTED_AT', 'TABLE_NAME', 'PARTITION_NAME',
            'ACTION', 'STATUS', 'DRY_RUN', 'NOTES'
        }
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COLUMN_NAME
                FROM USER_TAB_COLUMNS
                WHERE TABLE_NAME = 'IDP_MAINTENANCE_LOG'
            """)
            found_columns = {row[0] for row in cursor.fetchall()}

        missing = expected_columns - found_columns
        assert not missing, (
            f"Colonnes manquantes dans IDP_MAINTENANCE_LOG : {missing}. "
            "V087 Phase 1 devait créer toutes les colonnes spécifiées dans la story."
        )

    def test_maintenance_log_index_exists(self, db):
        """
        AC#8 — L'index IDX_MAINT_LOG_EXECUTED_AT doit exister sur IDP_MAINTENANCE_LOG.
        Requis pour les requêtes de monitoring sur EXECUTED_AT.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT INDEX_NAME, STATUS
                FROM USER_INDEXES
                WHERE TABLE_NAME = 'IDP_MAINTENANCE_LOG'
                  AND INDEX_NAME = 'IDX_MAINT_LOG_EXECUTED_AT'
            """)
            row = cursor.fetchone()

        assert row is not None, (
            "Index IDX_MAINT_LOG_EXECUTED_AT introuvable sur IDP_MAINTENANCE_LOG. "
            "V087 Phase 1 devait créer cet index pour le monitoring."
        )
        index_name, status = row
        assert status == 'VALID', (
            f"IDX_MAINT_LOG_EXECUTED_AT est '{status}' au lieu de 'VALID'. "
            "L'index doit être valide après création."
        )

    def test_dry_run_does_not_drop_partitions(self, db):
        """
        AC#9 — L'exécution en mode dry_run=1 ne doit supprimer aucune partition.

        Stratégie :
        1. Compter les partitions EXECUTIONS et AUDIT_LOG avant l'appel.
        2. Appeler purge_old_partitions avec p_dry_run=1 et rétention minimale (1 mois)
           pour maximiser les candidats théoriques.
        3. Vérifier que le nombre de partitions est identique après l'appel.
        4. Vérifier qu'aucune entrée IDP_MAINTENANCE_LOG avec DRY_RUN=0 n'a été créée
           depuis le début de ce test (isolation par horodatage, pas par pattern de notes).
        """
        with connection.cursor() as cursor:
            # Enregistrer l'horodatage de départ pour isoler les entrées créées par ce test
            cursor.execute("SELECT SYSTIMESTAMP FROM DUAL")
            test_start_time = cursor.fetchone()[0]

            # Compter les partitions avant
            cursor.execute("""
                SELECT TABLE_NAME, COUNT(*) AS PART_COUNT
                FROM USER_TAB_PARTITIONS
                WHERE TABLE_NAME IN ('EXECUTIONS', 'AUDIT_LOG')
                GROUP BY TABLE_NAME
            """)
            counts_before = {row[0]: row[1] for row in cursor.fetchall()}

            # Appeler purge_old_partitions en mode dry_run avec rétention très courte
            # p_retention_executions=1 et p_retention_audit_log=1 maximisent les candidats théoriques
            cursor.execute("""
                BEGIN
                    PKG_IDP_MAINTENANCE.purge_old_partitions(
                        p_retention_executions => 1,
                        p_retention_audit_log  => 1,
                        p_dry_run              => 1
                    );
                END;
            """)

            # Compter les partitions après
            cursor.execute("""
                SELECT TABLE_NAME, COUNT(*) AS PART_COUNT
                FROM USER_TAB_PARTITIONS
                WHERE TABLE_NAME IN ('EXECUTIONS', 'AUDIT_LOG')
                GROUP BY TABLE_NAME
            """)
            counts_after = {row[0]: row[1] for row in cursor.fetchall()}

            # Vérifier les entrées de log créées depuis le début du test
            cursor.execute("""
                SELECT ACTION, STATUS, DRY_RUN
                FROM IDP_MAINTENANCE_LOG
                WHERE DRY_RUN = 0
                  AND EXECUTED_AT >= :start_time
            """, [test_start_time])
            real_drops = cursor.fetchall()

        # Vérifier que les comptes de partitions sont identiques
        for table_name, count_before in counts_before.items():
            count_after = counts_after.get(table_name, 0)
            assert count_after == count_before, (
                f"Le nombre de partitions de {table_name} a changé après dry_run=1 : "
                f"avant={count_before}, après={count_after}. "
                "En mode dry_run=1, aucune partition ne doit être supprimée."
            )

        # Vérifier qu'aucun DROP réel n'a été loggué dans IDP_MAINTENANCE_LOG
        assert not real_drops, (
            "Des entrées avec DRY_RUN=0 ont été trouvées dans IDP_MAINTENANCE_LOG après un appel "
            f"avec p_dry_run=1 : {real_drops}. "
            "La procédure ne doit logger que DRY_RUN=1 en mode simulation."
        )

    def test_purge_respects_retention_window(self, db):
        """
        AC#9 — La procédure ne doit pas supprimer les partitions dans la fenêtre de rétention.

        Stratégie :
        Appeler purge_old_partitions avec p_dry_run=1 et une rétention de 999 mois
        (futur très lointain = aucune partition hors rétention).
        Vérifier qu'aucune entrée DROP n'est créée dans IDP_MAINTENANCE_LOG.
        """
        with connection.cursor() as cursor:
            # Nettoyer les entrées précédentes de ce test
            cursor.execute(
                "DELETE FROM IDP_MAINTENANCE_LOG WHERE EXECUTED_AT > SYSDATE - (1/1440)"  # 1 minute
            )

            # Appeler avec rétention de 999 mois : toutes les partitions sont "dans la fenêtre"
            cursor.execute("""
                BEGIN
                    PKG_IDP_MAINTENANCE.purge_old_partitions(
                        p_retention_executions => 999,
                        p_retention_audit_log  => 999,
                        p_dry_run              => 1
                    );
                END;
            """)

            # Vérifier qu'aucune entrée DROP n'est présente pour ce test
            cursor.execute("""
                SELECT COUNT(*)
                FROM IDP_MAINTENANCE_LOG
                WHERE ACTION = 'DROP'
                  AND EXECUTED_AT > SYSDATE - (1/1440)
            """)
            drop_count = cursor.fetchone()[0]

        assert drop_count == 0, (
            f"La procédure a créé {drop_count} entrée(s) DROP pour une rétention de 999 mois. "
            "Aucune partition ne devrait être identifiée comme hors rétention pour cette valeur. "
            "La logique de comparaison HIGH_VALUE vs cutoff_date est incorrecte."
        )

    def test_global_indexes_valid_after_purge(self, db):
        """
        AC#9 / AC#3 — Les index globaux doivent rester VALID après exécution de la purge.

        Ce test appelle purge_old_partitions(p_dry_run=1) avec une rétention normale (24/12 mois),
        puis vérifie que tous les index EXECUTIONS et AUDIT_LOG sont VALID.
        En mode dry_run, aucun DROP n'est effectué — ce test valide l'état de base des index.
        test_purge_drops_expired_partition (ci-dessous) valide le comportement réel post-DROP.
        """
        with connection.cursor() as cursor:
            # Exécuter la purge en mode dry_run pour s'assurer que la procédure ne cause pas
            # d'invalidation d'index même en mode simulation
            cursor.execute("""
                BEGIN
                    PKG_IDP_MAINTENANCE.purge_old_partitions(
                        p_retention_executions => 24,
                        p_retention_audit_log  => 12,
                        p_dry_run              => 1
                    );
                END;
            """)
            cursor.execute("""
                SELECT INDEX_NAME, TABLE_NAME, STATUS, PARTITIONED
                FROM USER_INDEXES
                WHERE TABLE_NAME IN ('EXECUTIONS', 'AUDIT_LOG')
                  AND STATUS != 'VALID'
                ORDER BY TABLE_NAME, INDEX_NAME
            """)
            invalid_indexes = cursor.fetchall()

        assert not invalid_indexes, (
            f"Des index invalides ont été trouvés sur EXECUTIONS ou AUDIT_LOG : "
            f"{[(row[0], row[1], row[2]) for row in invalid_indexes]}. "
            "Tous les index doivent être VALID. "
            "Si des index sont UNUSABLE, exécuter : ALTER INDEX <name> REBUILD."
        )

    def test_purge_drops_expired_partition(self, db):
        """
        AC#9 — L'appel de la procédure sur une partition hors rétention drop effectivement
        la partition et maintient les index globaux VALID (AC#3).

        Stratégie :
        1. Récupérer l'horodatage de départ pour isoler les entrées de log de ce test.
        2. Appeler purge_executions(p_retention_months=60, p_dry_run=0) pour déclencher
           la purge réelle de toute partition EXECUTIONS antérieure à 60 mois.
        3. Vérifier dans IDP_MAINTENANCE_LOG :
           - Si des SUCCESS sont loggués → des partitions ont été droppées, vérifier
             qu'elles n'existent plus dans USER_TAB_PARTITIONS.
           - Si aucun SUCCESS → pas de partitions éligibles dans l'environnement de test
             (acceptable : la procédure s'est exécutée sans erreur).
        4. Vérifier que les index globaux restent VALID (AC#3 — UPDATE GLOBAL INDEXES).

        Note : Oracle INTERVAL partitioned tables ne permettent pas d'ajouter manuellement
        une partition historique sans INSERT. La présence de partitions éligibles dépend
        donc des données de test de l'environnement. Si aucune partition éligible n'existe,
        ce test valide a minima que purge_executions(p_dry_run=0) s'exécute sans erreur.
        """
        with connection.cursor() as cursor:
            cursor.execute("SELECT SYSTIMESTAMP FROM DUAL")
            test_start_time = cursor.fetchone()[0]

            # Exécuter la purge réelle avec rétention 60 mois
            # Toute partition EXECUTIONS antérieure à 60 mois sera droppée
            cursor.execute("""
                BEGIN
                    PKG_IDP_MAINTENANCE.purge_executions(
                        p_retention_months => 60,
                        p_dry_run          => 0
                    );
                END;
            """)

            # Vérifier les drops effectués dans le log
            cursor.execute("""
                SELECT PARTITION_NAME
                FROM IDP_MAINTENANCE_LOG
                WHERE TABLE_NAME = 'EXECUTIONS'
                  AND ACTION = 'DROP'
                  AND STATUS = 'SUCCESS'
                  AND EXECUTED_AT >= :start_time
            """, [test_start_time])
            dropped_partitions = [row[0] for row in cursor.fetchall()]

            # Si des partitions ont été droppées, vérifier qu'elles n'existent plus
            for partition_name in dropped_partitions:
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM USER_TAB_PARTITIONS
                    WHERE TABLE_NAME = 'EXECUTIONS'
                      AND PARTITION_NAME = :name
                """, [partition_name])
                still_exists = cursor.fetchone()[0]
                assert still_exists == 0, (
                    f"La partition EXECUTIONS.{partition_name} a été loggée comme DROP SUCCESS "
                    f"dans IDP_MAINTENANCE_LOG, mais elle existe encore dans USER_TAB_PARTITIONS. "
                    "Le DROP PARTITION n'a pas été effectif."
                )

            # Vérifier que les index globaux EXECUTIONS sont tous VALID (AC#3)
            cursor.execute("""
                SELECT INDEX_NAME, STATUS
                FROM USER_INDEXES
                WHERE TABLE_NAME = 'EXECUTIONS'
                  AND STATUS != 'VALID'
                ORDER BY INDEX_NAME
            """)
            invalid_indexes = cursor.fetchall()

        assert not invalid_indexes, (
            f"Des index invalides ont été trouvés sur EXECUTIONS après purge_executions(p_dry_run=0) : "
            f"{[(row[0], row[1]) for row in invalid_indexes]}. "
            "UPDATE GLOBAL INDEXES devait maintenir tous les index VALID."
        )

    def test_purge_procedure_public_api(self, db):
        """
        AC#8 — Vérifie que les trois procédures publiques du package sont accessibles
        (USER_PROCEDURES ou USER_ARGUMENTS).

        PKG_IDP_MAINTENANCE doit exposer :
        - purge_old_partitions
        - purge_executions
        - purge_audit_log
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT PROCEDURE_NAME
                FROM USER_PROCEDURES
                WHERE OBJECT_NAME = 'PKG_IDP_MAINTENANCE'
                  AND PROCEDURE_NAME IS NOT NULL
                ORDER BY PROCEDURE_NAME
            """)
            rows = cursor.fetchall()

        found_procedures = {row[0] for row in rows}
        expected_procedures = {
            'PURGE_OLD_PARTITIONS',
            'PURGE_EXECUTIONS',
            'PURGE_AUDIT_LOG',
        }

        missing = expected_procedures - found_procedures
        assert not missing, (
            f"Procédures manquantes dans PKG_IDP_MAINTENANCE : {missing}. "
            "V087 devait créer les trois procédures publiques : "
            "purge_old_partitions, purge_executions, purge_audit_log."
        )

    def test_maintenance_log_pk_exists(self, db):
        """
        AC#8 — La clé primaire PK_IDP_MAINTENANCE_LOG doit exister sur IDP_MAINTENANCE_LOG.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE
                FROM USER_CONSTRAINTS
                WHERE TABLE_NAME = 'IDP_MAINTENANCE_LOG'
                  AND CONSTRAINT_TYPE = 'P'
            """)
            row = cursor.fetchone()

        assert row is not None, (
            "Aucune contrainte PRIMARY KEY trouvée sur IDP_MAINTENANCE_LOG. "
            "V087 Phase 1 devait créer PK_IDP_MAINTENANCE_LOG sur la colonne ID."
        )
        constraint_name, constraint_type = row
        assert constraint_name == 'PK_IDP_MAINTENANCE_LOG', (
            f"Nom de PK inattendu : '{constraint_name}'. Attendu : 'PK_IDP_MAINTENANCE_LOG'. "
            "Vérifier la définition de la contrainte dans V087."
        )
