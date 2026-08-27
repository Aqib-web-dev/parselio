from celery import shared_task

from .models import Document, DocumentChunk
from django.contrib.postgres.search import SearchVector 
from .services import extract_text_from_document, chunk_text, embed_text    # the two functions from increments 2–3


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def process_document_upload(self, document_id):
    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        return                          # row was deleted before the worker got to it — nothing to do

    if document.status != Document.Status.UPLOADED:
        return                          # idempotency guard (Day 9): already processed/processing → skip

    document.status = Document.Status.PROCESSING
    document.save(update_fields=["status"])   # tell the rest of the system "work started"

    try:
        text = extract_text_from_document(document)   # increment 3: S3 download + parse

        if not text.strip():                          # ← the empty-text POLICY decision lives here
            document.status = Document.Status.FAILED   # scanned/broken/empty PDF → fail loudly, don't store 0 chunks
            document.save(update_fields=["status"])
            return

        document.chunks.all().delete()   # IDEMPOTENCY: clear any chunks from a previous partial run,
                                         # so a Celery retry can't crash on UniqueConstraint(document, chunk_index).

        pieces = chunk_text(text)

        new_chunks = []
        any_failed = False
        for i, piece in enumerate(pieces):        # enumerate gives us (0, first), (1, second), ...
            try:
                vector = embed_text(piece)        # one Gemini API call for this chunk only
                new_chunks.append(DocumentChunk(
                    document=document,
                    tenant=document.tenant,       # copy the tenant onto every chunk — isolation reaches the chunk layer
                    chunk_index=i,                # preserves reading order; also the field in the unique constraint
                    text=piece,
                    embedding=vector,
                ))
            except Exception as exc:
                # this one chunk's embedding failed — keep the text anyway, with no vector,
                # and a note explaining why. Move to the next chunk instead of losing
                # everything embedded so far.
                new_chunks.append(DocumentChunk(
                    document=document,
                    tenant=document.tenant,
                    chunk_index=i,
                    text=piece,
                    embedding=None,
                    embedding_error=str(exc),
                ))
                any_failed = True

        DocumentChunk.objects.bulk_create(new_chunks)
        # still ONE database write for all chunks, not N — the save is no longer gated
        # behind every single embedding succeeding, only behind the loop finishing.
        document.chunks.update(                                        # ADD THESE 2 LINES
            search_vector=SearchVector('text', config='english')
        )

        document.status = (
            Document.Status.PARTIAL_FAILURE if any_failed else Document.Status.READY
        )
        document.save(update_fields=["status"])

    except Exception as exc:
        document.status = Document.Status.FAILED
        document.save(update_fields=["status"])
        raise self.retry(exc=exc)        # Celery re-queues; the idempotent delete above makes re-runs safe