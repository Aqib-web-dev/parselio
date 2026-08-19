import uuid

import boto3
from langchain_text_splitters import RecursiveCharacterTextSplitter
from google import genai
from google.genai import types
from pgvector.django import CosineDistance

from botocore.config import Config
from django.conf import settings
import io                         # to wrap downloaded bytes in a file-like object
from pypdf import PdfReader        # PDF reader
from docx import Document as DocxDocument   # python-docx; aliased so it doesn't clash with our Document model

# Module-level constants — one obvious place to tune later (Day 20 evals), not magic numbers buried in code.
CHUNK_SIZE = 2000       # ~500 tokens (≈4 chars/token). Counts CHARACTERS by default — the honest simple approach.
CHUNK_OVERLAP = 200     # ~10% overlap → an idea split on a boundary still survives whole in one chunk.

EMBEDDING_MODEL = "gemini-embedding-001"   # text-only Gemini embedding model
EMBEDDING_DIMENSIONS = 768                 # must match DocumentChunk.embedding's VectorField(dimensions=768)

def build_upload_key(tenant_id, filename):
    """Build a tenant-prefixed, collision-safe S3 key for a new document upload."""
    return f"tenants/{tenant_id}/documents/{uuid.uuid4()}/{filename}"


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