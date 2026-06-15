from dataclasses import dataclass, field


@dataclass
class ResolvedCall:
    """A provider selection resolved into LiteLLM call arguments."""
    model: str
    kwargs: dict = field(default_factory=dict)


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""


@dataclass
class ModelSelection:
    """Which provider config + model a chat/session should use."""
    provider_config_id: str
    model: str
    provider: str


class LLMError(Exception):
    """Normalized provider error with a stable `code`."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
