import os
import uuid
import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import settings
from core.sandbox.runner import run_python

router = APIRouter()
_IMG = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


class ExecReq(BaseModel):
    code: str


def _run_root() -> str:
    p = os.path.join(settings.workspace_path, "_exec")
    os.makedirs(p, exist_ok=True)
    return p


@router.post("/api/exec")
async def exec_code(req: ExecReq):
    if not req.code.strip():
        raise HTTPException(400, "Empty code.")
    run_id = str(uuid.uuid4())
    run_dir = os.path.join(_run_root(), run_id)
    result, artifacts = await asyncio.to_thread(run_python, req.code, run_dir)
    return {
        "run_id": run_id,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "artifacts": [
            {"name": n, "is_image": os.path.splitext(n)[1].lower() in _IMG}
            for n in artifacts
        ],
    }


@router.get("/api/exec/{run_id}/artifact/{name}")
async def get_artifact(run_id: str, name: str):
    run_dir = os.path.realpath(os.path.join(_run_root(), run_id))
    target = os.path.realpath(os.path.join(run_dir, name))
    if not target.startswith(run_dir + os.sep) or not os.path.isfile(target):
        raise HTTPException(404, "Artifact not found")
    return FileResponse(target)
