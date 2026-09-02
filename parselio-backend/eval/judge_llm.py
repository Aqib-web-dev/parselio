import litellm
from ragas.llms import llm_factory

from documents.services import GENERATION_MODEL


EMBEDDING_MODEL = "gemini/gemini-embedding-001"


class _LiteLLMQueryEmbeddings:
    """Minimal embed_query/embed_documents adapter over litellm.embedding().

    ragas.embeddings.litellm_provider.LiteLLMEmbeddings only implements the
    modern embed_text/embed_texts interface, but ResponseRelevancy calls
    self.embeddings.embed_query() directly (ragas/metrics/_answer_relevance.py),
    so it needs the legacy method names instead.
    """

    def __init__(self, model):
        self.model = model

    def embed_query(self, text):
        return litellm.embedding(model=self.model, input=[text]).data[0]["embedding"]

    def embed_documents(self, texts):
        return [d["embedding"] for d in litellm.embedding(model=self.model, input=texts).data]


def get_judge_embeddings():
    return _LiteLLMQueryEmbeddings(model=EMBEDDING_MODEL)



def get_judge_llm():
    return llm_factory(
        GENERATION_MODEL,
        provider="litellm",
        client=litellm.completion,
    )
