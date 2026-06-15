import os
import asyncio
import shlex
import subprocess
from pathlib import Path
from typing import Optional, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from config import settings
from core.sandbox.runner import run_subprocess, safe_argv


def _safe_path(project_id: str, rel_path: str) -> Path:
    base = Path(settings.workspace_path) / project_id
    target = (base / rel_path).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise PermissionError(f"Path {rel_path} escapes workspace")
    return target


# ─── File Tools ───────────────────────────────────────────────

class FileReadInput(BaseModel):
    path: str = Field(description="Relative file path inside project workspace")


class FileReadTool(BaseTool):
    name: str = "read_file"
    description: str = "Read a file from the project workspace. Provide a relative path."
    args_schema: Type[BaseModel] = FileReadInput
    project_id: str = ""

    def _run(self, path: str) -> str:
        try:
            fp = _safe_path(self.project_id, path)
            if not fp.exists():
                return f"ERROR: File not found: {path}"
            content = fp.read_text(errors="replace")
            if len(content) > 50000:
                content = content[:50000] + "\n... [TRUNCATED]"
            return f"FILE: {path}\n```\n{content}\n```"
        except Exception as e:
            return f"ERROR reading {path}: {e}"


class FileWriteInput(BaseModel):
    path: str = Field(description="Relative file path to write")
    content: str = Field(description="Content to write to the file")


class FileWriteTool(BaseTool):
    name: str = "write_file"
    description: str = "Write or overwrite a file in the project workspace."
    args_schema: Type[BaseModel] = FileWriteInput
    project_id: str = ""

    def _run(self, path: str, content: str) -> str:
        try:
            fp = _safe_path(self.project_id, path)
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content)
            return f"OK: Wrote {len(content)} chars to {path}"
        except Exception as e:
            return f"ERROR writing {path}: {e}"


class FileListInput(BaseModel):
    path: str = Field(default=".", description="Relative directory path to list")


class FileListTool(BaseTool):
    name: str = "list_files"
    description: str = "List files and directories in the project workspace."
    args_schema: Type[BaseModel] = FileListInput
    project_id: str = ""

    def _run(self, path: str = ".") -> str:
        try:
            base = _safe_path(self.project_id, path)
            if not base.exists():
                return f"ERROR: Path not found: {path}"
            lines = []
            for item in sorted(base.iterdir()):
                prefix = "DIR " if item.is_dir() else "FILE"
                lines.append(f"  {prefix}  {item.name}")
            return f"Contents of {path}:\n" + "\n".join(lines)
        except Exception as e:
            return f"ERROR: {e}"


class FileDeleteInput(BaseModel):
    path: str = Field(description="Relative file path to delete")


class FileDeleteTool(BaseTool):
    name: str = "delete_file"
    description: str = "Delete a file from the project workspace."
    args_schema: Type[BaseModel] = FileDeleteInput
    project_id: str = ""

    def _run(self, path: str) -> str:
        try:
            fp = _safe_path(self.project_id, path)
            if not fp.exists():
                return f"ERROR: Not found: {path}"
            fp.unlink()
            return f"OK: Deleted {path}"
        except Exception as e:
            return f"ERROR: {e}"


# ─── Bash Tool ────────────────────────────────────────────────

class BashInput(BaseModel):
    command: str = Field(description="Shell command to run in project workspace")
    timeout: int = Field(default=30, description="Timeout in seconds")


ALLOWED_COMMANDS = {"python", "python3", "pip", "pytest", "git", "ls", "cat",
                    "grep", "find", "echo", "mkdir", "cp", "mv", "head", "tail",
                    "wc", "sort", "uniq", "curl", "npm", "node"}


class BashTool(BaseTool):
    name: str = "run_bash"
    description: str = "Run shell commands in the project workspace. Safe subset only."
    args_schema: Type[BaseModel] = BashInput
    project_id: str = ""

    def _run(self, command: str, timeout: int = 30) -> str:
        try:
            argv = safe_argv(command, ALLOWED_COMMANDS)
        except ValueError as e:
            return f"ERROR: {e}"
        cwd = str(Path(settings.workspace_path) / self.project_id)
        res = run_subprocess(argv, cwd=cwd, timeout=timeout)
        out = res.stdout + res.stderr
        if len(out) > 10000:
            out = out[:10000] + "\n... [TRUNCATED]"
        return f"EXIT {res.exit_code}\n{out}"


# ─── Web Search Tool ──────────────────────────────────────────

class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    max_results: int = Field(default=5, description="Number of results")


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = "Search the web for current information, research, documentation."
    args_schema: Type[BaseModel] = WebSearchInput
    project_id: str = ""

    def _run(self, query: str, max_results: int = 5) -> str:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=settings.tavily_api_key)
            resp = client.search(query, max_results=max_results, include_answer=True)
            lines = []
            if resp.get("answer"):
                lines.append(f"ANSWER: {resp['answer']}\n")
            for r in resp.get("results", []):
                lines.append(f"SOURCE: {r['url']}")
                lines.append(f"TITLE: {r['title']}")
                lines.append(f"CONTENT: {r['content'][:500]}\n")
            return "\n".join(lines)
        except Exception as e:
            return f"ERROR: Web search failed: {e}"


# ─── Vector Search Tool ───────────────────────────────────────

class VectorSearchInput(BaseModel):
    query: str = Field(description="Semantic search query over project files")
    k: int = Field(default=5, description="Number of results")


class VectorSearchTool(BaseTool):
    name: str = "search_project"
    description: str = "Semantic search over indexed project files. Use to find relevant code, docs, or configs."
    args_schema: Type[BaseModel] = VectorSearchInput
    project_id: str = ""

    def _run(self, query: str, k: int = 5) -> str:
        try:
            import chromadb
            from memory.embedder import get_embeddings
            import asyncio
            client = chromadb.PersistentClient(path=settings.chroma_path)
            col = client.get_collection(f"proj_{self.project_id}")
            embeddings = asyncio.run(get_embeddings([query]))
            results = col.query(query_embeddings=embeddings, n_results=min(k, col.count()))
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            lines = []
            for doc, meta in zip(docs, metas):
                lines.append(f"FILE: {meta.get('file', 'unknown')} (chunk {meta.get('chunk', 0)})")
                lines.append(doc[:600])
                lines.append("")
            return "\n".join(lines) if lines else "No relevant results found."
        except Exception as e:
            return f"ERROR: Vector search failed: {e}. Project may not be indexed yet."


# ─── Git Tool ─────────────────────────────────────────────────

class GitInput(BaseModel):
    command: str = Field(description="Git subcommand: log, status, diff, show, branch")


ALLOWED_GIT = {"log", "status", "diff", "show", "branch", "stash"}


class GitTool(BaseTool):
    name: str = "git_info"
    description: str = "Query git history, status, and diffs. Read-only git access."
    args_schema: Type[BaseModel] = GitInput
    project_id: str = ""

    def _run(self, command: str) -> str:
        if any(c in command for c in ";&|`$()<>\n"):
            return "ERROR: command contains disallowed characters"
        parts = shlex.split(command)
        if not parts or parts[0] not in ALLOWED_GIT:
            return f"ERROR: Only allowed: {sorted(ALLOWED_GIT)}"
        cwd = str(Path(settings.workspace_path) / self.project_id)
        res = run_subprocess(["git", *parts], cwd=cwd, timeout=10)
        out = (res.stdout + res.stderr)
        return out[:5000] if out else "No output"


# ─── AG2 WebSurfer Tool ───────────────────────────────────────
#
# Wraps AG2's WebSurferAgent (Crawl4AI backend) as a CrewAI BaseTool.
# Crawl4AI = headless, no Playwright browser needed, server-safe.
# Falls back to httpx+BeautifulSoup if ag2/crawl4ai not installed.

class WebSurferInput(BaseModel):
    task: str = Field(
        description=(
            "Natural language task for the web surfer. Examples: "
            "'Scrape the pricing table from https://example.com', "
            "'Find the latest release notes for FastAPI', "
            "'Extract all links from https://docs.ag2.ai'. "
            "Can include a URL and/or a research goal."
        )
    )
    url: Optional[str] = Field(
        default=None,
        description="Optional specific URL to start from. If omitted, the surfer searches the web."
    )
    max_pages: int = Field(
        default=3,
        description="Max pages to crawl (1-10). Keep low for speed."
    )


class WebSurferTool(BaseTool):
    """
    AG2 WebSurferAgent wrapped as a CrewAI tool.

    Uses Crawl4AI (headless, no real browser) by default.
    Capable of: scraping pages, following links, extracting structured data,
    searching for documentation, reading articles, crawling multi-page sites.

    Install: pip install ag2[crawl4ai]
    """
    name: str = "web_surfer"
    description: str = (
        "Browse and scrape the web using an AI-powered web surfer. "
        "Can navigate pages, extract content, follow links, and read documentation. "
        "Use for: deep web research, scraping specific URLs, reading docs, "
        "finding API references, extracting structured data from websites. "
        "More powerful than web_search — actually reads page content."
    )
    args_schema: Type[BaseModel] = WebSurferInput
    project_id: str = ""

    def _run(self, task: str, url: Optional[str] = None, max_pages: int = 3) -> str:
        full_task = f"{task}\nStart URL: {url}" if url else task
        try:
            return asyncio.run(self._run_ag2_surfer(full_task, url, max_pages))
        except RuntimeError:
            # Already inside an event loop (FastAPI context)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self._run_ag2_surfer(full_task, url, max_pages))
                return future.result(timeout=120)

    async def _run_ag2_surfer(self, task: str, url: Optional[str], max_pages: int) -> str:
        try:
            return await self._ag2_crawl4ai(task, url, max_pages)
        except ImportError:
            # ag2/crawl4ai not installed — fallback to httpx scraper
            return await self._httpx_fallback(url, task)
        except Exception as e:
            return f"WebSurfer error: {e}\nFalling back to basic fetch...\n" + await self._httpx_fallback(url, task)

    async def _ag2_crawl4ai(self, task: str, url: Optional[str], max_pages: int) -> str:
        """Primary: AG2 WebSurferAgent with Crawl4AI backend."""
        from autogen import LLMConfig
        from autogen.agents.experimental import WebSurferAgent

        llm_config = LLMConfig(config_list=[{
            "api_type": "anthropic",
            "model": settings.llm_model,
            "api_key": settings.anthropic_api_key,
        }])

        surfer = WebSurferAgent(
            name="WebSurfer",
            web_tool="crawl4ai",
            web_tool_kwargs={
                "crawler_config": {
                    "headless": True,
                    "max_pages": max_pages,
                    "word_count_threshold": 50,
                }
            },
            llm_config=llm_config,
        )

        result = await asyncio.to_thread(
            surfer.run,
            task,
            tools=surfer.tools,
        )

        summary = getattr(result, "summary", None) or str(result)
        # Truncate to stay within context
        if len(summary) > 8000:
            summary = summary[:8000] + "\n... [TRUNCATED — content too long]"

        return f"[WebSurfer — Crawl4AI]\nTask: {task}\n\n{summary}"

    async def _httpx_fallback(self, url: Optional[str], task: str) -> str:
        """Fallback: plain httpx fetch + text extraction when ag2 not installed."""
        if not url:
            return (
                "[WebSurfer fallback] No URL provided and ag2[crawl4ai] not installed. "
                "Install with: pip install ag2[crawl4ai]"
            )
        try:
            import httpx
            from html.parser import HTMLParser

            class _Extractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []
                    self._skip = False

                def handle_starttag(self, tag, attrs):
                    if tag in ("script", "style", "nav", "footer"):
                        self._skip = True

                def handle_endtag(self, tag):
                    if tag in ("script", "style", "nav", "footer"):
                        self._skip = False

                def handle_data(self, data):
                    if not self._skip and data.strip():
                        self.text_parts.append(data.strip())

            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 CrewDev/1.0"})
                resp.raise_for_status()
                parser = _Extractor()
                parser.feed(resp.text)
                text = "\n".join(parser.text_parts)[:6000]

            return f"[WebSurfer fallback — httpx]\nURL: {url}\n\n{text}"
        except Exception as e:
            return f"[WebSurfer fallback] Fetch failed: {e}"


# ─── Page Fetch Tool (lightweight single-URL fetch) ───────────

class PageFetchInput(BaseModel):
    url: str = Field(description="Full URL to fetch and extract text from")


class PageFetchTool(BaseTool):
    """
    Lightweight single-page fetcher using httpx.
    Faster than WebSurfer for simple 'read this URL' tasks.
    No browser, no JS rendering. Use WebSurfer for JS-heavy pages.
    """
    name: str = "fetch_page"
    description: str = (
        "Fetch and extract text content from a single URL. "
        "Fast and lightweight. Use for: reading documentation, "
        "getting content from a known URL, reading articles or READMEs. "
        "Does NOT execute JavaScript. For JS-heavy pages, use web_surfer instead."
    )
    args_schema: Type[BaseModel] = PageFetchInput
    project_id: str = ""

    def _run(self, url: str) -> str:
        try:
            import httpx
            from html.parser import HTMLParser

            class _Extractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.parts = []
                    self._skip = False

                def handle_starttag(self, tag, attrs):
                    if tag in ("script", "style", "nav", "footer", "head"):
                        self._skip = True

                def handle_endtag(self, tag):
                    if tag in ("script", "style", "nav", "footer", "head"):
                        self._skip = False

                def handle_data(self, data):
                    if not self._skip and data.strip():
                        self.parts.append(data.strip())

            resp = httpx.get(url, timeout=20, follow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0 CrewDev/1.0"})
            resp.raise_for_status()
            parser = _Extractor()
            parser.feed(resp.text)
            text = "\n".join(parser.parts)
            if len(text) > 8000:
                text = text[:8000] + "\n... [TRUNCATED]"
            return f"URL: {url}\n\n{text}"
        except Exception as e:
            return f"ERROR fetching {url}: {e}"
