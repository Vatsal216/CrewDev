# CrewDev — AI Development Platform

Claude Code-style multi-agent platform using CrewAI, FastAPI, and Next.js.

## Architecture

```
User → Next.js UI → FastAPI WS → Main Orchestrator
                                    ├── Task Planner (Claude)
                                    ├── Agent Factory → [Coder | Researcher | Tester | Analyst | DevOps]
                                    │     └── Tools: FileRead/Write, Bash, WebSearch, VectorSearch, Git
                                    ├── Validation Loop (Claude reviewer)
                                    ├── Project Harness (persistent awareness)
                                    └── Memory: Redis (short-term) + ChromaDB (long-term) + Postgres (history)
```

## Stack

| Layer | Tech |
|-------|------|
| Agents | CrewAI 0.70+ |
| LLM | Claude Sonnet (Anthropic) |
| Embeddings | Voyage AI (voyage-3) |
| Vector DB | ChromaDB |
| Session memory | Redis |
| Relational DB | Postgres |
| Web search | Tavily |
| Backend | FastAPI + WebSocket |
| Frontend | Next.js 14 + Zustand |

## Quick start

### 1. API keys

```bash
cp backend/.env.example backend/.env
# Fill in:
# ANTHROPIC_API_KEY=sk-ant-...
# VOYAGE_API_KEY=pa-...        (get at voyage.ai)
# TAVILY_API_KEY=tvly-...      (get at app.tavily.com)
```

### 2. Run

```bash
# Docker (recommended)
docker-compose up

# Or manual
bash scripts/start.sh
```

### 3. Open

- UI: http://localhost:3000
- API docs: http://localhost:8000/docs

## Usage

1. Create a project
2. Upload project files (or create new)
3. Click "Index" to embed files into ChromaDB for semantic search
4. Chat — agents will read/write/research your project

## Agent types

| Agent | Triggered when |
|-------|----------------|
| `coder` | Default — write, edit, refactor code |
| `researcher` | Search/research/find keywords |
| `tester` | test/pytest/coverage keywords |
| `analyst` | analyze/explain/review keywords |
| `file_manager` | organize/move/rename/delete keywords |
| `devops` | docker/deploy/config/env keywords |

## Validation loop

Each agent output is reviewed by Claude before returning to user.
If it fails criteria, agent is given feedback and retries (max 3 iterations).

## Key files

```
backend/
  main.py                 # FastAPI + WebSocket
  core/orchestrator.py    # Main brain — planning + coordination
  core/agent_factory.py   # Runtime agent spawner
  core/validator.py       # Output review loop
  core/harness.py         # Persistent project awareness
  tools/all_tools.py      # FileRead/Write, Bash, WebSearch, VectorSearch, Git
  memory/short_term.py    # Redis session history
  memory/long_term.py     # ChromaDB conversation memory
  projects/manager.py     # Project CRUD + file indexing

frontend/
  app/page.tsx            # Main app shell
  components/ChatPanel.tsx    # Chat UI with streaming
  components/AgentTrace.tsx   # Live agent execution view
  components/Sidebar.tsx      # Project list
  components/FileExplorer.tsx # Project file tree
  components/RightPanel.tsx   # Files + Memory tabs
  lib/store.ts            # Zustand global state
  lib/api.ts              # REST + WebSocket client
```

## Extending

### Add a new agent type

1. Add config to `AGENT_CONFIGS` in `backend/core/agent_factory.py`
2. Add tool names to the `tools` list
3. Add keyword detection in `infer_agent_type()`

### Add a new tool

1. Create a class extending `BaseTool` in `backend/tools/all_tools.py`
2. Add to `TOOL_MAP` in `agent_factory.py`

### Change LLM

Edit `LLM_MODEL` in `.env`. Any LiteLLM-compatible model works with CrewAI.
