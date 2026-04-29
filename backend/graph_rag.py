"""
Graph RAG — knowledge graph over documents.

Why Graph RAG:
Current RAG treats every chunk independently.
It misses relationships BETWEEN entities across chunks.

Example failure:
Document says: "BERT was developed by Google" (chunk 1)
Document says: "The Transformer architecture was used in BERT" (chunk 2)
Document says: "The Transformer was introduced in 'Attention is All You Need'" (chunk 3)

Query: "Who created the architecture used in BERT?"
Correct answer: "Vaswani et al. at Google" (multi-hop: BERT → Transformer → paper → authors)
Current RAG: Retrieves one chunk, misses the connection.
Graph RAG: Traverses BERT → Transformer → paper → finds authors.

Implementation:
1. Extract entities and relations from each chunk (LLM-based NER)
2. Build a NetworkX graph: entities=nodes, relations=edges
3. At retrieval: find relevant entities, traverse graph, collect connected chunks
4. Combine graph-traversed chunks with vector search chunks

This is what Microsoft's GraphRAG does at scale.
We implement the core concept without their full infrastructure.
"""

import json
import hashlib
from collections import defaultdict
from openai import OpenAI
from backend.config import NVIDIA_API_KEY, NVIDIA_BASE_URL, LLM_FAST
from backend.auth import supabase

nvidia = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)

# In-memory graph — rebuilt from Supabase on startup
# For production: use a proper graph DB like Neo4j
_graphs = {}  # collection_name → NetworkX graph


def _get_graph(collection: str):
    """Get or create graph for a collection."""
    try:
        import networkx as nx
    except ImportError:
        raise ImportError("networkx not installed. Run: pip install networkx")

    if collection not in _graphs:
        _graphs[collection] = nx.DiGraph()
    return _graphs[collection]


# ── Entity extraction ─────────────────────────────────────────────────────────

def extract_entities_and_relations(
    text: str,
    chunk_id: str,
) -> dict:
    """
    Use LLM to extract entities and relations from a chunk.

    Returns:
    {
        "entities": [{"name": "BERT", "type": "MODEL"}, ...],
        "relations": [{"source": "BERT", "relation": "developed_by", "target": "Google"}, ...]
    }

    Why LLM-based NER over spaCy:
    spaCy misses domain-specific entities (model names, technical terms).
    LLM understands context — knows "Transformer" is an AI architecture,
    not an electrical device.
    """
    prompt = f"""Extract entities and relationships from this text.

Return ONLY valid JSON with this structure:
{{
  "entities": [
    {{"name": "entity name", "type": "PERSON|ORG|MODEL|CONCEPT|PAPER|DATASET|METRIC"}}
  ],
  "relations": [
    {{"source": "entity1", "relation": "relation_type", "target": "entity2"}}
  ]
}}

Common relation types: developed_by, introduced_in, based_on, outperforms,
trained_on, part_of, cited_by, uses, achieves, compared_to

Text: {text[:800]}

JSON output:"""

    try:
        resp = nvidia.chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.0,
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception:
        return {"entities": [], "relations": []}


def build_graph_for_collection(
    collection:  str,
    user_id:     str,
    chunks:      list,
) -> dict:
    """
    Build knowledge graph from all chunks in a collection.
    Extracts entities/relations, builds NetworkX graph, saves to Supabase.

    Returns: {"entities": count, "relations": count}
    """
    try:
        import networkx as nx
    except ImportError:
        return {"entities": 0, "relations": 0, "error": "networkx not installed"}

    G = nx.DiGraph()
    total_entities  = 0
    total_relations = 0

    for chunk in chunks:
        text     = chunk.payload.get("text", "")
        chunk_id = chunk.payload.get("chunk_id", str(chunk.id))

        extracted = extract_entities_and_relations(text, chunk_id)

        # Add entities as nodes with chunk reference
        for entity in extracted.get("entities", []):
            name = entity["name"].lower().strip()
            if not name or len(name) < 2:
                continue

            if G.has_node(name):
                G.nodes[name]["chunk_ids"].add(chunk_id)
            else:
                G.add_node(name,
                    name=entity["name"],
                    entity_type=entity.get("type", "CONCEPT"),
                    chunk_ids={chunk_id},
                )
            total_entities += 1

        # Add relations as directed edges
        for rel in extracted.get("relations", []):
            source = rel.get("source", "").lower().strip()
            target = rel.get("target", "").lower().strip()
            relation = rel.get("relation", "related_to")

            if source and target and source != target:
                G.add_edge(source, target, relation=relation, chunk_id=chunk_id)
                total_relations += 1

    # Store in memory
    _graphs[collection] = G

    # Persist to Supabase (for reload after restart)
    try:
        # Clear existing
        supabase.table("kg_entities").delete() \
            .eq("user_id", user_id).eq("collection", collection).execute()
        supabase.table("kg_relations").delete() \
            .eq("user_id", user_id).eq("collection", collection).execute()

        # Insert nodes
        entities_to_insert = []
        for node, data in G.nodes(data=True):
            entities_to_insert.append({
                "user_id":     user_id,
                "collection":  collection,
                "entity":      data.get("name", node),
                "entity_type": data.get("entity_type", "CONCEPT"),
                "chunk_ids":   list(data.get("chunk_ids", [])),
            })

        if entities_to_insert:
            supabase.table("kg_entities").insert(entities_to_insert).execute()

        # Insert edges
        relations_to_insert = []
        for source, target, data in G.edges(data=True):
            relations_to_insert.append({
                "user_id":    user_id,
                "collection": collection,
                "source":     source,
                "relation":   data.get("relation", "related_to"),
                "target":     target,
            })

        if relations_to_insert:
            supabase.table("kg_relations").insert(relations_to_insert).execute()

    except Exception as e:
        print(f"Graph persist error: {e}")

    return {"entities": total_entities, "relations": total_relations}


def load_graph_from_supabase(collection: str, user_id: str) -> None:
    """Reload graph from Supabase after server restart."""
    try:
        import networkx as nx
    except ImportError:
        return

    G = nx.DiGraph()

    # Load entities
    entities = supabase.table("kg_entities") \
        .select("*").eq("collection", collection).eq("user_id", user_id).execute()

    for e in entities.data or []:
        G.add_node(e["entity"].lower(),
            name=e["entity"],
            entity_type=e["entity_type"],
            chunk_ids=set(e["chunk_ids"] or []),
        )

    # Load relations
    relations = supabase.table("kg_relations") \
        .select("*").eq("collection", collection).eq("user_id", user_id).execute()

    for r in relations.data or []:
        G.add_edge(r["source"], r["target"], relation=r["relation"])

    _graphs[collection] = G


def graph_retrieve(
    query:       str,
    collection:  str,
    user_id:     str,
    all_chunks:  list,
    max_hops:    int = 2,
    max_chunks:  int = 10,
) -> list:
    """
    Graph-enhanced retrieval.

    Steps:
    1. Extract entities from query
    2. Find those entities in the knowledge graph
    3. Traverse graph up to max_hops away
    4. Collect all chunk_ids connected to those entities
    5. Return corresponding chunks

    Combine with vector search for best results:
    final_chunks = deduplicate(graph_chunks + vector_chunks)
    """
    try:
        import networkx as nx
    except ImportError:
        return []

    # Load graph if not in memory
    if collection not in _graphs:
        load_graph_from_supabase(collection, user_id)

    G = _graphs.get(collection)
    if not G or G.number_of_nodes() == 0:
        return []

    # Extract entities from query
    query_extracted = extract_entities_and_relations(query, "query")
    query_entities  = [
        e["name"].lower().strip()
        for e in query_extracted.get("entities", [])
    ]

    if not query_entities:
        # Fallback: fuzzy match entity names against query words
        query_words = query.lower().split()
        query_entities = [
            node for node in G.nodes()
            if any(word in node or node in word for word in query_words)
        ][:5]

    if not query_entities:
        return []

    # Traverse graph — collect connected chunk IDs
    relevant_chunk_ids = set()

    for entity in query_entities:
        if entity not in G:
            continue

        # Get chunks for this entity
        node_data = G.nodes[entity]
        relevant_chunk_ids.update(node_data.get("chunk_ids", set()))

        # Traverse neighbours up to max_hops
        try:
            neighbors = nx.single_source_shortest_path_length(
                G, entity, cutoff=max_hops
            )
            for neighbor, distance in neighbors.items():
                if distance > 0:
                    n_data = G.nodes.get(neighbor, {})
                    relevant_chunk_ids.update(n_data.get("chunk_ids", set()))
        except Exception:
            pass

    # Map chunk IDs back to chunk objects
    id_to_chunk = {c.payload.get("chunk_id"): c for c in all_chunks}
    graph_chunks = [
        id_to_chunk[cid]
        for cid in relevant_chunk_ids
        if cid in id_to_chunk
    ]

    return graph_chunks[:max_chunks]
