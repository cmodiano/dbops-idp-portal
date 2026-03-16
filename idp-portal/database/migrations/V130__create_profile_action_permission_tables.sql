-- V130: Tables PROFILE_ACTION_ALLOWLIST, PROFILE_ACTION_TAG_PATTERNS, PROFILE_ACTION_ENVS
-- Story 78.11 — Normalisation des permissions action de profil
--
-- Extraction des champs JSON CLOB (ACTION_IDS_JSON, TAG_PATTERNS_JSON, ENVIRONMENTS_JSON)
-- de PROFILE_ACTION_PERMISSIONS vers des tables relationnelles pour requêtes SQL directes,
-- indexes, contraintes DB et audit granulaire.

-- ============================================================
-- 1. PROFILE_ACTION_ALLOWLIST — une ligne par action autorisée par profil
-- ============================================================

CREATE TABLE PROFILE_ACTION_ALLOWLIST (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    PROFILE_ID      NUMBER NOT NULL,
    ACTION_ID       NUMBER NOT NULL,
    CONSTRAINT FK_PAA_PROFILE FOREIGN KEY (PROFILE_ID)
        REFERENCES PROFILE_ACTION_PERMISSIONS(PROFILE_ID) ON DELETE CASCADE,
    CONSTRAINT UK_PAA_PROFILE_ACTION UNIQUE (PROFILE_ID, ACTION_ID)
);

COMMENT ON TABLE PROFILE_ACTION_ALLOWLIST IS 'Actions autorisées par profil — une ligne par action (normalisation de ACTION_IDS_JSON).';
COMMENT ON COLUMN PROFILE_ACTION_ALLOWLIST.PROFILE_ID IS 'FK vers PROFILE_ACTION_PERMISSIONS — profil propriétaire.';
COMMENT ON COLUMN PROFILE_ACTION_ALLOWLIST.ACTION_ID IS 'Référence logique vers ACTIONS_CATALOG.ID — action autorisée.';

-- ============================================================
-- 2. PROFILE_ACTION_TAG_PATTERNS — une ligne par tag pattern autorisé
-- ============================================================

CREATE TABLE PROFILE_ACTION_TAG_PATTERNS (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    PROFILE_ID      NUMBER NOT NULL,
    TAG_PATTERN     VARCHAR2(255) NOT NULL,
    CONSTRAINT FK_PATP_PROFILE FOREIGN KEY (PROFILE_ID)
        REFERENCES PROFILE_ACTION_PERMISSIONS(PROFILE_ID) ON DELETE CASCADE,
    CONSTRAINT UK_PATP_PROFILE_TAG UNIQUE (PROFILE_ID, TAG_PATTERN)
);

COMMENT ON TABLE PROFILE_ACTION_TAG_PATTERNS IS 'Tag patterns autorisés par profil — une ligne par pattern (normalisation de TAG_PATTERNS_JSON).';
COMMENT ON COLUMN PROFILE_ACTION_TAG_PATTERNS.PROFILE_ID IS 'FK vers PROFILE_ACTION_PERMISSIONS — profil propriétaire.';
COMMENT ON COLUMN PROFILE_ACTION_TAG_PATTERNS.TAG_PATTERN IS 'Pattern de tag autorisé (ex: oracle, provisioning).';

-- ============================================================
-- 3. PROFILE_ACTION_ENVS — une ligne par environnement autorisé
-- ============================================================

CREATE TABLE PROFILE_ACTION_ENVS (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    PROFILE_ID      NUMBER NOT NULL,
    ENVIRONMENT     VARCHAR2(255) NOT NULL,
    CONSTRAINT FK_PAE_PROFILE FOREIGN KEY (PROFILE_ID)
        REFERENCES PROFILE_ACTION_PERMISSIONS(PROFILE_ID) ON DELETE CASCADE,
    CONSTRAINT UK_PAE_PROFILE_ENV UNIQUE (PROFILE_ID, ENVIRONMENT)
);

COMMENT ON TABLE PROFILE_ACTION_ENVS IS 'Environnements autorisés par profil — une ligne par environnement (normalisation de ENVIRONMENTS_JSON).';
COMMENT ON COLUMN PROFILE_ACTION_ENVS.PROFILE_ID IS 'FK vers PROFILE_ACTION_PERMISSIONS — profil propriétaire.';
COMMENT ON COLUMN PROFILE_ACTION_ENVS.ENVIRONMENT IS 'Environnement autorisé (ex: dev, staging, prod).';

-- ============================================================
-- 4. Indexes (FK lookup)
-- ============================================================

CREATE INDEX IDX_PAA_PROFILE_ID ON PROFILE_ACTION_ALLOWLIST(PROFILE_ID);
CREATE INDEX IDX_PATP_PROFILE_ID ON PROFILE_ACTION_TAG_PATTERNS(PROFILE_ID);
CREATE INDEX IDX_PAE_PROFILE_ID ON PROFILE_ACTION_ENVS(PROFILE_ID);
