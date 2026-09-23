"""Shared API/worker provider selection. Does not silently fall back."""

from forge.core.errors import DomainError
from forge.model_router.fake import FakeAdapter
from forge.model_router.gemini import GeminiAdapter
from forge.model_router.openai import OpenAIAdapter


class ProviderRouter:
    def __init__(self, settings):
        self.settings = settings

    def select(self, model):
        key = (
            self.settings.gemini_api_key
            if model.startswith("gemini-")
            else self.settings.openai_api_key
        )
        value = key.get_secret_value().strip() if key else None
        if model.startswith("gemini-"):
            return GeminiAdapter(value)
        if model.startswith(("gpt-", "o1", "o3", "o4")):
            return OpenAIAdapter(value)
        raise DomainError("MODEL_UNSUPPORTED", "Use a Gemini or OpenAI model identifier.", 422)


def select_adapter(adapter, model):
    return adapter.select(model) if isinstance(adapter, ProviderRouter) else adapter


def adapter_for(settings):
    if settings.model_backend == "fake":
        return FakeAdapter()
    if settings.model_backend == "routed":
        return ProviderRouter(settings)
    key = settings.openai_api_key if settings.model_backend == "openai" else settings.gemini_api_key
    value = key.get_secret_value().strip() if key else None
    return OpenAIAdapter(value) if settings.model_backend == "openai" else GeminiAdapter(value)
