# Ollama Cloud API Key Patch

This patch adds Ollama Cloud API key support without breaking local Ollama.

## UI

`frontend/components/SettingsModal.tsx`

Ollama provider now shows two fields:

- Base URL
  - Local: `http://localhost:11434`
  - Cloud: `https://ollama.com`
- API Key
  - Optional for local Ollama
  - Required for Ollama Cloud

## Backend provider store

`backend/core/llm/provider_store.py`

Changes:

- Added `normalize_ollama_base()` so users can enter either `https://ollama.com` or `https://ollama.com/api`.
- Added `is_ollama_cloud()` so API key is required only for hosted Ollama Cloud.
- `available_models()` now sends `Authorization: Bearer <api_key>` when an Ollama API key exists.
- Ollama connection error message now covers auth failures.
- Env seeding now supports `OLLAMA_API_KEY`.

## LiteLLM registry

`backend/core/llm/registry.py`

Changes:

- Ollama `api_base` is normalized before passing to LiteLLM.
- `api_key` is passed to LiteLLM when present.

## Environment

`backend/.env.example`

Added:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_API_KEY=

# For Ollama Cloud:
# OLLAMA_BASE_URL=https://ollama.com
# OLLAMA_API_KEY=ollama_...
```

## Tests

Updated:

- `backend/tests/test_registry.py`
- `backend/tests/test_conftest_fixture.py`

