import os
from dataclasses import dataclass


@dataclass
class Config:
    google_credentials_base64: str
    spreadsheet_id: str
    form_responses_sheet_name: str

    pix_key: str
    pix_key_type: str
    pix_beneficiary_name: str

    google_form_url: str

    smtp_email: str
    smtp_password: str
    smtp_host: str
    smtp_port: int
    email_from_name: str

    default_charge_amount: str
    tecpred_charge_amount: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            google_credentials_base64=os.getenv("GOOGLE_CREDENTIALS_BASE64", ""),
            spreadsheet_id=os.getenv("SPREADSHEET_ID", ""),
            form_responses_sheet_name=os.getenv("FORM_RESPONSES_SHEET_NAME", "Respostas do formulário 1"),
            pix_key=os.getenv("PIX_KEY", ""),
            pix_key_type=os.getenv("PIX_KEY_TYPE", "email"),
            pix_beneficiary_name=os.getenv("PIX_BENEFICIARY_NAME", "Trilha UFPB"),
            google_form_url=os.getenv("GOOGLE_FORM_URL", ""),
            smtp_email=os.getenv("SMTP_EMAIL", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            email_from_name=os.getenv("EMAIL_FROM_NAME", "Caixinha Trilha"),
            default_charge_amount=os.getenv("DEFAULT_CHARGE_AMOUNT", "40.00"),
            tecpred_charge_amount=os.getenv("TECPRED_CHARGE_AMOUNT", "25.00"),
        )
