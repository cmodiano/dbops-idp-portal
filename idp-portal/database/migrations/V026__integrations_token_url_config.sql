-- Migration V026: Integrations - token_url + CONFIG (flow steps + credentials per step)
-- Story 5.3 - token_url et structure flow (étapes + secrets par step) en JSON
-- AC1, AC2: TOKEN_URL (optional), CONFIG (CLOB/JSON optional)

-- 1. Add TOKEN_URL column (nullable, validated http(s) at application layer)
ALTER TABLE INTEGRATIONS ADD TOKEN_URL VARCHAR2(2000);

-- 2. Add CONFIG column (CLOB for JSON: auth_flow steps, url_ref, credential keys per step)
ALTER TABLE INTEGRATIONS ADD CONFIG CLOB;

-- Comments
COMMENT ON COLUMN INTEGRATIONS.TOKEN_URL IS 'Optional URL for token acquisition (obtain_token step); validated http(s)';
COMMENT ON COLUMN INTEGRATIONS.CONFIG IS 'Optional JSON: auth_flow steps (obtain_token, call_api), url_ref, credentials ref/keys per step';
