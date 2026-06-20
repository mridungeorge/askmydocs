"""
Creates the 'research_memory' collection in Qdrant.
Run once: python setup_qdrant.py
"""

import os
from dotenv import load_dotenv
load_dotenv()

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
collections = [c.name for c in client.get_collections().collections]
print("Existing collections:", collections)

if "research_memory" not in collections:
    client.create_collection(
        collection_name="research_memory",
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )
    print("Created: research_memory")
else:
    print("Already exists: research_memory")
