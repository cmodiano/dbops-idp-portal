-- V137: Rename PROFILE_TARGET_ATTRIBUTE_FILTERS → PROFILE_TARGET_ATTR_FILTERS
--
-- Oracle limite les identifiants à 30 caractères. PROFILE_TARGET_ATTRIBUTE_FILTERS (32 chars)
-- est tronqué par Django avec un hash (PROFILE_TARGET_ATTRIBUTE_FEDFB), provoquant ORA-00942.
-- Renommage pour respecter la limite 30 chars et aligner Django/Flyway.
--
-- Prerequisite: V132 created PROFILE_TARGET_ATTRIBUTE_FILTERS.

ALTER TABLE PROFILE_TARGET_ATTRIBUTE_FILTERS RENAME TO PROFILE_TARGET_ATTR_FILTERS;

COMMENT ON TABLE PROFILE_TARGET_ATTR_FILTERS IS 'Filtres par attribut par profil — une ligne par (clé, valeur) (normalisation de FILTER_BY_ATTRIBUTE_JSON).';
COMMENT ON COLUMN PROFILE_TARGET_ATTR_FILTERS.PROFILE_ID IS 'FK vers PROFILE_TARGET_PERMISSIONS — profil propriétaire.';
COMMENT ON COLUMN PROFILE_TARGET_ATTR_FILTERS.ATTRIBUTE_KEY IS 'Clé d''attribut inventaire (ex: engine_type, zone).';
COMMENT ON COLUMN PROFILE_TARGET_ATTR_FILTERS.ATTRIBUTE_VALUE IS 'Valeur d''attribut autorisée (ex: oracle, prod).';
