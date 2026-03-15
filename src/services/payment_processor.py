import logging
import re
from typing import Optional

from src.services.efi import EfiService
from src.services.email import EmailService
from src.services.sheets import SheetsService
from src.utils.business_days import get_current_month_column

logger = logging.getLogger(__name__)

EXPECTED_VALOR = "40.00"
TECPRED_VALOR = "25.00"
TECPRED_MEMBERS = {"malu quintela", "malu uchoa", "nicole", "joaquim"}


def _extract_month_from_description(description: str) -> Optional[str]:
    """Extract month from charge description like 'Caixinha Trilha - Março - João'."""
    match = re.search(r"Caixinha Trilha - (\w+) -", description)
    if match:
        return match.group(1)
    return None


def _extract_member_name_from_description(description: str) -> Optional[str]:
    """Extract member name from charge description like 'Caixinha Trilha - Março - João'."""
    parts = description.split(" - ")
    if len(parts) >= 3:
        return parts[-1].strip()
    return None


def process_pix_events(
    pix_list: list[dict],
    efi_service: Optional[EfiService] = None,
    sheets_service: Optional[SheetsService] = None,
    email_service: Optional[EmailService] = None,
) -> dict:
    """Process a list of PIX payment events (from webhook or polling).

    For each PIX:
    1. Look up the original charge via txid to find member + month
    2. Mark as paid in the spreadsheet
    3. Send confirmation email
    """
    efi_service = efi_service or EfiService()
    sheets_service = sheets_service or SheetsService()
    email_service = email_service or EmailService()

    members = sheets_service.get_members()
    members_by_name = {m.name.lower().strip(): m for m in members}
    members_by_first_name = {}
    for m in members:
        first_name = m.name.lower().strip().split()[0]
        if first_name not in members_by_first_name:
            members_by_first_name[first_name] = m

    # Load txid → member mappings from the spreadsheet
    txid_mappings = sheets_service.get_txid_mappings()

    processed = 0
    already_paid = 0
    not_found = 0
    errors = 0
    results = []

    for pix in pix_list:
        txid = pix.get("txid", "")
        valor = pix.get("valor", "")

        if valor not in (EXPECTED_VALOR, TECPRED_VALOR):
            logger.info(f"Skipping PIX with valor={valor} (expected {EXPECTED_VALOR} or {TECPRED_VALOR}), txid={txid}")
            continue

        member = None
        month = get_current_month_column()

        # Try txid → member mapping from spreadsheet first
        if txid and txid in txid_mappings:
            mapping = txid_mappings[txid]
            mapped_name = mapping["member"].lower().strip()
            member = members_by_name.get(mapped_name)
            if not member:
                first = mapped_name.split()[0]
                member = members_by_first_name.get(first)
            if member and mapping.get("month"):
                month = mapping["month"]
            if member:
                logger.info(f"Matched txid={txid} to {member.name} via txid mapping")

        # Try to resolve member and month from charge metadata via txid
        if not member and txid:
            try:
                charge = efi_service.get_charge_status(txid)
                description = charge.get("solicitacaoPagador", "")

                charge_month = _extract_month_from_description(description)
                if charge_month:
                    month = charge_month

                # Try devedor.nome first
                devedor = charge.get("devedor", {})
                nome = devedor.get("nome", "").lower().strip() if devedor else ""

                # Fallback to name in description
                if not nome:
                    nome_desc = _extract_member_name_from_description(description)
                    if nome_desc:
                        nome = nome_desc.lower().strip()

                if nome:
                    member = members_by_name.get(nome)
                    if not member:
                        first = nome.split()[0]
                        member = members_by_first_name.get(first)

            except Exception as e:
                logger.warning(f"Failed to get charge details for txid={txid}: {e}")

        # Fallback: try pagador info from the PIX event itself
        if not member:
            pagador = pix.get("pagador", {})
            nome_pagador = pagador.get("nome", "").lower().strip()
            if nome_pagador:
                member = members_by_name.get(nome_pagador)
                if not member:
                    first = nome_pagador.split()[0]
                    member = members_by_first_name.get(first)

        if not member:
            logger.warning(f"Could not identify member for txid={txid}")
            not_found += 1
            results.append({"txid": txid, "status": "not_found"})
            continue

        # Check idempotency
        current_status = member.payment_status.get(month, "").lower()
        if current_status in ["paid", "pago"]:
            logger.info(f"Member {member.name} already marked as paid for {month}")
            already_paid += 1
            results.append({"txid": txid, "name": member.name, "status": "already_paid"})
            continue

        try:
            sheets_service.mark_as_paid(member.name, month)
            logger.info(f"Marked {member.name} as paid for {month}")

            if member.email:
                try:
                    email_service.send_confirmation_email(
                        to=member.email,
                        name=member.name,
                        amount=valor,
                        month=month,
                    )
                    logger.info(f"Confirmation email sent to {member.email}")
                except Exception as e:
                    logger.error(f"Failed to send confirmation email to {member.email}: {e}")

            processed += 1
            results.append({
                "txid": txid,
                "name": member.name,
                "email": member.email,
                "month": month,
                "status": "success",
            })

        except Exception as e:
            logger.error(f"Failed to mark {member.name} as paid: {e}")
            errors += 1
            results.append({
                "txid": txid,
                "name": member.name,
                "status": "error",
                "error": str(e),
            })

    logger.info(
        f"Payment processing complete. "
        f"Processed: {processed}, Already paid: {already_paid}, "
        f"Not found: {not_found}, Errors: {errors}"
    )

    return {
        "status": "success",
        "processed": processed,
        "already_paid": already_paid,
        "not_found": not_found,
        "errors": errors,
        "results": results,
    }
