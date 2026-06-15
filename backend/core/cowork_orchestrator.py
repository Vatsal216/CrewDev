from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

from core.attachments import build_user_content
from core.llm.router import LLMRouter
from core.llm.types import ResolvedCall
from core.token_tracker import TokenTracker

StreamCallback = Callable[[dict], Awaitable[None]]
DOC_OPEN, DOC_CLOSE = "<doc>", "</doc>"


def parse_reply_and_doc(text: str) -> tuple[str, Optional[str]]:
    if DOC_OPEN in text:
        reply = text.split(DOC_OPEN, 1)[0].strip()
        rest = text.split(DOC_OPEN, 1)[1]
        doc = rest.split(DOC_CLOSE, 1)[0].strip() if DOC_CLOSE in rest else None
        return reply, doc
    return text.strip(), None


class CoworkOrchestrator:
    """Co-edit a shared markdown doc. Non-streaming completion, then fake-streams the
    reply and (if present) emits the full updated doc via a `doc_update` event."""

    def __init__(self):
        self.router = LLMRouter()

    async def process(
        self,
        user_message: str,
        history: list[dict],
        doc_content: str,
        resolved: ResolvedCall,
        stream_cb: Optional[StreamCallback] = None,
        skills_block: str = "",
        attachments_text: str = "",
        attachment_images=None,
    ) -> tuple[str, Optional[str]]:
        tracker = TokenTracker()

        async def emit(event: dict):
            if stream_cb:
                await stream_cb(event)

        system = f"""You co-edit a shared markdown document with the user in a workspace.

CURRENT DOCUMENT:
{doc_content or '(empty)'}

Reply to the user conversationally and concisely. If the document should change, output your
reply FIRST, then the COMPLETE updated document at the very end wrapped exactly like:
{DOC_OPEN}
<full updated markdown document>
{DOC_CLOSE}
Only include {DOC_OPEN}…{DOC_CLOSE} if the document should change."""
        if skills_block:
            system = f"{skills_block}\n\n{system}"

        messages = []
        for m in history[-30:]:
            if m.get("role") in {"user", "assistant"} and m.get("content"):
                messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": build_user_content(user_message, attachments_text, attachment_images)})

        text, usage = await self.router.acomplete(messages, resolved, system=system, max_tokens=4000)
        tracker.add_usage(usage, agent="cowork")

        reply, new_doc = parse_reply_and_doc(text)

        for i in range(0, len(reply), 24):
            await emit({"type": "token", "text": reply[i:i + 24]})
            await asyncio.sleep(0.01)

        if new_doc is not None:
            await emit({"type": "doc_update", "doc": new_doc})

        await emit({"type": "usage", **tracker.summary()})
        return reply, new_doc
