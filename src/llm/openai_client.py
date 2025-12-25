from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from openai import APIError, APITimeoutError, BadRequestError, OpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.exception import CustomException
from src.logger import get_logger
from src.utils.load_config import load_config_file

logger = get_logger(__name__)


class OpenAIClient:
    """
    Lightweight wrapper around the OpenAI Responses API with retry logic and optional
    JSON schema enforcement.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        client: Optional[OpenAI] = None,
        base_url: Optional[str] = None,
    ) -> None:
        config = load_config_file()
        llm_config = config.get("llm", {})

        self.model = model or llm_config.get("classification_model", "gpt-4o-mini")
        self.temperature = llm_config.get("temperature", 0.0) if temperature is None else temperature

        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        resolved_base_url = base_url or os.getenv("OPENAI_BASE_URL") or llm_config.get("base_url")

        if not resolved_api_key:
            raise CustomException("OPENAI_API_KEY is not set in the environment.")

        self.client = client or OpenAI(api_key=resolved_api_key, base_url=resolved_base_url)

    # ------------------------------------------------------------------
    def chat(
        self,
        prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Send a prompt to the OpenAI Responses API with optional JSON schema formatting.

        Args:
            prompt: User prompt to send to the model.
            json_schema: Optional JSON schema dict to enforce structured output.
            model: Override default model from config.
            temperature: Override default temperature from config.

        Returns:
            str: Model output text (JSON string if schema was provided).
        """
        request: Dict[str, Any] = {
            "model": model or self.model,
            "input": [{"role": "user", "content": prompt}],
            "temperature": self.temperature if temperature is None else temperature,
        }

        if json_schema:
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": json_schema,
            }

        try:
            logger.debug("Calling OpenAI with model=%s", request["model"])
            response = self._response_with_retry(request=request)
            output_text = self._extract_text(response)
            logger.info("Received response from OpenAI model %s", request["model"])
            return output_text
        except BadRequestError as exc:
            logger.error("OpenAI rejected the request: %s", exc)
            raise CustomException(exc)
        except Exception as exc:
            logger.error("OpenAI call failed: %s", exc)
            raise CustomException(exc)

    # ------------------------------------------------------------------
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((APITimeoutError, RateLimitError, APIError)),
    )
    def _response_with_retry(self, *, request: Dict[str, Any]):
        """Issue the API request with exponential backoff on transient errors."""
        return self.client.responses.create(**request)

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_text(response: Any) -> str:
        """
        Normalize text output from a Responses API payload.

        The Responses client exposes `output_text` for convenience; if unavailable,
        we attempt to read the first output content block, falling back to str().
        """
        text = getattr(response, "output_text", None)
        if text is not None:
            return text

        output = getattr(response, "output", None)
        if output:
            try:
                content = output[0].content[0]
                text_content = getattr(content, "text", None)
                if isinstance(text_content, str):
                    return text_content
                if text_content is not None and hasattr(text_content, "value"):
                    return text_content.value
                if hasattr(content, "parsed") and content.parsed is not None:
                    return json.dumps(content.parsed)
            except Exception:
                # Fall through to str(response)
                pass

        return str(response)
