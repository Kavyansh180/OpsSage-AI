from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """
    Abstract interface for Large Language Model providers.
    Decouples the RCA engine and higher-level services from specific LLM vendors.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. 'gemini', 'openai')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier being used (e.g. 'gemini-3.5-flash-lite')."""
        pass

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> str:
        """
        Executes a raw completion request and returns the resulting string.
        """
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema_cls: Type[T],
        system_instruction: Optional[str] = None,
    ) -> Tuple[T, str]:
        """
        Executes a completion request and parses the response into the specified Pydantic schema.
        Returns:
            Tuple of (parsed_pydantic_instance, raw_response_string)
        """
        pass
