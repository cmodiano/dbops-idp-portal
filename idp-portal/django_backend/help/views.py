import re

import structlog
import yaml
from pathlib import Path

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from core.exceptions import NotFoundError
from core.middleware import get_correlation_id
from help.topics import HELP_TOPICS, HELP_DIR

logger = structlog.get_logger(__name__)

_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n(.*)', re.DOTALL)


def _parse_help_file(path: Path) -> tuple[str, str]:
    content = path.read_text(encoding='utf-8')
    m = _FRONTMATTER_RE.match(content)
    if m:
        # HELP-MED-01: Protéger yaml.safe_load contre un frontmatter YAML malformé.
        # Un bloc ---...--- détecté mais invalide lèverait yaml.YAMLError → 500 non intentionnel.
        # Fallback sur meta={} (traitement comme Markdown pur) en cas d'erreur YAML.
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            logger.warning(
                "help_frontmatter_yaml_error",
                path=str(path),
            )
            meta = {}
        short: str = str(meta.get('short', ''))
        markdown: str = m.group(2).strip()
    else:
        lines = content.strip().split('\n')
        first = next((line.lstrip('#').strip() for line in lines if line.strip()), '')
        short = first[:200]
        markdown = content.strip()
    return short, markdown


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_help_topic(request: Request, topic_id: str) -> Response:
    correlation_id = get_correlation_id()

    if topic_id not in HELP_TOPICS:
        logger.warning(
            "help_topic_not_found",
            topic_id=topic_id,
            correlation_id=correlation_id,
        )
        raise NotFoundError(message="Topic d'aide inconnu")

    file_path = HELP_DIR / HELP_TOPICS[topic_id]
    if not file_path.exists():
        logger.warning(
            "help_file_missing",
            topic_id=topic_id,
            file=str(file_path),
            correlation_id=correlation_id,
        )
        raise NotFoundError(message="Fichier d'aide introuvable")

    short, markdown = _parse_help_file(file_path)

    logger.info(
        "help_topic_served",
        topic_id=topic_id,
        short_len=len(short),
        markdown_len=len(markdown),
        correlation_id=correlation_id,
    )

    return Response(
        {"topic_id": topic_id, "short": short, "markdown": markdown},
        status=status.HTTP_200_OK,
    )
