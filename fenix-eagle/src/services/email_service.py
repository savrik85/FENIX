import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from jinja2 import Template

from ..config import settings
from ..database.models import NotificationLog, get_db
from .ai_service import AIService


logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications about new tenders"""

    def __init__(self):
        self.smtp_server = getattr(settings, "smtp_server", "smtp.gmail.com")
        self.smtp_port = getattr(settings, "smtp_port", 587)
        self.username = getattr(settings, "email_username", None)
        self.password = getattr(settings, "email_password", None)
        self.default_email = getattr(settings, "default_notification_email", None)
        self.ai_service = AIService()

    async def send_tender_notification(
        self,
        tenders: list[dict[str, Any]],
        recipients: list[str],
        config_name: str = "default",
    ) -> dict[str, Any]:
        """
        Send notification email about new tenders

        Args:
            tenders: List of tender data
            recipients: List of email addresses
            config_name: Name of the monitoring configuration

        Returns:
            Dict with success status and details
        """
        try:
            if not tenders:
                return {"success": False, "error": "No tenders to notify about"}

            if not recipients:
                if self.default_email:
                    recipients = [self.default_email]
                else:
                    return {"success": False, "error": "No recipients specified"}

            # Generate email content
            subject = self._generate_subject(tenders, config_name)
            html_body = await self._generate_html_body(tenders, config_name)
            text_body = await self._generate_text_body(tenders, config_name)

            # Send email
            success = await self._send_email(
                recipients=recipients,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )

            # Log the notification
            await self._log_notification(
                tenders=tenders,
                recipients=recipients,
                subject=subject,
                success=success,
                config_name=config_name,
            )

            return {
                "success": success,
                "recipients": recipients,
                "tender_count": len(tenders),
                "config_name": config_name,
            }

        except Exception as e:
            logger.error(f"Failed to send tender notification: {str(e)}")

            # Log failed notification
            await self._log_notification(
                tenders=tenders,
                recipients=recipients,
                subject=f"Failed notification for {config_name}",
                success=False,
                error_message=str(e),
                config_name=config_name,
            )

            return {"success": False, "error": str(e)}

    def _generate_subject(self, tenders: list[dict[str, Any]], config_name: str) -> str:
        """Generate email subject line"""
        count = len(tenders)

        if count == 1:
            return f"🎯 Nová nabídka oken/dveří ({config_name})"
        else:
            return f"🔥 {count} nových nabídek oken/dveří ({config_name})"

    async def _generate_html_body(
        self, tenders: list[dict[str, Any]], config_name: str
    ) -> str:
        """Generate HTML email body with data overview and AI-generated business email"""
        # Generate AI business emails for each tender
        ai_emails = []
        for tender in tenders:
            ai_email = await self.ai_service.generate_business_email(tender)
            ai_emails.append(ai_email)

        template_str = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }
                .header {
                    background-color: #2c3e50;
                    color: white;
                    padding: 20px;
                    text-align: center;
                    border-radius: 8px;
                }
                .section-divider {
                    margin: 40px 0;
                    padding: 20px 0;
                    border-top: 3px solid #3498db;
                    border-bottom: 1px solid #ecf0f1;
                }
                .section-title {
                    color: #2c3e50;
                    font-size: 24px;
                    font-weight: bold;
                    margin-bottom: 20px;
                    text-align: center;
                    background-color: #ecf0f1;
                    padding: 15px;
                    border-radius: 8px;
                }
                .tender-card {
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    margin: 20px 0;
                    padding: 20px;
                    background-color: #f9f9f9;
                }
                .tender-title {
                    color: #2c3e50;
                    font-size: 18px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }
                .tender-meta {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 15px;
                    margin-bottom: 15px;
                }
                .meta-item {
                    background-color: #ecf0f1;
                    padding: 5px 10px;
                    border-radius: 4px;
                    font-size: 12px;
                }
                .relevance-high { background-color: #d5f4e6; }
                .relevance-medium { background-color: #fef9e7; }
                .relevance-low { background-color: #fadbd8; }
                .description {
                    margin-bottom: 15px;
                    padding: 10px;
                    background-color: white;
                    border-radius: 4px;
                }
                .keywords {
                    margin-bottom: 15px;
                }
                .keyword-tag {
                    background-color: #3498db;
                    color: white;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-size: 11px;
                    margin-right: 5px;
                }
                .action-button {
                    background-color: #e74c3c;
                    color: white;
                    padding: 10px 20px;
                    text-decoration: none;
                    border-radius: 4px;
                    display: inline-block;
                    margin-top: 10px;
                }
                .ai-email-card {
                    border: 2px solid #27ae60;
                    border-radius: 8px;
                    margin: 20px 0;
                    padding: 20px;
                    background-color: #f8fff9;
                }
                .ai-email-title {
                    color: #27ae60;
                    font-size: 16px;
                    font-weight: bold;
                    margin-bottom: 15px;
                    display: flex;
                    align-items: center;
                }
                .ai-email-title:before {
                    content: "🤖";
                    margin-right: 10px;
                    font-size: 20px;
                }
                .ai-email-content {
                    background-color: white;
                    padding: 20px;
                    border-radius: 6px;
                    border-left: 4px solid #27ae60;
                    white-space: pre-line;
                    font-family: Georgia, serif;
                    line-height: 1.8;
                }
                .footer {
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                    font-size: 12px;
                    color: #666;
                    text-align: center;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎯 FENIX - Nové příležitosti</h1>
                <p>Nalezeny nové nabídky odpovídající vašim kritériím</p>
                <p><strong>Konfigurace:</strong> {{ config_name }}</p>
            </div>

            <!-- SEKCE 1: PŘEHLED ZÍSKANÝCH DAT -->
            <div class="section-divider">
                <div class="section-title">📋 ČÁST 1: PŘEHLED ZÍSKANÝCH DAT</div>
            </div>

            <div class="content">
                <p><strong>Celkem nalezeno nabídek:</strong> {{ tender_count }}</p>

                {% for tender in tenders %}
                <div class="tender-card">
                    <div class="tender-title">{{ tender.title }}</div>

                    <div class="tender-meta">
                        <span class="meta-item">
                        <strong>Zdroj:</strong> {{ tender.source }}</span>
                        <span class="meta-item">
                        <strong>Lokalita:</strong> {{ tender.location or 'Nezadáno' }}
                        </span>
                        <span class="meta-item"><strong>Datum:</strong>
                        {{ tender.posting_date }}</span>
                        {% if tender.estimated_value %}
                        <span class="meta-item"><strong>Hodnota:</strong>
                        ${{ "{:,.0f}".format(tender.estimated_value) }}</span>
                        {% endif %}
                        {% if tender.response_deadline %}
                        <span class="meta-item"><strong>Deadline:</strong>
                        {{ tender.response_deadline }}</span>
                        {% endif %}
                        {% if tender.relevance_score %}
                        <span class="meta-item {{ 'relevance-high' if
                        tender.relevance_score > 0.7 else 'relevance-medium' if
                        tender.relevance_score > 0.5 else 'relevance-low' }}">
                            <strong>Relevance:</strong>
                            {{ (tender.relevance_score * 100)|round }}%
                        </span>
                        {% endif %}
                    </div>

                    {% if tender.description %}
                    <div class="description">
                        <strong>Popis:</strong><br>
                        {{ tender.description[:300] }}{% if
                        tender.description|length > 300 %}...{% endif %}
                    </div>
                    {% endif %}

                    {% if tender.keywords_found %}
                    <div class="keywords">
                        <strong>Klíčová slova:</strong>
                        {% for keyword in tender.keywords_found %}
                        <span class="keyword-tag">{{ keyword }}</span>
                        {% endfor %}
                    </div>
                    {% endif %}

                    {% if tender.contact_info %}
                    <div class="contact">
                        <strong>Kontakt:</strong>
                        {% if tender.contact_info.get('email') %}
                        <br>📧 {{ tender.contact_info.email }}
                        {% endif %}
                        {% if tender.contact_info.get('phone') %}
                        <br>📞 {{ tender.contact_info.phone }}
                        {% endif %}
                    </div>
                    {% endif %}

                    <a href="{{ tender.source_url }}"
                    class="action-button" target="_blank">
                        🔗 Zobrazit nabídku
                    </a>
                </div>
                {% endfor %}
            </div>

            <!-- SEKCE 2: AI GENEROVANÉ OBCHODNÍ EMAILY -->
            <div class="section-divider">
                <div class="section-title">✉️ ČÁST 2: AI GENEROVANÉ OBCHODNÍ EMAILY</div>
                <p style="text-align: center; color: #666; font-style: italic;">
                    Následující emailové obsahy byly automaticky vygenerovány pomocí AI<br>
                    a jsou připraveny pro použití v produkčním režimu.
                </p>
            </div>

            {% for tender, ai_email in zip(tenders, ai_emails) %}
            <div class="ai-email-card">
                <div class="ai-email-title">
                    Obchodní email pro: {{ tender.title[:50] }}{% if tender.title|length > 50 %}...{% endif %}
                </div>
                <div class="ai-email-content">
                    {{ ai_email }}
                </div>
            </div>
            {% endfor %}

            <div class="footer">
                <p>📅 Generováno: {{ timestamp }}</p>
                <p>🤖 Automaticky generováno systémem FENIX</p>
                <p><strong>TESTOVACÍ REŽIM:</strong> Pro změnu nastavení kontaktujte administrátora</p>
            </div>
        </body>
        </html>
        """

        template = Template(template_str)

        return template.render(
            tenders=tenders,
            config_name=config_name,
            tender_count=len(tenders),
            ai_emails=ai_emails,
            timestamp=datetime.now().strftime("%d.%m.%Y %H:%M"),
        )

    async def _generate_text_body(
        self, tenders: list[dict[str, Any]], config_name: str
    ) -> str:
        """Generate plain text email body with data overview and AI-generated business emails"""
        # Generate AI business emails for each tender
        ai_emails = []
        for tender in tenders:
            ai_email = await self.ai_service.generate_business_email(tender)
            ai_emails.append(ai_email)

        lines = []
        lines.append("FENIX - Nové příležitosti")
        lines.append("=" * 50)
        lines.append(f"Konfigurace: {config_name}")
        lines.append(f"Nalezeno nabídek: {len(tenders)}")
        lines.append(f"Čas: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        lines.append("")

        # SEKCE 1: Přehled získaných dat
        lines.append("ČÁST 1: PŘEHLED ZÍSKANÝCH DAT")
        lines.append("=" * 50)
        lines.append("")

        for i, tender in enumerate(tenders, 1):
            lines.append(f"{i}. {tender['title']}")
            lines.append(f"   Zdroj: {tender['source']}")
            lines.append(f"   Lokalita: {tender.get('location', 'Nezadáno')}")

            if tender.get("estimated_value"):
                lines.append(f"   Hodnota: ${tender['estimated_value']:,.0f}")

            if tender.get("relevance_score"):
                lines.append(f"   Relevance: {tender['relevance_score'] * 100:.0f}%")

            if tender.get("keywords_found"):
                lines.append(f"   Klíčová slova: {', '.join(tender['keywords_found'])}")

            if tender.get("contact_info"):
                contact = tender.get("contact_info", {})
                if contact.get("email"):
                    lines.append(f"   Email: {contact['email']}")
                if contact.get("phone"):
                    lines.append(f"   Telefon: {contact['phone']}")

            lines.append(f"   URL: {tender['source_url']}")
            lines.append("")

        # SEKCE 2: AI generované obchodní emaily
        lines.append("")
        lines.append("ČÁST 2: AI GENEROVANÉ OBCHODNÍ EMAILY")
        lines.append("=" * 50)
        lines.append("Následující emailové obsahy byly automaticky vygenerovány")
        lines.append("pomocí AI a jsou připraveny pro použití v produkčním režimu.")
        lines.append("")

        for i, (tender, ai_email) in enumerate(
            zip(tenders, ai_emails, strict=False), 1
        ):
            lines.append(
                f"EMAIL {i}: {tender['title'][:60]}{'...' if len(tender['title']) > 60 else ''}"
            )
            lines.append("-" * 50)
            lines.append("")
            lines.append(ai_email)
            lines.append("")
            lines.append("-" * 50)
            lines.append("")

        lines.append("---")
        lines.append("TESTOVACÍ REŽIM: Automaticky generováno systémem FENIX")

        return "\n".join(lines)

    async def _send_email(
        self, recipients: list[str], subject: str, html_body: str, text_body: str
    ) -> bool:
        """Send email using SMTP"""
        try:
            # For localhost/mailhog testing, credentials are optional
            if self.smtp_server not in ["localhost", "mailhog"] and (
                not self.username or not self.password
            ):
                logger.error("Email credentials not configured")
                return False

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.username if self.username else "fenix@localhost"
            msg["To"] = ", ".join(recipients)

            # Attach text and HTML parts
            text_part = MIMEText(text_body, "plain", "utf-8")
            html_part = MIMEText(html_body, "html", "utf-8")

            msg.attach(text_part)
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.smtp_server not in ["localhost", "mailhog"]:
                    server.starttls()
                    server.login(self.username, self.password)

                # Use sendmail for better compatibility
                from_addr = self.username if self.username else "fenix@localhost"
                server.sendmail(from_addr, recipients, msg.as_string())

            logger.info(f"Email sent successfully to {recipients}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False

    async def _log_notification(
        self,
        tenders: list[dict[str, Any]],
        recipients: list[str],
        subject: str,
        success: bool,
        config_name: str,
        error_message: str = None,
    ):
        """Log notification attempt to database"""
        try:
            db = next(get_db())

            # Extract tender IDs
            tender_ids = []
            for tender in tenders:
                if "id" in tender:
                    tender_ids.append(str(tender["id"]))
                elif "tender_id" in tender:
                    tender_ids.append(str(tender["tender_id"]))

            # Create notification log entry
            log_entry = NotificationLog(
                tender_ids=tender_ids,
                email_recipients=recipients,
                subject=subject,
                success=success,
                error_message=error_message,
                notification_metadata={
                    "config_name": config_name,
                    "tender_count": len(tenders),
                    "timestamp": datetime.now().isoformat(),
                },
            )

            db.add(log_entry)
            db.commit()

        except Exception as e:
            logger.error(f"Failed to log notification: {str(e)}")
        finally:
            if "db" in locals():
                db.close()

    async def send_test_email(self, recipient: str) -> dict[str, Any]:
        """Send test email to verify configuration"""
        try:
            # Create test tender data
            test_tender = {
                "title": "Test nabídka - FENIX monitoring",
                "source": "test",
                "location": "Prague, Czech Republic",
                "posting_date": "2023-12-01",  # Simple string date
                "estimated_value": 100000,
                "relevance_score": 0.85,
                "keywords_found": ["windows", "glazing"],
                "description": (
                    "Toto je testovací nabídka pro ověření funkčnosti "
                    "FENIX email notifikací."
                ),
                "source_url": "https://example.com/test",
                "contact_info": {
                    "email": "test@example.com",
                    "phone": "+420 123 456 789",
                },
                "response_deadline": "2023-12-15",  # Simple string date
            }

            logger.info(f"Test tender data: {test_tender}")

            result = await self.send_tender_notification(
                tenders=[test_tender],
                recipients=[recipient],
                config_name="test_configuration",
            )

            return result

        except Exception as e:
            logger.error(f"Failed to send test email: {str(e)}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def send_empty_report_notification(
        self, recipients: list[str], config_name: str, scan_results: list[dict] = None
    ) -> dict[str, Any]:
        """Send notification when no new relevant tenders were found"""
        try:
            if not recipients:
                if self.default_email:
                    recipients = [self.default_email]
                else:
                    return {"success": False, "error": "No recipients specified"}

            # Generate email content
            subject = f"📊 Žádné nové nabídky - {config_name}"
            html_body = self._generate_empty_report_html(config_name, scan_results)
            text_body = self._generate_empty_report_text(config_name, scan_results)

            # Send email
            success = await self._send_email(
                recipients=recipients,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )

            # Log the notification
            await self._log_notification(
                tenders=[],
                recipients=recipients,
                subject=subject,
                success=success,
                config_name=config_name,
            )

            return {
                "success": success,
                "recipients": recipients,
                "tender_count": 0,
                "config_name": config_name,
                "type": "empty_report",
            }

        except Exception as e:
            logger.error(f"Failed to send empty report notification: {str(e)}")
            return {"success": False, "error": str(e)}

    def _generate_empty_report_html(
        self, config_name: str, scan_results: list[dict] = None
    ) -> str:
        """Generate HTML for empty report email"""
        template_str = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }
                .header {
                    background-color: #34495e;
                    color: white;
                    padding: 20px;
                    text-align: center;
                    border-radius: 8px;
                }
                .content {
                    margin: 20px 0;
                    padding: 20px;
                    background-color: #f8f9fa;
                    border-radius: 8px;
                    border-left: 4px solid #3498db;
                }
                .scan-summary {
                    background-color: #ecf0f1;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 15px 0;
                }
                .footer {
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                    font-size: 12px;
                    color: #666;
                    text-align: center;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 FENIX - Monitoring Report</h1>
                <p>Žádné nové relevantní nabídky</p>
                <p><strong>Konfigurace:</strong> {{ config_name }}</p>
            </div>

            <div class="content">
                <h2>📈 Výsledky scanu</h2>
                <p>Systém FENIX provedl scan všech zdrojů,<br>
                ale nenašel žádné nové relevantní nabídky.</p>

                {% if scan_results %}
                <div class="scan-summary">
                    <h3>Přehled zdrojů:</h3>
                    <ul>
                    {% for result in scan_results %}
                        <li><strong>{{ result.config }}:</strong>
                        {% if result.get('sources_scanned') %}
                            {{ result.sources_scanned }} zdrojů prohledáno
                        {% else %}
                            Scan dokončen
                        {% endif %}
                        </li>
                    {% endfor %}
                    </ul>
                </div>
                {% endif %}

                <p><strong>💡 Tip:</strong> Monitoring běží automaticky.<br>
                Budete informováni o nových relevantních nabídkách.</p>
            </div>

            <div class="footer">
                <p>📅 Generováno: {{ timestamp }}</p>
                <p>🤖 Automaticky generováno systémem FENIX</p>
                <p>Pro změnu nastavení kontaktujte administrátora</p>
            </div>
        </body>
        </html>
        """

        from jinja2 import Template

        template = Template(template_str)

        return template.render(
            config_name=config_name,
            scan_results=scan_results or [],
            timestamp=datetime.now().strftime("%d.%m.%Y %H:%M"),
        )

    def _generate_empty_report_text(
        self, config_name: str, scan_results: list[dict] = None
    ) -> str:
        """Generate plain text for empty report email"""
        lines = []
        lines.append("FENIX - Monitoring Report")
        lines.append("=" * 30)
        lines.append(f"Konfigurace: {config_name}")
        lines.append(f"Čas: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        lines.append("")
        lines.append("VÝSLEDEK: Žádné nové relevantní nabídky")
        lines.append("")
        lines.append("Systém FENIX provedl automatický scan všech")
        lines.append("nakonfigurovaných zdrojů, ale nenašel žádné")
        lines.append("nové relevantní nabídky odpovídající vašim kritériím.")
        lines.append("")

        if scan_results:
            lines.append("Přehled zdrojů:")
            for result in scan_results:
                sources_info = ""
                if result.get("sources_scanned"):
                    sources_info = f" ({result['sources_scanned']} zdrojů)"
                lines.append(f"- {result['config']}{sources_info}")
            lines.append("")

        lines.append("Monitoring běží automaticky každý den.")
        lines.append("Jakmile se objeví relevantní nabídky,")
        lines.append("budete okamžitě informováni emailem.")
        lines.append("")
        lines.append("---")
        lines.append("Automaticky generováno systémem FENIX")

        return "\n".join(lines)
