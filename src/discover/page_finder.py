#!/usr/bin/env python3
"""
Object-oriented implementation of page discovery with LLM integration.
This class replaces the previous script-based approach in llm_page_finder.py
with a more robust and reusable class-based design.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# Import models
from .pydantic_models import (
    DiscoveryRequest,
    DiscoveredPage,
    DiscoveryResult,
    URLValidationResult,
)

class PageFinder:
    """
    Main class for discovering specific page types on websites using LLM.
    
    Features:
    - Clean object-oriented design
    - Reusable instance for multiple discoveries
    - Configurable LLM backend (OpenAI or Anthropic)
    - Built-in caching and validation
    - Proper error handling and logging
    
    Usage:
        finder = PageFinder()
        result = finder.discover_page("https://example.com", "careers")
    """
    
    def __init__(
        self,
        model: str = "gpt-4-turbo-preview",
        temperature: float = 0.3,
        request_timeout: int = 10,
        cache_results: bool = True,
        logger: Optional[logging.Logger] = None
    ):
        """Initialize the page finder with configuration."""
        self.model = model
        self.temperature = temperature
        self.request_timeout = request_timeout
        self.cache_results = cache_results
        self._cache = {}
        self.logger = logger or self._setup_logger()
        self.llm = self._setup_llm()
        
        # Headers for requests
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logging."""
        logger = logging.getLogger("page_finder")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _setup_llm(self):
        """Initialize LLM backend."""
        if os.getenv("OPENAI_API_KEY") and ChatOpenAI is not None:
            return ChatOpenAI(
                model=self.model,
                temperature=self.temperature
            )
        elif os.getenv("ANTHROPIC_API_KEY") and ChatAnthropic is not None:
            return ChatAnthropic(
                model="claude-3-opus-20240229",
                temperature=self.temperature
            )
        else:
            raise ValueError(
                "No LLM configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY "
                "and install required packages."
            )
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL with scheme and trailing slash."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        if not url.endswith("/"):
            url = f"{url}/"
        return url
    
    def _validate_url(self, url: str) -> URLValidationResult:
        """Validate if URL exists and is accessible."""
        validation_score = 0.5
        exists = False
        status_code = None
        is_redirect = False
        final_url = url
        reason = "Not checked"
        
        try:
            # Try HEAD request first
            response = requests.head(
                url,
                headers=self.headers,
                timeout=self.request_timeout,
                verify=False,
                allow_redirects=False
            )
            
            status_code = response.status_code
            
            # Handle redirects
            if status_code in (301, 302, 303, 307, 308):
                redirect_url = response.headers.get('Location')
                if redirect_url:
                    final_url = urljoin(url, redirect_url)
                    redirect_response = requests.head(
                        final_url,
                        headers=self.headers,
                        timeout=self.request_timeout,
                        verify=False
                    )
                    if 200 <= redirect_response.status_code < 300:
                        exists = True
                        validation_score = 0.85
                        reason = f"Redirects to valid page ({redirect_response.status_code})"
                    else:
                        validation_score = 0.25
                        reason = f"Redirects to invalid page ({redirect_response.status_code})"
                    is_redirect = True
            
            # Direct success
            elif 200 <= status_code < 300:
                exists = True
                validation_score = 1.0
                reason = f"Direct success ({status_code})"
            
            # Common error cases
            elif status_code == 404:
                validation_score = 0.1
                reason = "Page not found"
            elif status_code == 403:
                validation_score = 0.3
                reason = "Access forbidden"
            else:
                validation_score = 0.2
                reason = f"Unexpected status: {status_code}"
        
        except requests.exceptions.Timeout:
            validation_score = 0.2
            reason = "Timeout"
        except requests.exceptions.ConnectionError:
            validation_score = 0.2
            reason = "Connection error"
        except Exception as e:
            validation_score = 0.15
            reason = f"Error: {str(e)}"
        
        return URLValidationResult(
            url=url,
            exists=exists,
            status_code=status_code or 0,
            is_redirect=is_redirect,
            final_url=final_url,
            reason=reason,
            validation_score=validation_score
        )
    
    def _extract_links(self, url: str, html_content: str) -> Dict:
        """Extract all relevant links from page content."""
        soup = BeautifulSoup(html_content, "html.parser")
        base_domain = urlparse(url).netloc.lower()
        
        links_data = {
            "internal_links": [],
            "external_links": [],
            "mailto_links": [],
            "all_links_with_text": [],
            "is_javascript_rendered": False,
            "detection_method": "Standard HTML"
        }
        
        # Check if page is JavaScript-rendered
        has_nextjs = '_next' in html_content.lower()
        has_react = 'react' in html_content.lower() or '__REACT_' in html_content
        has_vue = '__vue__' in html_content or 'vue' in html_content.lower()
        links_data["is_javascript_rendered"] = has_nextjs or has_react or has_vue
        
        if links_data["is_javascript_rendered"]:
            links_data["detection_method"] = "JavaScript Framework Detected"
        
        # Extract links from HTML
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            text = a.get_text().strip()
            
            if not href or href == "#":
                continue
            
            # Normalize URL
            if not href.startswith(("http://", "https://", "mailto:")):
                href = urljoin(url, href)
            
            link_info = {"url": href, "text": text}
            
            if href.startswith("mailto:"):
                links_data["mailto_links"].append(link_info)
            elif base_domain in urlparse(href).netloc.lower():
                links_data["internal_links"].append(link_info)
            else:
                links_data["external_links"].append(link_info)
            
            links_data["all_links_with_text"].append(link_info)
        
        return links_data
    
    def _fetch_page_content(self, url: str) -> Optional[Dict]:
        """Fetch and parse webpage content."""
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.request_timeout,
                verify=False
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Get title
            title = soup.title.string if soup.title else "No title"
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)
            
            # Truncate to avoid token limits
            if len(text) > 4000:
                text = text[:4000] + "..."
            
            # Extract links
            links = self._extract_links(url, response.text)
            
            return {
                "text": text,
                "title": title,
                "links": links,
                "html": response.text
            }
            
        except Exception as e:
            self.logger.warning(f"Failed to fetch {url}: {e}")
            return None
    
    def _create_llm_prompt(self, website_url: str, page_type: str, content: Dict) -> str:
        """Create enhanced prompt for LLM."""
        links = content.get("links", {})
        all_links = links.get("all_links_with_text", [])
        is_spa = links.get("is_javascript_rendered", False)
        detection_method = links.get("detection_method", "Standard HTML")
        
        # Create link context
        if all_links:
            link_context = f"Extracted links from the page ({len(all_links)} total):\n"
            for i, link_item in enumerate(all_links[:20]):
                link_context += f"{i+1}. {link_item['url']} - {link_item['text']}\n"
        else:
            link_context = (
                f"[NO STATIC LINKS FOUND - {detection_method}]\n\n"
                "Note: This appears to be a JavaScript-rendered page.\n"
                "Common patterns to try:\n"
                "  - /careers\n  - /jobs\n  - /about\n  - /products"
            )
        
        # Create instructions based on available data
        if all_links:
            instructions = (
                f"1. Review the ACTUAL LINKS FOUND section\n"
                f"2. Identify which link(s) most likely lead to the {page_type} page\n"
                f"3. Consider both URL paths and link text\n"
                f"4. External links may be valid for careers pages\n"
                f"5. Return URLs from the provided list when possible"
            )
        else:
            instructions = (
                f"1. This is a JavaScript-rendered page without static links\n"
                f"2. Use content and common URL patterns to make suggestions\n"
                f"3. Consider industry-standard locations for {page_type} pages\n"
                f"4. Look for external integrations when relevant\n"
                f"5. Be specific with URL suggestions"
            )
        
        # Construct final prompt
        return f"""You are a web analyst. Find the URL for a {page_type} page.

Website: {website_url}
Page Type: {page_type}
Page Title: {content.get('title', 'Unknown')}

AVAILABLE LINKS:
{link_context}

PAGE CONTENT PREVIEW:
{content.get('text', '')[:2000]}

INSTRUCTIONS:
{instructions}

Return a JSON response with:
- discovered_url: The most likely URL
- confidence: 0.0-1.0 score
- reasoning: Brief explanation
- alternative_urls: Other possible URLs"""
    
    def discover_page(self, website_url: str, page_type: str) -> DiscoveryResult:
        """
        Main method to discover a specific page type on a website.
        
        Args:
            website_url: The website to search
            page_type: Type of page to find (e.g., "careers", "about")
            
        Returns:
            DiscoveryResult with the found page info and confidence
        """
        # Check cache first
        cache_key = (website_url, page_type)
        if self.cache_results and cache_key in self._cache:
            return self._cache[cache_key]
        
        self.logger.info(f"Starting discovery: {page_type} page on {website_url}")
        
        # Normalize URL
        website_url = self._normalize_url(website_url)
        
        # Fetch content
        content = self._fetch_page_content(website_url)
        if not content:
            return self._create_error_result(website_url, page_type)
        
        # Create LLM prompt
        prompt = self._create_llm_prompt(website_url, page_type, content)
        
        try:
            # Get LLM response
            response = self.llm.invoke(prompt)
            
            # Parse response (example - implement proper parsing)
            import json
            result_dict = json.loads(response.content)
            
            # Validate discovered URL
            if result_dict.get("discovered_url"):
                validation = self._validate_url(result_dict["discovered_url"])
                
                # Adjust confidence based on validation
                confidence = float(result_dict.get("confidence", 0.5))
                confidence *= validation.validation_score
                
                # Create result
                result = DiscoveryResult(
                    request=DiscoveryRequest(
                        website_url=website_url,
                        page_type=page_type,
                        page_content_snippet=content["text"][:500]
                    ),
                    result=DiscoveredPage(
                        page_type=page_type,
                        discovered_url=validation.final_url if validation.exists else result_dict["discovered_url"],
                        confidence=confidence,
                        reasoning=f"{result_dict.get('reasoning')} | {validation.reason}",
                        alternative_urls=result_dict.get("alternative_urls", [])
                    )
                )
                
                # Cache result
                if self.cache_results:
                    self._cache[cache_key] = result
                
                return result
            
            return self._create_error_result(website_url, page_type)
            
        except Exception as e:
            self.logger.error(f"LLM discovery failed: {e}")
            return self._create_error_result(website_url, page_type)
    
    def _create_error_result(self, website_url: str, page_type: str) -> DiscoveryResult:
        """Create an error result when discovery fails."""
        return DiscoveryResult(
            request=DiscoveryRequest(
                website_url=website_url,
                page_type=page_type,
                page_content_snippet="[Failed to process]"
            ),
            result=DiscoveredPage(
                page_type=page_type,
                discovered_url=None,
                confidence=0.0,
                reasoning="Failed to discover page",
                alternative_urls=[]
            )
        )

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Discover specific page types from websites using LLM."
    )
    parser.add_argument(
        "--website",
        required=True,
        help="Website URL (e.g., https://example.com)"
    )
    parser.add_argument(
        "--page-type",
        required=True,
        help="Type of page to discover (e.g., careers, about)"
    )
    parser.add_argument(
        "--model",
        default="gpt-4-turbo-preview",
        help="LLM model to use"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        help="LLM temperature (0.0-1.0)"
    )
    args = parser.parse_args()
    
    # Create finder instance
    finder = PageFinder(model=args.model, temperature=args.temperature)
    
    # Discover page
    result = finder.discover_page(args.website, args.page_type)
    
    # Print result
    print(result.model_dump_json(indent=2))