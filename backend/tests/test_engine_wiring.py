import httpx
from httpx import ASGITransport
import uuid


async def test_session_engine_patch(db_session):
    import main
    from db.models import get_db, Project, ChatSession

    proj = Project(id=str(uuid.uuid4()), name="p", workspace_path="/tmp/p")
    sess = ChatSession(id=str(uuid.uuid4()), project_id=proj.id, title="s")
    db_session.add(proj); db_session.add(sess); await db_session.commit()

    async def _o(): yield db_session
    main.app.dependency_overrides[get_db] = _o
    try:
        async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://t") as c:
            r = await c.patch(f"/api/projects/{proj.id}/sessions/{sess.id}", json={"engine": "deepagents"})
            assert r.status_code == 200
            assert r.json()["engine"] == "deepagents"
    finally:
        main.app.dependency_overrides.clear()
