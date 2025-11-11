import os
import sys
import json
import time
import math
import logging
import argparse
from pathlib import Path
from statistics import mean, pstdev  # population std dev (old summary looked like population)
from typing import Dict, List, Tuple, Any

from tqdm import tqdm
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
)

# Keyword extraction imports (with fallbacks)
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import yake
    HAS_YAKE = True
except ImportError:
    HAS_YAKE = False

try:
    from keybert import KeyBERT
    HAS_KEYBERT = True
except ImportError:
    HAS_KEYBERT = False


# -------------------------------
#  Token counting (with fallback)
# -------------------------------
def _make_token_counter():
    """Return a function(text) -> token_count. Falls back to len(text) if tiktoken not available."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")

        def count_tokens(text: str) -> int:
            return len(enc.encode(text or ""))

        return count_tokens
    except Exception:
        def count_chars(text: str) -> int:
            return len(text or "")
        return count_chars

count_tokens = _make_token_counter()


# -------------------------------
#  Keyword Extraction Methods
# -------------------------------
def extract_keywords_tfidf(text: str, num_keywords: int = 5) -> List[str]:
    """
    Extract keywords using TF-IDF (requires scikit-learn).
    Most lightweight and fastest method.
    """
    if not HAS_SKLEARN:
        return []
    
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        
        # Split text into sentences for TF-IDF calculation
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        if len(sentences) < 2:
            sentences = [text]  # Fall back to full text if too short
        
        vectorizer = TfidfVectorizer(max_features=100, stop_words='english', ngram_range=(1, 2))
        try:
            tfidf_matrix = vectorizer.fit_transform(sentences)
            feature_names = vectorizer.get_feature_names_out()
            
            # Get top scores
            scores = tfidf_matrix.sum(axis=0).A1
            top_indices = scores.argsort()[-num_keywords:][::-1]
            keywords = [feature_names[i] for i in top_indices if scores[i] > 0]
            return keywords[:num_keywords]
        except ValueError:
            # Handle case where vectorizer can't fit
            return []
    except Exception:
        return []


def extract_keywords_yake(text: str, num_keywords: int = 5) -> List[str]:
    """
    Extract keywords using YAKE (requires yake library).
    Language-independent, no training required.
    """
    if not HAS_YAKE:
        return []
    
    try:
        kw_extractor = yake.KeywordExtractor(lan="en", n=3, top=num_keywords)
        keywords_with_scores = kw_extractor.extract_keywords(text)
        # keywords_with_scores is list of (keyword, score) tuples
        keywords = [kw for kw, score in keywords_with_scores]
        return keywords
    except Exception:
        return []


def extract_keywords_keybert(text: str, num_keywords: int = 5) -> List[str]:
    """
    Extract keywords using KeyBERT (requires keybert library).
    Most advanced method using transformer embeddings.
    Warning: This is slower and requires more resources than the other methods.
    """
    if not HAS_KEYBERT:
        return []
    
    try:
        kw_model = KeyBERT()
        keywords = kw_model.extract_keywords(text, language="english", top_n=num_keywords)
        # keywords is list of (keyword, score) tuples
        return [kw for kw, score in keywords]
    except Exception:
        return []


def extract_keywords(text: str, method: str = "tfidf", num_keywords: int = 5) -> List[str]:
    """
    Extract keywords from text using the specified method.
    
    Args:
        text: Input text
        method: Extraction method - "tfidf" (default), "yake", or "keybert"
        num_keywords: Number of keywords to extract
    
    Returns:
        List of extracted keywords
    """
    if not text or len(text.strip()) < 10:
        return []
    
    if method == "tfidf":
        return extract_keywords_tfidf(text, num_keywords)
    elif method == "yake":
        return extract_keywords_yake(text, num_keywords)
    elif method == "keybert":
        return extract_keywords_keybert(text, num_keywords)
    else:
        # Default to TF-IDF
        return extract_keywords_tfidf(text, num_keywords)


# -------------------------------
#  I/O helpers
# -------------------------------
def load_provenance_metadata(company_slug: str, metadata_base: Path = Path("data/metadata")) -> Dict[str, Any]:
    """
    Load the text extraction provenance metadata for a company.
    Returns the parsed JSON from text_extraction_provenance.json.
    """
    provenance_path = metadata_base / company_slug / "text_extraction_provenance.json"
    
    if not provenance_path.exists():
        raise FileNotFoundError(f"Provenance metadata not found: {provenance_path}")
    
    with provenance_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def collect_texts_from_provenance(company_slug: str, metadata_base: Path = Path("data/metadata"), raw_base: Path = Path("data/raw")) -> Tuple[List[Dict[str, Any]], str]:
    """
    Reads text files from data/raw/{company_slug}/{page_type}/text.txt
    using the provenance metadata to guide the process.
    Returns (texts_with_metadata, first_source_path) where each item contains text and its source info.
    """
    provenance = load_provenance_metadata(company_slug, metadata_base)
    
    texts_with_metadata: List[Dict[str, Any]] = []
    first_source = ""
    
    results = provenance.get("text_extraction_results", [])
    
    for result in tqdm(results, desc="Loading pages"):
        if not result.get("success", False):
            print(f"⚠️  Skipping failed page: {result.get('page_type')}")
            continue
        
        # The text_file in provenance already contains the full path like "data/raw/world_labs/about/text.txt"
        # so we use it directly instead of prepending raw_base again
        text_file_path = Path(result["text_file"])
        
        if not text_file_path.exists():
            print(f"⚠️  Text file not found: {text_file_path}")
            continue
        
        # Read the text
        txt = text_file_path.read_text(encoding="utf-8", errors="ignore")
        if txt.strip():
            # Store text with its metadata
            texts_with_metadata.append({
                "text": txt,
                "page_type": result.get("page_type"),
                "text_file": str(result.get("text_file")),
                "text_size": result.get("text_size", 0),
                "word_count": result.get("word_count", 0),
            })
            
            if not first_source:
                first_source = str(text_file_path)
    
    return (texts_with_metadata, first_source or f"data/raw/{company_slug}")


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


# -------------------------------
#  Chunking strategies with source tracking
# -------------------------------
def chunk_recursive(text: str, source_file: str = "", page_type: str = ""):
    """Chunk text using recursive character splitting, tracking source file."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        add_start_index=True,
    )
    docs = splitter.create_documents([text])
    
    # Add source metadata to each chunk
    for doc in docs:
        if doc.metadata is None:
            doc.metadata = {}
        doc.metadata["source_file"] = source_file
        doc.metadata["page_type"] = page_type
    
    return docs


def chunk_markdownheader(text: str, source_file: str = "", page_type: str = ""):
    """Chunk text using markdown header splitting, tracking source file."""
    headers = [("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers)
    docs = splitter.split_text(text)
    
    # Add source metadata to each chunk
    for doc in docs:
        if doc.metadata is None:
            doc.metadata = {}
        doc.metadata["source_file"] = source_file
        doc.metadata["page_type"] = page_type
    
    return docs


# -------------------------------
#  Old-style chunk JSON schema
# -------------------------------
STRATEGY_FILE_KEYS = {
    "Recursive": "chunks_recursive",
    "MarkdownHeader": "chunks_markdownheader",
}

def to_old_style_chunks(
    company_slug: str,
    strategy_name: str,
    chunks: List[Any],
    keyword_method: str = "tfidf",
    num_keywords: int = 5,
) -> List[Dict[str, Any]]:
    """
    Convert list of doc/chunk objects to the new schema:
      {
        "text": "...",
        "chunk_id": "chunk_000000",
        "chunk_strategy": "<Strategy>",
        "doc_id": "<company_slug>_all_pages",
        "doc_title": "...",
        "company_slug": "world_labs",
        "page_type": "about|blog|careers|...",
        "source_file": "data/raw/world_labs/about/text.txt",
        "content_type": "general" | "code" | ...,
        "keywords": [list of extracted keywords],
        "page_number": <int>,
        "position_in_doc": <float>
      }
    """
    out: List[Dict[str, Any]] = []
    n = max(1, len(chunks))
    for idx, c in enumerate(chunks):
        if isinstance(c, dict):
            text = c.get("page_content") or c.get("text", "")
            metadata = c.get("metadata", {}) or {}
        else:
            text = getattr(c, "page_content", "")
            metadata = getattr(c, "metadata", {}) or {}

        content_type = metadata.get("type", "general")
        page_no = metadata.get("page", 1)
        page_type = metadata.get("page_type", "unknown")
        source_file = metadata.get("source_file", "")
        
        # Extract keywords from the chunk text
        keywords = extract_keywords(text, method=keyword_method, num_keywords=num_keywords)

        out.append({
            "text": text,
            "chunk_id": f"chunk_{idx:06d}",
            "chunk_strategy": strategy_name,
            "doc_id": f"{company_slug.lower()}_all_pages",
            "doc_title": f"{company_slug} - Company Pages",
            "company_slug": company_slug,
            "page_type": page_type,
            "source_file": source_file,
            "content_type": content_type,
            "keywords": keywords,
            "page_number": page_no,
            "position_in_doc": round(idx / n, 3),
        })
    return out


# -------------------------------
#  Stats for summary.json (old style)
# -------------------------------
def compute_summary_stats(strategy_name: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build the detailed metrics section like the old summary:
      - chunk_count
      - total_tokens (tokens if tiktoken available; else characters)
      - mean/min/max/std_dev (based on token counts / char counts)
      - execution_time_ms handled by caller (we pass it in)
    """
    sizes = [count_tokens(c.get("text", "")) for c in chunks]
    chunk_count = len(sizes)
    total_tokens = int(sum(sizes))
    if chunk_count == 0:
        return {
            "chunk_count": 0,
            "total_tokens": 0,
            "mean_chunk_size": 0.0,
            "min_chunk_size": 0,
            "max_chunk_size": 0,
            "std_dev": 0.0,
            "execution_time_ms": 0.0,
        }

    mu = mean(sizes)
    sigma = pstdev(sizes) if chunk_count > 1 else 0.0
    return {
        "chunk_count": chunk_count,
        "total_tokens": total_tokens,
        "mean_chunk_size": round(mu, 2),
        "min_chunk_size": min(sizes),
        "max_chunk_size": max(sizes),
        "std_dev": round(sigma, 2),
        # execution_time_ms added by caller
    }


# -------------------------------
#  Entry Point
# -------------------------------
def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run experimental chunking strategies on web pages from text extraction.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python experimental_framework.py world_labs
  python experimental_framework.py ai50_company --output data/custom_output
  python experimental_framework.py another_company --verbose
  python experimental_framework.py world_labs --keyword-method yake --num-keywords 10
  python experimental_framework.py world_labs --keyword-method keybert
        """
    )
    
    parser.add_argument(
        "company_slug",
        type=str,
        help="Company slug/name (e.g., world_labs, ai50_company)"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="data/rag_experiments",
        help="Output directory for results (default: data/rag_experiments)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--metadata-base",
        type=str,
        default="data/metadata",
        help="Base directory for metadata (default: data/metadata)"
    )
    
    parser.add_argument(
        "--raw-base",
        type=str,
        default="data/raw",
        help="Base directory for raw text files (default: data/raw)"
    )
    
    parser.add_argument(
        "--keyword-method",
        type=str,
        choices=["tfidf", "yake", "keybert"],
        default="tfidf",
        help="Keyword extraction method (default: tfidf). tfidf=fastest (scikit-learn), yake=language-independent, keybert=most advanced (slower, uses transformers)"
    )
    
    parser.add_argument(
        "--num-keywords",
        type=int,
        default=5,
        help="Number of keywords to extract per chunk (default: 5)"
    )
    
    return parser.parse_args()


def main():
    """Main entry point with argument parsing."""
    # Setup logging with both console and file handlers
    log_level = logging.INFO
    if sys.argv and any(arg in sys.argv for arg in ["--verbose", "-v"]):
        log_level = logging.DEBUG
    
    # Setup formatters and handlers
    log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    
    # File handler
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "experimental_framework.log")
    file_handler.setFormatter(log_formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()  # Clear any existing handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    logger = logging.getLogger(__name__)
    
    args = parse_arguments()
    
    # Validate company slug
    company_slug = args.company_slug.strip().lower()
    if not company_slug:
        print("❌ Error: Company slug cannot be empty")
        sys.exit(1)
    
    # Validate metadata directory exists
    metadata_base = Path(args.metadata_base)
    raw_base = Path(args.raw_base)
    
    provenance_path = metadata_base / company_slug / "text_extraction_provenance.json"
    if not provenance_path.exists():
        print(f"❌ Error: Provenance metadata not found: {provenance_path}")
        sys.exit(1)
    
    if args.verbose:
        print(f"📋 Configuration:")
        print(f"  Company slug: {company_slug}")
        print(f"  Metadata base: {metadata_base}")
        print(f"  Raw base: {raw_base}")
        print(f"  Output directory: {args.output}")
        print(f"  Keyword method: {args.keyword_method}")
        print(f"  Num keywords: {args.num_keywords}")
        print(f"  Verbose: {args.verbose}\n")
    
    # Run experiment with configuration
    run_experiment_with_output(
        company_slug, 
        args.output, 
        str(metadata_base), 
        str(raw_base),
        keyword_method=args.keyword_method,
        num_keywords=args.num_keywords
    )


def run_experiment_with_output(company_slug: str, output_dir_override: str = None, metadata_base: str = "data/metadata", raw_base: str = "data/raw", keyword_method: str = "tfidf", num_keywords: int = 5):
    """Run experiment with custom output directory and data sources."""
    metadata_path = Path(metadata_base)
    raw_path = Path(raw_base)
    output_dir = Path(output_dir_override) if output_dir_override else Path("data/rag_experiments")
    ensure_dir(output_dir)

    print(f"\n🔍 Collecting text pages for company: {company_slug}")
    texts_with_metadata, first_source = collect_texts_from_provenance(
        company_slug, metadata_path, raw_path
    )
    
    print(f"✅ Pages processed: {len(texts_with_metadata)}\n")

    strategies = {
        "Recursive": chunk_recursive,
        "MarkdownHeader": chunk_markdownheader,
    }

    # For summary.json
    detailed_results: Dict[str, Dict[str, Any]] = {}
    all_page_types = list(set(item["page_type"] for item in texts_with_metadata))
    
    # Track total text size across all pages
    total_doc_size_chars = sum(item["text_size"] for item in texts_with_metadata)

    for strat_name, splitter_fn in strategies.items():
        print(f"→ Running {strat_name} ...")
        t0 = time.perf_counter()
        
        # Process each text file separately to maintain source tracking
        all_raw_chunks = []
        for text_item in texts_with_metadata:
            text = text_item["text"]
            page_type = text_item["page_type"]
            source_file = text_item["text_file"]
            
            # Call splitter with source information
            raw_chunks = splitter_fn(text, source_file=source_file, page_type=page_type)
            all_raw_chunks.extend(raw_chunks)
        
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # Convert to chunk JSON schema with keyword extraction
        old_chunks = to_old_style_chunks(company_slug, strat_name, all_raw_chunks, keyword_method=keyword_method, num_keywords=num_keywords)

        # Save chunk file to the expected filename
        file_key = STRATEGY_FILE_KEYS[strat_name]  # e.g., "chunks_recursive"
        out_path = output_dir / f"{file_key}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(old_chunks, f, indent=2)
        print(f"  ✓ Saved {len(old_chunks)} chunks to {out_path}")

        # Collect metrics for the summary
        stats = compute_summary_stats(strat_name, old_chunks)
        stats["execution_time_ms"] = round(elapsed_ms, 1)
        detailed_results[strat_name] = stats

    # Build summary.json payload
    summary_payload = {
        "document": first_source,
        "company_slug": company_slug,
        "pages_processed": len(texts_with_metadata),
        "page_types": all_page_types,
        "document_size_chars": total_doc_size_chars,
        "strategies_tested": len(strategies),
        "results": detailed_results,
    }

    summary_path = output_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2)

    print("\n📊 Summary:")
    print(json.dumps(summary_payload, indent=2))
    print(f"\n✅ All outputs written to {output_dir.resolve()}\n")


if __name__ == "__main__":
    main()