"""
Structured pipeline for dashboard generation.

Loads structured payload JSON from data/payloads/ and uses LLM to generate 
investor-facing dashboard markdown.
"""

import json
import logging
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(env_path)
except ImportError:
    pass

logger = logging.getLogger(__name__)


def get_dashboard_system_prompt() -> str:
    """Load the dashboard system prompt from the markdown file."""
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "dashboard_system.md"
    
    if not prompt_path.exists():
        logger.warning(f"Dashboard system prompt not found at {prompt_path}")
        return ""
    
    try:
        return prompt_path.read_text()
    except Exception as e:
        logger.error(f"Failed to load dashboard prompt: {e}")
        return ""


def format_payload_for_llm(payload: Dict[str, Any]) -> str:
    """
    Format structured payload JSON into context for the LLM.
    
    Args:
        payload: The structured company payload from JSON
    
    Returns:
        Formatted context string
    """
    if not payload:
        return "No structured data available."
    
    context_parts = []
    
    # Company Record
    if "company_record" in payload and payload["company_record"]:
        context_parts.append("## Company Record")
        company = payload["company_record"]
        for key, value in company.items():
            if value:
                context_parts.append(f"**{key}:** {value}")
        context_parts.append("")
    
    # Events
    if "events" in payload and payload["events"]:
        context_parts.append(f"## Events ({len(payload['events'])} total)")
        for event in payload["events"][:10]:  # Limit to first 10 for brevity
            event_type = event.get("event_type", "Unknown")
            event_date = event.get("date", "Unknown date")
            event_desc = event.get("description", "")
            context_parts.append(f"- **{event_type}** ({event_date}): {event_desc}")
        if len(payload["events"]) > 10:
            context_parts.append(f"... and {len(payload['events']) - 10} more events")
        context_parts.append("")
    
    # Products
    if "products" in payload and payload["products"]:
        context_parts.append(f"## Products ({len(payload['products'])} total)")
        for product in payload["products"][:5]:  # Limit to first 5
            product_name = product.get("name", "Unknown")
            product_desc = product.get("description", "")
            context_parts.append(f"- **{product_name}**: {product_desc}")
        if len(payload["products"]) > 5:
            context_parts.append(f"... and {len(payload['products']) - 5} more products")
        context_parts.append("")
    
    # Leadership
    if "leadership" in payload and payload["leadership"]:
        context_parts.append(f"## Leadership ({len(payload['leadership'])} total)")
        for leader in payload["leadership"][:10]:  # Limit to first 10
            name = leader.get("name", "Unknown")
            title = leader.get("title", "")
            bio = leader.get("bio", "")
            context_parts.append(f"- **{name}** - {title}")
            if bio:
                context_parts.append(f"  {bio[:150]}...")  # Limit bio length
        if len(payload["leadership"]) > 10:
            context_parts.append(f"... and {len(payload['leadership']) - 10} more leaders")
        context_parts.append("")
    
    # Visibility
    if "visibility" in payload and payload["visibility"]:
        context_parts.append(f"## Visibility & Market Presence ({len(payload['visibility'])} mentions)")
        for visibility in payload["visibility"][:5]:
            mention = visibility.get("mention", "")
            source = visibility.get("source", "")
            context_parts.append(f"- **{source}**: {mention[:200]}...")
        if len(payload["visibility"]) > 5:
            context_parts.append(f"... and {len(payload['visibility']) - 5} more mentions")
        context_parts.append("")
    
    # Snapshots (funding, metrics, etc.)
    if "snapshots" in payload and payload["snapshots"]:
        context_parts.append(f"## Key Snapshots")
        for snapshot in payload["snapshots"][:10]:
            metric = snapshot.get("metric", "Unknown")
            value = snapshot.get("value", "")
            date = snapshot.get("date", "")
            context_parts.append(f"- **{metric}**: {value} (as of {date})")
        if len(payload["snapshots"]) > 10:
            context_parts.append(f"... and {len(payload['snapshots']) - 10} more snapshots")
        context_parts.append("")
    
    # Notes
    if "notes" in payload and payload["notes"]:
        context_parts.append("## Additional Notes")
        context_parts.append(payload["notes"])
        context_parts.append("")
    
    return "\n".join(context_parts)


def generate_dashboard_markdown(
    company_name: str,
    payload: Dict[str, Any],
    llm_client: Any = None,
    llm_model: str = "gpt-4o",
    temperature: float = 0.1
) -> str:
    """
    Generate investor-facing dashboard markdown using structured payload and LLM.
    
    Args:
        company_name: Name of the company
        payload: Structured company payload from JSON
        llm_client: OpenAI client (auto-initialized if None)
        llm_model: LLM model to use
        temperature: Temperature for LLM generation (0.0-2.0, default 0.1 for deterministic output)
    
    Returns:
        Markdown string with dashboard content
    """
    # Initialize LLM client if not provided
    if llm_client is None:
        try:
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                logger.error("OPENAI_API_KEY not set")
                return _generate_default_dashboard(company_name, payload)
            llm_client = OpenAI(api_key=api_key)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            return _generate_default_dashboard(company_name, payload)
    
    # Load system prompt
    system_prompt = get_dashboard_system_prompt()
    if not system_prompt:
        logger.warning("Dashboard system prompt is empty, using default template")
        return _generate_default_dashboard(company_name, payload)
    
    # Format payload as context
    context = format_payload_for_llm(payload)
    
    # Build user message
    user_message = f"""
Generate an investor-facing diligence dashboard for {company_name}.

Use ONLY the provided structured data below. If information is not available, use "Not disclosed."

Structured Company Data:
{context}

Generate the dashboard with the following sections in order:
1. Company Overview
2. Business Model and GTM
3. Funding & Investor Profile
4. Growth Momentum
5. Visibility & Market Sentiment
6. Risks and Challenges
7. Outlook
8. Disclosure Gaps

Use markdown formatting with ## for section headers.
"""
    
    try:
        logger.info(f"Calling LLM to generate dashboard for {company_name} (temperature={temperature})")
        
        response = llm_client.chat.completions.create(
            model=llm_model,
            max_tokens=4096,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )
        
        dashboard_markdown = response.choices[0].message.content
        logger.info(f"Successfully generated dashboard for {company_name}")
        
        return dashboard_markdown
        
    except Exception as e:
        logger.error(f"LLM call failed: {e}", exc_info=True)
        return _generate_default_dashboard(company_name, payload)


def _generate_default_dashboard(
    company_name: str,
    payload: Dict[str, Any]
) -> str:
    """Generate a fallback dashboard when LLM is unavailable."""
    logger.info(f"Generating default dashboard for {company_name}")
    
    context = format_payload_for_llm(payload)
    
    dashboard = f"""# {company_name} - Investor Diligence Dashboard

## Company Overview
Not disclosed.

## Business Model and GTM
Not disclosed.

## Funding & Investor Profile
Not disclosed.

## Growth Momentum
Not disclosed.

## Visibility & Market Sentiment
Not disclosed.

## Risks and Challenges
Not disclosed.

## Outlook
Not disclosed.

## Disclosure Gaps
**Available Data:**
{context}

**Note:** This is a fallback dashboard generated without LLM processing. 
For full dashboard generation, ensure OPENAI_API_KEY is set and the LLM is available.
"""
    
    return dashboard


def find_payload_file(company_name: str) -> Optional[Path]:
    """
    Find payload file with flexible naming conventions.
    
    Tries multiple variations:
    1. Slug with hyphens: "coactive-ai.json"
    2. Slug with underscores: "coactive_ai.json"
    3. Slug with no separators: "coactiveai.json"
    
    Args:
        company_name: Company display name (e.g., "Coactive AI")
    
    Returns:
        Path to found payload file or None
    """
    payloads_dir = Path("data/payloads")
    
    if not payloads_dir.exists():
        logger.debug(f"Payloads directory not found: {payloads_dir}")
        return None
    
    # Try different variations
    variants = [
        company_name.lower().replace(" ", "-").replace("_", "-"),  # coactive-ai
        company_name.lower().replace(" ", "_").replace("-", "_"),  # coactive_ai
        company_name.lower().replace(" ", "").replace("_", "").replace("-", ""),  # coactiveai
    ]
    
    for variant in variants:
        payload_file = payloads_dir / f"{variant}.json"
        if payload_file.exists():
            logger.debug(f"Found payload file: {payload_file}")
            return payload_file
    
    logger.debug(f"No payload file found for {company_name} (tried: {variants})")
    return None


def generate_dashboard_from_payload(
    company_name: str,
    company_slug: str,
    llm_client: Any = None,
    llm_model: str = "gpt-4o",
    temperature: float = 0.1,
    payload_file_path: Optional[Path] = None
) -> str:
    """
    Load structured payload and generate dashboard.
    
    Args:
        company_name: Display name of the company
        company_slug: Slug format (e.g., "world-labs")
        llm_client: OpenAI client (optional)
        llm_model: LLM model to use
        temperature: Temperature for LLM generation (0.0-2.0, default 0.1 for deterministic output)
        payload_file_path: Optional explicit path to payload file. If not provided, uses flexible matching.
    
    Returns:
        Dashboard markdown string
    
    Raises:
        FileNotFoundError: If payload file not found
        json.JSONDecodeError: If payload JSON is invalid
    """
    logger.info(f"Generating dashboard from structured payload for {company_name}")
    
    # Determine payload path
    if payload_file_path:
        payload_path = Path(payload_file_path)
        logger.debug(f"Using explicit payload path: {payload_path}")
    else:
        # Try flexible matching first
        found_path = find_payload_file(company_name)
        if found_path:
            payload_path = found_path
            logger.debug(f"Found payload via flexible matching: {payload_path}")
        else:
            # Fallback to normalized slug
            normalized_slug = company_slug.lower().replace(" ", "-").replace("_", "-")
            payload_path = Path("data/payloads") / f"{normalized_slug}.json"
            logger.debug(f"Using normalized slug path: {payload_path}")
    
    if not payload_path.exists():
        logger.error(f"Payload file not found: {payload_path}")
        raise FileNotFoundError(f"No payload found for {company_slug} at {payload_path}")
    
    try:
        with open(payload_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        logger.info(f"Successfully loaded payload from {payload_path}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in payload file: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to load payload: {e}")
        raise
    
    # Generate dashboard
    dashboard = generate_dashboard_markdown(
        company_name=company_name,
        payload=payload,
        llm_client=llm_client,
        llm_model=llm_model,
        temperature=temperature
    )
    
    return dashboard
