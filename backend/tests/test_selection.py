import pytest
from core.llm import provider_store as ps
from core.llm import selection as sel
from core.llm.types import ModelSelection, LLMError


async def test_explicit_selection_wins(db_session):
    row = await ps.create_provider(db_session, provider="openai", label="OAI", config={"api_key": "k"})
    s = await sel.resolve_selection(db_session, provider_id=row.id, model="gpt-4o")
    assert s == ModelSelection(provider_config_id=row.id, model="gpt-4o", provider="openai")


async def test_falls_back_to_default_model(db_session):
    row = await ps.create_provider(db_session, provider="anthropic", label="A", config={"api_key": "k"})
    await ps.set_default_model(db_session, f"{row.id}::claude-sonnet-4-6")
    s = await sel.resolve_selection(db_session, provider_id=None, model=None)
    assert s.provider == "anthropic"
    assert s.model == "claude-sonnet-4-6"


async def test_no_config_raises_not_configured(db_session):
    with pytest.raises(LLMError) as ei:
        await sel.resolve_selection(db_session, provider_id=None, model=None)
    assert ei.value.code == "not_configured"


async def test_build_call_resolves(db_session):
    row = await ps.create_provider(db_session, provider="azure", label="AZ",
                                   config={"api_key": "az", "api_base": "https://x", "api_version": "2024-06-01"})
    s = ModelSelection(provider_config_id=row.id, model="my-deploy", provider="azure")
    rc = await sel.build_call(db_session, s)
    assert rc.model == "azure/my-deploy"
    assert rc.kwargs["api_version"] == "2024-06-01"


async def test_build_call_missing_field_raises(db_session):
    row = await ps.create_provider(db_session, provider="azure", label="AZ",
                                   config={"api_key": "az", "api_base": "https://x"})
    s = ModelSelection(provider_config_id=row.id, model="my-deploy", provider="azure")
    with pytest.raises(LLMError) as ei:
        await sel.build_call(db_session, s)
    assert ei.value.code == "not_configured"
    assert "api_version" in ei.value.message
