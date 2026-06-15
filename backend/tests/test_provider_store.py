import os
from types import SimpleNamespace
from core.llm import provider_store as ps


async def test_create_list_get_update_delete(db_session):
    row = await ps.create_provider(
        db_session, provider="openai", label="OAI",
        config={"api_key": "sk-secret-123", "organization": "org-x"}, is_default=True,
    )
    assert row.id
    assert (await ps.get_provider(db_session, row.id)).label == "OAI"
    assert len(await ps.list_providers(db_session)) == 1

    assert ps.decrypt_config(row)["api_key"] == "sk-secret-123"

    updated = await ps.update_provider(db_session, row.id, label="OAI-2",
                                       config_updates={"api_key": "sk-new-456"})
    assert updated.label == "OAI-2"
    assert ps.decrypt_config(updated)["api_key"] == "sk-new-456"
    assert ps.decrypt_config(updated)["organization"] == "org-x"

    assert await ps.delete_provider(db_session, row.id) is True
    assert await ps.list_providers(db_session) == []


async def test_public_view_masks_secrets(db_session):
    row = await ps.create_provider(db_session, provider="openai", label="OAI",
                                   config={"api_key": "sk-abcdefgh", "organization": "org-x"})
    view = ps.public_view(row)
    assert view["has_key"] is True
    assert view["key_masked"] == "sk-…efgh"
    assert view["config"] == {"organization": "org-x"}
    assert "sk-abcdefgh" not in str(view)


async def test_single_default(db_session):
    a = await ps.create_provider(db_session, provider="openai", label="A",
                                 config={"api_key": "k"}, is_default=True)
    b = await ps.create_provider(db_session, provider="anthropic", label="B",
                                 config={"api_key": "k"}, is_default=True)
    rows = {r.id: r for r in await ps.list_providers(db_session)}
    assert rows[b.id].is_default is True
    assert rows[a.id].is_default is False


async def test_default_model_get_set(db_session):
    assert await ps.get_default_model(db_session) is None
    await ps.set_default_model(db_session, "pid::gpt-4o")
    assert await ps.get_default_model(db_session) == "pid::gpt-4o"
    await ps.set_default_model(db_session, "pid::gpt-4o-mini")
    assert await ps.get_default_model(db_session) == "pid::gpt-4o-mini"


async def test_seed_default_from_env_anthropic(db_session):
    settings = SimpleNamespace(anthropic_api_key="sk-ant", openai_api_key="",
                               ollama_base_url="", llm_model="claude-sonnet-4-6")
    assert await ps.seed_default_from_env(db_session, settings) is True
    providers = await ps.list_providers(db_session)
    assert len(providers) == 1 and providers[0].provider == "anthropic"
    assert await ps.get_default_model(db_session) == f"{providers[0].id}::claude-sonnet-4-6"
    assert await ps.seed_default_from_env(db_session, settings) is False
