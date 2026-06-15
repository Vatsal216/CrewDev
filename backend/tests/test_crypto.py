import importlib

import pytest


def _fresh_crypto(monkeypatch, secret="unit-test-secret"):
    monkeypatch.setenv("APP_SECRET", secret)
    import core.llm.crypto as crypto
    return importlib.reload(crypto)


def test_encrypt_decrypt_round_trip(monkeypatch):
    crypto = _fresh_crypto(monkeypatch)
    token = crypto.encrypt({"api_key": "sk-12345", "api_base": "https://x"})
    assert isinstance(token, str)
    assert "sk-12345" not in token  # actually encrypted, not plain
    assert crypto.decrypt(token) == {"api_key": "sk-12345", "api_base": "https://x"}


def test_same_secret_same_key(monkeypatch):
    crypto = _fresh_crypto(monkeypatch, "shared")
    token = crypto.encrypt({"k": "v"})
    crypto2 = _fresh_crypto(monkeypatch, "shared")
    assert crypto2.decrypt(token) == {"k": "v"}


def test_mask():
    import core.llm.crypto as crypto
    assert crypto.mask("sk-abcdefgh") == "sk-…efgh"
    assert crypto.mask("sk-abcd") == "…cd"   # 7 chars: head+tail must not reveal everything
    assert crypto.mask("xy") == "…xy"
    assert crypto.mask("") == ""


def test_decrypt_with_wrong_secret_fails(monkeypatch):
    crypto_a = _fresh_crypto(monkeypatch, "secret-A")
    token = crypto_a.encrypt({"k": "v"})
    crypto_b = _fresh_crypto(monkeypatch, "secret-B")
    with pytest.raises(Exception):
        crypto_b.decrypt(token)
