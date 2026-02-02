import base64
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)


@dataclass
class Member:
    name: str
    email: str
    payment_status: dict[str, str]


class SheetsService:
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        credentials_base64: Optional[str] = None,
        spreadsheet_id: Optional[str] = None,
    ):
        self.credentials_path = credentials_path or os.getenv(
            "GOOGLE_CREDENTIALS_PATH", "credentials.json"
        )
        self.credentials_base64 = credentials_base64 or os.getenv(
            "GOOGLE_CREDENTIALS_BASE64"
        )
        self.spreadsheet_id = spreadsheet_id or os.getenv("SPREADSHEET_ID")

        if not self.spreadsheet_id:
            raise ValueError(
                "SPREADSHEET_ID environment variable or spreadsheet_id parameter is required"
            )

        self._client: Optional[gspread.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None

    def _get_client(self) -> gspread.Client:
        if self._client is None:
            try:
                if self.credentials_base64:
                    credentials_json = base64.b64decode(self.credentials_base64).decode("utf-8")
                    credentials_info = json.loads(credentials_json)
                    credentials = Credentials.from_service_account_info(
                        credentials_info, scopes=self.SCOPES
                    )
                    logger.info("Authenticated using base64 credentials")
                else:
                    credentials = Credentials.from_service_account_file(
                        self.credentials_path, scopes=self.SCOPES
                    )
                    logger.info("Authenticated using credentials file")
                self._client = gspread.authorize(credentials)
                logger.info("Successfully authenticated with Google Sheets API")
            except FileNotFoundError:
                logger.error(f"Credentials file not found: {self.credentials_path}")
                raise
            except Exception as e:
                logger.error(f"Failed to authenticate with Google Sheets API: {e}")
                raise
        return self._client

    def _get_spreadsheet(self) -> gspread.Spreadsheet:
        if self._spreadsheet is None:
            try:
                client = self._get_client()
                self._spreadsheet = client.open_by_key(self.spreadsheet_id)
                logger.info(f"Opened spreadsheet: {self._spreadsheet.title}")
            except gspread.SpreadsheetNotFound:
                logger.error(f"Spreadsheet not found: {self.spreadsheet_id}")
                raise
            except Exception as e:
                logger.error(f"Failed to open spreadsheet: {e}")
                raise
        return self._spreadsheet

    def get_members(self, sheet_name: str = "Sheet1") -> list[Member]:
        try:
            spreadsheet = self._get_spreadsheet()
            worksheet = spreadsheet.worksheet(sheet_name)
            records = worksheet.get_all_records()

            members = []
            for record in records:
                name = record.get("Nome", record.get("Name", ""))
                email = record.get("Email", "")

                payment_status = {
                    key: value
                    for key, value in record.items()
                    if key not in ["Nome", "Name", "Email"]
                }

                if name:
                    members.append(
                        Member(name=name, email=email, payment_status=payment_status)
                    )

            logger.info(f"Retrieved {len(members)} members from spreadsheet")
            return members

        except gspread.WorksheetNotFound:
            logger.error(f"Worksheet not found: {sheet_name}")
            raise
        except Exception as e:
            logger.error(f"Failed to get members: {e}")
            raise

    def get_unpaid_members(
        self, month: str, sheet_name: str = "Sheet1"
    ) -> list[Member]:
        try:
            members = self.get_members(sheet_name)

            unpaid_members = [
                member
                for member in members
                if member.payment_status.get(month, "").lower() != "paid"
                and member.payment_status.get(month, "").lower() != "pago"
            ]

            logger.info(
                f"Found {len(unpaid_members)} unpaid members for month: {month}"
            )
            return unpaid_members

        except Exception as e:
            logger.error(f"Failed to get unpaid members for {month}: {e}")
            raise

    def mark_as_paid(
        self, name: str, month: str, sheet_name: str = "Sheet1"
    ) -> bool:
        try:
            spreadsheet = self._get_spreadsheet()
            worksheet = spreadsheet.worksheet(sheet_name)

            headers = worksheet.row_values(1)
            name_col = None
            month_col = None

            for idx, header in enumerate(headers, start=1):
                if header in ["Nome", "Name"]:
                    name_col = idx
                if header == month:
                    month_col = idx

            if name_col is None:
                logger.error("Name column not found in spreadsheet")
                raise ValueError("Name column not found")

            if month_col is None:
                logger.error(f"Month column '{month}' not found in spreadsheet")
                raise ValueError(f"Month column '{month}' not found")

            name_cells = worksheet.col_values(name_col)
            row_num = None
            for idx, cell_name in enumerate(name_cells, start=1):
                if cell_name == name:
                    row_num = idx
                    break

            if row_num is None:
                logger.error(f"Member not found: {name}")
                raise ValueError(f"Member not found: {name}")

            worksheet.update_cell(row_num, month_col, "Paid")
            logger.info(f"Marked {name} as paid for {month}")
            return True

        except gspread.WorksheetNotFound:
            logger.error(f"Worksheet not found: {sheet_name}")
            raise
        except Exception as e:
            logger.error(f"Failed to mark {name} as paid for {month}: {e}")
            raise
