"""Dashboard models for reporting API (Story 8.3).

Pydantic models for new dashboard endpoints:
- TechnologyStats: Aggregated stats by database engine
- EnvironmentStats: Aggregated stats by environment
- Response wrappers for API consistency
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TechnologyStats(BaseModel):
    """Aggregated execution statistics per database engine (Story 8.3, AC3).

    Attributes:
        engine: Database engine name (e.g., Oracle, PostgreSQL, N/A)
        count: Total execution count for this engine
        success_rate: Success rate as percentage (0-100), None if no finished executions
    """

    engine: str = Field(..., description="Database engine name")
    count: int = Field(..., ge=0, description="Total execution count")
    success_rate: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Success rate percentage (COMPLETED / (COMPLETED + FAILED) * 100)",
    )


class EnvironmentStats(BaseModel):
    """Aggregated execution statistics per environment (Story 8.3, AC4).

    Attributes:
        environment: Environment name (dev, staging, prod)
        count: Total execution count for this environment
        success_rate: Success rate as percentage (0-100), None if no finished executions
    """

    environment: str = Field(..., description="Environment name (dev, staging, prod)")
    count: int = Field(..., ge=0, description="Total execution count")
    success_rate: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Success rate percentage (COMPLETED / (COMPLETED + FAILED) * 100)",
    )


class DashboardStatsByTechnologyResponse(BaseModel):
    """Response wrapper for GET /dashboard/stats-by-technology (Story 8.3, AC7)."""

    data: list[TechnologyStats]


class DashboardStatsByEnvironmentResponse(BaseModel):
    """Response wrapper for GET /dashboard/stats-by-environment (Story 8.3, AC7)."""

    data: list[EnvironmentStats]


class DashboardStatsData(BaseModel):
    """Dashboard statistics (Story 5.1, AC1, AC4; Story 8.3, AC2).

    Extends the existing stats model to ensure consistency.
    """

    executions_jour: int = Field(..., ge=0, description="Executions created today")
    taux_succes_pct: float = Field(
        ...,
        ge=0,
        le=100,
        description="Success rate percentage over selected period",
    )
    executions_en_cours: int = Field(..., ge=0, description="Currently running executions")
    executions_en_erreur: int = Field(..., ge=0, description="Failed executions in period")


class DashboardStatsResponse(BaseModel):
    """Response wrapper for GET /dashboard/stats (Story 5.1, Story 8.3)."""

    data: DashboardStatsData
