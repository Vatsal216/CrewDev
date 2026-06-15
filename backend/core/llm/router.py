from typing import Awaitable, Callable, Optional

import litellm

from core.llm.types import ResolvedCall, Usage, LLMError

EmitCallback = Callable[[dict], Awaitable[None]]


def _classify(exc: Exception) -> LLMError:
    name = type(exc).__name__.lower()
    msg = str(exc) or name
    # Auth and unknown ("provider_error") messages can echo request details
    # (including the API key) from some providers, so use safe canned text for
    # those. The lower-risk categories keep the provider's message (it's useful
    # and unlikely to contain secrets).
    if "authentication" in name or "permission" in name or "auth" in name:
        return LLMError("auth", "Authentication failed — check the API key in Settings.")
    if "notfound" in name or "not_found" in name:
        return LLMError("model_not_found", msg)
    if "ratelimit" in name or "rate_limit" in name:
        return LLMError("rate_limit", msg)
    if "connection" in name or "timeout" in name or "apiconnection" in name:
        return LLMError("connection", msg)
    return LLMError("provider_error", "The model provider returned an error.")


def _safe_cost(model: str, usage: Usage, response=None) -> float:
    try:
        if response is not None:
            return float(litellm.completion_cost(completion_response=response) or 0.0)
        # No response object (streaming path): price from token counts.
        # NOTE: completion_cost() expects prompt/completion TEXT, not token counts —
        # cost_per_token() is the token-count API and returns (prompt_cost, completion_cost).
        prompt_cost, completion_cost = litellm.cost_per_token(
            model=model,
            prompt_tokens=usage.input_tokens,
            completion_tokens=usage.output_tokens,
        )
        return float((prompt_cost or 0.0) + (completion_cost or 0.0))
    except Exception:
        return 0.0


def _with_system(messages: list[dict], system: Optional[str]) -> list[dict]:
    if system:
        return [{"role": "system", "content": system}] + list(messages)
    return list(messages)


class LLMRouter:
    """One streaming/blocking entry point over all providers via LiteLLM."""

    async def astream(
        self,
        messages: list[dict],
        resolved: ResolvedCall,
        *,
        system: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        response_format: Optional[dict] = None,
        emit: Optional[EmitCallback] = None,
    ) -> tuple[str, Usage]:
        msgs = _with_system(messages, system)
        extra = {"response_format": response_format} if response_format else {}
        usage = Usage(model=resolved.model)
        parts: list[str] = []

        # Provider errors (opening the stream or iterating it) are normalized to
        # LLMError. Errors raised by the `emit` callback are deliberately NOT caught
        # here — they propagate as-is, so a transport failure (e.g. a closed
        # WebSocket) is never mislabeled as a provider error.
        try:
            response = await litellm.acompletion(
                model=resolved.model,
                messages=msgs,
                stream=True,
                max_tokens=max_tokens,
                temperature=temperature,
                stream_options={"include_usage": True},
                **extra,
                **resolved.kwargs,
            )
            chunks = response.__aiter__()
        except Exception as e:
            raise _classify(e)

        while True:
            try:
                chunk = await chunks.__anext__()
            except StopAsyncIteration:
                break
            except Exception as e:
                raise _classify(e)

            choices = getattr(chunk, "choices", None)
            delta = choices[0].delta.content if choices else None
            if delta:
                parts.append(delta)
                if emit:
                    await emit({"type": "token", "text": delta})
            chunk_usage = getattr(chunk, "usage", None)
            if chunk_usage:
                usage.input_tokens = getattr(chunk_usage, "prompt_tokens", 0) or 0
                usage.output_tokens = getattr(chunk_usage, "completion_tokens", 0) or 0

        usage.cost_usd = _safe_cost(resolved.model, usage)
        return "".join(parts), usage

    async def acomplete(
        self,
        messages: list[dict],
        resolved: ResolvedCall,
        *,
        system: Optional[str] = None,
        max_tokens: int = 1500,
        response_format: Optional[dict] = None,
    ) -> tuple[str, Usage]:
        msgs = _with_system(messages, system)
        extra = {"response_format": response_format} if response_format else {}
        try:
            response = await litellm.acompletion(
                model=resolved.model,
                messages=msgs,
                stream=False,
                max_tokens=max_tokens,
                **extra,
                **resolved.kwargs,
            )
        except Exception as e:
            raise _classify(e)

        text = response.choices[0].message.content or ""
        u = getattr(response, "usage", None)
        usage = Usage(
            model=resolved.model,
            input_tokens=getattr(u, "prompt_tokens", 0) or 0 if u else 0,
            output_tokens=getattr(u, "completion_tokens", 0) or 0 if u else 0,
        )
        usage.cost_usd = _safe_cost(resolved.model, usage, response=response)
        return text, usage
