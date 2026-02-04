import base64
import logging
import os
import smtplib
from email.mime.image import MIMEImage
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

    def _extract_image_data(self, data_uri: str) -> bytes:
        """Extract raw image bytes from a data URI."""
        if data_uri.startswith("data:"):
            # Format: data:image/png;base64,<base64_data>
            base64_data = data_uri.split(",", 1)[1]
            return base64.b64decode(base64_data)
        else:
            # Assume it's already base64 without prefix
            return base64.b64decode(data_uri)

    def _send_email(
        self, to: str, subject: str, html_content: str, qr_code_base64: Optional[str] = None
    ) -> bool:
        try:
            msg = MIMEMultipart("related")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.smtp_email}>"
            msg["To"] = to

            msg_alternative = MIMEMultipart("alternative")
            msg.attach(msg_alternative)

            html_part = MIMEText(html_content, "html")
            msg_alternative.attach(html_part)

            if qr_code_base64:
                image_data = self._extract_image_data(qr_code_base64)
                image = MIMEImage(image_data, _subtype="png")
                image.add_header("Content-ID", "<qrcode>")
                image.add_header("Content-Disposition", "inline", filename="qrcode.png")
                msg.attach(image)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_email, self.smtp_password)
                server.sendmail(self.smtp_email, to, msg.as_string())

            logger.info(f"Email sent to {to}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            raise

    def send_charge_email(
        self,
        to: str,
        name: str,
        qr_code_base64: str,
        pix_code: str,
        due_date: str,
        amount: str = "40.00",
    ) -> dict:
        html_content = self._render_template(
            "charge_email.html",
            name=name,
            qr_code_base64="cid:qrcode",
            pix_code=pix_code,
            due_date=due_date,
            amount=amount,
        )

        self._send_email(
            to=to,
            subject=f"[Caixinha Trilha] Cobrança de R$ {amount}",
            html_content=html_content,
            qr_code_base64=qr_code_base64,
        )

        logger.info(f"Charge email sent to {to}")
        return {"status": "sent", "to": to}

    def send_reminder_email(
        self,
        to: str,
        name: str,
        qr_code_base64: str,
        pix_code: str,
        amount: str = "40.00",
    ) -> dict:
        html_content = self._render_template(
            "reminder_email.html",
            name=name,
            qr_code_base64="cid:qrcode",
            pix_code=pix_code,
            amount=amount,
        )

        self._send_email(
            to=to,
            subject=f"[Caixinha Trilha] Lembrete de pagamento pendente - R$ {amount}",
            html_content=html_content,
            qr_code_base64=qr_code_base64,
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
