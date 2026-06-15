# General Chat Agent Mode Patch

This patch adds a normal-chat Agent Mode without project-linked access.

## Added

- `backend/core/general_agent_orchestrator.py`
  - Planner call
  - Safe tool loop
  - Final streamed synthesis
  - Events: `agent_status`, `agent_plan`, `tool_call`, `tool_result`

- `GeneralChatSession.agent_enabled`
- `GeneralChatSession.mode` with allowed values `direct` and `agent`
- Lightweight additive DB migration for existing local DBs
- `/api/chats` create/update support for `agent_enabled` and `mode`
- `/ws/chats/{chat_id}` now branches:
  - Direct mode -> `GeneralChatOrchestrator`
  - Agent mode -> `GeneralAgentOrchestrator`
- `GeneralChatPanel.tsx` Agent on/off button
- Agent status display in the chat header

## Boundaries

Agent Mode is only for normal chat. It does not access project files, does not run bash, does not mutate git, and does not create projects.

## Tool behavior

Agent Mode can use these safe tools only when Web is enabled for the chat:

- `web_search`
- `fetch_page`

If Web is off, the agent still plans and reasons, but tool requests are skipped.
