"""Tests for catalog API endpoints.

Story 2.14: RBAC by action removed — access control now via profile permissions.
Story 8.1: Action stats endpoint for scorecards.
Tests GET /api/v1/catalog/actions returns published actions.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.main import app
from app.models.catalog import (
    ActionDetail,
    ActionEngine,
    ActionPlatform,
    ActionStatus,
    ActionResponse,
    ExecutionStep,
    ExecutionStepType,
    ConnectorType,
)


@pytest.fixture(autouse=True)
def clear_catalog_cache():
    """Clear catalog cache before each test."""
    from app.api.v1.catalog import _catalog_cache
    _catalog_cache.clear()
    yield
    _catalog_cache.clear()


@pytest.fixture
def client():
    """Async test client for FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def sample_published_action():
    """Sample published ActionResponse for catalog list. Story 2.23: category removed."""
    return ActionResponse(
        id=1,
        name="Create PDB Oracle",
        description="Creates a Pluggable Database",
        engine=ActionEngine.ORACLE,
        platform=ActionPlatform.AAP,
        parameters_schema={"type": "object"},
        impact_rules={"DEV": {"level": "low"}},
        status=ActionStatus.PUBLISHED,
        created_by=1,
        created_at=datetime(2026, 1, 28, 10, 0, 0),
        updated_at=None,
    )


class TestListCatalogActions:
    """Tests for GET /api/v1/catalog/actions. Story 2.14: RBAC by action removed."""

    @pytest.mark.asyncio
    async def test_list_catalog_actions_returns_published(self, client, sample_published_action):
        """Returns all published actions with execution_count (Story 3.1)."""
        with patch("app.api.v1.catalog.catalog_repository.list_catalog", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [
                {**sample_published_action.model_dump(), "execution_count": 5}
            ]

            response = await client.get("/api/v1/catalog/actions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 1
        assert data["data"][0]["status"] == "published"
        assert data["data"][0]["execution_count"] == 5
        mock_list.assert_called_once_with(
            status=ActionStatus.PUBLISHED,
            tags_filter=None,
            q=None,
            engine=None,
            environment=None,
            impact=None,
        )

    @pytest.mark.asyncio
    async def test_list_catalog_actions_filter_by_tags(self, client, sample_published_action):
        """GET /catalog/actions?tags=rac,dataguard passes tags_filter (Story 2.6, AC4)."""
        with patch("app.api.v1.catalog.catalog_repository.list_catalog", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [
                {**sample_published_action.model_dump(), "execution_count": 0}
            ]

            response = await client.get("/api/v1/catalog/actions?tags=rac,dataguard")

        assert response.status_code == status.HTTP_200_OK
        # Verify tags_filter passed to repository
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs.get("tags_filter") == ["rac", "dataguard"]

    @pytest.mark.asyncio
    async def test_list_catalog_actions_filter_by_category(self, client, sample_published_action):
        """GET /catalog/actions?category=provisioning filters by tag (Story 3.1, AC6)."""
        with patch("app.api.v1.catalog.catalog_repository.list_catalog", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [
                {**sample_published_action.model_dump(), "execution_count": 0}
            ]

            response = await client.get("/api/v1/catalog/actions?category=provisioning")

        assert response.status_code == status.HTTP_200_OK
        # Category should be passed as tags_filter
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs.get("tags_filter") == ["provisioning"]

    @pytest.mark.asyncio
    async def test_list_catalog_actions_includes_execution_count(self, client, sample_published_action):
        """GET /catalog/actions includes execution_count per action (Story 3.1, AC3)."""
        with patch("app.api.v1.catalog.catalog_repository.list_catalog", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [
                {**sample_published_action.model_dump(), "execution_count": 42}
            ]

            response = await client.get("/api/v1/catalog/actions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"][0]["execution_count"] == 42

    @pytest.mark.asyncio
    async def test_list_catalog_actions_query_params_q_engine_environment_impact(self, client, sample_published_action):
        """GET /catalog/actions accepts q, engine, environment, impact (Story 3.3, AC9)."""
        with patch("app.api.v1.catalog.catalog_repository.list_catalog", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [
                {**sample_published_action.model_dump(), "execution_count": 0}
            ]

            response = await client.get(
                "/api/v1/catalog/actions?q=oracle&engine=Oracle&environment=PROD&impact=high"
            )

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs.get("q") == "oracle"
        assert call_kwargs.get("engine") == "Oracle"
        assert call_kwargs.get("environment") == "PROD"
        assert call_kwargs.get("impact") == "high"

    @pytest.mark.asyncio
    async def test_list_catalog_actions_cache_key_includes_all_params(self, client, sample_published_action):
        """Cache key includes q, tags, category, engine, environment, impact (Story 3.3, AC9, NFR4)."""
        with patch("app.api.v1.catalog.catalog_repository.list_catalog", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [
                {**sample_published_action.model_dump(), "execution_count": 0}
            ]

            await client.get("/api/v1/catalog/actions?q=test&tags=a,b&category=c&engine=Oracle&environment=DEV&impact=low")
            call_kwargs = mock_list.call_args.kwargs
            assert call_kwargs.get("q") == "test"
            assert set(call_kwargs.get("tags_filter") or []) >= {"a", "b", "c"}
            assert call_kwargs.get("engine") == "Oracle"
            assert call_kwargs.get("environment") == "DEV"
            assert call_kwargs.get("impact") == "low"

    @pytest.mark.asyncio
    async def test_list_catalog_actions_rejects_invalid_environment(self, client):
        """GET /catalog/actions returns 400 for invalid environment parameter (Story 3.3, security)."""
        response = await client.get("/api/v1/catalog/actions?environment=PROD;DROP TABLE")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid environment parameter" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_catalog_actions_rejects_invalid_impact(self, client):
        """GET /catalog/actions returns 400 for invalid impact parameter (Story 3.3)."""
        response = await client.get("/api/v1/catalog/actions?impact=extreme")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid impact parameter" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_catalog_actions_accepts_valid_impact_values(self, client, sample_published_action):
        """GET /catalog/actions accepts low, medium, high, critical for impact (Story 3.3)."""
        with patch("app.api.v1.catalog.catalog_repository.list_catalog", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [{**sample_published_action.model_dump(), "execution_count": 0}]

            for impact_value in ["low", "medium", "high", "critical"]:
                response = await client.get(f"/api/v1/catalog/actions?impact={impact_value}")
                assert response.status_code == status.HTTP_200_OK


@pytest.fixture
def sample_action_detail():
    """Sample ActionDetail for catalog detail endpoint (Story 3.2, 3.4)."""
    return ActionDetail(
        id=1,
        name="Create PDB Oracle",
        description="Creates a Pluggable Database for Oracle 19c environments",
        engine=ActionEngine.ORACLE,
        platform=ActionPlatform.AAP,
        parameters_schema={
            "type": "object",
            "properties": {
                "pdb_name": {"type": "string"},
                "size_gb": {"type": "number"},
            },
            "required": ["pdb_name"],
        },
        impact_rules={"DEV": {"level": "low"}, "PROD": {"level": "high"}},
        default_impact_level=None,
        status=ActionStatus.PUBLISHED,
        created_by=1,
        created_at=datetime(2026, 1, 28, 10, 0, 0),
        updated_at=None,
        tags=["provisioning", "oracle"],
        execution_steps=[
            ExecutionStep(
                order=1,
                name="Create PDB",
                type=ExecutionStepType.EXECUTION,
                connector_type=ConnectorType.AAP,
            )
        ],
        change_type_config=None,
        documentation_md="# Create PDB\n\n## Overview\n\nThis action creates a **Pluggable Database**.\n\n```sql\nCREATE PLUGGABLE DATABASE pdb_name;\n```",
    )


class TestGetCatalogActionById:
    """Tests for GET /api/v1/catalog/actions/{id} (Story 3.2, AC1, AC6)."""

    @pytest.mark.asyncio
    async def test_get_action_by_id_returns_published_action(self, client, sample_action_detail):
        """GET /catalog/actions/{id} returns ActionDetail for published action (AC1, AC6)."""
        with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_action_detail

            response = await client.get("/api/v1/catalog/actions/1")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert data["data"]["id"] == 1
        assert data["data"]["name"] == "Create PDB Oracle"
        assert data["data"]["description"] == "Creates a Pluggable Database for Oracle 19c environments"
        assert data["data"]["tags"] == ["provisioning", "oracle"]
        assert data["data"]["parameters_schema"]["properties"]["pdb_name"]["type"] == "string"
        mock_get.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_get_action_by_id_returns_404_when_not_found(self, client):
        """GET /catalog/actions/{id} returns 404 when action does not exist (AC6)."""
        with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            response = await client.get("/api/v1/catalog/actions/999")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_get.assert_called_once_with(999)

    @pytest.mark.asyncio
    async def test_get_action_by_id_returns_404_for_draft_action(self, client, sample_action_detail):
        """GET /catalog/actions/{id} returns 404 for non-published actions (AC6)."""
        draft_action = sample_action_detail.model_copy(update={"status": ActionStatus.DRAFT})
        with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = draft_action

            response = await client.get("/api/v1/catalog/actions/1")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_action_by_id_returns_404_for_disabled_action(self, client, sample_action_detail):
        """GET /catalog/actions/{id} returns 404 for disabled actions (AC6)."""
        disabled_action = sample_action_detail.model_copy(update={"status": ActionStatus.DISABLED})
        with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = disabled_action

            response = await client.get("/api/v1/catalog/actions/1")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_action_by_id_with_rbac_allowed(self, client, sample_action_detail):
        """GET /catalog/actions/{id} returns action when user has RBAC permission (AC6)."""
        from app.api.deps import get_optional_user
        from app.models.auth import UserProfile
        from app.models.profile import CumulativePermissionsResponse

        user = UserProfile(
            id=1,
            username="test",
            display_name="Test User",
            profile="dba",
            cumulative_permissions=CumulativePermissionsResponse(
                actions_type="list",
                action_ids=[1, 2, 3],
                tag_patterns=[],
            ),
        )

        app.dependency_overrides[get_optional_user] = lambda: user
        try:
            with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = sample_action_detail

                response = await client.get("/api/v1/catalog/actions/1")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["data"]["id"] == 1
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    @pytest.mark.asyncio
    async def test_get_action_by_id_with_rbac_denied(self, client, sample_action_detail):
        """GET /catalog/actions/{id} returns 404 when user lacks RBAC permission (AC6)."""
        from app.api.deps import get_optional_user
        from app.models.auth import UserProfile
        from app.models.profile import CumulativePermissionsResponse

        user = UserProfile(
            id=1,
            username="test",
            display_name="Test User",
            profile="viewer",
            cumulative_permissions=CumulativePermissionsResponse(
                actions_type="list",
                action_ids=[99, 100],  # action 1 not in list
                tag_patterns=[],
            ),
        )

        app.dependency_overrides[get_optional_user] = lambda: user
        try:
            with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = sample_action_detail

                response = await client.get("/api/v1/catalog/actions/1")

            assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    @pytest.mark.asyncio
    async def test_get_action_by_id_with_rbac_tag_pattern_allowed(self, client, sample_action_detail):
        """GET /catalog/actions/{id} allowed when user has matching tag pattern (AC6)."""
        from app.api.deps import get_optional_user
        from app.models.auth import UserProfile
        from app.models.profile import CumulativePermissionsResponse

        user = UserProfile(
            id=1,
            username="test",
            display_name="Test User",
            profile="dba",
            cumulative_permissions=CumulativePermissionsResponse(
                actions_type="pattern",
                action_ids=[],
                tag_patterns=["oracle"],  # matches action tags
            ),
        )

        app.dependency_overrides[get_optional_user] = lambda: user
        try:
            with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = sample_action_detail

                response = await client.get("/api/v1/catalog/actions/1")

            assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    @pytest.mark.asyncio
    async def test_get_action_by_id_anonymous_user_allowed(self, client, sample_action_detail):
        """GET /catalog/actions/{id} works for anonymous users (no RBAC filter)."""
        with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_action_detail

            response = await client.get("/api/v1/catalog/actions/1")

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_get_action_by_id_with_rbac_all_actions(self, client, sample_action_detail):
        """GET /catalog/actions/{id} allowed when user has actions_type='all' (AC6)."""
        from app.api.deps import get_optional_user
        from app.models.auth import UserProfile
        from app.models.profile import CumulativePermissionsResponse

        user = UserProfile(
            id=1,
            username="admin",
            display_name="Admin User",
            profile="admin",
            cumulative_permissions=CumulativePermissionsResponse(
                actions_type="all",
                action_ids=[],
                tag_patterns=[],
            ),
        )

        app.dependency_overrides[get_optional_user] = lambda: user
        try:
            with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = sample_action_detail

                response = await client.get("/api/v1/catalog/actions/1")

            assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    @pytest.mark.asyncio
    async def test_get_action_by_id_returns_can_execute_true(self, client, sample_action_detail):
        """GET /catalog/actions/{id} returns can_execute=True when user has environments (AC3)."""
        from app.api.deps import get_optional_user
        from app.models.auth import UserProfile
        from app.models.profile import CumulativePermissionsResponse

        user = UserProfile(
            id=1,
            username="dba",
            display_name="DBA User",
            profile="dba",
            cumulative_permissions=CumulativePermissionsResponse(
                actions_type="all",
                action_ids=[],
                tag_patterns=[],
                environments=["DEV", "QUAL", "PROD"],
            ),
        )

        app.dependency_overrides[get_optional_user] = lambda: user
        try:
            with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = sample_action_detail

                response = await client.get("/api/v1/catalog/actions/1")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["can_execute"] is True
            assert data["allowed_environments"] == ["DEV", "QUAL", "PROD"]
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    @pytest.mark.asyncio
    async def test_get_action_by_id_returns_can_execute_false_no_environments(self, client, sample_action_detail):
        """GET /catalog/actions/{id} returns can_execute=False when user has no environments (AC3)."""
        from app.api.deps import get_optional_user
        from app.models.auth import UserProfile
        from app.models.profile import CumulativePermissionsResponse

        user = UserProfile(
            id=1,
            username="viewer",
            display_name="Viewer User",
            profile="viewer",
            cumulative_permissions=CumulativePermissionsResponse(
                actions_type="all",
                action_ids=[],
                tag_patterns=[],
                environments=[],  # No environments
            ),
        )

        app.dependency_overrides[get_optional_user] = lambda: user
        try:
            with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = sample_action_detail

                response = await client.get("/api/v1/catalog/actions/1")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["can_execute"] is False
            assert data["allowed_environments"] == []
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    @pytest.mark.asyncio
    async def test_get_action_by_id_anonymous_returns_can_execute_false(self, client, sample_action_detail):
        """GET /catalog/actions/{id} returns can_execute=False for anonymous users (AC3)."""
        with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_action_detail

            response = await client.get("/api/v1/catalog/actions/1")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["can_execute"] is False
        assert data["allowed_environments"] == []

    @pytest.mark.asyncio
    async def test_get_action_by_id_returns_documentation_md(self, client, sample_action_detail):
        """GET /catalog/actions/{id} returns documentation_md when present (Story 3.4, AC1, AC4)."""
        with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_action_detail

            response = await client.get("/api/v1/catalog/actions/1")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "documentation_md" in data["data"]
        assert data["data"]["documentation_md"] is not None
        assert "# Create PDB" in data["data"]["documentation_md"]
        assert "```sql" in data["data"]["documentation_md"]

    @pytest.mark.asyncio
    async def test_get_action_by_id_returns_null_documentation_md(self, client, sample_action_detail):
        """GET /catalog/actions/{id} returns null documentation_md when not set (Story 3.4, AC3)."""
        action_without_docs = sample_action_detail.model_copy(update={"documentation_md": None})
        with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = action_without_docs

            response = await client.get("/api/v1/catalog/actions/1")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "documentation_md" in data["data"]
        assert data["data"]["documentation_md"] is None


class TestListCatalogTags:
    """Tests for GET /api/v1/catalog/tags (Story 3.3, AC3, AC10)."""

    @pytest.mark.asyncio
    async def test_list_catalog_tags_returns_name_and_action_count(self, client):
        """GET /catalog/tags returns list of { name, action_count }."""
        with patch("app.api.v1.catalog.catalog_repository.list_tags_with_counts", new_callable=AsyncMock) as mock_tags:
            mock_tags.return_value = [
                {"name": "rac", "action_count": 5},
                {"name": "dataguard", "action_count": 2},
            ]

            response = await client.get("/api/v1/catalog/tags")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 2
        assert data["data"][0]["name"] == "rac"
        assert data["data"][0]["action_count"] == 5
        mock_tags.assert_called_once_with(action_ids_filter=None)

    @pytest.mark.asyncio
    async def test_list_catalog_tags_with_rbac_restricts_to_allowed_actions(self, client):
        """GET /catalog/tags with RBAC passes action_ids_filter (Story 3.3, AC10)."""
        from app.api.deps import get_optional_user
        from app.models.auth import UserProfile
        from app.models.profile import CumulativePermissionsResponse

        user = UserProfile(
            id=1,
            username="dba",
            display_name="DBA",
            profile="dba",
            cumulative_permissions=CumulativePermissionsResponse(
                actions_type="list",
                action_ids=[1, 2, 3],
                tag_patterns=[],
            ),
        )
        app.dependency_overrides[get_optional_user] = lambda: user
        try:
            with patch("app.api.v1.catalog.catalog_repository.list_catalog", new_callable=AsyncMock) as mock_list, \
                 patch("app.api.v1.catalog.catalog_repository.list_tags_with_counts", new_callable=AsyncMock) as mock_tags:
                mock_list.return_value = [{"id": 1, "tags": ["rac"]}, {"id": 2, "tags": ["rac"]}]
                mock_tags.return_value = [{"name": "rac", "action_count": 2}]

                response = await client.get("/api/v1/catalog/tags")

            assert response.status_code == status.HTTP_200_OK
            call_kwargs = mock_tags.call_args.kwargs
            assert call_kwargs.get("action_ids_filter") == [1, 2]
        finally:
            app.dependency_overrides.pop(get_optional_user, None)


class TestGetActionStats:
    """Tests for GET /api/v1/catalog/actions/{id}/stats (Story 8.1, AC4)."""

    @pytest.mark.asyncio
    async def test_get_action_stats_returns_stats(self, client, sample_action_detail):
        """GET /catalog/actions/{id}/stats returns stats for action with executions (AC1, AC4)."""
        with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.catalog.execution_repository.get_action_stats", new_callable=AsyncMock) as mock_stats:
            mock_get.return_value = sample_action_detail
            mock_stats.return_value = {
                "success_rate": 95.5,
                "avg_execution_time_ms": 5000,
                "total_executions": 100,
                "incidents_count": 5,
            }

            response = await client.get("/api/v1/catalog/actions/1/stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert data["data"]["success_rate"] == 95.5
        assert data["data"]["avg_execution_time_ms"] == 5000
        assert data["data"]["total_executions"] == 100
        assert data["data"]["incidents_count"] == 5

    @pytest.mark.asyncio
    async def test_get_action_stats_returns_null_for_no_executions(self, client, sample_action_detail):
        """GET /catalog/actions/{id}/stats returns null data when no executions (AC3)."""
        with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.catalog.execution_repository.get_action_stats", new_callable=AsyncMock) as mock_stats:
            mock_get.return_value = sample_action_detail
            mock_stats.return_value = None  # No executions

            response = await client.get("/api/v1/catalog/actions/1/stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"] is None

    @pytest.mark.asyncio
    async def test_get_action_stats_returns_404_for_nonexistent_action(self, client):
        """GET /catalog/actions/{id}/stats returns 404 when action does not exist."""
        with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            response = await client.get("/api/v1/catalog/actions/999/stats")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_action_stats_returns_404_for_draft_action(self, client, sample_action_detail):
        """GET /catalog/actions/{id}/stats returns 404 for non-published actions."""
        draft_action = sample_action_detail.model_copy(update={"status": ActionStatus.DRAFT})
        with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = draft_action

            response = await client.get("/api/v1/catalog/actions/1/stats")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_action_stats_with_rbac_denied(self, client, sample_action_detail):
        """GET /catalog/actions/{id}/stats returns 404 when user lacks RBAC permission."""
        from app.api.deps import get_optional_user
        from app.models.auth import UserProfile
        from app.models.profile import CumulativePermissionsResponse

        user = UserProfile(
            id=1,
            username="test",
            display_name="Test User",
            profile="viewer",
            cumulative_permissions=CumulativePermissionsResponse(
                actions_type="list",
                action_ids=[99, 100],  # action 1 not in list
                tag_patterns=[],
            ),
        )

        app.dependency_overrides[get_optional_user] = lambda: user
        try:
            with patch("app.api.v1.catalog.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = sample_action_detail

                response = await client.get("/api/v1/catalog/actions/1/stats")

            assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides.pop(get_optional_user, None)
