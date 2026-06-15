import pytest
from core.llm.registry import build_resolved_call


def test_anthropic_mapping():
    rc = build_resolved_call("anthropic", {"api_key": "sk-ant"}, "claude-sonnet-4-6")
    assert rc.model == "anthropic/claude-sonnet-4-6"
    assert rc.kwargs == {"api_key": "sk-ant"}


def test_openai_mapping_with_optional_fields():
    rc = build_resolved_call(
        "openai",
        {"api_key": "sk-oai", "api_base": "https://proxy", "organization": "org-1"},
        "gpt-4o",
    )
    assert rc.model == "openai/gpt-4o"
    assert rc.kwargs == {"api_key": "sk-oai", "api_base": "https://proxy", "organization": "org-1"}


def test_openai_mapping_minimal():
    rc = build_resolved_call("openai", {"api_key": "sk-oai"}, "gpt-4o-mini")
    assert rc.model == "openai/gpt-4o-mini"
    assert rc.kwargs == {"api_key": "sk-oai"}


def test_azure_mapping():
    rc = build_resolved_call(
        "azure",
        {"api_key": "az-key", "api_base": "https://my.openai.azure.com", "api_version": "2024-06-01"},
        "my-gpt4o-deployment",
    )
    assert rc.model == "azure/my-gpt4o-deployment"
    assert rc.kwargs == {
        "api_key": "az-key",
        "api_base": "https://my.openai.azure.com",
        "api_version": "2024-06-01",
    }


def test_ollama_mapping_no_key():
    rc = build_resolved_call("ollama", {"api_base": "http://localhost:11434"}, "llama3")
    assert rc.model == "ollama_chat/llama3"
    assert rc.kwargs == {"api_base": "http://localhost:11434"}


def test_ollama_mapping_with_cloud_key():
    rc = build_resolved_call(
        "ollama",
        {"api_base": "https://ollama.com/api", "api_key": "ollama-key"},
        "glm-5:cloud",
    )
    assert rc.model == "ollama_chat/glm-5:cloud"
    assert rc.kwargs == {"api_base": "https://ollama.com", "api_key": "ollama-key"}


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        build_resolved_call("cohere", {"api_key": "x"}, "command")
