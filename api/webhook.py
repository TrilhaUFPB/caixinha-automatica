import json
import os
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.payment_processor import process_pix_events

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps({"status": "ok", "message": "Webhook endpoint is active"}).encode()
        )

    def do_POST(self):
        try:
            # Validate HMAC secret
            if WEBHOOK_SECRET:
                parsed_url = urlparse(self.path)
                query_params = parse_qs(parsed_url.query)
                hmac_param = query_params.get("hmac", [""])[0]
                if hmac_param != WEBHOOK_SECRET:
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Unauthorized"}).encode())
                    return

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length else ""

            # Efí sends empty body on webhook registration confirmation
            if not body:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"200")
                return

            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
                return

            pix_list = payload.get("pix", [])

            if not pix_list:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"200")
                return

            print(f"[{datetime.now().isoformat()}] Processing {len(pix_list)} PIX event(s)")

            result = process_pix_events(pix_list)

            print(
                f"[{datetime.now().isoformat()}] Result: "
                f"processed={result['processed']}, "
                f"already_paid={result['already_paid']}, "
                f"not_found={result['not_found']}"
            )

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "received", "count": len(pix_list)}).encode())

        except Exception as e:
            print(f"[{datetime.now().isoformat()}] Webhook error: {e}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"200")
