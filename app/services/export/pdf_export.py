"""PDF export service for generating formatted project reports.

Generates an A4 PDF report using WeasyPrint with:
- Cover section with project name and generation date.
- Summary table with all 13 extracted fields.
- Checklist tables grouped by category.
- Citation appendix on a new page.

WeasyPrint is an optional dependency. If not installed, the function
raises a RuntimeError with installation instructions.
"""

from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select

from app.database import async_session_factory
from app.models.project import Project
from app.schemas.checklist import RequirementsChecklist
from app.schemas.extraction import ProjectSummary

# Human-readable labels for the 13 summary fields
FIELD_LABELS: dict[str, str] = {
    "project_name": "Project Name",
    "project_owner": "Project Owner",
    "location": "Location",
    "submission_deadline": "Submission Deadline",
    "bid_validity_period": "Bid Validity Period",
    "pre_bid_meeting_date": "Pre-Bid Meeting Date",
    "scope_of_work": "Scope of Work",
    "contract_type": "Contract Type",
    "tender_bond": "Tender Bond",
    "advance_payment": "Advance Payment",
    "retention_percentage": "Retention Percentage",
    "payment_terms": "Payment Terms",
    "stakeholders": "Stakeholders",
}


async def generate_pdf_report(project_id: int) -> BytesIO:
    """Generate a formatted PDF report for the given project.

    Args:
        project_id: Database ID of the project.

    Returns:
        BytesIO buffer containing the PDF document.

    Raises:
        ValueError: If the project does not exist.
        RuntimeError: If WeasyPrint is not installed.
    """
    # Lazy import -- graceful degradation if WeasyPrint is missing
    try:
        import weasyprint
    except ImportError:
        raise RuntimeError(
            "WeasyPrint is not installed. "
            "Install it with: pip install weasyprint "
            "(requires Pango system library)"
        )

    async with async_session_factory() as session:
        result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise ValueError(f"Project with id {project_id} not found")

    # Parse summary and checklist data
    summary_data: dict | None = None
    if project.summary_json:
        summary = ProjectSummary.model_validate_json(project.summary_json)
        summary_data = {}
        for field_key in FIELD_LABELS:
            field = getattr(summary, field_key, None)
            if field is not None:
                summary_data[field_key] = field.model_dump()
            else:
                summary_data[field_key] = {
                    "value": None,
                    "confidence_level": "low",
                    "citations": [],
                    "requires_review": True,
                }

    checklist_data: dict | None = None
    if project.checklist_json:
        checklist = RequirementsChecklist.model_validate_json(project.checklist_json)
        checklist_data = {
            "requirements": [item.model_dump() for item in checklist.requirements],
            "submission_documents": [item.model_dump() for item in checklist.submission_documents],
            "eligibility_criteria": [item.model_dump() for item in checklist.eligibility_criteria],
        }

    # Render HTML template
    templates_dir = Path(__file__).resolve().parent.parent.parent / "templates" / "reports"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template("pdf_report.html")

    from datetime import datetime

    html_string = template.render(
        project_name=project.name,
        summary=summary_data,
        checklist=checklist_data,
        field_labels=FIELD_LABELS,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    # Load CSS stylesheet
    css_path = Path(__file__).resolve().parent.parent.parent / "static" / "css" / "pdf_report.css"
    stylesheets = []
    if css_path.exists():
        stylesheets.append(weasyprint.CSS(filename=str(css_path)))

    # Generate PDF
    html_doc = weasyprint.HTML(string=html_string)
    pdf_bytes = html_doc.write_pdf(stylesheets=stylesheets)

    buffer = BytesIO(pdf_bytes)
    buffer.seek(0)
    return buffer
