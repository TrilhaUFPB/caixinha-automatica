import logging
import sys

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

TEST_AMOUNT = "0.01"  # R$0.01 para teste


def run_test_charge() -> dict:
    logger.info("=== RUNNING TEST CHARGE (R$0.01) ===")
    
    month_column = get_current_month_column()
    logger.info(f"Current month: {month_column}")
    
    sheets_service = SheetsService()
    efi_service = EfiService()
    email_service = EmailService()
    
    # Usar aba "teste" em vez da aba de produção
    try:
        unpaid_members = sheets_service.get_unpaid_members(month_column, sheet_name="teste")
    except Exception as e:
        logger.error(f"Failed to get members from 'teste' sheet: {e}")
        return {"status": "error", "error": str(e)}
    
    if not unpaid_members:
        logger.info("No unpaid members in 'teste' sheet")
        return {"status": "success", "message": "No unpaid members", "charges": 0}
    
    # Processar apenas o primeiro membro para teste
    member = unpaid_members[0]
    logger.info(f"Testing with: {member.name} ({member.email})")
    
    try:
        charge = efi_service.create_pix_charge(
            valor=TEST_AMOUNT,
            nome_devedor=member.name,
            descricao=f"TESTE Caixinha - {month_column}",
        )
        
        logger.info(f"Created PIX charge: txid={charge.txid}")
        logger.info(f"PIX code: {charge.copy_paste_code[:50]}...")
        
        if member.email:
            email_service.send_charge_email(
                to=member.email,
                name=member.name,
                qr_code_base64=charge.qr_code_base64,
                pix_code=charge.copy_paste_code,
                due_date="07/02/2026",
                amount=TEST_AMOUNT,
            )
            logger.info(f"Email sent to {member.email}")
        
        return {
            "status": "success",
            "name": member.name,
            "email": member.email,
            "txid": charge.txid,
            "amount": TEST_AMOUNT,
        }
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return {"status": "error", "error": str(e)}


def main():
    result = run_test_charge()
    
    if result["status"] == "error":
        logger.error(f"Test failed: {result.get('error')}")
        sys.exit(1)
    
    logger.info(f"Test completed: {result}")


if __name__ == "__main__":
    main()
