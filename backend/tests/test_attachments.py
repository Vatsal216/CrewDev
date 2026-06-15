from core.attachments import extract, build_user_content


def test_extract_text():
    r = extract("notes.md", b"# Hello\nworld")
    assert r["kind"] == "text" and "Hello" in r["text"]


def test_extract_csv():
    r = extract("data.csv", b"a,b\n1,2")
    assert r["kind"] == "text" and "a,b" in r["text"]


def test_extract_image():
    r = extract("pic.png", b"\x89PNG\r\n\x1a\n")
    assert r["kind"] == "image"
    assert r["data_url"].startswith("data:image/png;base64,")


def test_extract_pdf(monkeypatch):
    import pdfplumber

    class _Page:
        def extract_text(self): return "PDF TEXT"

    class _PDF:
        pages = [_Page()]
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(pdfplumber, "open", lambda f: _PDF())
    r = extract("doc.pdf", b"%PDF-fake")
    assert r["kind"] == "text" and "PDF TEXT" in r["text"]


def test_extract_unsupported():
    r = extract("a.bin", b"\x00\x01\x02")
    assert r["kind"] == "text" and "unsupported" in r["text"]


def test_build_user_content_text_only():
    out = build_user_content("hi", attachments_text="DOC", attachment_images=None)
    assert out == "DOC\n\nhi"


def test_build_user_content_with_images():
    out = build_user_content("hi", attachments_text="DOC", attachment_images=["data:image/png;base64,AAA"])
    assert isinstance(out, list)
    assert out[0]["type"] == "text" and "DOC" in out[0]["text"]
    assert out[1]["type"] == "image_url" and out[1]["image_url"]["url"] == "data:image/png;base64,AAA"
