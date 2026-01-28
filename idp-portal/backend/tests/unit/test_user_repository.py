"""Tests for user repository contract — signatures and async verification."""

import inspect
from app.repositories import user_repository


def test_get_by_username_is_async():
    """Verify get_by_username is an async function."""
    assert inspect.iscoroutinefunction(user_repository.get_by_username)


def test_create_or_update_is_async():
    """Verify create_or_update is an async function."""
    assert inspect.iscoroutinefunction(user_repository.create_or_update)


def test_get_by_username_signature():
    """Verify get_by_username accepts username parameter."""
    sig = inspect.signature(user_repository.get_by_username)
    assert "username" in sig.parameters


def test_create_or_update_signature():
    """Verify create_or_update accepts required parameters."""
    sig = inspect.signature(user_repository.create_or_update)
    params = list(sig.parameters.keys())
    assert "username" in params
    assert "display_name" in params
    assert "profile" in params
    assert "saml_subject" in params


# Story 1.3 — new repository functions

def test_get_by_id_is_async():
    """Verify get_by_id is an async function."""
    assert inspect.iscoroutinefunction(user_repository.get_by_id)


def test_get_by_id_signature():
    """Verify get_by_id accepts user_id parameter."""
    sig = inspect.signature(user_repository.get_by_id)
    assert "user_id" in sig.parameters


def test_get_user_permissions_is_async():
    """Verify get_user_permissions is an async function."""
    assert inspect.iscoroutinefunction(user_repository.get_user_permissions)


def test_get_user_permissions_signature():
    """Verify get_user_permissions accepts user_id parameter."""
    sig = inspect.signature(user_repository.get_user_permissions)
    assert "user_id" in sig.parameters


def test_has_permission_is_async():
    """Verify has_permission is an async function."""
    assert inspect.iscoroutinefunction(user_repository.has_permission)


def test_has_permission_signature():
    """Verify has_permission accepts user_id, action_id, environment parameters."""
    sig = inspect.signature(user_repository.has_permission)
    params = list(sig.parameters.keys())
    assert "user_id" in params
    assert "action_id" in params
    assert "environment" in params
