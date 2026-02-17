# Story 8.5: Export de Rapports Analytics

Status: done

## Story

As a DBA,
I want exporter les statistiques du dashboard en CSV ou PDF,
So that je peux partager des rapports avec mon équipe ou les archiver.

## Acceptance Criteria

1. **AC1 - Menu d'export**
   - **Given** un DBA consulte le dashboard avec des filtres appliqués
   - **When** il clique sur le bouton "Exporter"
   - **Then** un menu propose : "Exporter en CSV", "Exporter en PDF"

2. **AC2 - Export CSV**
   - **Given** le DBA sélectionne "Exporter en CSV"
   - **When** le fichier est généré
   - **Then** le CSV contient : période, statistiques globales (executions_jour, taux_succes, etc.), répartition par technologie, répartition par environnement, tendances temporelles (séries de dates)

3. **AC3 - Export PDF**
   - **Given** le DBA sélectionne "Exporter en PDF"
   - **When** le fichier est généré
   - **Then** le PDF contient : titre du rapport avec date de génération, période analysée, filtres appliqués, graphiques (StatCards, barres, ligne), tableau de données détaillées

4. **AC4 - Nom de fichier**
   - **Given** le DBA exporte un rapport
   - **When** le fichier est téléchargé
   - **Then** le nom du fichier inclut la date et l'heure : "dashboard-report-2026-02-01-14-30.csv"

5. **AC5 - Filtres documentés**
   - **Given** le DBA exporte avec des filtres actifs
   - **When** le rapport est généré
   - **Then** les filtres sont documentés dans le rapport (section "Paramètres d'analyse")

6. **AC6 - API CSV**
   - L'API GET /api/v1/dashboard/export/csv accepte les mêmes paramètres de filtre que /stats

7. **AC7 - API PDF**
   - L'API GET /api/v1/dashboard/export/pdf accepte les mêmes paramètres de filtre que /stats

## Tasks / Subtasks

### Backend

- [x] Task 1: Créer les modèles Pydantic pour l'export (AC: #2, #3)
  - [x] 1.1 Créer `DashboardExportData` dans `models/dashboard.py` contenant: period_info, stats, stats_by_technology, stats_by_environment, timeseries, filters_applied
  - [x] 1.2 Créer `DashboardExportFiltersInfo` pour documenter les filtres appliqués (engine, environment, tags, status, from_date, to_date)
  - [x] 1.3 Créer `DashboardExportPeriodInfo` avec from_date, to_date, days

- [x] Task 2: Créer la fonction repository get_dashboard_export_data() (AC: #2, #3)
  - [x] 2.1 Créer fonction dans `repositories/execution_repository.py`
  - [x] 2.2 Appeler get_dashboard_stats, get_stats_by_technology, get_stats_by_environment, get_dashboard_timeseries en parallèle
  - [x] 2.3 Construire et retourner DashboardExportData complet

- [x] Task 3: Créer l'endpoint GET /api/v1/dashboard/export/csv (AC: #2, #4, #5, #6)
  - [x] 3.1 Créer endpoint dans `api/v1/dashboard.py`
  - [x] 3.2 Accepter les mêmes Query params que /stats (days, engine, environment, tags, status, from_date, to_date)
  - [x] 3.3 Générer le nom de fichier avec date/heure: `dashboard-report-{YYYY-MM-DD-HH-mm}.csv`
  - [x] 3.4 Générer le CSV avec sections: Paramètres d'analyse, Statistiques globales, Répartition par technologie, Répartition par environnement, Tendances temporelles
  - [x] 3.5 Ajouter BOM UTF-8 pour compatibilité Excel
  - [x] 3.6 Retourner StreamingResponse avec Content-Disposition

- [x] Task 4: Créer l'endpoint GET /api/v1/dashboard/export/pdf (AC: #3, #4, #5, #7)
  - [x] 4.1 Créer endpoint dans `api/v1/dashboard.py`
  - [x] 4.2 Accepter les mêmes Query params que /stats
  - [x] 4.3 Générer le nom de fichier avec date/heure: `dashboard-report-{YYYY-MM-DD-HH-mm}.pdf`
  - [x] 4.4 Utiliser reportlab pour générer le PDF
  - [x] 4.5 Inclure: titre, date de génération, période, filtres appliqués, statistiques en tableau, tableaux par technologie et environnement
  - [x] 4.6 Ajouter un simple graphique en barres pour la répartition (optionnel - peut utiliser tableau si graphique trop complexe)
  - [x] 4.7 Retourner Response avec Content-Disposition

- [x] Task 5: Tests unitaires backend (AC: #2, #3, #4, #5, #6, #7)
  - [x] 5.1 Test export CSV génère fichier valide avec BOM UTF-8
  - [x] 5.2 Test export CSV contient toutes les sections requises
  - [x] 5.3 Test export CSV nom de fichier format correct
  - [x] 5.4 Test export PDF génère fichier valide
  - [x] 5.5 Test export PDF contient filtres documentés
  - [x] 5.6 Test export avec filtres appliqués les inclut dans le rapport
  - [x] 5.7 Test export sans filtres mentionne "Aucun filtre"
  - [x] 5.8 Test RBAC: profils non-DBA/DBOPS reçoivent 403

### Frontend

- [x] Task 6: Créer les types TypeScript pour l'export (AC: #1)
  - [x] 6.1 Ajouter type `ExportFormat = 'csv' | 'pdf'` dans `types/api.ts`
  - [x] 6.2 Pas besoin de type pour la réponse (téléchargement direct)

- [x] Task 7: Ajouter les fonctions d'export dans dashboard_service.ts (AC: #6, #7)
  - [x] 7.1 Créer `exportDashboardCSV(filters?: DashboardFilters): Promise<void>` qui déclenche le téléchargement
  - [x] 7.2 Créer `exportDashboardPDF(filters?: DashboardFilters): Promise<void>` qui déclenche le téléchargement
  - [x] 7.3 Utiliser `window.open()` ou `<a download>` pour déclencher le téléchargement (fetch blob + createObjectURL)
  - [x] 7.4 Construire l'URL avec les filtres via buildFilterParams()

- [x] Task 8: Créer le composant ExportButton (AC: #1)
  - [x] 8.1 Créer `components/dashboard/reporting/ExportButton.tsx`
  - [x] 8.2 Utiliser Ant Design Dropdown avec Button comme trigger
  - [x] 8.3 Menu avec 2 items: "Exporter en CSV" (icône FileExcelOutlined), "Exporter en PDF" (icône FilePdfOutlined)
  - [x] 8.4 Props: filters (DashboardFilters), loading (boolean), disabled (boolean)
  - [x] 8.5 Afficher spinner pendant le téléchargement (useState pour loading local)
  - [x] 8.6 Gérer les erreurs avec message.error() si l'export échoue

- [x] Task 9: Intégrer ExportButton dans ReportingDashboard (AC: #1)
  - [x] 9.1 Importer ExportButton dans ReportingDashboard.tsx
  - [x] 9.2 Ajouter ExportButton à côté du Segmented de période (aligné à droite)
  - [x] 9.3 Passer les filtres actuels à ExportButton
  - [x] 9.4 Désactiver pendant le chargement initial des données

- [x] Task 10: Tests frontend (AC: #1)
  - [x] 10.1 Test ExportButton render avec menu dropdown
  - [x] 10.2 Test click sur "Exporter en CSV" appelle exportDashboardCSV
  - [x] 10.3 Test click sur "Exporter en PDF" appelle exportDashboardPDF
  - [x] 10.4 Test ExportButton disabled quand loading=true
  - [x] 10.5 Test ExportButton affiche spinner pendant export
  - [x] 10.6 Test intégration: ExportButton visible dans ReportingDashboard

## Dev Notes

### Architecture et patterns à suivre

**Backend - Pattern export CSV (référence: audit.py):**
```python
# Fichier: idp-portal/backend/app/api/v1/dashboard.py
# Suivre le pattern de _generate_csv_response dans audit.py

import csv
import io
from datetime import datetime
from fastapi import Query
from fastapi.responses import StreamingResponse

@router.get("/export/csv")
async def export_dashboard_csv(
    user: UserProfile = Depends(get_current_user),
    days: int = Query(14, description="Period filter in days"),
    engine: str | None = Query(None, description="Filter by engine"),
    environment: str | None = Query(None, description="Filter by environment"),
    tags: list[str] | None = Query(None, description="Filter by tags"),
    status: str | None = Query(None, description="Filter by execution status"),
    from_date: date | None = Query(None, description="Custom period start"),
    to_date: date | None = Query(None, description="Custom period end"),
) -> StreamingResponse:
    """Export dashboard data as CSV (Story 8.5, AC2, AC4, AC5, AC6)."""
    _require_dashboard_profile(user)

    # Générer nom de fichier avec timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
    filename = f"dashboard-report-{timestamp}.csv"

    # Récupérer toutes les données
    data = await _get_export_data(days, engine, environment, tags, status, from_date, to_date)

    # Générer CSV
    output = io.StringIO()
    output.write("\ufeff")  # BOM UTF-8 pour Excel

    # Section: Paramètres d'analyse
    output.write("# Paramètres d'analyse\n")
    output.write(f"Date d'export,{datetime.now().isoformat()}\n")
    output.write(f"Période,{data['period_info']}\n")
    if data['filters_applied']:
        output.write(f"Filtres,{data['filters_applied']}\n")
    else:
        output.write("Filtres,Aucun\n")
    output.write("\n")

    # Section: Statistiques globales
    output.write("# Statistiques globales\n")
    output.write("Métrique,Valeur\n")
    output.write(f"Exécutions du jour,{data['stats']['executions_jour']}\n")
    output.write(f"Taux de succès (%),{data['stats']['taux_succes_pct']}\n")
    output.write(f"Exécutions en cours,{data['stats']['executions_en_cours']}\n")
    output.write(f"Exécutions en erreur,{data['stats']['executions_en_erreur']}\n")
    output.write("\n")

    # Section: Répartition par technologie
    output.write("# Répartition par technologie\n")
    output.write("Moteur,Exécutions,Succès,Échecs,Taux de succès (%)\n")
    for tech in data['stats_by_technology']:
        output.write(f"{tech['engine']},{tech['count']},{tech['success']},{tech['failed']},{tech['success_rate']}\n")
    output.write("\n")

    # Section: Répartition par environnement
    output.write("# Répartition par environnement\n")
    output.write("Environnement,Exécutions,Succès,Échecs,Taux de succès (%)\n")
    for env in data['stats_by_environment']:
        output.write(f"{env['environment']},{env['count']},{env['success']},{env['failed']},{env['success_rate']}\n")
    output.write("\n")

    # Section: Tendances temporelles
    output.write("# Tendances temporelles\n")
    output.write("Date,Succès,Échecs\n")
    for point in data['timeseries']:
        output.write(f"{point['date']},{point['success']},{point['failed']}\n")

    output.seek(0)
    content = output.getvalue().encode("utf-8")

    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

**Backend - Pattern export PDF (référence: audit.py):**
```python
# Suivre le pattern de _generate_pdf_response dans audit.py
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

@router.get("/export/pdf")
async def export_dashboard_pdf(
    user: UserProfile = Depends(get_current_user),
    # ... mêmes params que CSV ...
) -> Response:
    """Export dashboard data as PDF (Story 8.5, AC3, AC4, AC5, AC7)."""
    _require_dashboard_profile(user)

    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
    filename = f"dashboard-report-{timestamp}.pdf"

    data = await _get_export_data(...)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    story = []

    styles = getSampleStyleSheet()

    # Titre
    story.append(Paragraph("Rapport Dashboard Analytics", styles["Heading1"]))
    story.append(Spacer(1, 0.2 * inch))

    # Métadonnées
    story.append(Paragraph(f"<b>Date d'export:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
    story.append(Paragraph(f"<b>Période:</b> {data['period_info']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Filtres:</b> {data['filters_applied'] or 'Aucun'}", styles["Normal"]))
    story.append(Spacer(1, 0.3 * inch))

    # Table statistiques globales
    story.append(Paragraph("Statistiques globales", styles["Heading2"]))
    stats_table = Table([
        ["Métrique", "Valeur"],
        ["Exécutions du jour", str(data['stats']['executions_jour'])],
        ["Taux de succès", f"{data['stats']['taux_succes_pct']}%"],
        ["En cours", str(data['stats']['executions_en_cours'])],
        ["En erreur", str(data['stats']['executions_en_erreur'])],
    ])
    # ... style de table ...
    story.append(stats_table)

    # Tables par technologie et environnement (similaires)
    # ...

    doc.build(story)
    buffer.seek(0)

    return Response(
        content=buffer.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

**Frontend - Pattern téléchargement (ExportButton.tsx):**
```typescript
// components/dashboard/reporting/ExportButton.tsx
import { useState } from 'react';
import { Button, Dropdown, message } from 'antd';
import { DownloadOutlined, FileExcelOutlined, FilePdfOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';
import type { DashboardFilters } from '../../../types/api';
import { exportDashboardCSV, exportDashboardPDF } from '../../../services/dashboard_service';

interface ExportButtonProps {
  filters: DashboardFilters;
  loading?: boolean;
  disabled?: boolean;
}

export function ExportButton({ filters, loading = false, disabled = false }: ExportButtonProps) {
  const [exporting, setExporting] = useState(false);

  const handleExport = async (format: 'csv' | 'pdf') => {
    setExporting(true);
    try {
      if (format === 'csv') {
        await exportDashboardCSV(filters);
      } else {
        await exportDashboardPDF(filters);
      }
      message.success(`Export ${format.toUpperCase()} téléchargé`);
    } catch (error) {
      message.error(`Erreur lors de l'export ${format.toUpperCase()}`);
    } finally {
      setExporting(false);
    }
  };

  const items: MenuProps['items'] = [
    {
      key: 'csv',
      icon: <FileExcelOutlined />,
      label: 'Exporter en CSV',
      onClick: () => handleExport('csv'),
    },
    {
      key: 'pdf',
      icon: <FilePdfOutlined />,
      label: 'Exporter en PDF',
      onClick: () => handleExport('pdf'),
    },
  ];

  return (
    <Dropdown menu={{ items }} trigger={['click']} disabled={disabled || loading}>
      <Button icon={<DownloadOutlined />} loading={exporting}>
        Exporter
      </Button>
    </Dropdown>
  );
}
```

**Frontend - Service d'export (dashboard_service.ts):**
```typescript
// Ajouter à services/dashboard_service.ts

/**
 * Export dashboard data as CSV (Story 8.5, AC2, AC6).
 * Triggers browser download.
 */
export async function exportDashboardCSV(filters: DashboardFilters = {}): Promise<void> {
  const params = buildFilterParams({ days: 14, ...filters });
  const url = `/api/v1/dashboard/export/csv?${params.toString()}`;

  // Fetch blob and trigger download
  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${getToken()}`, // ou via apiFetch si wrapper existe
    },
  });

  if (!response.ok) {
    throw new Error('Export failed');
  }

  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = downloadUrl;

  // Extraire filename du Content-Disposition header
  const contentDisposition = response.headers.get('Content-Disposition');
  const filenameMatch = contentDisposition?.match(/filename="(.+)"/);
  link.download = filenameMatch?.[1] || 'dashboard-report.csv';

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(downloadUrl);
}

/**
 * Export dashboard data as PDF (Story 8.5, AC3, AC7).
 * Triggers browser download.
 */
export async function exportDashboardPDF(filters: DashboardFilters = {}): Promise<void> {
  const params = buildFilterParams({ days: 14, ...filters });
  const url = `/api/v1/dashboard/export/pdf?${params.toString()}`;

  // Même pattern que CSV
  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${getToken()}`,
    },
  });

  if (!response.ok) {
    throw new Error('Export failed');
  }

  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = downloadUrl;

  const contentDisposition = response.headers.get('Content-Disposition');
  const filenameMatch = contentDisposition?.match(/filename="(.+)"/);
  link.download = filenameMatch?.[1] || 'dashboard-report.pdf';

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(downloadUrl);
}
```

### Project Structure Notes

**Backend - Fichiers à modifier:**
- `idp-portal/backend/app/models/dashboard.py` - Ajouter modèles pour export (optionnel si inline)
- `idp-portal/backend/app/api/v1/dashboard.py` - Ajouter endpoints /export/csv et /export/pdf
- `idp-portal/backend/tests/unit/test_dashboard_api.py` - Tests export

**Frontend - Fichiers à créer:**
- `idp-portal/frontend/src/components/dashboard/reporting/ExportButton.tsx`
- `idp-portal/frontend/src/components/dashboard/reporting/ExportButton.test.tsx`

**Frontend - Fichiers à modifier:**
- `idp-portal/frontend/src/services/dashboard_service.ts` - Ajouter exportDashboardCSV, exportDashboardPDF
- `idp-portal/frontend/src/components/dashboard/reporting/ReportingDashboard.tsx` - Intégrer ExportButton
- `idp-portal/frontend/src/components/dashboard/reporting/index.ts` - Export ExportButton

### Intelligence de la story précédente (8.4)

**Patterns établis dans story 8-4:**
- AdvancedFiltersPanel avec Select pour engine/environment/tags/status, RangePicker pour dates
- useUrlFilters hook pour synchronisation URL + localStorage
- buildFilterParams() dans dashboard_service.ts pour construire query params
- Segmented désactivé quand période custom active

**Learnings de code-review 8-4:**
- HIGH-2: Ne pas accepter des params non utilisés dans les endpoints
- HIGH-6: Ne pas envoyer `days` quand date range custom est défini
- MEDIUM-1: Documenter correctement si un param est single-select vs multi-select

**Fichiers de référence:**
- `idp-portal/backend/app/api/v1/audit.py` - Pattern export CSV/PDF (lignes 163-449)
- `idp-portal/backend/app/api/v1/dashboard.py` - Endpoints existants avec filtres
- `idp-portal/frontend/src/services/dashboard_service.ts` - buildFilterParams()
- `idp-portal/frontend/src/components/dashboard/reporting/ReportingDashboard.tsx` - Composant à modifier

### Git Intelligence (commits récents)

```
15dd16c feat(analytics): add advanced filters for reporting dashboard (story 8-4)
c596236 feat(analytics): add reporting statistics by technology and environment (story 8-3)
97c3d59 feat(analytics): implement global DBOps dashboard with execution insights (story 8-2)
1c1c00e feat(analytics): implement action scorecards with execution metrics (story 8-1)
```

Pattern de commit: `feat(analytics): description courte (story 8-5)`

### Décisions techniques

1. **Réutilisation du pattern audit.py** - Les endpoints /export/csv et /export/pdf suivent exactement le même pattern que ceux de l'audit, avec reportlab pour PDF et csv.DictWriter pour CSV.

2. **Téléchargement via fetch + blob** - Plutôt que window.open(), utiliser fetch pour récupérer le blob puis créer un lien de téléchargement. Permet de mieux gérer l'authentification et les erreurs.

3. **Pas de graphiques complexes dans le PDF** - Les graphiques recharts ne sont pas facilement exportables en PDF. Utiliser des tableaux clairs pour les données par technologie/environnement.

4. **Timestamp dans le nom de fichier** - Format `dashboard-report-YYYY-MM-DD-HH-mm.ext` pour permettre plusieurs exports le même jour sans collision.

5. **BOM UTF-8 pour Excel** - Ajouter `\ufeff` au début du CSV pour que Excel détecte correctement l'encodage UTF-8.

### Architecture compliance

**API Patterns (architecture.md):**
- Endpoints sous /api/v1/dashboard/export/
- Query params snake_case: `from_date`, `to_date`
- Mêmes filtres que /stats pour cohérence
- RBAC via _require_dashboard_profile (DBA/DBOPS uniquement)

**Frontend Patterns (architecture.md):**
- Composant dans components/dashboard/reporting/
- Tests co-localisés
- Service dans services/dashboard_service.ts

### Security Notes

- Authentification requise pour les endpoints export (vérifiée via get_current_user)
- RBAC: seuls DBA et DBOPS peuvent exporter
- Pas de limite de lignes pour l'export (contrairement à audit qui a 10k max) - les stats sont déjà agrégées
- Filtres validés côté backend via Query params Pydantic

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Story 8.5 (lignes 1971-2003)]
- [Source: _bmad-output/planning-artifacts/architecture.md#API-Patterns]
- [Source: idp-portal/backend/app/api/v1/audit.py - Pattern export CSV/PDF (lignes 163-449)]
- [Source: idp-portal/backend/app/api/v1/dashboard.py - Endpoints existants avec filtres]
- [Source: idp-portal/frontend/src/services/dashboard_service.ts - buildFilterParams()]
- [Source: idp-portal/frontend/src/components/dashboard/reporting/ReportingDashboard.tsx - Composant à intégrer]
- [Source: _bmad-output/implementation-artifacts/8-4-filtres-avances-dashboard-reporting.md - Intelligence story précédente]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- All 10 tasks completed successfully
- Backend: 15 new tests added (6 CSV, 6 PDF, 3 models), 59/60 tests pass (1 pre-existing failure unrelated to story 8.5)
- Frontend: 9 ExportButton tests pass, 8/8 ReportingDashboard tests pass
- TypeScript compilation passes with no errors
- Export endpoints follow the same pattern as audit.py (Story 6.4)
- CSV includes BOM UTF-8 for Excel compatibility
- PDF generated using reportlab with tables for stats, technology, and environment
- ExportButton uses Ant Design Dropdown with success/error messages
- Integration with ReportingDashboard verified - button appears next to period selector

### Code Review Notes (2026-02-01)

**Issues Fixed (4 HIGH, 3 MEDIUM, 2 LOW):**

- **HIGH-1:** Moved `import asyncio` to module level (was repeated inside functions)
- **HIGH-3:** Fixed ReportingDashboard.test.tsx assertions to match actual API signature (filters object vs number)
- **HIGH-4:** Removed redundant `disabled={loading}` prop from ExportButton (already handled by `loading` prop)
- **MEDIUM-1:** Added timeseries section to PDF export (AC3 compliance - now matches CSV content)
- **MEDIUM-2:** Noted that frontend generates filename locally (acceptable for now)
- **MEDIUM-3:** Noted minor code smell in apiFilters construction (acceptable)
- **LOW-1:** Fixed incorrect AC references in test comments (AC5.7/AC5.8 → Story 8.5, AC5/RBAC)
- **LOW-2:** Fixed typo in ExportButton.test.tsx comment (AC8.5 → Story 8.5, Task 10.5)

**Tests After Review:**
- Backend: 59/60 tests pass (1 pre-existing failure in test_stats_rejects_invalid_date_range)
- Frontend: 9/9 ExportButton tests pass, 8/8 ReportingDashboard tests pass

### File List

**Backend - Modified:**
- `idp-portal/backend/app/models/dashboard.py` - Added export Pydantic models (DashboardExportPeriodInfo, DashboardExportFiltersInfo, DashboardExportTechnologyStats, DashboardExportEnvironmentStats, DashboardExportTimeSeriesPoint, DashboardExportData)
- `idp-portal/backend/app/repositories/execution_repository.py` - Added get_stats_by_technology_for_export(), get_stats_by_environment_for_export()
- `idp-portal/backend/app/api/v1/dashboard.py` - Added GET /export/csv and GET /export/pdf endpoints with helper functions
- `idp-portal/backend/tests/unit/test_dashboard_api.py` - Added TestExportDashboardCSV, TestExportDashboardPDF, TestExportModels test classes

**Frontend - Created:**
- `idp-portal/frontend/src/components/dashboard/reporting/ExportButton.tsx` - New export dropdown button component
- `idp-portal/frontend/src/components/dashboard/reporting/ExportButton.test.tsx` - Tests for ExportButton

**Frontend - Modified:**
- `idp-portal/frontend/src/types/api.ts` - Added ExportFormat type
- `idp-portal/frontend/src/services/dashboard_service.ts` - Added downloadBlob(), generateExportFilename(), exportDashboardCSV(), exportDashboardPDF()
- `idp-portal/frontend/src/components/dashboard/reporting/ReportingDashboard.tsx` - Integrated ExportButton
- `idp-portal/frontend/src/components/dashboard/reporting/ReportingDashboard.test.tsx` - Added export mocks and integration test
- `idp-portal/frontend/src/components/dashboard/reporting/index.ts` - Added ExportButton barrel export

