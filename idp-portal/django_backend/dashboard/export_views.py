"""Vues d'export dashboard (CSV et PDF).

Story 30.2: Export des statistiques du dashboard en CSV et PDF.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta

import structlog
from django.db.models import Q, Count, QuerySet
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView

from core.exceptions import BadRequestError
from core.middleware import get_correlation_id
from core.permissions import IsAdminUser
from dashboard.views import _parse_date  # DASH-MED-01: shared helper, removed local duplicate
from executions.models import Execution, ExecutionStatus

logger = structlog.get_logger(__name__)

MAX_EXPORT_ROWS = 10_000


def _build_export_queryset(request: Request) -> QuerySet:
    """Build filtered and aggregated queryset for dashboard export.

    HIGH-4 fix: Apply scope filter to respect RBAC permissions.
    DASH-LOW-03: apply_scope_filter importé inline pour éviter un import circulaire potentiel
    (executions.utils → dashboard.views → executions.models). Import inline intentionnel.
    """
    from executions.utils import apply_scope_filter

    qs = Execution.objects.select_related("action")
    # Apply scope filter to respect RBAC permissions (HIGH-4 fix)
    # Default scope='mine' for exports unless user explicitly requests 'all' (DBA/DBOPS only)
    scope = request.query_params.get("scope", "mine")
    qs, _effective_scope = apply_scope_filter(qs, user=request.user, scope=scope)

    # Date filters
    start_date = _parse_date(request.query_params.get("start_date"), name="start_date")
    end_date = _parse_date(request.query_params.get("end_date"), name="end_date")

    if start_date:
        start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        qs = qs.filter(created_at__gte=start_dt)
    if end_date:
        end_dt = timezone.make_aware(
            datetime.combine(end_date + timedelta(days=1), datetime.min.time())
        )
        qs = qs.filter(created_at__lt=end_dt)

    # Engine filter
    engine = request.query_params.get("engine")
    if engine:
        qs = qs.filter(action__engine=engine)

    # Environment filter (iexact pour cohérence avec _apply_common_filters dans views.py)
    environment = request.query_params.get("environment")
    if environment:
        qs = qs.filter(environment__iexact=environment)

    # Tags filter
    tags = request.query_params.getlist("tags")
    tags = [t.strip() for t in tags if t and t.strip()]
    if tags:
        qs = qs.filter(action__actiontag__tag__name__in=tags)

    # Aggregate by date, engine, environment
    aggregated = (
        qs.annotate(exec_date=TruncDate("created_at"))
        .values("exec_date", "action__engine", "environment")
        .annotate(
            total_executions=Count("id"),
            successful_executions=Count(
                "id", filter=Q(status=ExecutionStatus.COMPLETED)
            ),
            failed_executions=Count(
                "id", filter=Q(status=ExecutionStatus.FAILED)
            ),
        )
        .order_by("exec_date", "action__engine", "environment")
    )

    return aggregated[:MAX_EXPORT_ROWS]


class DashboardExportCSVView(APIView):
    """GET /dashboard/export/csv — Export des statistiques dashboard en CSV."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        tags=["dashboard"],
        summary="Export CSV des statistiques dashboard",
        parameters=[
            OpenApiParameter('scope', str, description='mine (défaut) ou all'),
            OpenApiParameter('start_date', str, description='Date de début (YYYY-MM-DD)'),
            OpenApiParameter('end_date', str, description='Date de fin (YYYY-MM-DD)'),
            OpenApiParameter('engine', str, description='Filtrage par technologie'),
            OpenApiParameter('environment', str, description='Filtrage par environnement'),
            OpenApiParameter('tags', str, description='Tags (multi-valeur)'),
        ],
        responses={200: bytes},
    )
    def get(self, request: Request) -> HttpResponse:
        correlation_id = get_correlation_id()

        rows = list(_build_export_queryset(request))

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "date",
            "total_executions",
            "successful_executions",
            "failed_executions",
            "success_rate_pct",
            "avg_execution_time_ms",
            "engine",
            "environment",
        ])

        for row in rows:
            total = row["total_executions"]
            success = row["successful_executions"]
            success_rate = round((success / total) * 100, 1) if total > 0 else 0.0
            exec_date = row["exec_date"]
            date_str = exec_date.strftime("%Y-%m-%d") if exec_date else ""

            writer.writerow([
                date_str,
                total,
                success,
                row["failed_executions"],
                success_rate,
                "",  # DASH-LOW-04: avg_execution_time_ms — dette technique connue (Story 30.2).
                     # L'agrégation Python via _compute_avg_duration_s() est disponible mais non appliquée ici
                     # car _build_export_queryset() retourne des agrégats SQL sans timestamps individuels.
                row["action__engine"] or "",
                row["environment"] or "",
            ])

        # UTF-8 BOM for Excel compatibility
        content = buf.getvalue().encode("utf-8-sig")
        filename = f"dashboard-export-{timezone.now().date().isoformat()}.csv"

        logger.info(
            "dashboard_csv_exported",
            row_count=len(rows),
            user_id=request.user.id,
            correlation_id=correlation_id,
        )

        resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp


class DashboardExportPDFView(APIView):
    """GET /dashboard/export/pdf — Export des statistiques dashboard en PDF."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        tags=["dashboard"],
        summary="Export PDF des statistiques dashboard",
        parameters=[
            OpenApiParameter('scope', str, description='mine (défaut) ou all'),
            OpenApiParameter('start_date', str, description='Date de début (YYYY-MM-DD)'),
            OpenApiParameter('end_date', str, description='Date de fin (YYYY-MM-DD)'),
            OpenApiParameter('engine', str, description='Filtrage par technologie'),
            OpenApiParameter('environment', str, description='Filtrage par environnement'),
            OpenApiParameter('tags', str, description='Tags (multi-valeur)'),
        ],
        responses={200: bytes},
    )
    def get(self, request: Request) -> HttpResponse:
        correlation_id = get_correlation_id()

        try:
            from reportlab.lib import colors  # type: ignore[import-untyped]
            from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
            from reportlab.lib.styles import getSampleStyleSheet  # type: ignore[import-untyped]
            from reportlab.lib.units import mm  # type: ignore[import-untyped]
            from reportlab.platypus import (  # type: ignore[import-untyped]
                SimpleDocTemplate,
                Table,
                TableStyle,
                Paragraph,
                Spacer,
            )
            from reportlab.graphics.shapes import Drawing  # type: ignore[import-untyped]
            from reportlab.graphics.charts.lineplots import LinePlot  # type: ignore[import-untyped]
        except ImportError:
            raise BadRequestError(
                code="PDF_UNAVAILABLE",
                message="Export PDF non disponible (bibliothèque reportlab manquante)",
                details={},
            )

        rows = list(_build_export_queryset(request))

        # Calculate global stats
        total_executions = sum(r["total_executions"] for r in rows)
        total_success = sum(r["successful_executions"] for r in rows)
        total_failed = sum(r["failed_executions"] for r in rows)
        success_rate = (
            round((total_success / total_executions) * 100, 1)
            if total_executions > 0
            else 0.0
        )

        # Group by engine
        by_engine: dict[str, dict] = {}
        for r in rows:
            engine = r["action__engine"] or "N/A"
            if engine not in by_engine:
                by_engine[engine] = {"total": 0, "success": 0, "failed": 0}
            by_engine[engine]["total"] += r["total_executions"]
            by_engine[engine]["success"] += r["successful_executions"]
            by_engine[engine]["failed"] += r["failed_executions"]

        # Group by environment
        by_env: dict[str, dict] = {}
        for r in rows:
            env = r["environment"] or "N/A"
            if env not in by_env:
                by_env[env] = {"total": 0, "success": 0, "failed": 0}
            by_env[env]["total"] += r["total_executions"]
            by_env[env]["success"] += r["successful_executions"]
            by_env[env]["failed"] += r["failed_executions"]

        # Group by date for timeseries
        by_date: dict[str, int] = {}
        for r in rows:
            date_str = (
                r["exec_date"].strftime("%Y-%m-%d") if r["exec_date"] else "N/A"
            )
            by_date[date_str] = by_date.get(date_str, 0) + r["total_executions"]

        # Build PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements: list = []

        # Date range for title
        start_date_str = request.query_params.get("start_date", "début")
        end_date_str = request.query_params.get("end_date", "aujourd'hui")

        # Section 1: Title + global stats
        elements.append(
            Paragraph(
                f"Dashboard Export &mdash; {start_date_str} à {end_date_str}",
                styles["Title"],
            )
        )
        elements.append(Spacer(1, 6 * mm))
        elements.append(
            Paragraph(
                f"Total exécutions : {total_executions} | "
                f"Taux de succès : {success_rate}% | "
                f"Succès : {total_success} | Échecs : {total_failed}",
                styles["Normal"],
            )
        )
        elements.append(Spacer(1, 10 * mm))

        # Section 2: Table by technology (engine)
        elements.append(
            Paragraph("Statistiques par Technologie", styles["Heading2"])
        )
        engine_table_data = [
            ["Moteur", "Total", "Succès", "Échec", "Taux succès %"]
        ]
        for engine, stats in sorted(by_engine.items()):
            finished = stats["success"] + stats["failed"]
            rate = (
                round((stats["success"] / finished) * 100, 1) if finished > 0 else 0.0
            )
            engine_table_data.append(
                [engine, stats["total"], stats["success"], stats["failed"], f"{rate}%"]
            )

        if len(engine_table_data) > 1:
            t = Table(engine_table_data)
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ]
                )
            )
            elements.append(t)
        elements.append(Spacer(1, 10 * mm))

        # Section 3: Table by environment
        elements.append(
            Paragraph("Statistiques par Environnement", styles["Heading2"])
        )
        env_table_data = [
            ["Environnement", "Total", "Succès", "Échec", "Taux succès %"]
        ]
        for env, stats in sorted(by_env.items()):
            finished = stats["success"] + stats["failed"]
            rate = (
                round((stats["success"] / finished) * 100, 1) if finished > 0 else 0.0
            )
            env_table_data.append(
                [env, stats["total"], stats["success"], stats["failed"], f"{rate}%"]
            )

        if len(env_table_data) > 1:
            t = Table(env_table_data)
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ]
                )
            )
            elements.append(t)
        elements.append(Spacer(1, 10 * mm))

        # Section 4: Timeseries chart
        elements.append(Paragraph("Exécutions par jour", styles["Heading2"]))
        if by_date:
            sorted_dates = sorted(by_date.keys())
            chart_data = [(i, by_date[d]) for i, d in enumerate(sorted_dates)]

            drawing = Drawing(400, 200)
            lp = LinePlot()
            lp.x = 50
            lp.y = 30
            lp.width = 300
            lp.height = 150
            lp.data = [chart_data]
            lp.lines[0].strokeColor = colors.blue
            drawing.add(lp)
            elements.append(drawing)
        else:
            elements.append(
                Paragraph(
                    "Aucune donnée pour la période sélectionnée.",
                    styles["Normal"],
                )
            )

        doc.build(elements)

        content = buffer.getvalue()
        filename = f"dashboard-export-{timezone.now().date().isoformat()}.pdf"

        logger.info(
            "dashboard_pdf_exported",
            row_count=len(rows),
            user_id=request.user.id,
            correlation_id=correlation_id,
        )

        resp = HttpResponse(content, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp
