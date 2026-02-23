"""
Tests for _resolve_user_names batch query optimization (Story 30.9, PERF-1).

Verifies:
- Batch query for non-numeric user IDs (1 query instead of N)
- Backward compatibility with numeric user IDs
- Correct mapping user_id -> display_name
- Edge cases: empty list, mixed IDs, unknown users

LIMITATION: These are unit tests with mocked User.objects. They verify batch query logic
but NOT actual DB behavior with existing User data.

TODO: Add integration test with real DB fixtures to verify compatibility with production schema.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock


from audit.views import _resolve_user_names


def _make_user(*, id: int = 1, username: str = "alice", display_name: str | None = None):
    """Create a mock User object."""
    u = MagicMock()
    u.id = id
    u.username = username
    u.display_name = display_name
    return u


class TestResolveUserNamesOptimized:
    """Tests for _resolve_user_names batch optimization (PERF-1)."""

    def test_empty_list_returns_empty(self):
        result = _resolve_user_names([])
        assert result == {}

    @patch("audit.views.User.objects")
    def test_numeric_ids_batch_query(self, mock_user_objects):
        """Numeric IDs are resolved via filter(id__in=...) — 1 query."""
        user1 = _make_user(id=10, username="bob", display_name="Bob D.")
        user2 = _make_user(id=20, username="carol", display_name="Carol X.")

        mock_qs = MagicMock()
        mock_qs.only.return_value = [user1, user2]
        mock_user_objects.filter.return_value = mock_qs

        result = _resolve_user_names(["10", "20"])
        assert result == {"10": "Bob D.", "20": "Carol X."}
        mock_user_objects.filter.assert_called_once_with(id__in=[10, 20])

    @patch("audit.views.User.objects")
    def test_non_numeric_ids_batch_query(self, mock_user_objects):
        """Non-numeric IDs are resolved via filter(username__in=...) — 1 query instead of N."""
        user_alice = _make_user(id=1, username="alice", display_name="Alice W.")
        user_bob = _make_user(id=2, username="bob", display_name="Bob D.")

        # filter(username__in=...) call
        mock_qs_username = MagicMock()
        mock_qs_username.only.return_value = [user_alice, user_bob]
        mock_user_objects.filter.return_value = mock_qs_username

        result = _resolve_user_names(["alice", "bob"])

        assert result == {"alice": "Alice W.", "bob": "Bob D."}
        # Should be called once with username__in, NOT once per user
        mock_user_objects.filter.assert_called_once_with(username__in=["alice", "bob"])

    @patch("audit.views.User.objects")
    def test_mixed_numeric_and_non_numeric(self, mock_user_objects):
        """Mixed IDs: numeric via id__in, non-numeric via username__in — 2 queries total."""
        user_by_id = _make_user(id=42, username="user42", display_name="User 42")
        user_by_name = _make_user(id=7, username="admin_user", display_name="Admin")

        mock_qs_id = MagicMock()
        mock_qs_id.only.return_value = [user_by_id]
        mock_qs_name = MagicMock()
        mock_qs_name.only.return_value = [user_by_name]

        # First call: filter(id__in=[42]), Second call: filter(username__in=["admin_user"])
        mock_user_objects.filter.side_effect = [mock_qs_id, mock_qs_name]

        result = _resolve_user_names(["42", "admin_user"])
        assert result == {"42": "User 42", "admin_user": "Admin"}
        assert mock_user_objects.filter.call_count == 2

    @patch("audit.views.User.objects")
    def test_unknown_users_fallback_to_uid(self, mock_user_objects):
        """Unknown user IDs should fall back to the raw UID string."""
        mock_qs = MagicMock()
        mock_qs.only.return_value = []
        mock_user_objects.filter.return_value = mock_qs

        result = _resolve_user_names(["unknown_user"])
        assert result == {"unknown_user": "unknown_user"}

    @patch("audit.views.User.objects")
    def test_display_name_fallback_to_username(self, mock_user_objects):
        """If display_name is empty, fallback to username."""
        user = _make_user(id=1, username="alice", display_name=None)
        mock_qs = MagicMock()
        mock_qs.only.return_value = [user]
        mock_user_objects.filter.return_value = mock_qs

        result = _resolve_user_names(["alice"])
        assert result["alice"] == "alice"

    @patch("audit.views.User.objects")
    def test_no_n_plus_1_queries(self, mock_user_objects):
        """With 50 non-numeric IDs, only 1 query is made (not 50)."""
        usernames = [f"user_{i}" for i in range(50)]
        users = [_make_user(id=i, username=f"user_{i}", display_name=f"User {i}") for i in range(50)]

        mock_qs = MagicMock()
        mock_qs.only.return_value = users
        mock_user_objects.filter.return_value = mock_qs

        result = _resolve_user_names(usernames)

        assert len(result) == 50
        # Key assertion: only 1 call to filter, not 50
        mock_user_objects.filter.assert_called_once_with(username__in=usernames)

    @patch("audit.views.User.objects")
    def test_numeric_ids_not_found_fallback(self, mock_user_objects):
        """Numeric IDs not found in DB should fall back to the raw string."""
        mock_qs = MagicMock()
        mock_qs.only.return_value = []
        mock_user_objects.filter.return_value = mock_qs

        result = _resolve_user_names(["999"])
        assert result == {"999": "999"}
