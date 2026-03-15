"""Register the PIX webhook URL with Efí.

Usage:
    python -m src.jobs.register_webhook --url https://YOUR-PROJECT.vercel.app/api/webhook/pix
    python -m src.jobs.register_webhook --check  # Check current webhook config

The script will:
1. Use skip-mTLS (required for Vercel/shared hosting)
2. Append ?hmac=SECRET&ignorar= to handle Efí's automatic /pix suffix
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, str(__file__).rsplit("/src", 1)[0])

from src.services.efi import EfiService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Register PIX webhook with Efí")
    parser.add_argument("--url", type=str, help="Base webhook URL (e.g. https://your-app.vercel.app/api/webhook/pix)")
    parser.add_argument("--check", action="store_true", help="Check current webhook configuration")
    args = parser.parse_args()

    efi_service = EfiService()

    if args.check:
        try:
            info = efi_service.get_webhook_info()
            logger.info(f"Current webhook config: {info}")
        except Exception as e:
            logger.error(f"No webhook registered or error: {e}")
        return

    if not args.url:
        parser.error("--url is required when not using --check")

    webhook_secret = os.getenv("WEBHOOK_SECRET", "")

    # Build URL: add hmac for auth + ignorar= to absorb Efí's /pix suffix
    url = args.url.rstrip("/")
    if webhook_secret:
        url = f"{url}?hmac={webhook_secret}&ignorar="
    else:
        url = f"{url}?ignorar="
        logger.warning("WEBHOOK_SECRET not set! Webhook will have no HMAC authentication.")

    logger.info(f"Registering webhook URL: {url}")
    logger.info("Using skip-mTLS (x-skip-mtls-checking: true)")

    try:
        result = efi_service.register_webhook(url, skip_mtls=True)
        logger.info(f"Webhook registered successfully: {result}")
    except Exception as e:
        logger.error(f"Failed to register webhook: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
