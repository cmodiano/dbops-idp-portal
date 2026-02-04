"""
Custom pagination for DRF to match FastAPI format.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class CustomPageNumberPagination(PageNumberPagination):
    """
    Custom pagination that matches FastAPI format:
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
    
    def get_paginated_response(self, data):
        """Return paginated response in FastAPI format."""
        return Response({
            "data": data,
            "pagination": {
                "page": self.page.number,
                "page_size": self.page_size,
                "total": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages
            }
        })
