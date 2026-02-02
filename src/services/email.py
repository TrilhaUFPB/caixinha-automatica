import logging
import os
from pathlib import Path
from typing import Optional

import resend

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class EmailService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        from_email: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("RESEND_API_KEY")
        self.from_email = from_email or os.getenv(
            "EMAIL_FROM", "Caixinha Trilha <caixinha@trilhaufpb.com.br>"
        )

        if not self.api_key:
            logger.warning("Resend API key not configured")
        else:
            resend.api_key = self.api_key

    def _load_template(self, template_name: str) -> str:
        template_path = TEMPLATES_DIR / template_name
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()

    def _render_template(self, template_name: str, **kwargs) -> str:
        template = self._load_template(template_name)
        for key, value in kwargs.items():
            template = template.replace(f"{{{{{key}}}}}", str(value))
        return template

    def send_charge_email(
        self,
        to: str,
        name: str,
        qr_code_base64: str,
        pix_code: str,
        due_date: str,
        amount: str = "40.00",
    ) -> dict:
        try:
            html_content = self._render_template(
                "charge_email.html",
                name=name,
                qr_code_base64=qr_code_base64,
                pix_code=pix_code,
                due_date=due_date,
                amount=amount,
            )

            params: resend.Emails.SendParams = {
                "from": self.from_email,
                "to": [to],
                "subject": f"[Caixinha Trilha] Cobrança de R$ {amount}",
                "html": html_content,
            }

            response = resend.Emails.send(params)
            logger.info(f"Charge email sent to {to}: id={response.get('id')}")
            return response

        except Exception as e:
            logger.error(f"Failed to send charge email to {to}: {e}")
            raise

    def send_reminder_email(
        self,
        to: str,
        name: str,
        qr_code_base64: str,
        pix_code: str,
        amount: str = "40.00",
    ) -> dict:
        try:
            html_content = self._render_template(
                "reminder_email.html",
                name=name,
                qr_code_base64=qr_code_base64,
                pix_code=pix_code,
                amount=amount,
            )

            params: resend.Emails.SendParams = {
                "from": self.from_email,
                "to": [to],
                "subject": f"[Caixinha Trilha] Lembrete de pagamento pendente - R$ {amount}",
                "html": html_content,
            }

            response = resend.Emails.send(params)
            logger.info(f"Reminder email sent to {to}: id={response.get('id')}")
            return response

        except Exception as e:
            logger.error(f"Failed to send reminder email to {to}: {e}")
            raise

    def send_confirmation_email(
        self,
        to: str,
        name: str,
        amount: str = "40.00",
        month: str = "",
    ) -> dict:
        try:
            month_text = f" de {month}" if month else ""
            html_content = self._render_template(
                "confirmation_email.html",
                name=name,
                amount=amount,
                month_text=month_text,
            )

            params: resend.Emails.SendParams = {
                "from": self.from_email,
                "to": [to],
                "subject": f"[Caixinha Trilha] Pagamento confirmado - R$ {amount}",
                "html": html_content,
            }

            response = resend.Emails.send(params)
            logger.info(f"Confirmation email sent to {to}: id={response.get('id')}")
            return response

        except Exception as e:
            logger.error(f"Failed to send confirmation email to {to}: {e}")
            raise
