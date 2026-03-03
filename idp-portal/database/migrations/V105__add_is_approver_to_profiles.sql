-- V105: Add IS_APPROVER column to PROFILES (Story 57.14)
-- Epic 57 - Champ is_approver pour désigner les profils éligibles comme approbateurs dans les steps gate approval
-- Pattern INCON-4: NUMBER(1) avec CHECK (0, 1), backfill DBA et DBOPS à 1
-- Idempotent pour compatibilité avec baseline mis à jour

DECLARE
  v_cnt NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_cnt FROM user_tab_columns
  WHERE table_name = 'PROFILES' AND column_name = 'IS_APPROVER';
  IF v_cnt = 0 THEN
    EXECUTE IMMEDIATE 'ALTER TABLE PROFILES ADD IS_APPROVER NUMBER(1) DEFAULT 0 NOT NULL';
    EXECUTE IMMEDIATE 'ALTER TABLE PROFILES ADD CONSTRAINT CK_PROFILES_IS_APPROVER CHECK (IS_APPROVER IN (0, 1))';
    EXECUTE IMMEDIATE 'COMMENT ON COLUMN PROFILES.IS_APPROVER IS ''1 = profil éligible comme approbateur dans un step gate approval (Epic 57)''';
    COMMIT;
  END IF;
END;
/
