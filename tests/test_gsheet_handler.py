import pytest
from unittest.mock import MagicMock, patch
from expense_manager.integration.gsheet_handler import GSheetHandler
from expense_manager.exception import CustomException

@pytest.fixture
def mock_config():
    with patch("expense_manager.integration.gsheet_handler.load_config_file") as mock_load:
        mock_load.return_value = {
            "sheets": {
                "expense_sheet_type": "expense",
                "expense_sheet": "EXPENSE_ID",
                "expense_sheet_worksheet_name": "Sheet1",
                "taxonomy_sheet_type": "taxonomy",
                "taxonomy_sheet_id": "TAXONOMY_ID",
                "taxonomy_worksheet_name": "Taxonomy"
            }
        }
        yield mock_load

@pytest.fixture
def mock_gspread():
    with patch("expense_manager.integration.gsheet_handler.gspread") as mock_gs, \
         patch("expense_manager.integration.gsheet_handler.google.auth.default") as mock_auth:
        
        mock_auth.return_value = (MagicMock(), "project_id")
        
        mock_client = MagicMock()
        mock_gs.authorize.return_value = mock_client
        
        mock_sheet = MagicMock()
        mock_client.open_by_key.return_value = mock_sheet
        
        yield {
            "client": mock_client,
            "sheet": mock_sheet,
            "auth": mock_auth
        }

def test_init_expense_sheet(mock_config, mock_gspread):
    handler = GSheetHandler("expense")
    assert handler.sheet_id == "EXPENSE_ID"
    mock_gspread["client"].open_by_key.assert_called_with("EXPENSE_ID")

def test_init_taxonomy_sheet(mock_config, mock_gspread):
    handler = GSheetHandler("taxonomy")
    assert handler.sheet_id == "TAXONOMY_ID"

def test_init_invalid_type(mock_config):
    with pytest.raises(CustomException):
        GSheetHandler("invalid")

def test_load_sheet_as_df(mock_config, mock_gspread):
    handler = GSheetHandler("expense")
    
    mock_worksheet = MagicMock()
    mock_gspread["sheet"].worksheet.return_value = mock_worksheet
    mock_worksheet.get_all_records.return_value = [{"Col1": "Val1"}]
    
    df = handler.load_sheet_as_df()
    assert not df.empty
    assert df.iloc[0]["Col1"] == "Val1"

def test_append_df_to_sheet(mock_config, mock_gspread):
    import pandas as pd
    handler = GSheetHandler("expense")
    
    mock_worksheet = MagicMock()
    mock_gspread["sheet"].worksheet.return_value = mock_worksheet
    mock_worksheet.get_all_values.return_value = [["header"], ["row1"]] # 2 rows existing
    
    df = pd.DataFrame([{"Col1": "NewVal"}])
    
    with patch("expense_manager.integration.gsheet_handler.set_with_dataframe") as mock_set:
        handler.append_df_to_sheet(df)
        mock_set.assert_called()
        # Should append at row 3 (len=2 + 1)
        args, kwargs = mock_set.call_args
        assert kwargs["row"] == 3
