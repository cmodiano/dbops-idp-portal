-- V051: Create REF_PLATFORMS table (Story 13.7)
-- Platforms are now managed via reference table instead of CHECK constraints
-- This allows DBOPS to manage platforms without code changes

-- Create REF_PLATFORMS reference table
CREATE TABLE REF_PLATFORMS (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    CODE            VARCHAR2(50) NOT NULL,
    LABEL           VARCHAR2(100) NOT NULL,
    DISPLAY_ORDER   NUMBER DEFAULT 0 NOT NULL,
    IS_ACTIVE       NUMBER(1) DEFAULT 1 NOT NULL,
    
    CONSTRAINT UK_REF_PLATFORMS_CODE UNIQUE (CODE),
    CONSTRAINT CK_REF_PLATFORMS_IS_ACTIVE CHECK (IS_ACTIVE IN (0, 1))
);

-- Index for active platforms queries
CREATE INDEX IDX_REF_PLATFORMS_IS_ACTIVE ON REF_PLATFORMS(IS_ACTIVE);
CREATE INDEX IDX_REF_PLATFORMS_DISPLAY_ORDER ON REF_PLATFORMS(DISPLAY_ORDER);

-- Comments
COMMENT ON TABLE REF_PLATFORMS IS 'Reference table for execution platforms. Managed by DBOPS via admin interface.';
COMMENT ON COLUMN REF_PLATFORMS.CODE IS 'Unique code identifier (e.g., AAP, GitHub Actions, Azure DevOps, Terraform)';
COMMENT ON COLUMN REF_PLATFORMS.LABEL IS 'Display label (can be same as CODE)';
COMMENT ON COLUMN REF_PLATFORMS.DISPLAY_ORDER IS 'Order for display in dropdowns/lists';
COMMENT ON COLUMN REF_PLATFORMS.IS_ACTIVE IS '1 = active, 0 = inactive (soft delete)';

-- Insert current platform values
INSERT INTO REF_PLATFORMS (CODE, LABEL, DISPLAY_ORDER, IS_ACTIVE) VALUES ('AAP', 'AAP (Ansible Automation Platform)', 1, 1);
INSERT INTO REF_PLATFORMS (CODE, LABEL, DISPLAY_ORDER, IS_ACTIVE) VALUES ('GitHub Actions', 'GitHub Actions', 2, 1);
INSERT INTO REF_PLATFORMS (CODE, LABEL, DISPLAY_ORDER, IS_ACTIVE) VALUES ('Azure DevOps', 'Azure DevOps', 3, 1);
INSERT INTO REF_PLATFORMS (CODE, LABEL, DISPLAY_ORDER, IS_ACTIVE) VALUES ('Terraform', 'Terraform', 4, 1);
