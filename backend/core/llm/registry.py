from core.llm.types import ResolvedCall


def _normalize_ollama_base(api_base: str) -> str:
    base = (api_base or "").strip().rstrip("/")
    if base.endswith("/api"):
        base = base[:-4]
    return base


def build_resolved_call(provider: str, config: dict, model: str) -> ResolvedCall:
    """Map (provider, decrypted config, model) → LiteLLM model string + kwargs.

    Pure function: no DB, no network. `config` is the decrypted provider config.
    """
    p = (provider or "").lower()

    if p == "anthropic":
        return ResolvedCall(model=f"anthropic/{model}", kwargs={"api_key": config["api_key"]})

    if p == "openai":
        kwargs = {"api_key": config["api_key"]}
        if config.get("api_base"):
            kwargs["api_base"] = config["api_base"]
        if config.get("organization"):
            kwargs["organization"] = config["organization"]
        return ResolvedCall(model=f"openai/{model}", kwargs=kwargs)

    if p == "azure":
        # For Azure the selected "model" is the deployment name.
        return ResolvedCall(
            model=f"azure/{model}",
            kwargs={
                "api_key": config["api_key"],
                "api_base": config["api_base"],
                "api_version": config["api_version"],
            },
        )

    if p == "ollama":
        kwargs = {"api_base": _normalize_ollama_base(config["api_base"])}
        if config.get("api_key"):
            kwargs["api_key"] = config["api_key"]
        return ResolvedCall(model=f"ollama_chat/{model}", kwargs=kwargs)

    raise ValueError(f"Unknown provider: {provider}")
