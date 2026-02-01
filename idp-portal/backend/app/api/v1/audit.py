"""Audit API (Story 6.3, 6.4).

Provides read-only endpoints for audit log consultation.
- GET /api/v1/audit/executions: List execution audit entries with filters
- GET /api/v1/audit/export: Export audit entries as CSV or PDF

Access restricted to users with is_auditor=True in their profile(s).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse, Response
import structlog
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from app.api.deps import get_current_user
from app.core.exceptions import BadRequestError, ForbiddenError
from app.models.auth import UserProfile
from app.repositories import audit_repository, catalog_repository

logger = structlog.get_logger()

router = APIRouter(prefix="/audit", tags=["audit"])

# Maximum rows for export (NFR24)
MAX_EXPORT_ROWS = 10000


def _require_auditor(user: UserProfile) -> None:
    """Check that user has auditor role (Story 6.3, AC8, Task 4.1).

    Raises:
        ForbiddenError: If user is not an auditor
    """
    if not user.is_auditor:
        raise ForbiddenError(
            code="AUDITOR_REQUIRED",
            message="Accès réservé aux auditeurs",
        )


@router.get("/executions", response_model=None)
async def list_execution_audit(
    user: UserProfile = Depends(get_current_user),
    from_date: str | None = Query(None, alias="from", description="Start date (ISO format)"),
    to_date: str | None = Query(None, alias="to", description="End date (ISO format)"),
    environment: str | None = Query(None, description="Environment filter (dev, staging, prod)"),
    action_id: int | None = Query(None, description="Action ID filter"),
    user_id: str | None = Query(None, description="User ID filter"),
    status: str | None = Query(None, description="Status filter: success, failed, running"),
    sort: str = Query("timestamp", description="Sort field: timestamp, user_id, action_type"),
    order: str = Query("desc", description="Sort order: asc, desc"),
    limit: int = Query(25, ge=1, le=100, description="Page size (default 25)"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> dict[str, Any]:
    """GET /api/v1/audit/executions - List execution audit entries (Story 6.3, AC6).

    Returns paginated list of execution audit entries with filters.
    Access restricted to auditors (is_auditor=True).

    Query Parameters:
        from: Start date (ISO format, e.g. 2024-01-01T00:00:00)
        to: End date (ISO format)
        environment: Filter by environment (dev, staging, prod)
        action_id: Filter by action ID
        user_id: Filter by user ID
        status: Filter by status (success, failed, running)
        sort: Sort field (timestamp, user_id, action_type) - default: timestamp
        order: Sort order (asc, desc) - default: desc
        limit: Page size (1-100, default 25)
        offset: Offset for pagination

    Returns:
        {
            "data": [...],
            "pagination": { "page", "page_size", "total_count", "total_pages" }
        }

    Raises:
        403 AUDITOR_REQUIRED: If user is not an auditor
    """
    _require_auditor(user)

    logger.info(
        "audit_executions_list",
        from_date=from_date,
        to_date=to_date,
        environment=environment,
        action_id=action_id,
        user_id=user_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    # Validate sort and order
    valid_sort_fields = {"timestamp", "user_id", "action_type"}
    if sort not in valid_sort_fields:
        sort = "timestamp"
    if order not in {"asc", "desc"}:
        order = "desc"

    # Get entries and count in parallel would be ideal, but for simplicity do sequentially
    entries = await audit_repository.list_execution_audit_entries(
        from_date=from_date,
        to_date=to_date,
        user_id=user_id,
        environment=environment,
        action_id=action_id,
        status=status,
        sort_field=sort,
        sort_order=order,
        limit=limit,
        offset=offset,
    )

    # Enrich entries with action names (Story 6.3, HIGH-4 fix)
    action_ids = [
        entry["details"]["action_id"]
        for entry in entries
        if entry.get("details") and entry["details"].get("action_id")
    ]
    if action_ids:
        action_names = await catalog_repository.get_action_names_by_ids(action_ids)
        for entry in entries:
            action_id = entry.get("details", {}).get("action_id")
            if action_id and action_id in action_names:
                entry["action_name"] = action_names[action_id]

    total_count = await audit_repository.count_execution_audit_entries(
        from_date=from_date,
        to_date=to_date,
        user_id=user_id,
        environment=environment,
        action_id=action_id,
        status=status,
    )

    page = (offset // limit) + 1
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1

    return {
        "data": entries,
        "pagination": {
            "page": page,
            "page_size": limit,
            "total_count": total_count,
            "total_pages": total_pages,
        },
    }


@router.get("/export")
async def export_audit_report(
    user: UserProfile = Depends(get_current_user),
    format: Literal["csv", "pdf"] = Query(..., description="Export format: csv or pdf"),
    from_date: str | None = Query(None, alias="from", description="Start date (ISO format)"),
    to_date: str | None = Query(None, alias="to", description="End date (ISO format)"),
    environment: str | None = Query(None, description="Environment filter (dev, staging, prod)"),
    action_id: int | None = Query(None, description="Action ID filter"),
    user_id: str | None = Query(None, description="User ID filter"),
    status: str | None = Query(None, description="Status filter: success, failed, running"),
) -> Response:
    """GET /api/v1/audit/export - Export audit entries as CSV or PDF (Story 6.4, AC4).

    Exports filtered audit entries to CSV or PDF format.
    Access restricted to auditors (is_auditor=True).
    Maximum 10,000 rows (NFR24).

    Query Parameters:
        format: Export format (csv or pdf) - REQUIRED
        from: Start date (ISO format)
        to: End date (ISO format)
        environment: Filter by environment (dev, staging, prod)
        action_id: Filter by action ID
        user_id: Filter by user ID
        status: Filter by status (success, failed, running)

    Returns:
        CSV or PDF file with Content-Disposition header

    Raises:
        403 AUDITOR_REQUIRED: If user is not an auditor
        400: If export exceeds 10,000 rows
        422: If format is invalid (handled by FastAPI)
    """
    _require_auditor(user)

    logger.info(
        "audit_export_requested",
        format=format,
        from_date=from_date,
        to_date=to_date,
        environment=environment,
        action_id=action_id,
        user_id=user_id,
        status=status,
    )

    # Fetch entries with max limit of 10,000 (NFR24)
    entries = await audit_repository.list_execution_audit_entries(
        from_date=from_date,
        to_date=to_date,
        user_id=user_id,
        environment=environment,
        action_id=action_id,
        status=status,
        limit=MAX_EXPORT_ROWS + 1,  # Fetch one extra to detect overflow
        offset=0,
    )

    # Check if limit exceeded
    if len(entries) > MAX_EXPORT_ROWS:
        raise BadRequestError(
            code="EXPORT_LIMIT_EXCEEDED",
            message=f"Export limit exceeded: maximum {MAX_EXPORT_ROWS} rows allowed. Please apply additional filters.",
        )

    # Enrich entries with action names (Story 6.4, MEDIUM-1 fix - same as /executions)
    action_ids = [
        entry["details"]["action_id"]
        for entry in entries
        if entry.get("details") and entry["details"].get("action_id")
    ]
    if action_ids:
        action_names = await catalog_repository.get_action_names_by_ids(action_ids)
        for entry in entries:
            action_id = entry.get("details", {}).get("action_id")
            if action_id and action_id in action_names:
                entry["action_name"] = action_names[action_id]

    # Get total count for PDF header
    total_count = await audit_repository.count_execution_audit_entries(
        from_date=from_date,
        to_date=to_date,
        user_id=user_id,
        environment=environment,
        action_id=action_id,
        status=status,
    )

    # Generate filename with current date
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"audit-export-{today}.{format}"

    if format == "csv":
        return _generate_csv_response(entries, filename)
    else:  # pdf
        return _generate_pdf_response(entries, filename, from_date, to_date, environment, action_id, user_id, status, total_count)


def _generate_csv_response(entries: list[dict], filename: str) -> StreamingResponse:
    """Generate CSV export response (Story 6.4, Task 1.3)."""
    output = io.StringIO()
    # Add UTF-8 BOM for Excel compatibility
    output.write("\ufeff")

    # Define CSV columns based on table structure (Story 6.4, HIGH-1, HIGH-2 fix)
    fieldnames = [
        "id",
        "timestamp",
        "user_id",
        "action_name",
        "action_type",
        "entity_type",
        "entity_id",
        "environment",
        "action_id",
        "status",
        "ip_address",
        "correlation_id",
        "servicenow_change_id",
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for entry in entries:
        row = {
            "id": entry.get("id"),
            "timestamp": entry.get("timestamp"),
            "user_id": entry.get("user_id"),
            "action_name": entry.get("action_name", ""),  # Enriched by export_audit_report
            "action_type": entry.get("action_type"),
            "entity_type": entry.get("entity_type"),
            "entity_id": entry.get("entity_id"),
            "ip_address": entry.get("ip_address"),
            "correlation_id": entry.get("correlation_id"),
            "status": entry.get("derived_status"),
        }
        # Extract from details JSON
        details = entry.get("details") or {}
        row["environment"] = details.get("environment")
        row["action_id"] = details.get("action_id")
        row["servicenow_change_id"] = details.get("servicenow_change_id", "")

        writer.writerow(row)

    output.seek(0)
    content = output.getvalue().encode("utf-8")

    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


def _generate_pdf_response(
    entries: list[dict],
    filename: str,
    from_date: str | None,
    to_date: str | None,
    environment: str | None,
    action_id: int | None,
    user_id: str | None,
    status: str | None,
    total_count: int,
) -> Response:
    """Generate PDF export response (Story 6.4, Task 1.4)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#1a1a1a"),
        spaceAfter=12,
    )
    header_style = ParagraphStyle(
        "CustomHeader",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#666666"),
    )

    # Header: Date, filters, count
    story.append(Paragraph("Rapport d'audit - Export", title_style))
    story.append(Spacer(1, 0.2 * inch))

    header_info = [
        f"<b>Date d'export:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"<b>Nombre d'enregistrements:</b> {total_count}",
    ]

    filters_applied = []
    if from_date:
        filters_applied.append(f"Du: {from_date}")
    if to_date:
        filters_applied.append(f"Au: {to_date}")
    if environment:
        filters_applied.append(f"Environnement: {environment}")
    if action_id:
        filters_applied.append(f"Action ID: {action_id}")
    if user_id:
        filters_applied.append(f"Utilisateur: {user_id}")
    if status:
        filters_applied.append(f"Statut: {status}")

    if filters_applied:
        header_info.append(f"<b>Filtres appliqués:</b> {', '.join(filters_applied)}")
    else:
        header_info.append("<b>Filtres appliqués:</b> Aucun")

    for info in header_info:
        story.append(Paragraph(info, header_style))
        story.append(Spacer(1, 0.1 * inch))

    story.append(Spacer(1, 0.3 * inch))

    # Table data (Story 6.4, HIGH-3 fix - include action_name and servicenow_change_id)
    table_data = [["ID", "Date", "Utilisateur", "Action", "Environnement", "Action ID", "Statut", "Change SN", "Correlation ID"]]

    for entry in entries:
        details = entry.get("details") or {}
        # Use action_name if available (enriched), fallback to action_type
        action_display = entry.get("action_name") or entry.get("action_type", "")
        row = [
            str(entry.get("id", "")),
            entry.get("timestamp", "")[:19] if entry.get("timestamp") else "",
            entry.get("user_id", ""),
            action_display,
            details.get("environment", ""),
            str(details.get("action_id", "")),
            entry.get("derived_status", ""),
            str(details.get("servicenow_change_id", "")) or "",
            entry.get("correlation_id", "") or "",
        ]
        table_data.append(row)

    # Create table
    table = Table(table_data)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]
        )
    )

    story.append(table)
    
    # Generate PDF with error handling (Story 6.4, LOW-2 fix)
    try:
        doc.build(story)
    except Exception as e:
        logger.error("pdf_generation_failed", error=str(e))
        raise BadRequestError(
            code="PDF_GENERATION_FAILED",
            message="Erreur lors de la génération du PDF. Veuillez réessayer ou utiliser le format CSV.",
        )

    buffer.seek(0)
    content = buffer.read()

    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
