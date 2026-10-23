import abc
from pydantic import BaseModel
from typing import Optional


class LLMResponse(BaseModel):
    root_cause_summary: str
    suggested_fix: str
    raw_response: Optional[str] = None


class BaseLLMClient(abc.ABC):
    @abc.abstractmethod
    def generate_explanation(self, prompt: str) -> LLMResponse:
        """Generates root cause summary and fix recommendation given prompt context."""
        pass
