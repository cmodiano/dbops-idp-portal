export interface ApiResponse<T> {
  data: T;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

/** Pagination metadata aligned with DRF CustomPageNumberPagination response format. */
export interface PaginationInfo {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}
