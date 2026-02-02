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


# === Export Models (Story 8.5) ===


class DashboardExportPeriodInfo(BaseModel):
    """Period information for export report (Story 8.5, Task 1.3).

    Attributes:
        from_date: Start date of the period (YYYY-MM-DD)
        to_date: End date of the period (YYYY-MM-DD)
        days: Number of days in the period
    """

    from_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    to_date: str = Field(..., description="End date (YYYY-MM-DD)")
    days: int = Field(..., ge=1, description="Number of days in period")


class DashboardExportFiltersInfo(BaseModel):
    """Filters applied to export report (Story 8.5, Task 1.2).

    Documents which filters were applied when generating the export.

    Attributes:
        engine: Filter by database engine
        environment: Filter by environment
        tags: Filter by action tags
        status: Filter by execution status
        from_date: Custom period start
        to_date: Custom period end
    """

    engine: str | None = Field(None, description="Engine filter")
    environment: str | None = Field(None, description="Environment filter")
    tags: list[str] | None = Field(None, description="Tags filter")
    status: str | None = Field(None, description="Status filter")
    from_date: str | None = Field(None, description="Custom period start")
    to_date: str | None = Field(None, description="Custom period end")

    def to_display_string(self) -> str:
        """Convert filters to human-readable string for reports."""
        parts = []
        if self.engine:
            parts.append(f"Moteur: {self.engine}")
        if self.environment:
            parts.append(f"Environnement: {self.environment}")
        if self.tags:
            parts.append(f"Tags: {', '.join(self.tags)}")
        if self.status:
            parts.append(f"Statut: {self.status}")
        if self.from_date:
            parts.append(f"Du: {self.from_date}")
        if self.to_date:
            parts.append(f"Au: {self.to_date}")
        return ", ".join(parts) if parts else "Aucun"


class DashboardExportTechnologyStats(BaseModel):
    """Technology stats for export (Story 8.5, Task 1.1).

    Extended version of TechnologyStats with success/failed counts.
    """

    engine: str = Field(..., description="Database engine name")
    count: int = Field(..., ge=0, description="Total execution count")
    success: int = Field(..., ge=0, description="Successful executions")
    failed: int = Field(..., ge=0, description="Failed executions")
    success_rate: float | None = Field(None, ge=0, le=100, description="Success rate percentage")


class DashboardExportEnvironmentStats(BaseModel):
    """Environment stats for export (Story 8.5, Task 1.1).

    Extended version of EnvironmentStats with success/failed counts.
    """

    environment: str = Field(..., description="Environment name")
    count: int = Field(..., ge=0, description="Total execution count")
    success: int = Field(..., ge=0, description="Successful executions")
    failed: int = Field(..., ge=0, description="Failed executions")
    success_rate: float | None = Field(None, ge=0, le=100, description="Success rate percentage")


class DashboardExportTimeSeriesPoint(BaseModel):
    """Time series point for export (Story 8.5, Task 1.1)."""

    date: str = Field(..., description="Date (YYYY-MM-DD)")
    success: int = Field(..., ge=0, description="Successful executions")
    failed: int = Field(..., ge=0, description="Failed executions")


class DashboardExportData(BaseModel):
    """Complete dashboard export data (Story 8.5, Task 1.1).

    Contains all data needed for CSV and PDF exports:
    - Period information
    - Applied filters
    - Global statistics
    - Stats by technology
    - Stats by environment
    - Time series trends

    Attributes:
        period_info: Period covered by the report
        filters_applied: Filters used when generating the report
        stats: Global dashboard statistics
        stats_by_technology: Breakdown by database engine
        stats_by_environment: Breakdown by environment
        timeseries: Daily trends over the period
    """

    period_info: DashboardExportPeriodInfo
    filters_applied: DashboardExportFiltersInfo
    stats: DashboardStatsData
    stats_by_technology: list[DashboardExportTechnologyStats]
    stats_by_environment: list[DashboardExportEnvironmentStats]
    timeseries: list[DashboardExportTimeSeriesPoint]


# === Comparison Models (Story 8.6) ===

from enum import Enum


class ComparisonDimension(str, Enum):
    """Dimension for comparison analysis (Story 8.6, AC1, AC7).

    Defines what type of comparison the user wants to perform.
    """

    TECHNOLOGY = "technology"
    ENVIRONMENT = "environment"
    PERIOD = "period"


class ComparisonMetric(str, Enum):
    """Metrics available for comparison (Story 8.6, AC2, AC7).

    Defines which metrics can be compared across dimensions.
    """

    SUCCESS_RATE = "success_rate"
    AVG_TIME = "avg_time"
    EXECUTION_COUNT = "execution_count"
    INCIDENT_COUNT = "incident_count"


class ComparisonStats(BaseModel):
    """Statistics for one side of a comparison (Story 8.6, AC7).

    Attributes:
        success_rate: Success rate percentage (0-100), None if no finished executions
        avg_time: Average execution time in seconds, None if no completed executions
        execution_count: Total execution count
        incident_count: Count of failed executions (incidents)
    """

    success_rate: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Success rate percentage (COMPLETED / (COMPLETED + FAILED) * 100)",
    )
    avg_time: float | None = Field(
        None,
        ge=0,
        description="Average execution time in seconds",
    )
    execution_count: int = Field(..., ge=0, description="Total execution count")
    incident_count: int = Field(..., ge=0, description="Count of failed executions")


class ComparisonResult(BaseModel):
    """Result of a comparison between two values (Story 8.6, AC7).

    Attributes:
        dimension: The dimension being compared (technology, environment, period)
        value1: First value being compared
        value2: Second value being compared
        value1_stats: Statistics for the first value
        value2_stats: Statistics for the second value
        deltas: Percentage change for each metric ((value2 - value1) / value1 * 100)
    """

    dimension: ComparisonDimension = Field(..., description="Dimension being compared")
    value1: str = Field(..., description="First value being compared")
    value2: str = Field(..., description="Second value being compared")
    value1_stats: ComparisonStats = Field(..., description="Statistics for value1")
    value2_stats: ComparisonStats = Field(..., description="Statistics for value2")
    deltas: dict[str, float | None] = Field(
        ...,
        description="Percentage change for each metric (None if division by zero)",
    )


class ComparisonResponse(BaseModel):
    """Response wrapper for GET /dashboard/compare (Story 8.6, AC7)."""

    data: ComparisonResult
