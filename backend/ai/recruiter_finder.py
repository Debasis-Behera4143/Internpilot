"""Safe recruiter discovery link generator.
Builds tailored search queries without unauthorized or invasive scraping.
"""

import urllib.parse
from typing import Union, Dict, Any


def generate_recruiter_search(job: Union[Dict[str, Any], Any]) -> Dict[str, str]:
    """Generate search URLs for discovering recruiters on LinkedIn via search engines.
    Accepts both legacy job dict and modern Opportunity models.
    """
    if hasattr(job, "title"):
        title = job.title
        company = getattr(job, "company", "")
    else:
        title = job.get("title", "")
        company = job.get("company", "")

    # Create search keywords
    search_term = f"{company} {title}".strip() if company and company != "Unknown" else title

    query = f"{search_term} recruiter LinkedIn"
    encoded_query = urllib.parse.quote(query)
    google_url = f"https://www.google.com/search?q={encoded_query}"

    linkedin_query = urllib.parse.quote(f"{search_term} recruiter site:linkedin.com")
    linkedin_search_url = f"https://www.google.com/search?q={linkedin_query}"

    return {
        "google_search": google_url,
        "linkedin_search": linkedin_search_url
    }
