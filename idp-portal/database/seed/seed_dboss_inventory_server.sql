-- =============================================================================
-- Seed: Données de test pour DBOPS_INVENTORY.SERVER
-- Usage: exécuter dans le schéma DBOPS_INVENTORY (ou préfixer les tables).
-- Cas d'usage portail: inventaire (Story 13.1), wizard exécution (13.2),
-- filtres par environnement (DEV, STAGING, PROD). Le portail normalise
-- certif/test → staging ; utiliser DEV, STAGING, PROD pour cohérence.
--
-- Le portail (backend) se connecte en IDP_APP. Un synonyme IDP_APP.DBOPS_INVENTORY
-- pointe vers une vue (NAME, ENVIRONMENT, TYPE) construite sur cette table (et
-- éventuellement DB/INSTANCE). Pas de config inventaire nécessaire en fallback.
-- =============================================================================

-- Nettoyer les données de test (optionnel, décommenter si rejeu)
-- DELETE FROM DBOPS_INVENTORY.SERVER WHERE NAME LIKE 'srv-%' OR NAME LIKE 'db-%';

INSERT INTO DBOPS_INVENTORY.SERVER (
  NAME,
  HOSTNAME,
  IP_ADDRESS,
  ENVIRONMENT,
  OS_TYPE,
  STATUS,
  ENABLED,
  LOCATION
) VALUES (
  'srv-dev-01',
  'srv-dev-01.entreprise.local',
  '10.10.1.11',
  'DEV',
  'Linux',
  'ACTIVE',
  'Y',
  'DC1-Rack-A'
);

INSERT INTO DBOPS_INVENTORY.SERVER (
  NAME,
  HOSTNAME,
  IP_ADDRESS,
  ENVIRONMENT,
  OS_TYPE,
  STATUS,
  ENABLED,
  LOCATION
) VALUES (
  'srv-dev-02',
  'srv-dev-02.entreprise.local',
  '10.10.1.12',
  'DEV',
  'Linux',
  'ACTIVE',
  'Y',
  'DC1-Rack-A'
);

INSERT INTO DBOPS_INVENTORY.SERVER (
  NAME,
  HOSTNAME,
  IP_ADDRESS,
  ENVIRONMENT,
  OS_TYPE,
  STATUS,
  ENABLED,
  LOCATION
) VALUES (
  'srv-dev-03',
  'srv-dev-03.entreprise.local',
  '10.10.1.13',
  'DEV',
  'Windows',
  'ACTIVE',
  'Y',
  'DC1-Rack-B'
);

INSERT INTO DBOPS_INVENTORY.SERVER (
  NAME,
  HOSTNAME,
  IP_ADDRESS,
  ENVIRONMENT,
  OS_TYPE,
  STATUS,
  ENABLED,
  LOCATION
) VALUES (
  'srv-test-01',
  'srv-test-01.entreprise.local',
  '10.20.1.21',
  'STAGING',
  'Linux',
  'ACTIVE',
  'Y',
  'DC1-Rack-C'
);

INSERT INTO DBOPS_INVENTORY.SERVER (
  NAME,
  HOSTNAME,
  IP_ADDRESS,
  ENVIRONMENT,
  OS_TYPE,
  STATUS,
  ENABLED,
  LOCATION
) VALUES (
  'srv-test-02',
  'srv-test-02.entreprise.local',
  '10.20.1.22',
  'STAGING',
  'Linux',
  'ACTIVE',
  'Y',
  'DC1-Rack-C'
);

INSERT INTO DBOPS_INVENTORY.SERVER (
  NAME,
  HOSTNAME,
  IP_ADDRESS,
  ENVIRONMENT,
  OS_TYPE,
  STATUS,
  ENABLED,
  LOCATION
) VALUES (
  'srv-prod-01',
  'srv-prod-01.entreprise.local',
  '10.30.1.31',
  'PROD',
  'Linux',
  'ACTIVE',
  'Y',
  'DC2-Rack-A'
);

INSERT INTO DBOPS_INVENTORY.SERVER (
  NAME,
  HOSTNAME,
  IP_ADDRESS,
  ENVIRONMENT,
  OS_TYPE,
  STATUS,
  ENABLED,
  LOCATION
) VALUES (
  'srv-prod-02',
  'srv-prod-02.entreprise.local',
  '10.30.1.32',
  'PROD',
  'Linux',
  'ACTIVE',
  'Y',
  'DC2-Rack-A'
);

INSERT INTO DBOPS_INVENTORY.SERVER (
  NAME,
  HOSTNAME,
  IP_ADDRESS,
  ENVIRONMENT,
  OS_TYPE,
  STATUS,
  ENABLED,
  LOCATION
) VALUES (
  'srv-prod-03',
  'srv-prod-03.entreprise.local',
  '10.30.1.33',
  'PROD',
  'Linux',
  'ACTIVE',
  'Y',
  'DC2-Rack-B'
);

-- Serveur désactivé (pour tester filtrage / vue ENABLED = 'Y')
INSERT INTO DBOPS_INVENTORY.SERVER (
  NAME,
  HOSTNAME,
  IP_ADDRESS,
  ENVIRONMENT,
  OS_TYPE,
  STATUS,
  ENABLED,
  LOCATION
) VALUES (
  'srv-dev-off',
  'srv-dev-off.entreprise.local',
  '10.10.1.99',
  'DEV',
  'Linux',
  'ACTIVE',
  'N',
  'DC1-Rack-A'
);

COMMIT;

-- Vérification rapide
-- SELECT NAME, ENVIRONMENT, OS_TYPE, ENABLED FROM DBOPS_INVENTORY.SERVER ORDER BY ENVIRONMENT, NAME;
