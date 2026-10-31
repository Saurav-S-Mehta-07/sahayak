from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.rag.embeddings import EmbeddingManager
from app.rag.ingestion import IngestionService
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService
from app.services.eligibility_service import EligibilityService
from app.services.llm_service import LLMService
from app.services.memory_service import MemoryService
from app.services.scheme_service import SchemeService


@dataclass
class Runtime:
    embeddings: EmbeddingManager
    vector_store: VectorStore
    retriever: Retriever
    ingestion: IngestionService
    memory: MemoryService
    llm: LLMService
    chat: ChatService
    eligibility: EligibilityService
    schemes: SchemeService
    documents: DocumentService


@lru_cache(maxsize=1)
def get_runtime() -> Runtime:
    embeddings = EmbeddingManager()
    vector_store = VectorStore(embeddings)
    retriever = Retriever(embeddings, vector_store)
    ingestion = IngestionService(embeddings, vector_store)
    memory = MemoryService()
    llm = LLMService()
    return Runtime(
        embeddings=embeddings,
        vector_store=vector_store,
        retriever=retriever,
        ingestion=ingestion,
        memory=memory,
        llm=llm,
        chat=ChatService(retriever, memory, llm),
        eligibility=EligibilityService(retriever),
        schemes=SchemeService(ingestion),
        documents=DocumentService(ingestion),
    )
