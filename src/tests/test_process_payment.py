"""
Test script to process received PIX payments and update spreadsheet.
Uses the "teste" sheet with only test members.
"""
import logging
import sys
from datetime import date, timedelta

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

TEST_SHEET = "teste"


def run_test_process_payment(days_back: int = 1) -> dict:
    logger.info("=== TEST: PROCESS PAYMENTS ===")
    logger.info(f"Using sheet: {TEST_SHEET}")
    
    today = date.today()
    start_date = today - timedelta(days=days_back)
    
    logger.info(f"Checking for payments from {start_date} to {today}")
    
    efi_service = EfiService()
    sheets_service = SheetsService()
    email_service = EmailService()
    
    month_column = get_current_month_column()
    logger.info(f"Current month column: {month_column}")
    
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
    
    logger.info(f"Found {len(pix_list)} PIX payments")
    
    try:
        members = sheets_service.get_members(sheet_name=TEST_SHEET)
    except Exception as e:
        logger.error(f"Failed to get members: {e}")
        return {"status": "error", "error": str(e), "processed": 0}
    
    logger.info(f"Found {len(members)} members in '{TEST_SHEET}' sheet")
    
    members_by_name = {m.name.lower().strip(): m for m in members}
    
    processed = 0
    already_paid = 0
    not_found = 0
    results = []
    
    for pix in pix_list:
        txid = pix.get("txid", "")
        valor = pix.get("valor", "")
        pagador = pix.get("pagador", {})
        nome_pagador = pagador.get("nome", "").lower().strip()
        
        logger.info(f"Processing PIX: txid={txid}, valor={valor}, pagador={nome_pagador}")
        
        member = members_by_name.get(nome_pagador)
        
        if not member:
            for name, m in members_by_name.items():
                if nome_pagador in name or name in nome_pagador:
                    member = m
                    logger.info(f"Fuzzy matched '{nome_pagador}' to '{m.name}'")
                    break
        
        if not member:
            logger.warning(f"Member not found for pagador: {nome_pagador}")
            not_found += 1
            results.append({
                "txid": txid,
                "pagador": nome_pagador,
                "status": "not_found",
            })
            continue
        
        current_status = member.payment_status.get(month_column, "").lower()
        if current_status in ["paid", "pago"]:
            logger.info(f"Member {member.name} already marked as paid for {month_column}")
            already_paid += 1
            results.append({
                "txid": txid,
                "name": member.name,
                "status": "already_paid",
            })
            continue
        
        try:
            sheets_service.mark_as_paid(member.name, month_column, sheet_name=TEST_SHEET)
            logger.info(f"Marked {member.name} as paid for {month_column}")
            
            if member.email:
                try:
                    email_service.send_confirmation_email(
                        to=member.email,
                        name=member.name,
                        amount=valor,
                        month=month_column,
                    )
                    logger.info(f"Confirmation email sent to {member.email}")
                except Exception as e:
                    logger.error(f"Failed to send confirmation email: {e}")
            
            processed += 1
            results.append({
                "txid": txid,
                "name": member.name,
                "email": member.email,
                "status": "success",
            })
            
        except Exception as e:
            logger.error(f"Failed to mark {member.name} as paid: {e}")
            results.append({
                "txid": txid,
                "name": member.name,
                "status": "error",
                "error": str(e),
            })
    
    logger.info(
        f"Payment processing complete. "
        f"Processed: {processed}, Already paid: {already_paid}, Not found: {not_found}"
    )
    
    return {
        "status": "success",
        "processed": processed,
        "already_paid": already_paid,
        "not_found": not_found,
        "results": results,
    }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test: Process received PIX payments")
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days to look back for payments (default: 1)",
    )
    args = parser.parse_args()
    
    result = run_test_process_payment(days_back=args.days)
    
    if result["status"] == "error":
        logger.error(f"Test failed: {result.get('error')}")
        sys.exit(1)
    
    logger.info(f"Test completed: {result}")


if __name__ == "__main__":
    main()
