"""Compliant Authorized LinkedIn Adapter.

Adheres strictly to ethical automation:
- Clearly distinguishes between configured vs unconfigured integration states
- Supports authorized partner API, authorized JSON/CSV exports, and student export files
- Does NOT perform unauthorized web scraping, bot automation, or credential harvesting
"""

from backend.collectors.linkedin_collector import LinkedInCollector

# Export LinkedInAdapter as standard adapter class name
class LinkedInAdapter(LinkedInCollector):
    """Adapter for authorized LinkedIn integrations and exports."""
    pass

__all__ = ["LinkedInAdapter", "LinkedInCollector"]
