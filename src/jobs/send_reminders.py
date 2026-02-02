import logging
import sys
from datetime import date

sys.path.insert(0, str(__file__).rsplit("/src", 1)[0])

from src.services.efi import EfiService
from src.services.email import EmailService
from src.services.sheets import SheetsService
from src.utils.business_days import get_current_month_column

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

CHARGE_AMOUNT = "40.00"


def run_send_reminders() -> dict:
    today = date.today()
    logger.info(f"Starting reminder job for {today}")

    month_column = get_current_month_column()
    logger.info(f"Looking for unpaid members in column: {month_column}")

    sheets_service = SheetsService()
    efi_service = EfiService()
    email_service = EmailService()

    try:
        unpaid_members = sheets_service.get_unpaid_members(month_column)
    except Exception as e:
        logger.error(f"Failed to get unpaid members: {e}")
        return {"status": "error", "error": str(e), "reminders": 0}

    if not unpaid_members:
        logger.info("No unpaid members found. No reminders to send.")
        return {"status": "success", "reminders": 0}

    logger.info(f"Found {len(unpaid_members)} unpaid members")

    successful_reminders = 0
    failed_reminders = 0
    results = []

    for member in unpaid_members:
        if not member.email:
            logger.warning(f"No email for member {member.name}, skipping")
            results.append({
                "name": member.name,
                "status": "skipped",
                "reason": "no_email",
            })
            continue

        try:
            logger.info(f"Processing member: {member.name} ({member.email})")

            charge = efi_service.create_pix_charge(
                valor=CHARGE_AMOUNT,
                nome_devedor=member.name,
                descricao=f"Caixinha Trilha - {month_column}",
            )

            logger.info(f"Created/retrieved charge for {member.name}: txid={charge.txid}")

            email_service.send_reminder_email(
                to=member.email,
                name=member.name,
                qr_code_base64=charge.qr_code_base64,
                pix_code=charge.copy_paste_code,
                amount=CHARGE_AMOUNT,
            )

            logger.info(f"Reminder email sent to {member.email}")

            successful_reminders += 1
            results.append({
                "name": member.name,
                "email": member.email,
                "txid": charge.txid,
                "status": "success",
            })

        except Exception as e:
            logger.error(f"Failed to send reminder to {member.name}: {e}")
            failed_reminders += 1
            results.append({
                "name": member.name,
                "email": member.email,
                "status": "error",
                "error": str(e),
            })

    logger.info(
        f"Reminder job complete. "
        f"Successful: {successful_reminders}, Failed: {failed_reminders}"
    )

    return {
        "status": "success",
        "reminders": successful_reminders,
        "failed": failed_reminders,
        "results": results,
    }


def main():
    result = run_send_reminders()

    if result["status"] == "error":
        logger.error(f"Job failed: {result.get('error')}")
        sys.exit(1)

    logger.info(f"Job completed: {result}")


if __name__ == "__main__":
    main()
