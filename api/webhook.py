import hashlib
import hmac
import json
import logging
import os
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.sheets import SheetsService
from src.utils.business_days import get_month_name_pt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EFI_WEBHOOK_IPS = {"34.193.116.226"}
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")


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
    month_name = get_month_name_pt(today.month)
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
            for month_col, status in member.payment_status.items():
                if isinstance(status, str) and txid in status:
                    member_name = member.name
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
