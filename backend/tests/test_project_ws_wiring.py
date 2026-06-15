import httpx
from httpx import ASGITransport
import uuid


async def test_project_session_model_patch(db_session):
    import main
    from db.models import get_db, Project, ChatSession

    proj = Project(id=str(uuid.uuid4()), name="p", workspace_path="/tmp/p")
    sess = ChatSession(id=str(uuid.uuid4()), project_id=proj.id, title="s")
    db_session.add(proj); db_session.add(sess)
    await db_session.commit()

    async def _override():
        yield db_session
    main.app.dependency_overrides[get_db] = _override
    try:
        async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://t") as client:
            r = await client.patch(
                f"/api/projects/{proj.id}/sessions/{sess.id}",
                json={"model": "ollama_chat/llama3", "model_provider_id": "p9"},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["model"] == "ollama_chat/llama3"
            assert body["model_provider_id"] == "p9"
    finally:
        main.app.dependency_overrides.clear()


def test_main_still_imports():
    import main
    assert main.app is not None
