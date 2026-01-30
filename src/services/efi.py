import logging
import os
import base64
import tempfile
from dataclasses import dataclass
from typing import Optional

from efipay import EfiPay

logger = logging.getLogger(__name__)


@dataclass
class PixCharge:
    txid: str
    status: str
    qr_code_base64: str
    copy_paste_code: str
    location_id: int
    valor: str


class EfiService:
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        pix_key: Optional[str] = None,
        certificate_base64: Optional[str] = None,
        sandbox: bool = False,
    ):
        self.client_id = client_id or os.getenv("EFI_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("EFI_CLIENT_SECRET")
        self.pix_key = pix_key or os.getenv("EFI_PIX_KEY")
        self.certificate_base64 = certificate_base64 or os.getenv("EFI_CERTIFICATE_BASE64")
        self.sandbox = sandbox or os.getenv("EFI_SANDBOX", "false").lower() == "true"

        if not all([self.client_id, self.client_secret, self.pix_key, self.certificate_base64]):
            logger.warning("Efi credentials not fully configured")

        self._efi: Optional[EfiPay] = None
        self._cert_path: Optional[str] = None

    def _get_certificate_path(self) -> str:
        if self._cert_path and os.path.exists(self._cert_path):
            return self._cert_path

        cert_bytes = base64.b64decode(self.certificate_base64)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".p12") as f:
            f.write(cert_bytes)
            self._cert_path = f.name

        return self._cert_path

    def _get_client(self) -> EfiPay:
        if self._efi is not None:
            return self._efi

        credentials = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "sandbox": self.sandbox,
            "certificate": self._get_certificate_path(),
        }

        self._efi = EfiPay(credentials)
        return self._efi

    def create_pix_charge(
        self,
        valor: str,
        nome_devedor: str,
        cpf_devedor: Optional[str] = None,
        descricao: str = "Caixinha do Trilha",
        expiracao_segundos: int = 86400 * 7,  # 7 days default
    ) -> PixCharge:
        efi = self._get_client()

        body = {
            "calendario": {"expiracao": expiracao_segundos},
            "valor": {"original": valor},
            "chave": self.pix_key,
            "solicitacaoPagador": descricao,
        }

        if cpf_devedor:
            body["devedor"] = {"cpf": cpf_devedor, "nome": nome_devedor}

        logger.info(f"Creating PIX charge for {nome_devedor}, value: R${valor}")

        response = efi.pix_create_immediate_charge(body=body)

        txid = response["txid"]
        status = response["status"]
        loc = response["loc"]
        location_id = loc["id"]

        qr_response = efi.pix_generate_qrcode(params={"id": location_id})

        qr_code_base64 = qr_response.get("imagemQrcode", "")
        copy_paste_code = qr_response.get("qrcode", "")

        logger.info(f"PIX charge created: txid={txid}, status={status}")

        return PixCharge(
            txid=txid,
            status=status,
            qr_code_base64=qr_code_base64,
            copy_paste_code=copy_paste_code,
            location_id=location_id,
            valor=valor,
        )

    def get_charge_status(self, txid: str) -> dict:
        efi = self._get_client()
        response = efi.pix_detail_charge(params={"txid": txid})
        return response

    def list_received_pix(self, start_date: str, end_date: str) -> list:
        efi = self._get_client()
        params = {"inicio": start_date, "fim": end_date}
        response = efi.pix_received_list(params=params)
        return response.get("pix", [])
