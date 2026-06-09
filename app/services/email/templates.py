"""Bilingual (en/ar) email body templates rendered with Jinja2.

Templates are HTML. Jinja2 autoescaping protects against injection from
user/supplier-controlled fields (scope text, custom messages). The plain-text
alternative is derived with html_to_text().
"""

from __future__ import annotations

import re

from jinja2 import Environment, select_autoescape

_env = Environment(autoescape=select_autoescape(default=True, default_for_string=True))

_RFQ_EN = """\
<html><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>Dear {{ contact_name }},</p>
<p>We invite you to submit your quotation for the following package:</p>
<div style="background:#f5f5f5;padding:15px;margin:20px 0;border-radius:5px;">
  <p><strong>Project:</strong> {{ project_name }}</p>
  <p><strong>Package:</strong> {{ package_name }}</p>
  <p><strong>Package Code:</strong> {{ package_code }}</p>
  <p><strong>Trade:</strong> {{ trade_category }}</p>
</div>
<p><strong>Scope of Work:</strong></p>
<p>{{ scope_description }}</p>
<p><strong>Submission Deadline:</strong> {{ deadline }}</p>
<p><strong>Submission Instructions:</strong> {{ submission_instructions }}</p>
{% if custom_message %}<p><strong>Additional Notes:</strong> {{ custom_message }}</p>{% endif %}
<p>Documents attached:</p>
<ul>
{% for att in attachments %}<li>{{ att.name }}</li>
{% else %}<li>No attachments</li>
{% endfor %}</ul>
<p>We look forward to receiving your competitive offer.</p>
<p>Best regards,<br>{{ sender_name }}<br>{{ company_name }}</p>
</body></html>
"""

_RFQ_AR = """\
<html><body dir="rtl" style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>السادة {{ contact_name }},</p>
<p>ندعوكم لتقديم عرض أسعاركم للحزمة التالية:</p>
<div style="background:#f5f5f5;padding:15px;margin:20px 0;border-radius:5px;">
  <p><strong>المشروع:</strong> {{ project_name }}</p>
  <p><strong>الحزمة:</strong> {{ package_name }}</p>
  <p><strong>رمز الحزمة:</strong> {{ package_code }}</p>
  <p><strong>التخصص:</strong> {{ trade_category }}</p>
</div>
<p><strong>نطاق العمل:</strong></p>
<p>{{ scope_description }}</p>
<p><strong>الموعد النهائي للتسليم:</strong> {{ deadline }}</p>
<p><strong>تعليمات التقديم:</strong> {{ submission_instructions }}</p>
{% if custom_message %}<p><strong>ملاحظات إضافية:</strong> {{ custom_message }}</p>{% endif %}
<p>المرفقات:</p>
<ul>
{% for att in attachments %}<li>{{ att.name }}</li>
{% else %}<li>لا توجد مرفقات</li>
{% endfor %}</ul>
<p>نتطلع إلى استلام عرضكم التنافسي.</p>
<p>مع خالص التحية،<br>{{ sender_name }}<br>{{ company_name }}</p>
</body></html>
"""

_REMINDER_EN = """\
<html><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>Dear {{ contact_name }},</p>
<p>A friendly reminder that the submission deadline for the following package is approaching:</p>
<div style="background:#fff3cd;padding:15px;margin:20px 0;border-radius:5px;border-left:4px solid #ffc107;">
  <p><strong>Package:</strong> {{ package_name }}</p>
  <p><strong>Deadline:</strong> {{ deadline }}</p>
  <p><strong>Time Remaining:</strong> {{ time_remaining }}</p>
</div>
<p>If you have already submitted your quotation, please disregard this message.</p>
<p>Best regards,<br>{{ sender_name }}<br>{{ company_name }}</p>
</body></html>
"""

_REMINDER_AR = """\
<html><body dir="rtl" style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>السادة {{ contact_name }},</p>
<p>تذكير ودي بأن الموعد النهائي لتسليم العروض للحزمة التالية يقترب:</p>
<div style="background:#fff3cd;padding:15px;margin:20px 0;border-radius:5px;border-left:4px solid #ffc107;">
  <p><strong>الحزمة:</strong> {{ package_name }}</p>
  <p><strong>الموعد النهائي:</strong> {{ deadline }}</p>
  <p><strong>الوقت المتبقي:</strong> {{ time_remaining }}</p>
</div>
<p>إذا كنتم قد قدمتم عرضكم بالفعل، يُرجى تجاهل هذه الرسالة.</p>
<p>مع خالص التحية،<br>{{ sender_name }}<br>{{ company_name }}</p>
</body></html>
"""

_CLARIFICATION_EN = """\
<html><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>Dear {{ contact_name }},</p>
<p>Thank you for your offer for <strong>{{ package_name }}</strong> ({{ project_name }}).
After reviewing it we require clarification on the following points:</p>
<ol>
{% for item in clarification_items %}<li>{{ item }}</li>
{% else %}<li>(no items specified)</li>
{% endfor %}</ol>
<p>Please respond by <strong>{{ response_deadline }}</strong>.</p>
<p>Best regards,<br>{{ sender_name }}<br>{{ company_name }}</p>
</body></html>
"""

_CLARIFICATION_AR = """\
<html><body dir="rtl" style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>السادة {{ contact_name }},</p>
<p>شكرًا لعرضكم الخاص بـ <strong>{{ package_name }}</strong> ({{ project_name }}).
بعد مراجعته نحتاج إلى توضيح النقاط التالية:</p>
<ol>
{% for item in clarification_items %}<li>{{ item }}</li>
{% else %}<li>(لا توجد بنود)</li>
{% endfor %}</ol>
<p>يرجى الرد بحلول <strong>{{ response_deadline }}</strong>.</p>
<p>مع خالص التحية،<br>{{ sender_name }}<br>{{ company_name }}</p>
</body></html>
"""

_TEMPLATES = {
    ("rfq", "en"): _RFQ_EN,
    ("rfq", "ar"): _RFQ_AR,
    ("reminder", "en"): _REMINDER_EN,
    ("reminder", "ar"): _REMINDER_AR,
    ("clarification", "en"): _CLARIFICATION_EN,
    ("clarification", "ar"): _CLARIFICATION_AR,
}

SUPPORTED_TYPES = ("rfq", "reminder", "clarification")
SUPPORTED_LANGS = ("en", "ar")


def render_body(email_type: str, language: str, context: dict) -> str:
    """Render an HTML email body. Falls back to English for unknown languages."""
    lang = language if language in SUPPORTED_LANGS else "en"
    source = _TEMPLATES.get((email_type, lang))
    if source is None:
        raise ValueError(f"No template for email_type={email_type!r}")
    # attachments is optional; default to empty list for the {% for %} loop.
    ctx = {
        "attachments": [],
        "custom_message": None,
        "time_remaining": "",
        "clarification_items": [],
        "response_deadline": "",
        **context,
    }
    return _env.from_string(source).render(**ctx)


def html_to_text(html: str) -> str:
    """Crude HTML->text for the plain-text MIME alternative."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = (
        text.replace("&nbsp;", " ").replace("&amp;", "&")
        .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    )
    return re.sub(r"\s+", " ", text).strip()
