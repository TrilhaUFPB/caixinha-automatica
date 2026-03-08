import logging
import sys
from datetime import date, timedelta

sys.path.insert(0, str(__file__).rsplit("/src", 1)[0])

from src.services.efi import EfiService
from src.services.payment_processor import process_pix_events

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_process_payments(days_back: int = 3) -> dict:
    """Reconciliation job: polls Efí for received PIX and processes them.

    This is a fallback for the webhook. Runs daily to catch any missed payments.
    """
    today = date.today()
    start_date = today - timedelta(days=days_back)

    logger.info(f"Reconciliation: checking payments from {start_date} to {today}")

    efi_service = EfiService()

    start_iso = start_date.isoformat() + "T00:00:00Z"
    end_iso = today.isoformat() + "T23:59:59Z"

    try:
        pix_list = efi_service.list_received_pix(start_iso, end_iso)
    except Exception as e:
        logger.error(f"Failed to list received PIX: {e}")
        return {"status": "error", "error": str(e), "processed": 0}

    if not pix_list:
        logger.info("No PIX payments found in the period.")
        return {"status": "success", "processed": 0}

    logger.info(f"Found {len(pix_list)} PIX payments to reconcile")

    return process_pix_events(pix_list, efi_service=efi_service)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Reconcile received PIX payments")
    parser.add_argument(
        "--days",
        type=int,
        default=3,
        help="Number of days to look back for payments (default: 3)",
    )
    args = parser.parse_args()

    result = run_process_payments(days_back=args.days)

    if result["status"] == "error":
        logger.error(f"Job failed: {result.get('error')}")
        sys.exit(1)

    logger.info(f"Job completed: {result}")


if __name__ == "__main__":
    main()
