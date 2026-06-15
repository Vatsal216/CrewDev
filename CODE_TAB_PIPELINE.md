# Separate Code Tab Pipeline

This patch fixes the previous design mistake where Code Agent behavior was tied to Cowork.

## Separation

- General Chat remains normal chat + optional safe agent mode.
- Cowork remains shared markdown document collaboration only.
- Projects remain the existing project-agent area.
- Code is now a separate Claude Code-style tab and pipeline.

## Frontend

- Sidebar has a new `CODE` section.
- `CodePanel.tsx` is a dedicated chat UI for coding workspaces.
- Code uses `/ws/code/{code_session_id}` and `/api/code`.
- The right panel shows the Code workspace file tree.

## Backend

- `CodeSession` and `CodeMessage` are separate tables.
- `/api/code` creates and manages Code workspaces.
- `/ws/code/{code_session_id}` streams live agent events and tokens.
- Code creates a hidden internal Project workspace so existing file/bash/validation tools can be reused safely.
- Hidden Code projects are excluded from the normal Projects list.

## Runtime Flow

```text
User opens Code tab
 → creates CodeSession
 → backend creates hidden Project + ChatSession
 → CodePanel connects to /ws/code/{code_session_id}
 → backend resolves selected model/provider
 → backend runs CrewAI or DeepAgents engine against hidden workspace
 → agent can read/write files and run safe commands
 → live status/tokens stream to CodePanel
 → file tree refreshes after final answer
```

## Why hidden Project is used

The existing project engine already has the safe file tools, bash allowlist, validation loop, model routing, skills, and DeepAgents support. The Code tab uses those internals but keeps the user-facing workflow separate from Projects and Cowork.
