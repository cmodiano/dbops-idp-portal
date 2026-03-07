// === Admin Analytics Types (Story 8.2) ===

/** Executions count per engine (Story 8.2, AC1). */
export interface EngineExecutions {
  engine: string;
  count: number;
}

/** Executions count per user profile (Story 8.2, AC1). */
export interface ProfileExecutions {
  profile: string;
  count: number;
}

/** Weekly adoption trend point (Story 8.2, AC2). */
export interface WeeklyTrendPoint {
  week_start: string; // YYYY-MM-DD
  engine: string;
  count: number;
}

/** Admin analytics dashboard data (Story 8.2, AC1, AC4). */
export interface AdminAnalytics {
  total_published_actions: number;
  executions_by_engine: EngineExecutions[];
  executions_by_profile: ProfileExecutions[];
  adoption_trend: WeeklyTrendPoint[];
}

// === Reporting Dashboard Types (Story 8.3) ===

/** Executions aggregated by database engine (Story 8.3, AC3, AC7). */
export interface TechnologyStats {
  /** Database engine name (e.g., Oracle, PostgreSQL, N/A). */
  engine: string;
  /** Total execution count for this engine. */
  count: number;
  /** Success rate percentage (0-100), null if no finished executions. */
  success_rate: number | null;
}

/** Executions aggregated by environment (Story 8.3, AC4, AC7). */
export interface EnvironmentStats {
  /** Environment name (dev, staging, prod). */
  environment: string;
  /** Total execution count for this environment. */
  count: number;
  /** Success rate percentage (0-100), null if no finished executions. */
  success_rate: number | null;
}

// === Dashboard Advanced Filters Types (Story 8.4) ===

/** Status values for execution filter (Story 8.4, Task 8.2).
 * Includes all execution statuses including approval workflow statuses (Story 7.4). */
export type DashboardFilterStatus = 'PENDING' | 'SUBMITTED' | 'INTEGRATION_ERROR' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'PENDING_APPROVAL' | 'REJECTED';

/** Advanced filters for dashboard endpoints (Story 8.4, AC1, AC6, AC7). */
export interface DashboardFilters {
  /** Filter by database engine (e.g., 'aap', 'terraform'). */
  engine?: string;
  /** Filter by environment (e.g., 'dev', 'staging', 'prod'). */
  environment?: string;
  /** Filter by action tags (actions having any of these tags). */
  tags?: string[];
  /** Filter by execution status. */
  status?: DashboardFilterStatus;
  /** Custom period start (YYYY-MM-DD). */
  fromDate?: string;
  /** Custom period end (YYYY-MM-DD). */
  toDate?: string;
  /** Period in days (used when fromDate/toDate not provided). */
  days?: number;
}

/** Available filter options from API (Story 8.4, Task 14). */
export interface FilterOptions {
  /** Available database engines from published actions. */
  engines: string[];
  /** Used environments from executions. */
  environments: string[];
  /** All available tags. */
  tags: string[];
  /** All possible execution statuses. */
  statuses: string[];
}

// === Dashboard Export Types (Story 8.5) ===

/** Export format for dashboard reports (Story 8.5, AC1). */
export type ExportFormat = 'csv' | 'pdf';

// === Dashboard Comparison Types (Story 8.6) ===

/** Dimension for comparison analysis (Story 8.6, AC1, AC7). */
export type ComparisonDimension = 'technology' | 'environment' | 'period';

/** Metrics available for comparison (Story 8.6, AC2, AC7). */
export type ComparisonMetric = 'success_rate' | 'avg_time' | 'execution_count' | 'incident_count';

/** Statistics for one side of a comparison (Story 8.6, AC7). */
export interface ComparisonStats {
  /** Success rate percentage (0-100), null if no finished executions. */
  success_rate: number | null;
  /** Average execution time in seconds, null if no completed executions. */
  avg_time: number | null;
  /** Total execution count. */
  execution_count: number;
  /** Count of failed executions (incidents). */
  incident_count: number;
}

/** Result of a comparison between two values (Story 8.6, AC7). */
export interface ComparisonResult {
  /** Dimension being compared (technology, environment, period). */
  dimension: ComparisonDimension;
  /** First value being compared (label). */
  value1: string;
  /** Second value being compared (label). */
  value2: string;
  /** Statistics for the first value. */
  value1_stats: ComparisonStats;
  /** Statistics for the second value. */
  value2_stats: ComparisonStats;
  /** Percentage change for each metric ((value2 - value1) / value1 * 100). */
  deltas: Record<ComparisonMetric | string, number | null>;
}

/** Filters for comparison request (Story 8.6, AC1-AC4, AC7). */
export interface ComparisonFilters {
  /** Dimension to compare (technology, environment, period). */
  dimension: ComparisonDimension;
  /** First value to compare. */
  value1: string;
  /** Second value to compare. */
  value2: string;
  /** Metrics to include (all if not specified). */
  metrics?: ComparisonMetric[];
  /** Period in days (for technology/environment dimensions). */
  days?: number;
  /** Start date of first period (for period dimension). */
  period1Start?: string;
  /** End date of first period (for period dimension). */
  period1End?: string;
  /** Start date of second period (for period dimension). */
  period2Start?: string;
  /** End date of second period (for period dimension). */
  period2End?: string;
}

// === Stats Catalogue Admin Types (Story 60.1 / 60.3) ===

export interface StatsCatalogueByStatus {
  status: string;
  count: number;
}

export interface StatsCatalogueByItemType {
  item_type: string;
  count: number;
}

export interface StatsCatalogueByEngine {
  engine: string;
  count: number;
}

export interface StatsCatalogueByCategory {
  category: string | null;
  count: number;
}

export interface StatsCatalogueEvolutionPoint {
  week_start: string; // YYYY-MM-DD
  created_count: number;
  published_count: number;
}

export interface StatsCatalogueData {
  by_status: StatsCatalogueByStatus[];
  by_item_type: StatsCatalogueByItemType[];
  by_engine: StatsCatalogueByEngine[];
  by_category: StatsCatalogueByCategory[];
  evolution: StatsCatalogueEvolutionPoint[];
}

// === Stats Adoption Admin Types (Story 60.2 / 60.3) ===

export interface StatsAdoptionByProfile {
  profile: string;
  count: number;
}

export interface StatsAdoptionActiveUser {
  profile: string;
  user_count: number;
}

export interface StatsAdoptionTrendPoint {
  week_start: string; // YYYY-MM-DD
  profile: string;
  count: number;
}

export interface StatsAdoptionData {
  executions_by_profile: StatsAdoptionByProfile[];
  active_users_by_profile: StatsAdoptionActiveUser[];
  adoption_trend: StatsAdoptionTrendPoint[];
}

// === Stats Operations Types (Story 60.5 / 60.9) ===

export interface StatsOperationsActionItem {
  action_id: number;
  action_name: string;
  execution_count: number;
}

export interface StatsOperationsFailureItem {
  action_id: number;
  action_name: string;
  failure_count: number;
}

export interface StatsOperationsPlatformItem {
  platform: string;
  count: number;
}

export interface StatsOperationsData {
  avg_execution_time_s: number | null;
  top_actions_by_execution: StatsOperationsActionItem[];
  top_actions_by_failure: StatsOperationsFailureItem[];
  by_platform: StatsOperationsPlatformItem[];
}

// === Stats Approbations Types (Story 60.6 / 60.9) ===

export interface StatsApprobationsData {
  approved_count: number;
  rejected_count: number;
  approval_rate: number | null;
  avg_approval_delay_s: number | null;
}

// === Stats Planifiees Types (Story 60.7 / 60.9) ===

export interface StatsPlanifieesRecurrenceItem {
  pattern_type: string;
  count: number;
}

export interface StatsPlanifieesData {
  scheduled_count: number;
  manual_count: number;
  scheduled_rate: number | null;
  by_recurrence_type: StatsPlanifieesRecurrenceItem[];
}
