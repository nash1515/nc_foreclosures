"""
Enrichments module for fetching external property data URLs.

Submodules:
- common: Shared utilities and base classes
- router: Routes to appropriate county enricher
- wake_re: Wake County Real Estate enrichment
- durham_re: Durham County (not implemented)
- harnett_re: Harnett County (not implemented)
- lee_re: Lee County (not implemented)
- orange_re: Orange County (not implemented)
- chatham_re: Chatham County (not implemented)
"""

from enrichments.router import enrich_case

__all__ = ['enrich_case']
