import logging
import sys
from datetime import date, timedelta

sys.path.insert(0, str(__file__).rsplit("/src", 1)[0])

from src.services.efi import EfiService
from src.services.email import EmailService
from src.services.sheets import SheetsService
from src.utils.business_days import (
    get_current_month_column,
    get_nth_business_day,
    is_nth_business_day,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

CHARGE_AMOUNT = "40.00"
CHARGE_EXPIRATION_DAYS = 7


def calculate_due_date() -> str:
    due_date = date.today() + timedelta(days=CHARGE_EXPIRATION_DAYS)
    return due_date.strftime("%d/%m/%Y")


def run_charge_generation(force: bool = False) -> dict:
    today = date.today()
    
    if not force and not is_nth_business_day(today, n=5):
        logger.info(f"Today ({today}) is not the 5th business day. Skipping.")
        return {"status": "skipped", "reason": "not_5th_business_day", "charges": 0}
    
    logger.info(f"Starting charge generation for {today}")
    
    month_column = get_current_month_column()
    logger.info(f"Looking for unpaid members in column: {month_column}")
    
    sheets_service = SheetsService()
    efi_service = EfiService()
    email_service = EmailService()
    
    try:
        unpaid_members = sheets_service.get_unpaid_members(month_column)
    except Exception as e:
        logger.error(f"Failed to get unpaid members: {e}")
        return {"status": "error", "error": str(e), "charges": 0}
    
    if not unpaid_members:
        logger.info("No unpaid members found.")
        return {"status": "success", "charges": 0}
    
    logger.info(f"Found {len(unpaid_members)} unpaid members")
    
    due_date = calculate_due_date()
    successful_charges = 0
    failed_charges = 0
    results = []
    
    for member in unpaid_members:
        try:
            logger.info(f"Processing member: {member.name} ({member.email})")
            
            charge = efi_service.create_pix_charge(
                valor=CHARGE_AMOUNT,
                nome_devedor=member.name,
                descricao=f"Caixinha Trilha - {month_column}",
            )
            
            logger.info(f"Created charge for {member.name}: txid={charge.txid}")
            
            if member.email:
                email_service.send_charge_email(
                    to=member.email,
                    name=member.name,
                    qr_code_base64=charge.qr_code_base64,
                    pix_code=charge.copy_paste_code,
                    due_date=due_date,
                    amount=CHARGE_AMOUNT,
                )
                logger.info(f"Email sent to {member.email}")
            else:
                logger.warning(f"No email for member {member.name}, skipping email")
            
            successful_charges += 1
            results.append({
                "name": member.name,
                "email": member.email,
                "txid": charge.txid,
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
        f"Charge generation complete. "
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
    
    parser = argparse.ArgumentParser(description="Generate PIX charges for unpaid members")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force execution even if not the 5th business day",
    )
    args = parser.parse_args()
    
    result = run_charge_generation(force=args.force)
    
    if result["status"] == "error":
        logger.error(f"Job failed: {result.get('error')}")
        sys.exit(1)
    
    logger.info(f"Job completed: {result}")


if __name__ == "__main__":
    main()
