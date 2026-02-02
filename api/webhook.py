import base64
import json
import logging
import os
from datetime import date
from http.server import BaseHTTPRequestHandler
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EFI_WEBHOOK_IPS = {"34.193.116.226"}
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

MONTHS_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


class SheetsService:
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(self):
        self.credentials_base64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")
        self.spreadsheet_id = os.getenv("SPREADSHEET_ID")
        self._client: Optional[gspread.Client] = None
        self._spreadsheet = None

    def _get_client(self) -> gspread.Client:
        if self._client is None:
            credentials_json = base64.b64decode(self.credentials_base64).decode("utf-8")
            credentials_info = json.loads(credentials_json)
            credentials = Credentials.from_service_account_info(
                credentials_info, scopes=self.SCOPES
            )
            self._client = gspread.authorize(credentials)
        return self._client

    def _get_spreadsheet(self):
        if self._spreadsheet is None:
            client = self._get_client()
            self._spreadsheet = client.open_by_key(self.spreadsheet_id)
        return self._spreadsheet

    def get_members(self, sheet_name: str = "Sheet1") -> list:
        spreadsheet = self._get_spreadsheet()
        worksheet = spreadsheet.worksheet(sheet_name)
        return worksheet.get_all_records()

    def mark_as_paid(self, name: str, month: str, sheet_name: str = "Sheet1") -> bool:
        spreadsheet = self._get_spreadsheet()
        worksheet = spreadsheet.worksheet(sheet_name)
        headers = worksheet.row_values(1)
        
        name_col = None
        month_col = None
        for idx, header in enumerate(headers, start=1):
            if header in ["Nome", "Name"]:
                name_col = idx
            if header == month:
                month_col = idx

        if name_col is None or month_col is None:
            return False

        name_cells = worksheet.col_values(name_col)
        for idx, cell_name in enumerate(name_cells, start=1):
            if cell_name == name:
                worksheet.update_cell(idx, month_col, "Paid")
                return True
        return False


def validate_request(headers: dict, query_params: dict, client_ip: str) -> bool:
    if WEBHOOK_SECRET:
        hmac_param = query_params.get("hmac", "")
        if hmac_param != WEBHOOK_SECRET:
            logger.warning(f"Invalid HMAC: received '{hmac_param}'")
            return False

    if client_ip and client_ip not in EFI_WEBHOOK_IPS:
        x_forwarded_for = headers.get("x-forwarded-for", "")
        if x_forwarded_for:
            real_ip = x_forwarded_for.split(",")[0].strip()
            if real_ip not in EFI_WEBHOOK_IPS:
                logger.warning(f"Request from unauthorized IP: {real_ip}")

    return True


def get_current_month_column() -> str:
    today = date.today()
    month_name = MONTHS_PT.get(today.month, "")
    return f"{month_name}/{today.year}"


def process_pix_payment(pix_data: dict) -> dict:
    txid = pix_data.get("txid")
    end_to_end_id = pix_data.get("endToEndId")
    valor = pix_data.get("valor")
    horario = pix_data.get("horario")

    logger.info(f"Processing PIX payment: txid={txid}, e2e={end_to_end_id}, valor={valor}")

    if not txid:
        logger.warning("PIX without txid, skipping")
        return {"status": "skipped", "reason": "no txid"}

    try:
        sheets_service = SheetsService()
        members = sheets_service.get_members()

        member_name = None
        for member in members:
            name = member.get("Nome", member.get("Name", ""))
            for key, value in member.items():
                if key not in ["Nome", "Name", "Email"]:
                    if isinstance(value, str) and txid in value:
                        member_name = name
                        break
            if member_name:
                break

        if not member_name:
            logger.info(f"No member found with txid {txid}, payment may be manual")
            return {"status": "not_found", "txid": txid}

        month_column = get_current_month_column()
        sheets_service.mark_as_paid(member_name, month_column)

        logger.info(f"Successfully marked {member_name} as paid for {month_column}")
        return {
            "status": "success",
            "member": member_name,
            "month": month_column,
            "txid": txid,
        }

    except Exception as e:
        logger.error(f"Error processing payment: {e}")
        return {"status": "error", "error": str(e), "txid": txid}


def handler(request):
    if request.method == "GET":
        return {
            "statusCode": 200,
            "body": json.dumps({"status": "ok", "message": "Webhook endpoint is active"}),
        }

    if request.method != "POST":
        return {
            "statusCode": 405,
            "body": json.dumps({"error": "Method not allowed"}),
        }

    try:
        headers = dict(request.headers) if hasattr(request, "headers") else {}
        query_params = {}
        if hasattr(request, "query") and request.query:
            query_params = dict(request.query)

        client_ip = headers.get("x-real-ip", headers.get("x-forwarded-for", ""))

        if not validate_request(headers, query_params, client_ip):
            logger.warning("Webhook request validation failed")

        body = request.body if hasattr(request, "body") else ""
        if isinstance(body, bytes):
            body = body.decode("utf-8")

        if not body:
            logger.info("Empty body received (possibly mTLS test)")
            return {"statusCode": 200, "body": "200"}

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {body[:200]}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid JSON"}),
            }

        logger.info(f"Webhook payload received: {json.dumps(payload)[:500]}")

        pix_list = payload.get("pix", [])
        if not pix_list:
            logger.info("No pix array in payload")
            return {"statusCode": 200, "body": "200"}

        results = []
        for pix_data in pix_list:
            result = process_pix_payment(pix_data)
            results.append(result)

        return {
            "statusCode": 200,
            "body": json.dumps({"processed": len(results), "results": results}),
        }

    except Exception as e:
        logger.error(f"Unexpected error in webhook handler: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps({"status": "ok", "message": "Webhook endpoint is active"}).encode()
        )

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        class Request:
            pass

        request = Request()
        request.method = "POST"
        request.headers = dict(self.headers)
        request.body = body
        request.query = {}

        result = handler(request)

        self.send_response(result.get("statusCode", 200))
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(result.get("body", "").encode())
