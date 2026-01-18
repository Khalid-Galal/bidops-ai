"""Email service for sending RFQs and notifications."""

import os
import smtplib
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db_context
from app.models import EmailLog, Package, Supplier
from app.models.base import EmailStatus, EmailType
from app.services.llm_service import LLMService

settings = get_settings()


class EmailService:
    """Service for email operations.

    Handles:
    - Email template rendering
    - RFQ email generation
    - Email sending via SMTP
    - Email tracking
    """

    # Email templates
    TEMPLATES = {
        "rfq": {
            "subject": "Request for Quotation - {package_name} | {project_name}",
            "body": """
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>Dear {contact_name},</p>

<p>We are pleased to invite you to submit your quotation for the following package:</p>

<div style="background-color: #f5f5f5; padding: 15px; margin: 20px 0; border-radius: 5px;">
    <p><strong>Project:</strong> {project_name}</p>
    <p><strong>Package:</strong> {package_name}</p>
    <p><strong>Package Code:</strong> {package_code}</p>
    <p><strong>Trade Category:</strong> {trade_category}</p>
</div>

<p><strong>Scope of Work:</strong></p>
<p>{scope_description}</p>

<p><strong>Submission Deadline:</strong> {deadline}</p>

<p><strong>Submission Instructions:</strong></p>
<p>{submission_instructions}</p>

<p>Please find the following documents attached:</p>
<ul>
{attachment_list}
</ul>

<p>Should you have any questions or require clarification, please do not hesitate to contact us.</p>

<p>We look forward to receiving your competitive offer.</p>

<p>Best regards,<br>
{sender_name}<br>
{company_name}</p>

<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
<p style="font-size: 12px; color: #666;">
This email was sent by {company_name}. If you believe you received this in error, please contact us.
</p>
</body>
</html>
""",
        },
        "reminder": {
            "subject": "Reminder: Quotation Due - {package_name} | {project_name}",
            "body": """
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>Dear {contact_name},</p>

<p>This is a friendly reminder that the submission deadline for the following package is approaching:</p>

<div style="background-color: #fff3cd; padding: 15px; margin: 20px 0; border-radius: 5px; border-left: 4px solid #ffc107;">
    <p><strong>Package:</strong> {package_name}</p>
    <p><strong>Deadline:</strong> {deadline}</p>
    <p><strong>Time Remaining:</strong> {time_remaining}</p>
</div>

<p>If you have already submitted your quotation, please disregard this message.</p>

<p>If you have any questions or need additional time, please let us know.</p>

<p>Best regards,<br>
{sender_name}<br>
{company_name}</p>
</body>
</html>
""",
        },
        "clarification": {
            "subject": "Request for Clarification - {package_name} | {project_name}",
            "body": """
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>Dear {contact_name},</p>

<p>Thank you for submitting your quotation for {package_name}.</p>

<p>After reviewing your offer, we require clarification on the following points:</p>

<div style="background-color: #f5f5f5; padding: 15px; margin: 20px 0; border-radius: 5px;">
{clarification_items}
</div>

<p>Please provide your response by <strong>{response_deadline}</strong>.</p>

<p>Best regards,<br>
{sender_name}<br>
{company_name}</p>
</body>
</html>
""",
        },
        "award": {
            "subject": "Letter of Intent - Award Notification | {package_name}",
            "body": """
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>Dear {contact_name},</p>

<p>We are pleased to inform you that your quotation for the following package has been selected:</p>

<div style="background-color: #d4edda; padding: 15px; margin: 20px 0; border-radius: 5px; border-left: 4px solid #28a745;">
    <p><strong>Project:</strong> {project_name}</p>
    <p><strong>Package:</strong> {package_name}</p>
    <p><strong>Award Amount:</strong> {award_amount}</p>
</div>

<p>This Letter of Intent serves as notification of our intention to award the above package to your company,
subject to successful contract negotiations and finalization of terms.</p>

<p>Please confirm your acceptance of this award within <strong>5 business days</strong>.</p>

<p>We look forward to working with you on this project.</p>

<p>Best regards,<br>
{sender_name}<br>
{company_name}</p>
</body>
</html>
""",
        },
        "regret": {
            "subject": "Tender Result Notification | {package_name}",
            "body": """
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>Dear {contact_name},</p>

<p>Thank you for submitting your quotation for {package_name}.</p>

<p>After careful evaluation of all received offers, we regret to inform you that your quotation
was not selected for this package.</p>

<p>We appreciate your time and effort in preparing the quotation and look forward to
inviting you to participate in future opportunities.</p>

<p>Best regards,<br>
{sender_name}<br>
{company_name}</p>
</body>
</html>
""",
        },
    }

    def __init__(self):
        """Initialize email service."""
        self.llm = LLMService()
        self.smtp_host = getattr(settings, "SMTP_HOST", "localhost")
        self.smtp_port = getattr(settings, "SMTP_PORT", 587)
        self.smtp_user = getattr(settings, "SMTP_USER", "")
        self.smtp_password = getattr(settings, "SMTP_PASSWORD", "")
        self.smtp_use_tls = getattr(settings, "SMTP_USE_TLS", True)
        self.from_address = getattr(settings, "EMAIL_FROM", "noreply@bidops.ai")
        self.from_name = getattr(settings, "EMAIL_FROM_NAME", "BidOps AI")

    async def create_rfq_email(
        self,
        package_id: int,
        supplier_id: int,
        attachments: Optional[list[str]] = None,
        custom_message: Optional[str] = None,
    ) -> EmailLog:
        """Create an RFQ email for a supplier.

        Args:
            package_id: Package ID
            supplier_id: Supplier ID
            attachments: List of file paths to attach
            custom_message: Optional custom message to include

        Returns:
            Created email log entry
        """
        async with get_db_context() as db:
            # Get package with project
            from app.models import Project
            result = await db.execute(
                select(Package)
                .options(selectinload(Package.items))
                .where(Package.id == package_id)
            )
            package = result.scalar_one_or_none()

            if not package:
                raise ValueError(f"Package not found: {package_id}")

            # Get project
            result = await db.execute(
                select(Project).where(Project.id == package.project_id)
            )
            project = result.scalar_one_or_none()

            # Get supplier
            result = await db.execute(
                select(Supplier).where(Supplier.id == supplier_id)
            )
            supplier = result.scalar_one_or_none()

            if not supplier:
                raise ValueError(f"Supplier not found: {supplier_id}")

            # Prepare template data
            template_data = {
                "contact_name": supplier.contact_name or "Sir/Madam",
                "project_name": project.name if project else "Project",
                "package_name": package.name,
                "package_code": package.code,
                "trade_category": package.trade_category.replace("_", " ").title(),
                "scope_description": package.description or "Please refer to attached documents.",
                "deadline": package.submission_deadline.strftime("%Y-%m-%d %H:%M") if package.submission_deadline else "To be confirmed",
                "submission_instructions": package.submission_instructions or "Please submit your quotation via email.",
                "sender_name": self.from_name,
                "company_name": getattr(settings, "COMPANY_NAME", "BidOps"),
            }

            # Build attachment list HTML
            attachment_list = ""
            attachment_data = []
            total_size = 0

            if attachments:
                for att_path in attachments:
                    path = Path(att_path)
                    if path.exists():
                        size = path.stat().st_size
                        total_size += size
                        attachment_list += f"<li>{path.name}</li>\n"
                        attachment_data.append({
                            "name": path.name,
                            "path": str(path),
                            "size": size,
                        })

            # Add package brief if exists
            if package.brief_path and Path(package.brief_path).exists():
                size = Path(package.brief_path).stat().st_size
                total_size += size
                attachment_list += f"<li>{Path(package.brief_path).name} (Package Brief)</li>\n"
                attachment_data.append({
                    "name": Path(package.brief_path).name,
                    "path": package.brief_path,
                    "size": size,
                })

            template_data["attachment_list"] = attachment_list or "<li>No attachments</li>"

            # Render template
            template = self.TEMPLATES["rfq"]
            subject = template["subject"].format(**template_data)
            body_html = template["body"].format(**template_data)

            if custom_message:
                # Insert custom message after scope
                body_html = body_html.replace(
                    "</ul>",
                    f"</ul>\n<p><strong>Additional Notes:</strong></p>\n<p>{custom_message}</p>"
                )

            # Create email log
            email_log = EmailLog(
                package_id=package_id,
                supplier_id=supplier_id,
                email_type=EmailType.RFQ,
                status=EmailStatus.DRAFT,
                to_addresses=supplier.emails,
                subject=subject,
                body_html=body_html,
                body_text=self._html_to_text(body_html),
                attachments=attachment_data,
                total_attachment_size=total_size,
                from_address=self.from_address,
            )
            db.add(email_log)
            await db.commit()
            await db.refresh(email_log)

            return email_log

    async def create_clarification_email(
        self,
        offer_id: int,
        clarification_items: list[str],
        response_days: int = 3,
    ) -> EmailLog:
        """Create a clarification request email.

        Args:
            offer_id: Supplier offer ID
            clarification_items: List of clarification items
            response_days: Days to respond

        Returns:
            Created email log entry
        """
        from app.models.supplier import SupplierOffer
        from datetime import timedelta

        async with get_db_context() as db:
            # Get offer with relationships
            result = await db.execute(
                select(SupplierOffer)
                .options(
                    selectinload(SupplierOffer.package),
                    selectinload(SupplierOffer.supplier),
                )
                .where(SupplierOffer.id == offer_id)
            )
            offer = result.scalar_one_or_none()

            if not offer:
                raise ValueError(f"Offer not found: {offer_id}")

            # Get project
            from app.models import Project
            result = await db.execute(
                select(Project).where(Project.id == offer.package.project_id)
            )
            project = result.scalar_one_or_none()

            # Format clarification items
            items_html = "<ol>\n"
            for item in clarification_items:
                items_html += f"<li>{item}</li>\n"
            items_html += "</ol>"

            response_deadline = datetime.now(timezone.utc) + timedelta(days=response_days)

            template_data = {
                "contact_name": offer.supplier.contact_name or "Sir/Madam",
                "project_name": project.name if project else "Project",
                "package_name": offer.package.name,
                "clarification_items": items_html,
                "response_deadline": response_deadline.strftime("%Y-%m-%d"),
                "sender_name": self.from_name,
                "company_name": getattr(settings, "COMPANY_NAME", "BidOps"),
            }

            template = self.TEMPLATES["clarification"]
            subject = template["subject"].format(**template_data)
            body_html = template["body"].format(**template_data)

            email_log = EmailLog(
                package_id=offer.package.id,
                supplier_id=offer.supplier.id,
                offer_id=offer_id,
                email_type=EmailType.CLARIFICATION,
                status=EmailStatus.DRAFT,
                to_addresses=offer.supplier.emails,
                subject=subject,
                body_html=body_html,
                body_text=self._html_to_text(body_html),
                from_address=self.from_address,
            )
            db.add(email_log)
            await db.commit()
            await db.refresh(email_log)

            return email_log

    async def generate_email_with_ai(
        self,
        email_type: str,
        context: dict,
    ) -> dict:
        """Generate email content using AI.

        Args:
            email_type: Type of email (rfq, clarification, etc.)
            context: Context data for generation

        Returns:
            Generated email content
        """
        prompt = f"""Generate a professional {email_type} email with the following context:

Context:
{context}

Requirements:
1. Professional and courteous tone
2. Clear and concise language
3. Include all relevant details
4. Format properly for HTML email

Respond with JSON:
{{
    "subject": "email subject",
    "body_html": "full HTML email body",
    "key_points": ["list of key points covered"]
}}
"""
        response = await self.llm.generate(
            prompt=prompt,
            task_type="document_generation",
            json_mode=True,
        )

        import json
        return json.loads(response)

    async def send_email(
        self,
        email_id: int,
    ) -> dict:
        """Send an email.

        Args:
            email_id: Email log ID

        Returns:
            Send result
        """
        async with get_db_context() as db:
            result = await db.execute(
                select(EmailLog).where(EmailLog.id == email_id)
            )
            email_log = result.scalar_one_or_none()

            if not email_log:
                raise ValueError(f"Email not found: {email_id}")

            if email_log.status == EmailStatus.SENT:
                return {"success": True, "message": "Email already sent"}

            try:
                # Create message
                msg = MIMEMultipart("alternative")
                msg["Subject"] = email_log.subject
                msg["From"] = f"{self.from_name} <{email_log.from_address}>"
                msg["To"] = ", ".join(email_log.to_addresses)

                if email_log.cc_addresses:
                    msg["Cc"] = ", ".join(email_log.cc_addresses)

                if email_log.reply_to:
                    msg["Reply-To"] = email_log.reply_to

                # Add body
                if email_log.body_text:
                    msg.attach(MIMEText(email_log.body_text, "plain"))
                msg.attach(MIMEText(email_log.body_html, "html"))

                # Add attachments
                if email_log.attachments:
                    for att in email_log.attachments:
                        path = Path(att["path"])
                        if path.exists():
                            with open(path, "rb") as f:
                                part = MIMEApplication(f.read(), Name=att["name"])
                                part["Content-Disposition"] = f'attachment; filename="{att["name"]}"'
                                msg.attach(part)

                # Send email
                if self.smtp_user:
                    with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                        if self.smtp_use_tls:
                            server.starttls()
                        server.login(self.smtp_user, self.smtp_password)

                        all_recipients = email_log.to_addresses.copy()
                        if email_log.cc_addresses:
                            all_recipients.extend(email_log.cc_addresses)
                        if email_log.bcc_addresses:
                            all_recipients.extend(email_log.bcc_addresses)

                        server.sendmail(
                            email_log.from_address,
                            all_recipients,
                            msg.as_string(),
                        )

                # Update status
                email_log.status = EmailStatus.SENT
                email_log.sent_at = datetime.now(timezone.utc)
                email_log.message_id = msg.get("Message-ID")
                await db.commit()

                # Update supplier stats
                if email_log.supplier_id and email_log.email_type == EmailType.RFQ:
                    supplier_result = await db.execute(
                        select(Supplier).where(Supplier.id == email_log.supplier_id)
                    )
                    supplier = supplier_result.scalar_one_or_none()
                    if supplier:
                        supplier.total_rfqs_sent += 1
                        await db.commit()

                return {"success": True, "message": "Email sent successfully"}

            except Exception as e:
                email_log.status = EmailStatus.FAILED
                email_log.error_message = str(e)
                email_log.retry_count += 1
                await db.commit()

                return {"success": False, "error": str(e)}

    async def send_bulk_rfq(
        self,
        package_id: int,
        supplier_ids: list[int],
        attachments: Optional[list[str]] = None,
    ) -> dict:
        """Send RFQ emails to multiple suppliers.

        Args:
            package_id: Package ID
            supplier_ids: List of supplier IDs
            attachments: Common attachments

        Returns:
            Bulk send results
        """
        results = {
            "total": len(supplier_ids),
            "created": 0,
            "sent": 0,
            "failed": 0,
            "errors": [],
        }

        for supplier_id in supplier_ids:
            try:
                # Create email
                email = await self.create_rfq_email(
                    package_id=package_id,
                    supplier_id=supplier_id,
                    attachments=attachments,
                )
                results["created"] += 1

                # Send email
                send_result = await self.send_email(email.id)
                if send_result["success"]:
                    results["sent"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "supplier_id": supplier_id,
                        "error": send_result.get("error", "Unknown error"),
                    })

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "supplier_id": supplier_id,
                    "error": str(e),
                })

        return results

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text.

        Args:
            html: HTML content

        Returns:
            Plain text content
        """
        import re

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", html)
        # Replace multiple spaces/newlines
        text = re.sub(r"\s+", " ", text)
        # Decode HTML entities
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')

        return text.strip()

    async def get_email_history(
        self,
        package_id: Optional[int] = None,
        supplier_id: Optional[int] = None,
        email_type: Optional[EmailType] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[EmailLog], int]:
        """Get email history with filters.

        Args:
            package_id: Filter by package
            supplier_id: Filter by supplier
            email_type: Filter by email type
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (emails list, total count)
        """
        async with get_db_context() as db:
            query = select(EmailLog)

            if package_id:
                query = query.where(EmailLog.package_id == package_id)

            if supplier_id:
                query = query.where(EmailLog.supplier_id == supplier_id)

            if email_type:
                query = query.where(EmailLog.email_type == email_type)

            # Count
            from sqlalchemy import func
            count_query = select(func.count()).select_from(query.subquery())
            total = (await db.execute(count_query)).scalar() or 0

            # Fetch
            query = query.order_by(EmailLog.created_at.desc())
            query = query.offset((page - 1) * page_size).limit(page_size)
            result = await db.execute(query)
            emails = list(result.scalars().all())

            return emails, total
