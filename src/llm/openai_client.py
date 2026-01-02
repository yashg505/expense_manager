from __future__ import annotations
import os
import sys
from typing import Optional, Any, Dict

from openai import OpenAI

from src.llm.base import BaseLLM
from src.exception import CustomException
from src.logger import get_logger

logger = get_logger(__name__)

class OpenAIClient(BaseLLM):
    """
    A concrete implementation of BaseLLM specifically for interacting with OpenAI's API.
    
    This class handles client initialization, parameter preparation, and 
    comprehensive error handling for chat completion requests.
    """

    def __init__(self, model_name: str, api_key: Optional[str] = None) -> None:
        """
        Initializes the OpenAI client with necessary credentials and model configuration.

        Args:
            model_name (str): The specific OpenAI model identifier (e.g., 'gpt-4o').
            api_key (Optional[str]): The API key. Defaults to environment variable if None.
        """
        super().__init__(model_name, api_key)
        
        logger.info(f"Initializing OpenAIClient for model: {model_name}")
        
        # Retrieve API Key from argument or environment
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not resolved_api_key:
            error_msg = "OpenAI API Key not found in arguments or environment variables."
            logger.error(error_msg)
            raise CustomException(error_msg, sys)

        try:
            self.client = OpenAI(api_key=resolved_api_key)
            logger.debug("OpenAI client instance created successfully.")
        except Exception as e:
            logger.exception("Failed to initialize OpenAI client.")
            raise CustomException(e, sys)

    def _raw_generate(
        self,
        prompt: str,
        response_model: Optional[Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Executes a call to the OpenAI API and processes the raw response.
        """
        logger.info(f"Starting generation request for model '{self.model_name}'")
        logger.debug(f"Prompt payload: {prompt[:100]}...") 

        try:
            # Clean up kwargs to prevent conflicts with our internal logic
            if "text_format" in kwargs:
                logger.warning("Overriding 'text_format' found in kwargs to ensure internal consistency.")
                kwargs.pop("text_format")

            # Construct the payload for the OpenAI SDK
            payload = {
                "model": self.model_name,
                "input": [{"role": "user", "content": prompt}],
                **kwargs,
            }

            # Inject structured output formatting if a model is provided
            if response_model is not None:
                logger.info(f"Applying response model: {response_model.__class__.__name__}")
                payload["text_format"] = response_model

            logger.debug(f"Final payload sent to OpenAI: {payload}")

            # Execute the API call
            response = self.client.responses.parse(**payload)

            # Step-by-step validation of the response object
            if response is None:
                logger.error("API returned a None response object.")
                raise CustomException("Received empty response from OpenAI API", sys)

            # Accessing the output text safely
            message_content = getattr(response, "output_text", "")

            # Check if output_text is None (getattr returns default only if attribute is missing, not if value is None)
            if message_content is None:
                logger.error("Choice message content is None.")
                raise CustomException("Response from OpenAI API has no content", sys)

            if not str(message_content).strip():
                logger.warning("Response content is an empty string.")
                raise CustomException("Response from OpenAI API contains empty text", sys)

            # Extracting usage metrics with safety defaults
            usage = getattr(response, 'usage', None)
            
            usage_data = {
                "prompt_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
                "completion_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
                "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
            }

            logger.info(f"Successfully received response. Tokens used: {usage_data['total_tokens']}")

            return {
                "text": message_content,
                "usage": usage_data,
                "metadata": {
                    "provider": "openai",
                    "model": self.model_name,
                    "request_id": getattr(response, "_request_id", None),
                    "system_fingerprint": getattr(response, 'system_fingerprint', None)
                },
            }

        except Exception as exc:
            logger.error(f"Error during OpenAI API execution: {str(exc)}")
            logger.exception("Full traceback for API failure:")
            raise CustomException(exc, sys)