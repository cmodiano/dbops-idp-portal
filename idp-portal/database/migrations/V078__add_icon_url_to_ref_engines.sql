-- V078: Story 31.3 — Ajout de ICON_URL à REF_ENGINES
-- Permet à un DBOPS de définir l'icône (URL image ou identifiant) pour chaque moteur
-- afin d'afficher un logo personnalisé dans le catalogue, les exécutions et les rapports.

ALTER TABLE REF_ENGINES ADD ICON_URL VARCHAR2(500 CHAR) NULL;

COMMENT ON COLUMN REF_ENGINES.ICON_URL IS
  'URL d''image (SVG/PNG) ou identifiant d''icône prédéfinie pour l''affichage du moteur. NULL = fallback vers icônes par défaut (Story 31.3).';
