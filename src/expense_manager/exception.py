"""
exception.py

This module contains the CustomException class used for handling and providing detailed
context about exceptions that occur within the application. It captures information 
such as the line number, file name, and original error message to assist in debugging.

Classes:
    - CustomException: A custom exception handler that captures and displays detailed
      error information, including the script name and line number.

Example usage:
    try:
        1 / 0
    except Exception as e:
        raise CustomException(e, sys)
"""

import sys
import types
from typing import Optional


class CustomException(Exception):
    """
    CustomException is used to handle exceptions with more detailed context information.
    
    Attributes:
        error_message (str): The original error message passed to the exception.
        lineno (int): The line number where the exception occurred.
        file_name (str): The name of the file where the exception occurred.
    """

    def __init__(self, error_message, error_details: Optional[types.ModuleType] = None):
        self.error_message = error_message

        if error_details is None:
            error_details = sys

        _, _, exc_tb = error_details.exc_info()

        if exc_tb is not None:
            self.lineno = exc_tb.tb_lineno
            self.file_name = exc_tb.tb_frame.f_code.co_filename
        else:
            self.lineno = None
            self.file_name = "Unknown"

    def __str__(self):
        return (
            f"Error occurred in python script: '{self.file_name}', "
            f"line number: {self.lineno}, error message: {self.error_message}"
        )

if __name__ == "__main__":
    try:
        a = 1 / 0

    except Exception as e:
        raise CustomException(e, sys)
