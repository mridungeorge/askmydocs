import hashlib, re, time
import tiktoken
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from dataclasses import dataclass
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, PayloadSchemaType
from backend.config import *

# ── Clients ───────────────────────────────────────────────────────────────────
nvidia  = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)
qdrant  = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
enc     = tiktoken.get_encoding("cl100k_base")
splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=lambda t: len(enc.encode(t)),
    separators=["\n\n", "\n", ". ", " ", ""],
)

# ── Data class ────────────────────────────────────────────────────────────────
@dataclass
class Chunk:
    chunk_id:    str
    source_name: str
    source_type: str   # "pdf" or "url"
    chunk_index: int
    text:        str
    token_count: int

# ── Text extraction ───────────────────────────────────────────────────────────
def extract_from_url(url: str) -> tuple[str, str]:
    """Fetch a webpage and return (title, clean_text)."""
    r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    title = soup.title.string if soup.title else url
    text  = re.sub(r'\n{3,}', '\n\n', soup.get_text(separator="\n"))
    return title.strip(), text.strip()

def extract_from_pdf(file_bytes: bytes, filename: str) -> tuple[str, str]:
    """Extract text from PDF bytes, return (filename, text)."""
    import io
    reader = PdfReader(io.BytesIO(file_bytes))
    pages  = [page.extract_text() or "" for page in reader.pages]
    text   = "\n\n".join(pages)
    text   = re.sub(r'\n{3,}', '\n\n', text).strip()
    return filename, text

# ── Chunking ──────────────────────────────────────────────────────────────────
def make_chunks(source_name: str, source_type: str, text: str) -> list[Chunk]:
    raw_chunks = splitter.split_text(text)
    chunks = []
    for i, chunk_text in enumerate(raw_chunks):
        token_count = len(enc.encode(chunk_text))
        if token_count < 30:
            continue
        chunk_id = hashlib.md5(
            f"{source_name}::{i}".encode()
        ).hexdigest()
        chunks.append(Chunk(
            chunk_id    = chunk_id,
            source_name = source_name,
            source_type = source_type,
            chunk_index = i,
            text        = chunk_text,
            token_count = token_count,
        ))
    return chunks

# ── Embedding ─────────────────────────────────────────────────────────────────
def embed_passages(texts: list[str]) -> list[list[float]]:
    response = nvidia.embeddings.create(
        model          = EMBED_MODEL,
        input          = texts,
        encoding_format = "float",
        extra_body     = {"input_type": "passage", "truncate": "END"},
    )
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]

# ── Qdrant setup ──────────────────────────────────────────────────────────────
def ensure_collection(vector_size: int):
    """Create collection and payload index if they don't exist yet."""
    existing = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION_NAME not in existing:
        qdrant.create_collection(
            collection_name = COLLECTION_NAME,
            vectors_config  = VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    # Always ensure the payload index exists (safe to call repeatedly)
    qdrant.create_payload_index(
        collection_name = COLLECTION_NAME,
        field_name      = "source_name",
        field_schema    = "keyword",
    )

# ── Main ingest function ──────────────────────────────────────────────────────
def ingest(source_name: str, source_type: str, text: str) -> int:
    """
    Full ingestion pipeline:
    text → chunks → embeddings → Qdrant
    Returns number of chunks indexed.
    """
    chunks  = make_chunks(source_name, source_type, text)
    if not chunks:
        return 0

    # Embed in batches of 50 (respects NVIDIA free tier rate limits)
    all_vectors = []
    texts = [c.text for c in chunks]
    for i in range(0, len(texts), 50):
        batch = texts[i:i+50]
        all_vectors.extend(embed_passages(batch))
        if i + 50 < len(texts):
            time.sleep(1.5)

    ensure_collection(len(all_vectors[0]))

    # Build Qdrant points
    points = [
        PointStruct(
            id      = i,
            vector  = vector,
            payload = {
                "chunk_id":    c.chunk_id,
                "source_name": c.source_name,
                "source_type": c.source_type,
                "chunk_index": c.chunk_index,
                "text":        c.text,
                "token_count": c.token_count,
            }
        )
        for i, (c, vector) in enumerate(zip(chunks, all_vectors))
    ]

    qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
    return len(chunks)