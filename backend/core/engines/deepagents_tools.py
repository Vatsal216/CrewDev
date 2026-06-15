import asyncio
from langchain_core.tools import tool
from tools.all_tools import (
    FileReadTool, FileWriteTool, FileListTool, FileDeleteTool,
    BashTool, WebSearchTool, VectorSearchTool, GitTool,
)


def build_tools(project_id: str) -> list:
    """LangChain tools for DeepAgents that reuse the existing CrewAI tools' logic
    (hardened bash, workspace-confined files, etc.) via their `_run`, off-thread."""
    fr, fw, fl, fd = (FileReadTool(project_id=project_id), FileWriteTool(project_id=project_id),
                      FileListTool(project_id=project_id), FileDeleteTool(project_id=project_id))
    bash, web, vec, git = (BashTool(project_id=project_id), WebSearchTool(project_id=project_id),
                           VectorSearchTool(project_id=project_id), GitTool(project_id=project_id))

    @tool
    async def read_file(path: str) -> str:
        """Read a file from the project workspace (relative path)."""
        return await asyncio.to_thread(fr._run, path)

    @tool
    async def write_file(path: str, content: str) -> str:
        """Write/overwrite a file in the project workspace."""
        return await asyncio.to_thread(fw._run, path, content)

    @tool
    async def list_files(path: str = ".") -> str:
        """List files/dirs in the project workspace."""
        return await asyncio.to_thread(fl._run, path)

    @tool
    async def delete_file(path: str) -> str:
        """Delete a file in the project workspace."""
        return await asyncio.to_thread(fd._run, path)

    @tool
    async def run_bash(command: str) -> str:
        """Run an allowlisted, injection-safe shell command in the project workspace."""
        return await asyncio.to_thread(bash._run, command)

    @tool
    async def web_search(query: str) -> str:
        """Search the web for current information."""
        return await asyncio.to_thread(web._run, query)

    @tool
    async def search_project(query: str) -> str:
        """Semantic search over indexed project files."""
        return await asyncio.to_thread(vec._run, query)

    @tool
    async def git_info(command: str) -> str:
        """Read-only git info: log, status, diff, show, branch."""
        return await asyncio.to_thread(git._run, command)

    return [read_file, write_file, list_files, delete_file, run_bash, web_search, search_project, git_info]
