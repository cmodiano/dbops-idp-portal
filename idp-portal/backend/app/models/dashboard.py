"""Dashboard models for reporting API (Story 8.3, Story 8.4).

Pydantic models for new dashboard endpoints:
- TechnologyStats: Aggregated stats by database engine
- EnvironmentStats: Aggregated stats by environment
- DashboardFilters: Advanced filter parameters (Story 8.4)
- Response wrappers for API consistency
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator


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


class DashboardFilters(BaseModel):
    """Advanced filter parameters for dashboard endpoints (Story 8.4, AC7).

    Attributes:
        engine: Filter by database engine (e.g., 'aap', 'terraform')
        environment: Filter by environment (e.g., 'dev', 'staging', 'prod')
        tags: Filter by action tags (actions having any of these tags)
        status: Filter by execution status (e.g., 'COMPLETED', 'FAILED')
        from_date: Custom period start (inclusive)
        to_date: Custom period end (inclusive)
    """

    engine: str | None = Field(None, description="Filter by engine")
    environment: str | None = Field(None, description="Filter by environment")
    tags: list[str] | None = Field(None, description="Filter by action tags")
    status: str | None = Field(None, description="Filter by execution status")
    from_date: date | None = Field(None, description="Custom period start")
    to_date: date | None = Field(None, description="Custom period end")

    @model_validator(mode="after")
    def validate_date_range(self) -> "DashboardFilters":
        """Ensure from_date <= to_date if both are provided (Story 8.4, Task 1.2)."""
        if self.from_date is not None and self.to_date is not None:
            if self.from_date > self.to_date:
                msg = "from_date must be less than or equal to to_date"
                raise ValueError(msg)
        return self


class FilterOptionsResponse(BaseModel):
    """Response wrapper for GET /dashboard/filter-options (Story 8.4, Task 14)."""

    engines: list[str] = Field(default_factory=list, description="Available engines")
    environments: list[str] = Field(default_factory=list, description="Available environments")
    tags: list[str] = Field(default_factory=list, description="Available tags")
    statuses: list[str] = Field(default_factory=list, description="Available statuses")
