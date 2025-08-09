import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from jinja2 import Template

from ..config import settings
from ..database.models import NotificationLog, get_db


logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications about new tenders"""

    def __init__(self):
        self.smtp_server = getattr(settings, "smtp_server", "smtp.gmail.com")
        self.smtp_port = getattr(settings, "smtp_port", 587)
        self.username = getattr(settings, "email_username", None)
        self.password = getattr(settings, "email_password", None)
        self.default_email = getattr(settings, "default_notification_email", None)

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
            html_body = self._generate_html_body(tenders, config_name)
            text_body = self._generate_text_body(tenders, config_name)

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

    def _generate_html_body(
        self, tenders: list[dict[str, Any]], config_name: str
    ) -> str:
        """Generate HTML email body"""
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

            <div class="content">
                <h2>📋 Přehled nabídek ({{ tender_count }})</h2>

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
                        {{ tender.posting_date[:10] if tender.posting_date
                           else 'Nezadáno' }}</span>
                        {% if tender.estimated_value %}
                        <span class="meta-item"><strong>Hodnota:</strong>
                        ${{ "{:,.0f}".format(tender.estimated_value) }}</span>
                        {% endif %}
                        {% if tender.response_deadline %}
                        <span class="meta-item"><strong>Deadline:</strong>
                        {{ tender.response_deadline[:10] if tender.response_deadline
                           else 'Nezadáno' }}</span>
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

            <div class="footer">
                <p>📅 Generováno: {{ timestamp }}</p>
                <p>🤖 Automaticky generováno systémem FENIX</p>
                <p>Pro změnu nastavení kontaktujte administrátora</p>
            </div>
        </body>
        </html>
        """

        template = Template(template_str)

        return template.render(
            tenders=tenders,
            config_name=config_name,
            tender_count=len(tenders),
            timestamp=datetime.now().strftime("%d.%m.%Y %H:%M"),
        )

    def _generate_text_body(
        self, tenders: list[dict[str, Any]], config_name: str
    ) -> str:
        """Generate plain text email body"""
        lines = []
        lines.append("FENIX - Nové příležitosti")
        lines.append("=" * 30)
        lines.append(f"Konfigurace: {config_name}")
        lines.append(f"Nalezeno nabídek: {len(tenders)}")
        lines.append(f"Čas: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
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

            lines.append(f"   URL: {tender['source_url']}")
            lines.append("")

        lines.append("---")
        lines.append("Automaticky generováno systémem FENIX")

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
                "posting_date": datetime.now(),
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
            }

            result = await self.send_tender_notification(
                tenders=[test_tender],
                recipients=[recipient],
                config_name="test_configuration",
            )

            return result

        except Exception as e:
            logger.error(f"Failed to send test email: {str(e)}")
            return {"success": False, "error": str(e)}
