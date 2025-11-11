"""Upload RAG chunks to a local Qdrant collection.

Reads JSON chunk files in `data/rag_experiments` (files named `chunks_*.json`),
computes embeddings (OpenAI if OPENAI_API_KEY set; otherwise sentence-transformers),
and upserts vectors + payload to Qdrant in batches.

Usage examples:
  # using OpenAI embeddings (ensure OPENAI_API_KEY)
  python src/rag/ingest_to_qdrant.py --input-dir data/rag_experiments --collection world_labs_chunks

  # using local sentence-transformers (no API key required)
  python src/rag/ingest_to_qdrant.py --embedding-provider hf --embedding-model all-MiniLM-L6-v2

Environment variables:
  OPENAI_API_KEY (optional) - if present, script will prefer OpenAI embeddings
  QDRANT_URL (optional, default http://localhost:6333)
  QDRANT_API_KEY (optional)

This script is defensive: it will skip points with empty text and will batch upserts.
"""
from __future__ import annotations

import os
import sys
import json
import time
import argparse
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Iterable, Tuple

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use system env vars

try:
    # qdrant client
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as rest
except Exception:
    QdrantClient = None  # handled at runtime


def load_chunk_files(input_dir: Path, chunk_file: str | None = None) -> List[Dict[str, Any]]:
    """Load chunk files. If chunk_file is specified, load only that file; otherwise load all chunks_*.json files."""
    chunks = []
    logger = logging.getLogger(__name__)
    
    if chunk_file:
        # Load a specific file
        file_path = input_dir / chunk_file
        if not file_path.exists():
            logger.error("Chunk file not found: %s", file_path)
            return []
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    chunks.extend(data)
            logger.info("Loaded %d chunks from %s", len(data), chunk_file)
        except Exception as e:
            logger.warning("Failed to load %s: %s", file_path, e)
    else:
        # Load all chunks_*.json files in the directory
        for p in sorted(input_dir.glob("chunks_*.json")):
            try:
                with p.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        chunks.extend(data)
                logger.debug("Loaded %d chunks from %s", len(data), p.name)
            except Exception as e:
                logger.warning("Failed to load %s: %s", p, e)
    
    return chunks


def deterministic_int_id(s: str) -> int:
    """Deterministic positive int from string (fits in 63 bits)."""
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]
    return int(h, 16) % (2**63 - 1)


def embed_texts_openai(texts: List[str], model: str = "text-embedding-3-small") -> List[List[float]]:
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set for OpenAI embeddings")
    
    client = OpenAI(api_key=api_key)
    resp = client.embeddings.create(input=texts, model=model)
    return [e.embedding for e in resp.data]


def embed_texts_hf(texts: List[str], model: str = "all-MiniLM-L6-v2") -> List[List[float]]:
    # lazy import heavy dependencies
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(model)
    return m.encode(texts, show_progress_bar=False).tolist()


def choose_embedding_provider(prefer_openai: bool = True, hf_model: str = "all-MiniLM-L6-v2"):
    """Return a function that takes list[str] -> list[list[float]] and a string name."""
    if prefer_openai and os.environ.get("OPENAI_API_KEY"):
        try:
            import openai  # quick check
            return embed_texts_openai, "openai"
        except Exception:
            print("⚠️  OpenAI import failed, will try HF provider")

    try:
        # sentence-transformers
        import sentence_transformers  # type: ignore
        return (lambda texts: embed_texts_hf(texts, model=hf_model)), f"hf:{hf_model}"
    except Exception:
        raise RuntimeError("No embedding provider available. Install sentence-transformers or set OPENAI_API_KEY.")


def prepare_points(chunks: List[Dict[str, Any]]) -> List[Tuple[int, str, Dict[str, Any]]]:
    """Return list of (id, text, payload) to be filled after embedding.

    We keep minimal metadata to avoid payload bloat: chunk_id, company_slug, page_type, source_file, keywords.
    Text is NOT stored in payload (only passed for embedding).
    """
    points = []
    for c in chunks:
        text = c.get("text", "")
        if not text or not text.strip():
            continue
        chunk_id = c.get("chunk_id") or c.get("id") or hashlib.sha1(text.encode()).hexdigest()
        pid = deterministic_int_id(chunk_id)
        
        # Build minimal payload WITHOUT text to avoid bloat
        payload = {
            "chunk_id": c.get("chunk_id"),
            "company_slug": c.get("company_slug"),
            "page_type": c.get("page_type"),
            "source_file": c.get("source_file"),
            "keywords": c.get("keywords", []),
        }
        points.append((pid, text, payload))
    return points


def batch_iterable(iterable: Iterable, batch_size: int):
    batch = []
    for x in iterable:
        batch.append(x)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def upsert_to_qdrant(
    qdrant_url: str,
    api_key: str | None,
    collection_name: str,
    points_with_vectors: List[Tuple[int, List[float], Dict[str, Any]]],
    vector_size: int,
    batch_size: int = 64,
):
    if QdrantClient is None:
        raise RuntimeError("qdrant-client is not installed. Please pip install qdrant-client")

    client = QdrantClient(url=qdrant_url, api_key=api_key, timeout=30.0)

    logger = logging.getLogger(__name__)
    # Try to delete collection if it exists
    try:
        logger.info("Attempting to delete existing collection %s", collection_name)
        client.delete_collection(collection_name)
        logger.info("Collection %s deleted successfully", collection_name)
        # Wait a moment for deletion to complete
        import time
        time.sleep(1)
    except Exception as e:
        logger.debug("Collection %s doesn't exist or delete failed: %s", collection_name, e)
    
    # Create fresh collection using create_collection instead of recreate_collection
    try:
        logger.info("Creating collection %s (vector size=%d)", collection_name, vector_size)
        client.create_collection(
            collection_name=collection_name,
            vectors_config=rest.VectorParams(size=vector_size, distance=rest.Distance.COSINE),
        )
        logger.info("Collection %s created successfully", collection_name)
    except Exception as create_err:
        logger.error("Failed to create collection: %s", create_err)
        raise

    # Upsert in batches
    for i, batch in enumerate(batch_iterable(points_with_vectors, batch_size)):
        try:
            ids = [p[0] for p in batch]
            vectors = [p[1] for p in batch]
            payloads = [p[2] for p in batch]
            
            logger.info("Upserting batch %d with %d points", i + 1, len(batch))
            client.upsert(
                collection_name=collection_name, 
                points=[rest.PointStruct(id=id_, vector=vec, payload=pl) for id_, vec, pl in zip(ids, vectors, payloads)]
            )
            logger.debug("Upserted batch %d of %d points to %s", i + 1, len(batch), collection_name)
        except Exception as batch_err:
            logger.error("Failed to upsert batch %d: %s", i + 1, batch_err)
            raise


def main(argv: List[str] | None = None):
    parser = argparse.ArgumentParser(description="Upload chunk JSON files to Qdrant")
    parser.add_argument("--input-dir", type=str, default="data/rag_experiments")
    parser.add_argument("--chunk-file", type=str, default=None,
                        help="Optional: load only a specific chunk file (e.g., chunks_recursive.json) instead of all chunks_*.json")
    parser.add_argument("--collection", type=str, default=os.environ.get("QDRANT_COLLECTION_NAME") or "world_labs_chunks",
                        help="Qdrant collection name (default: from QDRANT_COLLECTION_NAME env or 'world_labs_chunks')")
    parser.add_argument("--embedding-provider", type=str, choices=["openai", "hf"], default=None,
                        help="Force embedding provider: 'openai' or 'hf' (sentence-transformers). By default prefers OpenAI if OPENAI_API_KEY set.")
    parser.add_argument("--embedding-model", type=str, default=None, help="Embedding model name (OpenAI or HF model)")
    parser.add_argument("--qdrant-url", type=str, default=os.environ.get("QDRANT_URL", "http://localhost:6333"))
    parser.add_argument("--qdrant-api-key", type=str, default=os.environ.get("QDRANT_API_KEY", None))
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args(argv)

    # Configure logging with both console and file handlers
    log_level = logging.INFO
    # if user passes VERBOSE via env or wants debug level
    if os.environ.get("VERBOSE", "0") in ("1", "true", "True"):
        log_level = logging.DEBUG
    
    # Setup formatters and handlers
    log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    
    # File handler
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "ingest_to_qdrant.log")
    file_handler.setFormatter(log_formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()  # Clear any existing handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    logger = logging.getLogger(__name__)

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        logger.error("Input directory not found: %s", input_dir)
        sys.exit(1)

    raw_chunks = load_chunk_files(input_dir, chunk_file=args.chunk_file)
    if not raw_chunks:
        logger.info("No chunk files found in input directory")
        sys.exit(0)

    # Prepare points list
    prepared = prepare_points(raw_chunks)
    if not prepared:
        logger.info("No valid chunks to upload (empty text?)")
        sys.exit(0)

    texts = [t for (_id, t, _pl) in prepared]

    # Choose provider
    prefer_openai = True if args.embedding_provider is None and os.environ.get("OPENAI_API_KEY") else False
    if args.embedding_provider == "openai":
        prefer_openai = True
    if args.embedding_provider == "hf":
        prefer_openai = False

    hf_model = args.embedding_model or "all-MiniLM-L6-v2"
    openai_model = args.embedding_model or "text-embedding-3-small"

    embed_fn, provider_name = choose_embedding_provider(prefer_openai=prefer_openai, hf_model=hf_model)
    logger.info("Using embedding provider: %s", provider_name)

    vectors = []
    # embed in batches to avoid huge single requests
    bs = args.batch_size
    for batch in batch_iterable(list(enumerate(texts)), bs):
        indices = [i for i, _t in batch]
        batch_texts = [t for _i, t in batch]
        if provider_name.startswith("openai"):
            batch_vecs = embed_texts_openai(batch_texts, model=openai_model)
        else:
            batch_vecs = embed_texts_hf(batch_texts, model=hf_model)
        for v in batch_vecs:
            vectors.append(v)

    if len(vectors) != len(prepared):
        logger.error("Embedding count (%d) != prepared points (%d)", len(vectors), len(prepared))
        raise RuntimeError("Embedding count != prepared points")

    # Combine ids, vectors, payloads
    points_with_vectors = []
    for (pid, _text, payload), vec in zip(prepared, vectors):
        points_with_vectors.append((pid, vec, payload))

    # Upsert to Qdrant
    qdrant_url = args.qdrant_url
    qdrant_api_key = args.qdrant_api_key
    vector_size = len(vectors[0])
    logger.info("Upserting %d points to Qdrant collection '%s' at %s", len(points_with_vectors), args.collection, qdrant_url)
    upsert_to_qdrant(qdrant_url, qdrant_api_key, args.collection, points_with_vectors, vector_size, batch_size=args.batch_size)

    logger.info("Done.")


if __name__ == "__main__":
    main()
