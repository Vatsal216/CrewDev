from fastapi import APIRouter, UploadFile, File
from core.attachments import extract

router = APIRouter()
MAX_BYTES = 5 * 1024 * 1024


@router.post("/api/attachments")
async def upload_attachments(files: list[UploadFile] = File(...)):
    out = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_BYTES:
            out.append({"name": f.filename, "kind": "text", "text": f"[file too large: {f.filename}]"})
        else:
            out.append(extract(f.filename or "file", data))
    return out
