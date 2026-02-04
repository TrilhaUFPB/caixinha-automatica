from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime
from urllib.parse import parse_qs, urlparse

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
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)

            if WEBHOOK_SECRET:
                hmac_param = query_params.get("hmac", [""])[0]
                if hmac_param != WEBHOOK_SECRET:
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Unauthorized"}).encode())
                    return

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length else ""

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

            for pix_data in pix_list:
                txid = pix_data.get("txid", "")
                valor = pix_data.get("valor", "")
                print(f"[{datetime.now().isoformat()}] PIX RECEIVED: txid={txid}, valor={valor}")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({"status": "received", "count": len(pix_list)}).encode()
            )

        except Exception as e:
            print(f"Error: {e}")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Internal server error"}).encode())
