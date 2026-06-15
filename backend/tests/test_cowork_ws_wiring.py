def test_cowork_ws_route_registered():
    import main
    ws_paths = {getattr(r, "path", None) for r in main.app.routes}
    assert "/ws/cowork/{session_id}" in ws_paths
    # REST routes too (via OpenAPI, stable across FastAPI versions)
    paths = set(main.app.openapi().get("paths", {}).keys())
    assert "/api/cowork" in paths
