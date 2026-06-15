import io
import os
import base64

TEXT_EXTS = {".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".csv",
             ".yaml", ".yml", ".html", ".css", ".sh", ".go", ".rs", ".java", ".rb",
             ".toml", ".xml", ".log"}
IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".gif": "image/gif", ".webp": "image/webp"}


def extract(filename: str, data: bytes, max_chars: int = 20000) -> dict:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in IMAGE_MIME:
        b64 = base64.b64encode(data).decode()
        return {"name": filename, "kind": "image", "data_url": f"data:{IMAGE_MIME[ext]};base64,{b64}"}
    if ext == ".pdf":
        try:
            import pdfplumber
            parts = []
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page in pdf.pages:
                    parts.append(page.extract_text() or "")
            return {"name": filename, "kind": "text", "text": "\n".join(parts)[:max_chars]}
        except Exception:
            return {"name": filename, "kind": "text", "text": f"[could not read PDF: {filename}]"}
    if ext in TEXT_EXTS or ext == "":
        return {"name": filename, "kind": "text", "text": data.decode("utf-8", "replace")[:max_chars]}
    return {"name": filename, "kind": "text", "text": f"[unsupported file type: {filename}]"}


def build_user_content(user_message: str, attachments_text: str = "", attachment_images=None):
    text = f"{attachments_text}\n\n{user_message}" if attachments_text else user_message
    if attachment_images:
        return [{"type": "text", "text": text}] + \
               [{"type": "image_url", "image_url": {"url": u}} for u in attachment_images]
    return text
