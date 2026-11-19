import json
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from backend.app.config import Settings
from backend.app.models.analysis import ConfidenceLevel
from backend.app.schemas.analysis import StructuredRCAResponse
from backend.app.services.llm.exceptions import (
    LLMConfigurationError,
    LLMError,
    LLMRateLimitError,
    LLMResponseParsingError,
    LLMTimeoutError,
)
from backend.app.services.llm.factory import get_llm_provider
from backend.app.services.llm.gemini import GeminiProvider


def test_gemini_missing_api_key_raises():
    with pytest.raises(LLMConfigurationError) as exc_info:
        GeminiProvider(api_key="")
    assert "not configured" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_gemini_generate_structured_success():
    provider = GeminiProvider(api_key="fake-test-key", model="gemini-3.5-flash-lite")

    mock_llm_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "probable_root_cause": "Database connection pool exhaustion",
                                "explanation": "The connection pool max_size was reached during peak traffic.",
                                "supporting_evidence": ["Log line: pool exhausted size=50"],
                                "contributing_factors": ["High concurrent requests", "Unclosed transactions"],
                                "confidence_level": "HIGH",
                                "recommended_actions": ["Increase pool size", "Audit connection leaks"],
                                "limitations": ["No database-side telemetry available"],
                            })
                        }
                    ]
                },
                "finishReason": "STOP",
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_llm_response

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        result, raw = await provider.generate_structured(
            prompt="Analyze this error",
            schema_cls=StructuredRCAResponse,
            system_instruction="Strict grounding",
        )

        assert isinstance(result, StructuredRCAResponse)
        assert result.probable_root_cause == "Database connection pool exhaustion"
        assert result.confidence_level == ConfidenceLevel.HIGH
        assert len(result.supporting_evidence) == 1
        assert len(result.recommended_actions) == 2


@pytest.mark.asyncio
async def test_gemini_strips_markdown_code_fences():
    provider = GeminiProvider(api_key="fake-key")

    inner_json = json.dumps({
        "probable_root_cause": "Memory leak",
        "explanation": "Out of memory in worker pod",
        "supporting_evidence": ["OOMKilled at 10:00:00"],
        "contributing_factors": [],
        "confidence_level": "MEDIUM",
        "recommended_actions": ["Increase pod memory limit"],
        "limitations": [],
    })

    fenced_text = f"```json\n{inner_json}\n```"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": fenced_text}]}}]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result, _ = await provider.generate_structured(
            prompt="Analyze", schema_cls=StructuredRCAResponse
        )
        assert result.probable_root_cause == "Memory leak"
        assert result.confidence_level == ConfidenceLevel.MEDIUM


@pytest.mark.asyncio
async def test_gemini_invalid_json_raises_parsing_error():
    provider = GeminiProvider(api_key="fake-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "This is plain text, not JSON"}]}}]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMResponseParsingError):
            await provider.generate_structured(
                prompt="Analyze", schema_cls=StructuredRCAResponse
            )


@pytest.mark.asyncio
async def test_gemini_missing_schema_fields_raises_parsing_error():
    provider = GeminiProvider(api_key="fake-key")
    # Missing required 'probable_root_cause' and 'explanation'
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": json.dumps({"extra": "value"})}]}}]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMResponseParsingError):
            await provider.generate_structured(
                prompt="Analyze", schema_cls=StructuredRCAResponse
            )


@pytest.mark.asyncio
async def test_gemini_429_rate_limit_handling():
    provider = GeminiProvider(api_key="fake-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Quota exceeded for quota metric 'GenerateContent'"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMRateLimitError):
            await provider.generate_structured(
                prompt="Analyze", schema_cls=StructuredRCAResponse
            )


@pytest.mark.asyncio
async def test_gemini_timeout_handling():
    provider = GeminiProvider(api_key="fake-key", timeout_seconds=5)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Read timed out")
        with pytest.raises(LLMTimeoutError):
            await provider.generate_text("Prompt")


@pytest.mark.asyncio
async def test_gemini_never_leaks_api_key_in_error():
    secret_key = "AIzaSyD-SecretKey123456789"
    provider = GeminiProvider(api_key=secret_key)

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = f"Internal server error occurred with key {secret_key}"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMError) as exc_info:
            await provider.generate_text("Prompt")

        error_repr = str(exc_info.value)
        assert secret_key not in error_repr


def test_factory_returns_gemini():
    settings = Settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="test-key")
    provider = get_llm_provider(settings)
    assert isinstance(provider, GeminiProvider)
    assert provider.provider_name == "gemini"


def test_factory_unsupported_provider():
    settings = Settings(LLM_PROVIDER="anthropic_claude")
    with pytest.raises(LLMConfigurationError):
        get_llm_provider(settings)
