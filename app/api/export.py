"""Export API endpoints for downloading project reports.

Routes:
    GET /api/projects/{project_id}/export/excel - Download Excel report
    GET /api/projects/{project_id}/export/pdf   - Download PDF report
"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.export.excel_export import generate_excel_report
from app.services.export.pdf_export import generate_pdf_report

logger = logging.getLogger(__name__)

router = APIRouter(tags=["export"])


@router.get("/projects/{project_id}/export/excel")
async def export_excel(project_id: int):
    """Download an Excel report for the given project.

    Returns a .xlsx file with Summary and Requirements Checklist sheets.
    """
    try:
        buffer = await generate_excel_report(project_id)
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="project_{project_id}_report.xlsx"',
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Excel export failed for project %s", project_id)
        raise HTTPException(status_code=500, detail=f"Excel export failed: {exc}")


@router.get("/projects/{project_id}/export/pdf")
async def export_pdf(project_id: int):
    """Download a PDF report for the given project.

    Returns a formatted A4 PDF with summary, checklist, and citation appendix.
    Requires WeasyPrint to be installed (with Pango system library).
    """
    try:
        buffer = await generate_pdf_report(project_id)
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="project_{project_id}_report.pdf"',
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        # WeasyPrint not installed
        raise HTTPException(status_code=501, detail=str(exc))
    except Exception as exc:
        logger.exception("PDF export failed for project %s", project_id)
        raise HTTPException(status_code=500, detail=f"PDF export failed: {exc}")
