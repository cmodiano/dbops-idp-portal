-- Story 31.12: Add oauth2_client_credentials and api_key to AUTH_FLOW CHECK constraint
-- Original constraint created in V024__integrations_type_libre_auth_flow.sql
ALTER TABLE INTEGRATIONS DROP CONSTRAINT CK_INTEGRATIONS_AUTH_FLOW;

ALTER TABLE INTEGRATIONS ADD CONSTRAINT CK_INTEGRATIONS_AUTH_FLOW
    CHECK (AUTH_FLOW IS NULL OR AUTH_FLOW IN (
        'token', 'basic', 'basic_then_token', 'pat',
        'oauth2_client_credentials', 'api_key'
    ));
