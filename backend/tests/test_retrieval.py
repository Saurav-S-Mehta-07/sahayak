from app.rag.retriever import Retriever


class FakeEmbeddings:
    def embed(self, texts):
        return [[float(len(text)), 1.0] for text in texts]


class FakeVectorStore:
    def query(self, vector, top_k, where):
        return [
            {
                "id": "chunk-1",
                "document": "PM-KISAN eligibility is described here.",
                "metadata": {
                    "content_hash": "same-content",
                    "page_number": 2,
                    "document_id": "doc-1",
                },
                "similarity_score": 0.8,
            },
            {
                "id": "chunk-2",
                "document": "PM-KISAN eligibility is described here.",
                "metadata": {
                    "content_hash": "same-content",
                    "page_number": 2,
                    "document_id": "doc-1",
                },
                "similarity_score": 0.7,
            },
        ]


def test_retriever_deduplicates_repeated_passages():
    retriever = Retriever(FakeEmbeddings(), FakeVectorStore())
    results = retriever.retrieve(["PM Kisan eligibility"])
    assert len(results) == 1
    assert results[0]["id"] == "chunk-1"


class LowScoreVectorStore:
    def query(self, vector, top_k, where):
        return [
            {
                "id": "weak",
                "document": "Unrelated scheme text",
                "metadata": {"content_hash": "weak"},
                "similarity_score": 0.45,
            }
        ]


def test_retriever_rejects_passages_below_calibrated_threshold():
    retriever = Retriever(FakeEmbeddings(), LowScoreVectorStore(), min_similarity=0.5)
    assert retriever.retrieve(["PM Kisan eligibility"]) == []
