import hashlib, re, time
import tiktoken
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from dataclasses import dataclass
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from backend.config import (
    NVIDIA_API_KEY, NVIDIA_BASE_URL, EMBED_MODEL,
    QDRANT_URL, QDRANT_API_KEY,
    CHUNK_SIZE, CHUNK_OVERLAP, COLLECTION_NAME,
)

# Lazy initialization - only create clients when API keys are available
nvidia   = None
qdrant   = None

def get_nvidia_client():
    global nvidia
    if nvidia is None:
        if not NVIDIA_API_KEY:
            raise ValueError("NVIDIA_API_KEY not set. Check environment variables.")
        nvidia = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)
    return nvidia

def get_qdrant_client():
    global qdrant
    if qdrant is None:
        if not QDRANT_URL or not QDRANT_API_KEY:
            raise ValueError("QDRANT_URL or QDRANT_API_KEY not set. Check environment variables.")
        qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    return qdrant

enc      = tiktoken.get_encoding("cl100k_base")
splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=lambda t: len(enc.encode(t)),
    separators=["\n\n", "\n", ". ", " ", ""],
)


@dataclass
class Chunk:
    chunk_id:    str
    source_name: str
    source_type: str
    chunk_index: int
    text:        str
    token_count: int


def extract_from_url(url: str) -> tuple[str, str]:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(url, timeout=15, headers=headers)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        title = soup.title.string if soup.title else url
        text  = re.sub(r'\n{3,}', '\n\n', soup.get_text(separator="\n"))
        return title.strip(), text.strip()
    except Exception as e:
        raise Exception(f"Could not fetch URL: {e}")


def extract_from_pdf(file_bytes: bytes, filename: str) -> tuple[str, str]:
    import io
    reader = PdfReader(io.BytesIO(file_bytes))
    pages  = [page.extract_text() or "" for page in reader.pages]
    text   = "\n\n".join(pages)
    text   = re.sub(r'\n{3,}', '\n\n', text).strip()
    return filename, text


def make_chunks(source_name: str, source_type: str, text: str) -> list[Chunk]:
    raw_chunks = splitter.split_text(text)
    chunks = []
    for i, chunk_text in enumerate(raw_chunks):
        token_count = len(enc.encode(chunk_text))
        if token_count < 30:
            continue
        chunk_id = hashlib.md5(f"{source_name}::{i}".encode()).hexdigest()
        chunks.append(Chunk(
            chunk_id=chunk_id, source_name=source_name,
            source_type=source_type, chunk_index=i,
            text=chunk_text, token_count=token_count,
        ))
    return chunks


def embed_passages(texts: list[str]) -> list[list[float]]:
    response = get_nvidia_client().embeddings.create(
        model=EMBED_MODEL, input=texts,
        encoding_format="float",
        extra_body={"input_type": "passage", "truncate": "END"},
    )
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


def ensure_collection(vector_size: int, collection_name: str):
    client = get_qdrant_client()
    existing = [c.name for c in client.get_collections().collections]
    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
    client.create_payload_index(
        collection_name=collection_name,
        field_name="source_name",
        field_schema="keyword",
    )


def ingest(
    source_name: str,
    source_type: str,
    text: str,
    collection_name: str = None,
) -> int:
    """
    Ingest text into Qdrant.
    collection_name defaults to global COLLECTION_NAME.
    When auth is enabled, pass the user's personal collection.
    """
    collection_name = collection_name or COLLECTION_NAME
    chunks = make_chunks(source_name, source_type, text)
    if not chunks:
        return 0

    all_vectors = []
    texts = [c.text for c in chunks]
    for i in range(0, len(texts), 50):
        batch = texts[i:i+50]
        all_vectors.extend(embed_passages(batch))
        if i + 50 < len(texts):
            time.sleep(1.5)

    ensure_collection(len(all_vectors[0]), collection_name)

    points = [
        PointStruct(
            id=i, vector=vector,
            payload={
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

    get_qdrant_client().upsert(collection_name=collection_name, points=points)
    return len(chunks)