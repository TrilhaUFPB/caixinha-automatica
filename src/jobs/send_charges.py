import logging
import os
import sys
from datetime import date

sys.path.insert(0, str(__file__).rsplit("/src", 1)[0])

from src.services.email import EmailService
from src.services.sheets import SheetsService
from src.utils.business_days import (
    get_current_month_column,
    get_unpaid_months,
    is_nth_business_day,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

CHARGE_AMOUNT = os.getenv("DEFAULT_CHARGE_AMOUNT", "40.00")
TECPRED_CHARGE_AMOUNT = os.getenv("TECPRED_CHARGE_AMOUNT", "25.00")
TECPRED_MEMBERS = {"malu quintela", "malu uchoa", "nicole", "joaquim"}

def get_charge_amount(member_name: str) -> str:
    return TECPRED_CHARGE_AMOUNT if member_name.strip().lower() in TECPRED_MEMBERS else CHARGE_AMOUNT


def run_send_charges(force: bool = False, send_email: bool = True, member_filter: str = None) -> dict:
    today = date.today()

    if not force and not is_nth_business_day(today, n=5):
        logger.info(f"Today ({today}) is not the 5th business day. Skipping.")
        return {"status": "skipped", "reason": "not_5th_business_day", "charges": 0}

    logger.info(f"Starting charge emails for {today}")

    month_column = get_current_month_column()
    logger.info(f"Looking for unpaid members in column: {month_column}")

    pix_key = os.getenv("PIX_KEY", "")
    pix_key_type = os.getenv("PIX_KEY_TYPE", "email")
    beneficiary_name = os.getenv("PIX_BENEFICIARY_NAME", "Trilha UFPB")
    form_url = os.getenv("GOOGLE_FORM_URL", "")

    sheets_service = SheetsService()
    email_service = EmailService()

    try:
        unpaid_members = sheets_service.get_unpaid_members(month_column)
    except Exception as e:
        logger.error(f"Failed to get unpaid members: {e}")
        return {"status": "error", "error": str(e), "charges": 0}

    if member_filter:
        unpaid_members = [m for m in unpaid_members if m.name.strip().lower() == member_filter.lower()]

    if not unpaid_members:
        logger.info("No unpaid members found.")
        return {"status": "success", "charges": 0}

    logger.info(f"Found {len(unpaid_members)} unpaid members")

    successful_charges = 0
    failed_charges = 0
    results = []

    for member in unpaid_members:
        try:
            amount = get_charge_amount(member.name)
            logger.info(f"Processing member: {member.name} ({member.email}), amount: R${amount}")

            pending = get_unpaid_months(member.payment_status, month_column)

            if send_email:
                if member.email:
                    email_service.send_charge_email(
                        to=member.email,
                        name=member.name,
                        pix_key=pix_key,
                        pix_key_type=pix_key_type,
                        beneficiary_name=beneficiary_name,
                        form_url=form_url,
                        amount=amount,
                        pending_months=pending,
                    )
                    logger.info(f"Email sent to {member.email}")
                else:
                    logger.warning(f"No email for member {member.name}, skipping email")
            else:
                logger.info(f"Email skipped for {member.name} (--no-email)")

            successful_charges += 1
            results.append({
                "name": member.name,
                "email": member.email,
                "status": "success",
            })

        except Exception as e:
            logger.error(f"Failed to process member {member.name}: {e}")
            failed_charges += 1
            results.append({
                "name": member.name,
                "email": member.email,
                "status": "error",
                "error": str(e),
            })

    logger.info(
        f"Charge emails complete. "
        f"Successful: {successful_charges}, Failed: {failed_charges}"
    )

    return {
        "status": "success",
        "charges": successful_charges,
        "failed": failed_charges,
        "results": results,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Send PIX charge emails to unpaid members")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force execution even if not the 5th business day",
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Skip sending emails (dry run)",
    )
    parser.add_argument(
        "--member",
        type=str,
        help="Send charge only for a specific member (by name)",
    )
    args = parser.parse_args()

    result = run_send_charges(force=args.force, send_email=not args.no_email, member_filter=args.member)

    if result["status"] == "error":
        logger.error(f"Job failed: {result.get('error')}")
        sys.exit(1)

    logger.info(f"Job completed: {result}")


if __name__ == "__main__":
    main()
