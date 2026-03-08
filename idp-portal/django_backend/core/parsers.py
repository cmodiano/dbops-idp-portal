"""
Shared DRF parsers and request helpers for CaC endpoints (Story 64.8).
"""

from collections.abc import Mapping
from typing import Any, cast

from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser
from rest_framework.request import Request


class YAMLParser(BaseParser):
    """Accept application/x-yaml raw body."""
    media_type = 'application/x-yaml'

    def parse(self, stream: Any, media_type: str | None = None, parser_context: Mapping[str, Any] | None = None) -> Any:
        try:
            return stream.read().decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ParseError(f"Le contenu YAML doit être encodé en UTF-8 : {exc}") from exc


def extract_yaml_content(request: Request) -> bytes | None:
    """
    Extract YAML content bytes from request (multipart file OR raw YAML body).

    Returns bytes or None if no content found.
    Propagates IO errors rather than swallowing them silently.
    """
    if 'file' in request.FILES:
        return cast(bytes, request.FILES['file'].read())
    # request.data may be a raw string when YAMLParser is used
    data: Any = request.data
    if data and isinstance(data, str) and data.strip():
        return cast(bytes, data.encode('utf-8'))
    return None
