"""
Test script for RAG search endpoint.

Provides curl-like examples and Python test functions to verify the /rag/search endpoint.

Usage:
    # Run the API first:
    python src/backend/rag_search_api.py
    
    # In another terminal, run the tests:
    python src/backend/test_rag_search.py
"""

import requests
import json
import sys
from typing import Dict, Any, List
from pathlib import Path

# Configuration
API_URL = "http://localhost:8000"
DEFAULT_COLLECTION = "world_labs_chunks"

# ANSI color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_section(title: str):
    """Print a section header."""
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}{title}{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")


def print_success(msg: str):
    """Print success message."""
    print(f"{GREEN}✓ {msg}{RESET}")


def print_error(msg: str):
    """Print error message."""
    print(f"{RED}✗ {msg}{RESET}")


def print_info(msg: str):
    """Print info message."""
    print(f"{BLUE}ℹ {msg}{RESET}")


def print_result(data: Dict[str, Any], indent: int = 2):
    """Pretty print result JSON."""
    print(json.dumps(data, indent=indent))


def test_health_check() -> bool:
    """Test health check endpoint."""
    print_section("Testing Health Check Endpoint")
    
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_result(data)
            
            if data.get("qdrant_connected"):
                print_success("Qdrant is connected and healthy")
                return True
            else:
                print_error("Qdrant is not connected")
                return False
        else:
            print_error(f"Unexpected status code: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Health check failed: {e}")
        return False


def test_search_query(
    query: str,
    collection_name: str = DEFAULT_COLLECTION,
    top_k: int = 5,
    threshold: float = None,
) -> bool:
    """Test search endpoint with a query."""
    print_section(f"Testing Search: '{query}'")
    print_info(f"Collection: {collection_name}")
    print_info(f"Top K: {top_k}")
    if threshold:
        print_info(f"Threshold: {threshold}")
    
    try:
        payload = {
            "query": query,
            "collection_name": collection_name,
            "top_k": top_k,
        }
        if threshold:
            payload["threshold"] = threshold
        
        response = requests.post(
            f"{API_URL}/rag/search",
            json=payload,
            timeout=10,
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_result(data)
            
            results = data.get("results", [])
            if results:
                print_success(f"Found {len(results)} results")
                
                # Print top result details
                top_result = results[0]
                print(f"\n{BOLD}Top Result:{RESET}")
                print(f"  Similarity Score: {GREEN}{top_result['similarity_score']:.4f}{RESET}")
                print(f"  Text Preview: {top_result['text'][:200]}...")
                
                # Print metadata
                metadata = top_result.get("metadata", {})
                if metadata:
                    print(f"\n{BOLD}Top Result Metadata:{RESET}")
                    print(f"  Chunk ID: {metadata.get('chunk_id')}")
                    print(f"  Page Type: {metadata.get('page_type')}")
                    print(f"  Source File: {metadata.get('source_file')}")
                    print(f"  Keywords: {metadata.get('keywords', [])}")
                    print(f"  Company: {metadata.get('company_slug')}")
                
                return True
            else:
                print_error("No results found")
                return False
        else:
            print_error(f"Unexpected status code: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print_error(f"Search failed: {e}")
        return False


def test_checkpoint_queries() -> bool:
    """Test checkpoint queries: 'funding' and 'leadership'."""
    print_section("Testing Checkpoint Queries")
    
    queries = [
        ("funding", "Should return chunks about company funding and investment"),
        ("leadership", "Should return chunks about company leadership and team"),
    ]
    
    all_passed = True
    for query, description in queries:
        print(f"\n{BOLD}Query: '{query}'{RESET}")
        print(f"Expected: {description}")
        
        if test_search_query(query, top_k=3):
            print_success("Query returned valid results")
        else:
            print_error("Query failed or returned no results")
            all_passed = False
    
    return all_passed


def test_multi_word_queries() -> bool:
    """Test multi-word queries."""
    print_section("Testing Multi-Word Queries")
    
    queries = [
        "spatial intelligence",
        "3D world generation",
        "artificial intelligence",
        "large language models",
    ]
    
    all_passed = True
    for query in queries:
        if test_search_query(query, top_k=3):
            print_success(f"Query '{query}' successful")
        else:
            print_error(f"Query '{query}' failed")
            all_passed = False
    
    return all_passed


def test_curl_examples():
    """Print curl command examples for testing."""
    print_section("Curl Command Examples")
    
    examples = [
        {
            "description": "Basic search - funding",
            "command": 'curl -X POST http://localhost:8000/rag/search -H "Content-Type: application/json" -d \'{"query": "funding", "top_k": 5}\'',
        },
        {
            "description": "Search with similarity threshold",
            "command": 'curl -X POST http://localhost:8000/rag/search -H "Content-Type: application/json" -d \'{"query": "leadership", "top_k": 5, "threshold": 0.5}\'',
        },
        {
            "description": "Health check",
            "command": "curl http://localhost:8000/health",
        },
        {
            "description": "Root endpoint",
            "command": "curl http://localhost:8000/",
        },
        {
            "description": "API documentation",
            "command": "# Open in browser: http://localhost:8000/docs",
        },
    ]
    
    for example in examples:
        print(f"\n{BOLD}{example['description']}{RESET}")
        print(f"{YELLOW}{example['command']}{RESET}")


def main():
    """Run all tests."""
    print(f"\n{BOLD}{BLUE}RAG Search API Test Suite{RESET}")
    print(f"API URL: {API_URL}")
    print(f"Collection: {DEFAULT_COLLECTION}\n")
    
    # Check if API is running
    try:
        response = requests.get(f"{API_URL}/", timeout=2)
        print_success(f"API is running at {API_URL}")
    except Exception as e:
        print_error(f"Cannot reach API at {API_URL}: {e}")
        print_info("Start the API with: python src/backend/rag_search_api.py")
        sys.exit(1)
    
    # Run tests
    results = {
        "Health Check": test_health_check(),
        "Checkpoint Queries (funding, leadership)": test_checkpoint_queries(),
        "Multi-word Queries": test_multi_word_queries(),
    }
    
    # Print curl examples
    test_curl_examples()
    
    # Summary
    print_section("Test Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = f"{GREEN}PASSED{RESET}" if result else f"{RED}FAILED{RESET}"
        print(f"{status} - {test_name}")
    
    print(f"\n{BOLD}Total: {passed}/{total} test groups passed{RESET}\n")
    
    if passed == total:
        print_success("All tests passed!")
        return 0
    else:
        print_error("Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
