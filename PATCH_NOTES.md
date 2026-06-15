# CrewDev fixed build

## Fixed

- Project chat UI crash caused by `setMessages(prev => ...)` while Zustand store only accepted arrays.
- WebSocket DB save bug caused by `ws.app.state.engine`, which was never initialized.
- WebSocket reconnect loop after component unmount.
- WebSocket send race where messages could be dropped before the socket reached OPEN.
- Project indexing background DB session handling.
- RightPanel memory fetch using `undefined/api/...` when `NEXT_PUBLIC_API_URL` was not set.

## Added

- Separate Chat mode, independent from Projects.
- General chat history with New Chat, search, pin, delete, grouped date sections.
- General chat WebSocket: `/ws/chats/{chat_id}`.
- General chat DB tables: `general_chat_sessions`, `general_chat_messages`, `chat_memories`.
- Chat memory panel, separate from project memory.
- Claude-style general chat UI, separate from project-agent chat.

## Important

- Chat does not create projects.
- Projects still use the existing project creation and project-agent flow.
- General chat does not access project files or project tools.
