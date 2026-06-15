from core.llm import provider_store, registry
from core.llm.types import ModelSelection, ResolvedCall, LLMError


async def resolve_selection(db, *, provider_id=None, model=None) -> ModelSelection:
    """Resolve which (provider, model) to use, by precedence:
    explicit session selection → global default → (none) → LLMError."""
    if provider_id and model:
        row = await provider_store.get_provider(db, provider_id)
        if row and row.enabled:
            return ModelSelection(provider_config_id=row.id, model=model, provider=row.provider)

    default = await provider_store.get_default_model(db)
    if default and "::" in default:
        pid, mname = default.split("::", 1)
        row = await provider_store.get_provider(db, pid)
        if row and row.enabled:
            return ModelSelection(provider_config_id=row.id, model=mname, provider=row.provider)

    raise LLMError("not_configured", "No usable model. Add a provider in Settings.")


async def build_call(db, selection: ModelSelection) -> ResolvedCall:
    """Load + decrypt the selected provider, validate required fields, and resolve
    to a LiteLLM ResolvedCall. Raises LLMError('not_configured') with the missing
    field if the config is incomplete."""
    row = await provider_store.get_provider(db, selection.provider_config_id)
    if not row:
        raise LLMError("not_configured", "Selected provider no longer exists.")
    cfg = provider_store.decrypt_config(row)
    missing = [f for f in provider_store.REQUIRED_FIELDS.get(row.provider, []) if not cfg.get(f)]
    if missing:
        raise LLMError("not_configured", f"Provider '{row.label}' missing: {', '.join(missing)}")
    return registry.build_resolved_call(row.provider, cfg, selection.model)
