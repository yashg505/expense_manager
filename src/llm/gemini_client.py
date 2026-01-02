from __future__ import annotations

import os
import sys
from typing import Optional, Any, Dict

from google import genai

from src.llm.base import BaseLLM
from src.exception import CustomException
from src.logger import get_logger

logger = get_logger(__name__)


class GeminiClient(BaseLLM):
    """
    A concrete implementation of BaseLLM for Google's Gemini models.
    """

    def __init__(self, model_name: str, api_key: Optional[str] = None) -> None:
        """
        Initializes the Gemini client with necessary credentials and model configuration.

        Args:
            model_name (str): The specific Gemini model identifier (e.g., 'gemini-2.5-flash').
            api_key (Optional[str]): The API key. Defaults to environment variable if None.
        """
        super().__init__(model_name, api_key)

        logger.info(f"Initializing GeminiClient for model: {model_name}")

        resolved_api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        if not resolved_api_key:
            error_msg = "Gemini API Key not found in arguments or environment variables."
            logger.error(error_msg)
            raise CustomException(error_msg, sys)

        try:
            self.client = genai.Client(api_key=resolved_api_key)
            logger.debug("Gemini client instance created successfully.")
        except Exception as e:
            logger.exception("Failed to initialize Gemini client.")
            raise CustomException(e, sys)

    def _raw_generate(
        self,
        prompt: str,
        response_model: Optional[Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Executes a call to the Gemini API and processes the raw response.
        """
        logger.info(f"Starting generation request for model '{self.model_name}'")
        logger.debug(f"Prompt payload: {prompt[:100]}...")

        try:
            config = kwargs.pop("config", None) or {}

            if response_model is not None:
                if "response_mime_type" in config or "response_json_schema" in config:
                    logger.warning(
                        "Overriding response_mime_type/response_json_schema in config due to response_model."
                    )
                config = {
                    **config,
                    "response_mime_type": "application/json",
                    "response_json_schema": response_model.model_json_schema(),
                }

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config if config else None,
                **kwargs,
            )

            if response is None:
                logger.error("API returned a None response object.")
                raise CustomException("Received empty response from Gemini API", sys)

            message_content = getattr(response, "text", None)
            if message_content is None:
                logger.error("Response content is None.")
                raise CustomException("Response from Gemini API has no content", sys)

            if not str(message_content).strip():
                logger.warning("Response content is an empty string.")
                raise CustomException("Response from Gemini API contains empty text", sys)

            usage = getattr(response, "usage_metadata", None)
            usage_data = {
                "prompt_tokens": getattr(usage, "prompt_token_count", 0) if usage else 0,
                "completion_tokens": getattr(usage, "candidates_token_count", 0) if usage else 0,
                "total_tokens": getattr(usage, "total_token_count", 0) if usage else 0,
            }

            logger.info(f"Successfully received response. Tokens used: {usage_data['total_tokens']}")

            return {
                "text": message_content,
                "usage": usage_data,
                "metadata": {
                    "provider": "gemini",
                    "model": self.model_name,
                    "request_id": getattr(response, "request_id", None),
                },
            }

        except Exception as exc:
            logger.error(f"Error during Gemini API execution: {str(exc)}")
            logger.exception("Full traceback for API failure:")
            raise CustomException(exc, sys)
