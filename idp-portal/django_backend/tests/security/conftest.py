"""
Security test fixtures.
Story 15.2: Tests de securite fonctionnels.

Provides fixtures that use real JWT tokens (not force_authenticate)
to exercise the full authentication pipeline.
"""

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from rest_framework.test import APIClient

from idp_auth.jwt_utils import create_access_token, create_refresh_token
from idp_auth.models import User
from integrations.models import Integration
from catalog.models import Action
from profiles.models import Profile


# ============================================================================
# User fixtures
# ============================================================================

@pytest.fixture
def sec_dbops_user(db):
    """DBOPS admin user for security tests."""
    return User.objects.create(
        username='sec_dbops',
        display_name='Security DBOPS',
        profile='dbops',
    )


@pytest.fixture
def sec_dba_user(db):
    """DBA user for security tests."""
    return User.objects.create(
        username='sec_dba',
        display_name='Security DBA',
        profile='dba',
    )


@pytest.fixture
def sec_dba_infra_user(db):
    """DBA Infrastructure user for security tests."""
    return User.objects.create(
        username='sec_dba_infra',
        display_name='Security DBA Infra',
        profile='dba_infrastructure',
    )


@pytest.fixture
def sec_business_user(db):
    """Client Business user for security tests."""
    return User.objects.create(
        username='sec_business',
        display_name='Security Business',
        profile='client_business',
    )


# ============================================================================
# Profile fixtures
# ============================================================================

@pytest.fixture
def sec_profile_dbops(db):
    """DBOPS profile with admin flag."""
    return Profile.objects.create(
        name='DBOPS',
        ad_group='CN=DBOPS,OU=Groups,DC=corp,DC=com',
        is_admin=1,
        is_auditor=0,
    )


@pytest.fixture
def sec_profile_dba(db):
    """DBA profile."""
    return Profile.objects.create(
        name='DBA',
        ad_group='CN=DBA,OU=Groups,DC=corp,DC=com',
        is_admin=0,
        is_auditor=0,
    )


@pytest.fixture
def sec_profile_business(db):
    """Client Business profile."""
    return Profile.objects.create(
        name='client_business',
        ad_group='CN=Business,OU=Groups,DC=corp,DC=com',
        is_admin=0,
        is_auditor=0,
    )


# ============================================================================
# Integration / Action fixtures
# ============================================================================

@pytest.fixture
def sec_integration(db):
    """Integration for security tests."""
    return Integration.objects.create(
        type='aap',
        name='Security AAP',
        base_url='https://aap.example.com',
    )


@pytest.fixture
def sec_action(db, sec_dbops_user, sec_integration):
    """Published action for security tests."""
    return Action.objects.create(
        name='Security Action',
        category='Provisioning',
        engine='Oracle',
        platform='AAP',
        status='published',
        created_by=sec_dbops_user,
        integration=sec_integration,
    )


# ============================================================================
# Token generation helpers
# ============================================================================

def _token_data(user, ad_groups=None):
    """Build token payload dict from user."""
    return {
        'sub': str(user.id),
        'username': user.username,
        'profile': user.profile,
        'ad_groups': ad_groups or [user.profile],
    }


@pytest.fixture
def sec_dbops_token(sec_dbops_user):
    """Valid access token for DBOPS user."""
    return create_access_token(_token_data(sec_dbops_user, ['dbops']))


@pytest.fixture
def sec_dba_token(sec_dba_user):
    """Valid access token for DBA user."""
    return create_access_token(_token_data(sec_dba_user, ['dba']))


@pytest.fixture
def sec_business_token(sec_business_user):
    """Valid access token for Client Business user."""
    return create_access_token(_token_data(sec_business_user, ['client_business']))


@pytest.fixture
def sec_dbops_refresh_token(sec_dbops_user):
    """Valid refresh token for DBOPS user."""
    return create_refresh_token(_token_data(sec_dbops_user, ['dbops']))


@pytest.fixture
def sec_dba_refresh_token(sec_dba_user):
    """Valid refresh token for DBA user."""
    return create_refresh_token(_token_data(sec_dba_user, ['dba']))


# ============================================================================
# Expired / malformed token fixtures
# ============================================================================

@pytest.fixture
def expired_access_token(sec_dba_user, settings):
    """Access token that is already expired."""
    data = _token_data(sec_dba_user)
    data['exp'] = datetime.now(timezone.utc) - timedelta(hours=1)
    data['type'] = 'access'
    return jwt.encode(data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture
def wrong_signature_token(sec_dba_user, settings):
    """Access token signed with wrong secret key."""
    data = _token_data(sec_dba_user)
    data['exp'] = datetime.now(timezone.utc) + timedelta(hours=1)
    data['type'] = 'access'
    return jwt.encode(data, 'wrong-secret-key-not-matching', algorithm=settings.JWT_ALGORITHM)


@pytest.fixture
def refresh_used_as_access_token(sec_dba_user):
    """Refresh token presented as access token (type mismatch)."""
    return create_refresh_token(_token_data(sec_dba_user))


@pytest.fixture
def corrupted_token():
    """Completely corrupted / garbage token."""
    return 'not.a.valid.jwt.token'


@pytest.fixture
def tampered_payload_token(sec_dba_user, settings):
    """Token with tampered user_id in payload (changed sub after signing)."""
    data = _token_data(sec_dba_user)
    data['sub'] = '999999'  # non-existent user
    data['exp'] = datetime.now(timezone.utc) + timedelta(hours=1)
    data['type'] = 'access'
    return jwt.encode(data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# ============================================================================
# API client helpers
# ============================================================================

@pytest.fixture
def anon_client():
    """Unauthenticated API client."""
    return APIClient()


def make_auth_client(token):
    """Create an API client with Bearer token."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client
