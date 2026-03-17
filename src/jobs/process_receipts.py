import logging
import os
import sys

sys.path.insert(0, str(__file__).rsplit("/src", 1)[0])

from src.services.email import EmailService
from src.services.sheets import SheetsService
from src.utils.business_days import get_month_name_pt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

CHARGE_AMOUNT = os.getenv("DEFAULT_CHARGE_AMOUNT", "40.00")
TECPRED_CHARGE_AMOUNT = os.getenv("TECPRED_CHARGE_AMOUNT", "25.00")
TECPRED_MEMBERS = {"malu quintela", "malu uchoa", "nicole", "joaquim"}

VALID_MONTHS = {
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
}


def get_expected_amount(member_name: str) -> str:
    return TECPRED_CHARGE_AMOUNT if member_name.strip().lower() in TECPRED_MEMBERS else CHARGE_AMOUNT


def normalize_month(month_str: str) -> str:
    """Normalize month name to title case (e.g. 'março' -> 'Março')."""
    month = month_str.strip().lower()
    if month in VALID_MONTHS:
        return month.capitalize()
    return ""


def find_member_by_response(members, email: str, name: str):
    """Match form response to a member. Prefers email match, falls back to name."""
    email_lower = email.strip().lower()
    for member in members:
        if member.email.strip().lower() == email_lower:
            return member

    name_lower = name.strip().lower()
    for member in members:
        if member.name.strip().lower() == name_lower:
            return member

    return None


def run_process_receipts() -> dict:
    logger.info("Starting receipt processing job")

    form_sheet_name = os.getenv("FORM_RESPONSES_SHEET_NAME", "Respostas do formulário 1")

    sheets_service = SheetsService()
    email_service = EmailService()

    try:
        responses = sheets_service.get_unprocessed_responses(form_sheet_name)
    except Exception as e:
        logger.error(f"Failed to get form responses: {e}")
        return {"status": "error", "error": str(e), "processed": 0}

    if not responses:
        logger.info("No unprocessed form responses found.")
        return {"status": "success", "processed": 0, "errors": 0, "already_paid": 0}

    logger.info(f"Found {len(responses)} unprocessed responses")

    try:
        members = sheets_service.get_members()
    except Exception as e:
        logger.error(f"Failed to get members: {e}")
        return {"status": "error", "error": str(e), "processed": 0}

    processed = 0
    errors = 0
    already_paid = 0
    results = []

    for response in responses:
        try:
            logger.info(f"Processing response: {response.name} ({response.email}) - {response.month}")

            month = normalize_month(response.month)
            if not month:
                logger.warning(f"Invalid month '{response.month}' for response from {response.name}")
                sheets_service.mark_response_as_processed(
                    form_sheet_name, response.row, "Erro: mês inválido"
                )
                errors += 1
                results.append({
                    "name": response.name,
                    "status": "error",
                    "reason": f"invalid_month: {response.month}",
                })
                continue

            member = find_member_by_response(members, response.email, response.name)
            if not member:
                logger.warning(f"Member not found for response: {response.name} ({response.email})")
                sheets_service.mark_response_as_processed(
                    form_sheet_name, response.row, "Erro: membro não encontrado"
                )
                errors += 1
                results.append({
                    "name": response.name,
                    "email": response.email,
                    "status": "error",
                    "reason": "member_not_found",
                })
                continue

            current_status = member.payment_status.get(month, "").lower()
            if current_status in ("paid", "pago"):
                logger.info(f"{member.name} already paid for {month}")
                sheets_service.mark_response_as_processed(
                    form_sheet_name, response.row, "Já pago"
                )
                already_paid += 1
                results.append({
                    "name": member.name,
                    "month": month,
                    "status": "already_paid",
                })
                continue

            expected_amount = get_expected_amount(member.name)
            response_amount = response.amount.replace(",", ".").replace("R$", "").strip()
            try:
                if float(response_amount) != float(expected_amount):
                    logger.warning(
                        f"Amount mismatch for {member.name}: "
                        f"expected R${expected_amount}, got R${response_amount}"
                    )
            except ValueError:
                logger.warning(f"Could not parse amount '{response.amount}' for {response.name}")

            sheets_service.mark_as_paid(member.name, month)
            sheets_service.mark_response_as_processed(form_sheet_name, response.row)

            if member.email:
                try:
                    email_service.send_confirmation_email(
                        to=member.email,
                        name=member.name,
                        amount=expected_amount,
                        month=month,
                    )
                except Exception as email_err:
                    logger.error(f"Failed to send confirmation email to {member.email}: {email_err}")

            processed += 1
            results.append({
                "name": member.name,
                "month": month,
                "status": "processed",
            })
            logger.info(f"Marked {member.name} as paid for {month}")

        except Exception as e:
            logger.error(f"Failed to process response from {response.name}: {e}")
            errors += 1
            results.append({
                "name": response.name,
                "status": "error",
                "reason": str(e),
            })

    logger.info(
        f"Receipt processing complete. "
        f"Processed: {processed}, Errors: {errors}, Already paid: {already_paid}"
    )

    return {
        "status": "success",
        "processed": processed,
        "errors": errors,
        "already_paid": already_paid,
        "results": results,
    }


def main():
    result = run_process_receipts()

    if result["status"] == "error":
        logger.error(f"Job failed: {result.get('error')}")
        sys.exit(1)

    logger.info(f"Job completed: {result}")


if __name__ == "__main__":
    main()
