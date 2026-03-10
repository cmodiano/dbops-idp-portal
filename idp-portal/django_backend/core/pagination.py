"""Custom pagination for DRF."""
from __future__ import annotations

from typing import TypedDict

from django.db.models import QuerySet
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class PaginationInfo(TypedDict):
    """Pagination metadata."""
    page: int
    page_size: int
    total: int
    total_pages: int


class PaginationResult(TypedDict):
    """Result of paginate_queryset()."""
    items: list
    pagination: PaginationInfo


# Story 26.11 (AC1): Utilitaire pagination réutilisable
MAX_PAGE_SIZE = 1000  # Code Review: prevent unbounded queries via limit=999999


def paginate_queryset(
    queryset: QuerySet,
    offset: int,
    limit: int,
) -> PaginationResult:
    """
    Paginate a Django queryset with offset/limit and return standardized format.

    Args:
        queryset: Django queryset to paginate (unevaluated).
        offset: Starting position (0-indexed, must be >= 0).
        limit: Number of items per page (must be > 0).

    Returns:
        {
            'items': list,  # Queryset slice results (not serialized)
            'pagination': {
                'page': int,        # Page number (1-indexed)
                'page_size': int,   # Items per page (= limit)
                'total': int,       # Total items count
                'total_pages': int, # Total pages count (minimum 1)
            }
        }

    Raises:
        ValueError: If offset < 0 or limit <= 0.

    Examples:
        >>> qs = Execution.objects.all()  # 250 items total
        >>> result = paginate_queryset(qs, offset=0, limit=50)
        >>> result['pagination']
        {'page': 1, 'page_size': 50, 'total': 250, 'total_pages': 5}

        >>> result = paginate_queryset(qs, offset=100, limit=50)
        >>> result['pagination']
        {'page': 3, 'page_size': 50, 'total': 250, 'total_pages': 5}
    """
    # Code Review Fix (HIGH-1): Input validation to prevent ZeroDivisionError and negative offsets
    if offset < 0:
        raise ValueError(f"offset must be >= 0, got {offset}")
    if limit <= 0:
        raise ValueError(f"limit must be > 0, got {limit}")
    # Code Review: cap limit to prevent unbounded queries
    limit = min(limit, MAX_PAGE_SIZE)

    total = queryset.count()
    page = (offset // limit) + 1
    # Code Review Fix (MEDIUM-1): Ensure minimum 1 page even if empty queryset (UX consistency)
    total_pages = max(1, (total + limit - 1) // limit)

    items = list(queryset[offset: offset + limit])

    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": limit,
            "total": total,
            "total_pages": total_pages,
        },
    }


class CustomPageNumberPagination(PageNumberPagination):
    """
    Custom pagination format:
    {
        "data": [...],
        "pagination": {
            "page": 1,
            "page_size": 25,
            "total": 100,
            "total_pages": 4
        }
    }
    """
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 1000
    
    def get_paginated_response(self, data: list) -> Response:
        """Return paginated response."""
        assert self.page is not None, "paginate_queryset must be called first"
        return Response({
            "data": data,
            "pagination": {
                "page": self.page.number,
                "page_size": self.page.paginator.per_page,  # MEDIUM-2: actual page size, not class default
                "total": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages
            }
        })
