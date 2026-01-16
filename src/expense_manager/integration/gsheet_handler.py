import pandas as pd
import google.auth
import gspread
from typing import cast
from google.auth.credentials import Credentials
from gspread_dataframe import set_with_dataframe
from datetime import datetime, timezone

from expense_manager.logger import get_logger
from expense_manager.exception import CustomException
from expense_manager.utils.load_config import load_config_file

logger = get_logger(__name__)


class GSheetHandler:
    """
    Google Sheet handler for Expense or Taxonomy sheets.
    """

    def __init__(self, sheet_type: str):
        """
        Args:
            sheet_type: "expense" or "taxonomy"
        """
        self.config = load_config_file()
        self.sheet_type = sheet_type

        sheets_cfg = self.config.get("sheets", {})

        if sheet_type == self.config["sheets"].get("expense_sheet_type", "expense"):
            self.sheet_id = sheets_cfg["expense_sheet"]
            self.worksheet_name = sheets_cfg["expense_sheet_worksheet_name"]
        elif sheet_type == self.config["sheets"].get('taxonomy_sheet_type', 'taxonomy'):
            self.sheet_id = sheets_cfg["taxonomy_sheet_id"]
            self.worksheet_name = sheets_cfg["taxonomy_worksheet_name"]
        else:
            raise CustomException(f"Invalid sheet_type: {sheet_type}")

        self.sheet = None
        self.df = None

        self._authenticate_and_load()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def _authenticate_and_load(self):
        try:
            scopes = self.config["sheets"].get(
                "sheet_scope",
                [
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ],
            )

            creds, _ = google.auth.default(scopes=scopes)
            creds = cast(Credentials, creds)

            client = gspread.authorize(creds)
            self.sheet = client.open_by_key(self.sheet_id)

            logger.info(
                f"Authenticated and loaded sheet [{self.sheet_type}] ({self.sheet_id})"
            )

        except Exception as e:
            logger.error(f"GSheet authentication failed: {e}")
            raise CustomException(e)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def load_sheet_as_df(self) -> pd.DataFrame:
        """
        Load worksheet into pandas DataFrame.
        """
        try:
            if self.sheet is None:
                raise CustomException("Google Sheet is not initialized")

            worksheet = self.sheet.worksheet(self.worksheet_name)
            records:list = worksheet.get_all_records()
            self.df = pd.DataFrame(records)
            logger.info(
                f"Loaded worksheet '{self.worksheet_name}' ({len(self.df)} rows)"
            )
            return self.df

        except Exception as e:
            logger.error(f"Failed loading sheet as DataFrame: {e}")
            raise CustomException(e)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    def append_df_to_sheet(self, df: pd.DataFrame):
        """
        Append DataFrame rows to worksheet.
        """
        try:
            if self.sheet is None:
                raise CustomException("Google Sheet is not initialized")

            worksheet = self.sheet.worksheet(self.worksheet_name)
            next_row = len(worksheet.get_all_values()) + 1

            set_with_dataframe(
                worksheet,
                df,
                row=next_row,
                include_index=False,
                include_column_header=False,
            )

            logger.info(
                f"Appended {len(df)} rows to '{self.worksheet_name}' at row {next_row}"
            )

        except Exception as e:
            logger.error(f"Failed appending DataFrame: {e}")
            raise CustomException(e)

    # ------------------------------------------------------------------
    # Taxonomy-specific helper
    # ------------------------------------------------------------------
    def fetch_taxonomy_rows(self):
        """
        Load taxonomy sheet and return rows with timestamp.
        Returns:
            rows: list[dict]
            timestamp: datetime
        """
        if self.sheet_type != "taxonomy":
            raise CustomException(
                "fetch_taxonomy_rows is only valid for taxonomy sheets"
            )

        df = self.load_sheet_as_df()
        if df.empty:
            raise CustomException("Taxonomy sheet is empty")

        rows = df.to_dict(orient="records")
        timestamp = datetime.now(timezone.utc)

        logger.info(f"Fetched {len(rows)} taxonomy rows")
        return rows, timestamp
