from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class ProjectEngine(Protocol):
    async def process(
        self,
        user_message: str,
        stream_cb=None,
        *,
        skills_block: str = "",
        attachments_text: str = "",
        attachment_images: Optional[list] = None,
    ) -> str: ...
