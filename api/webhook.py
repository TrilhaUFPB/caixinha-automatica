import json
import os
from datetime import datetime

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")


def handler(request):
    if request.method == "GET":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "ok", "message": "Webhook endpoint is active"}),
        }

    if request.method != "POST":
        return {
            "statusCode": 405,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Method not allowed"}),
        }

    try:
        query_params = dict(request.query) if hasattr(request, "query") and request.query else {}
        
        if WEBHOOK_SECRET:
            hmac_param = query_params.get("hmac", "")
            if hmac_param != WEBHOOK_SECRET:
                return {
                    "statusCode": 401,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({"error": "Unauthorized"}),
                }

        body = request.body if hasattr(request, "body") else ""
        if isinstance(body, bytes):
            body = body.decode("utf-8")

        if not body:
            return {"statusCode": 200, "body": "200"}

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Invalid JSON"}),
            }

        pix_list = payload.get("pix", [])
        
        for pix_data in pix_list:
            txid = pix_data.get("txid", "")
            valor = pix_data.get("valor", "")
            print(f"[{datetime.now().isoformat()}] PIX RECEIVED: txid={txid}, valor={valor}")

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "status": "received",
                "count": len(pix_list),
            }),
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error"}),
        }
