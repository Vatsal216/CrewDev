import uuid
import shutil
import asyncio
from pathlib import Path
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import chromadb
from chromadb.config import Settings as ChromaSettings
from db.models import Project, HarnessState
from memory.embedder import get_embeddings
from config import settings

SKIP_PATTERNS = {
    ".git", "node_modules", "__pycache__", ".next", "dist",
    "build", ".venv", "venv", ".env", "*.pyc", "*.pyo",
    "chroma_db", ".DS_Store"
}

TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
    ".cpp", ".c", ".h", ".cs", ".rb", ".php", ".swift", ".kt",
    ".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".env.example",
    ".html", ".css", ".scss", ".sql", ".sh", ".bash", ".dockerfile",
    ".gitignore", ".env.example", "Dockerfile", "Makefile"
}


def _should_skip(path: Path) -> bool:
    for part in path.parts:
        if part in SKIP_PATTERNS:
            return True
    return False


def _should_index(path: Path) -> bool:
    if _should_skip(path):
        return False
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name in {"Dockerfile", "Makefile"}


class ProjectManager:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_project(self, name: str, description: str = "") -> Project:
        project_id = str(uuid.uuid4())
        workspace = Path(settings.workspace_path) / project_id
        workspace.mkdir(parents=True, exist_ok=True)

        project = Project(
            id=project_id,
            name=name,
            description=description,
            workspace_path=str(workspace),
        )
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def get_project(self, project_id: str) -> Optional[Project]:
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()

    async def list_projects(self) -> list[Project]:
        result = await self.db.execute(select(Project).order_by(Project.updated_at.desc()))
        return list(result.scalars().all())

    async def delete_project(self, project_id: str):
        project = await self.get_project(project_id)
        if project:
            # Remove workspace
            ws = Path(project.workspace_path)
            if ws.exists():
                shutil.rmtree(ws)
            # Remove chroma collection
            try:
                client = chromadb.PersistentClient(path=settings.chroma_path)
                client.delete_collection(f"proj_{project_id}")
            except Exception:
                pass
            await self.db.delete(project)
            await self.db.commit()

    async def save_uploaded_file(self, project_id: str, filename: str, content: bytes) -> str:
        workspace = Path(settings.workspace_path) / project_id
        workspace.mkdir(parents=True, exist_ok=True)
        fp = workspace / filename
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_bytes(content)
        return str(fp.relative_to(workspace))

    async def get_file_tree(self, project_id: str) -> list[dict]:
        workspace = Path(settings.workspace_path) / project_id
        if not workspace.exists():
            return []
        return self._walk_tree(workspace, workspace)

    def _walk_tree(self, path: Path, base: Path) -> list[dict]:
        items = []
        for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
            if _should_skip(item):
                continue
            rel = str(item.relative_to(base))
            if item.is_dir():
                items.append({
                    "type": "dir",
                    "name": item.name,
                    "path": rel,
                    "children": self._walk_tree(item, base)
                })
            else:
                items.append({
                    "type": "file",
                    "name": item.name,
                    "path": rel,
                    "size": item.stat().st_size,
                    "extension": item.suffix
                })
        return items


class ProjectIndexer:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.chroma = chromadb.PersistentClient(
            path=settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection = self.chroma.get_or_create_collection(
            name=f"proj_{project_id}",
            metadata={"hnsw:space": "cosine"}
        )
        # Imported lazily here (only needed for indexing) so a missing indexing
        # dependency can't break project CRUD (create/list/get/delete).
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=150,
            separators=["\n\n", "\n", " ", ""]
        )

    async def index(self, workspace_path: str, progress_cb=None) -> int:
        workspace = Path(workspace_path)
        all_docs, all_ids, all_metas = [], [], []

        files = [f for f in workspace.rglob("*") if f.is_file() and _should_index(f)]
        total = len(files)

        for i, file in enumerate(files):
            if progress_cb:
                await progress_cb({"type": "index_progress", "file": file.name, "current": i+1, "total": total})

            try:
                text = file.read_text(errors="replace")
                if len(text) < 50:  # skip empty/tiny files
                    continue
                chunks = self.splitter.split_text(text)
                rel_path = str(file.relative_to(workspace))

                for j, chunk in enumerate(chunks[:50]):  # max 50 chunks per file
                    doc_id = f"{self.project_id}:{rel_path}:{j}"
                    all_docs.append(chunk)
                    all_ids.append(doc_id)
                    all_metas.append({"file": rel_path, "chunk": j, "project_id": self.project_id})

            except Exception:
                continue

        if not all_docs:
            return 0

        # Batch embed
        BATCH = 64
        for i in range(0, len(all_docs), BATCH):
            batch_docs = all_docs[i:i+BATCH]
            batch_ids = all_ids[i:i+BATCH]
            batch_metas = all_metas[i:i+BATCH]
            embeddings = await get_embeddings(batch_docs)
            self.collection.upsert(
                documents=batch_docs,
                ids=batch_ids,
                metadatas=batch_metas,
                embeddings=embeddings
            )

        return len(all_docs)

    def search(self, query: str, k: int = 5) -> list[dict]:
        import asyncio
        try:
            embeddings = asyncio.run(get_embeddings([query]))
            count = self.collection.count()
            if count == 0:
                return []
            results = self.collection.query(
                query_embeddings=embeddings,
                n_results=min(k, count)
            )
            return [
                {"content": doc, "file": meta.get("file"), "chunk": meta.get("chunk")}
                for doc, meta in zip(results["documents"][0], results["metadatas"][0])
            ]
        except Exception:
            return []
