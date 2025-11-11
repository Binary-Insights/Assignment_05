import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path("/app")
GROUND_TRUTH_FILE = PROJECT_ROOT / "data" / "eval" / "ground_truth.json"

logger.info(f"Checking: {GROUND_TRUTH_FILE}")
logger.info(f"Exists: {GROUND_TRUTH_FILE.exists()}")

if GROUND_TRUTH_FILE.exists():
    with open(GROUND_TRUTH_FILE, "r") as f:
        ground_truth = json.load(f)
    companies = list(ground_truth.keys())
    logger.info(f"✓ Loaded {len(companies)} companies: {companies}")
else:
    logger.error("File does not exist!")
