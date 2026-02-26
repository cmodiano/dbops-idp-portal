"""
Views for integration icon upload endpoint.
Story 30.5 — SEC-5/SEC-6/SEC-10: Extension allowlist, magic bytes validation, SVG sanitization.
"""

import os
import re
import uuid
import structlog
from pathlib import Path
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from core.permissions import DBOPSProfilePermission
from core.exceptions import BadRequestError, InvalidStateError

import puremagic
from defusedxml import ElementTree as DefusedET  # type: ignore[import-untyped]
from xml.etree.ElementTree import Element

logger = structlog.get_logger(__name__)

# SEC-5: Extension allowlist for icon uploads
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.svg', '.gif'}

# SEC-10: Mapping of allowed MIME types to expected magic byte signatures
ALLOWED_MIME_TYPES = {
    'image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml', 'image/gif',
}

# SEC-6: SVG event handler attributes to strip (XSS prevention)
SVG_EVENT_HANDLER_RE = re.compile(r'^on\w+', re.IGNORECASE)

# SVG namespaces
SVG_NS = 'http://www.w3.org/2000/svg'
XLINK_NS = 'http://www.w3.org/1999/xlink'


def sanitize_svg(svg_bytes: bytes) -> bytes:
    """
    Remove dangerous elements and attributes from SVG content.

    Strips:
    - <script> tags (any namespace)
    - Event handler attributes (onclick, onerror, onload, etc.)
    - <style> tags containing JavaScript
    - xlink:href with javascript: protocol
    - href with javascript: protocol

    Args:
        svg_bytes: Raw SVG file content

    Returns:
        Sanitized SVG bytes

    Raises:
        InvalidStateError: If SVG cannot be parsed (malformed XML)
    """
    try:
        root = DefusedET.fromstring(svg_bytes)
    except Exception as e:  # noqa: BLE001 — logged-and-wrapped: XML parsing can raise various errors, wrapped in InvalidStateError
        raise InvalidStateError(
            code="INVALID_SVG",
            message="Fichier SVG invalide ou malformé",
            details={"error": str(e)}
        )

    _strip_element_recursive(root)

    # Re-serialize
    from xml.etree.ElementTree import tostring
    return tostring(root, encoding='unicode').encode('utf-8')


def _strip_element_recursive(element: Element) -> None:
    """Recursively strip dangerous elements and attributes."""
    # Remove <script> tags (with or without namespace)
    children_to_remove = []
    for child in element:
        tag = child.tag if isinstance(child.tag, str) else ''
        local_tag = tag.split('}')[-1] if '}' in tag else tag
        if local_tag.lower() == 'script':
            children_to_remove.append(child)
        elif local_tag.lower() == 'style':
            # Remove <style> if it contains javascript
            if child.text and 'javascript' in child.text.lower():
                children_to_remove.append(child)

    for child in children_to_remove:
        element.remove(child)

    # Remove event handler attributes
    attrs_to_remove = []
    for attr_name in element.attrib:
        local_attr = attr_name.split('}')[-1] if '}' in attr_name else attr_name
        if SVG_EVENT_HANDLER_RE.match(local_attr):
            attrs_to_remove.append(attr_name)
        # Strip javascript: protocol in href/xlink:href
        if local_attr.lower() in ('href', 'xlink:href'):
            value = element.attrib[attr_name].strip()
            if value.lower().startswith('javascript:'):
                attrs_to_remove.append(attr_name)

    for attr_name in attrs_to_remove:
        del element.attrib[attr_name]

    # Recurse into children
    for child in element:
        _strip_element_recursive(child)


class UploadIconView(APIView):
    """
    POST /admin/integrations/upload-icon - Upload integration icon.
    """
    parser_classes = [MultiPartParser]
    permission_classes = [IsAuthenticated, DBOPSProfilePermission]

    def post(self, request):
        """
        Upload integration icon file.

        Validates:
        - File presence
        - Extension allowlist (SEC-5)
        - MIME type
        - File size (max 2MB)
        - Magic bytes vs declared MIME (SEC-10)
        - SVG sanitization against XSS (SEC-6)

        Returns:
            HTTP 201 with {"data": {"icon_url": "/static/icons/{uuid}.{ext}"}}
            HTTP 400 if validation fails
        """
        try:
            return self._do_upload(request)
        except (BadRequestError, InvalidStateError):
            raise
        except Exception as e:  # noqa: BLE001 — logged-and-wrapped: unexpected upload error wrapped in InvalidStateError
            logger.exception(
                "icon_upload_unexpected_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise InvalidStateError(
                code="UPLOAD_FAILED",
                message="Échec de l'upload de l'icône. Vérifiez le fichier ou les droits d'écriture du serveur.",
                details={"error_type": type(e).__name__},
            )

    def _do_upload(self, request):
        """Perform icon upload validation and file write."""
        file = request.FILES.get('file')
        if not file:
            raise BadRequestError(
                code="NO_FILE",
                message="Fichier requis",
                details={}
            )

        # SEC-5: Validate extension against allowlist
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise BadRequestError(
                code="INVALID_EXTENSION",
                message=f"Extension de fichier non autorisée. Extensions acceptées: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                details={
                    "extension": ext,
                    "allowed": sorted(ALLOWED_EXTENSIONS),
                }
            )

        # Validate MIME type
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise InvalidStateError(
                code="INVALID_FILE_TYPE",
                message=f"Type MIME invalide: {file.content_type}. Acceptés: PNG, JPEG, SVG, GIF.",
                details={
                    "content_type": file.content_type,
                    "allowed": sorted(ALLOWED_MIME_TYPES)
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

        # SEC-10: Validate magic bytes against declared MIME type
        file_header = file.read(2048)
        file.seek(0)

        is_svg = ext == '.svg' or file.content_type == 'image/svg+xml'

        if not is_svg:
            # Binary image — validate magic bytes
            try:
                detected_mime = puremagic.from_string(file_header, mime=True)
            except puremagic.PureError:
                detected_mime = None

            if not detected_mime or detected_mime not in ALLOWED_MIME_TYPES:
                logger.warning(
                    "upload_magic_bytes_mismatch",
                    declared_mime=file.content_type,
                    detected_mime=detected_mime,
                    upload_filename=file.name,
                )
                raise BadRequestError(
                    code="MAGIC_BYTES_MISMATCH",
                    message="Le contenu du fichier ne correspond pas à une image valide",
                    details={
                        "declared_mime": file.content_type,
                        "detected_mime": detected_mime,
                    }
                )

        # SEC-6: SVG sanitization against XSS
        if is_svg:
            file_content = file.read()
            file.seek(0)
            sanitized_content = sanitize_svg(file_content)
        else:
            sanitized_content = None

        # Generate unique filename with UUID
        unique_filename = f"{uuid.uuid4()}{ext}"

        # Create static/icons directory if doesn't exist
        static_root = getattr(settings, 'STATIC_ROOT', None)
        if not static_root:
            static_root = Path(settings.BASE_DIR) / 'static'
        else:
            static_root = Path(static_root)

        icons_dir = static_root / 'icons'
        try:
            icons_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(
                "icon_upload_dir_failed",
                error=str(e),
                icons_dir=str(icons_dir),
            )
            raise InvalidStateError(
                code="UPLOAD_FAILED",
                message="Impossible de créer le répertoire des icônes. Vérifiez les droits d'écriture du serveur.",
                details={"error_type": type(e).__name__},
            )

        # Write file to disk with error handling
        icon_path = icons_dir / unique_filename

        # SEC-14: Defense-in-depth — verify path stays inside icons_dir (path traversal prevention)
        if not icon_path.resolve().is_relative_to(icons_dir.resolve()):
            logger.error(
                "icon_upload_path_traversal",
                icon_path=str(icon_path.resolve()),
                icons_dir=str(icons_dir.resolve()),
            )
            raise BadRequestError(
                code="PATH_TRAVERSAL_DETECTED",
                message="Chemin d'écriture invalide — tentative de path traversal détectée.",
                details={},
            )

        try:
            with open(icon_path, 'wb') as f:
                if sanitized_content is not None:
                    # Write sanitized SVG
                    f.write(sanitized_content)
                else:
                    # Write original binary image
                    for chunk in file.chunks():
                        f.write(chunk)
        except OSError as e:
            logger.error(
                "icon_upload_failed",
                error=str(e),
                icon_path=str(icon_path),
                file_size=file.size,
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
