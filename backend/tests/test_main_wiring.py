def test_main_imports_without_heavy_stack():
    # crewai/chromadb/redis are NOT installed in this venv. main must still import,
    # which proves MainOrchestrator/ProjectManager are lazily imported.
    import main
    assert main.app is not None


def test_providers_router_mounted():
    import main
    # Use the OpenAPI schema (stable across FastAPI versions) rather than walking
    # app.routes — FastAPI 0.137 stores included routers as an _IncludedRouter object
    # without a .path attribute.
    paths = set(main.app.openapi().get("paths", {}).keys())
    assert "/api/providers" in paths
    assert "/api/settings/default-model" in paths


def test_chat_json_includes_model_fields():
    import main
    from db.models import GeneralChatSession
    from datetime import datetime
    chat = GeneralChatSession(id="c1", title="t", model="gpt-4o", model_provider_id="p1",
                              created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    data = main.chat_to_json(chat)
    assert data["model"] == "gpt-4o"
    assert data["model_provider_id"] == "p1"


async def test_chat_model_patch_persists(db_session):
    # The per-chat model selection must be settable via PATCH /api/chats/{id}.
    import httpx
    from httpx import ASGITransport
    import main
    from db.models import get_db

    async def _override():
        yield db_session

    main.app.dependency_overrides[get_db] = _override
    try:
        transport = ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            chat = (await client.post("/api/chats", json={})).json()
            patched = (await client.patch(
                f"/api/chats/{chat['id']}",
                json={"model": "gpt-4o", "model_provider_id": "p1"},
            )).json()
            assert patched["model"] == "gpt-4o"
            assert patched["model_provider_id"] == "p1"
    finally:
        main.app.dependency_overrides.clear()
