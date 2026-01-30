import os
from dataclasses import dataclass


@dataclass
class Config:
    # Efi (Gerencianet) credentials
    efi_client_id: str
    efi_client_secret: str
    efi_certificate_base64: str
    efi_pix_key: str
    efi_sandbox: bool

    # Google Sheets
    google_credentials_base64: str
    spreadsheet_id: str

    # Email (Resend)
    resend_api_key: str
    email_from: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            efi_client_id=os.getenv("EFI_CLIENT_ID", ""),
            efi_client_secret=os.getenv("EFI_CLIENT_SECRET", ""),
            efi_certificate_base64=os.getenv("EFI_CERTIFICATE_BASE64", ""),
            efi_pix_key=os.getenv("EFI_PIX_KEY", ""),
            efi_sandbox=os.getenv("EFI_SANDBOX", "false").lower() == "true",
            google_credentials_base64=os.getenv("GOOGLE_CREDENTIALS_BASE64", ""),
            spreadsheet_id=os.getenv("SPREADSHEET_ID", ""),
            resend_api_key=os.getenv("RESEND_API_KEY", ""),
            email_from=os.getenv("EMAIL_FROM", "caixinha@trilha.ufpb.br"),
        )
