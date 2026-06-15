from crewai import Agent, LLM
from config import settings
from core.llm.types import ResolvedCall
from tools.all_tools import (
    FileReadTool, FileWriteTool, FileListTool, FileDeleteTool,
    BashTool, WebSearchTool, VectorSearchTool, GitTool,
    WebSurferTool, PageFetchTool,
)


AGENT_CONFIGS = {
    "coder": {
        "role": "Senior Software Engineer",
        "goal": (
            "Write, edit, refactor, and debug code with full awareness of "
            "the project structure and existing patterns. Always read existing "
            "files before modifying. Write clean, well-tested code."
        ),
        "backstory": (
            "You are a senior engineer with 10+ years of experience. You read "
            "existing code thoroughly before changing anything. You write idiomatic, "
            "production-quality code with proper error handling and docstrings."
        ),
        "tools": ["file_read", "file_write", "file_list", "bash", "vector_search"],
    },
    "researcher": {
        "role": "Research and Intelligence Analyst",
        "goal": (
            "Find accurate, current information via web search, deep web surfing, "
            "and the project knowledge base. Synthesize findings clearly and cite sources. "
            "Use web_surfer to actually read pages — not just search snippets."
        ),
        "backstory": (
            "You are a research analyst who cross-references multiple sources "
            "before drawing conclusions. You use web_surfer to read full page content "
            "when search snippets aren't enough. You always distinguish facts from speculation."
        ),
        "tools": ["web_search", "web_surfer", "fetch_page", "vector_search", "file_read"],
    },
    "web_surfer": {
        "role": "Web Research Specialist",
        "goal": (
            "Browse, scrape, and extract information from the web using the AG2 WebSurferAgent. "
            "Navigate multi-page sites, read documentation, extract structured data, "
            "and synthesize findings into clear reports."
        ),
        "backstory": (
            "You are a specialist web researcher powered by AG2's WebSurferAgent with Crawl4AI. "
            "You can navigate to any URL, follow links, read full page content, "
            "and extract exactly what's needed. You always cite the source URLs you visit. "
            "For JavaScript-heavy pages you use web_surfer; for simple pages you use fetch_page."
        ),
        "tools": ["web_surfer", "fetch_page", "web_search", "file_write"],
    },
    "file_manager": {
        "role": "Project File Manager",
        "goal": "Organize, manage, and maintain project files and directory structure.",
        "backstory": "You are a meticulous project manager who keeps codebases clean and organized.",
        "tools": ["file_read", "file_write", "file_list", "file_delete", "bash", "git"],
    },
    "analyst": {
        "role": "Code and Architecture Analyst",
        "goal": (
            "Deeply understand and explain code, architecture decisions, "
            "data flows, and potential improvements."
        ),
        "backstory": "You excel at reading complex codebases and explaining them clearly.",
        "tools": ["file_read", "file_list", "vector_search", "git"],
    },
    "tester": {
        "role": "QA Engineer",
        "goal": "Write comprehensive tests, run them, and ensure code quality.",
        "backstory": "You write thorough unit, integration, and edge-case tests.",
        "tools": ["file_read", "file_write", "file_list", "bash", "vector_search"],
    },
    "devops": {
        "role": "DevOps Engineer",
        "goal": "Manage configuration, infrastructure files, and deployment scripts.",
        "backstory": "You handle Docker, CI/CD, environment configs, and deployment automation.",
        "tools": ["file_read", "file_write", "file_list", "bash", "git"],
    },
}

TOOL_MAP = {
    "file_read": FileReadTool,
    "file_write": FileWriteTool,
    "file_list": FileListTool,
    "file_delete": FileDeleteTool,
    "bash": BashTool,
    "web_search": WebSearchTool,
    "web_surfer": WebSurferTool,
    "fetch_page": PageFetchTool,
    "vector_search": VectorSearchTool,
    "git": GitTool,
}


class AgentFactory:
    def __init__(self, project_id: str, harness=None):
        self.project_id = project_id
        self.harness = harness

    def create(self, agent_type: str, resolved: ResolvedCall, extra_context: str = "") -> Agent:
        cfg = AGENT_CONFIGS.get(agent_type)
        if not cfg:
            cfg = AGENT_CONFIGS["coder"]

        tools = [
            TOOL_MAP[t](project_id=self.project_id)
            for t in cfg["tools"]
            if t in TOOL_MAP
        ]

        backstory = cfg["backstory"]
        if extra_context:
            backstory += f"\n\nProject context:\n{extra_context}"

        return Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=backstory,
            tools=tools,
            llm=LLM(model=resolved.model, **resolved.kwargs),
            verbose=True,
            memory=False,  # we handle memory externally
            max_iter=settings.max_agent_iter,
            allow_delegation=False,
        )

    def infer_agent_type(self, task_description: str) -> str:
        desc = task_description.lower()
        if any(w in desc for w in ["test", "pytest", "unittest", "coverage"]):
            return "tester"
        if any(w in desc for w in ["scrape", "crawl", "browse", "navigate to", "visit", "extract from url", "read the page", "open url"]):
            return "web_surfer"
        if any(w in desc for w in ["search", "research", "find", "look up", "latest", "http://", "https://"]):
            return "researcher"
        if any(w in desc for w in ["docker", "deploy", "ci", "config", "env", ".yml", "dockerfile"]):
            return "devops"
        if any(w in desc for w in ["analyze", "explain", "understand", "review", "audit"]):
            return "analyst"
        if any(w in desc for w in ["organize", "move", "rename", "delete", "structure"]):
            return "file_manager"
        return "coder"
