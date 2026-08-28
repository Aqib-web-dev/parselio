import uuid

import boto3
from langchain_text_splitters import RecursiveCharacterTextSplitter
from google import genai
from google.genai import types
from pgvector.django import CosineDistance
import cohere
from litellm import completion

from botocore.config import Config
from django.conf import settings
import io                         # to wrap downloaded bytes in a file-like object
from pypdf import PdfReader        # PDF reader
from docx import Document as DocxDocument   # python-docx; aliased so it doesn't clash with our Document model
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Q

# Module-level constants — one obvious place to tune later (Day 20 evals), not magic numbers buried in code.
CHUNK_SIZE = 2000       # ~500 tokens (≈4 chars/token). Counts CHARACTERS by default — the honest simple approach.
CHUNK_OVERLAP = 200     # ~10% overlap → an idea split on a boundary still survives whole in one chunk.

EMBEDDING_MODEL = "gemini-embedding-001"   # text-only Gemini embedding model
EMBEDDING_DIMENSIONS = 768                 # must match DocumentChunk.embedding's VectorField(dimensions=768)

def build_upload_key(tenant_id, filename):
    """Build a tenant-prefixed, collision-safe S3 key for a new document upload."""
    return f"tenants/{tenant_id}/documents/{uuid.uuid4()}/{filename}"

def _visibility_scoped_chunks(tenant, user):
    """DocumentChunks the user can see: company-wide + all chunks in their teams."""
    from .models import DocumentChunk, Document   # local import avoids circular refs
    from tenants.models import TeamMembership

    user_team_ids = (
        TeamMembership.objects
        .filter(membership__user=user, membership__tenant=tenant)
        .values_list('team_id', flat=True)
    )
    # Sub-query: which teams does this user belong to inside this tenant?
    # The membership FK chain: TeamMembership → Membership → (user, tenant)

    return DocumentChunk.objects.filter(
        tenant=tenant          # ALWAYS tenant first — isolation rule
    ).filter(
        Q(document__visibility=Document.Visibility.COMPANY)           # company-wide docs always visible
        | Q(document__visibility=Document.Visibility.TEAM,
            document__team_id__in=user_team_ids)                      # team docs only if user is in that team
    )



def generate_presigned_upload(key, content_type):
   
    client = boto3.client(
        "s3",
        region_name=settings.AWS_S3_REGION_NAME,
        endpoint_url=f"https://s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com",
        config=Config(signature_version="s3v4"),
    )
    return client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.AWS_QUERYSTRING_EXPIRE,
    )


def chunk_text(text):
    """Split one long extracted string into overlapping, retrieval-sized chunks."""
    splitter = RecursiveCharacterTextSplitter(
        # Build the splitter with our tuned sizes.
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        # Try these cut-points IN ORDER: paragraph → line → sentence → word → (last resort) mid-character.
        # This ordered fallback is *why* it's called "recursive": it never splits on a smaller unit than it must.
    )
    return splitter.split_text(text)
    # Returns a plain list[str]. No side effects, no I/O — that's what makes this function easy to trust and test.

def _s3_client():
    """One place that builds the region-correct S3 client (mirrors generate_presigned_upload)."""
    return boto3.client(
        "s3",
        region_name=settings.AWS_S3_REGION_NAME,
        endpoint_url=f"https://s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com",
        # Regional endpoint — same Day-8 fix: the global endpoint 307-redirects for non-us-east-1 buckets.
        config=Config(signature_version="s3v4"),
    )

def extract_text_from_document(document):
    """Download the document's file from S3 and return its text as one plain string."""
    client = _s3_client()
    obj = client.get_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=document.file_key,          # the tenant-prefixed key we stored on upload (Day 8)
    )
    raw = obj["Body"].read()            # the actual file bytes, downloaded into memory

    filename = document.original_filename.lower()
    # Decide how to parse by the ORIGINAL filename's extension. (Simple + good enough today;
    # a stricter version would trust the stored content-type instead of a user-supplied name.)

    if filename.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(raw))     # io.BytesIO turns the bytes into a file-like object pypdf can read
        pages = [page.extract_text() or "" for page in reader.pages]
        # extract_text() returns None for an image-only page → "or ''" prevents a TypeError on join.
        return "\n\n".join(pages)               # join pages with a blank line so the splitter sees page breaks

    if filename.endswith(".docx"):
        docx = DocxDocument(io.BytesIO(raw))    # python-docx also reads from a file-like object
        return "\n".join(p.text for p in docx.paragraphs)
        # Plain paragraph text. (Tables/headers need extra handling — noted as a known limitation, not today's job.)

    raise ValueError(f"Unsupported file type: {document.original_filename}")
    # Anything else is a real error — the caller (the task) will catch it and mark the document FAILED.

def _gemini_client():
    """One place that builds the Gemini client (mirrors _s3_client above)."""
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def embed_text(text):
    """Turn one piece of text into a 768-dim embedding vector using Gemini."""
    client = _gemini_client()
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
        # output_dimensionality truncates Gemini's native (larger) vector down to 768 —
        # must match DocumentChunk.embedding's VectorField(dimensions=768) exactly.
    )
    return result.embeddings[0].values   # plain list[float], length 768

def find_similar_chunks(tenant, query_embedding, limit=5):
    """Return the `limit` DocumentChunk rows in `tenant` closest in meaning to `query_embedding`."""
    from .models import DocumentChunk   # local import avoids a circular import (models imports from tenants, not services)

    return (
        DocumentChunk.objects
        .filter(tenant=tenant, embedding__isnull=False)
        # tenant FIRST — never compare against another tenant's chunks (isolation rule from Day 8 onward).
        # embedding__isnull=False — skip chunks that haven't finished the embed step yet.
        .annotate(distance=CosineDistance("embedding", query_embedding))
        # CosineDistance builds the "embedding <=> query_embedding" SQL expression pgvector provides.
        .order_by("distance")[:limit]
        # Smaller distance = more similar. This ORDER BY is what the pgvector index (Day 12) speeds up.
    )


def retrieve(tenant, user, query, top_k=10):
    """
    Hybrid retrieval: 60% vector similarity + 40% full-text keyword search.

    Returns top_k DocumentChunk rows ranked by combined score,
    scoped to what the user is permitted to see within tenant.
    """
    # 1. Scope: only chunks this user can access
    base_qs = _visibility_scoped_chunks(tenant, user)

    # 2. Embed the query — one Gemini API call
    query_embedding = embed_text(query)

    # 3. Fetch vector and keyword candidates SEPARATELY, then union.
    # A single query ordered by vector_distance only would silently drop a chunk that's
    # a strong keyword match but semantically distant (e.g. ranked 50th on vector) —
    # its text_rank never gets computed because it's cut before annotation matters.
    search_query = SearchQuery(query, config='english')

    vector_candidate_ids = (
        base_qs
        .filter(embedding__isnull=False)          # skip chunks that failed embedding
        .annotate(vector_distance=CosineDistance('embedding', query_embedding))
        .order_by('vector_distance')
        .values_list('id', flat=True)[:top_k * 2]
    )

    keyword_candidate_ids = (
        base_qs
        .filter(search_vector__isnull=False)
        .annotate(text_rank=SearchRank('search_vector', search_query))
        .filter(text_rank__gt=0)                  # exclude non-matches, not just null search_vector
        .order_by('-text_rank')
        .values_list('id', flat=True)[:top_k * 2]
    )

    candidate_ids = set(vector_candidate_ids) | set(keyword_candidate_ids)

    # 4. Re-annotate the union with BOTH scores in one query, then re-rank in Python
    candidates = list(
        base_qs
        .filter(id__in=candidate_ids)
        .annotate(
            vector_distance=CosineDistance('embedding', query_embedding),
            # CosineDistance builds the pgvector "embedding <=> query_vec" expression
            text_rank=SearchRank('search_vector', search_query),
            # SearchRank builds ts_rank(search_vector, to_tsquery('english', 'query'))
            # Returns 0.0 if search_vector is null or no match; up to ~1.0 for strong match
        )
    )
    scored = []
    for chunk in candidates:
        # A chunk can enter this set via keyword match alone, so vector_distance may be None
        # (chunk.embedding is null) — treat "no vector signal" as similarity 0, not a crash.
        vector_score = max(0.0, 1.0 - float(chunk.vector_distance)) if chunk.vector_distance is not None else 0.0
        # cosine distance → similarity: distance of 0 = perfect match, 1 = orthogonal
        keyword_score = float(chunk.text_rank)
        # SearchRank is already 0–1
        combined = 0.6 * vector_score + 0.4 * keyword_score
        scored.append((combined, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:top_k]]

def _cohere_client():
    """One place that builds the Cohere client"""
    return cohere.Client(api_key=settings.COHERE_API_KEY)

def rerank(query, chunks, top_n=5):
    """Cross-encoder rerank: reorder `chunks` by true relevance to `query`, keep the best top_n."""
    if not chunks:
        return []
    # Guard against an empty candidate list — calling Cohere with documents=[] is a wasted API call.

    client = _cohere_client()
    response = client.rerank(
        model="rerank-english-v3.0",
        query=query,
        documents=[chunk.text for chunk in chunks],
        top_n=min(top_n, len(chunks)),
        # min() guards the case where fewer than top_n candidates were retrieved at all —
        # asking Cohere for more results than documents provided would error.
    )
    return [chunks[result.index] for result in response.results]

GENERATION_MODEL = "gemini/gemini-3.6-flash"
# LiteLLM needs the "gemini/" prefix to route the call. Reuses GEMINI_API_KEY —
# the same key embed_text() already uses — since LiteLLM's Gemini provider reads
# that exact env var name. gemini-2.5-flash was Google's model at the time this
# lesson was first written but is no longer available to new API callers —
# always check https://ai.google.dev/gemini-api/docs/models for the current name.
# Switch to "anthropic/claude-sonnet-5" once Console API credits are funded
# (separate billing from a Claude.ai/Claude Code subscription).

SYSTEM_PROMPT = """You are Parselio's document assistant. Answer the user's question using
ONLY the numbered context chunks below. Cite the chunk number in square brackets
after every claim, like [2]. If the context does not contain the answer, say
"I don't have enough information in the provided documents to answer that."
Never use knowledge outside the provided context."""

def generate_answer(query, chunks):
    """Generate a cited answer to `query`, grounded only in `chunks`."""
    if not chunks:
        return "I don't have enough information in the provided documents to answer that."
    # Same escape hatch the prompt teaches the model — applied in code too, so an empty
    # rerank result doesn't waste an LLM call just to get told the same thing.

    context = "\n\n".join(
        f"[{i+1}] {chunk.text}" for i, chunk in enumerate(chunks)
    )
    response = completion(
        model=GENERATION_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ],
    )
    return response.choices[0].message.content