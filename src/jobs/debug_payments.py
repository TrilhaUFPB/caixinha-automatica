"""Debug script to inspect PIX payment details and matching logic."""

import json
import logging
import sys
from datetime import date, timedelta

sys.path.insert(0, str(__file__).rsplit("/src", 1)[0])

from src.services.efi import EfiService
from src.services.sheets import SheetsService

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main():
    days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 30

    efi = EfiService()
    sheets = SheetsService()

    today = date.today()
    start = today - timedelta(days=days_back)

    pix_list = efi.list_received_pix(
        f"{start.isoformat()}T00:00:00Z",
        f"{today.isoformat()}T23:59:59Z",
    )

    members = sheets.get_members()
    print(f"\n=== MEMBERS IN SPREADSHEET ({len(members)}) ===")
    for m in members:
        print(f"  Name: '{m.name}' | Email: '{m.email}'")

    print(f"\n=== PIX RECEIVED ({len(pix_list)}) ===")
    for i, pix in enumerate(pix_list, 1):
        txid = pix.get("txid", "")
        valor = pix.get("valor", "")
        pagador = pix.get("pagador", {})
        print(f"\n--- PIX #{i} ---")
        print(f"  txid: {txid}")
        print(f"  valor: {valor}")
        print(f"  pagador.nome: {pagador.get('nome', 'N/A')}")
        print(f"  pagador.cpf: {pagador.get('cpf', 'N/A')}")

        if txid:
            try:
                charge = efi.get_charge_status(txid)
                devedor = charge.get("devedor", {})
                descricao = charge.get("solicitacaoPagador", "")
                status = charge.get("status", "")
                print(f"  charge.status: {status}")
                print(f"  charge.solicitacaoPagador: '{descricao}'")
                print(f"  charge.devedor: {json.dumps(devedor, ensure_ascii=False)}")
            except Exception as e:
                print(f"  charge lookup failed: {e}")
        else:
            print("  (no txid - manual PIX transfer)")


if __name__ == "__main__":
    main()
