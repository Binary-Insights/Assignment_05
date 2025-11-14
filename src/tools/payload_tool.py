from typing import Optional
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path to allow imports from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.rag_models import Payload

# Setup logging
logger = logging.getLogger(__name__)

# Simple in-memory cache to avoid repeated disk reads
_payload_cache = {}

async def get_latest_structured_payload(company_id: str) -> Payload:
    """
    Tool: get_latest_structured_payload

    Retrieve the latest fully assembled structured payload for a company.
    The payload should include:
      - company_record (Company with legal_name, website, founding info, etc.)
      - events (List of Event: funding rounds, M&A, partnerships, etc.)
      - snapshots (List of Snapshot: headcount, hiring, pricing at points in time)
      - products (List of Product: name, description, pricing model, etc.)
      - leadership (List of Leadership: founders, executives, roles)
      - visibility (List of Visibility: news mentions, GitHub stars, ratings)

    Args:
        company_id: The canonical company_id used in your data pipeline.
                   Can be in formats like "world-labs", "world_labs", "World Labs", etc.

    Returns:
        A complete Payload object for the requested company.

    Raises:
        FileNotFoundError: If no payload file exists for the company
        ValueError: If payload file is corrupted or invalid JSON

    Example:
        payload = await get_latest_structured_payload("coactive")
        print(f"Company: {payload.company_record.legal_name}")
        print(f"Events: {len(payload.events)}")
        print(f"Products: {len(payload.products)}")
    """
    # Check in-memory cache first for performance
    if company_id in _payload_cache:
        logger.debug(f"Returning cached payload for {company_id}")
        return _payload_cache[company_id]
    
    # Look for payload file in data/payloads/ directory
    # The file should be named {company_id}.json
    payload_file = Path(f"data/payloads/{company_id}.json")
    
    if not payload_file.exists():
        # List available payloads to help debugging
        payloads_dir = Path("data/payloads")
        available = []
        if payloads_dir.exists():
            available = [f.stem for f in payloads_dir.glob("*.json")]
        
        raise FileNotFoundError(
            f"Payload not found for '{company_id}' at {payload_file.absolute()}\n"
            f"Available payloads: {available if available else 'none found'}"
        )
    
    try:
        # Load JSON file
        with open(payload_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Validate and parse using Pydantic model
        payload = Payload.model_validate(data)
        
        # Store in cache for subsequent calls
        _payload_cache[company_id] = payload
        
        # Log summary
        logger.info(
            f"✓ Loaded payload for '{company_id}': "
            f"company_record={payload.company_record.legal_name}, "
            f"events={len(payload.events)}, "
            f"snapshots={len(payload.snapshots)}, "
            f"products={len(payload.products)}, "
            f"leadership={len(payload.leadership)}, "
            f"visibility={len(payload.visibility)}"
        )
        
        return payload
        
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Payload file for '{company_id}' is corrupted - invalid JSON: {e}"
        )
    except Exception as e:
        raise ValueError(
            f"Failed to load/validate payload for '{company_id}': {e}"
        )