-- V077: Story 27.11 — Ajout de SECRET_SERVICE_ID à INTEGRATIONS
-- Permet de spécifier quelle intégration Vault utiliser pour résoudre les secrets
-- d'une intégration donnée. NULL = Vault par défaut (variables d'environnement).

-- Ajout de la colonne
ALTER TABLE INTEGRATIONS ADD SECRET_SERVICE_ID NUMBER(19) NULL;

-- Contrainte FK self-reference
ALTER TABLE INTEGRATIONS ADD CONSTRAINT FK_INTEGRATION_SECRET_SERVICE
  FOREIGN KEY (SECRET_SERVICE_ID) REFERENCES INTEGRATIONS(ID);

-- Commentaire Oracle
COMMENT ON COLUMN INTEGRATIONS.SECRET_SERVICE_ID IS
  'ID intégration Vault utilisée pour résoudre les secrets de cette intégration (NULL = Vault par défaut via variables d''environnement)';
