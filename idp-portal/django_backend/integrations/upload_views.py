"""
Views for integration icon upload endpoint.
"""

import uuid
import logging
from pathlib import Path
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from core.permissions import DBOPSProfilePermission
from core.exceptions import BadRequestError, InvalidStateError

logger = logging.getLogger(__name__)


class UploadIconView(APIView):
    """
    POST /admin/integrations/upload-icon - Upload integration icon.
    """
    parser_classes = [MultiPartParser]
    permission_classes = [IsAuthenticated, DBOPSProfilePermission]
    
    def post(self, request):
        """
        Upload integration icon file.
        
        Accepts multipart/form-data with image file (PNG, JPEG, SVG).
        Validates MIME type and size (max 2MB).
        Stores file locally in STATIC_ROOT/icons/ with unique UUID filename.
        
        Returns:
            HTTP 201 with {"data": {"icon_url": "/static/icons/{uuid}.{ext}"}}
            HTTP 400 if validation fails (invalid MIME type, size > 2MB, no file)
        """
        file = request.FILES.get('file')
        if not file:
            raise BadRequestError(
                code="NO_FILE",
                message="Fichier requis",
                details={}
            )
        
        # Validate MIME type
        allowed_mime_types = {'image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml'}
        if file.content_type not in allowed_mime_types:
            raise InvalidStateError(
                code="INVALID_FILE_TYPE",
                message=f"Type MIME invalide: {file.content_type}. Acceptés: PNG, JPEG, SVG.",
                details={
                    "content_type": file.content_type,
                    "allowed": list(allowed_mime_types)
                }
            )
        
        # Validate size (2MB max)
        MAX_ICON_SIZE_MB = 2
        MAX_ICON_SIZE_BYTES = MAX_ICON_SIZE_MB * 1024 * 1024
        if file.size > MAX_ICON_SIZE_BYTES:
            raise InvalidStateError(
                code="FILE_TOO_LARGE",
                message=f"Fichier trop volumineux: {file.size} bytes. Maximum: {MAX_ICON_SIZE_MB}MB.",
                details={
                    "size_bytes": file.size,
                    "max_bytes": MAX_ICON_SIZE_BYTES
                }
            )
        
        # Generate unique filename with UUID
        file_ext = Path(file.name).suffix or '.png'
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        
        # Create static/icons directory if doesn't exist
        static_root = getattr(settings, 'STATIC_ROOT', None)
        if not static_root:
            static_root = Path(settings.BASE_DIR) / 'static'
        else:
            static_root = Path(static_root)
        
        icons_dir = static_root / 'icons'
        icons_dir.mkdir(parents=True, exist_ok=True)
        
        # Write file to disk with error handling
        icon_path = icons_dir / unique_filename
        try:
            with open(icon_path, 'wb') as f:
                for chunk in file.chunks():
                    f.write(chunk)
        except OSError as e:
            logger.error(
                "icon_upload_failed",
                extra={
                    "error": str(e),
                    "icon_path": str(icon_path),
                    "file_size": file.size
                }
            )
            raise InvalidStateError(
                code="UPLOAD_FAILED",
                message=f"Échec de l'upload du fichier: {str(e)}",
                details={
                    "icon_path": str(icon_path),
                    "error_type": type(e).__name__
                }
            )
        
        # Return relative URL for frontend use
        icon_url = f"/static/icons/{unique_filename}"
        return Response(
            {'data': {'icon_url': icon_url}},
            status=status.HTTP_201_CREATED
        )
