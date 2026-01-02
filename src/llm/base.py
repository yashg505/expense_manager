import json
import time
import sys
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, Union

from pydantic import BaseModel, ValidationError
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type,
    before_sleep_log
)

from src.logger import get_logger
from src.exception import CustomException
from src.models import LLMResponse

# Configure logging
logger = get_logger(__name__)

class BaseLLM(ABC):
    """
    Abstract Base Class for LLM providers.
    Provides standardized orchestration for generation, retries, and schema validation.
    """
    
    def __init__(self, model_name: str, api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key
        logger.debug(f"Initialized {self.__class__.__name__} with model: {model_name}")

    @abstractmethod
    def _raw_generate(self, prompt: str, **kwargs) -> dict:
        """
        Hidden method: Each child class implements its specific API call here.
        Should return a dict containing 'text', 'usage', and 'metadata'.
        """
        raise NotImplementedError

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.INFO), 
        reraise=True
    )
    def generate(
        self,
        prompt: str,
        response_model: Optional[Type[BaseModel]] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        The main public method. It handles timing, retries, and Pydantic parsing.
        """
        start_time = time.perf_counter() # More precise than time.time()
        logger.info(f"LLM Dispatch: Provider={self.__class__.__name__}, Model={self.model_name}")

        try:
            # 1. Execute the raw API call (implemented by child)
            result = self._raw_generate(
                prompt,
                response_model=response_model,
                **kwargs
            )

            # 2. Calculate Latency
            latency = (time.perf_counter() - start_time) * 1000
            
            # 3. Extract Core Components
            raw_text = result.get("text", "")
            usage = result.get("usage", {})
            metadata = result.get("metadata", {})

            # 4. Handle Content Processing/Parsing
            processed_content = raw_text
            if response_model:
                logger.debug(f"Attempting to parse output into schema: {response_model.__name__}")
                try:
                    processed_content = self._parse_response(raw_text, response_model)
                    logger.info("Structured output parsing successful.")
                except (ValidationError, ValueError, TypeError) as exc:
                    logger.error(f"Schema validation failed for model {self.model_name}")
                    logger.debug(f"Failed raw_text: {raw_text}")
                    # We continue with raw_text but log the failure
                    raise CustomException(exc, sys) 

            # 5. Serialize raw response for logging/storage
            if isinstance(raw_text, str):
                raw_response_str = raw_text
            elif isinstance(raw_text, BaseModel):
                raw_response_str = raw_text.model_dump_json()
            else:
                try:
                    raw_response_str = json.dumps(raw_text)
                except (TypeError, ValueError):
                    raw_response_str = str(raw_text)

            logger.info(f"Generation complete. Latency: {latency:.2f}ms. Total Tokens: {usage.get('total_tokens', 0)}")

            return LLMResponse(
                content=processed_content,
                raw_response=raw_response_str,
                model_name=self.model_name,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                latency_ms=round(latency, 2),
                provider=self.__class__.__name__,
                metadata=metadata if isinstance(metadata, dict) else None,
            )

        except Exception as exc:
            # Re-wrap in CustomException for the rest of the application to catch
            logger.error(f"Exhausted all retry attempts for {self.model_name}")
            raise CustomException(exc, sys)

    @staticmethod
    def _parse_response(raw_text: Union[str, dict, list, BaseModel], response_model: Type[BaseModel]) -> BaseModel:
        """
        Verbosesly handles the conversion from raw LLM output to a Pydantic Model.
        """
        # If the SDK already returned the model instance
        if isinstance(raw_text, response_model):
            return raw_text

        # If the SDK already returned a dict/list (e.g., via Instructor or .parse())
        if isinstance(raw_text, (dict, list)):
            return response_model.model_validate(raw_text)

        if not isinstance(raw_text, str):
            logger.error(f"Unexpected response type: {type(raw_text)}")
            raise ValueError(f"Response is not a string or JSON payload. Type: {type(raw_text)}")

        # Attempt to parse as JSON string
        try:
            return response_model.model_validate_json(raw_text)
        except (ValidationError, ValueError, TypeError) as ve:
            logger.debug("Standard model_validate_json failed, attempting manual json.loads fallback.")
            try:
                parsed = json.loads(raw_text)
                return response_model.model_validate(parsed)
            except (json.JSONDecodeError, ValidationError, TypeError):
                # Raise the original validation error if fallback also fails
                raise ve