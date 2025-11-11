import os
import requests

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# Set this in your environment:
# export LINKEDIN_ACCESS_TOKEN="your_3_legged_oauth_token_here"
ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN")
print('ACCESS_TOKEN : ' , ACCESS_TOKEN)

if not ACCESS_TOKEN:
    raise RuntimeError("Missing LINKEDIN_ACCESS_TOKEN env var")

BASE_URL = "https://api.linkedin.com/rest"
API_VERSION = "202510"  # use a valid YYYYMM version from docs

COMMON_HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Linkedin-Version": API_VERSION,
    "X-Restli-Protocol-Version": "2.0.0",
    "Content-Type": "application/json",
}

def get_org_by_vanity_name(vanity_name: str) -> dict:
    """
    Look up an organization using its vanity name (the slug in the URL).
    Example:
      https://www.linkedin.com/company/world-labs/
      vanity_name = "world-labs"
    """
    url = f"{BASE_URL}/organizations"
    params = {
        "q": "vanityName",
        "vanityName": vanity_name,
    }

    resp = requests.get(url, headers=COMMON_HEADERS, params=params)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Error fetching org by vanity name: {resp.status_code} {resp.text}"
        )

    data = resp.json()
    elements = data.get("elements", [])
    if not elements:
        raise ValueError(f"No organization found for vanity name '{vanity_name}'")

    # In most cases first match is the correct org; refine if needed.
    return elements[0]


def get_org_by_id(org_id: int) -> dict:
    """
    Fetch detailed organization info by numeric org ID.
    If you are NOT an admin and/or lack required scopes,
    LinkedIn will only return a limited set of fields.
    """
    url = f"{BASE_URL}/organizations/{org_id}"
    resp = requests.get(url, headers=COMMON_HEADERS)

    if resp.status_code == 403:
        raise PermissionError(
            "403 Forbidden: your token does not have sufficient permissions "
            "for this organization's full data."
        )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Error fetching org by id: {resp.status_code} {resp.text}"
        )

    return resp.json()


def get_company_profile(vanity_name: str) -> dict:
    """
    Convenience wrapper:
      1) Resolve org by vanity
      2) Fetch details by ID
      3) Return a normalized profile dict
    """
    org = get_org_by_vanity_name(vanity_name)
    org_id = org.get("id")
    if org_id is None:
        raise RuntimeError(f"No 'id' field returned for {vanity_name}: {org}")

    details = get_org_by_id(org_id)

    # Normalize into something easy for your agent to consume
    profile = {
        "id": org_id,
        "urn": details.get("urn") or f"urn:li:organization:{org_id}",
        "name": details.get("localizedName") or org.get("localizedName"),
        "vanityName": details.get("vanityName") or org.get("vanityName"),
        "website": details.get("localizedWebsite") or org.get("localizedWebsite"),
        "logo": (details.get("logoV2") or org.get("logoV2")),
        "primaryType": details.get("primaryOrganizationType")
                         or org.get("primaryOrganizationType"),
        "locations": details.get("locations") or org.get("locations"),
        # Add more fields here depending on what your token is allowed to see.
    }

    return profile


if __name__ == "__main__":
    # Example usage: replace with the real vanity from the LinkedIn URL
    vanity = "world-labs"  # e.g. for https://www.linkedin.com/company/world-labs/
    try:
        profile = get_company_profile(vanity)
        print(profile)
    except Exception as e:
        print("Error:", e)
