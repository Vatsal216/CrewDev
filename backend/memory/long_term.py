import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import Optional
from config import settings
from .embedder import get_embeddings


class LongTermMemory:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.client = chromadb.PersistentClient(
            path=settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name=f"mem_{project_id}",
            metadata={"hnsw:space": "cosine"}
        )

    async def store(self, user_msg: str, assistant_msg: str, context: str = ""):
        text = f"User: {user_msg}\nAssistant: {assistant_msg[:1000]}"
        embedding = await get_embeddings([text])
        import uuid
        doc_id = str(uuid.uuid4())
        self.collection.upsert(
            documents=[text],
            ids=[doc_id],
            embeddings=embedding,
            metadatas=[{"project_id": self.project_id, "type": "conversation"}]
        )

    async def search(self, query: str, k: int = 5) -> list[str]:
        try:
            q_emb = await get_embeddings([query])
            results = self.collection.query(
                query_embeddings=q_emb,
                n_results=min(k, self.collection.count())
            )
            return results["documents"][0] if results["documents"] else []
        except Exception:
            return []

    async def store_fact(self, fact: str, fact_type: str = "general"):
        embedding = await get_embeddings([fact])
        import uuid
        self.collection.upsert(
            documents=[fact],
            ids=[str(uuid.uuid4())],
            embeddings=embedding,
            metadatas=[{"project_id": self.project_id, "type": fact_type}]
        )

    def count(self) -> int:
        return self.collection.count()
