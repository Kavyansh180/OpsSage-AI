import asyncio
import json
import re
from typing import Any, Dict, Optional, Tuple, Type, TypeVar
import httpx
from pydantic import BaseModel, ValidationError

from backend.app.core.logging import get_logger
from backend.app.services.llm.base import LLMProvider
from backend.app.services.llm.exceptions import (
    LLMConfigurationError,
    LLMError,
    LLMRateLimitError,
    LLMResponseParsingError,
    LLMTimeoutError,
)

logger = get_logger("services.llm.gemini")
T = TypeVar("T", bound=BaseModel)


class GeminiProvider(LLMProvider):
    """
    Gemini implementation of LLMProvider via native asynchronous HTTP REST client.
    Uses Google Gemini REST API v1beta.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.5-flash-lite",
        timeout_seconds: int = 30,
        temperature: float = 0.2,
    ):
        if not api_key:
            raise LLMConfigurationError("Gemini API key is not configured.")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._temperature = temperature

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def _build_url(self) -> str:
        return f"{self.BASE_URL}/{self._model}:generateContent"

    def _build_payload(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": self._temperature,
            },
        }

        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        return payload

    def _extract_text_from_response(self, response_data: Dict[str, Any]) -> str:
        candidates = response_data.get("candidates", [])
        if not candidates:
            feedback = response_data.get("promptFeedback", {})
            block_reason = feedback.get("blockReason", "No candidates returned")
            raise LLMError(f"Gemini API returned no content candidates. Reason: {block_reason}")

        candidate = candidates[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        if not parts:
            finish_reason = candidate.get("finishReason", "UNKNOWN")
            raise LLMError(f"Gemini response contained no text parts. Finish reason: {finish_reason}")

        return parts[0].get("text", "").strip()

    def _strip_markdown_code_fences(self, text: str) -> str:
        """
        Strips wrapping ```json ... ``` or ``` ... ``` if present.
        """
        trimmed = text.strip()
        if trimmed.startswith("```"):
            trimmed = re.sub(r"^```(?:json)?\s*\n?", "", trimmed, flags=re.IGNORECASE)
            trimmed = re.sub(r"\n?```\s*$", "", trimmed)
        return trimmed.strip()

    async def _send_request(self, payload: Dict[str, Any]) -> str:
        url = self._build_url()
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

        max_attempts = 3
        last_status_code = None
        last_sanitized_body = None

        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    return self._extract_text_from_response(data)

                # Handle non-200 responses
                status_code = response.status_code
                last_status_code = status_code
                error_body = response.text

                # Redact API key from error body if inadvertently reflected
                sanitized_body = error_body.replace(self._api_key, "[REDACTED_API_KEY]")
                last_sanitized_body = sanitized_body

                # Transient errors: retry with backoff
                if status_code in (429, 500, 502, 503, 504) and attempt < max_attempts - 1:
                    logger.warning(
                        f"Gemini API returned HTTP {status_code} on attempt {attempt + 1}/{max_attempts}. "
                        f"Retrying in {1.0 * (attempt + 1)}s..."
                    )
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue

                logger.error(f"Gemini API returned HTTP {status_code}: {sanitized_body[:300]}")

                if status_code == 429:
                    raise LLMRateLimitError(
                        "Gemini API quota or rate limit exceeded. Please try again later.",
                        details={"provider": "gemini", "model": self._model},
                    )
                elif status_code in (401, 403):
                    raise LLMConfigurationError(
                        "Gemini API authentication failed. Verify the GEMINI_API_KEY setting.",
                        details={"provider": "gemini"},
                    )
                else:
                    raise LLMError(
                        f"Gemini API failed with HTTP {status_code}",
                        details={"status_code": status_code, "provider": "gemini", "model": self._model},
                    )

            except httpx.TimeoutException as exc:
                if attempt < max_attempts - 1:
                    logger.warning(f"Gemini API request timed out on attempt {attempt + 1}/{max_attempts}. Retrying...")
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                logger.error(f"Gemini API request timed out after {self._timeout_seconds}s")
                raise LLMTimeoutError(
                    f"Gemini API request timed out after {self._timeout_seconds} seconds.",
                    details={"timeout_seconds": self._timeout_seconds, "model": self._model},
                ) from exc
            except (LLMError, LLMRateLimitError, LLMConfigurationError, LLMTimeoutError):
                raise
            except Exception as exc:
                logger.exception("Unexpected error communicating with Gemini API")
                raise LLMError(
                    f"Unexpected error communicating with Gemini API: {str(exc)}",
                    details={"provider": "gemini", "model": self._model},
                ) from exc

        raise LLMError(
            f"Gemini API failed with HTTP {last_status_code}",
            details={"status_code": last_status_code, "provider": "gemini", "model": self._model},
        )

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> str:
        payload = self._build_payload(prompt, system_instruction, json_mode=False)
        return await self._send_request(payload)

    async def generate_structured(
        self,
        prompt: str,
        schema_cls: Type[T],
        system_instruction: Optional[str] = None,
    ) -> Tuple[T, str]:
        payload = self._build_payload(prompt, system_instruction, json_mode=True)
        raw_text = await self._send_request(payload)

        clean_json_str = self._strip_markdown_code_fences(raw_text)

        try:
            parsed_dict = json.loads(clean_json_str)
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to decode LLM response as JSON: {clean_json_str[:300]}")
            raise LLMResponseParsingError(
                "Gemini returned an invalid JSON response.",
                details={"raw_preview": clean_json_str[:200]},
            ) from exc

        try:
            instance = schema_cls.model_validate(parsed_dict)
            return instance, raw_text
        except ValidationError as exc:
            logger.error(f"LLM JSON failed schema validation: {exc}")
            raise LLMResponseParsingError(
                "Gemini response did not conform to the expected RCA schema.",
                details={"validation_errors": exc.errors()},
            ) from exc
