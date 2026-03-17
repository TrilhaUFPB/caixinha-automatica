import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class EmailService:
    def __init__(
        self,
        smtp_email: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
    ):
        self.smtp_email = smtp_email or os.getenv("SMTP_EMAIL")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.from_name = os.getenv("EMAIL_FROM_NAME", "Caixinha Trilha")

        if not self.smtp_email or not self.smtp_password:
            logger.warning("SMTP credentials not configured")

    def _load_template(self, template_name: str) -> str:
        template_path = TEMPLATES_DIR / template_name
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()

    def _render_template(self, template_name: str, **kwargs) -> str:
        template = self._load_template(template_name)
        for key, value in kwargs.items():
            template = template.replace(f"{{{{{key}}}}}", str(value))
        return template

    def _send_email(self, to: str, subject: str, html_content: str) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.smtp_email}>"
            msg["To"] = to

            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_email, self.smtp_password)
                server.sendmail(self.smtp_email, to, msg.as_string())

            logger.info(f"Email sent to {to}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            raise

    @staticmethod
    def _build_pending_months_html(pending_months: list[str]) -> str:
        if not pending_months:
            return ""

        months_list = ", ".join(f"<strong>{m}</strong>" for m in pending_months)
        return (
            '<div style="background-color: #fff3e0; border: 1px solid #ffcc80; border-radius: 8px; '
            'padding: 16px; margin-bottom: 25px; text-align: center;">'
            '<p style="margin: 0 0 6px 0; font-size: 13px; color: #e65100;">Faturas em aberto:</p>'
            f'<p style="margin: 0; font-size: 15px; color: #333;">{months_list}</p>'
            '<p style="margin: 6px 0 0 0; font-size: 12px; color: #999;">'
            'Pague os meses pendentes.</p>'
            '</div>'
        )

    def send_charge_email(
        self,
        to: str,
        name: str,
        pix_key: str,
        pix_key_type: str,
        beneficiary_name: str,
        form_url: str,
        due_date: str,
        amount: str = "40.00",
        pending_months: list[str] | None = None,
    ) -> dict:
        html_content = self._render_template(
            "charge_email.html",
            name=name,
            pix_key=pix_key,
            pix_key_type=pix_key_type,
            beneficiary_name=beneficiary_name,
            form_url=form_url,
            due_date=due_date,
            amount=amount,
            pending_months_section=self._build_pending_months_html(pending_months or []),
        )

        self._send_email(
            to=to,
            subject=f"[Caixinha Trilha] Cobrança de R$ {amount}",
            html_content=html_content,
        )

        logger.info(f"Charge email sent to {to}")
        return {"status": "sent", "to": to}

    def send_reminder_email(
        self,
        to: str,
        name: str,
        pix_key: str,
        form_url: str,
        amount: str = "40.00",
        pending_months: list[str] | None = None,
    ) -> dict:
        html_content = self._render_template(
            "reminder_email.html",
            name=name,
            pix_key=pix_key,
            form_url=form_url,
            amount=amount,
            pending_months_section=self._build_pending_months_html(pending_months or []),
        )

        self._send_email(
            to=to,
            subject=f"[Caixinha Trilha] Lembrete de pagamento pendente - R$ {amount}",
            html_content=html_content,
        )

        logger.info(f"Reminder email sent to {to}")
        return {"status": "sent", "to": to}

    def send_confirmation_email(
        self,
        to: str,
        name: str,
        amount: str = "40.00",
        month: str = "",
    ) -> dict:
        month_text = f" de {month}" if month else ""
        html_content = self._render_template(
            "confirmation_email.html",
            name=name,
            amount=amount,
            month_text=month_text,
        )

        self._send_email(
            to=to,
            subject=f"[Caixinha Trilha] Pagamento confirmado - R$ {amount}",
            html_content=html_content,
        )

        logger.info(f"Confirmation email sent to {to}")
        return {"status": "sent", "to": to}
