"""Core views for health check and system status."""

from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint.
    
    Returns:
        Response matching FastAPI format:
        {
            "data": {
                "status": "healthy" | "degraded",
                "oracle": "connected" | "disconnected"
            }
        }
        Status code: 200 if healthy, 503 if degraded
    """
    try:
        # Test database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM DUAL")
            oracle_status = "connected"
            health_status = "healthy"
    except Exception:
        oracle_status = "disconnected"
        health_status = "degraded"
    
    # Format response with envelope (matching FastAPI format exactly)
    response_data = {
        "data": {
            "status": health_status,
            "oracle": oracle_status
        }
    }
    
    http_status = status.HTTP_200_OK if health_status == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return Response(response_data, status=http_status)
