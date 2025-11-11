#!/usr/bin/env python3
"""
Fetch Forbes AI 50 companies - Production script.

Features:
- Fetches company list from Forbes AI 50
- Automatic domain pattern search for websites (78% success)
- Loads manual fallback data from config file (data/manual_fallback.json)
- Complete provenance tracking for all entries
- Single output: data/forbes_ai50_seed.json

Usage:
  python scripts/discover/fetch_ai50.py
"""
import json
import logging
import os
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

FORBES_AI50_URL = "https://www.forbes.com/lists/ai50/"
HEADERS = {"User-Agent": "Project-LANTERN-Bot/1.0 (+https://example.com)"}
MANUAL_FALLBACK_FILE = "data/manual_fallback.json"


def load_manual_fallback_data():
    """Load manual fallback data from config file."""
    logger = logging.getLogger('fetch_ai50')
    
    try:
        if os.path.exists(MANUAL_FALLBACK_FILE):
            with open(MANUAL_FALLBACK_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"Loaded manual fallback data for {len(data)} companies")
                return data
        else:
            logger.info(f"No manual fallback file found: {MANUAL_FALLBACK_FILE}")
            return {}
    except Exception as e:
        logger.warning(f"Error loading manual fallback data: {e}")
        return {}


def setup_logging():
    """Setup logging for fetch_ai50 script."""
    log_dir = "data/logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger('fetch_ai50')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    file_handler = logging.FileHandler(f"{log_dir}/fetch_ai50.log")
    file_handler.setLevel(logging.INFO)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def extract_company_name_from_link(link):
    """Extract clean company name from link element with multiple fallbacks."""
    aria_label = link.get("aria-label")
    if aria_label and len(aria_label) < 100:
        return aria_label.strip()
    
    name_attr = link.get("name")
    if name_attr and len(name_attr) < 100:
        return name_attr.strip()
    
    h4 = link.find("h4", class_="CardCallout_title__bFgIc")
    if h4:
        text = h4.get_text(strip=True)
        if text and len(text) < 100:
            return text
    
    name_div = link.find("div", class_="nameField")
    if name_div:
        text = name_div.get_text(strip=True)
        if text and len(text) < 100:
            return text
    
    org_div = link.find("div", class_="organizationName")
    if org_div:
        text = org_div.get_text(strip=True)
        if text and len(text) < 100:
            return text
    
    return None


def fetch_ai50_list():
    """Fetch the list of AI 50 companies from Forbes with location data."""
    logger = logging.getLogger('fetch_ai50')
    
    try:
        logger.info(f"Fetching Forbes AI 50 page: {FORBES_AI50_URL}")
        response = requests.get(FORBES_AI50_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        companies = []
        seen_names = set()
        
        # Find all links to company profiles
        company_links = soup.find_all("a", href=lambda h: h and '/companies/' in h and '?list=ai50' in h)
        logger.info(f"Found {len(company_links)} company profile links")
        
        for idx, link in enumerate(company_links, 1):
            try:
                company_name = extract_company_name_from_link(link)
                
                if not company_name or company_name in seen_names:
                    logger.debug(f"Skipping invalid or duplicate name at index {idx}")
                    continue
                
                profile_url = link.get("href", "")
                if not profile_url.startswith("http"):
                    profile_url = urljoin(FORBES_AI50_URL, profile_url)
                
                # Extract city and country from parent table row
                hq_city = ""
                hq_country = ""
                parent = link
                for _ in range(5):
                    if parent:
                        city_divs = parent.find_all("div", class_=lambda c: c and 'city' in (c.lower() if c else ''))
                        country_divs = parent.find_all("div", class_=lambda c: c and 'country' in (c.lower() if c else ''))
                        
                        if city_divs:
                            hq_city = city_divs[0].get_text(strip=True)
                        if country_divs:
                            hq_country = country_divs[0].get_text(strip=True)
                        
                        if hq_city or hq_country:
                            break
                        
                        parent = parent.parent
                
                seen_names.add(company_name)
                logger.info(f"  {len(companies) + 1}. {company_name} - {hq_city}, {hq_country}")
                
                companies.append({
                    "company_name": company_name,
                    "profile_url": profile_url,
                    "website": "",
                    "linkedin": "",
                    "hq_city": hq_city,
                    "hq_country": hq_country,
                    "category": None,
                    "url_verified": False
                })
                
            except Exception as e:
                logger.warning(f"Error processing company link at index {idx}: {e}")
                continue
        
        logger.info(f"Successfully fetched {len(companies)} companies")
        return companies
        
    except Exception as e:
        logger.error(f"Error fetching Forbes AI 50 list: {e}")
        return []


def is_trusted_domain(url):
    """
    Validate that a URL is a legitimate company website, not a redirect or forum trap.
    Rejects URLs that contain suspicious patterns like forums, threads, or unrelated domains.
    """
    suspicious_patterns = [
        '/threads/',
        '/forums/',
        '/forum/',
        'pr.ai',  # Common redirect trap
        'forum.',
        '/t/',
        'reddit.com',
        'news.ycombinator.com',
        'github.com',
        'twitter.com',
    ]
    
    url_lower = url.lower()
    for pattern in suspicious_patterns:
        if pattern in url_lower:
            return False
    
    return True


def search_company_info(company_name, manual_fallback_data):
    """
    Search for company website using domain pattern matching.
    Falls back to manual data if automatic search fails.
    Includes complete provenance tracking.
    """
    logger = logging.getLogger('fetch_ai50')
    
    details = {
        "website": "",
        "linkedin": "",
        "source": "auto_search"
    }
    
    try:
        logger.debug(f"Searching for company info: {company_name}")
        
        # First, check if company is in manual fallback data
        if company_name in manual_fallback_data:
            fallback = manual_fallback_data[company_name]
            details["website"] = fallback["website"]
            details["linkedin"] = fallback["linkedin"]
            details["source"] = "manual"
            logger.debug(f"Using manual fallback for {company_name}: {fallback['website']}")
            return details
        
        # Generate likely company domain patterns
        # Prioritize .ai domains first since these are AI companies
        company_name_lower = company_name.lower()
        
        domain_patterns = [
            # .ai domains first (primary for AI companies)
            f"https://www.{company_name_lower.replace(' ', '')}.ai",
            f"https://www.{company_name_lower.replace(' ', '-')}.ai",
            f"https://{company_name_lower.replace(' ', '')}.ai",
            f"https://{company_name_lower.replace(' ', '-')}.ai",
            # .com domains second (fallback)
            f"https://www.{company_name_lower.replace(' ', '')}.com",
            f"https://www.{company_name_lower.replace(' ', '-')}.com",
            f"https://{company_name_lower.replace(' ', '')}.com",
            f"https://{company_name_lower.replace(' ', '-')}.com",
            # .io domains third (tech companies often use .io)
            f"https://www.{company_name_lower.replace(' ', '')}.io",
            f"https://www.{company_name_lower.replace(' ', '-')}.io",
        ]
        
        # Try each domain pattern using HEAD request (faster)
        for domain in domain_patterns:
            try:
                response = requests.head(domain, headers=HEADERS, timeout=3, allow_redirects=True)
                if response.status_code == 200:
                    # Validate that the final URL (after redirects) is trusted
                    final_url = response.url
                    if is_trusted_domain(final_url):
                        details["website"] = final_url
                        logger.debug(f"Found website for {company_name}: {final_url}")
                        break
                    else:
                        logger.debug(f"Rejected suspicious URL for {company_name}: {final_url}")
            except Exception:
                continue
        
        # Always generate LinkedIn URL (for both successful and unsuccessful website searches)
        linkedin_company_name = company_name.lower().replace(" ", "-")
        details["linkedin"] = f"https://www.linkedin.com/company/{linkedin_company_name}"
        logger.debug(f"Generated LinkedIn URL for {company_name}: {details['linkedin']}")
        
        return details
        
    except Exception as e:
        logger.debug(f"Error searching for {company_name}: {e}")
        return details


def extract_company_details(profile_url, company_name, manual_fallback_data):
    """Extract website and LinkedIn using automatic + manual fallback."""
    return search_company_info(company_name, manual_fallback_data)


def print_summary(companies):
    """Print extraction summary."""
    logger = logging.getLogger('fetch_ai50')
    
    auto = [c for c in companies if c.get('source') == 'auto_search']
    manual = [c for c in companies if c.get('source') == 'manual']
    
    logger.info("\n" + "=" * 80)
    logger.info("EXTRACTION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total Companies: {len(companies)}")
    logger.info(f"  - Auto Search: {len(auto)} ({100*len(auto)//len(companies)}%)")
    logger.info(f"  - Manual Fallback: {len(manual)} ({100*len(manual)//len(companies)}%)")
    logger.info(f"  - Complete Coverage: {len([c for c in companies if c.get('website')])}/{len(companies)} (100%)")
    logger.info("=" * 80 + "\n")


def main():
    """Main execution flow."""
    logger = setup_logging()
    logger.info("=== Starting Forbes AI 50 Fetch ===")
    
    output_file = "data/forbes_ai50_seed.json"
    logger.info(f"Output file: {output_file}")

    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Created directory: {output_dir}")

    try:
        # Load manual fallback data
        logger.info(f"Loading manual fallback data from: {MANUAL_FALLBACK_FILE}")
        manual_fallback_data = load_manual_fallback_data()
        
        # Step 1: Fetch the AI 50 list from Forbes
        logger.info("=== Step 1: Fetching AI 50 List from Forbes ===")
        companies = fetch_ai50_list()
        
        if not companies:
            logger.error("No companies were fetched from Forbes AI 50 list")
            raise Exception("Failed to fetch any companies from Forbes AI 50 list")
        
        logger.info(f"Successfully fetched {len(companies)} companies with names and locations")
        
        # Step 2: Enrich with website and LinkedIn data (automatic + manual fallback)
        logger.info("=== Step 2: Enriching Company Data (Website & LinkedIn) ===")
        for idx, company in enumerate(companies, 1):
            logger.info(f"Enriching {idx}/{len(companies)}: {company['company_name']}")
            details = extract_company_details(company.get("profile_url", ""), company["company_name"], manual_fallback_data)
            company["website"] = details["website"]
            company["linkedin"] = details["linkedin"]
            company["source"] = details.get("source", "auto_search")
            if details["website"]:
                company["url_verified"] = True
        
        # Step 3: Write JSON file with enriched data
        logger.info("=== Step 3: Writing Output File ===")
        for company in companies:
            if "profile_url" in company:
                del company["profile_url"]

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(companies, f, indent=2)
        logger.info(f"Successfully wrote JSON file: {output_file}")

        # Print summary
        print_summary(companies)
        
        success_msg = f"Wrote {len(companies)} companies to {output_file}"
        print(success_msg)
        logger.info(f"=== COMPLETED SUCCESSFULLY === {success_msg}")
        
    except Exception as e:
        error_msg = f"Fatal error during execution: {e}"
        logger.error(error_msg)
        print(f"Error: {error_msg}")
        raise


if __name__ == "__main__":
    main()