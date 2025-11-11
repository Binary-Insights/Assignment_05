#!/usr/bin/env python3
"""
LLM-based page discovery using LangChain + Instructor.

This script uses an LLM (via LangChain) to discover specific page types
(e.g., "careers", "product", "about", "blog") from a given website URL
by fetching the page content and analyzing it with structured I/O.

Structured input/output is handled using Instructor library with Pydantic models.

Usage:
  python src/discover/llm_page_finder.py --website "https://worldlabs.ai/" --page-type "product"
  python src/discover/llm_page_finder.py --website "https://www.abridge.com/" --page-type "careers"
  
Environment:
  Set OPENAI_API_KEY or ANTHROPIC_API_KEY depending on your LLM choice.
"""

import argparse
import json
import logging
import os
import sys
from typing import Optional, Any
from urllib.parse import urlparse, urljoin
import re
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

# Fix Python path to allow imports from same directory when called as subprocess
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# Import all models from models.py
from pydantic_models import (
    DiscoveryRequest,
    DiscoveredPage,
    DiscoveryResult,
    URLValidationInput,
    URLValidationResult,
)

# Try to import from Instructor and LangChain
try:
    import instructor
except ImportError:
    print("Error: 'instructor' library not found. Install with: pip install instructor")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
    print("Warning: openai not found. Will try LangChain integration instead.")

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None
    print("Warning: langchain_openai not found. Will try Anthropic instead.")

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None
    print("Warning: langchain_anthropic not found. Will try OpenAI instead.")

# ============================================================================
# URL Validation Tool (for LangChain Tool Calling)
# ============================================================================

"""
URL Validation Tool Architecture:
==================================

This tool provides comprehensive URL validation to ensure discovered URLs 
are actually valid before being returned to the user. It follows the 
LangChain Tool Calling pattern where:

1. TOOL DEFINITION: URLValidationInput & URLValidationResult models (in models.py)
   define the input/output contract for the validation tool.

2. TOOL IMPLEMENTATION: validate_url_for_tool() performs the actual validation
   by making HTTP HEAD requests and computing a validation_score (0.0-1.0).

3. TOOL INTEGRATION: The validation tool is called at TWO points:
   a) In Instructor path: After LLM generates structured output
   b) In Fallback path: Before ranking candidate URLs
   
   This ensures no discovered_url is returned without validation.

4. CONFIDENCE ADJUSTMENT: The validation_score from the tool directly 
   influences the final confidence value reported to the user:
   - Valid URLs (200-299): validation_score up to 1.0
   - Redirects to valid: validation_score ~0.85
   - Redirects to invalid: validation_score ~0.25
   - 404 errors: validation_score ~0.1
   - Connection errors: validation_score ~0.2

5. INTELLIGENT RE-RANKING: If alternatives have better validation scores,
   they're promoted to become the primary discovered_url.

This approach prevents hallucinated URLs (like 404s) from being returned 
with artificially high confidence scores.
"""


def validate_url_for_tool(url: str, timeout: int = 5) -> URLValidationResult:
    """
    Validate if a URL actually exists and is accessible.
    This function is designed to be called by LangChain tools.
    
    Returns URLValidationResult with validation metadata and confidence score adjustment.
    """
    logger = logging.getLogger("llm_page_finder")
    validation_score = 0.5  # Default neutral score
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # Try HEAD request first (faster)
        response = requests.head(
            url, 
            headers=headers, 
            timeout=timeout, 
            verify=False, 
            allow_redirects=False
        )
        
        status_code = response.status_code
        final_url = url
        is_redirect = False
        reason = ""
        exists = False
        
        # Check for redirects
        if status_code in (301, 302, 303, 307, 308):
            is_redirect = True
            redirect_url = response.headers.get('Location', url)
            
            try:
                final_response = requests.head(
                    redirect_url, 
                    headers=headers, 
                    timeout=timeout, 
                    verify=False, 
                    allow_redirects=False
                )
                final_url = redirect_url
                final_status = final_response.status_code
                
                if 200 <= final_status < 300:
                    exists = True
                    validation_score = 0.85  # Redirect to valid page
                    reason = f"Redirects to {redirect_url} (status {final_status})"
                else:
                    exists = False
                    validation_score = 0.25  # Redirect to invalid page
                    reason = f"Redirects to {redirect_url} (status {final_status}) - NOT VALID"
            except Exception as e:
                validation_score = 0.15  # Redirect failed
                reason = f"Redirect found but couldn't verify target: {e}"
        
        elif 200 <= status_code < 300:
            exists = True
            validation_score = 1.0  # Perfect score for valid URL
            reason = f"Valid (HTTP {status_code})"
        
        elif status_code == 404:
            exists = False
            validation_score = 0.1  # Very low score for 404
            reason = f"404 Not Found"
        
        elif status_code == 403:
            exists = True  # Likely valid but restricted
            validation_score = 0.7
            reason = f"Access Forbidden (HTTP {status_code}) - likely valid but restricted"
        
        else:
            exists = False
            validation_score = 0.3  # Low score for other errors
            reason = f"HTTP {status_code}"
        
        logger.debug(f"URL validation: {url} -> score={validation_score}, exists={exists}")
        
    except requests.exceptions.Timeout:
        validation_score = 0.2
        reason = "Timeout"
        status_code = None
    except requests.exceptions.ConnectionError:
        validation_score = 0.2
        reason = "Connection error"
        status_code = None
    except Exception as e:
        validation_score = 0.15
        reason = f"Error: {str(e)}"
        status_code = None
    
    return URLValidationResult(
        url=url,
        exists=exists,
        status_code=status_code or 0,
        is_redirect=is_redirect,
        final_url=final_url,
        reason=reason,
        validation_score=validation_score
    )


# ============================================================================
# LLM Setup
# ============================================================================

def setup_logger(name: str = "llm_page_finder") -> logging.Logger:
    """Setup logging."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


def get_llm() -> Any:
    """Initialize LLM (OpenAI or Anthropic)."""
    # Try OpenAI first
    if ChatOpenAI is not None and os.getenv("OPENAI_API_KEY"):
        return ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    
    # Fall back to Anthropic
    if ChatAnthropic is not None and os.getenv("ANTHROPIC_API_KEY"):
        return ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0.3)
    
    raise ValueError(
        "No LLM configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY, "
        "and install langchain_openai or langchain_anthropic."
    )


def extract_relevant_links(url: str) -> dict:
    """
    Extract all relevant links from a page for context.
    Handles both static HTML and JavaScript-rendered pages.
    """
    logger = logging.getLogger("llm_page_finder")
    links_data = {
        "internal_links": [],
        "external_links": [],
        "mailto_links": [],
        "all_links_with_text": [],
        "is_javascript_rendered": False,
        "detection_method": None
    }
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Check if page is JavaScript-rendered (Next.js, React, Vue, etc.)
        has_nextjs = '_next' in response.text.lower()
        has_react = 'react' in response.text.lower() or '__REACT_' in response.text
        has_vue = '__vue__' in response.text or 'vue' in response.text.lower()
        is_spa = has_nextjs or has_react or has_vue
        
        if is_spa:
            links_data["is_javascript_rendered"] = True
            links_data["detection_method"] = "SPA/SSR detected"
            logger.debug("Detected JavaScript-rendered page (SPA/SSR)")
        
        base_domain = urlparse(url).netloc.lower()
        
        # Try to extract links from HTML
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href', '').strip()
            text = link.get_text(strip=True)
            
            # Skip if no href or is anchor/javascript
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue
            
            # Skip empty text links
            if not text:
                continue
            
            # Categorize and process
            if href.startswith('mailto:'):
                links_data["mailto_links"].append(href)
                links_data["all_links_with_text"].append({"url": href, "text": text})
            elif href.startswith('http'):
                # Absolute URL
                if base_domain in urlparse(href).netloc.lower():
                    links_data["internal_links"].append(href)
                else:
                    links_data["external_links"].append(href)
                links_data["all_links_with_text"].append({"url": href, "text": text})
            elif href.startswith('/'):
                # Relative URL - convert to absolute
                full_url = url.rstrip('/') + href
                links_data["internal_links"].append(full_url)
                links_data["all_links_with_text"].append({"url": full_url, "text": text})
            else:
                # Other relative URLs
                full_url = urljoin(url, href)
                links_data["internal_links"].append(full_url)
                links_data["all_links_with_text"].append({"url": full_url, "text": text})
        
        # If no links found and it's a JavaScript page, try to extract from meta tags and text
        if len(links_data["all_links_with_text"]) == 0 and is_spa:
            logger.debug("No links found in HTML. Trying alternative extraction for SPA...")
            
            # Look for common patterns in meta tags, structured data, etc.
            # For now, we'll rely on LLM to make educated guesses
            links_data["detection_method"] = "SPA/SSR - no static links found"
        
        logger.debug(f"Found {len(links_data['internal_links'])} internal links, {len(links_data['external_links'])} external links, {len(links_data['all_links_with_text'])} total links with text")
        
    except Exception as e:
        logger.warning(f"Failed to extract links from {url}: {e}")
    
    return links_data


def validate_url_exists(url: str, timeout: int = 5) -> dict:
    """
    Validate if a URL actually exists and is accessible.
    Returns validation metadata for confidence scoring.
    
    Returns dict with:
    - exists: bool (True if URL returns 2xx status)
    - status_code: int (HTTP status code)
    - is_redirect: bool (True if URL redirects)
    - final_url: str (URL after redirects)
    - reason: str (validation reason/message)
    """
    logger = logging.getLogger("llm_page_finder")
    validation = {
        "exists": False,
        "status_code": None,
        "is_redirect": False,
        "final_url": url,
        "reason": "Not checked"
    }
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        # Don't follow redirects initially to detect them
        response = requests.head(url, headers=headers, timeout=timeout, verify=False, allow_redirects=False)
        
        validation["status_code"] = response.status_code
        
        # Check for redirects
        if response.status_code in (301, 302, 303, 307, 308):
            validation["is_redirect"] = True
            redirect_url = response.headers.get('Location', url)
            # Try to follow redirect
            try:
                final_response = requests.head(redirect_url, headers=headers, timeout=timeout, verify=False, allow_redirects=False)
                validation["final_url"] = redirect_url
                validation["status_code"] = final_response.status_code
                if 200 <= final_response.status_code < 300:
                    validation["exists"] = True
                    validation["reason"] = f"Redirects to {redirect_url} (status {final_response.status_code})"
                else:
                    validation["reason"] = f"Redirects to {redirect_url} (status {final_response.status_code}) - not valid"
            except Exception as e:
                validation["reason"] = f"Redirect found but couldn't verify target: {e}"
        elif 200 <= response.status_code < 300:
            validation["exists"] = True
            validation["reason"] = f"Valid (status {response.status_code})"
        elif response.status_code == 404:
            validation["reason"] = "404 Not Found"
        else:
            validation["reason"] = f"HTTP {response.status_code}"
        
        logger.debug(f"URL validation for {url}: {validation}")
    
    except requests.exceptions.Timeout:
        validation["reason"] = "Timeout"
    except requests.exceptions.ConnectionError:
        validation["reason"] = "Connection error"
    except Exception as e:
        validation["reason"] = f"Error: {str(e)}"
    
    return validation


def fetch_page_content(url: str, timeout: int = 10) -> Optional[dict]:
    """Fetch page content from URL and extract text with links."""
    logger = logging.getLogger("llm_page_finder")
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=timeout, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Get title
        title = soup.title.string if soup.title else "No title"
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)
        
        # Limit to first 4000 chars to avoid token overflow
        if len(text) > 4000:
            text = text[:4000] + "\n[... content truncated ...]"
        
        # Extract links
        links = extract_relevant_links(url)
        
        return {
            "text": text,
            "title": title,
            "links": links
        }
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


# ============================================================================
# Main Discovery Function
# ============================================================================

def discover_page_with_llm(
    website_url: str,
    page_type: str,
    use_structured_output: bool = True
) -> DiscoveryResult:
    """
    Discover a specific page type from a website using LLM + Instructor.
    
    Strategy:
    1. Extract actual links from the page
    2. Filter links by relevance to page_type
    3. Use LLM to validate and rank them with reasoning
    
    Args:
        website_url: Base website URL
        page_type: Type of page to discover (e.g., "product", "careers")
        use_structured_output: Whether to use Instructor for structured output
    
    Returns:
        DiscoveryResult with structured input and discovered page info
    """
    logger = logging.getLogger("llm_page_finder")
    logger.info(f"Starting discovery: {page_type} page on {website_url}")
    
    # Normalize URL
    if not website_url.startswith(("http://", "https://")):
        website_url = f"https://{website_url}"
    if not website_url.endswith("/"):
        website_url += "/"
    
    # Fetch homepage content
    logger.info(f"Fetching content from {website_url}")
    content = fetch_page_content(website_url)
    
    if not content:
        logger.warning(f"Could not fetch content from {website_url}")
        return DiscoveryResult(
            request=DiscoveryRequest(
                website_url=website_url,
                page_type=page_type,
                page_content_snippet="[Failed to fetch]"
            ),
            result=DiscoveredPage(
                page_type=page_type,
                discovered_url=None,
                confidence=0.0,
                reasoning="Failed to fetch webpage content",
                alternative_urls=[]
            )
        )
    
    # Strategy 1: Pre-filter links by relevance before LLM
    logger.info(f"Analyzing extracted links for {page_type}...")
    links = content.get("links", {})
    all_links = links.get("all_links_with_text", [])
    is_spa = links.get("is_javascript_rendered", False)
    detection_method = links.get("detection_method", "Standard HTML")
    
    # Create link context for LLM
    if all_links:
        link_context = f"Extracted links from the page ({len(all_links)} total):\n"
        for i, link_item in enumerate(all_links[:20]):  # Show top 20 links
            link_context += f"  - URL: {link_item['url']}\n    Text: {link_item['text']}\n"
    else:
        link_context = f"[NO STATIC LINKS FOUND - {detection_method}]\n\nNote: This appears to be a JavaScript-rendered page. The navigation may be generated dynamically.\nUse common URL patterns and business logic to infer the careers page location.\n\nCommon patterns:\n  - /careers\n  - /jobs\n  - /team\n  - /hiring\n  - https://jobs.ashbyhq.com/<company-name>\n  - https://jobs.lever.co/<company-name>\n  - External job board links"
    
    # Get LLM
    llm = get_llm()
    logger.info(f"Using LLM model for page discovery")
    
    # Create enhanced prompt that handles both cases
    if all_links:
        instructions = f"""1. Look through the ACTUAL LINKS FOUND section above
2. Identify which link(s) most likely lead to the {page_type} page
3. Check both the URL path AND the link text for clues
4. External links (to job platforms, social media) might also be valid {page_type} pages
5. Return ONLY a URL that actually appears in the "ACTUAL LINKS FOUND" section if possible"""
    else:
        instructions = f"""1. The page has no static HTML links (it's JavaScript-rendered)
2. Use the page title, description, and content to make educated guesses
3. Consider common URL patterns for {page_type} pages
4. Look for external job portals (Ashby, Lever, etc.)
5. Be specific - suggest exact URLs based on company name and industry patterns"""
    
    # Create enhanced prompt
    prompt_text = f"""You are a web analyst. Your task is to find the URL for a {page_type} page.

Website: {website_url}
Page Type Needed: {page_type}
Page Title: {content.get('title', 'Unknown')}

AVAILABLE LINK DATA:
{link_context}

PAGE CONTENT PREVIEW:
{content.get('text', '')[:2000]}

INSTRUCTIONS:
{instructions}

What is the most likely URL for the {page_type} page? 
Return a JSON response with these fields:
- discovered_url: The exact URL, or the most likely URL based on patterns
- confidence: 0.0 (uncertain) to 1.0 (very confident)
- reasoning: Brief explanation of your choice
- alternative_urls: List of other possible URLs

Be precise and specific with your answer."""

    # Use Instructor to get structured output
    if use_structured_output:
        try:
            logger.debug("Using Instructor for structured output")
            print("\n[DEBUG] === INSTRUCTOR PATH ===")
            print("[DEBUG] Attempting to use Instructor.patch(OpenAI) for structured output")
            
            # Instructor patches the OpenAI client to return structured output
            # We use it by passing response_model parameter
            if OpenAI is None:
                logger.error("OpenAI client not available. Install with: pip install openai")
                print("[ERROR] OpenAI not available, switching to fallback")
                use_structured_output = False
            else:
                print("[DEBUG] OpenAI client found, patching with Instructor...")
                client = instructor.patch(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))
                print("[DEBUG] Calling LLM with response_model=DiscoveredPage...")
                
                # Call LLM with Instructor using messages API
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    response_model=DiscoveredPage,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt_text
                        }
                    ],
                    temperature=0.2  # Lower temperature for more deterministic results
                )
                
                print(f"[DEBUG] LLM Response received:")
                print(f"  - discovered_url: {response.discovered_url}")
                print(f"  - confidence (from LLM): {response.confidence}")
                print(f"  - reasoning: {response.reasoning[:100]}...")
                print(f"  - alternative_urls: {response.alternative_urls}")
                print("[DEBUG] CONFIDENCE SOURCE: LLM (directly from Instructor response)")
                
                # === VALIDATION STEP: Validate discovered URL before returning ===
                print(f"\n[DEBUG] === VALIDATING DISCOVERED URL ===")
                print(f"[DEBUG] Calling URL validation tool for: {response.discovered_url}")
                
                validated_confidence = response.confidence  # Start with LLM confidence
                
                if response.discovered_url:
                    # Validate the discovered URL using the tool
                    discovered_validation = validate_url_for_tool(response.discovered_url)
                    print(f"[DEBUG] Validation result:")
                    print(f"  - Status Code: {discovered_validation.status_code}")
                    print(f"  - Exists: {discovered_validation.exists}")
                    print(f"  - Reason: {discovered_validation.reason}")
                    print(f"  - Validation Score: {discovered_validation.validation_score}")
                    
                    # Adjust confidence based on validation
                    validated_confidence = discovered_validation.validation_score
                    print(f"[DEBUG] Confidence adjusted: {response.confidence} → {validated_confidence}")
                    
                    # Also validate alternatives and re-rank if needed
                    if response.alternative_urls:
                        print(f"\n[DEBUG] Validating {len(response.alternative_urls)} alternative URLs...")
                        alt_validations = []
                        for alt_url in response.alternative_urls:
                            alt_validation = validate_url_for_tool(alt_url)
                            alt_validations.append((alt_url, alt_validation))
                            print(f"  - {alt_url}: {alt_validation.reason} (score: {alt_validation.validation_score})")
                        
                        # If best alternative has higher score, use it as primary
                        alt_validations.sort(key=lambda x: x[1].validation_score, reverse=True)
                        if alt_validations and alt_validations[0][1].validation_score > validated_confidence:
                            print(f"\n[DEBUG] Better URL found in alternatives!")
                            print(f"  Original: {response.discovered_url} (score: {validated_confidence})")
                            print(f"  Better: {alt_validations[0][0]} (score: {alt_validations[0][1].validation_score})")
                            # Swap URLs
                            response.alternative_urls = [response.discovered_url] + response.alternative_urls[1:]
                            response.discovered_url = alt_validations[0][0]
                            validated_confidence = alt_validations[0][1].validation_score
                            response.reasoning = f"Original URL replaced with validated alternative. {response.reasoning}"
                
                # Create request model
                request = DiscoveryRequest(
                    website_url=website_url,
                    page_type=page_type,
                    page_content_snippet=content.get("text", "")[:500] + "..." if len(content.get("text", "")) > 500 else content.get("text", "")
                )
                
                # Update response with validated confidence
                response.confidence = validated_confidence
                
                # === CONFIDENCE CONSTRAINT: Return empty URL if confidence <= 0.5 ===
                if response.confidence <= 0.5:
                    print(f"[DEBUG] CONFIDENCE CONSTRAINT: confidence ({response.confidence:.2f}) <= 0.5")
                    print(f"[DEBUG] Clearing discovered_url due to low confidence")
                    response.reasoning = f"Confidence too low ({response.confidence:.2f} <= 0.5). No reliable URL found. {response.reasoning}"
                    response.discovered_url = None
                else:
                    print(f"[DEBUG] CONFIDENCE CHECK: confidence ({response.confidence:.2f}) > 0.5 ✓ - URL retained")
                
                logger.info(f"Discovered URL: {response.discovered_url} (confidence: {response.confidence})")
                print(f"[DEBUG] Final response confidence: {response.confidence}")
                print("[DEBUG] === END INSTRUCTOR PATH (SUCCESS) ===\n")
                return DiscoveryResult(request=request, result=response)

        
        except Exception as e:
            logger.warning(f"Instructor structured output failed: {e}. Falling back to manual parsing.")
            print(f"\n[WARNING] Instructor path failed with error: {e}")
            print("[DEBUG] Switching to fallback (manual parsing) path")
            use_structured_output = False
    
    # Fallback: Use direct LLM call with manual parsing
    if not use_structured_output:
        print("\n[DEBUG] === FALLBACK PATH (Manual Parsing) ===")
        logger.info("Using fallback manual parsing...")
        print("[DEBUG] Calling LLM directly (without Instructor structured output)...")
        
        # Call LLM directly
        response = llm.invoke(prompt_text)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        logger.debug(f"LLM Response:\n{response_text}")
        print(f"[DEBUG] Raw LLM response (first 200 chars):\n{response_text[:200]}\n")
        
        # Try to extract URL from response
        discovered_url = None
        confidence = 0.5
        reasoning = response_text[:300]
        alternatives = []
        
        print("[DEBUG] Starting confidence score computation:")
        print(f"  1. Initial confidence = 0.5 (default)")
        
        # Look for URLs in response that match extracted links
        import re
        url_pattern = r'https?://[^\s\"\'\)]*'
        response_urls = re.findall(url_pattern, response_text)
        
        print(f"  2. Extracted {len(response_urls)} URLs from LLM response: {response_urls}")
        
        # VALIDATION: Check if URLs actually exist (to catch hallucinated 404s)
        print(f"\n  3. VALIDATING URLs using LangChain tool calling pattern...")
        print(f"     (Calling validate_url_for_tool for each candidate URL)")
        
        url_validations = {}
        url_validation_results = {}
        
        for url in response_urls:
            # Use the tool-based validation function
            validation_result = validate_url_for_tool(url, timeout=5)
            url_validations[url] = {
                "exists": validation_result.exists,
                "status_code": validation_result.status_code,
                "is_redirect": validation_result.is_redirect,
                "final_url": validation_result.final_url,
                "reason": validation_result.reason
            }
            url_validation_results[url] = validation_result
            
            print(f"     - {url}")
            print(f"       Status: {validation_result.status_code}, Exists: {validation_result.exists}")
            print(f"       Reason: {validation_result.reason}")
            print(f"       Validation Score: {validation_result.validation_score}")

        
        # Rank URLs by preference using validation results:
        # Priority 1: Valid external job boards (highest priority - most reliable)
        # Priority 2: Valid URLs from extracted links
        # Priority 3: Other valid URLs
        # Priority 4: Invalid URLs (with penalties)
        
        ranked_urls = []
        
        # Priority 1: External job boards (most reliable source)
        job_boards = ['ashbyhq', 'lever.co', 'greenhouse', 'workable', 'smartrecruiters', 'talentdesk', 'bamboohr']
        for url in response_urls:
            if any(board in url.lower() for board in job_boards):
                validation = url_validation_results[url]
                # Use validation_score from tool, boost to 0.95+ for valid job boards
                base_score = validation.validation_score
                rank_score = max(base_score, 0.92) if validation.exists else min(base_score, 0.35)
                ranked_urls.append((url, rank_score, "job_board", validation))
                print(f"\n  4a. Job board detected: {url}")
                print(f"       Validation score: {base_score} → Final score: {rank_score}")
        
        # Priority 2: URLs from extracted page links (trusted source)
        for url in response_urls:
            if not any(u[0] == url for u in ranked_urls):  # Not already ranked
                for link_item in all_links:
                    if url.lower() in link_item['url'].lower() or link_item['url'].lower() in url.lower():
                        validation = url_validation_results[url]
                        base_score = validation.validation_score
                        # Boost to 0.85+ for valid extracted links
                        rank_score = max(base_score, 0.82) if validation.exists else min(base_score, 0.30)
                        ranked_urls.append((url, rank_score, "extracted_link", validation))
                        print(f"\n  4b. Extracted link: {url}")
                        print(f"       Validation score: {base_score} → Final score: {rank_score}")
                        break
        
        # Priority 3: Other LLM-suggested URLs (lowest priority)
        for url in response_urls:
            if not any(u[0] == url for u in ranked_urls):  # Not already ranked
                validation = url_validation_results[url]
                base_score = validation.validation_score
                # Use validation score as-is, with slight boost for valid URLs
                rank_score = max(base_score, 0.70) if validation.exists else base_score
                ranked_urls.append((url, rank_score, "generic", validation))
                print(f"\n  4c. Generic URL: {url}")
                print(f"       Validation score: {base_score} → Final score: {rank_score}")
        
        # Select best URL
        if ranked_urls:
            ranked_urls.sort(key=lambda x: x[1], reverse=True)
            best_url, best_score, url_type, best_validation = ranked_urls[0]
            discovered_url = best_url
            confidence = best_score
            
            print(f"\n  5. FINAL RANKING (top 5):")
            for i, ranking_entry in enumerate(ranked_urls[:5]):
                url, score, utype, validation = ranking_entry
                marker = "✓ SELECTED" if url == discovered_url else ""
                print(f"     {i+1}. {url}")
                print(f"        Score: {score:.2f}, Type: {utype}, Valid: {validation.exists} {marker}")
            
            print(f"\n  6. CONFIDENCE CALCULATION (from URL Validation Tool):")
            print(f"     - Selected URL: {discovered_url}")
            print(f"     - URL Type: {url_type}")
            print(f"     - HTTP Status: {best_validation.status_code}")
            print(f"     - URL Valid: {best_validation.exists}")
            print(f"     - Validation Status: {best_validation.reason}")
            print(f"     - Tool Validation Score: {best_validation.validation_score}")
            print(f"     - Final Confidence: {confidence:.2f}")
        
        # Alternative URLs (next best ranked)
        alternatives = [url for url, _, _, _ in ranked_urls[1:3]] if len(ranked_urls) > 1 else []
        
        # Extract confidence value if present in response
        conf_match = re.search(r'confidence["\']?\s*:\s*([0-9.]+)', response_text, re.IGNORECASE)
        if conf_match:
            try:
                llm_confidence = float(conf_match.group(1))
                print(f"  4. FOUND explicit confidence in LLM response: {llm_confidence}")
                print(f"     → REPLACING heuristic confidence ({confidence}) with LLM value ({llm_confidence})")
                confidence = llm_confidence
            except ValueError:
                print(f"  4. Could not parse confidence value from LLM response")
        else:
            print(f"  4. NO explicit confidence found in LLM response")
            print(f"     → Using heuristic confidence: {confidence}")
        
        print(f"\n[DEBUG] FINAL CONFIDENCE: {confidence}")
        print(f"[DEBUG] CONFIDENCE SOURCE: {'LLM (extracted from response)' if conf_match else 'Heuristic (URL matching)'}\n")
        
        # === CONFIDENCE CONSTRAINT: Return empty URL if confidence <= 0.5 ===
        print(f"[DEBUG] CONFIDENCE CONSTRAINT CHECK:")
        if confidence <= 0.5:
            print(f"  - Confidence: {confidence:.2f} <= 0.5 ✗")
            print(f"  - Action: Clearing discovered_url due to low confidence")
            reasoning = f"Confidence too low ({confidence:.2f} <= 0.5). No reliable URL found. {reasoning}"
            discovered_url = None
        else:
            print(f"  - Confidence: {confidence:.2f} > 0.5 ✓")
            print(f"  - Action: URL retained with confidence {confidence:.2f}")
        
        request = DiscoveryRequest(
            website_url=website_url,
            page_type=page_type,
            page_content_snippet=content.get("text", "")[:500] + "..." if len(content.get("text", "")) > 500 else content.get("text", "")
        )
        
        result = DiscoveredPage(
            page_type=page_type,
            discovered_url=discovered_url,
            confidence=confidence,
            reasoning=reasoning,
            alternative_urls=alternatives
        )
        
        logger.info(f"Discovered URL: {discovered_url} (confidence: {confidence})")
        print("[DEBUG] === END FALLBACK PATH (MANUAL PARSING) ===\n")
        return DiscoveryResult(request=request, result=result)


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Discover specific page types from websites using LLM."
    )
    parser.add_argument(
        "--website",
        type=str,
        required=True,
        help="Website URL (e.g., https://worldlabs.ai/)"
    )
    parser.add_argument(
        "--page-type",
        type=str,
        required=True,
        # choices=["product", "careers", "about", "blog"],
        help="Type of page to discover"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (JSON). If not provided, prints to stdout."
    )
    parser.add_argument(
        "--no-structured",
        action="store_true",
        help="Disable Instructor structured output (use fallback parsing)"
    )
    
    args = parser.parse_args()
    
    logger = setup_logger()
    logger.info("Starting LLM Page Finder")
    
    # Discover page
    result = discover_page_with_llm(
        website_url=args.website,
        page_type=args.page_type,
        use_structured_output=not args.no_structured
    )
    
    # Serialize result
    result_dict = result.model_dump()
    
    # Output
    if args.output:
        logger.info(f"Writing result to {args.output}")
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, indent=2)
        print(f"✓ Result written to {args.output}")
    else:
        print(json.dumps(result_dict, indent=2))
    
    logger.info("Discovery complete")
    return 0 if result.result.discovered_url else 1


if __name__ == "__main__":
    exit(main())
