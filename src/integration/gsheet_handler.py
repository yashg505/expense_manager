import re
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe
from src.logger import get_logger
from src.exception import CustomException
from src.utils.load_config import load_config_file

logger = get_logger(__name__)

class GSheetHandler:
    config = load_config_file()

    def __init__(self, sheet_url=None, credential_file=None, sheet_id=None):
        self.sheet_id = sheet_id
        self.sheet_url = sheet_url or self._extract_sheet_id()
        self.credential_file = credential_file or self.config['credential_file']
        self.sheet = None
        self.df = None

        self._authenticate_and_load()

    def _extract_sheet_id(self):
        """
        Extract sheet_id from sheet_url or load from config if URL is not given.
        """
        try:
            if self.sheet_id:
                return self.sheet_id
            if not self.sheet_url:
                logger.info("No sheet URL provided, loading from config.")
                self.sheet_id = self.config['sheets']['sheet_id']
            else:
                match = re.search(r'/d/([a-zA-Z0-9-_]+)', self.sheet_url)
                if match:
                    self.sheet_id = match.group(1)
                else:
                    raise CustomException("Invalid Google Sheet URL.")
            logger.info(f"Sheet ID: {self.sheet_id}")
        except Exception as e:
            logger.error(f"Error extracting sheet id: {e}")
            raise e

    def _authenticate_and_load(self):
        """
        Authenticate using service account and load the Google Sheet.
        """
        try:
            if not self.credential_file:
                raise CustomException("Credential file is not provided.")
            self._extract_sheet_id()
            scopes = self.config['sheets']['sheet_scope']
            creds = Credentials.from_service_account_file(self.credential_file, scopes=scopes)
            client = gspread.authorize(creds)
            
            if self.sheet_id is not None:
                self.sheet = client.open_by_key(self.sheet_id)
            
            logger.info("Successfully authenticated and loaded Google Sheet.")
        except Exception as e:
            logger.error(f"Authentication or loading failed: {e}")
            raise e

    def load_sheet_as_df(self, worksheet_name=None):
        """
        Load a worksheet as a DataFrame.

        :param worksheet_name: Name of the worksheet (tab) to load, else loads from config.
        :return: pandas DataFrame with worksheet data.
        """
        try:
            if self.sheet is None:
                raise CustomException("Google Sheet is not initialized. Make sure you call authenticate() first.")
            
            ws_name = worksheet_name or self.config['sheets'].get('worksheet_name')
            if not ws_name:
                raise CustomException("Worksheet name not specified in arguments or config.")

            worksheet = self.sheet.worksheet(ws_name)
            records = worksheet.get_all_records()
            self.df = pd.DataFrame(records)
            logger.info(f"Loaded worksheet '{ws_name}' into DataFrame.")
            return self.df

        except Exception as e:
            logger.error(f"Failed to load sheet as DataFrame: {e}")
            raise CustomException(f"Failed to load sheet as DataFrame: {e}")

    def append_df_to_sheet(self, df: pd.DataFrame, worksheet_name=None):
        """
        Append a DataFrame to the worksheet (at the bottom).

        :param df: DataFrame to append.
        :param worksheet_name: Worksheet to append to, else from config.
        """
        try:
            if self.sheet is None:
                raise CustomException("Google Sheet is not initialized. Call authenticate() first.")

            ws_name = worksheet_name or self.config['sheets'].get('worksheet_name')
            if not ws_name:
                raise CustomException("Worksheet name not specified in arguments or config.")

            worksheet = self.sheet.worksheet(ws_name)

            # Find the next empty row
            existing_rows = len(worksheet.get_all_values())
            next_row = existing_rows + 1

            # Append using set_with_dataframe starting at next_row
            set_with_dataframe(
                worksheet,
                df,
                row=next_row,
                include_index=False,
                include_column_header=False
            )
            logger.info(f"Appended {len(df)} rows to worksheet '{ws_name}' at row {next_row}.")

        except Exception as e:
            logger.error(f"Failed to append DataFrame to sheet: {e}")
    
    def fetch_taxonomy_rows(self):
        """
        Loads taxonomy sheet into a list of dictionaries and returns a timestamp.
        Returns:
            rows (list[dict])
            timestamp (datetime)
        """
        try:
            df = self.load_sheet_as_df()
            if df is None or df.empty:
                raise CustomException("Taxonomy sheet is empty.")

            # Convert to list of dict rows
            rows = df.to_dict(orient="records")

            # Determine sheet timestamp (last modified time)
            # Google Sheets does not provide timestamp directly → so we use NOW.
            # If you want real timestamps, we need Drive API.
            from datetime import datetime
            timestamp = datetime.utcnow()

            logger.info(f"Fetched {len(rows)} taxonomy rows from Google Sheet.")
            return rows, timestamp

        except Exception as e:
            logger.error(f"Failed fetching taxonomy rows: {e}")
            raise CustomException(e)
