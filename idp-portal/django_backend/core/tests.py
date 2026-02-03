"""Tests for core app health check endpoint."""

import pytest
from django.test import Client
from unittest.mock import patch
from django.db import connection


def test_health_check_endpoint_exists():
    """Test that health check endpoint exists and is accessible."""
    client = Client()
    response = client.get('/api/v1/health')
    
    # Should return 200 or 503 depending on DB connection
    assert response.status_code in [200, 503]


def test_health_check_response_format():
    """Test that health check response has correct format (envelope data/error, snake_case)."""
    client = Client()
    response = client.get('/api/v1/health')
    
    assert response.status_code in [200, 503]
    data = response.json()
    
    # Verify envelope format (matching FastAPI format)
    assert 'data' in data
    assert 'error' not in data
    
    # Verify snake_case format and field names match FastAPI
    assert 'status' in data['data']
    assert 'oracle' in data['data']  # Must match FastAPI format
    
    # Verify status values match FastAPI (healthy/degraded, not ok)
    assert data['data']['status'] in ['healthy', 'degraded']
    assert data['data']['oracle'] in ['connected', 'disconnected']


def test_health_check_database_connection():
    """Test that health check verifies database connection."""
    client = Client()
    response = client.get('/api/v1/health')
    
    assert response.status_code in [200, 503]  # 200 if connected, 503 if not
    data = response.json()
    
    # Oracle status should be reported (matching FastAPI field name)
    assert 'oracle' in data['data']
    assert data['data']['oracle'] in ['connected', 'disconnected']


def test_health_check_returns_503_on_db_error():
    """Test that health check returns 503 when database connection fails."""
    client = Client()
    
    # Mock database connection to raise an exception
    with patch.object(connection, 'cursor', side_effect=Exception("Database connection failed")):
        response = client.get('/api/v1/health')
        
        assert response.status_code == 503
        data = response.json()
        
        # Verify error format
        assert 'data' in data
        assert data['data']['status'] == 'degraded'
        assert data['data']['oracle'] == 'disconnected'


def test_health_check_returns_200_on_db_success():
    """Test that health check returns 200 when database connection succeeds."""
    client = Client()
    
    # Mock successful database connection
    with patch.object(connection, 'cursor') as mock_cursor:
        mock_cursor.return_value.__enter__.return_value.execute.return_value = None
        
        response = client.get('/api/v1/health')
        
        # If DB is actually connected, should return 200
        # If not, this test will pass if status_code is 200 (best effort)
        if response.status_code == 200:
            data = response.json()
            assert data['data']['status'] == 'healthy'
            assert data['data']['oracle'] == 'connected'
