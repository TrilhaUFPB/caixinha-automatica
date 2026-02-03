import json
import logging
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EFI_WEBHOOK_IPS = {"34.193.116.226"}
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")


def validate_request(headers: dict, query_params: dict) -> bool:
    if WEBHOOK_SECRET:
        hmac_param = query_params.get("hmac", "")
        if hmac_param != WEBHOOK_SECRET:
            logger.warning(f"Invalid HMAC received")
            return False
    return True


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

        if not validate_request(headers, query_params):
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Unauthorized"}),
            }

        body = request.body if hasattr(request, "body") else ""
        if isinstance(body, bytes):
            body = body.decode("utf-8")

        if not body:
            logger.info("Empty body received (mTLS test)")
            return {"statusCode": 200, "body": "200"}

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid JSON"}),
            }

        pix_list = payload.get("pix", [])
        
        for pix_data in pix_list:
            txid = pix_data.get("txid", "")
            end_to_end_id = pix_data.get("endToEndId", "")
            valor = pix_data.get("valor", "")
            horario = pix_data.get("horario", "")
            
            logger.info(f"PIX RECEIVED: txid={txid}, e2e={end_to_end_id}, valor={valor}, horario={horario}")
            print(f"[{datetime.now().isoformat()}] PIX: txid={txid}, valor={valor}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "received",
                "count": len(pix_list),
                "message": "Payment notifications logged successfully"
            }),
        }

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
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
